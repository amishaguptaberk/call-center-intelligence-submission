# Optional experiments

`compare_role_mapping_sample01.py` compares acoustic clusters with production
role mapping on sample_01. Its annotation-based best permutation is an evaluation
reference, not a production role classifier. Existing local edits were preserved.

Run from the repository root:

```sh
.venv/bin/python scripts/experiments/compare_role_mapping_sample01.py
```

This performs model inference and writes the existing A/B report. It is not
needed for caching or transcript-cleaning implementation.
