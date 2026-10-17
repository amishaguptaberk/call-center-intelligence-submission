# Requirement Coverage

Reconciled 2026-10-16 against `1-4/spec.txt` (all six milestone self-checks)
and the local Problem Statement, Requirements & Evaluation Guide, read using
`.scratch/read_criteria.py`. No reference solution was consulted.

Evidence labels: **T** = implemented and exercised by the current automated suite;
**S** = source/document artifact exists, operational behavior not established;
**P** = historical live evidence only (`VERIFICATION.md` or `1-4/completion.md`);
**U** = unverified; **D** = compatibility difference described below.
T does not imply live provider, hardware, browser, deployment, or security certification.
Test paths below are relative to `tests/`; source paths are repository-relative.

## All Milestone Self-Checks

48 checks: M1 7, M2 8, M3 9, M4 8, M5 8, M6 8. Each numbered row
corresponds to one check in the guide, in its original order.

| ID | Requirement | Source evidence | Test / other evidence | State |
| --- | --- | --- | --- | --- |
| M1.1 | WAV magic-byte detection | `src/utils/audio.py` | `unit/test_audio.py::test_detection` | T |
| M1.2 | MP3 sync-byte detection | `src/utils/audio.py` | `unit/test_audio.py::test_detection` | T |
| M1.3 | Empty input rejected | `src/utils/audio.py` | `unit/test_audio.py::test_validation_boundaries_and_filename_independence` | T |
| M1.4 | 52,428,801-byte input rejected | `src/utils/audio.py` | same boundary test | T |
| M1.5 | Five-second WAV properties | `src/utils/audio.py` | `unit/test_audio.py::test_wav_properties` | T |
| M1.6 | Environment config loads | `src/utils/config.py` | `unit/test_config.py` | T |
| M1.7 | Audio utility suite passes | `src/utils/audio.py` | `unit/test_audio.py` in full suite | T |
| M2.1 | Valid WAV intake | `src/agents/intake.py` | `unit/test_intake.py::test_valid_wav_preserves_audio_and_extracts_properties` | T |
| M2.2 | Empty intake error | `src/agents/intake.py` | `unit/test_intake.py::test_invalid_input_leaves_no_file` | T |
| M2.3 | Unsupported intake error | `src/agents/intake.py` | same invalid-input test; `unit/test_milestone6_ui.py::test_unsupported_bytes_with_wav_filename_block_analysis` | T |
| M2.4 | Overlong WAV rejected | `src/agents/intake.py` | `unit/test_intake.py::test_overlong_wav_is_rejected` | T |
| M2.5 | Metadata SSN detected | `src/agents/intake.py` | `unit/test_intake.py::test_metadata_pii_is_flagged_by_field` | T |
| M2.6 | Unique call IDs | `src/agents/intake.py` | `unit/test_intake.py::test_repeated_intake_uses_distinct_ids_and_files` | T |
| M2.7 | Invalid confidence rejected | `src/graph/state.py` | `unit/test_state.py::test_invalid_confidence_is_rejected` | T |
| M2.8 | Zero QA dimension score rejected | `src/graph/state.py` | `unit/test_state.py::test_invalid_dimension_score_is_rejected` | T |
| M3.1 | Mocked transcription preserves ID | `src/agents/transcription.py` | `unit/test_transcription.py::test_transcription_options_output_and_distinct_audio` | T |
| M3.2 | Identical audio avoids second inference | `src/agents/transcription.py` | `unit/test_transcription.py::test_identical_audio_transcribed_only_once` | T, P |
| M3.3 | Injection/DAN detected | `src/security/injection_detector.py` | `security/test_prompt_injection.py` | T |
| M3.4 | Clean subscription text accepted | same detector | `security/test_prompt_injection.py` | T |
| M3.5 | SSN placeholder | `src/security/pii_redactor.py` | `security/test_pii_detection.py` | T |
| M3.6 | Phone and email redacted together | same redactor | `security/test_pii_detection.py` | T |
| M3.7 | Clean text unchanged | same redactor | `security/test_pii_detection.py` | T |
| M3.8 | All 22 named injection patterns | same detector | `security/test_prompt_injection.py` parametrization | T |
| M3.9 | Security suite passes | `src/security/` | `security/` in full suite | T |
| M4.1 | OpenAI adapter construction | `src/utils/llm_factory.py` | `unit/test_llm_analysis_contracts.py::test_real_provider_adapter_constructs_without_network` | T, P |
| M4.2 | Gemini adapter construction | same factory | same parametrized adapter test; live calls outstanding | T, U, D |
| M4.3 | Groq adapter construction | same factory | same parametrized adapter test; live calls outstanding | T, U |
| M4.4 | Structured summary preserves ID | `src/agents/summarization.py` | `unit/test_summarization.py`, `unit/test_llm_analysis_contracts.py` | T, P |
| M4.5 | Three failures exhaust summary retries | same agent | `unit/test_llm_analysis_contracts.py::test_analysis_contracts_and_backoff` | T |
| M4.6 | Five scores of 5 override overall 3 to 5 | `src/agents/qa_scoring.py` | `unit/test_llm_analysis_contracts.py::test_analysis_contracts_and_backoff` | T |
| M4.7 | Timestamp zero-padding | `src/utils/formatters.py` | `unit/test_milestone4_formatters.py::test_secs_to_mmss_uses_flooring_and_zero_padding` | T |
| M4.8 | No-compliance empty message | same formatters | `unit/test_llm_analysis_contracts.py::test_formatter_required_empty_case_and_boundaries` | T |
| M5.1 | Assemble report and propagate ID | `src/services/report_generator.py` | `unit/test_report_generator.py::test_report_outputs_json_and_pdf` | T |
| M5.2 | PDF signature | same report service | same report test; reviewer journey | T, P |
| M5.3 | Serialized JSON has call ID and summary | same report service | same report test | T, P |
| M5.4 | Persist and retrieve report | `src/database/repository.py` | `unit/test_graph_workflow_milestone5.py::test_compiled_workflow_persists_report_and_audit_events` | T |
| M5.5 | Valid/invalid intake routing | `src/graph/workflow.py::route_after_intake` | `unit/test_graph_workflow_milestone5.py` valid/invalid workflow tests | T |
| M5.6 | Critical/normal QA routing | `src/graph/workflow.py::route_after_qa` | `unit/test_graph_workflow_milestone5.py` completed/flagged workflow tests | T |
| M5.7 | Compile workflow | `src/graph/workflow.py` | `unit/test_graph_workflow_milestone5.py` | T |
| M5.8 | Invoke mocked complete workflow | same workflow | `unit/test_graph_workflow_milestone5.py::test_compiled_workflow_persists_report_and_audit_events` | T |
| M6.1 | Entrypoint/browser startup on 7860 | `app.py`, `src/ui/app.py` | app construction tested; historical browser walkthrough in `VERIFICATION.md`; no new startup | T, P |
| M6.2 | Sample 01 transcript, summary, QA | UI and pipeline service | historical live Sample 01 evidence in `VERIFICATION.md`; mocked reviewer journey current | T, P |
| M6.3 | Unsupported recording safe error | intake and UI service boundary | `unit/test_milestone6_ui.py` unsupported-byte tests | T |
| M6.4 | Dashboard counts after processing | `src/services/observability.py` | `integration/test_reviewer_journeys.py` completed/review/failure scenarios | T, P |
| M6.5 | Docker build and serve | `Dockerfile`, `compose.yaml` | artifact test only; historical Docker timeout; build/run outstanding | S, U |
| M6.6 | Commented environment template | `.env.example` | template present; no deployment/configuration completeness certification | S |
| M6.7 | README setup/architecture/run/tests/GPU | `README.md` | sections present; fresh walkthrough outstanding | S, U |
| M6.8 | At least 100 passing tests | `tests/unit`, `tests/integration`, `tests/security` | full suite command below (same collection as `pytest tests/ -v`) | T |

## Final Guide Coverage

These rows cover sections 4-5 technical requirements, all six section 6 journeys,
sections 7-8 stack/deliverables, all seven section 9 grading criteria, and the
section 10-11 pitfalls/submission rules. Business-volume and compliance claims in
sections 1-3 are motivation, not measured throughput or legal guarantees.

| Guide requirement / criterion | Implementation and evidence | State / qualification |
| --- | --- | --- |
| Architecture 20%; sections 4, 5.1: seven stages, typed state, conditional edges, failure isolation, invoke | `src/graph/{state,nodes,workflow}.py`; `unit/test_graph_workflow_milestone5.py`, `unit/test_graph_pii_boundary.py` | T; safe failure retains earlier state; summary and QA remain sequential |
| Audio/transcription 15%; 5.2-5.3: four content types, size/duration, properties, metadata scan, temp audio | `src/utils/audio.py`, `src/agents/intake.py`; audio/intake tests including compressed files and duration-before-size precedence | T; UI suffix gate removed; valid `call.bin` and spoofed `.wav` regressions |
| Startup singleton, CUDA/CPU fallback, greedy/VAD/no conditioning, cleaning, confidence, heuristic labels | `app.py`, `src/agents/transcription.py`, diarization modules; transcription and diarization test files | T, P for CPU Whisper; U for real GPU and acoustic accuracy; ambiguous labels retained (D) |
| SHA-256 persistent cache, same audio skips model, current call ID | transcription agent; `unit/test_transcription.py` cache/restart/backend-isolation tests | T, P; no throughput SLA measured |
| Security 15%; 5.4: 22 patterns block before inference and return names | injection detector, graph nodes; `security/test_prompt_injection.py`, reviewer journey injection test | T; regex detection is bounded, not complete adversarial protection |
| SSN/card/email/phone, right-to-left replacement, full text and segments before both models | PII redactor, graph nodes; `security/test_pii_detection.py`, `security/test_split_pii.py`, `unit/test_graph_pii_boundary.py`, reviewer journey | T; pattern-based, no anonymization guarantee; local raw cache retention remains a limitation |
| Append-only timestamped started/completed/failed/flagged audit events | audit logger, database triggers, graph; `unit/test_audit.py`, `unit/test_graph_event_logging.py`, reviewer journey mutation tests | T; SQLite UPDATE/DELETE rejected; not a privileged filesystem tamper guarantee |
| LLM integration 20%; 5.5: summary fields, Pydantic structure, retries/backoff, summary passed to QA | analysis agents, state models; summary/QA/analysis-contract tests and `integration/test_milestones_1_to_4.py` | T, P OpenAI only; model factual grounding is prompted, not guaranteed |
| Five dimensions and weights 15/20/30/20/15, evidence timestamps, severity, deterministic overall | `src/agents/qa_scoring.py`; QA/analysis-contract tests, `unit/test_milestone4_formatters.py` | T; model quality/compliance judgments still require human review |
| OpenAI, Gemini, Groq selected through env; model/timeout overrides | config and LLM factory; `unit/test_config.py`, `unit/test_llm_analysis_contracts.py` | T; P OpenAI; U live Gemini/Groq; Gemini default D |
| Reports/persistence 10%; 5.6: CallReport, PDF/JSON, SQLite records/cache/audit, pooled sessions | report service, `src/database/`; report/workflow/transcription tests; reviewer restart/history journey | T, P exports; legacy upgrade covered; stock SQLite encryption not established |
| 5.7 observability: all statuses, success %, completed average, compliance total, latest 20 events, tracing link | observability service; reviewer journeys, `unit/test_graph_event_logging.py`, UI refresh wiring | T, P dashboard; U live LangSmith trace delivery |
| 5.8 UI: upload/microphone, optional metadata, analyze, labeled transcript, summary/QA, downloads, processing warning | `src/ui/app.py`, pipeline service; `unit/test_milestone6_ui.py`, `unit/test_submission.py`, reviewer journeys | T, P browser uploads/downloads; U physical microphone; filepath and three tabs D |
| Testing 10%; 5.9: 100+ tests, independent unit/integration/security, mocks, multiple PII formats, all patterns | `tests/` suites and shared fixtures; current full run below | T; no new live provider requests |
| Code/deployment 10%; 5.10: layers, environment config, Docker, README, Make targets, GPU fallback | `src/`, config, `Dockerfile`, `.env.example`, README, Makefile; config/submission/space tests | T for tested config/adapters; S artifacts; U Docker build/run and GPU |
| Journey 1: valid call yields complete downloadable analysis | `integration/test_reviewer_journeys.py::test_upload_to_redacted_downloads_history_and_restart` | T with generated WAV and mocked inference; P live MP3 |
| Journey 2: spoken credit card redacted before either analysis model | same reviewer journey; `security/test_split_pii.py` | T; P historical browser redaction |
| Journey 3: compliance flag and critical supervisor outcome | `unit/test_qa_scoring.py`, flagged workflow/reviewer tests | T mocked classification/routing; U real violation classification accuracy |
| Journey 4: injection blocks analysis with matched names | reviewer injection journey, security suite | T |
| Journey 5: unsupported format / spoofed `.wav` safe rejection | UI regressions and intake tests | T |
| Journey 6: auto/manual dashboard refresh and metrics | UI wiring, app construction, reviewer metric tests | T; P browser dashboard; no new interaction walkthrough |
| Stack: Python, LangGraph, Whisper, three adapters, mutagen, Pydantic, SQLAlchemy, Gradio, ReportLab, optional LangSmith | `requirements.txt`, `pyproject.toml`; installed-dependency check; relevant component tests | T installed environment; D Gradio 6; U fresh resolution and provider availability |
| Entrypoint <50 lines, modular source, tests and development artifacts | `app.py`, `src/`, `tests/`, `Makefile`, `.pre-commit-config.yaml`, `.github/workflows/checks.yml` | S artifacts; T local lint/format/tests; U remote CI and secret-scan execution |
| Reproducible dependencies and Python target in pyproject | pinned direct requirements; project metadata `>=3.11,<3.12`; `unit/test_submission.py::test_project_metadata_declares_python_311_support` | T on 3.11.15 only; narrow supported minor matches Docker/CI; no transitive lock or fresh install claim |
| Pitfalls: no raw PII to models, cache, bytes validation, weighted score, isolation, retries, startup reuse, rolling cleanup | tests referenced above plus `integration/test_reviewer_journeys.py::test_retention_cap_is_configurable` | T; retention applies to temp exports, not automatic raw-cache expiry |
| Submission: public accessible repository, secrets/runtime data excluded, reviewer setup | `.gitignore`, README, environment template | S; U publication, permissions, current archive freshness and clean-clone setup; not published by this ticket |

## Compatibility Decisions

- **Gradio 6 rather than 5:** retain the existing installed dependency set and its
  launch-time theme/CSS API. App construction is tested. Downgrading would require
  separate compatibility work and would not repair the confirmed intake defect.
- **Filepath audio rather than numpy UI mode:** preserves original uploaded bytes
  for content validation. The service also accepts numpy microphone tuples, covered
  by `test_microphone_tuple_completes_with_blank_metadata`. A physical microphone
  recording and browser preprocessing of misleading suffixes remain unverified.
- **Three tabs rather than two:** follows the final overview's explicit history
  requirement while retaining Analyze Call and Observability from section 5.8.
- **Gemini default differs from Gemini 2.0 Flash:** retained existing configuration;
  historical completion notes describe the change but are not current availability
  evidence. Live verification of the configured Gemini and Groq models is outstanding.
  No provider/model availability or pricing claim is made here.
- **API names and speaker uncertainty:** equivalent report/build/workflow APIs are
  tested under their actual names rather than guide example names. Heuristic output
  may include Ambiguous in addition to Agent/Customer; speaker accuracy is not assured.

## Confirmed Repairs And Verification

The UI previously rejected a supported recording solely because its filename did
not end in an allowed suffix. `_run` now delegates directly to `process_call` and
the existing intake byte validator. No duplicate parser or layout change was added.
The real-WAV `call.bin` test failed at the old suffix gate before the fix; unsupported
bytes with a `.wav` suffix remain blocked before summarization/QA. Project metadata
was absent; the metadata regression failed with `KeyError: 'project'` before adding
the supported Python 3.11 declaration. No documentation-mirroring tests were added.

Executed checks on Python 3.11.15 in the existing virtual environment:

| Command | Outcome |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/unit/test_milestone6_ui.py tests/unit/test_submission.py` | Pass: 14 tests |
| `.venv/bin/python -m pytest -q` | Pass: 361 tests, four third-party audio-reader warnings |
| `.venv/bin/ruff check .` | Pass; initial fixture-import lint failure corrected without disabling checks |
| `.venv/bin/ruff format --check .` | Pass: 91 files already formatted |
| `.venv/bin/python -m pip check` | Pass: no broken requirements found |
| `git diff --check` | Pass |

Final scoped diff review: six owned paths only; no dependency additions, visual
changes, credentials, runtime artifacts, or unrelated implementation edits.
Concurrent publication-review and sample README edits belong to another ticket
and were preserved. The initial unsupported-file unit test needed an isolated
database because intake audits rejected inputs; it now uses the existing journey
fixture and checks the real validation result rather than the old suffix gate.

Docker, a fresh installation, physical microphone, GPU, remote CI, live tracing,
provider-specific live calls, publication and access permissions were not verified
by this ticket. Historical evidence is explicitly P and does not upgrade those
checks to current passes. No commit or publication is part of this work.
