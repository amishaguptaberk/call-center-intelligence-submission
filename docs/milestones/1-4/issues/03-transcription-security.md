# 03: Milestone 3 — Transcription, security, and audit

**What to build:** Accepted recordings produce reusable speaker-labeled transcripts; malicious instructions and sensitive data are detected/redacted and audit events persist.

**Blocked by:** None. Final integration and regression checks passed.

**Status:** verified — see completion.md for scope and documented differences

**Ownership:** Transcription and existing acoustic support, security components, cache/audit database infrastructure, and their tests. Preserve acoustic/hybrid extensions; coordinate model/config changes with their owners.

- [x] Verify Whisper model reuse, device selection/fallback, all specified transcription options, cleaning rules, exact confidence formula, and speaker heuristic priority/boundaries.
- [x] Prove SHA-256 chunked hashing, persistent miss/save/hit behavior, restored segments, current-call identity, no second inference for identical audio, and backend isolation.
- [x] Individually test every one of the 22 named injection patterns plus clean negatives.
- [x] Test required phone/email/SSN/card format variants, repeated/mixed/overlapping PII, right-to-left replacements, labels, and clean-text behavior.
- [x] Verify audit event persistence with all required fields and optional details using a real temporary database; test rollback and session cleanup.
- [x] Exercise relevant transcription/cache failures and preserve current public contracts.
- [x] Run a short real-audio fresh transcription and cache-hit check; report dependency/network blocks honestly.
- [x] Run focused unit/security/database checks and every official Milestone 3 self-check.

**Execution rules:** You are not alone in the codebase. Do not revert others’ changes. Verify existing behavior before editing, fix demonstrated gaps, reuse existing patterns/tests, and leave unrelated work intact. Do not commit, push, or publish issues. Report modified files, commands, outcomes, and unresolved requirements.

**Parent integration gate:** Exercise intake → transcription → injection detection/redaction → summary → QA through a test harness, prove no LLM invocation for injection-positive input and no known PII in outgoing requests, preserve IDs and stop dependent work on errors. Run the full regression suite and produce the official Milestones 1–4 acceptance matrix. Production LangGraph, reports, and final UI remain outside scope.


## Completion evidence — 2026-09-27

- Baseline: 111 focused tests passed before edits. Existing injection names/PII format tests already covered the official minimums; no replacement implementation was needed.
- Reproduced 18 failures in new regressions: newline-wrapped injection patterns, deletion of ordinary music/silence words, and consecutive-question speaker switching. Fixed the shared functions, including acoustic word cleaning, and retained acoustic/hybrid extensions.
- Final focused command: `.venv/bin/python -m pytest tests/security tests/unit/test_transcription.py tests/unit/test_audit.py tests/unit/test_diarization_pipeline.py tests/unit/test_hybrid_diarization.py -q` — **157 passed in 3.41s**.
- Added coverage: all 22 names under uppercase/line wrapping; overlapping email/phone/SSN matches and repeated/mixed PII; Whisper singleton/size/device/no-torch behavior; exact options and confidence math; 8192-byte hashing; distinct audio and backend cache isolation; restart persistence and duplicate insertion; invalid/missing input and failed inference; audit fields/timestamps/details, rollback on body/commit failures, close, and recovery.
- Bounded real smoke: `PYTHONPATH=. .venv/bin/python docs/milestones/1-4/smoke-transcription.py` — actual offline tiny Whisper on first 12 seconds of existing sample_01.mp3, heuristic backend, **1 nonempty segment**, **3.285 seconds fresh**, **0.003 seconds cached**. Second invocation was forbidden from accessing Whisper and passed; all segments matched and the new call ID replaced the original. Temporary intake audio and database were cleaned up; no raw transcript was printed.
- `git diff --check` passed.
- No unresolved owned Milestone 3 requirement. Production workflow enforcement and full Milestones 1–4 regression remain the parent's integration gate. The smoke proves real ASR/cache execution; acoustic quality beyond preserved regression coverage was not re-benchmarked.

**Final parent verification:** 303 tests passed in both existing and clean environments; five cross-milestone harness tests passed. See ../completion.md.
