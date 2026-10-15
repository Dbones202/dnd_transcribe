import os
import re
import numpy as np
import torch
from dotenv import load_dotenv
import argparse
import datetime

load_dotenv()

# We only import the heavy audio models when this script actually needs them
from pyannote.audio import Model, Inference
from pyannote.core import Segment
import whisperx.audio

def time_str_to_seconds(time_str):
    # Formats like 0:01:23 or 01:23:45
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = [int(p) for p in parts]
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = [int(p) for p in parts]
        return m * 60 + s
    return 0

def normalize_embedding(emb):
    if emb is None:
        return emb
    norm = np.linalg.norm(emb)
    if norm > 1e-12:
        return emb / norm
    return emb

def parse_speaker_choice(chosen_info):
    raw = str(chosen_info or "").strip()
    if not raw:
        return "", "", False
    is_bg = False
    if re.search(r'(?:\b|_|\(|\[)bg(?:\b|_|\)|\])', raw, re.IGNORECASE):
        is_bg = True
        raw = re.sub(r'[\(\[]\s*bg\s*[\)\]]', '', raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r'\s+bg\b', '', raw, flags=re.IGNORECASE).strip()

    persona = ""
    m_paren = re.match(r'^([^\(\/]+?)\s*[\(\/]\s*([^\)]+?)\s*\)?$', raw)
    if m_paren:
        base = m_paren.group(1).strip()
        persona = m_paren.group(2).strip()
    elif "__" in raw:
        parts = raw.split("__", 1)
        base = parts[0].strip()
        persona = parts[1].strip()
    else:
        base = raw.strip()

    safe_base = re.sub(r'[^a-zA-Z0-9]', '', base)
    safe_persona = re.sub(r'[^a-zA-Z0-9]', '', persona)

    if not safe_base:
        return "", "", False

    if safe_persona:
        model_key = f"{safe_base}__{safe_persona}"
        display_name = f"{safe_base} ({safe_persona})"
    else:
        model_key = safe_base
        display_name = safe_base

    if is_bg:
        display_name = f"{display_name} (bg)"

    return display_name, model_key, is_bg

def parse_markdown_for_speakers(md_path):
    """
    Parses a markdown file and returns a dictionary of:
    { "SpeakerName": [ (start_sec, end_sec), ... ], ... }
    """
    speaker_segments = {}
    
    # Regex to match: [0:01:23 - 0:01:45] **Donovan**: Hello there!
    # Or: [00:01:23 - 00:01:45] **Donovan**:
    pattern = re.compile(r'^\[(\d{1,2}:\d{2}:\d{2}) - (\d{1,2}:\d{2}:\d{2})\] \*\*(.+?)\*\*:')
    
    with open(md_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                start_str, end_str, speaker = match.groups()
                start_sec = time_str_to_seconds(start_str)
                end_sec = time_str_to_seconds(end_str)
                
                spk_clean = speaker.strip()
                # Ignore generic SPEAKER_XX labels from training
                if spk_clean.startswith("SPEAKER_"):
                    continue
                # Ignore unverified best guesses from training
                if re.search(r'(?:\b|_|\(|\[)bg(?:\b|_|\)|\])', spk_clean, re.IGNORECASE):
                    continue
                    
                if spk_clean not in speaker_segments:
                    speaker_segments[spk_clean] = []
                speaker_segments[spk_clean].append((start_sec, end_sec))
                
    return speaker_segments

def main():
    parser = argparse.ArgumentParser(description="Harvest Voices from an annotated Markdown Transcript")
    parser.add_argument("markdown_file", help="Path to the edited markdown (.md) file")
    parser.add_argument("audio_file", help="Path to the original audio (.wav) file")
    args = parser.parse_args()
    
    md_path = args.markdown_file
    audio_path = args.audio_file
    
    if not os.path.exists(md_path):
        print(f"Error: Markdown file {md_path} not found.")
        return
        
    if not os.path.exists(audio_path):
        print(f"Error: Audio file {audio_path} not found.")
        return
        
    os.makedirs("voice_library", exist_ok=True)
    
    print(f"Parsing {md_path}...")
    speaker_segments = parse_markdown_for_speakers(md_path)
    
    if not speaker_segments:
        print("No valid named speakers found in the markdown. Did you edit the SPEAKER_XX tags and leave the timestamps?")
        return
        
    print(f"Found {len(speaker_segments)} unique named speakers to harvest.")
    
    HF_TOKEN = os.getenv("HF_TOKEN")
    if not HF_TOKEN:
        print("Error: HF_TOKEN not found in .env file.")
        return
        
    print("Loading PyAnnote Embedding Model...")
    # This is the industry standard 3.0 embedding model
    model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=HF_TOKEN)
    if not model:
        # Fallback to older embedding if wespeaker fails
        model = Model.from_pretrained("pyannote/embedding", use_auth_token=HF_TOKEN)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    inference = Inference(model, window="whole")
    
    # We load the whole audio array to pass crop segments to pyannote
    print(f"Loading Audio {audio_path}...")
    # WhisperX load_audio returns a standard numpy array at 16000Hz
    audio_data = whisperx.audio.load_audio(audio_path)
    
    for speaker, segments in speaker_segments.items():
        print(f"\nProcessing embeddings for: {speaker}")
        speaker_embeddings = []
        total_duration = 0.0
        
        # Sort by longest segments to get the most continuous speech data
        segments.sort(key=lambda x: x[1] - x[0], reverse=True)
        
        for start_sec, end_sec in segments:
            duration = end_sec - start_sec
            if duration < 1.0:
                continue # Skip tiny coughs/sounds
                
            # PyAnnote Inference expects a standard dict format
            start_sample = int(start_sec * whisperx.audio.SAMPLE_RATE)
            end_sample = int(end_sec * whisperx.audio.SAMPLE_RATE)
            chunk_audio = audio_data[start_sample:end_sample]
            
            # Format as (Channels, Samples)
            tensor_chunk = torch.from_numpy(chunk_audio).unsqueeze(0)
            
            try:
                emb = inference({"waveform": tensor_chunk, "sample_rate": 16000})
                speaker_embeddings.append(normalize_embedding(emb))
                total_duration += duration
                
                # ~15-20 seconds of pure audio is generally plenty for a solid voice print
                if total_duration > 20.0:
                    break
            except Exception as e:
                print(f"  Error processing chunk for {speaker}: {e}")
                
        if speaker_embeddings:
            avg_embedding = np.mean(speaker_embeddings, axis=0)
            avg_embedding = normalize_embedding(avg_embedding)
            
            display_name, model_key, _ = parse_speaker_choice(speaker)
            if not model_key:
                model_key = "".join([c for c in speaker if c.isalnum() or c == '_'])
                display_name = speaker
                
            out_file = os.path.join("voice_library", f"{model_key}.npy")
            if os.path.exists(out_file):
                print(f"  -> Refining existing profile for {display_name} (weighted blend)...")
                old_emb = normalize_embedding(np.load(out_file))
                avg_embedding = normalize_embedding(0.7 * old_emb + 0.3 * avg_embedding)
            else:
                print(f"  -> Creating new profile for {display_name}...")
                
            np.save(out_file, avg_embedding)
            print(f"  -> Saved {out_file} (Harvested {round(total_duration, 1)} seconds of speech)")
        else:
            print(f"  -> Failed to harvest sufficient audio for {speaker}")

if __name__ == "__main__":
    main()
