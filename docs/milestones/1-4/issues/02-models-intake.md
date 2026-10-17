# 02: Milestone 2 — Models and intake

**What to build:** Recordings and optional caller metadata become coherent typed intake results with unique identities, valid temporary audio, and predictable rejection behavior.

**Blocked by:** None. Final integration and regression checks passed.

**Status:** verified — see completion.md for scope and documented differences

**Ownership:** Shared data models/state and intake agent plus their tests. Sole owner of shared model changes; collect requested schema changes from Milestones 3 and 4.

- [x] Map all named official models, enum values, fields, nested types, and PipelineState keys to implementation and tests.
- [x] Verify confidence and QA score constraints at and beyond their boundaries.
- [x] Exercise real audio utilities through intake for supported, empty, corrupt, unsupported, oversized, and overlong inputs.
- [x] Prove WAV duration rejection precedes size rejection when both limits are exceeded.
- [x] Verify temporary file bytes, format suffixes, distinct files and UUIDs, and coherent failed results.
- [x] Test SSN, credit-card, email, and phone metadata in caller ID and department, including clean and absent values and affected field names.
- [x] Run focused tests and all official self-checks; coordinate utility fixes with Milestone 1 rather than editing its owned files.

**Execution rules:** You are not alone in the codebase. Do not revert others’ changes. Verify existing behavior before editing, fix demonstrated gaps, reuse existing patterns/tests, and leave unrelated work intact. Do not commit, push, or publish issues. Report modified files, commands, outcomes, and unresolved requirements.

**Parent integration gate:** Exercise intake → transcription → injection detection/redaction → summary → QA through a test harness, prove no LLM invocation for injection-positive input and no known PII in outgoing requests, preserve IDs and stop dependent work on errors. Run the full regression suite and produce the official Milestones 1–4 acceptance matrix. Production LangGraph, reports, and final UI remain outside scope.

## Evidence — 2026-09-27

- Shared models tested for required field/enum contracts, numeric boundaries, nested CallReport JSON round trip, default list isolation and optional PipelineState keys. Explicit null timestamp now accepted as optional metadata.
- Canonical QA dimension Literal schema added after real provider returned invalid labels; schema and runtime validation are regression-tested.
- Real generated MP3, M4A and FLAC bytes pass detection, extraction and intake despite misleading filenames; compressed duration limits reject correctly. WAV bytes, UUIDs, temp suffixes, metadata PII, failure isolation and duration-before-size precedence pass.
- Independent review found truncated WAV payload acceptance. Shared audio extractor now rejects incomplete frame data; tests cover both direct extraction and intake with no temp artifact.
- Final combined suite: 303 passed in existing environment and 303 passed in clean installation.

**Final parent verification:** 303 tests passed in both existing and clean environments; five cross-milestone harness tests passed. See ../completion.md.
