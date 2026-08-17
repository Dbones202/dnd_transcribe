import os
import sys

# Ensure venv/Scripts (containing ffmpeg) is always present in PATH for subprocess calls
_script_dir = os.path.dirname(os.path.abspath(__file__))
_venv_scripts = os.path.join(_script_dir, "venv", "Scripts")
if os.path.exists(_venv_scripts) and _venv_scripts not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _venv_scripts + os.pathsep + os.environ.get("PATH", "")

import ctypes
import json
import urllib.request
import urllib.error
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

def generate_ai_diff(
    raw_lines: List[str],
    refined_lines: List[str],
    diff_output_path: str,
    session_name: str,
    duration_str: str = "",
    batch_stats: dict = None
) -> dict:
    """
    Compares raw and refined transcript lines, computes change metrics,
    and writes a Markdown diff/evaluation report.
    """
    import re
    
    total_lines = max(len(raw_lines), len(refined_lines))
    modified_lines = []
    
    pattern = re.compile(r'^(\[\d{1,2}:\d{2}:\d{2} - \d{1,2}:\d{2}:\d{2}\])\s*\*\*(.+?)\*\*:\s*(.*)$')
    
    for idx in range(min(len(raw_lines), len(refined_lines))):
        raw = raw_lines[idx].strip()
        ref = refined_lines[idx].strip()
        
        if raw != ref:
            raw_match = pattern.match(raw)
            ref_match = pattern.match(ref)
            
            raw_spk = raw_match.group(2) if raw_match else "Unknown"
            ref_spk = ref_match.group(2) if ref_match else "Unknown"
            raw_text = raw_match.group(3) if raw_match else raw
            ref_text = ref_match.group(3) if ref_match else ref
            ts = raw_match.group(1) if raw_match else (ref_match.group(1) if ref_match else f"Line {idx+1}")
            
            # If speaker names differ, include speaker in the change cell
            if raw_spk != ref_spk:
                before_cell = f"**{raw_spk}**: {raw_text}"
                after_cell = f"**{ref_spk}**: {ref_text}"
                spk_header = f"{raw_spk} -> {ref_spk}"
            else:
                before_cell = raw_text
                after_cell = ref_text
                spk_header = raw_spk
            
            modified_lines.append({
                "line_num": idx + 1,
                "timestamp": ts,
                "speaker_info": spk_header,
                "before": before_cell,
                "after": after_cell
            })
            
    # Check for line count differences
    if len(raw_lines) != len(refined_lines):
        diff_len = abs(len(raw_lines) - len(refined_lines))
        note = f"⚠️ Line count mismatch: Raw has {len(raw_lines)} lines, Refined has {len(refined_lines)} lines ({diff_len} line delta)."
    else:
        note = "✅ Line counts match identically (100% line alignment preserved)."

    num_modified = len(modified_lines)
    pct_modified = (num_modified / total_lines * 100) if total_lines > 0 else 0.0
    
    os.makedirs(os.path.dirname(os.path.abspath(diff_output_path)), exist_ok=True)
    with open(diff_output_path, "w", encoding="utf-8") as f:
        f.write(f"# AI Refinement Evaluation & Diff Report\n\n")
        f.write(f"> **Session**: `{session_name}`  \n")
        f.write(f"> **Date**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        if duration_str:
            f.write(f"> **AI Processing Duration**: {duration_str}  \n")
        f.write(f"\n## Summary Metrics\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"| :--- | :--- |\n")
        f.write(f"| **Total Dialogue Lines** | {total_lines} |\n")
        f.write(f"| **Lines Modified by AI** | {num_modified} ({pct_modified:.1f}%) |\n")
        f.write(f"| **Lines Unchanged** | {total_lines - num_modified} ({(100 - pct_modified):.1f}%) |\n")
        if batch_stats:
            f.write(f"| **Batches Completed** | {batch_stats.get('completed', 0)} / {batch_stats.get('total', 0)} |\n")
            f.write(f"| **Mismatched / Discarded Batches** | {batch_stats.get('failed', 0)} |\n")
        f.write(f"| **Integrity Check** | {note} |\n\n")
        
        f.write(f"## Detailed Line-by-Line Changes\n\n")
        if modified_lines:
            f.write(f"| Line # | Time & Speaker | Before AI (Raw) | After AI (Refined) |\n")
            f.write(f"| :--- | :--- | :--- | :--- |\n")
            for item in modified_lines:
                raw_clean = item['before'].replace('|', '\\|')
                ref_clean = item['after'].replace('|', '\\|')
                f.write(f"| {item['line_num']} | {item['timestamp']} **{item['speaker_info']}** | {raw_clean} | {ref_clean} |\n")
        else:
            f.write(f"_No lines were altered by the AI._\n")

    print(f"\n[AI Evaluation] Diff report written to: {diff_output_path}")
    print(f"  -> Modified {num_modified}/{total_lines} lines ({pct_modified:.1f}%)")
    
    return {
        "total_lines": total_lines,
        "num_modified": num_modified,
        "pct_modified": pct_modified,
        "modified_lines": modified_lines
    }

def refine_transcript_with_llm(
    formatted_lines: List[str], 
    api_url: str = None,
    batch_size: int = 50
) -> tuple[List[str], dict]:
    """
    Optional post-processing pass using local LLM (e.g. Gemma / Llama via LM Studio REST API)
    to refine D&D terms, homophones, punctuation, and stutter artifacts without altering verbatim meaning or line structure.
    Returns (refined_lines, batch_stats).
    """
    if not api_url:
        api_url = os.getenv("LLM_API_URL", "http://localhost:1234/v1")
        
    endpoint = f"{api_url.rstrip('/')}/chat/completions"
    
    stats = {
        "total": (len(formatted_lines) + batch_size - 1) // batch_size if formatted_lines else 0,
        "completed": 0,
        "failed": 0
    }
    
    # 1. Health check to test if LM Studio server is online AND a model is loaded
    try:
        req = urllib.request.Request(f"{api_url.rstrip('/')}/models", method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status != 200:
                print(f"\n[LM Studio WARNING] Server reachable at {api_url} but returned status {resp.status}.")
                print("  -> Please verify LM Studio server status. Skipping LLM refinement.\n")
                return formatted_lines, stats
            
            res_body = json.loads(resp.read().decode("utf-8"))
            models_data = res_body.get("data", [])
            if not models_data:
                print(f"\n[LM Studio WARNING] Local LLM server detected at {api_url}, but NO MODEL IS LOADED!")
                print("  -> Please load a model (e.g. Gemma, Llama 3) inside LM Studio.")
                print("  -> Skipping LLM refinement for this session.\n")
                return formatted_lines, stats
            
            loaded_model_id = models_data[0].get("id", "Unknown Model")
            print(f"\n[LM Studio] Connected to local server. Loaded model: '{loaded_model_id}'")

    except Exception as e:
        print(f"\n[LM Studio WARNING] Local LLM server not detected at {api_url}.")
        print("  -> Please start the LM Studio server (Developer -> Local Server) and load a model.")
        print("  -> Skipping LLM refinement for this session.\n")
        return formatted_lines, stats

    print("\n--- Refining Transcript with Local LLM (LM Studio) ---")
    print(f"[NOTICE] Processing {stats['total']} batches (Batch size: {batch_size} lines)...")
    print("[NOTICE] Batch HTTP timeout is set to 300s (5 minutes).\n")
    
    system_prompt = (
        "You are an expert editor for Dungeons & Dragons tabletop session audio transcripts.\n"
        "Your task is to refine the provided transcript lines for accuracy:\n"
        "1. Correct mis-transcribed D&D vocabulary, spell names, character names, and homophones "
        "(e.g., 'man to core' -> 'manticore', 'tea fling' -> 'tiefling', 'elder itch' -> 'Eldritch').\n"
        "2. Fix missing punctuation, capitalization, and remove hallucinated audio repetitions (e.g., 'the the the').\n"
        "3. STRICT RULE: Keep every timestamp '[HH:MM:SS - HH:MM:SS]' and speaker tag '**Speaker Name**:' EXACTLY unchanged.\n"
        "4. STRICT RULE: Do NOT summarize, drop, or alter the core meaning of any line. Keep the line count and line order identical.\n"
        "Output ONLY the corrected transcript lines."
    )

    refined_lines = []
    total_batches = stats['total']
    
    for i in range(0, len(formatted_lines), batch_size):
        batch_num = i // batch_size + 1
        chunk = formatted_lines[i:i + batch_size]
        prompt_content = "\n".join(chunk)
        
        print(f"  -> Processing batch {batch_num}/{total_batches} ({len(chunk)} lines)... (Waiting for LLM response)")
        
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Refine these transcript lines:\n\n{prompt_content}"}
            ],
            "temperature": 0.1,
            "max_tokens": 4096
        }
        
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                endpoint, 
                data=req_data, 
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=300.0) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
                output_text = res_body["choices"][0]["message"]["content"].strip()
                
                output_lines = [l for l in output_text.splitlines() if l.strip()]
                if len(output_lines) == len(chunk):
                    refined_lines.extend(output_lines)
                    stats['completed'] += 1
                    print(f"     Batch {batch_num}/{total_batches} completed successfully.")
                else:
                    print(f"  [LLM Warning] Line count mismatch in batch {batch_num} (expected {len(chunk)}, got {len(output_lines)}). Keeping raw chunk.")
                    refined_lines.extend(chunk)
                    stats['failed'] += 1
        except urllib.error.HTTPError as e:
            if e.code == 400:
                print(f"  [LLM Error] Batch {batch_num} failed (HTTP 400 Bad Request): Ensure a model is loaded in LM Studio. Keeping raw chunk.")
            else:
                print(f"  [LLM Error] Batch {batch_num} failed with HTTP {e.code}: {e.reason}. Keeping raw chunk.")
            refined_lines.extend(chunk)
            stats['failed'] += 1
        except Exception as e:
            print(f"  [LLM Error] Failed to refine batch {batch_num}: {e}. Keeping raw chunk.")
            refined_lines.extend(chunk)
            stats['failed'] += 1
            
    print(f"[LM Studio] LLM refinement complete ({stats['completed']}/{total_batches} successful batches).")
    return refined_lines, stats

def refine_existing_transcript(
    md_path: str, 
    api_url: str = None, 
    batch_size: int = 50
):
    """
    Standalone function to refine an existing raw markdown transcript file,
    produce a refined version, and generate a diff/evaluation report.
    """
    import re
    if not os.path.exists(md_path):
        print(f"Error: Transcript file '{md_path}' not found.")
        return
        
    print(f"\n--- Loading Transcript: {md_path} ---")
    headers = []
    dialogue_lines = []
    pattern = re.compile(r'^\[\d{1,2}:\d{2}:\d{2} - \d{1,2}:\d{2}:\d{2}\]')
    
    with open(md_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.rstrip()
            if pattern.search(stripped):
                dialogue_lines.append(stripped)
            elif not dialogue_lines:
                headers.append(stripped)
                
    if not dialogue_lines:
        print("Error: No timestamped dialogue lines found in the file.")
        return
        
    print(f"Found {len(dialogue_lines)} dialogue lines to refine.")
    
    base_name = os.path.splitext(os.path.basename(md_path))[0]
    # Strip existing _raw or _session_log suffixes for clean naming
    clean_base = base_name.replace("_session_log_raw", "").replace("_session_log_refined", "").replace("_raw", "")
    
    out_dir = os.path.dirname(os.path.abspath(md_path))
    refined_path = os.path.join(out_dir, f"{clean_base}_session_log_refined.md")
    diff_path = os.path.join(out_dir, f"{clean_base}_ai_diff.md")
    
    start_time = time.time()
    refined_lines, stats = refine_transcript_with_llm(dialogue_lines, api_url=api_url, batch_size=batch_size)
    duration_str = str(datetime.timedelta(seconds=int(time.time() - start_time)))
    
    # Save refined transcript
    with open(refined_path, 'w', encoding='utf-8') as f:
        if headers:
            for h in headers:
                f.write(f"{h}\n")
            f.write("\n")
        else:
            f.write(f"# D&D Session Transcript (Refined)\n\n")
            f.write(f"> Refined on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        for line in refined_lines:
            f.write(f"{line}  \n")
            
    print(f"Refined transcript saved to: {refined_path}")
    
    # Generate Diff Report
    generate_ai_diff(
        raw_lines=dialogue_lines,
        refined_lines=refined_lines,
        diff_output_path=diff_path,
        session_name=clean_base,
        duration_str=duration_str,
        batch_stats=stats
    )

def run_dnd_session(audio_path=None, skip_llm=False, batch_size=50):
    overall_timer = Timer("Total Session")
    overall_timer.__enter__() # Manually start total timer

    if not audio_path:
        file_path = input("Enter path to recording: ").strip()
    else:
        file_path = audio_path.strip()

    file_path = file_path.strip('"\'')

    if not file_path or not os.path.exists(file_path):
        print(f"File not found: '{file_path}'")
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
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", file_path, 
                "-af", "dynaudnorm=f=150:g=15", 
                "-c:a", "pcm_f32le", 
                temp_file_path
            ]
            try:
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

    # 1. Transcribe
    with Timer("Loading & Transcription") as t_transcribe:
        model = whisperx.load_model("large-v3-turbo", DEVICE_ASR, compute_type=COMPUTE_TYPE)
        audio = whisperx.load_audio(process_file_path)
        
        audio_duration = len(audio) / SAMPLE_RATE
        log_metric(f"Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}")
        
        result = model.transcribe(audio, batch_size=BATCH_SIZE, language="en")
        
    del model
    gc.collect()
    torch.cuda.empty_cache()
    
    # 2. Align & Diarize
    with Timer("Alignment") as t_align:
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=DEVICE_OTHER)
        result["segments"] = TqdmList(result["segments"], desc="Aligning", unit="seg")
        result = whisperx.align(result["segments"], model_a, metadata, audio, DEVICE_OTHER)
        
    del model_a
    gc.collect()
    torch.cuda.empty_cache()
    
    print("\n--- Diarizing (Progress bar unavailable for this step) ---")

    with Timer("Diarization") as t_diarize:
        if device_diarize == "cpu":
            print(">> Running Diarization on CPU...")
        diarize_model = whisperx.diarize.DiarizationPipeline(token=HF_TOKEN, device=device_diarize)
        diarize_segments = diarize_model(audio)
        
    del diarize_model
    gc.collect()
    torch.cuda.empty_cache()
    
    # 3. Final Merge & Voice Identification
    llm_duration_str = "N/A"
    with Timer("Merge & Save") as t_merge:
        final_result = whisperx.assign_word_speakers(diarize_segments, result)
        
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
                
                emb_model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=hf_token_lib)
                if not emb_model:
                     emb_model = Model.from_pretrained("pyannote/embedding", use_auth_token=hf_token_lib)
                
                device_emb = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                emb_model.to(device_emb)
                inference = Inference(emb_model, window="whole")
                
                speaker_chunks = {}
                for seg in final_result["segments"]:
                    spk = seg.get("speaker", "UNKNOWN")
                    if spk.startswith("SPEAKER_"):
                        if spk not in speaker_chunks:
                            speaker_chunks[spk] = []
                        speaker_chunks[spk].append((seg["start"], seg["end"]))
                        
                speaker_mapping = {}
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
                            if total_dur > 20.0: break
                        except Exception as e:
                            pass
                            
                    if spk_embeds:
                        avg_emb = np.mean(spk_embeds, axis=0)
                        best_match = None
                        best_score = -1.0
                        for lib_name, lib_emb in library_models.items():
                            sim = 1.0 - cosine(avg_emb.flatten(), lib_emb.flatten())
                            if sim > best_score:
                                best_score = sim
                                best_match = lib_name
                                
                        if best_score > 0.90 and best_match:
                            print(f"[Match] Reassigned {spk} -> {best_match} (Similarity: {round(best_score*100, 1)}%)")
                            speaker_mapping[spk] = best_match
                        else:
                            if best_match and best_score > 0.40:
                                best_str = f"Ambiguous match with {best_match} at {round(best_score*100, 1)}%"
                            else:
                                best_str = f"Best was {best_match} at {round(best_score*100, 1)}%" if best_match else "No library match"
                            
                            print(f"\n[No Match] {spk} remains unknown ({best_str})")
                            
                            best_chunk = chunks[0]
                            st_samp = int(best_chunk[0] * SAMPLE_RATE)
                            playback_dur = min(8.0, best_chunk[1] - best_chunk[0])
                            en_samp = st_samp + int(playback_dur * SAMPLE_RATE)
                            
                            playback_audio = audio[st_samp:en_samp]
                            temp_playback_file = "temp_playback.wav"
                            
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
                                    safe_name = "".join([c for c in user_input if c.isalpha() or c.isdigit()]).rstrip()
                                    speaker_mapping[spk] = safe_name
                                    print(f"Assigned {spk} -> {safe_name}")
                                    
                                    out_file = os.path.join("voice_library", f"{safe_name}.npy")
                                    os.makedirs("voice_library", exist_ok=True)
                                    
                                    if os.path.exists(out_file):
                                        print(f"  -> Found existing profile for {safe_name}. Refining voice print...")
                                        old_embedding = np.load(out_file)
                                        avg_emb = (old_embedding + avg_emb) / 2.0
                                        
                                    np.save(out_file, avg_emb)
                                    print(f"  -> Saved {out_file} (Harvested {round(total_dur, 1)} seconds of speech)")
                                    
                                    library_models[safe_name] = avg_emb
                                    break
                                    
                            if os.path.exists(temp_playback_file):
                                os.remove(temp_playback_file)
                            
                for seg in final_result["segments"]:
                    spk = seg.get("speaker", "UNKNOWN")
                    if spk in speaker_mapping:
                        seg["speaker"] = speaker_mapping[spk]
                        
                del emb_model
                gc.collect()
                torch.cuda.empty_cache()
            else:
                print("No voices found in voice_library/. Skipping identification.")
                
        except Exception as e:
            print(f"Error during speaker identification: {e}")
            
        print("\n--- Writing Markdown ---")
        orig_name = os.path.basename(process_file_path)
        if temp_file_path and process_file_path == temp_file_path:
            orig_name = os.path.basename(file_path)
            
        clean_stem = os.path.splitext(orig_name)[0]
        os.makedirs("transcripts", exist_ok=True)
        
        raw_output_filename = os.path.join("transcripts", f"{clean_stem}_session_log_raw.md")
        standard_output_filename = os.path.join("transcripts", f"{clean_stem}_session_log.md")
        refined_output_filename = os.path.join("transcripts", f"{clean_stem}_session_log_refined.md")
        diff_output_filename = os.path.join("transcripts", f"{clean_stem}_ai_diff.md")
        
        raw_lines = []
        for segment in final_result["segments"]:
            speaker_id = segment.get("speaker", "UNKNOWN")
            st_str = str(datetime.timedelta(seconds=int(segment['start'])))
            et_str = str(datetime.timedelta(seconds=int(segment['end'])))
            raw_lines.append(f"[{st_str} - {et_str}] **{speaker_id}**: {segment['text'].strip()}")

        # 1. ALWAYS write raw transcript immediately
        with open(raw_output_filename, "w", encoding="utf-8") as f:
            f.write(f"# D&D Session Transcript (Raw)\n\n")
            f.write(f"> Processed on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"> Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}\n\n")
            for line in raw_lines:
                f.write(f"{line}  \n")
                
        print(f"\n[Output] Raw transcript saved to: {raw_output_filename}")
        
        # Also write the default session_log.md with raw content initially
        with open(standard_output_filename, "w", encoding="utf-8") as f:
            f.write(f"# D&D Session Transcript\n\n")
            f.write(f"> Processed on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"> Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}\n\n")
            for line in raw_lines:
                f.write(f"{line}  \n")

        # 2. Optional LLM Refinement Pass
        if not skip_llm:
            llm_start_time = time.time()
            refined_lines, stats = refine_transcript_with_llm(raw_lines, batch_size=batch_size)
            llm_duration_str = str(datetime.timedelta(seconds=int(time.time() - llm_start_time)))
            log_metric(f"LLM Refinement finished in {llm_duration_str}")
            
            # Write refined file
            with open(refined_output_filename, "w", encoding="utf-8") as f:
                f.write(f"# D&D Session Transcript (Refined)\n\n")
                f.write(f"> Processed on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write(f"> Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}\n")
                f.write(f"> Refined with Local LLM in {llm_duration_str}\n\n")
                for line in refined_lines:
                    f.write(f"{line}  \n")
            print(f"[Output] Refined transcript saved to: {refined_output_filename}")
            
            # Update main session_log.md to the refined content
            with open(standard_output_filename, "w", encoding="utf-8") as f:
                f.write(f"# D&D Session Transcript\n\n")
                f.write(f"> Processed on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write(f"> Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}\n\n")
                for line in refined_lines:
                    f.write(f"{line}  \n")
                    
            # 3. Generate AI Diff & Evaluation Report
            generate_ai_diff(
                raw_lines=raw_lines,
                refined_lines=refined_lines,
                diff_output_path=diff_output_filename,
                session_name=clean_stem,
                duration_str=llm_duration_str,
                batch_stats=stats
            )

    # 4. Cleanup
    if temp_file_path and os.path.exists(temp_file_path):
        os.remove(temp_file_path)
        log_metric("Temporary normalized audio file removed.")
    overall_timer.__exit__(None, None, None)

    print("\n" + "="*50)
    print(f"{'Phase':<25} | {'Duration':<15}")
    print("-" * 50)
    print(f"{'Transcription':<25} | {t_transcribe.format_duration():<15}")
    print(f"{'Alignment':<25} | {t_align.format_duration():<15}")
    print(f"{'Diarization':<25} | {t_diarize.format_duration():<15}")
    print(f"{'LLM Refinement':<25} | {llm_duration_str:<15}")
    print(f"{'Merge & Save':<25} | {t_merge.format_duration():<15}")
    print("-" * 50)
    print(f"{'Total Runtime':<25} | {overall_timer.format_duration():<15}")
    print("="*50 + "\n")

    print(f"\n[Success] Transcripts and logs generated:")
    print(f"  -> Raw Transcript:     {raw_output_filename}")
    if not skip_llm:
        print(f"  -> Refined Transcript: {refined_output_filename}")
        print(f"  -> AI Diff Report:     {diff_output_filename}")
    print(f"  -> Active Session Log: {standard_output_filename}")


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
    pattern = re.compile(r'^\[(\d{1,2}:\d{2}:\d{2} - \d{1,2}:\d{2}:\d{2})\] \*\*(.+?)\*\*:')
    
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


def diff_two_transcripts(raw_md_path: str, refined_md_path: str, output_diff_path: str = None):
    """Utility to compare any two transcript markdown files and output an AI diff report."""
    import re
    if not os.path.exists(raw_md_path) or not os.path.exists(refined_md_path):
        print(f"Error: One or both files not found: '{raw_md_path}', '{refined_md_path}'")
        return
        
    pattern = re.compile(r'^\[\d{1,2}:\d{2}:\d{2} - \d{1,2}:\d{2}:\d{2}\]')
    
    def read_lines(path):
        lines = []
        with open(path, 'r', encoding='utf-8') as f:
            for l in f:
                s = l.rstrip()
                if pattern.search(s):
                    lines.append(s)
        return lines
        
    raw_lines = read_lines(raw_md_path)
    refined_lines = read_lines(refined_md_path)
    
    if not output_diff_path:
        base = os.path.splitext(raw_md_path)[0].replace("_session_log_raw", "").replace("_raw", "")
        output_diff_path = f"{base}_ai_diff.md"
        
    session_name = os.path.splitext(os.path.basename(raw_md_path))[0]
    generate_ai_diff(raw_lines, refined_lines, output_diff_path, session_name=session_name)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="D&D Transcription, AI Refinement & Voice Training")
    parser.add_argument("-a", "--audio", type=str, help="Path to the audio recording file (supports tab completion).")
    parser.add_argument("-i", "--input", type=str, help="Alias for --audio / -a.")
    
    # Standalone AI Refinement & Diff Options
    parser.add_argument("--refine", type=str, help="Run AI refinement and generate a diff on an existing markdown transcript.")
    parser.add_argument("--diff", nargs=2, metavar=('RAW_MD', 'REFINED_MD'), help="Compare two markdown transcripts and generate an AI diff report.")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size (number of dialogue lines) per LLM request (default: 50).")
    parser.add_argument("--api-url", type=str, default=None, help="LLM API URL (default: http://localhost:1234/v1 or LLM_API_URL env var).")
    parser.add_argument("--no-llm", action="store_true", help="Skip local LLM (LM Studio) transcript refinement.")
    
    # Voice Harvesting / Training
    parser.add_argument("--train", action="store_true", help="Harvest voices from an annotated markdown transcript to build the voice_library.")
    parser.add_argument("--md", type=str, help="Path to the edited markdown (.md) file (for --train)")
    
    args = parser.parse_args()
    
    selected_audio = args.audio or args.input

    with WindowsSleepPreventer():
        if args.diff:
            diff_two_transcripts(args.diff[0], args.diff[1])
        elif args.refine:
            refine_existing_transcript(args.refine, api_url=args.api_url, batch_size=args.batch_size)
        elif args.train:
            if not args.md or not selected_audio:
                print("Error: --train requires both --md and --audio/-a arguments.")
            else:
                train_voices(args.md, selected_audio)
        else:
            run_dnd_session(audio_path=selected_audio, skip_llm=args.no_llm, batch_size=args.batch_size)