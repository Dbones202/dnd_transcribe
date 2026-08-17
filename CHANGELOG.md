# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-16

### Added
- **Dual Transcript Output**: Automatically saves the unedited transcript immediately upon completing diarization to `transcripts/<session>_session_log_raw.md`.
- **Refined Transcript Output**: Writes LLM-refined transcripts to `transcripts/<session>_session_log_refined.md`.
- **AI Evaluation & Diff Report**: Generates `transcripts/<session>_ai_diff.md` containing line-by-line before/after diffs, modification percentages, duration, and batch integrity statistics.
- **Adaptive LLM Batch Splitting**: Sets default batch size to 25 lines with automatic binary fallback to 13 and 12 lines if a batch fails or mismatches, plus extended 360s timeout and output sanitization.
- **Cross-Talk Resilient Voice Matching**: Sub-segments long audio blocks into 2s sliding windows with consensus voting to eliminate multi-speaker contamination from voice embeddings.
- **Standalone AI Refinement CLI**: Added `--refine <raw_transcript.md>` flag to run or benchmark LLM refinement on existing markdown transcripts without re-running audio transcription.
- **Transcript Diff CLI**: Added `--diff <raw_transcript.md> <refined_transcript.md>` flag to generate an AI evaluation diff between any two transcripts.
- **Custom Batch Sizing & Endpoint**: Added `--batch-size` (default: 25 lines) and `--api-url` to tune LLM throughput and connect to custom endpoints.
- **Graphify Integration**: Added `.agents/rules/graphify.md`, `.agents/workflows/graphify.md`, and automated git commit/checkout hooks.
- **Version Tracking**: Added `VERSION` file and `CHANGELOG.md`.

### Changed
- Presets language to `en` in `whisperx.load_model` to eliminate language detection initialization overhead.
- Updated `README.md` with comprehensive documentation for all new output files and CLI flags.

### Fixed
- Addressed 3-hour bottleneck in AI review by decoupling raw transcription from LLM refinement and optimizing batch size.
- Resolved silent batch discard issue by implementing automatic adaptive sub-batch splitting and recording stats in the AI Diff report.
