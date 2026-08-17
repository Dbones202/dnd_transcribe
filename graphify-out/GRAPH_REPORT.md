# Graph Report - DnD  (2026-08-16)

## Corpus Check
- 23 files · ~452,820 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 125 nodes · 125 edges · 29 communities (15 shown, 14 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `570cae2f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]

## God Nodes (most connected - your core abstractions)
1. `run_dnd_session()` - 9 edges
2. `D&D Session Transcriber & Voice Harvester` - 9 edges
3. `TqdmList` - 6 edges
4. `Timer` - 6 edges
5. `Commands & Options` - 6 edges
6. `generate_ai_diff()` - 5 edges
7. `refine_transcript_with_llm()` - 5 edges
8. `GitNexus — Code Intelligence` - 5 edges
9. `GitNexus — Code Intelligence` - 5 edges
10. `⚙️ Configuration & Prerequisites` - 5 edges

## Surprising Connections (you probably didn't know these)
- `run_dnd_session()` --calls--> `TqdmList`  [EXTRACTED]
  dnd_transcribe.py → dnd_transcribe.py  _Bridges community 2 → community 28_
- `run_dnd_session()` --calls--> `generate_ai_diff()`  [EXTRACTED]
  dnd_transcribe.py → dnd_transcribe.py  _Bridges community 0 → community 28_

## Communities (29 total, 14 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.2
Nodes (13): diff_two_transcripts(), generate_ai_diff(), parse_markdown_for_speakers(), Optional post-processing pass using local LLM (e.g. Gemma / Llama via LM Studio, Compares raw and refined transcript lines, computes change metrics,     and wri, Optional post-processing pass using local LLM (e.g. Gemma / Llama via LM Studio, Standalone function to refine an existing raw markdown transcript file,     pro, Utility to compare any two transcript markdown files and output an AI diff repor (+5 more)

### Community 1 - "Community 1"
Cohesion: 0.2
Nodes (10): code:powershell (python dnd_transcribe.py -a audio_files/session_1.wav), D&D Session Transcriber & Voice Harvester, 🗂️ Folder Structure, How It Works, 🤖 Local LLM Transcript Refinement & Diff Evaluation, 🤖 Local LLM Transcript Refinement (LM Studio + Gemma 4), 📄 Output Files Generated, 🎙️ Recommended Audio Preparation (Audacity Workflow) (+2 more)

### Community 2 - "Community 2"
Cohesion: 0.25
Nodes (5): custom_transcribe(), A list wrapper that updates a tqdm progress bar when iterated.     Used to show, Monkeypatched version of whisperx.asr.FasterWhisperPipeline.transcribe     to u, TqdmList, list

### Community 3 - "Community 3"
Cohesion: 0.25
Nodes (8): 1. Edit the Transcript, 2. Run Training (Voice Harvesting), code:markdown (<!-- BEFORE -->), code:powershell (python dnd_transcribe.py --train --md "transcripts/your_edit), code:powershell (python extract_voices.py "transcripts/your_edited_transcript), Option A: Via Main Script (Recommended), Option B: Via Extraction Script (Alternative), 🎓 Step 3: How to Train the Software (Refining Voice Profiles)

### Community 4 - "Community 4"
Cohesion: 0.29
Nodes (7): code:powershell (.\venv\Scripts\Activate.ps1), code:cmd (venv\Scripts\activate.bat), code:bash (source venv/Scripts/activate), 🔹 For Command Prompt (cmd), 🔹 For Git Bash / WSL, 🔹 For PowerShell (Recommended on Windows), 🛠️ Step 1: Open the Virtual Environment (venv)

### Community 5 - "Community 5"
Cohesion: 0.33
Nodes (5): Always Do, CLI, GitNexus — Code Intelligence, Never Do, Resources

### Community 6 - "Community 6"
Cohesion: 0.33
Nodes (5): Always Do, CLI, GitNexus — Code Intelligence, Never Do, Resources

### Community 7 - "Community 7"
Cohesion: 0.6
Nodes (4): main(), parse_markdown_for_speakers(), Parses a markdown file and returns a dictionary of:     { "SpeakerName": [ (sta, time_str_to_seconds()

### Community 25 - "Community 25"
Cohesion: 0.25
Nodes (9): code:powershell (python dnd_transcribe.py --refine "transcripts/my_session_se), code:powershell (python dnd_transcribe.py --diff "transcripts/session_raw.md"), code:powershell (python dnd_transcribe.py --refine "transcripts/session_raw.m), code:env (HF_TOKEN="hf_your_token_here"), code:powershell (python verify_gpu.py), code:powershell (python dnd_transcribe.py -a audio_files/session_1.wav), code:powershell (python dnd_transcribe.py -a audio_files/session_1.wav --no-l), Commands & Options (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.33
Nodes (5): [1.1.0] - 2026-08-16, Added, Changed, Changelog, Fixed

### Community 27 - "Community 27"
Cohesion: 0.5
Nodes (3): AI Refinement Evaluation & Diff Report, Detailed Line-by-Line Changes, Summary Metrics

### Community 28 - "Community 28"
Cohesion: 0.73
Nodes (3): log_metric(), run_dnd_session(), Timer

## Knowledge Gaps
- **52 isolated node(s):** `Context manager to prevent Windows from sleeping during execution.`, `A list wrapper that updates a tqdm progress bar when iterated.     Used to show`, `Monkeypatched version of whisperx.asr.FasterWhisperPipeline.transcribe     to u`, `Compares raw and refined transcript lines, computes change metrics,     and wri`, `Optional post-processing pass using local LLM (e.g. Gemma / Llama via LM Studio` (+47 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `D&D Session Transcriber & Voice Harvester` connect `Community 1` to `Community 25`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `🎓 Step 3: How to Train the Software (Refining Voice Profiles)` connect `Community 3` to `Community 1`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `🛠️ Step 1: Open the Virtual Environment (venv)` connect `Community 4` to `Community 1`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **What connects `Context manager to prevent Windows from sleeping during execution.`, `A list wrapper that updates a tqdm progress bar when iterated.     Used to show`, `Monkeypatched version of whisperx.asr.FasterWhisperPipeline.transcribe     to u` to the rest of the system?**
  _52 weakly-connected nodes found - possible documentation gaps or missing edges._