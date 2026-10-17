# Evaluation framework

This directory defines **data contracts and annotations** for reproducible speaker-attribution evaluation. Sample_01 overlap scoring is implemented in `scripts/eval_sample01_diarization.py`; hybrid comparison and cache export are in `scripts/eval_hybrid_vs_heuristic.py`. See the root README for commands and current limitations.

## What this is / is not

| Claim | Status |
|-------|--------|
| Operational success (pipeline ok / runtime / errors) | You will implement from prediction runs |
| Content-anchor accuracy | Requires annotated intervals with `automated_content_inference` or confirmed content tags |
| Transcript-role (migrated) labels | Draft only for `sample_01`; **not audio-verified** |
| Audio-verified speaker attribution | Requires listen-pass worksheets → updated annotations with `audio_verified: true` |
| DER | **Do not compute** until a listen-pass reference timeline exists |

Never treat unannotated time as correct. Never claim acoustic GT without a listen-pass.

## Layout

```text
evaluation/
  schemas/
    annotation.schema.json
    prediction_run.schema.json
  annotations/recordings/sample_01/
    annotation.v1.draft.json     # reference transcript-role migration; NOT audio-verified
    annotation.v2.json           # listen-pass on student heuristics_v1 timestamps
  worksheets/
    sample_01_listen_pass.json   # completed listen-pass (no transcripts)
    sample_01_listen_pass.csv
  baselines/heuristics_v1/
    sample_01.prediction.json    # frozen predictions only (no verified labels)
  historical/
    non_comparable_sample01.json # frozen 15/37 and 20/30
  imports/ref_eval_2026-09-20/   # sanitized reference artifacts + SOURCE.md
  runs/                          # gitignored prediction outputs (local)
```

## Privacy

- Recordings live under `data/samples/` (gitignored).
- Raw transcripts and full prediction text belong only under `evaluation/runs/` or `diagnostics/` (gitignored).
- Committed worksheets and annotations **omit transcript text**.
- Shareable reports must not include raw ASR or PII.

## Sample_01 annotations

| File | Role |
|------|------|
| `annotation.v1.draft.json` | Historical: reference ASR transcript-role migration; **not** audio-verified; keep for provenance |
| `annotation.v2.json` | Canonical listen-pass on **heuristics_v1** student timestamps; 35 clear + 1 mixed (#7) |

`annotation.v2.json` notes:

- Provenance: `manual_audio_verification` / `listen_pass` / `audio_verified: true`.
- Mixed interval `s01-student-007`: Agent then Customer; **no invented internal split**; tags include `pending_internal_boundary`.
- Boundaries follow heuristics_v1 ASR cuts (not independent RTTM).

## Listen-pass worksheet

`worksheets/sample_01_listen_pass.*` is **completed** for sample_01:

- Predictions / rules / times frozen from heuristics_v1.
- `verified_speaker` filled for 35 single-speaker rows; row 7 marked mixed with pending internal boundary.
- No transcript text stored.

## Baseline predictions

`baselines/heuristics_v1/sample_01.prediction.json` stores the original run only (labels, times, rule traces). Verified annotations are separate.

## Historical results (non-comparable)

| ID | Result | Why not comparable |
|----|--------|--------------------|
| `ref_index_manual_sample01_15_of_37` | 15/37 | Index-aligned to **reference** ASR segments |
| `ad_hoc_student_vs_ref_gt_tol_0.6_20_of_30` | 20/30 | Different denominator; 7 unmatched intervals dropped; ad-hoc 0.6s tolerance |

Canonical future scores must use the **same** time-interval annotation for every system.

## Metric families (for when you implement scoring)

1. **Operational** — `operational.ok`, runtime, errors.
2. **Content-anchor** — clear intervals whose provenance is automated/content confirmed.
3. **Audio-verified attribution** — clear intervals with `audio_verified: true` only.
4. **DER** — `NOT_COMPUTED` until a suitable listen-pass timeline exists.

Score by **time overlap** against annotated intervals, not by segment index.

## Historical scope

The original scaffolding pass only defined contracts and annotations. The scripts
listed above were added later; the original metric cautions still apply.
