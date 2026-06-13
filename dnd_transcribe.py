import os
import ctypes
from dotenv import load_dotenv
load_dotenv() # Load the .env file immediately

import gc
# SECURITY PATCH: Tell PyTorch 2.6 to trust the local models you just downloaded
os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1" 

import whisperx
import whisperx.asr
import whisperx.diarize
import torch
import time
import datetime
import subprocess
import warnings
import scipy.io.wavfile as wavfile
import winsound

# Suppress annoying pyannote/torchcodec warnings
warnings.filterwarnings("ignore", module="pyannote.audio.core.io")

# RTX 5000 Series (sm_120) Workaround: Disable cuDNN to prevent 'cudnnGetLibConfig Error 127'
torch.backends.cudnn.enabled = False
from tqdm import tqdm
from typing import Optional, Union, List
import numpy as np
from dataclasses import replace
from whisperx.audio import N_SAMPLES, SAMPLE_RATE, load_audio, log_mel_spectrogram
from whisperx.schema import SingleSegment, TranscriptionResult
from whisperx.vads import Vad, Pyannote
from faster_whisper.tokenizer import Tokenizer

# --- HELPER CLASSES & MONKEYPATCHING ---

class WindowsSleepPreventer:
    """Context manager to prevent Windows from sleeping during execution."""
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __enter__(self):
        try:
            # Prevent system sleep
            ctypes.windll.kernel32.SetThreadExecutionState(
                self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
            )
            print("\n[System] Windows sleep mode temporarily disabled for this run.")
        except Exception as e:
            print(f"\n[System] Warning: Could not disable Windows sleep mode: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            # Re-enable system sleep
            ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            print("[System] Windows sleep mode settings restored.")
        except Exception:
            pass

class TqdmList(list):
    """
    A list wrapper that updates a tqdm progress bar when iterated.
    Used to show progress during the alignment phase.
    """
    def __init__(self, iterable, desc, unit="seg"):
        super().__init__(iterable)
        self._tqdm = tqdm(total=len(self), desc=desc, unit=unit)

    def __iter__(self):
        for item in super().__iter__():
            yield item
            self._tqdm.update(1)
        self._tqdm.close()

def custom_transcribe(
    self,
    audio: Union[str, np.ndarray],
    batch_size: Optional[int] = None,
    num_workers=0,
    language: Optional[str] = None,
    task: Optional[str] = None,
    chunk_size=30,
    print_progress=False, # Kept for signature compatibility, but ignored in favor of tqdm
    combined_progress=False, # Kept for signature compatibility
    verbose=False,
) -> TranscriptionResult:
    """
    Monkeypatched version of whisperx.asr.FasterWhisperPipeline.transcribe
    to use tqdm for progress reporting.
    """
    if isinstance(audio, str):
        audio = load_audio(audio)

    def data(audio, segments):
        for seg in segments:
            f1 = int(seg['start'] * SAMPLE_RATE)
            f2 = int(seg['end'] * SAMPLE_RATE)
            # print(f2-f1)
            yield {'inputs': audio[f1:f2]}

    # Pre-process audio and merge chunks as defined by the respective VAD child class 
    if issubclass(type(self.vad_model), Vad):
        waveform = self.vad_model.preprocess_audio(audio)
        merge_chunks =  self.vad_model.merge_chunks
    else:
        waveform = Pyannote.preprocess_audio(audio)
        merge_chunks = Pyannote.merge_chunks

    # Show VAD progress? It's usually fast, but let's just do the main loop.
    print("Performing VAD...")
    vad_segments = self.vad_model({"waveform": waveform, "sample_rate": SAMPLE_RATE})
    vad_segments = merge_chunks(
        vad_segments,
        chunk_size,
        onset=self._vad_params["vad_onset"],
        offset=self._vad_params["vad_offset"],
    )

    if self.tokenizer is None:
        language = language or self.detect_language(audio)
        task = task or "transcribe"
        self.tokenizer = Tokenizer(
            self.model.hf_tokenizer,
            self.model.model.is_multilingual,
            task=task,
            language=language,
        )
    else:
        language = language or self.tokenizer.language_code
        task = task or self.tokenizer.task
        if task != self.tokenizer.task or language != self.tokenizer.language_code:
            self.tokenizer = Tokenizer(
                self.model.hf_tokenizer,
                self.model.model.is_multilingual,
                task=task,
                language=language,
            )

    if self.suppress_numerals:
        previous_suppress_tokens = self.options.suppress_tokens
        # We need to access the module-level function found in asr.py
        # Since we are not in asr.py, we have to duplicate logic or import it.
        # simpler to just assume we don't need to suppress numerals for this specific user case
        # or we can import it if it was exported. It's not exported by default.
        # Let's skip the suppression logic for now or implement a dummy if needed?
        # The user's code just calls load_model -> scribe, likely default options.
        # Checking source of asr.py: find_numeral_symbol_tokens is defined at module level.
        # We can implement it here if needed or just skip it if user doesn't use it.
        # Let's import it from the internal if possible, or copy it.
        # Copying it for safety:
        def find_numeral_symbol_tokens(tokenizer):
            numeral_symbol_tokens = []
            for i in range(tokenizer.eot):
                token = tokenizer.decode([i]).removeprefix(" ")
                has_numeral_symbol = any(c in "0123456789%$£" for c in token)
                if has_numeral_symbol:
                    numeral_symbol_tokens.append(i)
            return numeral_symbol_tokens

        numeral_symbol_tokens = find_numeral_symbol_tokens(self.tokenizer)
        # logger.info("Suppressing numeral and symbol tokens")
        new_suppressed_tokens = numeral_symbol_tokens + self.options.suppress_tokens
        new_suppressed_tokens = list(set(new_suppressed_tokens))
        self.options = replace(self.options, suppress_tokens=new_suppressed_tokens)

    segments: List[SingleSegment] = []
    batch_size = batch_size or self._batch_size
    total_segments = len(vad_segments)
    
    # --- TQDM LOOP ---
    with tqdm(total=total_segments, unit="seg", desc="Transcribing") as pbar:
        for idx, out in enumerate(self.__call__(data(audio, vad_segments), batch_size=batch_size, num_workers=num_workers)):
            pbar.update(1)
            
            text = out['text']
            if batch_size in [0, 1, None]:
                text = text[0]
            if verbose:
                print(f"Transcript: [{round(vad_segments[idx]['start'], 3)} --> {round(vad_segments[idx]['end'], 3)}] {text}")
            segments.append(
                {
                    "text": text,
                    "start": round(vad_segments[idx]['start'], 3),
                    "end": round(vad_segments[idx]['end'], 3)
                }
            )

    # revert the tokenizer if multilingual inference is enabled
    if self.preset_language is None:
        self.tokenizer = None

    # revert suppressed tokens if suppress_numerals is enabled
    if self.suppress_numerals:
        self.options = replace(self.options, suppress_tokens=previous_suppress_tokens)

    return {"segments": segments, "language": language}

# Apply the monkeypatch
whisperx.asr.FasterWhisperPipeline.transcribe = custom_transcribe

# --- CONFIGURATION (NVIDIA RTX Optimized) ---
HF_TOKEN = os.getenv("HF_TOKEN") # Set this in your environment or a .env file
DEVICE_ASR = "cuda"           # Transcription BEST on GPU for NVIDIA
DEVICE_OTHER = "cuda"         # Align/Diarize best on GPU (CUDA) for NVIDIA
BATCH_SIZE = 8                # Lowered from 16 -> 8 to prevent RTX 5060 Ti 8GB Out Of Memory
COMPUTE_TYPE = "float16"         # Best performance and accuracy for modern NVIDIA GPUs (RTX 5060 Ti handles float16 easily)
LOG_FILE = "transcription_metrics.log"

def log_metric(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry) # Also print to console
    with open(LOG_FILE, "a") as f:
        f.write(log_entry + "\n")

class Timer:
    def __init__(self, name):
        self.name = name
        self.start = None
        self.end = None
        self.duration = 0

    def __enter__(self):
        self.start = time.time()
        log_metric(f"--- Starting: {self.name} ---")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end = time.time()
        self.duration = self.end - self.start
        log_metric(f"--- Finished: {self.name} (Duration: {self.format_duration()}) ---")

    def format_duration(self):
        return str(datetime.timedelta(seconds=int(self.duration)))

def run_dnd_session():
    overall_timer = Timer("Total Session")
    overall_timer.__enter__() # Manually start total timer

    file_path = input("Enter path to recording: ").strip()
    if not os.path.exists(file_path):
        print("File not found!")
        return

    print(f"\n--- Auto-detecting Speaker IDs (SPEAKER_00, SPEAKER_01, etc.) ---")
    print(f"You will be prompted to identify unknown speakers interactively.")

    # Normalization (Standard)
    normalize_audio = True

    # Diarization Device Prompt (Diarization on CPU is only needed as a fallback for VRAM/CUDA limits)
    run_on_cpu = input("Run Diarization on CPU instead of GPU? (Only recommended if you experience GPU/CUDA errors) [y/N]: ").strip().lower() == 'y'
    device_diarize = "cpu" if run_on_cpu else DEVICE_OTHER
    
    print(f"\n--- Processing Locally on NVIDIA GPU ---")

    # 0. Preprocess Audio (Dynamic Normalization via FFmpeg)
    temp_file_path = None
    process_file_path = file_path
    
    if normalize_audio:
        temp_file_path = os.path.splitext(file_path)[0] + "_normalizedTemp.wav"
        print("\n--- Preprocessing Audio (Dynamic Normalization) ---")
        with Timer("Audio Normalization") as t_norm:
            # dynaudnorm: dynamic audio normalizer. f=150 (frame length), g=15 (Gaussian filter window)
            # -y overwrites without asking
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", file_path, 
                "-af", "dynaudnorm=f=150:g=15", 
                "-c:a", "pcm_f32le", 
                temp_file_path
            ]
            try:
                # shell=True helps resolve winget "Links" folder alias on Windows
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
                process_file_path = temp_file_path
                log_metric("Audio normalization complete.")
            except FileNotFoundError:
                print("\n[ERROR] FFmpeg not found. Skipping normalization.")
                print("Please install FFmpeg and add it to your system PATH to use this feature.\n")
                process_file_path = file_path
                temp_file_path = None
            except subprocess.CalledProcessError as e:
                print(f"\n[ERROR] FFmpeg failed during normalization: {e}")
                print("Skipping normalization.\n")
                process_file_path = file_path
                temp_file_path = None

    # 1. Transcribe (Model is already cached on your 8TB drive!)
    with Timer("Loading & Transcription") as t_transcribe:
        model = whisperx.load_model("large-v3-turbo", DEVICE_ASR, compute_type=COMPUTE_TYPE)
        audio = whisperx.load_audio(process_file_path)
        
        audio_duration = len(audio) / SAMPLE_RATE
        log_metric(f"Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}")
        
        result = model.transcribe(audio, batch_size=BATCH_SIZE, language="en")
        
    # Free up VRAM used by the massive transcription model before moving to alignment
    del model
    gc.collect()
    torch.cuda.empty_cache()
    
    # 2. Align & Diarize (THE FIX IS HERE: whisperx.diarize)
    with Timer("Alignment") as t_align:
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=DEVICE_OTHER)
        
        # Wrap segments in TqdmList for alignment progress
        result["segments"] = TqdmList(result["segments"], desc="Aligning", unit="seg")
        
        result = whisperx.align(result["segments"], model_a, metadata, audio, DEVICE_OTHER)
        
    # Free up VRAM from the alignment model before starting the diarization pipeline
    del model_a
    gc.collect()
    torch.cuda.empty_cache()
    
    # Since TqdmList was exhausted by align, we might need it back as a regular list if we use it again, 
    # but whisperx.align returns a new dictionary with new segments, so we are good.

    print("\n--- Diarizing (Progress bar unavailable for this step) ---")

    # Use the new sub-module path for diarization
    with Timer("Diarization") as t_diarize:
        if device_diarize == "cpu":
            print(">> Running Diarization on CPU...")
        diarize_model = whisperx.diarize.DiarizationPipeline(token=HF_TOKEN, device=device_diarize)
        diarize_segments = diarize_model(audio)
        
    # Free up VRAM one more time
    del diarize_model
    gc.collect()
    torch.cuda.empty_cache()
    
    # 3. Final Merge
    with Timer("Merge & Save") as t_merge:
        final_result = whisperx.assign_word_speakers(diarize_segments, result)
        
        # --- CONTINUOUS SPEAKER RECOGNITION (VOICE HARVESTING) ---
        print("\n--- Identifying Speakers vs Voice Library ---")
        try:
            import glob
            from scipy.spatial.distance import cosine
            from pyannote.audio import Model, Inference
            
            hf_token_lib = os.getenv("HF_TOKEN")
            voice_files = glob.glob(os.path.join("voice_library", "*.npy"))
            
            if voice_files:
                library_models = {}
                for vf in voice_files:
                    name = os.path.splitext(os.path.basename(vf))[0]
                    library_models[name] = np.load(vf)
                    
                print(f"Loaded {len(library_models)} voices from voice_library/")
                
                # Load Pyannote Embedding model
                emb_model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=hf_token_lib)
                if not emb_model:
                     emb_model = Model.from_pretrained("pyannote/embedding", use_auth_token=hf_token_lib)
                
                device_emb = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                emb_model.to(device_emb)
                inference = Inference(emb_model, window="whole")
                
                # Group segments by SPEAKER_XX
                speaker_chunks = {}
                for seg in final_result["segments"]:
                    spk = seg.get("speaker", "UNKNOWN")
                    if spk.startswith("SPEAKER_"):
                        if spk not in speaker_chunks:
                            speaker_chunks[spk] = []
                        speaker_chunks[spk].append((seg["start"], seg["end"]))
                        
                speaker_mapping = {}
                # Calculate embeddings for each unknown speaker
                for spk, chunks in speaker_chunks.items():
                    chunks.sort(key=lambda x: x[1] - x[0], reverse=True)
                    spk_embeds = []
                    total_dur = 0.0
                    for c_start, c_end in chunks:
                        dur = c_end - c_start
                        if dur < 1.0: continue
                        
                        s_samp = int(c_start * SAMPLE_RATE)
                        e_samp = int(c_end * SAMPLE_RATE)
                        c_audio = audio[s_samp:e_samp]
                        t_chunk = torch.from_numpy(c_audio).unsqueeze(0)
                        
                        try:
                            emb = inference({"waveform": t_chunk, "sample_rate": SAMPLE_RATE})
                            spk_embeds.append(emb)
                            total_dur += dur
                            if total_dur > 20.0: break # Use max 20 seconds of pure speech audio for identification
                        except Exception as e:
                            pass
                            
                    if spk_embeds:
                        avg_emb = np.mean(spk_embeds, axis=0)
                        # Compare against library
                        best_match = None
                        best_score = -1.0
                        for lib_name, lib_emb in library_models.items():
                            # cosine function from scipy returns distance (0 is identical)
                            # similarity score is 1 - distance
                            sim = 1.0 - cosine(avg_emb.flatten(), lib_emb.flatten())
                            if sim > best_score:
                                best_score = sim
                                best_match = lib_name
                                
                        # Confidence threshold: 0.90 is strict enough to avoid ambiguous/false matches
                        if best_score > 0.90 and best_match:
                            print(f"[Match] Reassigned {spk} -> {best_match} (Similarity: {round(best_score*100, 1)}%)")
                            speaker_mapping[spk] = best_match
                        else:
                            if best_match and best_score > 0.40:
                                best_str = f"Ambiguous match with {best_match} at {round(best_score*100, 1)}%"
                            else:
                                best_str = f"Best was {best_match} at {round(best_score*100, 1)}%" if best_match else "No library match"
                            
                            print(f"\n[No Match] {spk} remains unknown ({best_str})")
                            
                            # Interactive Prompt Setup
                            # Find the longest continuous chunk for this speaker to play back
                            best_chunk = chunks[0]
                            st_samp = int(best_chunk[0] * SAMPLE_RATE)
                            # Limit playback to max 8 seconds
                            playback_dur = min(8.0, best_chunk[1] - best_chunk[0])
                            en_samp = st_samp + int(playback_dur * SAMPLE_RATE)
                            
                            playback_audio = audio[st_samp:en_samp]
                            temp_playback_file = "temp_playback.wav"
                            
                            # whisperx audio is float32 [-1.0, 1.0]. Convert to int16 for winsound compat
                            scaled_audio = np.int16(playback_audio * 32767)
                            wavfile.write(temp_playback_file, SAMPLE_RATE, scaled_audio)
                            
                            while True:
                                print(f"Playing audio sample for {spk}...")
                                winsound.PlaySound(temp_playback_file, winsound.SND_FILENAME)
                                
                                user_input = input(f"Who is speaking? (Type name, press Enter to keep as {spk}, type 'replay' to listen again): ").strip()
                                
                                if user_input.lower() == 'replay':
                                    continue
                                elif user_input == "":
                                    print(f"Leaving as {spk}")
                                    break
                                else:
                                    # User provided a name!
                                    safe_name = "".join([c for c in user_input if c.isalpha() or c.isdigit()]).rstrip()
                                    speaker_mapping[spk] = safe_name
                                    print(f"Assigned {spk} -> {safe_name}")
                                    
                                    # Train the model instantly for this new name using the avg_emb we just calculated
                                    out_file = os.path.join("voice_library", f"{safe_name}.npy")
                                    os.makedirs("voice_library", exist_ok=True)
                                    
                                    if os.path.exists(out_file):
                                        print(f"  -> Found existing profile for {safe_name}. Refining voice print...")
                                        old_embedding = np.load(out_file)
                                        # Average the old and new embeddings
                                        avg_emb = (old_embedding + avg_emb) / 2.0
                                        
                                    np.save(out_file, avg_emb)
                                    print(f"  -> Saved {out_file} (Harvested {round(total_dur, 1)} seconds of speech)")
                                    
                                    # Dynamically update the in-memory library so it can be used for subsequent unknown speakers in THIS run
                                    library_models[safe_name] = avg_emb
                                    break
                                    
                            # Cleanup playback file
                            if os.path.exists(temp_playback_file):
                                os.remove(temp_playback_file)
                            
                # Apply mapping
                for seg in final_result["segments"]:
                    spk = seg.get("speaker", "UNKNOWN")
                    if spk in speaker_mapping:
                        seg["speaker"] = speaker_mapping[spk]
                        
                # Free VRAM
                del emb_model
                gc.collect()
                torch.cuda.empty_cache()
            else:
                print("No voices found in voice_library/. Skipping identification.")
                
        except Exception as e:
            print(f"Error during speaker identification: {e}")
            
        print("\n--- Writing Markdown ---")
        orig_name = os.path.basename(process_file_path)
        # Handle original temp normalization
        if temp_file_path and process_file_path == temp_file_path:
            orig_name = os.path.basename(file_path)
            
        output_filename = os.path.join("transcripts", os.path.splitext(orig_name)[0] + "_session_log.md")
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(f"# D&D Session Transcript\n\n")
            f.write(f"> Processed on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"> Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}\n\n")
            
            for segment in final_result["segments"]:
                speaker_id = segment.get("speaker", "UNKNOWN")
                
                # Create nice [0:01:23 - 0:01:45] timestamps
                st_str = str(datetime.timedelta(seconds=int(segment['start'])))
                et_str = str(datetime.timedelta(seconds=int(segment['end'])))
                
                f.write(f"[{st_str} - {et_str}] **{speaker_id}**: {segment['text'].strip()}  \n")

    # 4. Cleanup
    if temp_file_path and os.path.exists(temp_file_path):
        os.remove(temp_file_path)
        log_metric("Temporary normalized audio file removed.")

    overall_timer.__exit__(None, None, None) # Stop total timer

    # Print Summary Table
    print("\n" + "="*50)
    print(f"{'Phase':<25} | {'Duration':<15}")
    print("-" * 50)
    print(f"{'Transcription':<25} | {t_transcribe.format_duration():<15}")
    print(f"{'Alignment':<25} | {t_align.format_duration():<15}")
    print(f"{'Diarization':<25} | {t_diarize.format_duration():<15}")
    print(f"{'Merge & Save':<25} | {t_merge.format_duration():<15}")
    print("-" * 50)
    print(f"{'Total Runtime':<25} | {overall_timer.format_duration():<15}")
    print("="*50 + "\n")

    print(f"\nSuccess! Transcript saved to: {output_filename}")


# --- VOICE HARVESTING (LIBRARY CREATION) ---

def time_str_to_seconds(time_str):
    import re
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = [int(p) for p in parts]
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = [int(p) for p in parts]
        return m * 60 + s
    return 0

def parse_markdown_for_speakers(md_path):
    import re
    speaker_segments = {}
    pattern = re.compile(r'^\[(\d{1,2}:\d{2}:\d{2}) - (\d{1,2}:\d{2}:\d{2})\] \*\*(.+?)\*\*:')
    
    with open(md_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                start_str, end_str, speaker = match.groups()
                start_sec = time_str_to_seconds(start_str)
                end_sec = time_str_to_seconds(end_str)
                
                if speaker.startswith("SPEAKER_"):
                    continue
                    
                if speaker not in speaker_segments:
                    speaker_segments[speaker] = []
                speaker_segments[speaker].append((start_sec, end_sec))
    return speaker_segments

def train_voices(md_path, audio_path):
    if not os.path.exists(md_path) or not os.path.exists(audio_path):
        print("Error: Markdown or audio file not found.")
        return
        
    os.makedirs("voice_library", exist_ok=True)
    speaker_segments = parse_markdown_for_speakers(md_path)
    
    if not speaker_segments:
        print("No valid named speakers found. Did you edit the SPEAKER_XX tags and leave the timestamps?")
        return
        
    print(f"Found {len(speaker_segments)} unique named speakers.")
    
    HF_TOKEN = os.getenv("HF_TOKEN")
    from pyannote.audio import Model, Inference
    
    print("Loading PyAnnote Embedding Model...")
    model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=HF_TOKEN)
    if not model:
        model = Model.from_pretrained("pyannote/embedding", use_auth_token=HF_TOKEN)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    inference = Inference(model, window="whole")
    
    print(f"Loading Audio {audio_path}...")
    audio_data = whisperx.audio.load_audio(audio_path)
    
    for speaker, segments in speaker_segments.items():
        print(f"\nProcessing embeddings for: {speaker}")
        speaker_embeddings = []
        total_duration = 0.0
        segments.sort(key=lambda x: x[1] - x[0], reverse=True)
        
        for start_sec, end_sec in segments:
            duration = end_sec - start_sec
            if duration < 1.0: continue
                
            start_sample = int(start_sec * whisperx.audio.SAMPLE_RATE)
            end_sample = int(end_sec * whisperx.audio.SAMPLE_RATE)
            chunk_audio = audio_data[start_sample:end_sample]
            tensor_chunk = torch.from_numpy(chunk_audio).unsqueeze(0)
            
            try:
                emb = inference({"waveform": tensor_chunk, "sample_rate": 16000})
                speaker_embeddings.append(emb)
                total_duration += duration
                if total_duration > 20.0: break
            except Exception as e:
                pass
                
        if speaker_embeddings:
            avg_embedding = np.mean(speaker_embeddings, axis=0)
            safe_name = "".join([c for c in speaker if c.isalpha() or c.isdigit()]).rstrip()
            out_file = os.path.join("voice_library", f"{safe_name}.npy")
            
            if os.path.exists(out_file):
                print(f"  -> Found existing profile for {speaker}. Refining voice print...")
                old_embedding = np.load(out_file)
                # Average the old and new embeddings to refine over time
                avg_embedding = (old_embedding + avg_embedding) / 2.0
                
            np.save(out_file, avg_embedding)
            print(f"  -> Saved {out_file} (Harvested {round(total_duration, 1)} seconds)")
        else:
            print(f"  -> Failed to harvest audio for {speaker}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D&D Transcription and Voice Training")
    parser.add_argument("--train", action="store_true", help="Harvest voices from an annotated markdown transcript to build the voice_library.")
    parser.add_argument("--md", type=str, help="Path to the edited markdown (.md) file (for --train)")
    parser.add_argument("--audio", type=str, help="Path to the original audio (.wav) file (for --train)")
    
    args = parser.parse_args()
    
    with WindowsSleepPreventer():
        if args.train:
            if not args.md or not args.audio:
                print("Error: --train requires both --md and --audio arguments.")
            else:
                train_voices(args.md, args.audio)
        else:
            run_dnd_session()