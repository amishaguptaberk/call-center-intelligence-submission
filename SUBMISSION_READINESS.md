# Submission Readiness

Status on 2026-10-16: **public source; final acceptance evidence pending**.
Scope: the standalone SQLite/Gradio capstone. Tickets 06/07 remain open.
The previous ZIP is stale. This checklist does not award a grade.

This is the source snapshot's evidence and release checklist. Consult
[Actions](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions)
for results tied to the final revision and
[Releases](https://github.com/amishaguptaberk/call-center-intelligence-submission/releases)
and the final handoff for public-access confirmation, release revision, archive
checksum, and extraction results. Those external records are populated after
checks and packaging; their links do not assert completion. Archive metadata
is kept outside its own source snapshot to avoid a checksum self-reference.

## Accepted Evidence

| Evidence | Scope and result |
| --- | --- |
| Requirements, accepted `e8e5d2c` | [Requirement matrix](docs/milestones/requirements-matrix.md); Gradio 6, filepath audio, and three-tab compatibility decisions documented. Python target is 3.11. |
| Privacy, accepted `8825f5d` | Current report excerpts sanitized; original history remains unsuitable for publication. See [publication review](PUBLICATION_REVIEW.md). |
| Clean-install report, accepted `28669fb` | Exported source `8825f5d`: fresh install, 362 tests, lint, format, pip check, and HTTP startup with three tabs passed on Python 3.11.15/macOS ARM64 with FFmpeg 7.1. [Full report](docs/verification/clean-install.md) preserves earlier failures and corrected test isolation. |
| Live browser walkthrough | Two analyses verified detected-pattern redaction, matching PDF/JSON IDs, weighted 3.45/5, cache, history/restart, and metrics. [Walkthrough](docs/verification/reviewer-walkthrough.md) records failures and limits. |

## Hosted Baseline

Historical staging evidence records the clean-history repository
[call-center-intelligence-submission](https://github.com/amishaguptaberk/call-center-intelligence-submission)
initial revision `2ea14c02de44c884437bfa6cc1d0c737f0402c16`,
mapping to private source `2882df9`. Its new root contains 139 files; original
private history was not uploaded. Baseline local checks passed 363 tests,
lint, and formatting; the bounded scan found no blocked token patterns or
forbidden runtime paths.

[Run 38990340548](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38990340548)
completed successfully with both tests and container jobs passing.
These results certify the staging baseline only. Updated local source passes
365 tests, including new container integration coverage. Synthetic browser
checks pass mobile geometry/History stacking, desktop columns, invalid-decode
feedback and recovery after reload, redacted exports, cache, history, metrics,
and newest-20 audit rows. Real `score_qa` overrides a fixture's incorrect
overall 5 with weighted 3.70 from scores 4/2/5/3/4 in JSON/PDF/UI.
These are fixture results, separate from the two real analyses.
Independent UI repair review passed: 365 tests, lint, formatting, and fresh
browser software checks were independently rerun. The repository is now public
at proven code revision `1ce33f620cec42f0a97ff4c0b2b3e689a28fbc24`;
[run 38991300177](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38991300177)
completed successfully with 365 Linux tests and the extended container job.
Anonymous repository API returned `private: false`, raw README GET 200, and
demo HEAD 200; these probes do not establish browser playback.
The preliminary 143-file ZIP was byte-verified and extracted
source passed 365 tests using the existing environment, not a fresh install.
CI for the later documentation revision will rerun; no result for that revision
is claimed. Final release revision/checksum remains in the external handoff.

## Remaining Gates

- [x] Complete independent UI repair review: 365 tests, lint, formatting, and
  fresh browser software checks passed on independent rerun, including zero
  overflow at 390px and stacked History. Prior failures remain recorded.
- [ ] Verify physical microphone permission, capture, and end-to-end recording.
  One device was found, but actual capture returned `NotSupportedError`;
  manual user verification remains pending.
- [x] Verify software invalid-decode feedback/recovery and newest-20 audit rows
  with the synthetic browser harness; recovery required reload.
- [x] Verify code revision `1ce33f6` in run 38991300177: tests and extended
  container job passed, including persisted History exports after replacement.
  Baseline hosted container execution passed; local Docker readiness timed out
  and no local image build/run passed. See the
  [container report](docs/verification/container.md). Extended source `a732aa1`
  passed independent source review and eight targeted tests; real-pipeline
  synthetic audio with mocked ASR/model boundaries, reports, and persisted
  History exports after replacement passed hosted execution. Fixture overall
  was 3 and `persistence_verified` was true.
- [ ] Run relevant checks against final source, review the complete final diff
  and publication scope, and record exact revision/results.
- [x] Prepare a source-only repository with newly created history, now public.
  Keep original local commits, refs, tags, and objects private.
- [x] Confirm public visibility of the clean-history
  [public repository](https://github.com/amishaguptaberk/call-center-intelligence-submission).
- [x] Record anonymous probes: API `private: false`, raw README GET 200,
  demo HEAD 200. Browser playback is not established.
- [ ] Monitor all required final-source remote checks to completion and record
  run links and outcomes for the later documentation revision. The proven code
  run does not certify subsequent revisions.
- [x] Byte-verify the 143-file ZIP and run its extracted source: 365 tests passed
  using the existing environment, not a new installation.
- [ ] Record release revision/checksum and any final archive regeneration in the
  external handoff/release; reverify if subsequent source changes alter it.
  Exclude secrets, runtime data, caches, private evidence, model weights, and
  repository internals.
- [ ] Record final proof in the release/handoff: revision-specific CI, review,
  public visibility/access, archive checksum, and extraction verification.
  Source evidence remains in [verification](VERIFICATION.md) and
  [submission notes](SUBMISSION.md).

The owner approved inclusion of the ten samples; the existing synthetic Echo
demo is included. No new media is required. Owner approval is not independent
third-party rights verification. Private extended Echo source is outside scope.

## Limits

Tests do not establish scoring accuracy, policy validity, production capacity,
or complete anonymization. Live provider evidence covers OpenAI/GPT-4o;
other providers, GPU, and acoustic diarization remain unverified. A hosted
Space is optional unless separately required and has not been verified.
Historical failures remain in their reports; later passes do not erase them.
