import os
# SECURITY PATCH: Tell PyTorch 2.6 to trust the local models you just downloaded
os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1" 

import whisperx
import whisperx.asr
import whisperx.diarize
import torch
import time
import datetime
from tqdm import tqdm
from typing import Optional, Union, List
import numpy as np
from dataclasses import replace
from whisperx.audio import N_SAMPLES, SAMPLE_RATE, load_audio, log_mel_spectrogram
from whisperx.schema import SingleSegment, TranscriptionResult
from whisperx.vads import Vad, Pyannote
from faster_whisper.tokenizer import Tokenizer

# --- HELPER CLASSES & MONKEYPATCHING ---

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

# --- CONFIGURATION (M1 Max Optimized) ---
HF_TOKEN = os.getenv("HF_TOKEN") # Set this in your environment or a .env file
DEVICE_ASR = "cpu"            # Transcription best on CPU (int8) for Mac
DEVICE_OTHER = "mps"          # Align/Diarize best on GPU (MPS) for Mac
BATCH_SIZE = 32               # Increased for 64GB RAM
COMPUTE_TYPE = "int8"         # Best performance for long CPU sessions
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

    num_speakers = int(input("Total speakers (Players + DM)? "))
    print(f"\n--- Auto-detecting Speaker IDs (SPEAKER_00, SPEAKER_01, etc.) ---")
    print(f"You can Find & Replace these labels in the output file later.")

    # High Accuracy Mode Prompt
    high_accuracy = input("Enable High Accuracy Mode (slower, runs on CPU)? [y/N]: ").strip().lower() == 'y'
    device_diarize = "cpu" if high_accuracy else DEVICE_OTHER
    
    print(f"\n--- Processing Locally on M1 Max ---")

    # 1. Transcribe (Model is already cached on your 8TB drive!)
    with Timer("Loading & Transcription") as t_transcribe:
        model = whisperx.load_model("large-v3", DEVICE_ASR, compute_type=COMPUTE_TYPE)
        audio = whisperx.load_audio(file_path)
        
        audio_duration = len(audio) / SAMPLE_RATE
        log_metric(f"Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}")
        
        result = model.transcribe(audio, batch_size=BATCH_SIZE)
    
    # 2. Align & Diarize (THE FIX IS HERE: whisperx.diarize)
    with Timer("Alignment") as t_align:
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=DEVICE_OTHER)
        
        # Wrap segments in TqdmList for alignment progress
        result["segments"] = TqdmList(result["segments"], desc="Aligning", unit="seg")
        
        result = whisperx.align(result["segments"], model_a, metadata, audio, DEVICE_OTHER)
    
    # Since TqdmList was exhausted by align, we might need it back as a regular list if we use it again, 
    # but whisperx.align returns a new dictionary with new segments, so we are good.

    print("\n--- Diarizing (Progress bar unavailable for this step) ---")

    # Use the new sub-module path for diarization
    with Timer("Diarization") as t_diarize:
        if high_accuracy:
            print(">> Running Diarization on CPU for maximum precision...")
        diarize_model = whisperx.diarize.DiarizationPipeline(use_auth_token=HF_TOKEN, device=device_diarize)
        diarize_segments = diarize_model(audio, min_speakers=num_speakers, max_speakers=num_speakers, num_speakers=num_speakers)
    
    # 3. Final Merge
    with Timer("Merge & Save") as t_merge:
        final_result = whisperx.assign_word_speakers(diarize_segments, result)
        output_filename = os.path.splitext(file_path)[0] + "_session_log.md"
        
        with open(output_filename, "w") as f:
            f.write(f"# D&D Session Transcript\n\n")
            f.write(f"> Processed on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"> Audio Duration: {str(datetime.timedelta(seconds=int(audio_duration)))}\n\n")
            
            for segment in final_result["segments"]:
                speaker_id = segment.get("speaker", "UNKNOWN")
                f.write(f"**{speaker_id}**: {segment['text'].strip()}  \n")

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

if __name__ == "__main__":
    run_dnd_session()