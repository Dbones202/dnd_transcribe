"""
Launcher script for D&D Session Transcriber GUI.
Run this script or double-click it to start the desktop graphical user interface.
"""

import os
import sys
import subprocess

# Ensure venv/Scripts (with ffmpeg and dependencies) is in PATH
_root_dir = os.path.dirname(os.path.abspath(__file__))
_venv_scripts = os.path.join(_root_dir, "venv", "Scripts")
if os.path.exists(_venv_scripts) and _venv_scripts not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _venv_scripts + os.pathsep + os.environ.get("PATH", "")

# Ensure working directory is the project root
os.chdir(_root_dir)

# Import and run GUI
import dnd_gui

if __name__ == "__main__":
    dnd_gui.main()
