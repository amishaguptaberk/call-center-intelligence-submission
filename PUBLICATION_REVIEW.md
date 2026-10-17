# Publication review

Date: 2026-10-16. Status: **public clean-history source; code CI passed**.
This is a bounded publication
review, not exhaustive secret, media-content, or legal clearance.

The review below applies to its stated historical snapshot. Sanitization was
accepted at `8825f5d`; subsequent requirement/verification work includes
`28669fb`, and HEAD observed for this documentation pass is `2882df9`.
Later changes still require final diff and publication-scope review.
The public submission repository is
[call-center-intelligence-submission](https://github.com/amishaguptaberk/call-center-intelligence-submission).
Proven public code revision is `1ce33f620cec42f0a97ff4c0b2b3e689a28fbc24`.
Anonymous API returned `private: false`, raw README GET 200, and demo HEAD 200.
Final release metadata remains external; tickets 06/07 are not marked complete.

## Clean-history Publication Update

The repository was initially staged privately and is now public.
Initial revision `2ea14c02de44c884437bfa6cc1d0c737f0402c16`
maps to private source `2882df9`, with a new Git root containing 139 files.
Original private history was not uploaded. Baseline local verification passed
363 tests, lint, and formatting; a bounded scan found no blocked token patterns
or forbidden runtime paths. These findings are not exhaustive privacy clearance.

[Run 38990340548](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38990340548)
completed successfully for both tests and container jobs. Later supplied source
verification passed 365 local tests and synthetic browser repair checks;
extended container source `a732aa1` passed independent source review and eight
targeted tests. Independent UI repair review passed with 365 tests, lint,
formatting, and fresh browser software checks independently rerun.
Physical microphone capture remains unverified; full ticket 04 remains open.
These local results do not extend the baseline hosted result or establish a
fresh Linux pass. Current [run 38991300177](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38991300177)
completed successfully for code revision `1ce33f6`: 365 Linux tests and the
extended container job passed. Container logs report fixture
`4e65793b-f47c-40e6-ae72-b947a0ffa00a`, overall 3, and persistence verified
after replacement. This later documentation revision will rerun CI; no result
for it is asserted.
The preliminary 143-file ZIP was byte-verified; extracted source passed 365 tests
using the existing environment, not a fresh installation. Anonymous demo HEAD
200 is availability evidence, not browser playback. Final release
revision/checksum remain in the external handoff.
The historical review below retains its original scope and observations.

Subsequent final-source checks are recorded in
[Actions](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions).
Public visibility/access confirmation and archive revision/checksum/extraction
results belong in the final handoff and
[Releases](https://github.com/amishaguptaberk/call-center-intelligence-submission/releases),
outside the source snapshot being archived. Their links are reference points,
not claims that publication or final checks have completed.

## Scope and boundary

Reviewed the public capstone checkout at revision
`34c494975cfd2e111d8eda686c0172ab6032c6d1`: 134 tracked paths,
17 reachable commits, 317 reachable objects, and 193 unique blobs
(181 text blobs and 12 media blobs). Concurrent ticket work is outside this
snapshot; its transient changes were not treated as publication regressions.
No private Echo checkout, credentials, remotes, or remote services were accessed.

`SUBMISSION.md` identifies the SQLite/Gradio capstone and excludes the later
Echo dashboard and Postgres migration. The extended product remains private;
the included demo is described there as synthetic. That description was not
independently verified against video frames or audio.

## Recording permission

On 2026-10-16, the owner answered "yes thats fine can include in the repo"
to the specific question whether all ten bundled recordings may appear in a
public submission. Owner approval is confirmed. No independently inspected
license, original source URL, creator attribution, or third-party rights
verification was available. The sample README records this distinction;
educational/testing language alone was not treated as a redistribution grant.

## Sanitized current source

`evaluation/reports/heuristic_all10_failure_modes.json` originally contained
**73 nonempty call-text excerpts** in example `text` fields across the ten
samples. One contained identifier-like digits; their real-world significance
was not established. All 73 example text values are now null. The report note
explicitly records the omission. Aggregates, timestamps, speaker labels,
reasons, and other diagnostic fields are retained. No excerpts are reproduced
here. Read-only consumer search found only a script comment stating it does
not overwrite this report; no code consumer of its example text was located.

The original unsanitized file remains in reachable history, with one
path-specific commit. All ten MP3s also entered the root commit. Sanitizing
the working source does not remove historical copies. History was not rewritten.

## Mandatory publication condition (ticket 06)

Generate a **NEW clean-history publication repository from the reviewed,
sanitized source snapshot**. Retain the original history privately. Do not
push this existing repository's history or import its commits, refs, object
database, or tags into the public repository. Copy only reviewed source files,
not the working directory wholesale; exclude local configuration, credentials,
runtime data, caches, and diagnostic scratch evidence. Include the provenance
note, this review, sanitized report, and regression test in that snapshot.

Ticket 06 must verify that the new repository contains only the reviewed
snapshot and clean newly created history before publication. This is a
mandatory acceptance condition, not a suggestion. At the historical review
snapshot, no new repository or publication had been created; private staging
was subsequently created as recorded above. The original history is **not cleared
for publication**. Under this explicit condition, the concrete current-source
disclosure finding is resolved; no other actual disclosure issue was identified
within the bounded review. Owner recording approval is not third-party licensing.

## Other evidence and configuration

- Inspected structure and selected privacy fields across all 21 tracked
  evaluation files and the historical milestone evidence (33 evidence blob
  versions in reachable history). Baseline segment text is null in all 36
  entries. Imported public predictions contain 809 redacted length/hash
  fingerprints rather than raw text. Worksheets have 36 timing/role rows;
  schemas describe fields rather than populated transcripts. Milestone live
  evidence declares synthetic input; it does not verify this export's tests.
- Reference import provenance contains an author workstation path. This is
  identifying provenance metadata already present in source, not a credential;
  no private path contents were accessed or reproduced here. Tests/specification
  also contain email-shaped examples; their provenance was not independently
  authenticated. These are bounded scan observations, not blanket PII clearance.
- The tracked environment template leaves credential values blank and disables
  tracing by default. Ignore rules exclude local environment files, databases,
  caches, raw prediction exports, and runtime audio. Ignore rules do not protect
  already tracked files or historical content.
- `scripts/deploy_space.py:runtime_files` is a deployment allowlist, including
  samples and demo media. It is not a public Git publication allowlist. Its
  deployment entry point was not run because it accesses remote services.
- A local bounded scan of all 181 reachable text blobs found no matches for
  selected provider-token, access-key, and private-key-header patterns. This
  does not establish absence of secrets, arbitrary credentials, or private data.

## Media and verification limits

Local metadata inspection used the already installed `mutagen` library and
PNG chunk parsing. Each MP3 has only an encoder (`TSSE`) tag and no ID3v1
tag; none supplies source or permission metadata. The MP4 is about 41.72
seconds and exposes only an encoder tag. The preview PNG has image,
resolution, and end chunks, with no text metadata chunks. These checks do not
inspect spoken content, visible frames, embedded overlays, or steganography.
No recording was played or transcribed; no audio or image content was sent
to a model service. The demo was not played or visually cleared.

Dedicated scanners `gitleaks` and `trufflehog` were unavailable. `ffprobe`,
`ffmpeg`, and `exiftool` were also unavailable on PATH. Nothing was installed.
An exhaustive legal, semantic PII, media-content, or secret audit was not run.

## Executed checks

- `git ls-files`: pass; 134 tracked paths at inventory time.
- `git rev-list --objects --all`: pass; 317 reachable objects, 17 commits.
- Local read-only history, structured evidence, credential-pattern, and media
  metadata inspection: completed with the scope and limitations above.
- `.venv/bin/python -m pytest -q tests/unit/test_space_deployment.py tests/unit/test_submission.py`:
  pass, **7 passed in 3.12s**. This result preceded concurrent test-file edits;
  it is a run-specific observation, not final verification of that ticket.
  These tests cover packaging/runtime behavior, not legal permission or privacy.
- Repeated the same pytest command after the concurrent test changes observed
  during this audit: pass, **8 passed in 5.61s**. `git diff --check`: pass.
- Dedicated secret scanner: unavailable, not passed. Full CI, GPU behavior,
  remote publication, audio listening, and video/image content review: not run.
- Sanitization regression: `tests/security/test_publication_reports.py` first
  failed on nonempty example text (1 failed), then passed after sanitization.
  Combined command:
  `.venv/bin/python -m pytest -q tests/security/test_publication_reports.py tests/unit/test_space_deployment.py tests/unit/test_submission.py`:
  **9 passed in 3.01s**.
- `.venv/bin/ruff check .`: pass. `.venv/bin/ruff format --check .`: pass,
  92 files already formatted. Structured comparison against HEAD confirmed
  only the 73 example text values and appended omission note changed in the
  failure-mode report; all other diagnostic data was preserved.

The publication report, local diagnostic evidence, narrow sample provenance
note, sanitized evaluation report, and focused security regression test were
authored for this review. No application implementation changes, commits,
pushes, history changes, or remote operations were performed.
