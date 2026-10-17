# Verification Report

## Current Evidence: 2026-10-16

Final handoff remains **pending**. Requirements were accepted at `e8e5d2c`,
privacy sanitization at `8825f5d`, and clean-install documentation at
`28669fb`. Latest observed container source is `a732aa1`,
extending container acceptance checks. Passing evidence is tied to tested source,
not automatically to HEAD or a future publication revision.

This report records evidence available for the source snapshot. Latest
revision-specific hosted outcomes are in
[Actions](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions).
The final handoff and
[Releases](https://github.com/amishaguptaberk/call-center-intelligence-submission/releases)
carry subsequent public-visibility/access confirmation, release revision,
archive checksum, and extraction verification. Links alone do not prove
completion; archive metadata is external to the source snapshot it identifies.

## Fresh Installation

The [clean-install report](docs/verification/clean-install.md) records fresh
exported source `8825f5dc23a2a9edf7b089292f8f7d5227813177` on macOS ARM64,
Python 3.11.15 and externally supplied FFmpeg 7.1:

- Fresh requirements-dev installation: passed.
- Full suite: **362 passed, 5 warnings**, no skipped or weakened tests.
- Ruff lint and formatting: passed, 92 files formatted.
- Dependency consistency (`python -m pip check`): passed.
- Actual HTTP `/config`: 200, with Analyze call, All MP3 History, and
  Observability; provider credentials absent and speech preload disabled.

Earlier failures remain in that report: an older install ran out of disk;
a subsequent suite had 361 passed and 1 failed because the harness disabled
dotenv loading needed by a test fixture. After the authorized pytest environment
correction, all 362 passed without source changes. HTTP startup alone does not
verify model download or inference.

## Live Reviewer Walkthrough

The [walkthrough](docs/verification/reviewer-walkthrough.md) records exactly
two actual browser analyses of Sample 01 on accepted source `8825f5d`:

- Real transcription and provider analysis completed.
- The detected sample pattern was redacted from UI and downloaded reports.
- Browser PDF/JSON exports had matching call IDs; PDFs contained three pages.
- Independent weighted calculations matched the rendered **3.45/5** score.
- Repeated audio hit the transcription cache; downstream analysis still ran.
- History reopened stored results and regenerated exports without inference,
  including after restart.
- Observability matched the isolated database: two completed calls, one cache
  row, four audit events, 100% success, average 3.45.

This does not establish complete PII detection or scoring accuracy. Separately,
11 reviewer-journey and 29 intake fixture tests passed; mocked failure, routing,
and microphone cases do not establish live hardware behavior.

## Hosted Baseline Evidence

Historical supplied evidence records the initially private staging repository
[call-center-intelligence-submission](https://github.com/amishaguptaberk/call-center-intelligence-submission)
at initial revision `2ea14c02de44c884437bfa6cc1d0c737f0402c16`, mapped to
private source `2882df9`. Its new Git root contains 139 files; original private
history was not uploaded. Before push, baseline local verification passed
363 tests, lint, and formatting; the bounded publication scan found no blocked
token patterns or forbidden runtime paths.

[Run 38990340548](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38990340548)
completed successfully: both tests and container jobs passed. This is hosted
baseline evidence supplied for this documentation update, not a new execution
by this documentation pass. It does not certify subsequent source changes.

## Supplied Source And Browser Update

The updated source suite passed **365 tests**, including new container
integration coverage. This is a supplied local source result, not a fresh Linux
installation or final hosted CI result. Supplied independent UI repair review
passed, with all 365 tests, lint, formatting, and fresh browser software checks
independently rerun. This verifies source/software behavior, not hardware capture.

The synthetic browser harness now passes 390px geometry with zero overflow,
stacked History panels, and two-column desktop layout. Invalid decode produces
a visible error without a traceback; recovery passed after reload. Redacted
exports, transcription cache, stored history, metrics, and the newest 20 audit
rows passed fixture checks. Earlier mobile and audit assertion failures remain
historical evidence in the walkthrough.

The score fixture runs the real `score_qa` implementation with unequal scores
4/2/5/3/4. The model's incorrect overall 5 is overridden by the weighted
**3.70/5**, verified in JSON, PDF, and UI. Browser regression went from failing
to passing. ASR/model boundaries use fixtures; these results remain separate
from the two real analyses and their 3.45/5 observations.

Physical microphone capture remains unverified. Device enumeration found an
input, but actual `getUserMedia` returned `NotSupportedError`. Manual user
verification is pending with the application launched on port 7860; launch
alone does not establish successful hardware recording.

Local `docker info` timed out after 12 seconds; no fresh local image build/run
passed. Hosted baseline container execution passed in the run above. See the
[container report](docs/verification/container.md). Extended container source
`a732aa1` passed independent source review and eight targeted tests. Its
real-pipeline synthetic-WAV smoke mocks ASR/model boundaries and checks actual
reports and persisted History exports after container replacement. Execution
of this extended smoke passed in run 38991300177 at code revision
`1ce33f620cec42f0a97ff4c0b2b3e689a28fbc24`. Logs identify fixture
`4e65793b-f47c-40e6-ae72-b947a0ffa00a`, overall 3, and
`persistence_verified: true` after replacement. This is not live inference.

Code revision CI passed, including 365 Linux tests and the extended container
job. CI will rerun for this later documentation revision; its result is not
claimed here. No GPU/acoustic-model run or additional live provider verification
is claimed. Full ticket 04 remains open on physical microphone verification.
Gradio 6 is documented; Python support targets 3.11, with later minors uncertified.

## Publication And Archive

The [submission repository](https://github.com/amishaguptaberk/call-center-intelligence-submission)
is now public with clean history, at proven code revision
`1ce33f620cec42f0a97ff4c0b2b3e689a28fbc24`.
[Run 38991300177](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38991300177)
completed successfully for both tests and container jobs. Supplied anonymous
probes returned repository API `private: false`, raw README GET 200, and
demo HEAD 200. Original local
history contains raw excerpts and remains private. See
[publication review](PUBLICATION_REVIEW.md).

The owner approved the ten samples. The existing synthetic Echo demo remains
included in the public repository; demo HEAD 200 confirms availability,
not browser playback. Extended Echo source
remains private. No new media was created for this handoff.

The preliminary 143-file ZIP was byte-verified. Its extracted source passed
365 tests with four warnings using an existing environment, not a fresh
installation. Ruff formatting passed for 98 files. Extracted `app.main`
startup returned HTTP 200 with exactly Analyze call, All MP3 History, and
Observability on Gradio 6.28.0. The initial normal entrypoint hit a port
conflict because the user's app occupied 7860; a launch shim overrode only
`server_port` to 17862. This was a verification-environment conflict, not a
product defect; no source was edited for the retry. Final release
revision/checksum, any archive regeneration after later edits, final diff review,
and final workflow outcomes belong in the external handoff/release.
Tickets 06/07 are not marked complete here. See
[submission readiness](SUBMISSION_READINESS.md).

## Historical Evidence And Limits

Earlier evidence reported 358 tests, Sample 01/03 analysis, PDF rendering,
cache/history, metrics, and a mobile pass. It predates the fresh-install and
latest walkthrough reports and is not final-source acceptance. The initial
mobile failure and subsequent fixture-based repair checks are recorded above;
independent UI repair review subsequently passed for source/software behavior.
Timings were machine/provider-specific.

Regex redaction is approximate; raw local transcription cache has no automatic
expiry. Stock SQLite is not encrypted by setting a PRAGMA alone. Passing
software tests does not establish production readiness or policy validity.
