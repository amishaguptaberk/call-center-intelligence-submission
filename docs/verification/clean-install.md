# Clean Installation Verification

Current status: **green** at `8825f5dc23a2a9edf7b089292f8f7d5227813177`.
The fresh install, dependency consistency, Ruff checks, and actual app HTTP
startup passed. After the authorized harness environment correction, the full
suite completed with **362 passed, 5 warnings**. Earlier disk-failure and
harness-isolation failure evidence is preserved below.

## Fresh retry at accepted source

The user's updated source instruction superseded the contract file's older SHA.
`git rev-parse 8825f5d^{commit}` resolved to
**`8825f5dc23a2a9edf7b089292f8f7d5227813177`**. This includes the publication
regression `tests/security/test_publication_reports.py`, which passed in this run.

The new root is `/tmp/submission-verify-fesKgJ`; no previous venv was reused.
The committed source was exported with `git archive`, with `.git` and `.env`
absence asserted. The temporary archive was removed after extraction. No
uncommitted report or private evidence entered the exported source.

Before installation, both the provided Python executable and supplied FFmpeg
were confirmed present and executable. Python reported **3.11.15**; FFmpeg
reported **7.1**. FFmpeg was copied into the task's `bin` directory, retaining
the external-prerequisite distinction described in the historical record.
The fresh venv explicitly excludes system site-packages.

The subprocess environment inherited only `HOME`, `LANG`, and `LC_ALL` when
present. `HOME` was preserved and `CODEX_HOME` was not reassigned or inherited.
Provider credentials were excluded. `TMPDIR` was explicitly assigned to the
task's new `tmp` directory. `HF_HOME`, `XDG_CACHE_HOME`, `PIP_CACHE_DIR`,
`DB_PATH`, and PATH were task-specific. The required
`PYTHON_DOTENV_DISABLED=1`, `PYTHONNOUSERSITE=1`, heuristic diarization,
analytics disabled, tracing disabled, and `WHISPER_PRELOAD=false` settings
remained in effect. The complete allowlist is in `02-retry-environment.json`.

Initial `df -k` reported **3,519,168 KiB available (3.36 GiB)**, above the
2 GiB threshold. After the completed checks, `df -k` reported **1,410,080 KiB
(1.34 GiB)**. These are shared-filesystem observations, not a measured install
footprint; other activity also affects free space. `du -sh` reported **1.0 GiB**
for the complete task root. No disk error occurred in this attempt.

### Executed retry checks

Here `$V` is `/tmp/submission-verify-fesKgJ/venv`. Commands ran from the exported
source directory with the explicit isolated environment.

| Command or assertion | Result |
| --- | --- |
| Supplied Python `-m venv $V` | PASS, exit 0 |
| `$V/bin/python -V` | PASS, exit 0, Python 3.11.15 |
| Task `bin/ffmpeg -version` | PASS, exit 0, FFmpeg 7.1 |
| `$V/bin/python -m pip install --no-cache-dir -r requirements-dev.txt` | PASS, exit 0 |
| `$V/bin/python -m pip check` | PASS, exit 0, no broken requirements |
| `$V/bin/python -m pytest tests/ -v` | FAIL, exit 1: 361 passed, 1 failed, 5 warnings in 54.33s |
| `$V/bin/ruff check .` | PASS, exit 0, all checks passed |
| `$V/bin/ruff format --check .` | PASS, exit 0, 92 files already formatted |
| `$V/bin/python app.py`, HTTP `/config` assertion | PASS, HTTP 200 and all three tabs |
| `$V/bin/python -m pip freeze` | PASS, exit 0; resolved package versions saved |

The full suite collected and executed **362 tests**, including the publication
regression and the nearest submission tests. No tests were added, skipped, or
modified for this verification. The failure's exact final output was:

```text
FAILED tests/unit/test_config.py::test_dotenv_loading - AssertionError: asser...
================== 1 failed, 361 passed, 5 warnings in 54.33s ==================
```

The full assertion in the saved log is `assert 'base' == 'tiny'` at
`tests/unit/test_config.py:151`. That test creates its own temporary `.env`
containing `WHISPER_MODEL_SIZE=tiny` and explicitly calls python-dotenv on it.
The contract-required `PYTHON_DOTENV_DISABLED=1` suppresses this loading, leaving
the default `base`. This explains the failure without establishing a defect in
the application. No source fix, test skip, or environment exception was made.
To complete acceptance, the contract needs to permit dotenv loading for the
test suite in this credential-free exported environment, while retaining dotenv
disablement for startup, or authorize a separately scoped test-isolation change.

### Actual HTTP startup

Port 7860 was available, so no alternate launch or port was used. The actual
`app.py` initialized its workflow and temporary SQLite database and returned
HTTP **200** from `http://127.0.0.1:7860/config`. The JSON contained exactly:

- `Analyze call`
- `All MP3 History`
- `Observability`

Only the owned server, PID 61977, was terminated and reaped (exit -15 after
SIGTERM). No server remains running from this attempt. The HTTP response,
startup log, database-existence assertion, and termination result are saved.
This verifies credential-free UI startup with `WHISPER_PRELOAD=false`; it does
not verify speech-model downloads, inference, provider calls, or microphone
workflows. Live acceptance remains ticket04's scope.

### Retry evidence and retained environment

All new compact evidence uses the `02-retry-*` prefix under
`.scratch/submission-ready/evidence/`, preserving original failure logs.
It includes the runner, command exit codes, environment, venv configuration,
install/test/Ruff logs, resolved dependency versions, HTTP JSON, and disk data.
The new task source and venv are temporarily retained for independent review
and to avoid another install. The venv installation is complete; the remaining
blocker is the test-environment contract conflict. No second install was made
within this fresh retry. No developer files, application source, dependencies,
history, or remotes were changed; no commits, pushes, or delegation occurred.
This remains macOS ARM64 verification, not Ubuntu CI, Docker, GPU, pre-commit,
or remote verification. Transitive requirements are not fully locked.

## Corrected pytest environment and final acceptance

The user clarified that `PYTHON_DOTENV_DISABLED=1` applies to runtime startup,
not pytest. The earlier **361 passed, 1 failed** result above is retained as a
**harness isolation error**, not an application regression. Under the corrected
contract, acceptance is now satisfied.

The same genuinely fresh installed venv and exported source were reused:

- Interpreter: `/tmp/submission-verify-fesKgJ/venv/bin/python`
- Source: `/tmp/submission-verify-fesKgJ/source`
- Source SHA: `8825f5dc23a2a9edf7b089292f8f7d5227813177`

Before rerunning tests, the export's `.env` absence and all lexical and resolved
parent discovery paths were checked using existence checks that also reject
symlinks. The absent paths were `/.env`, `/private/.env`, `/private/tmp/.env`,
`/tmp/.env`, and `.env` at the task root and source directory under both
`/tmp` and `/private/tmp`. No private dotenv source was found on those discovery
paths. No credentials were inherited or added. Tests remain free to create
their own controlled temporary `.env` fixtures.

Only `PYTHON_DOTENV_DISABLED` was removed from the previously recorded explicit
pytest environment. Startup evidence continues to use `PYTHON_DOTENV_DISABLED=1`
and `WHISPER_PRELOAD=false`. No application or test implementation changed;
no test was skipped, xfailed, or otherwise weakened.

| Corrected command | Result |
| --- | --- |
| Fresh venv `python -m pytest tests/unit/test_config.py::test_dotenv_loading -v` | PASS, exit 0, 1 passed |
| Fresh venv `python -m pytest tests/ -v` | PASS, exit 0, 362 passed, 5 warnings in 9.13s |

Existing passing installation, pip check, lint, formatting, and actual HTTP
startup results above remain applicable: no source changes or reinstall occurred.
Only the requested targeted and full tests were rerun. The five warnings are
the existing librosa/audioread fallback and deprecated standard-library audio
module warnings, retained in the full log. No inference claim is made.

New evidence is saved under `.scratch/submission-ready/evidence/02-corrected-*`:
the explicit pytest environment, absent dotenv discovery paths, runner, targeted
and full test logs, command exit codes, and final reviewer manifest. Original
`02-retry-*` failed-suite logs and manifest remain unchanged historical records.
The complete venv and source remain temporarily retained for reviewer reuse;
no second install, commits, pushes, or delegation occurred. Only the owned
report and private evidence were updated in the submission workspace.

## Historical attempt at older source

The remainder records the earlier failed installation and its authorized cleanup.

## Source and isolation

- Attempt date: 2026-10-16 (UTC).
- Exact source revision: `e8e5d2c1edcfd18b4679a5a84e337b28e90a42ca`.
- Source exported with `git archive` into `/tmp/submission-verify-XT1JGw/source`.
  The export contains committed files only; `.git` and `.env` absence was asserted.
  Later commits and existing submission workspace changes were not included.
- Host: macOS, Darwin arm64. This does not verify Ubuntu CI or other platforms.
- Fresh venv: `/tmp/submission-verify-XT1JGw/venv`, Python 3.11.15,
  `include-system-site-packages = false`. No developer venv was reused.
- Bootstrap interpreter:
  `/Users/amisha.gupta/.local/share/uv/python/cpython-3.11-macos-aarch64-none/bin/python3.11`.
- FFmpeg 7.1 was explicitly copied from the externally supplied executable
  `/Users/amisha.gupta/call-center-intelligence/.scratch/video-deps/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1`
  into the temporary `bin/ffmpeg`. This is an externally supplied prerequisite,
  not an application dependency or evidence FFmpeg was originally on PATH.

All subprocesses used an explicit environment allowlist: inherited `HOME`,
`TMPDIR`, `LANG`, and `LC_ALL` only when present, plus task-specific settings.
`HOME` was not reassigned. Provider credentials and developer Python paths were
not inherited. Settings included `PYTHONNOUSERSITE=1`,
`PYTHON_DOTENV_DISABLED=1`, `WHISPER_PRELOAD=false`,
`DIARIZATION_BACKEND=heuristic`, `GRADIO_ANALYTICS_ENABLED=False`,
`LANGCHAIN_TRACING_V2=false`, temporary `DB_PATH`, and temporary
`HF_HOME`, `XDG_CACHE_HOME`, and `PIP_CACHE_DIR`.

## Executed checks

Commands below ran in the exported source using the fresh environment.
`$V` denotes `/tmp/submission-verify-XT1JGw/venv`.

| Check | Result |
| --- | --- |
| Bootstrap Python `-m venv $V` | PASS, exit 0 |
| `$V/bin/python -V` | PASS, exit 0: Python 3.11.15 |
| `/tmp/submission-verify-XT1JGw/bin/ffmpeg -version` | PASS, exit 0: FFmpeg 7.1 |
| `$V/bin/python -m pip install -r requirements-dev.txt` | FAIL, exit 1: disk full |

The exact install failure was:

```text
ERROR: Could not install packages due to an OSError: [Errno 28] No space left on device: '/tmp/submission-verify-XT1JGw/venv/lib/python3.11/site-packages/scipy/spatial/transform/tests/test_rigid_transform.py'
```

After failure, `df -h` reported the shared Data filesystem at 100% capacity,
with 131 MiB available. The temporary export used 34 MiB, incomplete venv
408 MiB, pip cache 226 MiB, and archive 34 MiB. This is an environment blocker,
not evidence of an application or dependency compatibility defect. No dependency
versions were changed and no installation workaround was attempted.

## Unexecuted acceptance checks

The runner stopped at the failed installation as required by this ticket.

- `$V/bin/python -m pip check`: not run.
- `$V/bin/python -m pytest tests/ -v`: not run; **0 tests executed**.
- `$V/bin/ruff check .`: not run.
- `$V/bin/ruff format --check .`: not run.
- `$V/bin/python app.py` and `GET http://127.0.0.1:7860/config`: not run.
  The expected tabs remain unverified over HTTP: `Analyze call`,
  `All MP3 History`, `Observability`.

No application server was started and no unrelated process was stopped.
No inference, provider request, speech-model download, microphone test,
Docker build, pre-commit run, or remote CI verification was performed.
The intended `WHISPER_PRELOAD=false` startup checks credential-free UI only;
live end-to-end acceptance belongs to ticket04.

## Evidence and retry

Private evidence is under `.scratch/submission-ready/evidence/02-*`, with the
original logs also retained in `/tmp/submission-verify-XT1JGw/evidence`.
`02-verify.py` records the exact export, environment, command sequence, intended
HTTP assertions, and owned-process cleanup. `02-results.json` contains actual
executed command exit codes, not planned results. The incomplete venv was removed
during the authorized cleanup below.

To unblock, provide sufficient local disk capacity or an authorized volume with
space, then repeat from a new temporary root and fresh venv at the same SHA.
Do not treat retrying the partially installed venv as clean-install evidence.
Direct requirements are pinned; transitive dependencies are not fully locked,
so this attempt cannot establish identical future dependency resolution.

Only this report and owned private evidence were added. Existing tracked and
untracked work, developer environments, databases, settings, history, and remotes
were preserved. No commits, pushes, or delegation occurred.

## Authorized cleanup and retry assessment

On the subsequent cleanup request, compact logs and the original runner were
confirmed present in the owned private evidence directory before deletion.
Only these task-created paths under `/tmp/submission-verify-XT1JGw` were removed:
`pip-cache`, `venv`, `source`, `source.tar`, and `bin` (the copied FFmpeg).
The original supplied FFmpeg, preexisting caches, and user files were untouched.

| Observation | Available space |
| --- | --- |
| Before cleanup, `df -k` | 657,252 KiB (642 MiB) |
| After cleanup, `df -k` | 1,429,556 KiB (1,396 MiB) |
| Observed increase | 772,304 KiB (754 MiB) |

The available-space change is a point-in-time observation on a shared filesystem;
other activity can also affect it. `du -sh` confirmed the temporary root now
contains only **84 KiB** of compact evidence and the runner. There are no remaining
task-owned source copies, venvs, wheels, or copied executables there.

A conservative **2 GiB available-space threshold** was used for deciding whether
to make the single permitted fresh attempt. This is an operational estimate for
the installed scientific/speech stack plus transient wheel/extraction space,
not a measured application minimum. Disabling pip caching removes persistent
download duplication but does not eliminate installation temporary files.
The observed 1,396 MiB was below that threshold, so **no second install was
attempted**. The next fresh attempt should use `python -m pip install
--no-cache-dir -r requirements-dev.txt` and a task-owned `TMPDIR` in addition
to the original isolated environment settings.

Cleanup checks executed successfully: `df -k` before and after, task-root `du`,
private evidence inventory, and bounded removal of the five owned paths.
The initial shell removal command was rejected by the command runner's policy;
bounded standard-library deletion then completed successfully. No application
checks ran during cleanup. Total tests executed remains **0**; pip check,
Ruff, and HTTP startup remain unverified. Evidence: `02-cleanup.txt`.
