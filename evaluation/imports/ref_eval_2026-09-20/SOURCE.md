# Imported reference evaluation artifacts (2026-09-20)

## Source

- Project: `/Users/amisha.gupta/Desktop/ik-agentic-ai/call-center-ref-eval`
- Package under test: `Call-Center-Intelligence-System-main` (isolated; not copied here)
- Artifacts directory: `call-center-ref-eval/evaluation/artifacts/`

## Files imported here

| File | Contents | Safe to share? |
|------|----------|----------------|
| `predictions_public.json` | Per-file operational status, segment times, speakers, confidence, **redacted** text fingerprints only | Yes |
| `metrics_report.json` | Operational totals, content-anchor scores, sample_01 manual content GT summary | Yes (no raw transcripts) |

## Not imported (keep local / out of this repo)

- `predictions_full.json` (contains raw ASR text / PII)
- `full_diagnostic.log` (contains raw text)
- Reference implementation source

## Ground-truth method (from source scoring script)

1. **Content-role anchors** — automated regexes over ASR text; exclusive Agent/Customer cues only.
2. **sample_01 manual map** — human **transcript review** of reference ASR (`manual_sample01_notes`), index-aligned to that run’s segments; one `?` ambiguous/merged turn.
3. **Not acoustic ground truth** — no listen-pass RTTM; DER was explicitly `NOT_COMPUTED`.

## Historical frozen scores (non-comparable)

See `evaluation/historical/non_comparable_sample01.json`:

- Reference index-aligned manual: **15/37**
- Ad-hoc student time-align (0.6s collar): **20/30**

These use different units and must not be compared as a single leaderboard.
