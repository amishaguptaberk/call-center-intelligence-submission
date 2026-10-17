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

## Outstanding verification

Publish the change and run the Checks workflow. Inspect the `container` job to
confirm the actual image build, startup, assertions, replacement persistence,
and cleanup complete successfully. Until that run succeeds, runtime container
verification is blocked. Provider analysis and export downloads are outside
this credential-free smoke test and still require separate end-to-end evidence.
