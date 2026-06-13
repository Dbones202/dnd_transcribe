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

## 🚀 Step 2: How to Run the Software (Transcription)

To start transcribing a D&D session recording:

1. **Place your recording** (e.g., `.wav`, `.mp3`) in the `audio_files/` directory.
2. Run the main script:
   ```powershell
   python dnd_transcribe.py
   ```
3. **Interactive Prompts**:
   - **Recording Path**: Enter the relative path to your file (e.g., `audio_files/session_1.wav`).
   - **CPU vs GPU Diarization**: You'll be asked if you want to run speaker diarization on CPU instead of GPU. Press `Enter` (default is GPU) unless you run out of GPU VRAM (CUDA errors).
   - **Interactive Speaker Identification**: During transcription, the tool checks speaker audio prints against `voice_library/`. If it doesn't find a matching voice profile, it will play a short audio clip of the unknown speaker (`winsound`) and prompt you to name them. Typing a name will instantly save that player's voice print to the library.

The final Markdown transcript will be saved to:
`transcripts/<recording_name>_session_log.md`

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

## 🗂️ Folder Structure

- `audio_files/` — Put your raw game session recording files here.
- `transcripts/` — Output folder for generated Markdown transcripts.
- `voice_library/` — Contains mathematical voice profiles (`.npy` files) for players.
- `venv/` — Python virtual environment containing WhisperX, PyTorch, and other packages.

---

## ⚙️ Configuration & Prerequisites

- **Hugging Face Token**: Speaker diarization uses PyAnnote. Ensure you have a `.env` file in the root directory containing your Hugging Face read token:
  ```env
  HF_TOKEN="hf_your_token_here"
  ```
- **FFmpeg**: Required for audio normalization. Ensure FFmpeg is installed on your Windows system and added to your system's `PATH`.
- **GPU Check**: You can verify that Python can access your NVIDIA GPU by running:
  ```powershell
  python verify_gpu.py
  ```
