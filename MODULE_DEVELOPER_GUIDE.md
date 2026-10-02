# Tool Bench — Module Developer & Handoff Guide

> **For Developers & AI Coding Agents:** Follow this specification when building a new program or adding an existing tool to Donovan's Tool Bench. Adhering to this contract ensures your program works out-of-the-box without modifying the Tool Bench wrapper.

---

## 1. The Core Architecture

Tool Bench is a **generic process supervisor and web dashboard**. It communicates with your program through standard OS processes:

```
[Tool Bench Web UI]
       ↕ (WebSocket)
[Tool Bench Server]
       ↕ (Subprocess IPC: stdin/stdout)
[Your Program (in its own Virtual Environment)]
```

* **No direct code imports**: Tool Bench runs your program in a separate OS process using your program's own Python executable and dependencies.
* **Loose Coupling**: If your program's internal functions or libraries change, Tool Bench will not break as long as the CLI entry point and JSON output contract remain intact.

---

## 2. The 3 Requirements for Any Program

To integrate with Tool Bench, a program needs exactly three things:

### Requirement 1: A `manifest.yaml` in Tool Bench
Create a folder inside Tool Bench at `modules/<module-id>/manifest.yaml`.
This tells Tool Bench how to render the UI form and what command to execute:

```yaml
id: my-tool                          # Unique kebab-case ID
name: My Cool Tool                   # UI Display Name
version: 1.0.0
description: What this tool does in 1-2 sentences.
icon: wrench                         # Lucide icon name (https://lucide.dev)
color: "#6366f1"                     # Brand hex color
author: Donovan Nichols
source_root: "E:\\git\\my-tool"      # Path to your repo on disk

resources:
  gpu: false                         # Set true if task uses CUDA (prevents concurrent GPU tasks)
  lm_studio: false                   # Set true if task requires LM Studio

tasks:
  - id: process-data                 # Task ID passed to your script
    name: Process Data
    description: Runs data processing pipeline.
    entry: main:run_process          # Entry file (main.py)
    long_running: true
    params:
      - id: input_file
        name: Input File
        type: file                   # string | text | number | boolean | path | file | select
        required: true
        accept: ".csv,.json,.txt"
      - id: output_dir
        name: Output Directory
        type: path
        required: false
        default: "C:\\tmp\\output"
      - id: fast_mode
        name: Fast Mode
        type: boolean
        default: true
```

#### Supported Parameter Types
| Type | UI Control | Value Passed to Script |
| --- | --- | --- |
| `string` | Single-line text input | `str` |
| `text` | Multi-line textarea | `str` |
| `number` | Number spinner | `int` or `float` |
| `boolean` | Toggle switch | `bool` (`true`/`false`) |
| `file` | In-browser host file picker | `str` (absolute path) |
| `path` | In-browser host folder picker | `str` (absolute path) |
| `select` | Dropdown menu (`options: [...]`) | Selected value |

---

### Requirement 2: Entrypoint Execution
Tool Bench executes your entry point file like this:
```bash
<your-venv>\Scripts\python.exe -u <source_root>\<entry_file>.py <task_id> [--params <json_string>]
```
1. `sys.argv[1]` is the `task_id` (e.g. `process-data`).
2. Parameters are supplied **either** via the `--params '<json>'` flag **or** as a single line-delimited JSON object written to `sys.stdin` at startup.

---

### Requirement 3: Output Contract (Line-Delimited JSON)
Your program reports status and progress by writing JSON lines to `sys.stdout` (with `flush=True`):

| Message Type | JSON Format | Effect in Tool Bench UI |
| --- | --- | --- |
| **Status** | `{"type": "status", "status": "running", "message": "Starting..."}` | Updates badge (`running`, `completed`, `failed`) |
| **Progress** | `{"type": "progress", "percent": 45, "message": "Processed 45/100"}` | Updates progress bar (0 to 100) |
| **Log** | `{"type": "log", "level": "info", "message": "Step 1 complete"}` | Appends to terminal log window (`info`, `warning`, `error`) |
| **Result** | `{"type": "result", "data": {"items": 42, "out": "C:\\..."}}` | Displays structured JSON result card when finished |
| **Raw Print** | `print("Hello world")` | *Tool Bench automatically wraps any plain text print as an info log line so standard prints never break.* |

---

## 3. Drop-in Boilerplate (`toolbench_adapter.py`)

Copy this lightweight adapter directly into your project's repository as `main.py` or `toolbench_adapter.py`. It handles all IPC, non-blocking Windows stdin, UTF-8 BOM, and task dispatching:

```python
#!/usr/bin/env python3
"""
Tool Bench Adapter Template
Drop this into your project to integrate with Donovan's Tool Bench.
"""
import sys
import os
import json
import time
from typing import Dict, Any

def emit(payload: Dict[str, Any]) -> None:
    """Emit structured event to Tool Bench web interface."""
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()

def log(message: str, level: str = "info") -> None:
    emit({"type": "log", "level": level, "message": str(message)})

def progress(percent: int, message: str = "") -> None:
    emit({"type": "progress", "percent": max(0, min(100, int(percent))), "message": str(message)})

def status(task_status: str, message: str = "") -> None:
    emit({"type": "status", "status": task_status, "message": str(message)})

def result(data: Dict[str, Any]) -> None:
    emit({"type": "result", "data": data})

def read_params() -> Dict[str, Any]:
    """Parse task parameters from --params CLI argument or piped stdin."""
    args = sys.argv[1:]
    if "--params" in args:
        idx = args.index("--params")
        if idx + 1 < len(args):
            try:
                return json.loads(args[idx + 1].strip().lstrip("\ufeff"))
            except Exception as e:
                log(f"Failed to parse --params: {e}", level="error")
                return {}

    if sys.stdin.isatty():
        return {}

    try:
        if sys.platform == "win32":
            import msvcrt, ctypes
            from ctypes import wintypes
            h = msvcrt.get_osfhandle(sys.stdin.fileno())
            avail = wintypes.DWORD()
            res = ctypes.windll.kernel32.PeekNamedPipe(h, None, 0, None, ctypes.byref(avail), None)
            if not res or avail.value == 0:
                time.sleep(0.05)
                ctypes.windll.kernel32.PeekNamedPipe(h, None, 0, None, ctypes.byref(avail), None)
            if not res or avail.value == 0:
                return {}
        line = sys.stdin.readline().strip().lstrip("\ufeff")
        return json.loads(line) if line else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Your Task Functions
# ---------------------------------------------------------------------------

def run_my_task(params: Dict[str, Any]) -> None:
    status("running", "Starting task...")
    log(f"Received parameters: {params}")

    progress(20, "Step 1: Initializing...")
    time.sleep(1)

    progress(60, "Step 2: Processing data...")
    time.sleep(1)

    progress(100, "Finished successfully!")
    status("completed", "Task complete")
    result({
        "status": "success",
        "output_file": params.get("output_dir", "C:\\tmp"),
    })


# ---------------------------------------------------------------------------
# CLI Dispatcher
# ---------------------------------------------------------------------------

TASK_MAP = {
    "process-data": run_my_task,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <task_id> [--params <json>]")
        sys.exit(1)

    task_id = sys.argv[1]
    handler = TASK_MAP.get(task_id)
    if not handler:
        emit({"type": "error", "message": f"Unknown task: {task_id}"})
        sys.exit(1)

    params = read_params()
    try:
        handler(params)
    except Exception as e:
        emit({"type": "error", "message": str(e)})
        status("failed", str(e))
        sys.exit(1)
```

---

## 4. Checklist for Future Projects

When handing off work to another AI coding session or building a new tool:

1. **Virtual Environment**:
   * Keep a standard `.venv` or `venv` inside the project root (`E:\git\<project>\venv`).
   * Tool Bench will automatically detect it and use that Python executable.
2. **Project Decoupling**:
   * Keep your project's business logic in your normal modules (e.g. `core/`, `scraper/`, `analyzer/`).
   * Use a single `main.py` entry point that imports your business logic and calls `progress()`, `log()`, `result()`.
3. **Register in Tool Bench**:
   * Create `modules/<your-tool>/manifest.yaml` inside `my_scripts_wrapper`.
   * Set `source_root: "E:\\git\\<your-tool>"`.
   * Trigger reload: `Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8400/api/admin/reload"`
4. **Done**: The tool card and parameter form immediately appear on the web UI at `http://127.0.0.1:8400`. No edits to Tool Bench's backend or frontend code are needed!
