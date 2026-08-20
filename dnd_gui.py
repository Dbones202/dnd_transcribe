"""
D&D Session Transcriber & Voice Harvester - Graphical User Interface
A rich, modern desktop application for transcribing tabletop RPG sessions,
managing voice profiles, refining transcripts with local LLMs, and analyzing diffs.
"""

import os
import sys
import time
import json
import glob
import queue
import ctypes
import threading
import datetime
import subprocess
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Ensure venv/Scripts is in PATH
_script_dir = os.path.dirname(os.path.abspath(__file__))
_venv_scripts = os.path.join(_script_dir, "venv", "Scripts")
if os.path.exists(_venv_scripts) and _venv_scripts not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _venv_scripts + os.pathsep + os.environ.get("PATH", "")

# Lazy import helper for backend
_backend = None
def get_backend():
    global _backend
    if _backend is None:
        import dnd_transcribe
        _backend = dnd_transcribe
    return _backend

# Try winsound for Windows audio playback
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Enable High-DPI Awareness on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ==========================================
# MODERN COLOR PALETTE & DESIGN SYSTEM
# ==========================================
COLORS = {
    "bg_app": "#0f1117",
    "bg_card": "#181a24",
    "bg_card_inner": "#1f2230",
    "bg_hover": "#282c3f",
    "border": "#2d3247",
    "border_focus": "#6366f1",
    
    "primary": "#6366f1",        # Indigo
    "primary_hover": "#4f46e5",
    "primary_active": "#4338ca",
    
    "success": "#10b981",        # Emerald
    "success_hover": "#059669",
    
    "warning": "#f59e0b",        # Amber
    "warning_hover": "#d97706",
    
    "danger": "#ef4444",         # Rose
    "danger_hover": "#dc2626",
    
    "text_main": "#f9fafb",
    "text_muted": "#9ca3af",
    "text_subtle": "#6b7280",
    
    "console_bg": "#0a0c10",
    "console_fg": "#e2e8f0",
    "console_info": "#60a5fa",
    "console_success": "#34d399",
    "console_warn": "#fbbf24",
    "console_error": "#f87171",
    "console_stage": "#c084fc",
}


def open_file_externally(filepath: str):
    """Opens a file using the default OS application."""
    if not filepath or not os.path.exists(filepath):
        messagebox.showwarning("File Not Found", f"The file '{filepath}' could not be found.")
        return
    try:
        if sys.platform == "win32":
            os.startfile(os.path.abspath(filepath))
        else:
            subprocess.run(["xdg-open", filepath], check=True)
    except Exception as e:
        messagebox.showerror("Error Opening File", f"Could not open file: {e}")


def open_folder_externally(folderpath: str):
    """Opens a folder in Windows Explorer."""
    if not folderpath or not os.path.exists(folderpath):
        os.makedirs(folderpath, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(os.path.abspath(folderpath))
        else:
            subprocess.run(["xdg-open", folderpath], check=True)
    except Exception as e:
        messagebox.showerror("Error", f"Could not open folder: {e}")


# ==========================================
# INTERACTIVE SPEAKER RESOLUTION MODAL
# ==========================================
class SpeakerIdentifyModal(tk.Toplevel):
    """
    Modal dialog for identifying an unknown speaker during the transcription pipeline.
    Provides audio clip playback, dropdown of enrolled voice profiles, and custom naming.
    """
    def __init__(self, parent, spk_tag, clip_path, best_match, best_score, library_speakers, duration):
        super().__init__(parent)
        self.title(f"Identify Speaker: {spk_tag}")
        self.geometry("540x440")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg_app"])
        self.transient(parent)
        self.grab_set()

        self.spk_tag = spk_tag
        self.clip_path = clip_path
        self.best_match = best_match
        self.best_score = best_score
        self.library_speakers = library_speakers
        self.duration = duration
        self.result = ""
        self.is_playing = False

        self._build_ui()
        self._center_window(parent)

        # Auto-play sample once loaded
        self.after(300, self._play_audio)

    def _center_window(self, parent):
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _build_ui(self):
        # Header banner
        header = tk.Frame(self, bg=COLORS["bg_card"], padx=20, pady=14, highlightthickness=1, highlightbackground=COLORS["border"])
        header.pack(fill="x", padx=16, pady=(16, 10))

        lbl_title = tk.Label(header, text=f"🎙️ Unrecognized Speaker: {self.spk_tag}", font=("Segoe UI", 12, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"])
        lbl_title.pack(anchor="w")

        info_text = f"Speech duration: ~{round(self.duration, 1)}s"
        if self.best_match and self.best_score > 0.35:
            info_text += f"  |  Closest match: '{self.best_match}' ({round(self.best_score * 100, 1)}%)"
        else:
            info_text += "  |  No confident match in Voice Library"

        lbl_sub = tk.Label(header, text=info_text, font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"])
        lbl_sub.pack(anchor="w", pady=(3, 0))

        # Audio Playback Card
        audio_card = tk.Frame(self, bg=COLORS["bg_card_inner"], padx=16, pady=12, highlightthickness=1, highlightbackground=COLORS["border"])
        audio_card.pack(fill="x", padx=16, pady=6)

        lbl_aud = tk.Label(audio_card, text="Listen to audio clip:", font=("Segoe UI", 9, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card_inner"])
        lbl_aud.pack(side="left", padx=(0, 12))

        self.btn_play = tk.Button(
            audio_card, text="▶️ Play Sample", font=("Segoe UI", 9, "bold"),
            bg=COLORS["primary"], fg=COLORS["text_main"], activebackground=COLORS["primary_hover"],
            activeforeground=COLORS["text_main"], relief="flat", padx=12, pady=4, cursor="hand2",
            command=self._play_audio
        )
        self.btn_play.pack(side="left", padx=4)

        # Identification Choice Card
        choice_card = tk.Frame(self, bg=COLORS["bg_card"], padx=16, pady=14, highlightthickness=1, highlightbackground=COLORS["border"])
        choice_card.pack(fill="both", expand=True, padx=16, pady=6)

        lbl_prompt = tk.Label(choice_card, text="Who was speaking in this clip?", font=("Segoe UI", 10, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"])
        lbl_prompt.pack(anchor="w", pady=(0, 8))

        # Radio 1: Existing Speaker
        self.choice_var = tk.StringVar(value="existing" if self.library_speakers else "new")

        if self.library_speakers:
            r1 = tk.Radiobutton(
                choice_card, text="Select existing player/character from Voice Library:",
                variable=self.choice_var, value="existing", font=("Segoe UI", 9),
                fg=COLORS["text_main"], bg=COLORS["bg_card"], selectcolor=COLORS["bg_app"],
                activebackground=COLORS["bg_card"], activeforeground=COLORS["text_main"]
            )
            r1.pack(anchor="w")

            combo_frame = tk.Frame(choice_card, bg=COLORS["bg_card"])
            combo_frame.pack(fill="x", padx=20, pady=(4, 10))

            self.combo_speakers = ttk.Combobox(combo_frame, values=sorted(self.library_speakers), state="readonly", font=("Segoe UI", 9))
            if self.best_match in self.library_speakers:
                self.combo_speakers.set(self.best_match)
            elif self.library_speakers:
                self.combo_speakers.set(self.library_speakers[0])
            self.combo_speakers.pack(fill="x")

        # Radio 2: New Speaker Name
        r2 = tk.Radiobutton(
            choice_card, text="Enter a new player or character name:",
            variable=self.choice_var, value="new", font=("Segoe UI", 9),
            fg=COLORS["text_main"], bg=COLORS["bg_card"], selectcolor=COLORS["bg_app"],
            activebackground=COLORS["bg_card"], activeforeground=COLORS["text_main"]
        )
        r2.pack(anchor="w")

        entry_frame = tk.Frame(choice_card, bg=COLORS["bg_card"])
        entry_frame.pack(fill="x", padx=20, pady=(4, 6))

        self.entry_new_name = tk.Entry(
            entry_frame, font=("Segoe UI", 10), bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"], insertbackground=COLORS["text_main"],
            relief="flat", highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border_focus"]
        )
        self.entry_new_name.pack(fill="x", ipady=4)
        if self.best_match:
            self.entry_new_name.insert(0, self.best_match)
        self.entry_new_name.bind("<Return>", lambda e: self._on_assign())

        # Buttons footer
        footer = tk.Frame(self, bg=COLORS["bg_app"], pady=12)
        footer.pack(fill="x", padx=16, side="bottom")

        btn_assign = tk.Button(
            footer, text="✅ Assign & Save Profile", font=("Segoe UI", 10, "bold"),
            bg=COLORS["success"], fg="#ffffff", activebackground=COLORS["success_hover"],
            activeforeground="#ffffff", relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._on_assign
        )
        btn_assign.pack(side="right", padx=(8, 0))

        btn_skip = tk.Button(
            footer, text=f"Skip (Keep {self.spk_tag})", font=("Segoe UI", 9),
            bg=COLORS["bg_hover"], fg=COLORS["text_muted"], activebackground=COLORS["border"],
            activeforeground=COLORS["text_main"], relief="flat", padx=12, pady=6, cursor="hand2",
            command=self._on_skip
        )
        btn_skip.pack(side="right")

    def _play_audio(self):
        if not HAS_WINSOUND or not self.clip_path or not os.path.exists(self.clip_path):
            return

        def _worker():
            try:
                self.btn_play.config(text="🔊 Playing...")
                winsound.PlaySound(self.clip_path, winsound.SND_FILENAME)
            except Exception:
                pass
            finally:
                if self.winfo_exists():
                    self.btn_play.config(text="▶️ Replay Sample")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_assign(self):
        mode = self.choice_var.get()
        if mode == "existing" and hasattr(self, "combo_speakers"):
            name = self.combo_speakers.get().strip()
        else:
            name = self.entry_new_name.get().strip()

        if not name:
            messagebox.showwarning("Name Required", "Please enter or select a speaker name, or click Skip.", parent=self)
            return

        self.result = name
        self.destroy()

    def _on_skip(self):
        self.result = ""
        self.destroy()


# ==========================================
# MAIN APPLICATION WINDOW
# ==========================================
class DnDTranscribeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("D&D Session Transcriber & Voice Harvester")
        self.geometry("1120x820")
        self.minsize(980, 680)
        self.configure(bg=COLORS["bg_app"])

        # State tracking
        self.pipeline_queue = queue.Queue()
        self.is_running = False
        self.current_worker = None
        self.cancellation_event = threading.Event()
        self.output_files = {}

        self._setup_styles()
        self._build_header()
        self._build_tabs()
        self._build_status_bar()

        # Start periodic UI event dispatcher
        self.after(50, self._poll_queue)

        # Initial background scan for diagnostics and files
        self._refresh_audio_dropdown()
        self._refresh_voice_library()
        self.after(500, self._async_run_diagnostics)

    def _setup_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Notebook tabs
        self.style.configure(
            "TNotebook",
            background=COLORS["bg_app"],
            borderwidth=0,
            tabmargins=[12, 8, 12, 0]
        )
        self.style.configure(
            "TNotebook.Tab",
            background=COLORS["bg_card"],
            foreground=COLORS["text_muted"],
            font=("Segoe UI", 10, "bold"),
            padding=[18, 10],
            borderwidth=0
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["primary"]), ("active", COLORS["bg_hover"])],
            foreground=[("selected", "#ffffff"), ("active", COLORS["text_main"])],
        )

        # Progress bar
        self.style.configure(
            "Horizontal.TProgressbar",
            background=COLORS["primary"],
            troughcolor=COLORS["bg_card_inner"],
            borderwidth=0,
            thickness=10
        )

        # Treeview for tables
        self.style.configure(
            "Treeview",
            background=COLORS["bg_card_inner"],
            foreground=COLORS["text_main"],
            fieldbackground=COLORS["bg_card_inner"],
            font=("Segoe UI", 9),
            rowheight=26,
            borderwidth=0
        )
        self.style.configure(
            "Treeview.Heading",
            background=COLORS["bg_card"],
            foreground=COLORS["text_muted"],
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
            padding=6
        )
        self.style.map(
            "Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", "#ffffff")]
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", COLORS["bg_hover"])]
        )

        # Scrollbars
        self.style.configure(
            "Vertical.TScrollbar",
            background=COLORS["bg_card"],
            troughcolor=COLORS["bg_app"],
            borderwidth=0,
            arrowsize=12
        )

    def _build_header(self):
        header_frame = tk.Frame(self, bg=COLORS["bg_card"], padx=20, pady=12, highlightthickness=1, highlightbackground=COLORS["border"])
        header_frame.pack(fill="x")

        title_box = tk.Frame(header_frame, bg=COLORS["bg_card"])
        title_box.pack(side="left")

        lbl_app_title = tk.Label(
            title_box, text="🎲 D&D Session Transcriber",
            font=("Segoe UI", 14, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"]
        )
        lbl_app_title.pack(anchor="w")

        lbl_app_sub = tk.Label(
            title_box, text="WhisperX · PyAnnote Diarization · Voice Biometrics · LM Studio Refinement",
            font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"]
        )
        lbl_app_sub.pack(anchor="w")

        # Top Quick Status Badges
        self.badge_box = tk.Frame(header_frame, bg=COLORS["bg_card"])
        self.badge_box.pack(side="right")

        self.lbl_gpu_badge = tk.Label(
            self.badge_box, text="GPU: Checking...", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["bg_card_inner"], padx=10, pady=4
        )
        self.lbl_gpu_badge.pack(side="left", padx=4)

        self.lbl_llm_badge = tk.Label(
            self.badge_box, text="LM Studio: Offline", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["bg_card_inner"], padx=10, pady=4
        )
        self.lbl_llm_badge.pack(side="left", padx=4)

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=10)

        # Tab 1: Transcription Studio
        self.tab_transcribe = tk.Frame(self.notebook, bg=COLORS["bg_app"])
        self.notebook.add(self.tab_transcribe, text="  🎙️ Transcribe Session  ")
        self._build_transcribe_tab()

        # Tab 2: AI Refinement & Diff Viewer
        self.tab_diff = tk.Frame(self.notebook, bg=COLORS["bg_app"])
        self.notebook.add(self.tab_diff, text="  🤖 AI Refinement & Diff  ")
        self._build_diff_tab()

        # Tab 3: Voice Library & Training
        self.tab_voices = tk.Frame(self.notebook, bg=COLORS["bg_app"])
        self.notebook.add(self.tab_voices, text="  🎓 Voice Library & Training  ")
        self._build_voices_tab()

        # Tab 4: System Diagnostics
        self.tab_diag = tk.Frame(self.notebook, bg=COLORS["bg_app"])
        self.notebook.add(self.tab_diag, text="  ⚙️ System Diagnostics  ")
        self._build_diagnostics_tab()

    def _build_status_bar(self):
        self.status_frame = tk.Frame(self, bg=COLORS["bg_card"], padx=16, pady=6, highlightthickness=1, highlightbackground=COLORS["border"])
        self.status_frame.pack(fill="x", side="bottom")

        self.lbl_status = tk.Label(
            self.status_frame, text="Ready.", font=("Segoe UI", 9),
            fg=COLORS["text_muted"], bg=COLORS["bg_card"]
        )
        self.lbl_status.pack(side="left")

        self.lbl_timer = tk.Label(
            self.status_frame, text="", font=("Segoe UI", 9, "bold"),
            fg=COLORS["primary"], bg=COLORS["bg_card"]
        )
        self.lbl_timer.pack(side="right")


    # =========================================================================
    # TAB 1: TRANSCRIBE SESSION
    # =========================================================================
    def _build_transcribe_tab(self):
        # Container PanedWindow (Top Controls / Bottom Console)
        paned = tk.PanedWindow(self.tab_transcribe, orient="vertical", bg=COLORS["bg_app"], bd=0, sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=4, pady=4)

        top_container = tk.Frame(paned, bg=COLORS["bg_app"])
        paned.add(top_container, minsize=320)

        # 1. AUDIO INPUT CARD
        input_card = tk.LabelFrame(
            top_container, text="  1. Select Session Audio Recording  ",
            font=("Segoe UI", 10, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"],
            padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["border"], bd=0
        )
        input_card.pack(fill="x", pady=(0, 8))

        row_file = tk.Frame(input_card, bg=COLORS["bg_card"])
        row_file.pack(fill="x")

        lbl_quick = tk.Label(row_file, text="Recent Audio:", font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"])
        lbl_quick.pack(side="left", padx=(0, 6))

        self.combo_audio_files = ttk.Combobox(row_file, state="readonly", font=("Segoe UI", 9), width=36)
        self.combo_audio_files.pack(side="left", padx=(0, 8))
        self.combo_audio_files.bind("<<ComboboxSelected>>", self._on_audio_combo_selected)

        btn_refresh_aud = tk.Button(
            row_file, text="🔄", font=("Segoe UI", 9), bg=COLORS["bg_hover"],
            fg=COLORS["text_main"], relief="flat", padx=8, pady=2, cursor="hand2",
            command=self._refresh_audio_dropdown
        )
        btn_refresh_aud.pack(side="left", padx=(0, 16))

        self.entry_audio_path = tk.Entry(
            row_file, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"], insertbackground=COLORS["text_main"],
            relief="flat", highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border_focus"]
        )
        self.entry_audio_path.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)

        btn_browse_audio = tk.Button(
            row_file, text="📂 Browse...", font=("Segoe UI", 9, "bold"),
            bg=COLORS["primary"], fg="#ffffff", activebackground=COLORS["primary_hover"],
            activeforeground="#ffffff", relief="flat", padx=12, pady=3, cursor="hand2",
            command=self._browse_audio_file
        )
        btn_browse_audio.pack(side="right")

        # 2. CONFIGURATION CARD (2 Columns)
        config_card = tk.LabelFrame(
            top_container, text="  2. Pipeline Configuration  ",
            font=("Segoe UI", 10, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"],
            padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["border"], bd=0
        )
        config_card.pack(fill="x", pady=(0, 8))

        cfg_cols = tk.Frame(config_card, bg=COLORS["bg_card"])
        cfg_cols.pack(fill="x")

        # Column Left: Hardware & Audio Preprocessing
        col_left = tk.Frame(cfg_cols, bg=COLORS["bg_card"])
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 16))

        lbl_hw_title = tk.Label(col_left, text="Audio & Diarization Hardware:", font=("Segoe UI", 9, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"])
        lbl_hw_title.pack(anchor="w", pady=(0, 4))

        self.diarize_device_var = tk.StringVar(value="cuda")
        r_gpu = tk.Radiobutton(
            col_left, text="GPU / CUDA (Recommended for NVIDIA RTX)",
            variable=self.diarize_device_var, value="cuda", font=("Segoe UI", 9),
            fg=COLORS["text_main"], bg=COLORS["bg_card"], selectcolor=COLORS["bg_app"],
            activebackground=COLORS["bg_card"], activeforeground=COLORS["text_main"]
        )
        r_gpu.pack(anchor="w")

        r_cpu = tk.Radiobutton(
            col_left, text="CPU Diarization (Fallback if VRAM Out Of Memory)",
            variable=self.diarize_device_var, value="cpu", font=("Segoe UI", 9),
            fg=COLORS["text_muted"], bg=COLORS["bg_card"], selectcolor=COLORS["bg_app"],
            activebackground=COLORS["bg_card"], activeforeground=COLORS["text_main"]
        )
        r_cpu.pack(anchor="w")

        self.normalize_audio_var = tk.BooleanVar(value=True)
        chk_norm = tk.Checkbutton(
            col_left, text="Enable Dynamic Normalization (FFmpeg dynaudnorm)",
            variable=self.normalize_audio_var, font=("Segoe UI", 9),
            fg=COLORS["text_main"], bg=COLORS["bg_card"], selectcolor=COLORS["bg_app"],
            activebackground=COLORS["bg_card"], activeforeground=COLORS["text_main"]
        )
        chk_norm.pack(anchor="w", pady=(4, 0))

        # Batch Size Setting
        row_wbatch = tk.Frame(col_left, bg=COLORS["bg_card"])
        row_wbatch.pack(anchor="w", pady=(6, 0))
        tk.Label(row_wbatch, text="WhisperX Batch Size:", font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left", padx=(0, 6))
        self.combo_whisper_batch = ttk.Combobox(row_wbatch, values=["4", "8", "16", "24", "32"], width=6, state="readonly", font=("Segoe UI", 9))
        self.combo_whisper_batch.set("8")
        self.combo_whisper_batch.pack(side="left")

        # Column Right: LM Studio Refinement
        col_right = tk.Frame(cfg_cols, bg=COLORS["bg_card"])
        col_right.pack(side="right", fill="both", expand=True, padx=(16, 0))

        lbl_llm_cfg = tk.Label(col_right, text="Local LLM Transcript Refinement:", font=("Segoe UI", 9, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"])
        lbl_llm_cfg.pack(anchor="w", pady=(0, 4))

        self.enable_llm_var = tk.BooleanVar(value=True)
        chk_llm = tk.Checkbutton(
            col_right, text="Refine D&D homophones & clean dialogue with LM Studio",
            variable=self.enable_llm_var, font=("Segoe UI", 9),
            fg=COLORS["text_main"], bg=COLORS["bg_card"], selectcolor=COLORS["bg_app"],
            activebackground=COLORS["bg_card"], activeforeground=COLORS["text_main"]
        )
        chk_llm.pack(anchor="w")

        row_api = tk.Frame(col_right, bg=COLORS["bg_card"])
        row_api.pack(fill="x", pady=(4, 0))
        tk.Label(row_api, text="API URL:", font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left", padx=(0, 6))
        self.entry_llm_url = tk.Entry(
            row_api, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"], insertbackground=COLORS["text_main"],
            relief="flat", highlightthickness=1, highlightbackground=COLORS["border"], width=24
        )
        self.entry_llm_url.insert(0, os.getenv("LLM_API_URL", "http://localhost:1234/v1"))
        self.entry_llm_url.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=2)

        btn_test_llm = tk.Button(
            row_api, text="🔌 Test", font=("Segoe UI", 8, "bold"), bg=COLORS["bg_hover"],
            fg=COLORS["text_main"], relief="flat", padx=8, pady=2, cursor="hand2",
            command=self._test_lm_studio_connection
        )
        btn_test_llm.pack(side="right")

        row_lbatch = tk.Frame(col_right, bg=COLORS["bg_card"])
        row_lbatch.pack(anchor="w", pady=(6, 0))
        tk.Label(row_lbatch, text="LLM Batch Size:", font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left", padx=(0, 6))
        self.combo_llm_batch = ttk.Combobox(row_lbatch, values=["15", "25", "50", "75"], width=6, state="readonly", font=("Segoe UI", 9))
        self.combo_llm_batch.set("25")
        self.combo_llm_batch.pack(side="left")

        # 3. ACTION & PIPELINE PROGRESS CARD
        action_card = tk.Frame(top_container, bg=COLORS["bg_card"], padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["border"])
        action_card.pack(fill="x", pady=(0, 8))

        row_action = tk.Frame(action_card, bg=COLORS["bg_card"])
        row_action.pack(fill="x")

        self.btn_start = tk.Button(
            row_action, text="🚀 START TRANSCRIPTION", font=("Segoe UI", 11, "bold"),
            bg=COLORS["success"], fg="#ffffff", activebackground=COLORS["success_hover"],
            activeforeground="#ffffff", relief="flat", padx=20, pady=8, cursor="hand2",
            command=self._on_start_transcription
        )
        self.btn_start.pack(side="left")

        self.btn_stop = tk.Button(
            row_action, text="⏹️ Stop Pipeline", font=("Segoe UI", 9, "bold"),
            bg=COLORS["danger"], fg="#ffffff", activebackground=COLORS["danger_hover"],
            activeforeground="#ffffff", relief="flat", padx=14, pady=8, state="disabled",
            cursor="hand2", command=self._on_stop_transcription
        )
        self.btn_stop.pack(side="left", padx=10)

        # Multi-Phase Pipeline Indicator Badges
        self.stage_box = tk.Frame(row_action, bg=COLORS["bg_card"])
        self.stage_box.pack(side="right")

        self.stage_labels = {}
        stages = [("Norm", "1. Norm"), ("Trans", "2. Transcribe"), ("Align", "3. Align"), ("Diar", "4. Diarize"), ("Voice", "5. Voice ID"), ("LLM", "6. LLM"), ("Done", "7. Done")]
        for key, name in stages:
            lbl = tk.Label(
                self.stage_box, text=name, font=("Segoe UI", 8, "bold"),
                fg=COLORS["text_subtle"], bg=COLORS["bg_card_inner"], padx=7, pady=4
            )
            lbl.pack(side="left", padx=2)
            self.stage_labels[key] = lbl

        # Progress bar
        row_prog = tk.Frame(action_card, bg=COLORS["bg_card"])
        row_prog.pack(fill="x", pady=(10, 0))

        self.progress_bar = ttk.Progressbar(row_prog, orient="horizontal", mode="determinate", style="Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", side="left", expand=True, padx=(0, 10))

        self.lbl_progress_pct = tk.Label(row_prog, text="0%", font=("Segoe UI", 9, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"], width=5)
        self.lbl_progress_pct.pack(side="right")

        # 4. OUTPUT RESULTS BANNER (Hidden until complete)
        self.output_banner = tk.Frame(top_container, bg=COLORS["bg_card_inner"], padx=14, pady=8, highlightthickness=1, highlightbackground=COLORS["success"])

        lbl_out_title = tk.Label(self.output_banner, text="✨ Outputs Ready:", font=("Segoe UI", 9, "bold"), fg=COLORS["success"], bg=COLORS["bg_card_inner"])
        lbl_out_title.pack(side="left", padx=(0, 8))

        self.btn_open_raw = tk.Button(
            self.output_banner, text="📄 Raw Transcript", font=("Segoe UI", 8, "bold"),
            bg=COLORS["bg_card"], fg=COLORS["text_main"], relief="flat", padx=8, pady=3, cursor="hand2",
            command=lambda: open_file_externally(self.output_files.get("raw_path"))
        )
        self.btn_open_raw.pack(side="left", padx=3)

        self.btn_open_refined = tk.Button(
            self.output_banner, text="✨ Refined Transcript", font=("Segoe UI", 8, "bold"),
            bg=COLORS["bg_card"], fg=COLORS["text_main"], relief="flat", padx=8, pady=3, cursor="hand2",
            command=lambda: open_file_externally(self.output_files.get("refined_path"))
        )
        self.btn_open_refined.pack(side="left", padx=3)

        self.btn_open_diff = tk.Button(
            self.output_banner, text="📊 AI Diff Report", font=("Segoe UI", 8, "bold"),
            bg=COLORS["bg_card"], fg=COLORS["text_main"], relief="flat", padx=8, pady=3, cursor="hand2",
            command=lambda: open_file_externally(self.output_files.get("diff_path"))
        )
        self.btn_open_diff.pack(side="left", padx=3)

        self.btn_open_folder = tk.Button(
            self.output_banner, text="📂 Open Folder", font=("Segoe UI", 8, "bold"),
            bg=COLORS["primary"], fg="#ffffff", relief="flat", padx=8, pady=3, cursor="hand2",
            command=lambda: open_folder_externally(os.path.join(_script_dir, "transcripts"))
        )
        self.btn_open_folder.pack(side="right")

        # 5. BOTTOM CONSOLE LOG CARD
        bottom_container = tk.Frame(paned, bg=COLORS["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=COLORS["border"])
        paned.add(bottom_container, minsize=200)

        con_header = tk.Frame(bottom_container, bg=COLORS["bg_card"])
        con_header.pack(fill="x", pady=(0, 4))

        tk.Label(con_header, text="📋 Execution Log & Real-time Metrics", font=("Segoe UI", 9, "bold"), fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left")

        btn_clear_log = tk.Button(
            con_header, text="Clear Log", font=("Segoe UI", 8), bg=COLORS["bg_hover"],
            fg=COLORS["text_muted"], relief="flat", padx=8, pady=1, cursor="hand2",
            command=self._clear_console
        )
        btn_clear_log.pack(side="right")

        # Text Console
        con_body = tk.Frame(bottom_container, bg=COLORS["console_bg"])
        con_body.pack(fill="both", expand=True)

        self.console_text = tk.Text(
            con_body, bg=COLORS["console_bg"], fg=COLORS["console_fg"],
            font=("Consolas", 9), wrap="word", relief="flat", padx=8, pady=6,
            insertbackground=COLORS["text_main"]
        )
        self.console_text.pack(side="left", fill="both", expand=True)

        con_scroll = ttk.Scrollbar(con_body, orient="vertical", command=self.console_text.yview, style="Vertical.TScrollbar")
        con_scroll.pack(side="right", fill="y")
        self.console_text.config(yscrollcommand=con_scroll.set)

        # Tags for colored console lines
        self.console_text.tag_config("INFO", foreground=COLORS["console_fg"])
        self.console_text.tag_config("SUCCESS", foreground=COLORS["console_success"])
        self.console_text.tag_config("WARNING", foreground=COLORS["console_warn"])
        self.console_text.tag_config("ERROR", foreground=COLORS["console_error"])
        self.console_text.tag_config("STAGE", foreground=COLORS["console_stage"])


    # =========================================================================
    # TAB 2: AI REFINEMENT & DIFF VIEWER
    # =========================================================================
    def _build_diff_tab(self):
        paned = tk.PanedWindow(self.tab_diff, orient="vertical", bg=COLORS["bg_app"], bd=0, sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        top_frame = tk.Frame(paned, bg=COLORS["bg_app"])
        paned.add(top_frame, minsize=260)

        # Tool 1: Standalone Refinement
        refine_card = tk.LabelFrame(
            top_frame, text="  🤖 Standalone AI Refinement (Refine existing raw transcript)  ",
            font=("Segoe UI", 10, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"],
            padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["border"], bd=0
        )
        refine_card.pack(fill="x", pady=(0, 10))

        row_rf = tk.Frame(refine_card, bg=COLORS["bg_card"])
        row_rf.pack(fill="x", pady=(2, 6))

        tk.Label(row_rf, text="Raw Transcript (.md):", font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left", padx=(0, 6))
        self.entry_refine_md = tk.Entry(
            row_rf, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"], fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"], relief="flat", highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.entry_refine_md.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)

        btn_browse_ref = tk.Button(
            row_rf, text="📂 Browse...", font=("Segoe UI", 9), bg=COLORS["bg_hover"],
            fg=COLORS["text_main"], relief="flat", padx=10, pady=2, cursor="hand2",
            command=self._browse_refine_md
        )
        btn_browse_ref.pack(side="right")

        row_rf_act = tk.Frame(refine_card, bg=COLORS["bg_card"])
        row_rf_act.pack(fill="x", pady=(4, 0))

        self.btn_run_refine = tk.Button(
            row_rf_act, text="✨ Run Local LLM Refinement & Diff", font=("Segoe UI", 9, "bold"),
            bg=COLORS["primary"], fg="#ffffff", activebackground=COLORS["primary_hover"],
            activeforeground="#ffffff", relief="flat", padx=14, pady=6, cursor="hand2",
            command=self._on_run_standalone_refine
        )
        self.btn_run_refine.pack(side="left")

        # Tool 2: Compare Any Two Transcripts
        diff_card = tk.LabelFrame(
            top_frame, text="  📊 Compare Two Transcripts (Generate AI Diff Report)  ",
            font=("Segoe UI", 10, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"],
            padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["border"], bd=0
        )
        diff_card.pack(fill="x")

        row_d1 = tk.Frame(diff_card, bg=COLORS["bg_card"])
        row_d1.pack(fill="x", pady=2)
        tk.Label(row_d1, text="Raw File:        ", font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left", padx=(0, 6))
        self.entry_diff_raw = tk.Entry(
            row_d1, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"], fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"], relief="flat", highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.entry_diff_raw.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=2)
        tk.Button(row_d1, text="📂 Browse", font=("Segoe UI", 8), bg=COLORS["bg_hover"], fg=COLORS["text_main"], relief="flat", padx=8, pady=1, cursor="hand2", command=lambda: self._browse_into_entry(self.entry_diff_raw)).pack(side="right")

        row_d2 = tk.Frame(diff_card, bg=COLORS["bg_card"])
        row_d2.pack(fill="x", pady=(4, 6))
        tk.Label(row_d2, text="Refined File: ", font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left", padx=(0, 6))
        self.entry_diff_refined = tk.Entry(
            row_d2, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"], fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"], relief="flat", highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.entry_diff_refined.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=2)
        tk.Button(row_d2, text="📂 Browse", font=("Segoe UI", 8), bg=COLORS["bg_hover"], fg=COLORS["text_main"], relief="flat", padx=8, pady=1, cursor="hand2", command=lambda: self._browse_into_entry(self.entry_diff_refined)).pack(side="right")

        self.btn_run_diff = tk.Button(
            diff_card, text="📊 Compare & View Changes", font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_hover"], fg=COLORS["text_main"], relief="flat", padx=14, pady=5, cursor="hand2",
            command=self._on_run_diff_tool
        )
        self.btn_run_diff.pack(anchor="w", pady=(2, 0))

        # Bottom Diff Report & Table Viewer
        diff_viewer_card = tk.Frame(paned, bg=COLORS["bg_card"], padx=12, pady=10, highlightthickness=1, highlightbackground=COLORS["border"])
        paned.add(diff_viewer_card, minsize=240)

        header_dv = tk.Frame(diff_viewer_card, bg=COLORS["bg_card"])
        header_dv.pack(fill="x", pady=(0, 6))

        self.lbl_diff_summary = tk.Label(header_dv, text="Line-by-Line Changes (Select or generate a diff above):", font=("Segoe UI", 9, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"])
        self.lbl_diff_summary.pack(side="left")

        self.btn_open_current_diff = tk.Button(
            header_dv, text="📄 Open Diff .md File", font=("Segoe UI", 8),
            bg=COLORS["bg_hover"], fg=COLORS["text_muted"], relief="flat", padx=8, pady=2, cursor="hand2",
            command=self._open_active_diff_file
        )
        self.btn_open_current_diff.pack(side="right")

        # Treeview for Diff Changes
        columns = ("line", "spk", "raw", "refined")
        self.tree_diff = ttk.Treeview(diff_viewer_card, columns=columns, show="headings", selectmode="browse")
        self.tree_diff.heading("line", text="Line #")
        self.tree_diff.heading("spk", text="Timestamp & Speaker")
        self.tree_diff.heading("raw", text="Before AI (Raw)")
        self.tree_diff.heading("refined", text="After AI (Refined)")

        self.tree_diff.column("line", width=60, minwidth=50, stretch=False, anchor="center")
        self.tree_diff.column("spk", width=220, minwidth=150, stretch=False)
        self.tree_diff.column("raw", width=400, minwidth=250, stretch=True)
        self.tree_diff.column("refined", width=400, minwidth=250, stretch=True)

        self.tree_diff.pack(side="left", fill="both", expand=True)

        diff_scroll = ttk.Scrollbar(diff_viewer_card, orient="vertical", command=self.tree_diff.yview, style="Vertical.TScrollbar")
        diff_scroll.pack(side="right", fill="y")
        self.tree_diff.config(yscrollcommand=diff_scroll.set)


    # =========================================================================
    # TAB 3: VOICE LIBRARY & TRAINING
    # =========================================================================
    def _build_voices_tab(self):
        # 2-Column Split: Left = Enrolled Profiles Manager / Right = Voice Harvester Trainer
        container = tk.Frame(self.tab_voices, bg=COLORS["bg_app"])
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # LEFT: Voice Library Profiles
        left_card = tk.LabelFrame(
            container, text="  📁 Enrolled Voice Profiles (voice_library/)  ",
            font=("Segoe UI", 10, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"],
            padx=12, pady=10, highlightthickness=1, highlightbackground=COLORS["border"], bd=0
        )
        left_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Search bar & actions
        row_vact = tk.Frame(left_card, bg=COLORS["bg_card"])
        row_vact.pack(fill="x", pady=(0, 8))

        self.entry_voice_search = tk.Entry(
            row_vact, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"], fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"], relief="flat", highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.entry_voice_search.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=2)
        self.entry_voice_search.bind("<KeyRelease>", lambda e: self._filter_voice_library())

        btn_ref_lib = tk.Button(
            row_vact, text="🔄 Refresh", font=("Segoe UI", 8), bg=COLORS["bg_hover"],
            fg=COLORS["text_main"], relief="flat", padx=8, pady=2, cursor="hand2",
            command=self._refresh_voice_library
        )
        btn_ref_lib.pack(side="right")

        # Treeview for voices
        v_cols = ("name", "size", "modified")
        self.tree_voices = ttk.Treeview(left_card, columns=v_cols, show="headings", selectmode="browse")
        self.tree_voices.heading("name", text="Speaker Name")
        self.tree_voices.heading("size", text="Profile Size")
        self.tree_voices.heading("modified", text="Last Updated")

        self.tree_voices.column("name", width=180, minwidth=120, stretch=True)
        self.tree_voices.column("size", width=90, minwidth=70, stretch=False, anchor="center")
        self.tree_voices.column("modified", width=150, minwidth=120, stretch=False, anchor="center")

        self.tree_voices.pack(side="left", fill="both", expand=True)

        v_scroll = ttk.Scrollbar(left_card, orient="vertical", command=self.tree_voices.yview, style="Vertical.TScrollbar")
        v_scroll.pack(side="right", fill="y")
        self.tree_voices.config(yscrollcommand=v_scroll.set)

        # Action buttons under voice table
        row_vbtns = tk.Frame(left_card, bg=COLORS["bg_card"])
        row_vbtns.pack(fill="x", pady=(8, 0), side="bottom")

        btn_del_v = tk.Button(
            row_vbtns, text="🗑️ Delete Profile", font=("Segoe UI", 9),
            bg=COLORS["danger"], fg="#ffffff", activebackground=COLORS["danger_hover"],
            activeforeground="#ffffff", relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._on_delete_voice_profile
        )
        btn_del_v.pack(side="left")

        btn_ren_v = tk.Button(
            row_vbtns, text="✏️ Rename", font=("Segoe UI", 9),
            bg=COLORS["bg_hover"], fg=COLORS["text_main"], relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._on_rename_voice_profile
        )
        btn_ren_v.pack(side="left", padx=8)

        btn_op_vdir = tk.Button(
            row_vbtns, text="📂 Open Folder", font=("Segoe UI", 9),
            bg=COLORS["bg_hover"], fg=COLORS["text_main"], relief="flat", padx=10, pady=4, cursor="hand2",
            command=lambda: open_folder_externally(os.path.join(_script_dir, "voice_library"))
        )
        btn_op_vdir.pack(side="right")

        # RIGHT: Voice Harvester (Training from Edited Transcript)
        right_card = tk.LabelFrame(
            container, text="  🎯 Voice Harvester (Train from Edited Transcript)  ",
            font=("Segoe UI", 10, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"],
            padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["border"], bd=0
        )
        right_card.pack(side="right", fill="both", expand=True, padx=(8, 0))

        lbl_hinfo = tk.Label(
            right_card,
            text="Train the Voice Library from an edited transcript where you replaced\n"
                 "generic 'SPEAKER_XX' tags with real player names.\n"
                 "Both the edited markdown and matching audio recording are required.",
            font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"], justify="left"
        )
        lbl_hinfo.pack(anchor="w", pady=(0, 12))

        # Edited Markdown picker
        tk.Label(right_card, text="Edited Markdown Transcript (.md):", font=("Segoe UI", 9, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"]).pack(anchor="w")
        row_hmd = tk.Frame(right_card, bg=COLORS["bg_card"])
        row_hmd.pack(fill="x", pady=(2, 10))

        self.entry_train_md = tk.Entry(
            row_hmd, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"], fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"], relief="flat", highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.entry_train_md.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=3)
        tk.Button(row_hmd, text="📂 Browse", font=("Segoe UI", 8), bg=COLORS["bg_hover"], fg=COLORS["text_main"], relief="flat", padx=8, pady=2, cursor="hand2", command=lambda: self._browse_into_entry(self.entry_train_md)).pack(side="right")

        # Audio file picker
        tk.Label(right_card, text="Matching Audio Recording (.wav / .mp3):", font=("Segoe UI", 9, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"]).pack(anchor="w")
        row_haud = tk.Frame(right_card, bg=COLORS["bg_card"])
        row_haud.pack(fill="x", pady=(2, 16))

        self.entry_train_audio = tk.Entry(
            row_haud, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"], fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"], relief="flat", highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.entry_train_audio.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=3)
        tk.Button(row_haud, text="📂 Browse", font=("Segoe UI", 8), bg=COLORS["bg_hover"], fg=COLORS["text_main"], relief="flat", padx=8, pady=2, cursor="hand2", command=lambda: self._browse_into_entry(self.entry_train_audio)).pack(side="right")

        self.btn_run_training = tk.Button(
            right_card, text="🎯 Harvest & Refine Voice Profiles", font=("Segoe UI", 10, "bold"),
            bg=COLORS["primary"], fg="#ffffff", activebackground=COLORS["primary_hover"],
            activeforeground="#ffffff", relief="flat", padx=16, pady=8, cursor="hand2",
            command=self._on_run_voice_training
        )
        self.btn_run_training.pack(anchor="w", pady=(0, 12))

        # Harvester result output box
        tk.Label(right_card, text="Harvesting Progress & Results:", font=("Segoe UI", 9, "bold"), fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(anchor="w", pady=(4, 2))
        self.txt_train_log = tk.Text(
            right_card, bg=COLORS["bg_card_inner"], fg=COLORS["text_main"],
            font=("Consolas", 9), wrap="word", relief="flat", padx=8, pady=6, height=10
        )
        self.txt_train_log.pack(fill="both", expand=True)


    # =========================================================================
    # TAB 4: SYSTEM DIAGNOSTICS
    # =========================================================================
    def _build_diagnostics_tab(self):
        container = tk.Frame(self.tab_diag, bg=COLORS["bg_app"])
        container.pack(fill="both", expand=True, padx=14, pady=14)

        # Header with Refresh
        row_dtop = tk.Frame(container, bg=COLORS["bg_app"])
        row_dtop.pack(fill="x", pady=(0, 12))

        tk.Label(row_dtop, text="System Environment & AI Diagnostic Status", font=("Segoe UI", 12, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_app"]).pack(side="left")

        btn_run_diag = tk.Button(
            row_dtop, text="🔄 Re-check All Diagnostics", font=("Segoe UI", 9, "bold"),
            bg=COLORS["primary"], fg="#ffffff", relief="flat", padx=12, pady=4, cursor="hand2",
            command=self._async_run_diagnostics
        )
        btn_run_diag.pack(side="right")

        # Diagnostics Grid
        diag_grid = tk.Frame(container, bg=COLORS["bg_card"], padx=18, pady=16, highlightthickness=1, highlightbackground=COLORS["border"])
        diag_grid.pack(fill="x", pady=(0, 12))

        self.diag_items = {}
        checks = [
            ("gpu", "NVIDIA CUDA Acceleration:"),
            ("vram", "GPU VRAM Available:"),
            ("torch", "PyTorch Version:"),
            ("whisperx", "WhisperX ASR Engine:"),
            ("ffmpeg", "FFmpeg Binary in PATH:"),
            ("hf_token", "Hugging Face Token (.env):"),
            ("lm_studio", "LM Studio Server Status:"),
            ("sleep_prevent", "Windows Sleep Prevention:")
        ]

        for idx, (key, label_text) in enumerate(checks):
            row = idx // 2
            col = (idx % 2) * 2

            lbl_key = tk.Label(diag_grid, text=label_text, font=("Segoe UI", 9, "bold"), fg=COLORS["text_muted"], bg=COLORS["bg_card"])
            lbl_key.grid(row=row, column=col, sticky="w", padx=(10, 8), pady=8)

            lbl_val = tk.Label(diag_grid, text="Checking...", font=("Segoe UI", 9), fg=COLORS["text_main"], bg=COLORS["bg_card"])
            lbl_val.grid(row=row, column=col+1, sticky="w", padx=(0, 24), pady=8)
            self.diag_items[key] = lbl_val

        # Hugging Face Token Configuration Card
        hf_card = tk.LabelFrame(
            container, text="  🔑 Hugging Face Token Configuration (.env)  ",
            font=("Segoe UI", 10, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"],
            padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["border"], bd=0
        )
        hf_card.pack(fill="x", pady=(0, 12))

        tk.Label(
            hf_card, text="PyAnnote speaker diarization requires a Hugging Face Read Token.",
            font=("Segoe UI", 9), fg=COLORS["text_muted"], bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 6))

        row_hf = tk.Frame(hf_card, bg=COLORS["bg_card"])
        row_hf.pack(fill="x")

        self.entry_hf_token = tk.Entry(
            row_hf, font=("Segoe UI", 9), bg=COLORS["bg_card_inner"], fg=COLORS["text_main"],
            insertbackground=COLORS["text_main"], relief="flat", highlightthickness=1,
            highlightbackground=COLORS["border"], show="*"
        )
        token_env = os.getenv("HF_TOKEN", "")
        if token_env:
            self.entry_hf_token.insert(0, token_env)
        self.entry_hf_token.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)

        self.btn_show_token = tk.Button(
            row_hf, text="👁️ Show", font=("Segoe UI", 8), bg=COLORS["bg_hover"],
            fg=COLORS["text_main"], relief="flat", padx=8, pady=2, cursor="hand2",
            command=self._toggle_token_visibility
        )
        self.btn_show_token.pack(side="left", padx=(0, 8))

        btn_save_hf = tk.Button(
            row_hf, text="💾 Save to .env", font=("Segoe UI", 9, "bold"),
            bg=COLORS["success"], fg="#ffffff", relief="flat", padx=12, pady=3, cursor="hand2",
            command=self._save_hf_token
        )
        btn_save_hf.pack(side="right")


    # =========================================================================
    # QUEUE DISPATCHER & LOGGING ENGINE
    # =========================================================================
    def _poll_queue(self):
        """Processes messages from background threads in a thread-safe manner."""
        try:
            while True:
                msg = self.pipeline_queue.get_nowait()
                msg_type = msg.get("type")

                if msg_type == "LOG":
                    self._append_console(msg.get("text", ""), msg.get("level", "INFO"))

                elif msg_type == "PROGRESS":
                    phase = msg.get("phase", "")
                    pct = msg.get("percent", 0.0)
                    desc = msg.get("desc", "")
                    self._update_progress(phase, pct, desc)

                elif msg_type == "STAGE":
                    stage_key = msg.get("stage")
                    self._highlight_stage(stage_key)

                elif msg_type == "COMPLETE":
                    self._on_pipeline_completed(msg.get("results", {}))

                elif msg_type == "ERROR":
                    self._on_pipeline_error(msg.get("error", "Unknown error"))

                elif msg_type == "IDENTIFY_SPEAKER":
                    self._handle_identify_speaker_event(msg)

                elif msg_type == "DIAG_UPDATE":
                    key = msg.get("key")
                    val = msg.get("val")
                    color = msg.get("color", COLORS["text_main"])
                    if key in self.diag_items:
                        self.diag_items[key].config(text=val, fg=color)

                self.pipeline_queue.task_done()
        except queue.Empty:
            pass

        self.after(50, self._poll_queue)

    def _append_console(self, text: str, level: str = "INFO"):
        self.console_text.insert("end", text + "\n", level)
        self.console_text.see("end")

    def _clear_console(self):
        self.console_text.delete("1.0", "end")

    def _update_progress(self, phase: str, pct: float, desc: str):
        clamped_pct = max(0.0, min(100.0, pct))
        self.progress_bar["value"] = clamped_pct
        self.lbl_progress_pct.config(text=f"{int(clamped_pct)}%")
        if desc:
            self.lbl_status.config(text=f"[{phase}] {desc}")

    def _highlight_stage(self, stage_key: str):
        for key, lbl in self.stage_labels.items():
            if key == stage_key:
                lbl.config(bg=COLORS["primary"], fg="#ffffff")
            elif key == "Done" and stage_key == "Done":
                lbl.config(bg=COLORS["success"], fg="#ffffff")
            else:
                lbl.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_subtle"])

    def _reset_stages(self):
        for lbl in self.stage_labels.values():
            lbl.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_subtle"])
        self.progress_bar["value"] = 0
        self.lbl_progress_pct.config(text="0%")


    # =========================================================================
    # PIPELINE EXECUTION WRAPPERS (BACKGROUND THREADS)
    # =========================================================================
    def _on_start_transcription(self):
        audio_path = self.entry_audio_path.get().strip('"\' ')
        if not audio_path or not os.path.exists(audio_path):
            messagebox.showwarning("File Required", "Please select a valid audio recording file to transcribe.")
            return

        self.is_running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.output_banner.pack_forget()
        self._reset_stages()
        self._clear_console()

        diarize_dev = self.diarize_device_var.get()
        normalize = self.normalize_audio_var.get()
        skip_llm = not self.enable_llm_var.get()
        llm_url = self.entry_llm_url.get().strip()
        try:
            whisper_b = int(self.combo_whisper_batch.get())
        except Exception:
            whisper_b = 8
        try:
            llm_b = int(self.combo_llm_batch.get())
        except Exception:
            llm_b = 25

        self.cancellation_event.clear()
        start_time = time.time()

        def _log_cb(line):
            lvl = "INFO"
            if "[ERROR]" in line or "Error" in line:
                lvl = "ERROR"
            elif "[Success]" in line or "Saved" in line or "[Match]" in line:
                lvl = "SUCCESS"
            elif "[WARNING]" in line or "Warning" in line:
                lvl = "WARNING"
            elif "---" in line:
                lvl = "STAGE"
            self.pipeline_queue.put({"type": "LOG", "text": line, "level": lvl})

        def _prog_cb(phase, percent, msg):
            stage_map = {
                "Normalization": "Norm",
                "Transcription": "Trans",
                "Alignment": "Align",
                "Diarization": "Diar",
                "Voice Identification": "Voice",
                "LLM Refinement": "LLM",
                "Complete": "Done"
            }
            if phase in stage_map:
                self.pipeline_queue.put({"type": "STAGE", "stage": stage_map[phase]})
            self.pipeline_queue.put({"type": "PROGRESS", "phase": phase, "percent": percent, "desc": msg})

        def _speaker_identify_cb(spk_tag, audio_clip_path, best_match, best_score, library_names, duration):
            # Sync with main UI thread
            resp_event = threading.Event()
            res_container = {"name": ""}
            self.pipeline_queue.put({
                "type": "IDENTIFY_SPEAKER",
                "spk_tag": spk_tag,
                "clip_path": audio_clip_path,
                "best_match": best_match,
                "best_score": best_score,
                "library_speakers": library_names,
                "duration": duration,
                "event": resp_event,
                "container": res_container
            })
            resp_event.wait()
            return res_container["name"]

        def _worker():
            try:
                results = get_backend().run_dnd_session(
                    audio_path=audio_path,
                    skip_llm=skip_llm,
                    batch_size=llm_b,
                    whisper_batch_size=whisper_b,
                    device_diarize=diarize_dev,
                    normalize_audio=normalize,
                    api_url=llm_url,
                    progress_cb=_prog_cb,
                    log_cb=_log_cb,
                    speaker_identify_cb=_speaker_identify_cb
                )
                self.pipeline_queue.put({"type": "COMPLETE", "results": results or {}})
            except Exception as e:
                import traceback
                self.pipeline_queue.put({"type": "ERROR", "error": f"{e}\n{traceback.format_exc()}"})

        self.current_worker = threading.Thread(target=_worker, daemon=True)
        self.current_worker.start()

        # Update elapsed timer periodically
        def _update_timer():
            if self.is_running:
                elapsed = int(time.time() - start_time)
                self.lbl_timer.config(text=f"⏱️ Elapsed: {str(datetime.timedelta(seconds=elapsed))}")
                self.after(1000, _update_timer)
        _update_timer()

    def _on_stop_transcription(self):
        if messagebox.askyesno("Confirm Stop", "Are you sure you want to cancel the active transcription?"):
            self.cancellation_event.set()
            self._append_console("\n[System] Cancellation requested by user.", "WARNING")
            self.btn_stop.config(state="disabled")

    def _handle_identify_speaker_event(self, msg):
        modal = SpeakerIdentifyModal(
            parent=self,
            spk_tag=msg["spk_tag"],
            clip_path=msg["clip_path"],
            best_match=msg["best_match"],
            best_score=msg["best_score"],
            library_speakers=msg["library_speakers"],
            duration=msg["duration"]
        )
        self.wait_window(modal)
        msg["container"]["name"] = modal.result
        msg["event"].set()

    def _on_pipeline_completed(self, results: dict):
        self.is_running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._highlight_stage("Done")
        self.progress_bar["value"] = 100
        self.lbl_progress_pct.config(text="100%")
        self.lbl_status.config(text="Transcription finished successfully!")

        self.output_files = results
        self.output_banner.pack(fill="x", pady=(0, 8), after=self.stage_box.master.master)

        if results.get("refined_path"):
            self.btn_open_refined.config(state="normal")
            self.btn_open_diff.config(state="normal")
        else:
            self.btn_open_refined.config(state="disabled")
            self.btn_open_diff.config(state="disabled")

        self._refresh_voice_library()
        messagebox.showinfo("Transcription Complete", "Session transcription and analysis completed successfully!")

    def _on_pipeline_error(self, err_msg: str):
        self.is_running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._append_console(f"\n[PIPELINE ERROR]\n{err_msg}", "ERROR")
        self.lbl_status.config(text="Pipeline encountered an error.")
        messagebox.showerror("Transcription Error", f"An error occurred during execution:\n\n{err_msg}")


    # =========================================================================
    # TAB 2 ACTIONS: STANDALONE REFINEMENT & DIFF
    # =========================================================================
    def _browse_refine_md(self):
        path = filedialog.askopenfilename(
            title="Select Raw Markdown Transcript",
            initialdir=os.path.join(_script_dir, "transcripts"),
            filetypes=[("Markdown Files", "*.md"), ("All Files", "*.*")]
        )
        if path:
            self.entry_refine_md.delete(0, "end")
            self.entry_refine_md.insert(0, path)

    def _browse_into_entry(self, entry_widget):
        path = filedialog.askopenfilename(
            title="Select File",
            initialdir=_script_dir,
            filetypes=[("All Supported", "*.md;*.wav;*.mp3;*.m4a;*.flac"), ("Markdown", "*.md"), ("Audio", "*.wav;*.mp3"), ("All Files", "*.*")]
        )
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    def _on_run_standalone_refine(self):
        md_path = self.entry_refine_md.get().strip('"\' ')
        if not md_path or not os.path.exists(md_path):
            messagebox.showwarning("File Required", "Please select a valid raw markdown transcript file.")
            return

        api_url = self.entry_llm_url.get().strip()
        try:
            batch_size = int(self.combo_llm_batch.get())
        except Exception:
            batch_size = 25

        self.btn_run_refine.config(state="disabled", text="✨ Refining...")
        self.lbl_status.config(text="Running standalone AI refinement...")

        def _worker():
            try:
                res = get_backend().refine_existing_transcript(
                    md_path=md_path,
                    api_url=api_url,
                    batch_size=batch_size,
                    progress_cb=lambda ph, pct, msg: self.pipeline_queue.put({"type": "PROGRESS", "phase": ph, "percent": pct, "desc": msg}),
                    log_cb=lambda line: self.pipeline_queue.put({"type": "LOG", "text": line, "level": "INFO"})
                )
                self.after(0, lambda: self._on_refine_completed(res))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Refinement Error", str(e)))
            finally:
                self.after(0, lambda: self.btn_run_refine.config(state="normal", text="✨ Run Local LLM Refinement & Diff"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_refine_completed(self, res):
        if not res:
            return
        diff_res = res.get("diff_results", {})
        self._populate_diff_tree(diff_res)
        self.active_diff_path = res.get("diff_path")
        messagebox.showinfo("Refinement Complete", f"Refined transcript saved:\n{res.get('refined_path')}\n\nDiff Report generated:\n{res.get('diff_path')}")

    def _on_run_diff_tool(self):
        raw_p = self.entry_diff_raw.get().strip('"\' ')
        ref_p = self.entry_diff_refined.get().strip('"\' ')

        if not raw_p or not os.path.exists(raw_p) or not ref_p or not os.path.exists(ref_p):
            messagebox.showwarning("Files Required", "Please select both Raw and Refined transcript files.")
            return

        import re
        pat = re.compile(r'^\[\d{1,2}:\d{2}:\d{2} - \d{1,2}:\d{2}:\d{2}\]')
        def read_l(p):
            lines = []
            with open(p, 'r', encoding='utf-8') as f:
                for l in f:
                    s = l.rstrip()
                    if pat.search(s): lines.append(s)
            return lines

        raw_lines = read_l(raw_p)
        ref_lines = read_l(ref_p)
        base = os.path.splitext(raw_p)[0].replace("_session_log_raw", "").replace("_raw", "")
        out_diff = f"{base}_ai_diff.md"

        res = get_backend().generate_ai_diff(raw_lines, ref_lines, out_diff, session_name=os.path.basename(base))
        self.active_diff_path = out_diff
        self._populate_diff_tree(res)

    def _populate_diff_tree(self, diff_dict: dict):
        self.tree_diff.delete(*self.tree_diff.get_children())
        if not diff_dict:
            return

        tot = diff_dict.get("total_lines", 0)
        mod = diff_dict.get("num_modified", 0)
        pct = diff_dict.get("pct_modified", 0.0)

        self.lbl_diff_summary.config(
            text=f"Summary: {mod}/{tot} lines modified by AI ({pct:.1f}% altered). Detailed changes below:"
        )

        for item in diff_dict.get("modified_lines", []):
            self.tree_diff.insert(
                "", "end",
                values=(item["line_num"], f"{item['timestamp']} {item['speaker_info']}", item["before"], item["after"])
            )

    def _open_active_diff_file(self):
        if hasattr(self, "active_diff_path") and self.active_diff_path and os.path.exists(self.active_diff_path):
            open_file_externally(self.active_diff_path)
        else:
            messagebox.showinfo("No Diff Active", "No diff file has been generated or selected yet.")


    # =========================================================================
    # TAB 3 ACTIONS: VOICE LIBRARY & TRAINING
    # =========================================================================
    def _refresh_voice_library(self):
        self.tree_voices.delete(*self.tree_voices.get_children())
        v_dir = os.path.join(_script_dir, "voice_library")
        os.makedirs(v_dir, exist_ok=True)
        files = glob.glob(os.path.join(v_dir, "*.npy"))

        self.enrolled_voices = []
        for f in files:
            name = os.path.splitext(os.path.basename(f))[0]
            size_kb = f"{round(os.path.getsize(f) / 1024, 1)} KB"
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            self.enrolled_voices.append((name, size_kb, mtime, f))
            self.tree_voices.insert("", "end", values=(name, size_kb, mtime))

    def _filter_voice_library(self):
        query = self.entry_voice_search.get().strip().lower()
        self.tree_voices.delete(*self.tree_voices.get_children())
        for name, size_kb, mtime, _ in getattr(self, "enrolled_voices", []):
            if query in name.lower():
                self.tree_voices.insert("", "end", values=(name, size_kb, mtime))

    def _on_delete_voice_profile(self):
        sel = self.tree_voices.selection()
        if not sel:
            messagebox.showwarning("Select Voice", "Please select a voice profile from the table to delete.")
            return
        name = self.tree_voices.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete voice profile '{name}'?"):
            filepath = os.path.join(_script_dir, "voice_library", f"{name}.npy")
            if os.path.exists(filepath):
                os.remove(filepath)
            self._refresh_voice_library()

    def _on_rename_voice_profile(self):
        sel = self.tree_voices.selection()
        if not sel:
            messagebox.showwarning("Select Voice", "Please select a voice profile to rename.")
            return
        old_name = str(self.tree_voices.item(sel[0])["values"][0])

        dialog = tk.Toplevel(self)
        dialog.title("Rename Voice Profile")
        dialog.geometry("380x150")
        dialog.configure(bg=COLORS["bg_card"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text=f"Rename '{old_name}' to:", font=("Segoe UI", 9, "bold"), fg=COLORS["text_main"], bg=COLORS["bg_card"]).pack(anchor="w", padx=16, pady=(16, 4))
        entry = tk.Entry(dialog, font=("Segoe UI", 10), bg=COLORS["bg_card_inner"], fg=COLORS["text_main"], insertbackground=COLORS["text_main"], relief="flat")
        entry.insert(0, old_name)
        entry.pack(fill="x", padx=16, pady=4, ipady=3)

        def _do_rename():
            new_name = "".join([c for c in entry.get().strip() if c.isalpha() or c.isdigit()])
            if not new_name:
                messagebox.showwarning("Invalid Name", "Please enter an alphanumeric name.", parent=dialog)
                return
            old_f = os.path.join(_script_dir, "voice_library", f"{old_name}.npy")
            new_f = os.path.join(_script_dir, "voice_library", f"{new_name}.npy")
            if os.path.exists(old_f):
                os.rename(old_f, new_f)
            dialog.destroy()
            self._refresh_voice_library()

        btn_box = tk.Frame(dialog, bg=COLORS["bg_card"])
        btn_box.pack(fill="x", padx=16, pady=12)
        tk.Button(btn_box, text="Rename", font=("Segoe UI", 9, "bold"), bg=COLORS["primary"], fg="#ffffff", relief="flat", padx=12, pady=4, cursor="hand2", command=_do_rename).pack(side="right")
        tk.Button(btn_box, text="Cancel", font=("Segoe UI", 9), bg=COLORS["bg_hover"], fg=COLORS["text_muted"], relief="flat", padx=10, pady=4, cursor="hand2", command=dialog.destroy).pack(side="right", padx=6)

    def _on_run_voice_training(self):
        md_path = self.entry_train_md.get().strip('"\' ')
        audio_path = self.entry_train_audio.get().strip('"\' ')

        if not md_path or not os.path.exists(md_path) or not audio_path or not os.path.exists(audio_path):
            messagebox.showwarning("Files Required", "Please select both an edited Markdown file and matching Audio file.")
            return

        self.btn_run_training.config(state="disabled", text="🎯 Harvesting...")
        self.txt_train_log.delete("1.0", "end")
        self.txt_train_log.insert("end", f"Starting Voice Harvesting for {os.path.basename(md_path)}...\n")

        def _worker():
            try:
                def _log(line):
                    self.after(0, lambda: self.txt_train_log.insert("end", line + "\n"))
                    self.after(0, lambda: self.txt_train_log.see("end"))

                res = get_backend().train_voices(md_path, audio_path, log_cb=_log)
                self.after(0, lambda: self._on_training_complete(res))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Harvesting Error", str(e)))
            finally:
                self.after(0, lambda: self.btn_run_training.config(state="normal", text="🎯 Harvest & Refine Voice Profiles"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_training_complete(self, res):
        self._refresh_voice_library()
        if res.get("success"):
            harvested = res.get("harvested", [])
            spk_list = ", ".join([f"{h['speaker']} ({h['duration']}s)" for h in harvested])
            messagebox.showinfo("Voice Harvesting Complete", f"Successfully harvested and updated {len(harvested)} speaker profiles:\n\n{spk_list}")
        else:
            messagebox.showwarning("Harvesting Notice", res.get("error", "No speaker profiles were updated."))


    # =========================================================================
    # TAB 4 ACTIONS: DIAGNOSTICS & SYSTEM CHECKS
    # =========================================================================
    def _async_run_diagnostics(self):
        def _worker():
            # 1. GPU & CUDA
            try:
                import torch
                cuda_avail = torch.cuda.is_available()
                if cuda_avail:
                    dev_name = torch.cuda.get_device_name(0)
                    self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "gpu", "val": f"✅ {dev_name}", "color": COLORS["success"]})
                    self.lbl_gpu_badge.config(text=f"GPU: {dev_name}", fg=COLORS["success"])

                    # VRAM
                    total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "vram", "val": f"{total_vram:.1f} GB Total VRAM", "color": COLORS["text_main"]})
                else:
                    self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "gpu", "val": "❌ CUDA Unavailable (Running on CPU)", "color": COLORS["danger"]})
                    self.lbl_gpu_badge.config(text="GPU: CPU Fallback", fg=COLORS["danger"])
                    self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "vram", "val": "N/A", "color": COLORS["text_muted"]})

                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "torch", "val": f"v{torch.__version__}", "color": COLORS["text_main"]})
            except Exception as e:
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "gpu", "val": f"Error: {e}", "color": COLORS["danger"]})

            # 2. WhisperX
            try:
                import whisperx
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "whisperx", "val": f"✅ v{whisperx.__version__ if hasattr(whisperx, '__version__') else 'Installed'}", "color": COLORS["success"]})
            except Exception as e:
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "whisperx", "val": f"❌ Not Found ({e})", "color": COLORS["danger"]})

            # 3. FFmpeg
            try:
                subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "ffmpeg", "val": "✅ FFmpeg Installed in PATH", "color": COLORS["success"]})
            except Exception:
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "ffmpeg", "val": "⚠️ FFmpeg Not Found in PATH", "color": COLORS["warning"]})

            # 4. Hugging Face Token
            token = os.getenv("HF_TOKEN")
            if token and token.startswith("hf_"):
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "hf_token", "val": "✅ Configured (hf_...)", "color": COLORS["success"]})
            elif token:
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "hf_token", "val": "⚠️ Token set (non-standard format)", "color": COLORS["warning"]})
            else:
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "hf_token", "val": "❌ Missing in .env", "color": COLORS["danger"]})

            # 5. LM Studio Server Check
            self._test_lm_studio_connection(silent=True)

            # 6. Windows Sleep Preventer
            self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "sleep_prevent", "val": "✅ Enabled during transcription", "color": COLORS["success"]})

        threading.Thread(target=_worker, daemon=True).start()

    def _test_lm_studio_connection(self, silent: bool = False):
        api_url = self.entry_llm_url.get().strip() if hasattr(self, "entry_llm_url") else os.getenv("LLM_API_URL", "http://localhost:1234/v1")
        endpoint = f"{api_url.rstrip('/')}/models"

        def _test():
            try:
                req = urllib.request.Request(endpoint, method="GET")
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        models = data.get("data", [])
                        if models:
                            model_id = models[0].get("id", "Unknown Model")
                            val = f"✅ Online (Model: {model_id})"
                            self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "lm_studio", "val": val, "color": COLORS["success"]})
                            self.lbl_llm_badge.config(text=f"LM Studio: {model_id[:16]}...", fg=COLORS["success"])
                            if not silent:
                                messagebox.showinfo("LM Studio Online", f"Connected successfully to LM Studio!\n\nLoaded Model:\n{model_id}")
                        else:
                            val = "⚠️ Online, but NO MODEL IS LOADED"
                            self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "lm_studio", "val": val, "color": COLORS["warning"]})
                            self.lbl_llm_badge.config(text="LM Studio: No Model", fg=COLORS["warning"])
                            if not silent:
                                messagebox.showwarning("No Model Loaded", "LM Studio server is running, but no model is currently loaded in memory.")
                    else:
                        val = f"❌ Server returned status {resp.status}"
                        self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "lm_studio", "val": val, "color": COLORS["danger"]})
                        self.lbl_llm_badge.config(text="LM Studio: Error", fg=COLORS["danger"])
            except Exception as e:
                val = f"❌ Offline ({api_url})"
                self.pipeline_queue.put({"type": "DIAG_UPDATE", "key": "lm_studio", "val": val, "color": COLORS["danger"]})
                self.lbl_llm_badge.config(text="LM Studio: Offline", fg=COLORS["text_muted"])
                if not silent:
                    messagebox.showerror("Connection Failed", f"Could not reach LM Studio at {api_url}.\nPlease ensure Local Server is started in LM Studio.")

        threading.Thread(target=_test, daemon=True).start()

    def _toggle_token_visibility(self):
        if self.entry_hf_token.cget("show") == "*":
            self.entry_hf_token.config(show="")
            self.btn_show_token.config(text="🔒 Hide")
        else:
            self.entry_hf_token.config(show="*")
            self.btn_show_token.config(text="👁️ Show")

    def _save_hf_token(self):
        token = self.entry_hf_token.get().strip()
        env_path = os.path.join(_script_dir, ".env")
        lines = []
        token_written = False

        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("HF_TOKEN="):
                        lines.append(f'HF_TOKEN="{token}"\n')
                        token_written = True
                    else:
                        lines.append(line)

        if not token_written:
            lines.append(f'HF_TOKEN="{token}"\n')

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        os.environ["HF_TOKEN"] = token
        try:
            get_backend().HF_TOKEN = token
        except Exception:
            pass
        messagebox.showinfo("Saved", "Hugging Face token saved to .env and environment updated!")
        self._async_run_diagnostics()


    # =========================================================================
    # UTILITY HELPERS
    # =========================================================================
    def _refresh_audio_dropdown(self):
        audio_dir = os.path.join(_script_dir, "audio_files")
        os.makedirs(audio_dir, exist_ok=True)
        files = []
        for ext in ("*.wav", "*.mp3", "*.m4a", "*.flac", "*.ogg"):
            files.extend(glob.glob(os.path.join(audio_dir, ext)))

        basenames = [os.path.basename(f) for f in files]
        self.combo_audio_files["values"] = sorted(basenames)
        if basenames and not self.entry_audio_path.get():
            self.combo_audio_files.set(basenames[0])
            self.entry_audio_path.delete(0, "end")
            self.entry_audio_path.insert(0, os.path.join(audio_dir, basenames[0]))

    def _on_audio_combo_selected(self, event=None):
        sel = self.combo_audio_files.get()
        if sel:
            full_path = os.path.join(_script_dir, "audio_files", sel)
            self.entry_audio_path.delete(0, "end")
            self.entry_audio_path.insert(0, full_path)

    def _browse_audio_file(self):
        path = filedialog.askopenfilename(
            title="Select Audio Recording",
            initialdir=os.path.join(_script_dir, "audio_files"),
            filetypes=[("Audio Files", "*.wav;*.mp3;*.m4a;*.flac;*.ogg"), ("All Files", "*.*")]
        )
        if path:
            self.entry_audio_path.delete(0, "end")
            self.entry_audio_path.insert(0, path)


# ==========================================
# APPLICATION ENTRYPOINT
# ==========================================
def main():
    app = DnDTranscribeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
