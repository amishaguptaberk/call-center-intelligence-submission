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

The private staging repository `amishaguptaberk/call-center-intelligence-submission`
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

## Remaining acceptance limits

The hosted smoke used `WHISPER_PRELOAD=false` and no provider credentials.
It verifies container build, startup, configuration, and storage persistence;
it does not verify container ASR, provider analysis, or export downloads.
The original ticket's container analysis and export acceptance remains
unverified and requires separate end-to-end evidence. Full ticket 03 acceptance
is therefore not established by this successful smoke run.

## Synthetic analysis and export extension (hosted execution pending)

`scripts/container_smoke.py` now generates a unique, one-second synthetic WAV
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

Local subprocess regression tests passed in module and stdin modes using
isolated temporary databases, including reopening the same call in a second
process. No local Docker build or run was attempted. The baseline hosted run
above predates this extension and does not verify its execution in a container.
The next hosted CI run must pass these additional commands before synthetic
container analysis/export acceptance can be recorded. Live ASR, model-provider
behavior, and model downloads remain outside this synthetic verification.
