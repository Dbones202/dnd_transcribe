# Graph Report - DnD  (2026-10-02)

## Corpus Check
- 35 files · ~697,620 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 283 nodes · 377 edges · 37 communities (16 shown, 21 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f550ffe4`
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
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]

## God Nodes (most connected - your core abstractions)
1. `DnDTranscribeApp` - 42 edges
2. `run_dnd_session()` - 12 edges
3. `D&D Session Transcriber & Voice Harvester` - 12 edges
4. `emit()` - 10 edges
5. `log()` - 10 edges
6. `SpeakerIdentifyModal` - 9 edges
7. `refine_transcript_with_llm()` - 9 edges
8. `refine_existing_transcript()` - 9 edges
9. `progress()` - 9 edges
10. `status()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `list`  [INFERRED]
  main.py →   _Bridges community 2 → community 0_

## Communities (37 total, 21 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.16
Nodes (27): emit(), log(), _log_cb(), main(), _prog_cb(), progress(), Full session transcription pipeline with speaker diarization., Run LLM refinement on an existing raw transcript. (+19 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (42): 1. Edit the Transcript, 2. Run Training (Voice Harvesting), code:powershell (.\venv\Scripts\Activate.ps1), code:powershell (python dnd_transcribe.py -a audio_files/session_1.wav), code:powershell (python dnd_transcribe.py -a audio_files/session_1.wav --no-l), code:powershell (python dnd_transcribe.py --refine "transcripts/my_session_se), code:powershell (python dnd_transcribe.py --diff "transcripts/session_raw.md"), code:powershell (python dnd_transcribe.py --refine "transcripts/session_raw.m) (+34 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (43): custom_transcribe(), diff_two_transcripts(), generate_ai_diff(), log_metric(), parse_markdown_for_speakers(), _process_chunk_adaptive(), Utility to compare any two transcript markdown files and output an AI diff repor, Monkeypatched version of whisperx.asr.FasterWhisperPipeline.transcribe     to u (+35 more)

### Community 3 - "Community 3"
Cohesion: 0.14
Nodes (13): 1. The Core Architecture, 2. The 3 Requirements for Any Program, 3. Drop-in Boilerplate (`toolbench_adapter.py`), 4. Checklist for Future Projects, code:block1 ([Tool Bench Web UI]), code:yaml (id: my-tool                          # Unique kebab-case ID), code:bash (<your-venv>\Scripts\python.exe -u <source_root>\<entry_file>), code:python (#!/usr/bin/env python3) (+5 more)

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
Cohesion: 0.22
Nodes (10): [1.1.0] - 2026-08-16, [1.2.0] - 2026-08-20, [1.3.0] - 2026-10-02, Added, Added, Added, Added, Changed (+2 more)

### Community 27 - "Community 27"
Cohesion: 0.5
Nodes (3): AI Refinement Evaluation & Diff Report, Detailed Line-by-Line Changes, Summary Metrics

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (3): AI Refinement Evaluation & Diff Report, Detailed Line-by-Line Changes, Summary Metrics

### Community 32 - "Community 32"
Cohesion: 0.4
Nodes (3): Context manager to prevent Windows from sleeping during execution., Context manager to prevent Windows from sleeping during execution., WindowsSleepPreventer

## Knowledge Gaps
- **105 isolated node(s):** `D&D Session Transcriber & Voice Harvester - Graphical User Interface A rich, mod`, `Opens a file using the default OS application.`, `Opens a folder in Windows Explorer.`, `Modal dialog for identifying an unknown speaker during the transcription pipelin`, `Processes messages from background threads in a thread-safe manner.` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `Community 0` to `Community 2`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **What connects `D&D Session Transcriber & Voice Harvester - Graphical User Interface A rich, mod`, `Opens a file using the default OS application.`, `Opens a folder in Windows Explorer.` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._