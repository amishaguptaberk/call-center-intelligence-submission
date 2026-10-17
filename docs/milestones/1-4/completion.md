# Milestones 1–4 completion evidence

Date: 2026-09-27. No commit, push, or external tickets created.

## Outcome

Implementation and component acceptance for Milestones 1–4 are verified, with the explicit specification differences below. Work was split across three agents (M1, M3, M4) and the parent (M2/integration). The original worktree was clean.

- Baseline: 184 passed.
- Final existing environment: `.venv/bin/python -m pytest -q` — **303 passed in 5.19s**, zero failures/skips.
- Final isolated fresh installation: `/private/tmp/call-center-m1-clean/bin/python -m pytest -q` — **303 passed in 5.45s**, zero failures/skips.
- Isolated installation resolved 112 compatible packages; dependency check passed. Existing virtualenv was not changed.
- `git diff --check` passed.

## Acceptance matrix

| Milestone / requirement group | Evidence | Result |
| --- | --- | --- |
| M1 package structure, frozen dotenv config, all specified settings, documented environment | test_config; package checks; .env.example | Pass |
| M1 fresh installation | requirements-dev.txt installed into isolated Python 3.12 environment; dependency compatibility check | Pass |
| M1 all four magic-byte formats, first 12 bytes, wrong extensions, empty/unsupported/size boundaries | test_audio | Pass |
| M1 properties and corrupt input | test_audio; real generated MP3/M4A/FLAC intake; truncated-WAV regressions | Pass |
| M2 named models, enums, ranges, nested report serialization, partial PipelineState | test_state | Pass |
| M2 valid/invalid intake, unique IDs, temp bytes/suffix, size/duration precedence | test_intake | Pass |
| M2 metadata PII and clean/absent fields | test_intake | Pass |
| M3 Whisper lifecycle, device fallback, options, confidence formula and cleaner | test_transcription, test_diarization_pipeline | Pass for required heuristic path |
| M3 speaker patterns, gaps, question switching and short turns | test_diarization_pipeline; existing hybrid regressions | Pass with existing ambiguity extension retained |
| M3 persistent hash cache, repeated/different audio, backend isolation, current ID | test_transcription; actual Whisper smoke | Pass |
| M3 22 injection names and clean negatives | test_prompt_injection, including line-wrapped variants | Pass |
| M3 required PII formats, overlap/right-to-left replacements and clean text | test_pii_detection | Pass |
| M3 audit insert/retrieve, details, timestamps, rollback/close/recovery | test_audit with real temporary SQLite | Pass |
| M4 three provider adapters, selection, model/timeouts and bounded retries | test_llm_analysis_contracts, summary/QA tests | Pass |
| M4 summary formatting, typed output and call ID | summary tests; live OpenAI | Pass |
| M4 summary-to-QA, canonical dimensions, weighted recomputation and rubric | QA tests, outgoing prompt checks; live OpenAI | Pass |
| M4 timestamps, summary/QA sections, severity icons and empty cases | test_milestone4_formatters | Pass |
| M1–4 handoffs, PII-free outgoing requests, injection gate, failure short-circuit, cache/IDs | five tests in test_milestones_1_to_4 | Pass in acceptance harness |

## Material fixes

- Added pinned direct runtime/dev manifests and missing package initializers; resolved Gradio/Pydantic incompatibility in clean installation.
- Configuration loads model override and rejects zero attempts.
- Audio properties reject truncated WAV payloads; unsupported error matches the documented self-check.
- Optional input timestamps accept null; QA schema restricts dimensions to the five canonical names.
- Injection detection handles line-wrapped instructions. Transcript cleaning retains ordinary spoken music/silence words. Consecutive heuristic speaker switches use the preceding speaker correctly.
- Summary honors the model override; factory honors provider environment selection and avoids nested SDK retries.
- QA rejects duplicate/missing dimensions, recomputes score to two decimals, strengthens rubric examples, and renders the requested severity icons.

## Live evidence

- Offline tiny Whisper transcribed the first 12 seconds of local sample_01.mp3: nonempty output, 3.285 seconds fresh, 0.003 seconds cached. Repeated run was prevented from accessing the model and returned identical segments with the new call ID. Script: smoke-transcription.py. This proves execution/cache behavior, not general transcription accuracy.
- OpenAI on synthetic PII-free dialogue returned a valid summary and five QA dimensions, preserved IDs, and passed deterministic recomputation (3.25). Script: live_llm_smoke.py; sanitized evidence: live-llm-evidence.json.
- Gemini and Groq adapter construction was checked without network; live calls to those providers were not run.

## Specification differences and limits

- The original Gemini default has been retired. Uses Google's documented replacement gemini-3.6-flash; explicit model override remains available. Source verified by the M4 agent: https://ai.google.dev/gemini-api/docs/deprecations .
- Existing speaker attribution deliberately supports Ambiguous labels beyond the document's Agent/Customer examples. Retained to preserve the project's uncertainty handling. Exact two-label-only parity is not claimed.
- Existing optional acoustic/hybrid path retains its documented flat confidence values; the required Whisper confidence formula is verified on the heuristic path. No new acoustic accuracy benchmark or optional acoustic dependency fresh install was performed.
- The integration harness demonstrates component ordering/security handoffs. It is not a production LangGraph workflow; production ordering enforcement, reports, final UI and deployment remain Milestones 5–6.
- Core direct dependencies are pinned, not every transitive dependency. Clean install was verified on Python 3.12, not all supported Python versions.
- Gradio debug app construction and existing UI tests pass; visual UI behavior was not reviewed. Its pre-existing row-select argument warning remains outside this backend completion scope.

## Review

M1 agent independently reviewed root/M3/M4 changes. M3 agent independently reviewed M1 changes and found the truncated-WAV defect; it was fixed and regression-tested before final suites. No remaining introduced blocking defect was reported. This is cross-review, not an independent full product/security certification.
