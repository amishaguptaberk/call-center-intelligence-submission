# Submission Notes

See [Requirement Coverage](docs/milestones/requirements-matrix.md) for all 48
milestone self-checks, final guide requirements, compatibility decisions, and
the distinction between current tests, historical live evidence, and unverified
deployment/provider behavior. The declared Python target is 3.11; later minors
are not certified by this submission's current environment.

| Milestone | Implementation | Regression coverage |
| --- | --- | --- |
| 1. Foundation/audio | `src/utils/config.py`, `src/utils/audio.py` | Config and audio |
| 2. Models/intake | `src/graph/state.py`, `src/agents/intake.py` | State and intake |
| 3. Transcription/security | `src/agents/transcription.py`, `src/security/` | Transcription, injection, PII |
| 4. Analysis | Summarization and QA agents | Structured output, retries, evidence |
| 5. Persistence/pipeline | Database, graph, report generator | Workflows, persistence, reports |
| 6. Gradio/polish | UI, pipeline service, observability | UI, exports, packaging |

## Scope

This standalone capstone is based on the SQLite/Gradio implementation
(source revision e18542d) with submission packaging and UI refinements. It
excludes the later Echo product dashboard and Postgres migration. Audio uses
filepath mode to preserve original-format validation; the service also accepts
numpy tuples. Gradio 6 theme/CSS are supplied at launch. Summary and QA reflow
from two columns on wide screens to one on narrow screens.

The final requirements guide mentions a third history tab in its overview,
while the milestone guide and a later UI section specify two tabs. This
submission includes all three: Analyze Call, All MP3 History, and Observability.

The SQLite tables are `call_records`, `audit_log`, and `transcription_cache`.
Startup upgrades the earlier `call_analyses` table in place, preserving records.
Audit entries are protected against updates and deletes by database triggers.

The [extended Echo version](https://github.com/amishaguptaberk/call-center-intelligence)
and an included synthetic-data demo are linked from the README. The extended
repository is private; the video can be viewed from this submission archive.

## Limits

Speaker labels may be wrong. QA scores are model assessments, not independently
verified policy judgments. Redaction is pattern-based. Inference needs provider
credentials and downloaded model weights. GPU behavior is unverified.

Historical milestone evidence under `docs/milestones/` describes earlier work;
it does not establish checks passed for this export. See `VERIFICATION.md`.

## Handoff Status: 2026-10-16

Requirement reconciliation was accepted at `e8e5d2c`, publication sanitization
at `8825f5d`, and clean-install documentation at `28669fb`. The fresh source
actually exercised was `8825f5d`: 362 tests, lint, formatting, dependency
consistency, and HTTP startup with all three tabs passed. HEAD observed during
this documentation pass is `2882df9`, adding container acceptance checks;
hosted execution for the baseline and later code revision is recorded below.

Two live browser analyses verified redaction for the detected sample pattern,
matching PDF/JSON exports, a weighted 3.45/5 score, transcription caching,
stored history, and metrics. Subsequent synthetic browser checks pass mobile
geometry/History stacking, desktop columns, invalid-decode feedback and recovery
after reload, exports/cache/history/metrics, and newest-20 audit rows. A real
`score_qa` fixture with scores 4/2/5/3/4 overrides model overall 5 to weighted
3.70 in JSON/PDF/UI. These fixture results are separate from live analyses.
The source suite now passes 365 tests, including container integration;
independent UI repair review passed with 365 tests, lint, formatting, and fresh
browser software checks independently rerun. These local checks are separate
from the passing Linux CI below. Physical capture returned `NotSupportedError`; manual verification
remains pending. See [reviewer walkthrough](docs/verification/reviewer-walkthrough.md).

The public clean-history submission repository is
[call-center-intelligence-submission](https://github.com/amishaguptaberk/call-center-intelligence-submission).
Initial revision `2ea14c02de44c884437bfa6cc1d0c737f0402c16` maps to private
source `2882df9`; its new root has 139 files and original history was not uploaded.
Baseline local verification passed 363 tests, lint, and formatting, with no
blocked token patterns or forbidden runtime paths found by the bounded scan.
[Hosted run 38990340548](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38990340548)
completed successfully for both tests and container jobs.

Extended container source `a732aa1` passed independent source review and eight
targeted tests. Its synthetic-audio real-pipeline smoke, with mocked ASR/model
boundaries, reports, and History exports after replacement passed in the hosted
code run below; overall was 3 and persistence verification was true.

Hosted passing results above apply to the baseline. The public revision is now
`1ce33f620cec42f0a97ff4c0b2b3e689a28fbc24`;
[run 38991300177](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38991300177)
completed successfully with 365 Linux tests and the extended container job.
This later documentation revision will rerun CI; its outcome is not claimed.
The preliminary 143-file ZIP was byte-verified and extracted source passed
365 tests using the existing environment, not a fresh installation.
Anonymous probes returned repository API `private: false`, raw README GET 200,
and demo HEAD 200; browser playback is not proven. Final release revision and
checksum remain in the external handoff.
Original local history contains raw excerpts and remains private.
Tickets 06/07 are not complete.

This status records evidence available at the source snapshot. Consult
[Actions](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions)
for revision-specific checks and the final handoff/
[Releases](https://github.com/amishaguptaberk/call-center-intelligence-submission/releases)
for subsequent public-access confirmation, release revision, archive checksum,
and extraction results. Archive metadata is not embedded in its own source
snapshot. These links do not assert release completion.
