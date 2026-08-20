# Graph Report - DnD  (2026-08-20)

## Corpus Check
- 29 files · ~551,366 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 224 nodes · 283 edges · 34 communities (16 shown, 18 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `32673dac`
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
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]

## God Nodes (most connected - your core abstractions)
1. `DnDTranscribeApp` - 42 edges
2. `run_dnd_session()` - 12 edges
3. `D&D Session Transcriber & Voice Harvester` - 11 edges
4. `SpeakerIdentifyModal` - 9 edges
5. `refine_transcript_with_llm()` - 9 edges
6. `refine_existing_transcript()` - 9 edges
7. `report_progress()` - 8 edges
8. `TqdmList` - 7 edges
9. `Commands & Options` - 7 edges
10. `log_metric()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `diff_two_transcripts()` --calls--> `generate_ai_diff()`  [EXTRACTED]
  dnd_transcribe.py → dnd_transcribe.py  _Bridges community 2 → community 31_
- `refine_transcript_with_llm()` --calls--> `_process_chunk_adaptive()`  [EXTRACTED]
  dnd_transcribe.py → dnd_transcribe.py  _Bridges community 0 → community 2_

## Communities (34 total, 18 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.22
Nodes (9): _process_chunk_adaptive(), Cleans raw LLM output by stripping code fences, reasoning/thinking tags,     an, Cleans raw LLM output by stripping code fences, reasoning/thinking tags,     an, Sends a single batch request to LM Studio and returns cleaned lines if line coun, Sends a single batch request to LM Studio and returns cleaned lines if line coun, Recursively processes a dialogue chunk:     1. Tries the full batch (e.g. 25 li, Recursively processes a dialogue chunk:     1. Tries the full batch (e.g. 25 li, sanitize_llm_lines() (+1 more)

### Community 1 - "Community 1"
Cohesion: 0.1
Nodes (21): code:powershell (.\venv\Scripts\Activate.ps1), code:cmd (venv\Scripts\activate.bat), code:bash (source venv/Scripts/activate), code:powershell (python run_gui.py), code:powershell (python dnd_transcribe.py -a audio_files/session_1.wav), D&D Session Transcriber & Voice Harvester, 🗂️ Folder Structure, 🔹 For Command Prompt (cmd) (+13 more)

### Community 2 - "Community 2"
Cohesion: 0.1
Nodes (29): custom_transcribe(), generate_ai_diff(), log_metric(), parse_markdown_for_speakers(), Monkeypatched version of whisperx.asr.FasterWhisperPipeline.transcribe     to u, Optional post-processing pass using local LLM (e.g. Gemma / Llama via LM Studio, Compares raw and refined transcript lines, computes change metrics,     and wri, Compares raw and refined transcript lines, computes change metrics,     and wri (+21 more)

### Community 3 - "Community 3"
Cohesion: 0.15
Nodes (17): 1. Edit the Transcript, 2. Run Training (Voice Harvesting), code:powershell (python dnd_transcribe.py -a audio_files/session_1.wav --no-l), code:powershell (python dnd_transcribe.py --refine "transcripts/my_session_se), code:powershell (python dnd_transcribe.py --diff "transcripts/session_raw.md"), code:powershell (python dnd_transcribe.py --refine "transcripts/session_raw.m), code:env (HF_TOKEN="hf_your_token_here"), code:powershell (python verify_gpu.py) (+9 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (9): DnDTranscribeApp, get_backend(), main(), open_file_externally(), open_folder_externally(), D&D Session Transcriber & Voice Harvester - Graphical User Interface A rich, mod, Opens a folder in Windows Explorer., Processes messages from background threads in a thread-safe manner. (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.33
Nodes (5): Always Do, CLI, GitNexus — Code Intelligence, Never Do, Resources

### Community 6 - "Community 6"
Cohesion: 0.33
Nodes (5): Always Do, CLI, GitNexus — Code Intelligence, Never Do, Resources

### Community 7 - "Community 7"
Cohesion: 0.6
Nodes (4): main(), parse_markdown_for_speakers(), Parses a markdown file and returns a dictionary of:     { "SpeakerName": [ (sta, time_str_to_seconds()

### Community 8 - "Community 8"
Cohesion: 0.5
Nodes (3): AI Refinement Evaluation & Diff Report, Detailed Line-by-Line Changes, Summary Metrics

### Community 26 - "Community 26"
Cohesion: 0.29
Nodes (7): [1.1.0] - 2026-08-16, [1.2.0] - 2026-08-20, Added, Added, Changed, Changelog, Fixed

### Community 27 - "Community 27"
Cohesion: 0.5
Nodes (3): AI Refinement Evaluation & Diff Report, Detailed Line-by-Line Changes, Summary Metrics

### Community 31 - "Community 31"
Cohesion: 0.4
Nodes (5): diff_two_transcripts(), Utility to compare any two transcript markdown files and output an AI diff repor, Utility to compare any two transcript markdown files and output an AI diff repor, Utility to compare any two transcript markdown files and output an AI diff repor, Utility to compare any two transcript markdown files and output an AI diff repor

### Community 32 - "Community 32"
Cohesion: 0.4
Nodes (3): Context manager to prevent Windows from sleeping during execution., Context manager to prevent Windows from sleeping during execution., WindowsSleepPreventer

## Knowledge Gaps
- **77 isolated node(s):** `D&D Session Transcriber & Voice Harvester - Graphical User Interface A rich, mod`, `Opens a file using the default OS application.`, `Opens a folder in Windows Explorer.`, `Modal dialog for identifying an unknown speaker during the transcription pipelin`, `Processes messages from background threads in a thread-safe manner.` (+72 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DnDTranscribeApp` connect `Community 4` to `Community 30`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `D&D Session Transcriber & Voice Harvester` connect `Community 1` to `Community 3`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `SpeakerIdentifyModal` connect `Community 30` to `Community 4`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **What connects `D&D Session Transcriber & Voice Harvester - Graphical User Interface A rich, mod`, `Opens a file using the default OS application.`, `Opens a folder in Windows Explorer.` to the rest of the system?**
  _77 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._