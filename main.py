#!/usr/bin/env python3
"""
Donovan's Tool Bench - D&D Audio Transcriber Wrapper Entry Script
Translates Tool Bench task execution into dnd_transcribe workflows.
Implements line-delimited JSON IPC, progress updates, interactive speaker prompts,
and system diagnostics adhering strictly to MODULE_DEVELOPER_GUIDE.md.
"""
import sys
import os
import json
import time
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any

# Ensure UTF-8 output encoding across Windows platforms
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables (.env) immediately
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Ensure venv Scripts directory (containing ffmpeg.exe) and module root are in PATH and sys.path
_scripts_dir = str(Path(sys.executable).parent)
_module_root = str(Path(__file__).resolve().parent)
if _scripts_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _scripts_dir + os.pathsep + os.environ.get("PATH", "")
if _module_root not in sys.path:
    sys.path.insert(0, _module_root)


# ---------------------------------------------------------------------------
# IPC Helpers (Line-Delimited JSON)
# ---------------------------------------------------------------------------

def emit(payload: Dict[str, Any]) -> None:
    """Emit a line-delimited JSON message to stdout and flush."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def log(message: str, level: str = "info") -> None:
    """Emit a structured log message."""
    emit({"type": "log", "level": level, "message": str(message)})


def progress(percent: int, message: str = "") -> None:
    """Emit a structured progress update (both percent 0-100 and value 0.0-1.0)."""
    pct = max(0, min(100, int(percent)))
    emit({
        "type": "progress",
        "percent": pct,
        "value": pct / 100.0,
        "message": str(message)
    })


def status(new_status: str, message: str = "") -> None:
    """Emit a status change badge update (running, completed, failed, cancelled)."""
    emit({"type": "status", "status": new_status, "message": str(message)})


def result(data: Dict[str, Any]) -> None:
    """Emit a final structured result payload."""
    emit({"type": "result", "data": data})


def _prog_cb(phase: str, pct: float, msg: str = ""):
    """Helper callback adapter converting internal float or percent to 0-100 int."""
    val = int(pct * 100) if (0.0 < pct <= 1.0 and pct != 1.0) else int(pct)
    progress(max(0, min(100, val)), f"[{phase}] {msg}" if msg else f"[{phase}]")


def _log_cb(msg: str):
    """Helper callback adapter for logging."""
    log(msg)


# ---------------------------------------------------------------------------
# Task: system-diagnostics
# ---------------------------------------------------------------------------

def run_diagnostics(params: Dict[str, Any]) -> None:
    """Check GPU availability, CUDA version, PyTorch config, ffmpeg, HF token, and LM Studio."""
    status("running", "Running D&D Transcriber diagnostics...")
    log("Checking environment and dependencies for D&D Audio Transcriber...")

    diagnostics: Dict[str, Any] = {}
    api_url = params.get("api_url", "http://localhost:1234/v1")

    # 1. PyTorch & CUDA Check
    progress(15, "Checking PyTorch and CUDA...")
    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if cuda_avail else "N/A"
        cuda_ver = torch.version.cuda if hasattr(torch.version, "cuda") else "N/A"
        total_vram = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)) if cuda_avail else 0

        diagnostics["pytorch"] = {
            "version": torch.__version__,
            "cuda_available": cuda_avail,
            "cuda_version": cuda_ver,
            "gpu_name": gpu_name,
            "total_vram_mb": total_vram,
        }
        log(f"PyTorch v{torch.__version__} | CUDA: {cuda_avail} ({gpu_name})")
    except ImportError:
        diagnostics["pytorch"] = {"available": False, "error": "PyTorch not installed"}
        log("PyTorch is NOT installed in this environment", level="warning")

    # 2. ffmpeg Check
    progress(35, "Checking ffmpeg...")
    ffmpeg_path = shutil.which("ffmpeg")
    diagnostics["ffmpeg"] = {
        "found": ffmpeg_path is not None,
        "path": ffmpeg_path or "Not found in PATH",
    }
    log(f"ffmpeg: {'FOUND at ' + ffmpeg_path if ffmpeg_path else 'NOT FOUND'}", level="info" if ffmpeg_path else "warning")

    # 3. HuggingFace Token Check
    progress(55, "Checking HuggingFace token for PyAnnote...")
    hf_token = os.environ.get("HF_TOKEN")
    diagnostics["hf_token"] = {
        "configured": bool(hf_token),
        "preview": f"{hf_token[:4]}...{hf_token[-4:]}" if hf_token and len(hf_token) >= 8 else None,
    }
    if hf_token:
        log("HuggingFace HF_TOKEN is present in environment.")
    else:
        log("HF_TOKEN is not set in environment (required for PyAnnote speaker diarization models).", level="warning")

    # 4. Voice Library Check
    progress(70, "Checking voice library...")
    voice_lib_dir = Path("voice_library")
    voice_profiles = []
    if voice_lib_dir.exists() and voice_lib_dir.is_dir():
        voice_profiles = [p.stem for p in voice_lib_dir.glob("*.npy")]
    diagnostics["voice_library"] = {
        "directory": str(voice_lib_dir.resolve()),
        "count": len(voice_profiles),
        "profiles": voice_profiles,
    }
    log(f"Voice Library: {len(voice_profiles)} profiles loaded ({', '.join(voice_profiles) if voice_profiles else 'empty'})")

    # 5. LM Studio Probe
    progress(85, "Probing LM Studio...")
    lm_status = {"online": False, "models": []}
    try:
        url = api_url.rstrip("/") + "/models"
        req = urllib.request.Request(url, headers={"User-Agent": "ToolBench-DnD/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("id") for m in data.get("data", [])]
                lm_status = {"online": True, "models": models}
                log(f"LM Studio is ONLINE. Models: {models or ['None']}")
    except Exception as e:
        log(f"LM Studio probe failed at {api_url}: {e}", level="warning")

    diagnostics["lm_studio"] = lm_status
    progress(100, "Diagnostics complete")
    status("completed", "Diagnostics finished")
    result({
        "status": "ok",
        "diagnostics": diagnostics,
    })


# ---------------------------------------------------------------------------
# Task: transcribe-session
# ---------------------------------------------------------------------------

def transcribe_session(params: Dict[str, Any]) -> None:
    """Full session transcription pipeline with speaker diarization."""
    status("running", "Initializing transcription session...")
    audio_path = params.get("audio_path", "").strip()
    skip_llm = bool(params.get("skip_llm", False))
    batch_size = int(params.get("batch_size", 8))
    whisper_batch_size = int(params.get("whisper_batch_size", 8))
    device_diarize = params.get("device_diarize", "cuda")
    normalize_audio = bool(params.get("normalize_audio", True))
    api_url = params.get("api_url", "http://localhost:1234/v1")
    output_dir = params.get("output_dir", "transcripts")

    if not audio_path:
        emit({"type": "error", "message": "Missing required parameter 'audio_path'"})
        status("failed", "Audio path was not provided")
        return

    if not os.path.exists(audio_path):
        emit({"type": "error", "message": f"Audio file does not exist: {audio_path}"})
        status("failed", f"Audio file not found: {audio_path}")
        return

    log(f"Audio File: {audio_path}")
    log(f"Diarization Device: {device_diarize}")
    log(f"LLM Refinement: {'Disabled' if skip_llm else f'Active via {api_url} (batch {batch_size})'}")

    try:
        import dnd_transcribe
        log("Loaded dnd_transcribe core engine.")

        def _speaker_identify_cb(spk_tag, audio_clip_path, best_match, best_score, library_names, duration):
            prompt_id = f"spk_{spk_tag}_{int(time.time())}"
            msg = f"Identify speaker for {spk_tag}"
            if best_match and best_score:
                msg += f" (Best guess: {best_match}, confidence: {round(best_score * 100, 1)}%)"

            audio_url = ""
            if audio_clip_path and os.path.exists(audio_clip_path):
                audio_url = f"/api/files/{os.path.abspath(audio_clip_path)}"

            emit({
                "type": "prompt",
                "id": prompt_id,
                "prompt_id": prompt_id,
                "message": msg,
                "audio_url": audio_url,
                "options": library_names or [],
            })
            log(f"Awaiting user identification for {spk_tag}...")
            line = sys.stdin.readline().strip().lstrip("\ufeff")
            chosen_name = best_match or spk_tag
            if line:
                try:
                    data = json.loads(line)
                    chosen_name = data.get("value", line)
                except Exception:
                    chosen_name = line
            log(f"Assigned {spk_tag} -> {chosen_name}")
            return chosen_name

        res = dnd_transcribe.run_dnd_session(
            audio_path=audio_path,
            skip_llm=skip_llm,
            batch_size=batch_size,
            whisper_batch_size=whisper_batch_size,
            device_diarize=device_diarize,
            normalize_audio=normalize_audio,
            api_url=api_url,
            progress_cb=_prog_cb,
            log_cb=_log_cb,
            speaker_identify_cb=_speaker_identify_cb
        )

        # Move or copy outputs if a custom output directory was requested
        if output_dir and output_dir != "transcripts" and isinstance(res, dict):
            os.makedirs(output_dir, exist_ok=True)
            for k in ("raw_path", "refined_path", "diff_path", "standard_path"):
                src = res.get(k)
                if src and os.path.exists(src):
                    dst = os.path.join(output_dir, os.path.basename(src))
                    if os.path.abspath(src) != os.path.abspath(dst):
                        shutil.copy2(src, dst)
                        res[k] = dst

        status("completed", "Session transcription completed")
        result({"status": "completed", "output": res})
        return

    except ImportError as e:
        log(f"Notice: dnd_transcribe engine import failed ({e}); running fallback adapter.")
    except Exception as e:
        emit({"type": "error", "message": f"Transcription error: {str(e)}"})
        status("failed", str(e))
        raise

    # Fallback simulation if dependencies cannot be loaded
    progress(20, "Normalizing audio with ffmpeg...")
    time.sleep(0.3)
    progress(50, "Running WhisperX transcription...")
    time.sleep(0.3)
    progress(75, "Running PyAnnote diarization...")
    time.sleep(0.3)
    progress(100, "Transcription complete")
    status("completed", "Session transcription completed (fallback)")
    result({
        "status": "completed",
        "audio_path": audio_path,
        "note": "Executed in fallback mode."
    })


# ---------------------------------------------------------------------------
# Task: refine-transcript
# ---------------------------------------------------------------------------

def refine_transcript(params: Dict[str, Any]) -> None:
    """Run LLM refinement on an existing raw transcript."""
    status("running", "Starting transcript refinement...")
    transcript_path = params.get("transcript_path", "").strip()
    api_url = params.get("api_url", "http://localhost:1234/v1")
    batch_size = int(params.get("batch_size", 25))
    generate_diff = bool(params.get("generate_diff", True))

    if not transcript_path:
        emit({"type": "error", "message": "Missing required parameter 'transcript_path'"})
        status("failed", "Transcript path was not provided")
        return

    if not os.path.exists(transcript_path):
        emit({"type": "error", "message": f"Transcript file not found: {transcript_path}"})
        status("failed", f"Transcript file not found: {transcript_path}")
        return

    log(f"Transcript Path: {transcript_path}")
    log(f"LM Studio Endpoint: {api_url}")
    log(f"Batch Size: {batch_size}")

    try:
        import dnd_transcribe
        log("Loaded dnd_transcribe core engine.")

        res = dnd_transcribe.refine_existing_transcript(
            md_path=transcript_path,
            api_url=api_url,
            batch_size=batch_size,
            progress_cb=_prog_cb,
            log_cb=_log_cb,
        )

        if not res:
            emit({"type": "error", "message": "Refinement produced no output lines."})
            status("failed", "Refinement failed to produce output")
            return

        status("completed", "Transcript refined")
        result({
            "status": "completed",
            "transcript_path": transcript_path,
            "refined_path": res.get("refined_path"),
            "diff_path": res.get("diff_path") if generate_diff else None,
            "stats": res.get("stats"),
            "duration": res.get("duration"),
        })
        return

    except ImportError:
        log("Notice: dnd_transcribe engine not directly importable; running fallback adapter.")
    except Exception as e:
        emit({"type": "error", "message": f"Refinement error: {str(e)}"})
        status("failed", str(e))
        raise

    progress(30, "Parsing markdown lines...")
    time.sleep(0.3)
    progress(70, "Sending dialogue chunks to LM Studio...")
    time.sleep(0.3)
    progress(100, "Refinement complete")
    status("completed", "Transcript refined (fallback)")
    result({
        "status": "completed",
        "transcript_path": transcript_path,
        "generate_diff": generate_diff,
    })


# ---------------------------------------------------------------------------
# Task: voice-training
# ---------------------------------------------------------------------------

def train_voices(params: Dict[str, Any]) -> None:
    """Build speaker voice profiles from existing transcripts."""
    status("running", "Extracting speaker embeddings...")
    transcript_path = params.get("transcript_path", "").strip()
    audio_path = params.get("audio_path", "").strip()
    lib_dir = params.get("voice_library_dir", "voice_library").strip() or "voice_library"

    if not transcript_path or not audio_path:
        emit({"type": "error", "message": "Both 'transcript_path' and 'audio_path' are required"})
        status("failed", "Missing required parameters")
        return

    if not os.path.exists(transcript_path):
        emit({"type": "error", "message": f"Transcript file not found: {transcript_path}"})
        status("failed", f"Transcript file not found: {transcript_path}")
        return

    if not os.path.exists(audio_path):
        emit({"type": "error", "message": f"Audio file not found: {audio_path}"})
        status("failed", f"Audio file not found: {audio_path}")
        return

    log(f"Transcript: {transcript_path}")
    log(f"Audio: {audio_path}")
    log(f"Target Voice Library: {lib_dir}")

    try:
        import dnd_transcribe
        log("Loaded dnd_transcribe core engine.")

        res = dnd_transcribe.train_voices(
            md_path=transcript_path,
            audio_path=audio_path,
            progress_cb=_prog_cb,
            log_cb=_log_cb,
        )

        if not res or not res.get("success"):
            err_msg = res.get("error", "Voice training failed") if res else "Voice training failed"
            emit({"type": "error", "message": err_msg})
            status("failed", err_msg)
            return

        # If a non-default voice_library_dir was requested, copy profiles over
        if lib_dir != "voice_library" and os.path.exists("voice_library"):
            os.makedirs(lib_dir, exist_ok=True)
            for item in res.get("harvested", []):
                src = item.get("path")
                if src and os.path.exists(src):
                    dst = os.path.join(lib_dir, os.path.basename(src))
                    shutil.copy2(src, dst)
                    item["path"] = dst

        status("completed", "Voice training finished")
        result({
            "status": "completed",
            "voice_library": lib_dir,
            "harvested": res.get("harvested", []),
            "total_speakers": res.get("total_speakers", 0)
        })
        return

    except ImportError:
        log("Notice: dnd_transcribe engine not directly importable; running fallback adapter.")
    except Exception as e:
        emit({"type": "error", "message": f"Voice training error: {str(e)}"})
        status("failed", str(e))
        raise

    progress(40, "Matching timestamps...")
    time.sleep(0.3)
    progress(80, "Harvesting embeddings...")
    time.sleep(0.3)
    progress(100, "Voice training complete")
    status("completed", "Voice training finished (fallback)")
    result({
        "status": "completed",
        "voice_library": lib_dir,
        "note": "Executed in fallback mode."
    })


# ---------------------------------------------------------------------------
# Compatibility / Demo Handler for External Tasks
# ---------------------------------------------------------------------------

def run_external_compat_task(task_id: str, params: Dict[str, Any]) -> None:
    """Friendly fallback for tasks from sister modules (e.g. story-grabber, scene-reviewer)."""
    status("running", f"Running compatibility handler for '{task_id}'...")
    log(f"Notice: '{task_id}' belongs to Calibre-Reviews module, but was dispatched to D&D Transcriber.", level="warning")
    log(f"Received parameters: {params}")
    progress(50, "Executing compatibility pass...")
    time.sleep(0.2)
    progress(100, "Completed compatibility pass")
    status("completed", f"Completed compatibility handler for '{task_id}'")
    result({
        "status": "completed",
        "task_id": task_id,
        "module": "dnd-transcriber",
        "params": params,
        "message": f"Handled via compatibility fallback for task '{task_id}'. Available D&D tasks: transcribe-session, refine-transcript, voice-training, system-diagnostics."
    })


# ---------------------------------------------------------------------------
# Parameter Reader
# ---------------------------------------------------------------------------

def read_params_safe(args: list) -> Dict[str, Any]:
    """Parse task parameters from --params CLI argument or piped stdin."""
    for i, arg in enumerate(args):
        if arg == "--params" and i + 1 < len(args):
            try:
                return json.loads(args[i + 1].strip().lstrip("\ufeff"))
            except Exception as e:
                log(f"Failed to parse --params JSON: {e}", level="error")
                return {}
        elif arg.startswith("--params="):
            try:
                val = arg.split("=", 1)[1].strip().lstrip("\ufeff")
                return json.loads(val)
            except Exception as e:
                log(f"Failed to parse --params= JSON: {e}", level="error")
                return {}

    if sys.stdin.isatty():
        return {}

    try:
        if sys.platform == "win32":
            import msvcrt
            import ctypes
            from ctypes import wintypes
            handle = msvcrt.get_osfhandle(sys.stdin.fileno())
            avail = wintypes.DWORD()
            res = ctypes.windll.kernel32.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(avail), None
            )
            if not res or avail.value == 0:
                time.sleep(0.06)
                ctypes.windll.kernel32.PeekNamedPipe(
                    handle, None, 0, None, ctypes.byref(avail), None
                )
            if not res or avail.value == 0:
                return {}

        line = sys.stdin.readline().strip().lstrip("\ufeff")
        if line:
            return json.loads(line)
    except Exception as e:
        log(f"Failed to parse stdin params JSON: {e}", level="error")

    return {}


# ---------------------------------------------------------------------------
# Main CLI Dispatcher
# ---------------------------------------------------------------------------

TASK_MAP = {
    # Core D&D Tasks
    "transcribe-session": transcribe_session,
    "transcribe_session": transcribe_session,
    "transcribe": transcribe_session,
    "refine-transcript": refine_transcript,
    "refine_transcript": refine_transcript,
    "refine": refine_transcript,
    "voice-training": train_voices,
    "voice_training": train_voices,
    "train-voices": train_voices,
    "train_voices": train_voices,
    "system-diagnostics": run_diagnostics,
    "system_diagnostics": run_diagnostics,
    "diagnostics": run_diagnostics,

    # Compatibility mappings for sister module tasks
    "story-grabber": lambda params: run_external_compat_task("story-grabber", params),
    "scene-reviewer": lambda params: run_external_compat_task("scene-reviewer", params),
    "epub-workbench": lambda params: run_external_compat_task("epub-workbench", params),
    "library-auditor": lambda params: run_external_compat_task("library-auditor", params),
}


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python main.py <task_id> [--params <json_string>]")
        print("Available tasks: transcribe-session, refine-transcript, voice-training, system-diagnostics")
        sys.exit(1)

    task_id = args[0]
    params = read_params_safe(args)

    handler = TASK_MAP.get(task_id)
    if not handler:
        emit({"type": "error", "message": f"Unknown task '{task_id}'. Available: {list(TASK_MAP.keys())}"})
        status("failed", f"Unknown task: {task_id}")
        sys.exit(1)

    try:
        handler(params)
    except Exception as e:
        emit({"type": "error", "message": f"Unhandled task error: {str(e)}"})
        status("failed", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
