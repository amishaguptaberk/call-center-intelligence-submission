# Container verification

The `container` job in `.github/workflows/checks.yml` builds the Dockerfile on
Ubuntu and starts the resulting image without provider credentials or model
preloading. It asserts a nonroot runtime, available FFmpeg, bundled MP3 samples,
valid Gradio `/config`, and the initialized application database. It writes a
SQLite sentinel into an isolated named volume, replaces the container, and
checks that the sentinel survives and HTTP readiness returns.

The job has a 30-minute limit, a 20-minute build limit, bounded Docker commands,
and a bounded HTTP readiness loop. Cleanup targets only the image, container,
and volume named for that workflow run and attempt. Failures propagate through
strict shell handling and Python assertions; cleanup is best effort.

## Local evidence (2026-10-16)

- Docker daemon readiness: `docker info` timed out after 12 seconds.
- Available disk: 1.19 GiB. No image build or container run was attempted locally.
- No Docker restart, reset, prune, or unrelated process termination was performed.
- The workflow structure regression test failed first because the container job
  was absent. Its passing result verifies structure only, not Docker execution.

## Hosted Ubuntu evidence (2026-10-17 UTC)

The then-private staging repository `amishaguptaberk/call-center-intelligence-submission`
completed [Checks run 38990340548](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38990340548)
successfully at source SHA `2ea14c02de44c884437bfa6cc1d0c737f0402c16`.
This clean-history source corresponds to local source `2882df9`, as recorded
in the publication handoff. Read-only run metadata confirms both `tests` and
`container` jobs completed successfully; the container job finished at
`2026-10-17T01:21:25Z` on hosted Ubuntu 24.04.

The container job logs and successful strict-shell step establish:

- The Docker image built successfully and the built image started.
- The runtime UID was nonzero, FFmpeg executed, and bundled MP3 samples existed.
- Gradio `/config` returned a version and exactly these ordered tab labels:
  `Analyze call`, `All MP3 History`, `Observability`, on both startups.
- The application initialized the `call_records` table in the mounted SQLite database.
- A SQLite sentinel survived stopping and removing the first container and
  starting a replacement with the same isolated named volume.

Cleanup was invoked for run-owned resources, but its best-effort commands
suppress failures; job success alone does not prove each cleanup succeeded.
This is hosted Ubuntu runtime evidence. It does not establish that the local
Docker daemon recovered; the earlier local timeout evidence remains applicable.

## Synthetic analysis and export evidence (2026-10-17 UTC)

The now-public repository completed
[Checks run 38991300177](https://github.com/amishaguptaberk/call-center-intelligence-submission/actions/runs/38991300177)
successfully at source SHA `1ce33f620cec42f0a97ff4c0b2b3e689a28fbc24`.
Read-only run metadata confirms both `tests` and `container` jobs passed.
The hosted Ubuntu container job ran from `2026-10-17T01:32:29Z` to
`2026-10-17T01:34:25Z` (1 minute 56 seconds).

`scripts/container_smoke.py` generated a unique, one-second synthetic WAV
and invokes the real `process_call` intake, security, graph, report, and database
flow. Only the transcription, summarization, and QA boundary functions are
replaced in that process. Every report contains `SYNTHETIC FIXTURE ONLY`.
The script asserts redaction before both model boundaries, a 3.0 weighted
baseline across five dimensions, matching report call IDs, and decoded PDF
and JSON content. It removes its temporary exports after verification.

CI streams the script into the running image without adding development
dependencies or copying scripts into the image. After container replacement,
`--check-persistence` queries the actual `call_records` fixture row and invokes
the real `history_report` to regenerate and verify both exports for that call.
Each invocation has a 60-second timeout; both existing ordered-tab startup
assertions and the independent storage sentinel remain in place.

The successful extended job verified the real pipeline and regenerated PDF
and JSON exports after container replacement for synthetic fixture call
`4e65793b-f47c-40e6-ae72-b947a0ffa00a`. Logs recorded `overall_score: 3.0`
on both invocations, with `persistence_verified: false` at
`2026-10-17T01:34:04.9337096Z` and `persistence_verified: true` at
`2026-10-17T01:34:22.8306815Z`. Both outputs explicitly identify
`synthetic_fixture: true`. This establishes synthetic container analysis,
redacted PDF/JSON generation, actual call-record persistence, and history
export regeneration for the same call after replacement.

Local subprocess regression tests also passed in module and stdin modes using
isolated temporary databases. No local Docker build or run was attempted;
hosted success does not imply recovery of the local daemon.

## Verified scope and limits

Hosted verification now covers Docker build, nonroot execution, FFmpeg,
samples, both ordered-tab startup assertions, synthetic pipeline analysis and
PDF/JSON contents, and persisted-call reopening with regenerated exports after
container replacement. This closes the scoped synthetic container analysis
and export verification extension.

The run used `WHISPER_PRELOAD=false` and no provider credentials. Transcription,
summarization, and QA model boundaries were synthetic in-process fixtures;
live ASR and provider behavior inside the container remain unchecked. Export
files were verified inside the container, not downloaded through a browser.
No broader live-model or browser-download acceptance is implied. Cleanup
remains best effort as described above, and the local daemon timeout evidence
is unchanged.
