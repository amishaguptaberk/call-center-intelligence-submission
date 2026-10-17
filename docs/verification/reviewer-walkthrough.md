# Ticket 04: Reviewer Walkthrough

Current status: **software acceptance passed; physical microphone blocked**.
Latest software evidence is the weighted-score repair section at the end of
this report, under `04-final-score-repair-green`; earlier captures are retained.
The final verification addendum below supersedes the original open software
items. The original evidence and live-provider results are preserved here.

Original status: **blocked (partial verification)**. Run date: 2026-10-16 America/Chicago
(SQLite timestamps cross into 2026-10-17 UTC).

## Scope and Isolation

Used accepted source snapshot `8825f5dc23a2a9edf7b089292f8f7d5227813177`
at `/tmp/submission-verify-fesKgJ/source` with its accepted Python 3.11 venv.
Browser and PDF inspection used `/opt/anaconda3/bin/python` with existing
Playwright Chromium and pypdf. FFmpeg 7.1 executed successfully.
No installations, model downloads, implementation edits, delegation, commits,
or pushes. Existing base weights were reused read-only with hub offline mode.

Task root: `/tmp/ticket04-eRBiQj`. SQLite, temporary audio, exports, and browser
uploads were isolated there. Server bound to `127.0.0.1:17864`, share disabled,
analytics disabled, both tracing flags disabled, preload false, heuristic
diarization, Whisper base. Dotenv discovery and user-site imports disabled.
Only allowlisted provider settings were imported into server memory. No
credentials or raw transcript were included in this report or evidence manifest.

## Executed Live Checks

Exactly two real browser analyses: uploaded `sample_01.mp3`, then uploaded the
same recording again. No other model analyses were run. First completion:
27.65 seconds, 19 transcript segments, QA 3.45/5.

| Check | Result and evidence |
| --- | --- |
| Model/browser readiness | Existing Chromium launched; cached base model completed ASR without downloads. |
| Runtime discovery | `/config` labels and `_run` dependency discovered at runtime; output order recorded in `04-results.json`. |
| First analysis | PASS; `04-analysis-desktop.png`. Full ID `398ed812-bd9a-4057-8db6-f4ce9ac441b9`. |
| Browser exports | PASS; first report downloaded from reopened History, repeat report downloaded from Analyze. Both PDF/JSON full IDs match each other and nested JSON stages. PDFs privately inspected with pypdf: 3 pages each. |
| Weighted scores | PASS; independently applied professionalism .15, empathy .20, problem resolution .30, compliance .20, communication clarity .15. Both equal 3.45 and rendered score. |
| Redaction | PASS for the sample's one detected pattern span: absent from UI transcript, downloaded JSON and PDF. Two placeholders in serialized report. No claim of complete PII detection. |
| Cache | PASS; `cache_hit=True` diagnostic plus cache count unchanged at 1. Server shutdown flushed buffered diagnostic. This is transcription caching; repeat still performs downstream analysis. |
| History | PASS; reopened first call and regenerated browser exports with counts unchanged: 1 call, 1 cache row, 2 audit events. Reopened stored report after server restart without inference. `04-history.png`. |
| Observability | PASS metrics: total/completed 2, success 100%, average 3.45, review/failed/flags 0, audits 4; compared all displayed metrics to isolated DB. `04-observability.png`. |
| Audit rows/cap | Four rows visibly confirmed in screenshot. Automated unscoped `tbody tr` assertion failed; source `limit(20)` read, but saturation behavior was not executed. |
| Browser failure handling | UNVERIFIED; corrupt MP3 fixture uploaded, no visible error after 2.5 seconds. No Analyze click/model call. `04-failure.png` records this inconclusive state, not a passing failure screen. |
| Mobile | FAIL at 390px: document width 390, one button spans x=295..412. History summary/QA remain narrow side-by-side columns with excessive word wrapping. `04-mobile.png`; no design edits. |
| Physical microphone | UNVERIFIED; browser inventory reported 1 audio input, but no physical capture or end-to-end hardware recording was verified. No fake audio used. |

Repeat full ID: `fc5d33e5-37d8-49aa-85be-839270465f8d`.
First downloaded PDF/JSON: 6,417 / 10,833 bytes; repeat: 6,411 / 10,915 bytes.
Final live DB before cleanup: 2 call records, 1 transcription-cache row,
4 audit events. Local database contains raw cached ASR; it is not public evidence.

## Automated Fixture Checks

Executed from accepted source with a credential-cleared `env -i`, disabled dotenv,
disabled bytecode writes, and task-owned pytest cache/temp directories:

```text
/tmp/submission-verify-fesKgJ/venv/bin/python -m pytest tests/integration/test_reviewer_journeys.py -q
11 passed in 6.84s

/tmp/submission-verify-fesKgJ/venv/bin/python -m pytest tests/unit/test_intake.py -q
29 passed in 0.34s
```

Commands additionally used `-o cache_dir=/tmp/ticket04-eRBiQj/pytest-cache`
and task-owned `--basetemp` paths. Logs retained as `04-reviewer-tests.log`
and `04-intake-tests.log`.

Reviewer journeys mock ASR and provider results. Injection rejection, critical
review, low confidence, sanitized provider failure, redaction sent to mocked
providers, restart/history, audit immutability, and simulated microphone tuple
passed as fixture coverage. Intake tests cover invalid/malformed audio and
compressed-format handling. These are not live adversarial model results or
physical microphone proof. No scoring-accuracy or policy-validity claim.

## Limitations and Stop Conditions

Ticket remains blocked on physical microphone proof and mobile acceptance.
Browser-visible failure handling and a saturated 20-row audit display remain
unverified. No provider quota/error-path testing was attempted beyond the two
authorized analyses. Successful provider responses do not establish retry or
quota behavior.

Harness corrections were limited to task-owned scripts: scope upload selector
after History introduced another file input; use visible transcript textarea;
flush buffered cache diagnostic on server shutdown. The audit DOM assertion
failed and was not counted as passing. The mobile assertion failed and was
recorded, with no implementation change or acceptance relaxation.

All five screenshots and `04-results.json` are in
`.scratch/submission-ready/evidence/`. `04-closeout.json` records final server
shutdown, file hashes/sizes, and task-only cleanup. No accepted environment or
shared model cache was removed. Accepted venv remains available.

## Final Verification Addendum

Verified the submission workspace from `28669fb` with the narrow changes in
`src/ui/app.py`. No provider calls, installations, model downloads, commits,
pushes, or delegation were performed for this addendum. The two live-provider
analyses above remain the only live-provider validation. New results use
isolated synthetic ASR/provider fixtures and the existing intake, transcription
cache, redaction, graph, SQLite storage, rendering, and export pipeline.

### Red Regression and Repair

`scripts/verify_submission_browser.py --layout-only` failed on the unchanged
source. Retained evidence:
`.scratch/submission-ready/evidence/04-final-red-layout/04-final-results.json`.
At 390x844, History summary and QA were each 131px wide at x=56 and x=203,
with the same y=835.125. The measured out-of-bounds button was specifically
`Observability`, x=295.015625, right=411.984375. DOM inspection identified
this as Gradio's `aria-hidden` tab-measurement clone, not the visible navigation
button. Document width itself was 390px. This distinction corrects the original
diagnosis; it is not evidence of a visible navigation button protruding.

The repair wraps each History Markdown in a Gradio Column, matching Analyze,
and anchors the hidden measurement container to the viewport. No content,
validation, or visual design was replaced. The browser regression asserts
actual bounds and section positions, not CSS source text.

### Fresh Browser Acceptance

Command, using the existing Playwright/pypdf runtime and .venv server:

```text
/opt/anaconda3/bin/python scripts/verify_submission_browser.py --output .scratch/submission-ready/evidence/04-final-current
```

The output directory must be new; the runner never overwrites prior evidence.
All new screenshots and manifests are synthetic-fixture evidence, not model
accuracy, policy validity, or new live-provider validation.

| Check | Result |
| --- | --- |
| Invalid MP3 | Actual Analyze click produces application rejection, "Unsupported audio format"; no traceback or stored call. Validation remains enabled. |
| Recovery | Reload, upload a valid WAV, and Analyze completes through the real controls. This proves recovery after reload, not automatic decoder reset. |
| Redaction/exports | Known synthetic phone/email/SSN/card values absent from displayed transcript and downloaded PDF/JSON; redaction placeholders asserted, PDF and nested JSON full IDs agree. |
| Cache | Repeat completes with 2 stored calls and 1 transcription-cache row; `cache_hit=True` diagnostic checked in private unbuffered server log. |
| History | Stored transcript is redacted and results reopen with database counts unchanged. |
| Metrics | 3 outcomes: 2 completed, 1 rejected, success 67%, completed average 4.00, review/flags 0, 31 audit events. All eight rendered values asserted. |
| Newest 20 | 25 timestamped synthetic audit fixtures seeded separately. Scroll the labeled virtualized audit component and assert indices 0..19 are fixture-024..fixture-005 in order. Hidden sizing tbody is not counted. |
| Desktop geometry | 1440x1000, History panels 526px each, x=186 and x=728, equal y; two columns retained. |
| Mobile geometry | 390x844, History panels 278px each at x=56; second starts below first. All analysis/history/observability/failure captures have matching document width and no out-of-bounds controls. |

Review screenshots in `.scratch/submission-ready/evidence/04-final-current/`:
`04-final-{analysis,history,observability,failure}-{desktop,mobile}.png`.
`04-final-results.json` contains actual geometry, ordered audit identifiers,
runtime component discovery, fixture provenance, and microphone result.
Screenshots were visually inspected for readability and section positioning.
The audit viewport is scrolled into view and a painted row is asserted before
each Observability capture, including after mobile resize.
Mobile tables retain native horizontal scrolling; browser emulation does not
establish physical phone compatibility.

### Microphone Blocker

Chromium launched without fake-device flags. Device enumeration found one audio
input. A real `getUserMedia({audio:true})` attempt returned
`NotSupportedError: Not supported` at the getUserMedia stage, before recording.
The runner requests a local two-second MediaRecorder capture only if access
succeeds, stops tracks afterward, and never uploads microphone audio for
analysis. No physical capture is claimed. Existing tuple ingestion coverage
does not resolve this blocker. Physical recording remains an operator/device
acceptance item; software changes can be reviewed independently.

### Source Verification and Limits

```text
.venv/bin/python -m pytest -q tests/unit/test_milestone6_ui.py tests/integration/test_reviewer_journeys.py
20 passed
.venv/bin/python -m pytest -q
363 passed, 4 warnings
.venv/bin/ruff check .
All checks passed!
.venv/bin/ruff format --check .
96 files already formatted
git diff --check
passed
```

Warnings concern existing audio-reader fallback/deprecations. No tests were
removed or disabled. Browser dependencies were already installed in the
separate runner runtime; no project dependency was added. The mechanical UI
detector reported no findings. Earlier diagnostic attempts are preserved under
other `04-final-*` directories and must not be mistaken for final acceptance.
Private SQLite, generated raw fixture artifacts, and diagnostics remain in
task-owned temporary directories; only sanitized evidence is referenced here.
Compatibility risk: the measurement-container selector depends on the installed
Gradio DOM. Rerun browser geometry acceptance after a Gradio upgrade.

## Weighted-Score Acceptance Repair

Review identified a coverage gap in `scripts/verify_submission_browser.py`:
the equal 4/5 fixture could not distinguish weighted scoring from an arithmetic
mean, and export acceptance checked redaction and full IDs without asserting
the score in all three surfaces. Production scoring code was not defective
and was not changed in this repair.

The browser fixture now supplies professionalism 4, empathy 2,
problem_resolution 5, compliance 3, and communication_clarity 4. The independent
worked-example expectation is **3.70**, distinct from arithmetic mean **3.60**
and the deliberately incorrect provider overall **5.00**. Expected values are
literals from the worked example; assertions do not import or recalculate with
the production weight mapping.

Red was executed before restoring the production scorer. With the inherited
fixture's graph-level QA mock returning the unequal scores and wrong overall,
the new browser assertion failed with:

```text
AssertionError: {'expected': 3.7, 'arithmetic_mean': 3.6,
'provider_overall': 5.0, 'observed': {'json': 5.0, 'pdf': 5.0, 'ui': 5.0}}
```

Red evidence is preserved in
`.scratch/submission-ready/evidence/04-final-score-repair-red/`.

For green, fixture setup restores the real
`src.agents.qa_scoring.score_qa` as `nodes.score_qa` after loading the existing
analysis fixture. Only `qa_scoring.get_llm` is stubbed: structured invocation
returns a fresh response with those unequal dimensions and overall 5.00 on
every call. The real scorer validates dimensions, replaces the provider call
ID, and recomputes the weighted total. No provider API is called.

The browser downloads JSON and PDF through Gradio controls, validates the exact
dimension scores in JSON, extracts the overall score from the PDF text and
visible QA UI, and asserts **JSON 3.70 / PDF 3.70 / UI 3.70**. Observability's
completed average must also be **3.70**. Existing redaction/full-ID assertions,
repeat/cache/history checks, newest-20 audit verification, all eight viewport
geometry captures, and the honest microphone attempt remain enabled.

Executed checks:

```text
/opt/anaconda3/bin/python scripts/verify_submission_browser.py --output .scratch/submission-ready/evidence/04-final-score-repair-red
FAIL as expected: JSON/PDF/UI 5.00 versus required 3.70
/opt/anaconda3/bin/python scripts/verify_submission_browser.py --output .scratch/submission-ready/evidence/04-final-score-repair-green
PASS: JSON/PDF/UI 3.70; eight geometry checks passed; newest 20 audits passed
.venv/bin/python -m pytest -q tests/unit/test_milestone6_ui.py tests/integration/test_reviewer_journeys.py
20 passed in 3.29s
.venv/bin/python -m pytest -q
365 passed, 4 warnings in 15.52s
.venv/bin/ruff check .
All checks passed!
.venv/bin/ruff format --check .
98 files already formatted
```

Final fixture screenshots, visually reviewed, are in
`.scratch/submission-ready/evidence/04-final-score-repair-green/`:
`04-final-analysis-desktop.png` and `04-final-analysis-mobile.png` show the
unequal scorecard and 3.70 overall. History, Observability, and failure captures
are retained alongside them. `04-final-results.json` records observed scores,
fixture provenance, metrics, cache-hit evidence, audit order, and geometry.
These are synthetic acceptance results; the prior two live-provider analyses
remain separate and unchanged.

Software repair is green. Ticket 04 is not fully accepted: the latest physical
microphone attempt again enumerated one input but failed at `getUserMedia`
with `NotSupportedError: Not supported`. No capture or hardware pass is claimed.
Only the browser runner and this report were edited in this repair round;
other work and prior evidence were preserved. No commits, pushes, installs,
delegation, production scorer edits, or additional provider calls occurred.
