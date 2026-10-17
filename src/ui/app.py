from __future__ import annotations

import gradio as gr

from src.services.history import history_report, history_rows
from src.services.observability import get_observability_dashboard
from src.services.pipeline import process_call
from src.ui.debug_transcription import list_sample_names, resolve_sample_path

CSS = """
.gradio-container { width:100%!important; min-width:0!important; box-sizing:border-box!important; }
.gradio-container .main, .gradio-container .main > .wrap, .gradio-container .contain { min-width:0!important; max-width:100%!important; box-sizing:border-box!important; }
.gradio-container .main { width:100%!important; }
.ledger { min-width:0!important; max-width:100%!important; overflow:auto!important; }
[role="tablist"] { flex-wrap:wrap!important; }
:root { --canvas:#f6f7f8; --surface:#fff; --ink:#17212b; --muted:#5d6b78; --accent:#245b78; --line:#d7dde2; --soft:#eef2f4; --warning:#9a5b12; }
.gradio-container { --body-text-color:var(--ink)!important; --body-text-color-subdued:var(--muted)!important; --block-label-text-color:var(--ink)!important; --block-info-text-color:var(--muted)!important; --background-fill-primary:var(--canvas)!important; --background-fill-secondary:var(--surface)!important; --block-background-fill:var(--surface)!important; --input-background-fill:var(--surface)!important; --input-border-color:#b8c2ca!important; --input-placeholder-color:#667684!important; --border-color-primary:var(--line)!important; --table-border-color:var(--line)!important; --table-even-background-fill:var(--surface)!important; --table-odd-background-fill:#f8fafb!important; background:var(--canvas)!important; color:var(--ink)!important; max-width:1180px!important; margin:auto!important; padding-inline:24px!important; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif!important; font-size:15px!important; line-height:1.5; overflow-wrap:anywhere; }
.gradio-container .prose { color:var(--ink)!important; font-size:.95rem!important; line-height:1.55!important; }
.gradio-container .prose :is(h1,h2,h3,h4,p,li,strong,em) { color:inherit!important; }
.gradio-container .prose h2 { font-size:1.35rem!important; line-height:1.25!important; margin:1.3rem 0 .45rem!important; letter-spacing:-.015em; }
.gradio-container .prose h3 { font-size:1.05rem!important; line-height:1.35!important; margin:1.1rem 0 .4rem!important; }
.gradio-container [data-testid="block-label"] { background:var(--surface)!important; color:var(--ink)!important; }
.gradio-container [data-testid="block-info"], .gradio-container label span { color:var(--ink)!important; }
.gradio-container .prose code { background:#253746!important; color:#fff!important; }
.masthead { margin:0 -8px 18px; padding:24px 8px 20px; border-bottom:1px solid var(--line); display:grid; grid-template-columns:minmax(0,1fr) minmax(280px,420px); gap:48px; align-items:end; }
.product-mark { display:flex; align-items:center; gap:10px; color:var(--ink); font-size:.82rem; font-weight:650; letter-spacing:.01em; }
.product-mark::before { content:""; width:12px; height:12px; background:var(--accent); border-radius:3px; box-shadow:6px 6px 0 #a9c3d0; }
.masthead h1 { color:var(--ink)!important; font-size:clamp(1.9rem,3vw,2.75rem); font-weight:650; line-height:1.08; letter-spacing:-.035em; margin:24px 0 0; max-width:660px; text-wrap:balance; }
.masthead p { max-width:52ch; margin:0; color:var(--muted)!important; font-size:.95rem; line-height:1.6; }
.panel { border:1px solid var(--line)!important; border-radius:8px!important; background:var(--surface)!important; padding:20px!important; box-shadow:0 1px 2px rgba(23,33,43,.04)!important; }
.processing { border-color:#d8b47b!important; background:#fff9ef!important; }
.result-status { border-top:1px solid var(--line); padding-top:18px; }
.metric-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); border:1px solid var(--line); background:var(--surface); border-radius:8px; overflow:hidden; }
.metric-grid div { padding:18px; border-right:1px solid var(--line); }
.metric-grid div:last-child { border-right:0; }
.metric-grid span { display:block; color:var(--muted)!important; font-size:.8rem; font-weight:600; line-height:1.3; }
.metric-grid strong { display:block; color:var(--ink)!important; font-family:ui-monospace,"SFMono-Regular",monospace; font-size:1.7rem; font-variant-numeric:tabular-nums; line-height:1.1; margin-top:7px; }
[role="tab"] { color:var(--muted)!important; font-size:.92rem!important; font-weight:550!important; }
[role="tab"][aria-selected="true"] { color:var(--ink)!important; }
button { transition:background-color .16s ease,border-color .16s ease,transform .08s ease!important; }
button.primary { min-height:44px!important; background:var(--accent)!important; border-color:var(--accent)!important; font-weight:600!important; }
button.primary:hover { background:#194960!important; border-color:#194960!important; }
button.secondary { background:var(--surface)!important; border:1px solid #b8c2ca!important; color:var(--ink)!important; }
button.secondary:hover { background:var(--soft)!important; }
button:active { transform:translateY(1px); }
button:focus-visible, input:focus-visible, textarea:focus-visible { outline:3px solid #8bb8cf!important; outline-offset:2px!important; }
.footer-note { border-top:1px solid var(--line); padding-top:16px; color:var(--muted)!important; font-size:.88rem!important; line-height:1.55; max-width:78ch; }
::selection { background:#c9dce6; color:var(--ink); }
input, textarea { caret-color:var(--accent); }
.gradio-container table { background:var(--surface)!important; color:var(--ink)!important; }
.gradio-container table :is(th,td) { border-color:var(--line)!important; color:var(--ink)!important; }
.gradio-container table th { background:var(--soft)!important; font-weight:600!important; }
.gradio-container table tbody tr:nth-child(odd) td { background:var(--surface)!important; }
.gradio-container table tbody tr:nth-child(even) td { background:#f8fafb!important; }
.review-guide { padding:24px; background:#edf3f6; border-radius:10px; color:var(--ink); }
.review-guide h3 { margin:0 0 20px; font-size:1.1rem; font-weight:600; }
.review-guide dl { margin:0; }
.review-guide dt { font-size:.94rem; font-weight:600; margin:20px 0 4px; }
.review-guide dd { margin:0; color:var(--muted); line-height:1.6; font-size:.9rem; }
.review-guide p { margin:24px 0 0; padding-top:16px; border-top:1px solid #cbd8df; color:var(--muted); font-size:.85rem; line-height:1.6; }
.gradio-container input, .gradio-container textarea { color:var(--ink)!important; }
.gradio-container { --block-title-text-color:var(--ink)!important; --button-secondary-text-color:var(--ink)!important; }
.gradio-container table :is(button,span) { color:var(--ink)!important; font-family:inherit!important; }
.metric-grid strong { font-family:inherit; font-weight:600; }
.analysis-panel .prose { font-size:1rem!important; line-height:1.6!important; }
.analysis-panel .prose > :is(p,ul,ol) { max-width:72ch; }
.analysis-panel .prose p { margin-block:.55rem 1rem!important; }
.analysis-panel .prose h2 { margin-top:0!important; }
.analysis-panel .prose h3 { font-size:1.05rem!important; margin-top:1.8rem!important; padding-top:1.1rem; border-top:1px solid var(--line); }
.analysis-panel details { border-top:1px solid var(--line); padding:12px 0; color:var(--ink); }
.analysis-panel .coaching-item { max-width:72ch; margin:10px 0; padding:14px 18px; background:#f3f6f8; border-radius:8px; }
.analysis-panel .coaching-item p { margin:6px 0 0!important; }
.analysis-panel .coaching-item strong { font-size:.95rem; }
.analysis-panel .quiet-result { color:var(--muted); font-size:.92rem; }
.analysis-panel summary { cursor:pointer; font-weight:600; line-height:1.5; min-height:28px; color:var(--ink); }
.analysis-panel summary:focus-visible { outline:3px solid #8bb8cf; outline-offset:3px; }
.analysis-panel details p { margin:12px 0 4px; max-width:65ch; }
.analysis-panel table { width:100%; font-family:inherit; }
.analysis-panel table :is(th,td) { padding:10px 12px!important; }
.analysis-panel li { margin-block:8px; }
button.primary { color:#fff!important; }
button.primary:disabled { background:#dce4e9!important; border-color:#dce4e9!important; color:#52616d!important; opacity:1!important; }
@media (max-width:900px) { .masthead { grid-template-columns:1fr; gap:18px; } .metric-grid { grid-template-columns:repeat(2,1fr); } .metric-grid div { border-bottom:1px solid var(--line); } }
@media (max-width:560px) { .gradio-container { padding-inline:14px!important; } .masthead { padding-top:18px; } .masthead h1 { font-size:1.8rem; } }
@media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:.01ms!important; transition-duration:.01ms!important; } }
"""


def build_theme():
    # This UI uses light surfaces even when the browser prefers dark mode.
    # Keep every Gradio component token consistent, including nested controls.
    theme = gr.themes.Base().set(
        body_text_color="#17212b",
        body_text_color_subdued="#5d6b78",
        block_label_text_color="#17212b",
        block_title_text_color="#17212b",
        input_placeholder_color="#667684",
    )
    tokens = theme.to_dict()["theme"]
    theme.set(
        **{
            key: tokens[key.removesuffix("_dark")]
            for key in tokens
            if key.endswith("_dark") and key.removesuffix("_dark") in tokens
        }
    )
    return theme


def build_app() -> gr.Blocks:
    sample_names = list_sample_names()
    with gr.Blocks(title="Call Intelligence", analytics_enabled=False) as demo:
        gr.HTML(
            '<header class="masthead"><div><span class="product-mark">Call Review</span><h1>Review a customer call</h1></div>'
            "<p>Upload a recording to generate a transcript, quality score, summary, and review-ready exports. Detected PII is removed before analysis.</p></header>"
        )
        with gr.Tabs():
            with gr.Tab("Analyze call", id="analyze"):
                gr.Markdown(
                    "## Choose a recording\nTry a sample call, upload a file, or record directly. Then select **Analyze Call**."
                )
                with gr.Row(equal_height=False):
                    with gr.Column(scale=3, elem_classes="panel"):
                        sample = gr.Dropdown(
                            label="Sample recordings",
                            choices=[
                                (name.replace("_", " ").title(), name) for name in sample_names
                            ],
                            value=None,
                            interactive=bool(sample_names),
                            info="Choose a sample to explore the demo."
                            if sample_names
                            else "No bundled recordings are available.",
                        )
                        audio = gr.Audio(
                            label="Call recording",
                            sources=["upload", "microphone"],
                            type="filepath",
                        )
                        sample.change(
                            _load_sample,
                            inputs=sample,
                            outputs=audio,
                        )
                        with (
                            gr.Accordion("Add call details (optional)", open=False),
                            gr.Row(),
                        ):
                            caller = gr.Textbox(label="Caller ID", placeholder="Internal reference")
                            department = gr.Textbox(
                                label="Department", placeholder="e.g. Customer support"
                            )
                        analyze = gr.Button("Analyze Call", variant="primary", interactive=False)
                        gr.Markdown("Supported: WAV, MP3, FLAC, M4A · Up to 50 MB / 60 minutes")
                    with gr.Column(scale=2):
                        gr.HTML(
                            '<aside class="review-guide"><h3>Your call review includes</h3><dl>'
                            "<dt>Conversation summary</dt><dd>Understand the reason for the call, its outcome, and next steps.</dd>"
                            "<dt>Quality assessment</dt><dd>Review the QA scorecard and any compliance findings.</dd>"
                            "<dt>Speaker-labeled transcript</dt><dd>Read the conversation with timestamps and confidence indicators.</dd>"
                            "<dt>Downloadable reports</dt><dd>Take the review into your workflow with PDF and JSON exports.</dd>"
                            "</dl><p>Analysis may take several minutes, depending on recording length. You can listen to a sample before starting.</p></aside>"
                        )

                processing = gr.Markdown(visible=False, elem_classes=["panel", "processing"])
                status = gr.Markdown(
                    "### Ready for a recording\nChoose a file, record audio, or load a bundled sample.",
                    elem_classes="result-status",
                )
                with gr.Column(visible=False) as results:
                    meta = gr.Markdown()
                    with gr.Row(equal_height=False):
                        with gr.Column():
                            summary = gr.Markdown(elem_classes="analysis-panel")
                        with gr.Column():
                            qa = gr.Markdown(elem_classes="analysis-panel")
                    with gr.Accordion("Speaker-labeled transcript", open=True):
                        transcript = gr.Textbox(
                            label="Transcript",
                            lines=15,
                            interactive=False,
                            buttons=["copy"],
                        )
                    with gr.Row():
                        pdf = gr.File(label="PDF report")
                        json_file = gr.File(label="JSON report")

                audio.change(
                    lambda value: gr.update(interactive=bool(value)),
                    inputs=audio,
                    outputs=analyze,
                )
                outputs = [
                    status,
                    meta,
                    transcript,
                    summary,
                    qa,
                    pdf,
                    json_file,
                    results,
                ]
                analyze.click(
                    lambda: gr.update(
                        value="### Analyzing your call\nAllow several minutes for transcription and analysis; longer recordings take more time. Please keep this page open and do not refresh.",
                        visible=True,
                    ),
                    outputs=processing,
                ).then(
                    _run,
                    inputs=[audio, caller, department],
                    outputs=outputs,
                ).then(lambda: gr.update(visible=False), outputs=processing)

            with gr.Tab("All MP3 History", id="history") as history_tab:
                gr.Markdown("## Call history")
                history_table = gr.Dataframe(
                    headers=["Call ID", "Processed", "Purpose", "QA", "Status"],
                    interactive=False,
                    wrap=True,
                    elem_classes="ledger",
                )
                history_choice = gr.Dropdown(label="Stored call", choices=[], interactive=True)
                history_refresh = gr.Button("Refresh history")
                history_status = gr.Markdown("Select a stored call.")
                with gr.Column(visible=False) as history_results:
                    history_meta = gr.Markdown()
                    with gr.Row():
                        history_summary = gr.Markdown(elem_classes="analysis-panel")
                        history_qa = gr.Markdown(elem_classes="analysis-panel")
                    history_transcript = gr.Textbox(
                        label="Stored transcript", lines=15, interactive=False, buttons=["copy"]
                    )
                    with gr.Row():
                        history_pdf = gr.File(label="Stored PDF report")
                        history_json = gr.File(label="Stored JSON report")
                history_refresh.click(_refresh_history, outputs=[history_table, history_choice])
                history_tab.select(_refresh_history, outputs=[history_table, history_choice])
                history_choice.change(
                    lambda call_id: _outputs(history_report(call_id)),
                    inputs=history_choice,
                    outputs=[
                        history_status,
                        history_meta,
                        history_transcript,
                        history_summary,
                        history_qa,
                        history_pdf,
                        history_json,
                        history_results,
                    ],
                )

            with gr.Tab("Observability", id="observability") as operations_tab:
                gr.Markdown(
                    "## Observability\nPipeline health, analysis outcomes, and the 20 most recent audit events."
                )
                metrics = gr.HTML()
                tracing = gr.Markdown(elem_classes="panel")
                audit = gr.Dataframe(
                    headers=["Timestamp", "Call ID", "Action", "Details"],
                    datatype=["str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                    label="Recent audit events",
                    elem_classes="ledger",
                )
                refresh = gr.Button("Refresh ledger")
                refresh.click(get_observability_dashboard, outputs=[metrics, tracing, audit])
                operations_tab.select(
                    get_observability_dashboard, outputs=[metrics, tracing, audit]
                )

        gr.Markdown(
            "Detected PII is removed before external LLM analysis. Raw audio and transcription artifacts remain local and require an appropriate retention policy before production use.",
            elem_classes="footer-note",
        )
        demo.load(get_observability_dashboard, outputs=[metrics, tracing, audit])
    return demo


def _run(audio, caller: str, department: str):
    return _outputs(process_call(audio, caller, department))


def _outputs(result):
    return (
        result.status_md,
        result.call_meta_md,
        result.transcript,
        result.summary_md,
        result.qa_md,
        result.pdf_path,
        result.json_path,
        gr.update(visible=result.ok),
    )


def _load_sample(sample_name: str | None) -> str | None:
    return resolve_sample_path(sample_name)


def _refresh_history():
    rows = history_rows()
    return rows, gr.update(
        choices=[(f"{row[1]} - {row[2]} ({row[0][:8]})", row[0]) for row in rows], value=None
    )
