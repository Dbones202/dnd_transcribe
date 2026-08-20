# D&D Session Transcriber & Voice Harvester

A specialized Python utility designed to transcribe large D&D session audio recordings, perform speaker diarization (separating who speaks when), and mathematically recognize/train player voices using a custom local **Voice Library**.

This software runs locally on your machine and is optimized to utilize **NVIDIA CUDA** acceleration (e.g., RTX 5060 Ti) for WhisperX.

---

## 🛠️ Step 1: Open the Virtual Environment (venv)

Before running any script, you **must** activate the Python virtual environment (`venv`) to ensure all dependencies (PyTorch, WhisperX, etc.) are available.

Depending on your shell, run **one** of the following commands in the project root folder:

### 🔹 For PowerShell (Recommended on Windows)
```powershell
.\venv\Scripts\Activate.ps1
```
> [!TIP]
> If you encounter an execution policy error (e.g., *"script execution is disabled on this system"*), temporarily allow execution in your current session by running:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
> ```
> Then try running `.\venv\Scripts\Activate.ps1` again.

### 🔹 For Command Prompt (cmd)
```cmd
venv\Scripts\activate.bat
```

### 🔹 For Git Bash / WSL
```bash
source venv/Scripts/activate
```

*You will know the venv is active when you see `(venv)` prepended to your command prompt line.*

---

## 🖥️ Graphical User Interface (GUI App)

You can run the full transcription suite with a modern desktop GUI:

```powershell
python run_gui.py
```

### 🌟 GUI Features:
- **🎙️ Transcription Studio**: Visual pipeline stepper, audio file browser, GPU/CPU toggles, normalization controls, LM Studio connection tester, and live colored terminal console.
- **Interactive Speaker Identification**: Pops up an audio playback modal with replay controls, enrolled speaker dropdown, and name input.
- **🤖 AI Refinement & Diff Viewer**: Standalone transcript refinement and side-by-side / line-by-line diff inspection table.
- **🎓 Voice Library Manager**: Search, rename, or delete `.npy` voice models, and harvest voices from edited transcripts.
- **⚙️ System Diagnostics**: Real-time inspection of CUDA GPU acceleration, VRAM, WhisperX, FFmpeg, Hugging Face Token, and LM Studio server status.

---

## 🚀 Step 2: How to Run via CLI (Terminal)

To start transcribing a D&D session recording from the command line:

1. **Place your recording** (e.g., `.wav`, `.mp3`) in the `audio_files/` directory.
2. Run the main script with the `-a` / `--audio` flag (allows **Tab auto-completion** in PowerShell/Terminal):
   ```powershell
   python dnd_transcribe.py -a audio_files/session_1.wav
   ```
   *(If omitted, the script will prompt you interactively for the recording path).*
3. **Interactive Prompts**:
   - **CPU vs GPU Diarization**: You'll be asked if you want to run speaker diarization on CPU instead of GPU. Press `Enter` (default is GPU) unless you run out of GPU VRAM (CUDA errors).
   - **Interactive Speaker Identification**: During transcription, the tool checks speaker audio prints against `voice_library/`. If it doesn't find a matching voice profile, it will play a short audio clip of the unknown speaker (`winsound`) and prompt you to name them. Typing a name will instantly save that player's voice print to the library.

### 📄 Output Files Generated

When transcription finishes, the following files are automatically produced in `transcripts/`:
- **`transcripts/<name>_session_log_raw.md`**: The complete, unedited WhisperX + PyAnnote transcript (available immediately in ~15 mins).
- **`transcripts/<name>_session_log_refined.md`**: The post-LLM refined transcript (if AI refinement is active).
- **`transcripts/<name>_ai_diff.md`**: A detailed **AI Evaluation & Diff Report** listing exact before-and-after line modifications, percentage of lines altered, and processing duration.
- **`transcripts/<name>_session_log.md`**: The active session log (used for reading and voice training).

---

## 🎓 Step 3: How to Train the Software (Refining Voice Profiles)

If the system failed to identify a speaker, or if you want to make a player's mathematical voice profile more precise, you can train it using an edited transcript.

### 1. Edit the Transcript
Open the output markdown file in `transcripts/` and replace the generic speaker placeholders (e.g., `SPEAKER_00`) with the actual player names (e.g., `Donovan` or `Mercer`), leaving timestamps intact:
```markdown
<!-- BEFORE -->
[0:01:23 - 0:01:45] **SPEAKER_00**: Roll for initiative!

<!-- AFTER -->
[0:01:23 - 0:01:45] **Donovan**: Roll for initiative!
```

### 2. Run Training (Voice Harvesting)
Use **either** of the following methods to extract voice profiles from your edited transcript:

#### Option A: Via Main Script (Recommended)
```powershell
python dnd_transcribe.py --train --md "transcripts/your_edited_transcript.md" --audio "audio_files/your_game_recording.wav"
```

#### Option B: Via Extraction Script (Alternative)
```powershell
python extract_voices.py "transcripts/your_edited_transcript.md" "audio_files/your_game_recording.wav"
```

The script scans the markdown file, extracts audio segments where named speakers spoke, generates PyAnnote embeddings, and saves/refines the mathematical voice print (`.npy` files) in:
`voice_library/<name>.npy`

---

## 🤖 Local LLM Transcript Refinement & Diff Evaluation

`dnd_transcribe.py` supports post-processing via **LM Studio** using local models like **Gemma 4 / 4B** or **Llama 3**.

### How It Works
* After WhisperX and PyAnnote finish and free GPU VRAM, the script checks if LM Studio is running on `http://localhost:1234/v1`.
* If detected, it sends transcript batches to the LLM to correct D&D homophones (e.g. *"man to core"* $\rightarrow$ *"manticore"*, *"tea fling"* $\rightarrow$ *"tiefling"*), fix punctuation, and clean up audio stutter repetitions while keeping **100% of line order, dialogue, timestamps, and speaker tags**.
* **Pre-AI & Post-AI Isolation**: The raw transcript is **always** saved to `_session_log_raw.md` first. The refined transcript is saved to `_session_log_refined.md`, and a diff report is generated at `_ai_diff.md` so you can evaluate the value of the AI edits.

### Commands & Options
* **Standard Transcription (LLM Enabled if active)**:
  ```powershell
  python dnd_transcribe.py -a audio_files/session_1.wav
  ```
* **Fast Transcription (Skip LLM Post-Processing)**:
  ```powershell
  python dnd_transcribe.py -a audio_files/session_1.wav --no-llm
  ```
* **Standalone AI Refinement** (Refine an existing raw transcript without re-running audio):
  ```powershell
  python dnd_transcribe.py --refine "transcripts/my_session_session_log_raw.md"
  ```
* **Compare Any Two Transcripts** (Generate an AI Diff Report between raw and refined files):
  ```powershell
  python dnd_transcribe.py --diff "transcripts/session_raw.md" "transcripts/session_refined.md"
  ```
* **Custom Batch Size & API Endpoint**:
  ```powershell
  python dnd_transcribe.py --refine "transcripts/session_raw.md" --batch-size 75 --api-url "http://localhost:1234/v1"
  ```

---

## 🎙️ Recommended Audio Preparation (Audacity Workflow)

Before feeding session audio to WhisperX, prepping audio in Audacity ensures maximum transcription accuracy:

1. **Noise Reduction**: Sample 2–3s of room silence $\rightarrow$ *Effect > Noise Removal > Noise Reduction* (Settings: 12dB, Sensitivity 6).
2. **Truncate Silence**: Cut long pauses $\rightarrow$ *Effect > Special > Truncate Silence* (Threshold -35dB to -40dB, Duration 1.0s, Truncate to 0.5s).
3. **Compressor**: Equalize quiet and loud voices $\rightarrow$ *Effect > Volume and Compression > Compressor* (Threshold -18dB, Ratio 3:1).
4. **Filter Curve EQ**: Remove low-end table thumps $\rightarrow$ *Effect > EQ and Filters > Filter Curve EQ > Presets: Low Roll-off for Speech*.
5. **Normalize**: Consistent peak amplitude $\rightarrow$ *Effect > Volume and Compression > Normalize* (Peak -1.0 dB).

> [!IMPORTANT]
> **Audio Consistency Note**: Always use the **exact same prepped/truncated audio file** for both transcription (`python dnd_transcribe.py`) and subsequent voice harvesting (`python dnd_transcribe.py --train`).

---

## 🗂️ Folder Structure

- `audio_files/` — Put your raw or prepped game session recording files here.
- `transcripts/` — Output folder for generated Markdown transcripts.
- `voice_library/` — Contains mathematical voice profiles (`.npy` files) for players.
- `venv/` — Python virtual environment containing WhisperX, PyTorch, and other packages.

---

## ⚙️ Configuration & Prerequisites

- **LM Studio (Optional)**: Start LM Studio's Local Server on port `1234` with Gemma 4 / 4B loaded for automated transcript refinement.
- **Hugging Face Token**: Speaker diarization uses PyAnnote. Ensure you have a `.env` file in the root directory containing your Hugging Face read token:
  ```env
  HF_TOKEN="hf_your_token_here"
  ```
- **FFmpeg**: Required for audio normalization. Ensure FFmpeg is installed on your Windows system and added to your system's `PATH`.
- **GPU Check**: You can verify that Python can access your NVIDIA GPU by running:
  ```powershell
  python verify_gpu.py
  ```
