# 01: Milestone 1 — Foundation and audio

**What to build:** Fresh installation and configuration support reliable detection, validation, and property extraction for supported call recordings.

**Blocked by:** None. Final integration and regression checks passed.

**Status:** verified — see completion.md for scope and documented differences

**Ownership:** Configuration/audio utilities, package structure, dependency manifests, environment example, and their tests. Coordinate configuration changes required by Milestone 4 with its owner.

- [x] Inspect project guidance, preserve existing work, record baseline test results, and map every official Milestone 1 requirement to evidence.
- [x] Verify the required package structure, dotenv loading, frozen configuration, every specified environment setting, and documented acceptable values.
- [x] Fix demonstrated dependency-manifest gaps and verify installation in a clean environment.
- [x] Test first-12-byte detection for WAV, both MP3 headers, FLAC, and M4A independent of filename extensions.
- [x] Test empty, unsupported, corrupt, and oversized audio, exact size boundaries, and specified constants and validation result contracts.
- [x] Verify WAV and mutagen property extraction and typed errors for corrupt inputs.
- [x] Run focused tests and record exact results; coordinate real audio-to-intake checks with Milestone 2.

**Execution rules:** You are not alone in the codebase. Do not revert others’ changes. Verify existing behavior before editing, fix demonstrated gaps, reuse existing patterns/tests, and leave unrelated work intact. Do not commit, push, or publish issues. Report modified files, commands, outcomes, and unresolved requirements.

**Parent integration gate:** Exercise intake → transcription → injection detection/redaction → summary → QA through a test harness, prove no LLM invocation for injection-positive input and no known PII in outgoing requests, preserve IDs and stop dependent work on errors. Run the full regression suite and produce the official Milestones 1–4 acceptance matrix. Production LangGraph, reports, and final UI remain outside scope.


## Evidence — 2026-09-27

- Baseline reported by parent: 184 existing tests passed.
- Added missing package initializers, pinned application/dev manifests, documented fresh install, and removed an unused audio import.
- Configuration now loads optional LLM_MODEL and rejects zero maximum attempts (zero previously prevented any LLM request). All official environment fields, frozen behavior, dotenv loading and secret-safe repr are tested.
- `python -m pytest tests/unit/test_audio.py tests/unit/test_config.py -q`: 54 passed in the clean environment. Covers every official M1 self-check, first-12-byte detection, both MP3 headers, exact 50 MiB boundary, misleading filenames, WAV properties, mutagen parser contracts, and typed failures for corrupt inputs.
- Created an isolated Python 3.12.7 environment at `/private/tmp/call-center-m1-clean`; installed `requirements-dev.txt` successfully (112 packages). `uv pip check` confirmed all installed packages compatible.
- Clean installation exposed a real Gradio 5.50/Pydantic conflict with the Google provider adapter. Pinned compatible Gradio 6.28.0; 65 focused M1/UI tests passed before the final package/env test was added. Debug app construction succeeded (22 components), without starting a server.
- UI construction emits an existing row-select argument-count warning; visual UI behavior and optional acoustic dependency installation are outside M1 sign-off. Optional acoustic dependencies remain separate.
- Actual compressed-format fixtures through intake are owned by parent (M2); mocked parser-return tests here alone do not establish real codec decoding.
- Core direct dependencies are pinned; transitive dependencies are resolver-selected, not a full lockfile. No new dependency framework was added.

**Final parent verification:** 303 tests passed in both existing and clean environments; five cross-milestone harness tests passed. See ../completion.md.
