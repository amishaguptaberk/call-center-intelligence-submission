# Rubric Review

Assessment uses the supplied capstone grading rubric and both requirement
documents. This is an evidence report, not an awarded grade or a guarantee of
100 points. The rubric contains seven criteria weighted to 100 percent.

| Criterion | Weight | Verified implementation and evidence | Remaining limit |
| --- | --- | --- | --- |
| Pipeline architecture | 20% | Typed LangGraph state; named stages; invalid-input, injection, low-confidence, and critical-review routes; one compiled workflow; retained prior state on failure; exponential model retries | Production-load behavior not measured |
| Audio and transcription | 15% | Real Faster-Whisper runs on Samples 01/03; greedy decoding, VAD, word timestamps, disabled previous-text conditioning; singleton startup model; heuristic speaker labels; cache-hit replay; confidence flags | GPU and acoustic backend not exercised; heuristic labels are imperfect |
| Security | 15% | Four PII categories with at least five tested variants each; split-number redaction preserves turns; 22+ injection patterns; model-input redaction checks; immutable audit triggers; configurable export cleanup; intake-file deletion | Regex cannot anonymize every spoken/ASR variant; raw local cache has no expiry |
| Model integration | 20% | Structured summaries and five-dimension QA; summary context; weighted score recomputed in Python; three provider adapters; retry tests; temperature-zero default; real GPT-4o structured output | Gemini/Groq live calls not run because their keys are absent; model judgments are not guaranteed facts |
| Reports and persistence | 10% | Three indexed SQLite tables; commit/rollback coverage; history across engine restart and schema upgrade; browser PDF/JSON downloads; matching call ID and weighted score; all pages of a live PDF inspected | Hosted SQLite durability depends on external persistent storage |
| Testing | 10% | 358 passing tests across unit/integration/security; no provider credentials required; real browser regression reproduced and fixed; microphone tuple tested; desktop/390px checks | Physical microphone permission/recording not exercised |
| Code quality and deployment | 10% | Five layers; thin entrypoint; JSON stage/retry logging; documented environment; Makefile; Python 3.11 target; lint/format hooks; non-root Docker/Spaces package | Container build/run and hosted build remain unverified because Docker is unresponsive and Spaces write login is absent |

## Live Walkthrough

- Two distinct supplied recordings completed actual speech recognition,
  summary, QA, persistence, and report generation.
- Re-upload of Sample 01 served a transcription cache hit. The initial replay
  completed in 5.02 seconds; later temperature-zero model runs took about 10 seconds.
- Browser Sample 01 analysis with blank metadata completed and exposed all outputs.
- Both files downloaded through the browser; their call ID and 3.45/5 QA score matched.
- History reopened the saved call and regenerated reports without model calls.
- Observability displayed seven completed calls, 14 audit entries, 100% pipeline
  completion, and a 3.18 average score, matching the saved test history.
- The phone viewport measured 390px with a 390px document width after the
  table-layout fix, with no page-level horizontal overflow.

## Corrections Made

Blank optional Gradio values are normalized before building input metadata.
Exceptions are represented by stage/type instead of leaking provider text.
Failed outcomes count toward total calls and success rate; supervisor-review
scores are excluded from the completed-call average. Low-confidence input is
held before model analysis. PII crossing numeric segment boundaries is removed
without merging unrelated speakers or timestamps. SQLite history survives the
schema upgrade. Audit mutation and temporary-file accumulation are prevented.

## Submission Access

The capstone archive includes the full app, tests, configuration, and walkthrough.
The README links to the extended personal Echo repository and includes its demo
video. That repository is private, so reviewers need access for the source;
the bundled synthetic-data video is independently viewable.
