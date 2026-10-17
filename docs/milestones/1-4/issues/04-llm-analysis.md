# 04: Milestone 4 — LLM analysis and formatting

**What to build:** Redacted transcripts yield structured summaries and grounded QA with deterministic weighted scores, configurable providers, and complete readable output.

**Blocked by:** None. Final integration and regression checks passed.

**Status:** verified — see completion.md for scope and documented differences

**Ownership:** Provider factory, summary/QA agents, prompts, formatters, and associated tests. Request shared model/config/dependency changes from Milestone 2/1 owners.

- [x] Verify all three provider adapters, environment selection, model defaults or documented supported replacements, and timeout propagation.
- [x] Verify structured summary output, complete ordered timestamped transcript formatting, call-ID override, retry recovery, exact attempt limit, capped exponential backoff, and terminal typed errors.
- [x] Verify QA receives the actual summary and transcript, preserves identity, validates dimensions, and always recomputes the five specified weights; test all-fives/model-three and mixed scores.
- [x] Inspect actual outgoing prompts for baseline-three philosophy, concrete 1–5 rubrics for all dimensions, timestamp evidence, genuine compliance violations, and efficient short calls.
- [x] Verify QA retries and typed exhausted failure without real sleeps in deterministic tests.
- [x] Verify timestamp boundaries and all summary/QA formatter sections, empty collections, severity indicators, and exact no-compliance message.
- [x] Run focused mocked tests; coordinate one configured-provider smoke test with the parent without exposing sensitive input or claiming untested providers work live.

**Execution rules:** You are not alone in the codebase. Do not revert others’ changes. Verify existing behavior before editing, fix demonstrated gaps, reuse existing patterns/tests, and leave unrelated work intact. Do not commit, push, or publish issues. Report modified files, commands, outcomes, and unresolved requirements.

**Parent integration gate:** Exercise intake → transcription → injection detection/redaction → summary → QA through a test harness, prove no LLM invocation for injection-positive input and no known PII in outgoing requests, preserve IDs and stop dependent work on errors. Run the full regression suite and produce the official Milestones 1–4 acceptance matrix. Production LangGraph, reports, and final UI remain outside scope.

## Implementation evidence

- Verified 23 focused tests: `python -m pytest tests/unit/test_llm_analysis_contracts.py tests/unit/test_summarization.py tests/unit/test_summarization_behavior.py tests/unit/test_qa_scoring.py tests/unit/test_milestone4_formatters.py -q`.
- Factory honors environment selection and model override; summary now propagates configured model. SDK retries disabled so the agent owns the exact bounded attempt count.
- QA rejects duplicate/missing/unknown dimensions before calculating the rounded weighted score. Outgoing prompt contains all five 1–5 rubrics, baseline-three scoring, timestamp coaching, real compliance guidance and short-call fairness.
- Live testing exposed unconstrained dimension strings; coordinated the canonical Literal schema fix with the state owner and retained a runtime duplicate guard.
- Real OpenAI, Gemini and Groq adapters construct offline using synthetic credentials. Live verification is only for the configured OpenAI provider, never implied for Gemini/Groq.
- Specification exception: Google shut down `gemini-2.0-flash` on June 1, 2026; factory uses its documented replacement `gemini-3.6-flash`. Official source: https://ai.google.dev/gemini-api/docs/deprecations (checked September 27, 2026). Explicit `LLM_MODEL` overrides remain supported.
- Live smoke input is synthetic store-hours dialogue. Reproducible opt-in script: `PYTHONPATH=. .venv/bin/python docs/milestones/1-4/live_llm_smoke.py`; sanitized outcome is recorded in `live-llm-evidence.json`. Initial sandbox connection failed; elevated requests reached OpenAI and identified the schema defect above.

- Final elevated OpenAI smoke passed: typed summary, resolved outcome, five valid QA dimensions, call IDs preserved, weighted score recomputation asserted (3.25). Evidence: `docs/milestones/1-4/live-llm-evidence.json`.

**Final parent verification:** 303 tests passed in both existing and clean environments; five cross-milestone harness tests passed. See ../completion.md.
