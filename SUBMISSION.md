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
