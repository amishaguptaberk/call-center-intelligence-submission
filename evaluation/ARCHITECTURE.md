# Acoustic transcription (consolidated)

Production modules:

- `src/agents/transcription.py` — Milestone 3 Whisper entry + `SpeakerDiarizer` + orchestration
- `src/agents/acoustic.py` — Community-1 (bounded timeout), align, group, role map

```bash
DIARIZATION_BACKEND=heuristic   # Milestone 3 / baseline
DIARIZATION_BACKEND=acoustic    # Community-1 only (raises on failure)
DIARIZATION_BACKEND=hybrid      # acoustic first; heuristic fallback (default)
```

Public acoustic entry: `run_acoustic_diarization(audio_path, words, asr_spans, timeout_sec=...)`.

Accept terms: https://huggingface.co/pyannote/speaker-diarization-community-1

Ambiguous segments are returned as `speaker="Ambiguous"` with low confidence (public schema limitation).
