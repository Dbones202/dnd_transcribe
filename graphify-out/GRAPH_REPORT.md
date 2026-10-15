# Graph Report - DnD  (2026-10-14)

## Corpus Check
- 14 files · ~17,778 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 211 nodes · 325 edges · 15 communities (11 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 11 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `371a44a9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- dnd_transcribe.py
- DnDTranscribeApp
- main.py
- D&D Session Transcriber & Voice Harvester
- Changelog
- Tool Bench — Module Developer & Handoff Guide
- SpeakerIdentifyModal
- GitNexus — Code Intelligence
- GitNexus — Code Intelligence
- WindowsSleepPreventer
- extract_voices.py
- rules/graphify.md
- workflows/graphify.md

## God Nodes (most connected - your core abstractions)
1. `DnDTranscribeApp` - 42 edges
2. `run_dnd_session()` - 11 edges
3. `emit()` - 11 edges
4. `log()` - 10 edges
5. `transcribe_session()` - 10 edges
6. `refine_transcript()` - 10 edges
7. `train_voices()` - 10 edges
8. `D&D Session Transcriber & Voice Harvester` - 10 edges
9. `SpeakerIdentifyModal` - 9 edges
10. `progress()` - 9 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (15 total, 4 thin omitted)

### Community 0 - "dnd_transcribe.py"
Cohesion: 0.08
Nodes (37): custom_transcribe(), diff_two_transcripts(), generate_ai_diff(), log_metric(), model_key_to_display(), normalize_embedding(), parse_markdown_for_speakers(), parse_speaker_choice() (+29 more)

### Community 1 - "DnDTranscribeApp"
Cohesion: 0.07
Nodes (10): DnDTranscribeApp, get_backend(), main(), open_file_externally(), open_folder_externally(), D&D Session Transcriber & Voice Harvester - Graphical User Interface A rich,…, Opens a folder in Windows Explorer., Processes messages from background threads in a thread-safe manner. (+2 more)

### Community 2 - "main.py"
Cohesion: 0.18
Nodes (28): Any, emit(), log(), _log_cb(), main(), _prog_cb(), progress(), Full session transcription pipeline with speaker diarization. (+20 more)

### Community 3 - "D&D Session Transcriber & Voice Harvester"
Cohesion: 0.09
Nodes (23): 1. Edit the Transcript, 2. Run Training (Voice Harvesting), Commands & Options, ⚙️ Configuration & Prerequisites, D&D Session Transcriber & Voice Harvester, 🧰 Donovan's Tool Bench Integration (`main.py`), 🗂️ Folder Structure, 🔹 For Command Prompt (cmd) (+15 more)

### Community 4 - "Changelog"
Cohesion: 0.15
Nodes (12): [1.1.0] - 2026-08-16, [1.2.0] - 2026-08-20, [1.3.0] - 2026-10-02, [1.4.0] - 2026-10-14, Added, Added, Added, Added (+4 more)

### Community 6 - "Tool Bench — Module Developer & Handoff Guide"
Cohesion: 0.18
Nodes (9): 1. The Core Architecture, 2. The 3 Requirements for Any Program, 3. Drop-in Boilerplate (`toolbench_adapter.py`), 4. Checklist for Future Projects, Requirement 1: A `manifest.yaml` in Tool Bench, Requirement 2: Entrypoint Execution, Requirement 3: Output Contract (Line-Delimited JSON), Supported Parameter Types (+1 more)

### Community 8 - "GitNexus — Code Intelligence"
Cohesion: 0.33
Nodes (5): Always Do, CLI, GitNexus — Code Intelligence, Never Do, Resources

### Community 9 - "GitNexus — Code Intelligence"
Cohesion: 0.33
Nodes (5): Always Do, CLI, GitNexus — Code Intelligence, Never Do, Resources

### Community 11 - "extract_voices.py"
Cohesion: 0.48
Nodes (6): main(), normalize_embedding(), parse_markdown_for_speakers(), parse_speaker_choice(), Parses a markdown file and returns a dictionary of: { "SpeakerName": […, time_str_to_seconds()

## Knowledge Gaps
- **38 isolated node(s):** `graphify`, `Workflow: graphify`, `Always Do`, `Never Do`, `Resources` (+33 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `D&D Session Transcriber & Voice Harvester` connect `D&D Session Transcriber & Voice Harvester` to `Tool Bench — Module Developer & Handoff Guide`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `SpeakerIdentifyModal` connect `SpeakerIdentifyModal` to `DnDTranscribeApp`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `transcribe_session()` (e.g. with `main.py` and `_log_cb()`) actually correct?**
  _`transcribe_session()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `graphify`, `Workflow: graphify`, `Always Do` to the rest of the system?**
  _38 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `dnd_transcribe.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08139534883720931 - nodes in this community are weakly interconnected._
- **Should `DnDTranscribeApp` be split into smaller, more focused modules?**
  _Cohesion score 0.06636500754147813 - nodes in this community are weakly interconnected._
- **Should `D&D Session Transcriber & Voice Harvester` be split into smaller, more focused modules?**
  _Cohesion score 0.08695652173913043 - nodes in this community are weakly interconnected._