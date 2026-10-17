"""Slice 1 local debug helpers: intake → transcription → inspectable view.

Developer-only. Does not log raw transcript text.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.agents.acoustic import clear_acoustic_cancel, request_acoustic_cancel
from src.agents.call_bounds import (
    call_bounds_notice,
    call_bounds_summary,
    write_call_audio_clip,
)
from src.agents.intake import run_intake
from src.agents.transcription import (
    get_last_transcription_diagnostics,
    run_transcription,
)
from src.agents.wait_events import (
    compute_wait_events,
    for_display,
    wait_summary_line,
)
from src.graph.state import AudioInput, TranscriptionResult, TranscriptionSegment

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLES_DIR = _REPO_ROOT / "data" / "samples" / "samples"
DEFAULT_FLAGS_DIR = _REPO_ROOT / "diagnostics" / "flags"

SEGMENT_HEADERS = ["#", "flag", "start", "end", "speaker", "confidence", "text"]


@dataclass(frozen=True)
class DebugTranscriptionView:
    status: str
    ok: bool
    audio_path: str | None = None
    segment_rows: list[list[str]] = field(default_factory=list)
    transcript_text: str = ""


def list_sample_names(samples_dir: Path | None = None) -> list[str]:
    """Return sorted sample stem names (sample_01 … sample_10)."""
    root = samples_dir or DEFAULT_SAMPLES_DIR
    if not root.is_dir():
        return []
    names = sorted(
        p.stem
        for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a", ".flac"}
    )
    return names


def resolve_sample_path(
    sample_name: str | None,
    samples_dir: Path | None = None,
) -> str | None:
    if not sample_name:
        return None
    root = samples_dir or DEFAULT_SAMPLES_DIR
    for suffix in (".mp3", ".wav", ".m4a", ".flac"):
        path = root / f"{sample_name}{suffix}"
        if path.is_file():
            return str(path)
    return None


def format_timestamp(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:05.2f}"


def format_segment_line(segment: TranscriptionSegment) -> str:
    return (
        f"[{format_timestamp(segment.start_time)}-{format_timestamp(segment.end_time)}] "
        f"{segment.speaker} (conf={segment.confidence:.2f}): {segment.text.strip()}"
    )


def segments_as_rows(
    result: TranscriptionResult,
    flagged_indices: set[int] | None = None,
) -> list[list]:
    flagged = flagged_indices or set()
    return [
        [
            i,
            i in flagged,
            format_timestamp(s.start_time),
            format_timestamp(s.end_time),
            s.speaker,
            f"{s.confidence:.2f}",
            s.text.strip(),
        ]
        for i, s in enumerate(result.segments)
    ]


def format_transcript_text(
    result: TranscriptionResult,
    *,
    include_holds: bool = True,
) -> str:
    display, bounds = for_display(result.segments)
    if not include_holds:
        display = [s for s in display if s.speaker != "Hold"]
    events = compute_wait_events(display) if include_holds else []
    body = "\n".join(format_segment_line(s) for s in display)
    header = call_bounds_summary(bounds)
    notice = call_bounds_notice(bounds)
    if include_holds:
        header = f"{header}\n{wait_summary_line(events)}"
    top = f"{header}\n{notice}"
    return f"{top}\n{body}" if body else top


def toggle_flag_at(rows: list[list], row_index: int) -> list[list]:
    """Flip the flag checkbox for one row (tap-to-flag)."""
    if row_index < 0 or row_index >= len(rows):
        return rows
    out = [list(r) for r in rows]
    out[row_index][1] = not bool(out[row_index][1])
    return out


def count_flagged(rows: list[list]) -> int:
    return sum(1 for r in rows if len(r) > 1 and bool(r[1]))


def flags_path(
    sample_or_stem: str,
    backend: str,
    flags_dir: Path | None = None,
) -> Path:
    root = flags_dir or DEFAULT_FLAGS_DIR
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in sample_or_stem)
    return root / f"{safe}__{backend}.json"


def extract_flagged_records(rows: list[list]) -> list[dict]:
    """Persist times/speaker only — no transcript text."""
    records: list[dict] = []
    for row in rows:
        if len(row) < 6 or not bool(row[1]):
            continue
        records.append(
            {
                "row_id": int(row[0]),
                "start": str(row[2]),
                "end": str(row[3]),
                "predicted_speaker": str(row[4]),
                "confidence": str(row[5]),
            }
        )
    return records


def save_flags(
    sample_or_stem: str,
    backend: str,
    rows: list[list],
    flags_dir: Path | None = None,
) -> Path:
    path = flags_path(sample_or_stem, backend, flags_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sample": sample_or_stem,
        "backend": backend,
        "flagged": extract_flagged_records(rows),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_flagged_indices(
    sample_or_stem: str,
    backend: str,
    flags_dir: Path | None = None,
) -> set[int]:
    path = flags_path(sample_or_stem, backend, flags_dir)
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        int(item["row_id"])
        for item in data.get("flagged") or []
        if isinstance(item, dict) and "row_id" in item
    }


def process_uploaded_audio(
    audio_path: str | None,
    *,
    backend: str | None = None,
    sample_name: str | None = None,
) -> DebugTranscriptionView:
    if not audio_path:
        return DebugTranscriptionView(
            status="Upload an audio file to run intake + transcription.",
            ok=False,
        )

    path = Path(audio_path)
    if not path.is_file():
        return DebugTranscriptionView(
            status=f"Audio file not found: {audio_path}",
            ok=False,
        )

    # Local debug default: heuristic. Acoustic/hybrid stay available via UI.
    chosen = (backend or "heuristic").strip().lower()
    if chosen not in {"heuristic", "hybrid", "acoustic"}:
        return DebugTranscriptionView(
            status=f"Unknown backend {chosen!r}; use heuristic, hybrid, or acoustic.",
            ok=False,
            audio_path=str(path),
        )

    clear_acoustic_cancel()
    previous_backend = os.environ.get("DIARIZATION_BACKEND")
    os.environ["DIARIZATION_BACKEND"] = chosen
    t0 = time.perf_counter()
    try:
        audio_input = AudioInput(
            audio_data=path.read_bytes(),
            filename=path.name,
        )
        intake = run_intake(audio_input)
        if not intake.validation_passed:
            return DebugTranscriptionView(
                status=f"Intake failed: {intake.validation_error or 'validation failed'}",
                ok=False,
                audio_path=str(path),
            )

        try:
            result = run_transcription(intake)
        except Exception as exc:  # noqa: BLE001 — surface any agent error in the UI
            elapsed = time.perf_counter() - t0
            return DebugTranscriptionView(
                status=(f"Transcription failed ({chosen}, {elapsed:.1f}s): {exc}"),
                ok=False,
                audio_path=intake.temp_file_path or str(path),
            )

        elapsed = time.perf_counter() - t0
        n = len(result.segments)
        diagnostics = get_last_transcription_diagnostics() or {}
        timing = diagnostics.get("timing_sec") or {}
        label_source = diagnostics.get("label_source") or chosen
        cached = bool(diagnostics.get("cache_hit")) or (
            elapsed < 1.0 and not timing and not diagnostics.get("label_source")
        )
        full_playback = intake.temp_file_path or str(path)
        stem = sample_name or path.stem
        display_segments, bounds = for_display(result.segments)
        display_result = result.model_copy(update={"segments": display_segments})
        prior = load_flagged_indices(stem, chosen)
        rows = segments_as_rows(display_result, prior)
        n_flagged = len(prior)
        waits = compute_wait_events(display_segments)
        wait_bit = wait_summary_line(waits)
        bounds_bit = call_bounds_summary(bounds)
        source_bit = (
            f"label_source={label_source}"
            if label_source == chosen
            else f"requested={chosen} label_source={label_source}"
        )
        playback = full_playback
        if bounds.trimmed and bounds.start_sec is not None and bounds.end_sec is not None:
            try:
                playback = str(
                    write_call_audio_clip(full_playback, bounds.start_sec, bounds.end_sec)
                )
            except Exception:  # noqa: BLE001 — fall back to full file
                playback = full_playback
        return DebugTranscriptionView(
            status=(
                f"OK — {source_bit} — {elapsed:.1f}s"
                f"{' — cache hit' if cached else ''}"
                f" — call_id={result.call_id} — {len(display_segments)} in-call "
                f"row{'s' if len(display_segments) != 1 else ''} "
                f"(raw {n})"
                f" — {bounds_bit} — {wait_bit}"
                + (f" — {n_flagged} prior flag(s) loaded" if n_flagged else "")
            ),
            ok=True,
            audio_path=playback,
            segment_rows=rows,
            transcript_text=format_transcript_text(result),
        )
    finally:
        if previous_backend is None:
            os.environ.pop("DIARIZATION_BACKEND", None)
        else:
            os.environ["DIARIZATION_BACKEND"] = previous_backend


def build_debug_app():
    """Local-only Gradio Blocks. Import gradio only when building the UI."""
    import gradio as gr

    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    sample_names = list_sample_names()

    def _outputs(view: DebugTranscriptionView):
        n_flag = count_flagged(view.segment_rows)
        flag_msg = f"{n_flag} flagged" if view.segment_rows else "Tap a row or check flag"
        return (
            view.status,
            view.audio_path,
            view.segment_rows,
            view.transcript_text,
            flag_msg,
        )

    def _run_path(
        audio_path: str | None,
        backend: str | None,
        sample_name: str | None = None,
    ):
        stem = sample_name or (Path(audio_path).stem if audio_path else None)
        return _outputs(process_uploaded_audio(audio_path, backend=backend, sample_name=stem))

    def _run_sample(sample_name: str | None, backend: str | None):
        path = resolve_sample_path(sample_name)
        if path is None:
            return _outputs(
                DebugTranscriptionView(
                    status=f"Sample not found: {sample_name!r}",
                    ok=False,
                )
            )
        return _run_path(path, backend, sample_name=sample_name)

    def _step_sample(sample_name: str | None, backend: str | None, delta: int):
        if not sample_names:
            return None, *_outputs(
                DebugTranscriptionView(status="No local samples found.", ok=False)
            )
        if sample_name in sample_names:
            idx = sample_names.index(sample_name)
        else:
            idx = 0
        nxt = sample_names[(idx + delta) % len(sample_names)]
        return nxt, *_run_sample(nxt, backend)

    def _on_row_select(rows, evt):
        # Tap any cell in a row → toggle that row's flag.
        if rows is None:
            return [], "0 flagged"
        row_list = rows if isinstance(rows, list) else rows.values.tolist()
        idx = evt.index
        row_i = idx[0] if isinstance(idx, (list, tuple)) else int(idx)
        updated = toggle_flag_at(row_list, row_i)
        return updated, f"{count_flagged(updated)} flagged — Save flags to keep"

    def _on_table_edit(rows):
        if rows is None:
            return "0 flagged"
        row_list = rows if isinstance(rows, list) else rows.values.tolist()
        return f"{count_flagged(row_list)} flagged — Save flags to keep"

    def _save(sample_name, backend, rows, audio_path):
        stem = sample_name or (Path(audio_path).stem if audio_path else "upload")
        be = (backend or "heuristic").strip().lower()
        row_list = (
            [] if rows is None else (rows if isinstance(rows, list) else rows.values.tolist())
        )
        path = save_flags(stem, be, row_list)
        n = count_flagged(row_list)
        return f"Saved {n} flag(s) → {path}"

    def _clear(rows):
        if rows is None:
            return [], "0 flagged"
        row_list = rows if isinstance(rows, list) else rows.values.tolist()
        cleared = [list(r) for r in row_list]
        for r in cleared:
            if len(r) > 1:
                r[1] = False
        return cleared, "0 flagged"

    with gr.Blocks(
        title="M3 transcription debug (local)",
        analytics_enabled=False,
    ) as demo:
        gr.Markdown(
            "## Milestone 3 — local transcription debug (Slice 1)\n"
            "Defaults to **heuristic** (~seconds). Hybrid/acoustic can take up to "
            "~1 min — use **Stop** to cancel. UI shows **in-call only** (prelude/"
            "outro hidden). Tap a row to **flag** bad labels; **Save flags** writes "
            "times/speaker only under `diagnostics/flags/` (no transcript text)."
        )
        sample = gr.Dropdown(
            label="Bundled samples",
            choices=sample_names,
            value=sample_names[0] if sample_names else None,
            interactive=True,
        )
        backend = gr.Dropdown(
            label="Diarization backend",
            choices=["heuristic", "hybrid", "acoustic"],
            value="heuristic",
            interactive=True,
        )
        with gr.Row():
            prev_btn = gr.Button("← Prev")
            run_sample_btn = gr.Button("Run sample", variant="primary")
            next_btn = gr.Button("Next →")
            stop_btn = gr.Button("Stop", variant="stop")
        audio_in = gr.Audio(
            label="Or upload call audio",
            type="filepath",
            sources=["upload"],
        )
        run_upload_btn = gr.Button("Run upload")
        status = gr.Textbox(label="Status", interactive=False)
        audio_out = gr.Audio(label="Playback (in-call clip)", type="filepath", interactive=False)
        table = gr.Dataframe(
            label="Segments — tap a row to flag incorrect",
            headers=SEGMENT_HEADERS,
            datatype=["number", "bool", "str", "str", "str", "str", "str"],
            interactive=True,
            wrap=True,
        )
        with gr.Row():
            flag_status = gr.Textbox(
                label="Flags",
                value="Tap a row or check flag",
                interactive=False,
            )
            save_flags_btn = gr.Button("Save flags", variant="secondary")
            clear_flags_btn = gr.Button("Clear flags")
        text = gr.Textbox(
            label="Transcript (in-call, speaker-labeled)",
            lines=16,
            interactive=False,
        )

        def _request_stop():
            request_acoustic_cancel()
            return "Stop requested — cancelling run / killing acoustic worker if active."

        run_outs = [status, audio_out, table, text, flag_status]
        run_sample_evt = run_sample_btn.click(
            fn=_run_sample,
            inputs=[sample, backend],
            outputs=run_outs,
        )
        prev_evt = prev_btn.click(
            fn=lambda name, be: _step_sample(name, be, -1),
            inputs=[sample, backend],
            outputs=[sample, *run_outs],
        )
        next_evt = next_btn.click(
            fn=lambda name, be: _step_sample(name, be, 1),
            inputs=[sample, backend],
            outputs=[sample, *run_outs],
        )
        run_upload_evt = run_upload_btn.click(
            fn=lambda path, be: _run_path(path, be),
            inputs=[audio_in, backend],
            outputs=run_outs,
        )
        stop_btn.click(
            fn=_request_stop,
            inputs=None,
            outputs=[status],
            cancels=[run_sample_evt, prev_evt, next_evt, run_upload_evt],
        )
        table.select(
            fn=_on_row_select,
            inputs=[table],
            outputs=[table, flag_status],
        )
        table.change(
            fn=_on_table_edit,
            inputs=[table],
            outputs=[flag_status],
        )
        save_flags_btn.click(
            fn=_save,
            inputs=[sample, backend, table, audio_out],
            outputs=[flag_status],
        )
        clear_flags_btn.click(
            fn=_clear,
            inputs=[table],
            outputs=[table, flag_status],
        )
        if sample_names:
            demo.load(
                fn=lambda: resolve_sample_path(sample_names[0]),
                inputs=None,
                outputs=[audio_out],
            )
    return demo


def main() -> None:
    demo = build_debug_app()
    print("Local debug UI → http://127.0.0.1:7860  (use 127.0.0.1, not localhost)")
    demo.queue()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=False,
    )


if __name__ == "__main__":
    main()
