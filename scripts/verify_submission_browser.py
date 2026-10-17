"""Local reviewer acceptance. Provider responses are synthetic; no network inference.

Run with a Python containing Playwright/pypdf; the server uses the existing .venv.
Evidence is written only to the supplied new output directory.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def serve(work: Path, port: int):
    sys.path.insert(0, str(ROOT))
    os.environ.update(
        DB_PATH=str(work / "fixture.sqlite3"),
        OPENAI_API_KEY="fixture-only",
        PYTHON_DOTENV_DISABLED="1",
        WHISPER_PRELOAD="false",
        DIARIZATION_BACKEND="heuristic",
        LANGCHAIN_TRACING_V2="false",
        LANGSMITH_TRACING="false",
        GRADIO_ANALYTICS_ENABLED="False",
        GRADIO_TEMP_DIR=str(work / "gradio"),
    )
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import pytest

    from src.agents import qa_scoring, transcription
    from src.database import connection
    from src.database.models import AuditLogEntry
    from src.graph import nodes
    from src.graph.state import QADimensionScore, QAScoreResult
    from src.ui.app import CSS, build_app, build_theme
    from tests.integration.test_reviewer_journeys import analysis, recording

    connection.init_db()
    patch = pytest.MonkeyPatch()
    transcript, _, _ = analysis.__wrapped__(patch)
    qa_response = QAScoreResult(
        call_id="fixture-provider-id",
        dimension_scores=[
            QADimensionScore(dimension=name, score=score, justification="Synthetic evidence")
            for name, score in [
                ("professionalism", 4),
                ("empathy", 2),
                ("problem_resolution", 5),
                ("compliance", 3),
                ("communication_clarity", 4),
            ]
        ],
        overall_score=5.0,
    )
    llm = MagicMock()
    # Each invocation supplies the wrong provider total so the real scorer must correct it.
    llm.with_structured_output.return_value.invoke.side_effect = lambda _: qa_response.model_copy(
        deep=True
    )
    patch.setattr(qa_scoring, "get_llm", lambda **_: llm)
    patch.setattr(nodes, "score_qa", qa_scoring.score_qa)
    # Avoid repeated-digit ASR cleanup changing the synthetic card before redaction.
    transcript.full_text = transcript.full_text.replace(
        "4111 1111 1111 1111", "4539 1488 0343 6467"
    )
    model = MagicMock()
    model.transcribe.return_value = (
        [
            SimpleNamespace(
                text=transcript.full_text,
                start=0,
                end=1,
                avg_logprob=-0.05,
                no_speech_prob=0,
                words=[],
            )
        ],
        None,
    )
    patch.setattr(transcription, "_get_whisper_model", lambda: model)
    patch.setattr(transcription, "_audio_duration_sec", lambda _: 1.0)
    patch.setattr(nodes, "run_transcription", transcription.run_transcription)
    recording.__wrapped__(work)
    with connection.session_scope() as session:
        for index in range(25):
            session.add(
                AuditLogEntry(
                    call_id=f"fixture-{index:03}",
                    action="fixture",
                    user="local-test",
                    timestamp=datetime(2099, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
                    details=json.dumps({"sequence": index}),
                )
            )
    build_app().queue().launch(
        server_name="127.0.0.1",
        server_port=port,
        share=False,
        theme=build_theme(),
        css=CSS,
    )


def geometry(page):
    return page.evaluate("""() => {
      const bounds = e => { const r=e.getBoundingClientRect(); return {
        tag:e.tagName, id:e.id, label:e.getAttribute('aria-label'),
        text:(e.innerText||'').slice(0,80), x:r.x,y:r.y,width:r.width,
        right:r.right,bottom:r.bottom}; };
      const visible=e=>e.getClientRects().length && e.getBoundingClientRect().width;
      return {viewport:innerWidth,document:document.documentElement.scrollWidth,
        overflow:[...document.querySelectorAll('button,textarea,input,[role="tab"],.analysis-panel,.metric-grid')]
          .filter(visible).map(bounds).filter(r=>r.x < -1 || r.right > innerWidth+1),
        panels:[...document.querySelectorAll('.analysis-panel:not(:has(.analysis-panel))')].filter(visible).map(bounds)};
    }""")


def run_browser(work: Path, output: Path, port: int, layout_only: bool):
    import re
    import sqlite3

    from playwright.sync_api import expect, sync_playwright
    from pypdf import PdfReader

    results = {"source": "isolated synthetic fixtures; no fresh model validation", "geometry": {}}

    def counts():
        with sqlite3.connect(work / "fixture.sqlite3") as db:
            return {
                table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("call_records", "transcription_cache", "audit_log")
            }

    def save():
        (output / "04-final-results.json").write_text(json.dumps(results, indent=2))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page.set_default_timeout(15000)
        page.goto(f"http://127.0.0.1:{port}")
        config = page.request.get(f"http://127.0.0.1:{port}/config").json()
        results["runtime_components"] = {
            c["props"]["label"]: c["id"] for c in config["components"] if c["props"].get("label")
        }
        upload = page.get_by_test_id("waveform-Call recording").locator("input[type=file]")
        analyze = page.get_by_role("button", name="Analyze Call", exact=True)
        upload.wait_for(state="attached")
        print("Reviewer UI ready", flush=True)
        if not layout_only:
            invalid = work / "invalid.mp3"
            invalid.write_bytes(b"Invalid audio fixture")
            upload.set_input_files(invalid)
            print("Corrupt recording uploaded", flush=True)
            page.wait_for_timeout(2500)
            if analyze.is_enabled():
                analyze.click()
                page.wait_for_timeout(1500)
            body = page.locator("body").inner_text()
            results["invalid_upload"] = {
                "visible_error": "error" in body.lower() or "attention" in body.lower(),
                "no_traceback": "Traceback" not in body,
            }
            page.screenshot(path=str(output / "04-final-failure-desktop.png"), full_page=True)
            results["geometry"]["failure-desktop"] = geometry(page)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "04-final-failure-mobile.png"), full_page=True)
            results["geometry"]["failure-mobile"] = geometry(page)
            page.set_viewport_size({"width": 1440, "height": 1000})
            assert all(results["invalid_upload"].values())
            assert counts()["call_records"] == 0
            save()
            page.reload()
            upload.wait_for(state="attached")
        upload.set_input_files(work / "call.wav")
        expect(analyze).to_be_enabled(timeout=15000)
        analyze.click()
        page.get_by_text("Analysis complete", exact=False).wait_for(timeout=30000)
        results["valid_upload_recovery"] = "valid upload completed after page reload"

        def capture(screen):
            for width, height, size in [(1440, 1000, "desktop"), (390, 844, "mobile")]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(500)
                if screen == "observability":
                    viewport = page.locator(".ledger:visible .virtual-table-viewport")
                    viewport.scroll_into_view_if_needed()
                    viewport.evaluate("e=>e.scrollTop=0")
                    page.wait_for_timeout(500)
                    expect(page.locator(".ledger:visible .virtual-row").first).to_be_visible()
                results["geometry"][f"{screen}-{size}"] = geometry(page)
                page.screenshot(path=str(output / f"04-final-{screen}-{size}.png"), full_page=True)
            save()

        capture("analysis")
        if not layout_only:
            secrets = ("555-123-4567", "jane@co.com", "123-45-6789", "4539 1488 0343 6467")
            transcript = page.locator("textarea:visible").last.input_value()
            assert "[REDACTED_" in transcript and all(s not in transcript for s in secrets)
            assert "[REDACTED_CREDIT_CARD]" in transcript
            exports = {}
            for label, suffix in [("JSON report", "json"), ("PDF report", "pdf")]:
                component = (
                    page.locator(".block")
                    .filter(has=page.get_by_text(label, exact=True))
                    .filter(has=page.locator("a[download]"))
                    .last
                )
                with page.expect_download() as event:
                    component.locator("a[download]").click()
                target = work / f"export.{suffix}"
                event.value.save_as(target)
                exports[suffix] = target
            report = json.loads(exports["json"].read_text())
            pdf = "\n".join(p.extract_text() or "" for p in PdfReader(exports["pdf"]).pages)
            assert all(s not in exports["json"].read_text() and s not in pdf for s in secrets)
            assert report["call_id"] in pdf
            assert all(
                report[k]["call_id"] == report["call_id"]
                for k in ("intake", "transcription", "summary", "qa_scores")
            )
            results["redacted_exports_full_ids"] = True
            assert {
                d["dimension"]: d["score"] for d in report["qa_scores"]["dimension_scores"]
            } == {
                "professionalism": 4,
                "empathy": 2,
                "problem_resolution": 5,
                "compliance": 3,
                "communication_clarity": 4,
            }
            ui = page.locator(
                ".analysis-panel:not(:has(.analysis-panel)):visible"
            ).last.inner_text()
            pdf_score = re.search(r"Overall Score:\s*(\d+\.\d+)/5", pdf)
            ui_score = re.search(r"Overall Score:\s*(\d+\.\d+)/5\.00", ui)
            assert pdf_score and ui_score, "Overall score must be readable in PDF and UI"
            results["weighted_score"] = {
                "scorer": "production score_qa; synthetic structured get_llm response",
                "expected": 3.70,
                "arithmetic_mean": 3.60,
                "provider_overall": 5.0,
                "observed": {
                    "json": report["qa_scores"]["overall_score"],
                    "pdf": float(pdf_score[1]),
                    "ui": float(ui_score[1]),
                },
            }
            save()
            assert results["weighted_score"]["observed"] == {
                "json": 3.70,
                "pdf": 3.70,
                "ui": 3.70,
            }, results["weighted_score"]
            first_counts = counts()
            assert first_counts["transcription_cache"] == 1
            page.set_viewport_size({"width": 1440, "height": 1000})
            analyze.click()
            page.wait_for_timeout(2000)
            page.get_by_text("Analysis complete", exact=False).wait_for()
            results["repeat_analysis"] = True
            assert counts()["call_records"] == 2 and counts()["transcription_cache"] == 1
            results["cache"] = {"first": first_counts, "repeat": counts()}
        results["tab_structure"] = page.locator('[role="tablist"]').evaluate("(e)=>e.outerHTML")
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.get_by_role("tab", name="All MP3 History", exact=True).click()
        before_history = counts()
        page.get_by_label("Stored call", exact=True).click()
        page.get_by_role("option").first.click()
        page.get_by_text("Stored PDF report", exact=True).wait_for()
        if not layout_only:
            stored_transcript = page.locator("textarea:visible").last.input_value()
            assert all(s not in stored_transcript for s in secrets)
            assert "[REDACTED_CREDIT_CARD]" in stored_transcript
        capture("history")
        assert counts() == before_history
        results["history_without_inference"] = True
        if layout_only:
            mobile = results["geometry"]["history-mobile"]
            a, b = mobile["panels"]
            assert not mobile["overflow"] and a["width"] >= 270 and b["y"] >= a["bottom"], mobile
            desktop = results["geometry"]["history-desktop"]
            a, b = desktop["panels"]
            assert abs(a["y"] - b["y"]) <= 2 and b["x"] >= a["right"], desktop
            browser.close()
            return
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.get_by_role("tab", name="Observability", exact=True).click()
        page.locator(".metric-grid").wait_for()
        audit = page.locator(".ledger:visible").filter(
            has=page.get_by_text("Recent audit events", exact=True)
        )
        viewport = audit.locator(".virtual-table-viewport")
        seen = {}
        for offset in range(0, 1001, 100):
            viewport.evaluate("(e,offset)=>e.scrollTop=offset", offset)
            page.wait_for_timeout(100)
            seen.update(
                audit.locator(".virtual-row").evaluate_all(
                    "es=>Object.fromEntries(es.map(e=>[e.dataset.index,e.innerText]))"
                )
            )
        assert sorted(map(int, seen)) == list(range(20)), sorted(seen)
        assert all(f"fixture-{24 - i:03}" in seen[str(i)] for i in range(20))
        results["audit_order"] = [f"fixture-{24 - i:03}" for i in range(20)]
        viewport.evaluate("e=>e.scrollTop=0")
        results["newest_20_audit"] = True
        results["metrics"] = page.locator(".metric-grid").evaluate(
            "e=>Object.fromEntries([...e.children].map(c=>[c.querySelector('span').textContent,c.querySelector('strong').textContent]))"
        )
        assert results["metrics"] == {
            "Total calls": "3",
            "Completed": "2",
            "Success rate": "67%",
            "Average QA (completed)": "3.70",
            "Needs review": "0",
            "Failed": "1",
            "Compliance flags": "0",
            "Audit events": "31",
        }
        capture("observability")
        results["microphone"] = page.evaluate("""async () => {
          let stream; let audio_inputs; let stage='enumerateDevices';
          try {
            const devices=await navigator.mediaDevices.enumerateDevices();
            audio_inputs=devices.filter(d=>d.kind==='audioinput').length;
            stage='getUserMedia';
            stream=await Promise.race([navigator.mediaDevices.getUserMedia({audio:true}),
              new Promise((_,reject)=>setTimeout(()=>reject(new DOMException('Permission request unresolved after 10s','TimeoutError')),10000))]);
            stage='MediaRecorder';
            const recorder=new MediaRecorder(stream); let bytes=0;
            recorder.ondataavailable=e=>bytes+=e.data.size;
            const done=new Promise(resolve=>recorder.onstop=resolve);
            recorder.start(); await new Promise(r=>setTimeout(r,2000)); recorder.stop(); await done;
            return {captured:true,bytes,audio_inputs:devices.filter(d=>d.kind==='audioinput').length};
          } catch(e) {return {captured:false,audio_inputs,stage,error:e.name,message:e.message};}
          finally {if(stream) stream.getTracks().forEach(t=>t.stop());}
        }""")
        save()
        browser.close()
    failures = []
    for name, g in results["geometry"].items():
        if g["overflow"] or g["document"] > g["viewport"] + 1:
            failures.append(f"{name}: overflow {g['overflow']}")
        if name.startswith("history"):
            a, b = g["panels"]
            if name.endswith("mobile"):
                if a["width"] < 270 or b["width"] < 270 or b["y"] < a["bottom"]:
                    failures.append(f"{name}: sections not stacked/readable: {g['panels']}")
            elif abs(a["y"] - b["y"]) > 2 or b["x"] < a["right"]:
                failures.append(f"{name}: sections not two columns")
    assert not failures, "\n".join(failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--port", type=int, default=17869)
    parser.add_argument("--layout-only", action="store_true")
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.port)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix="submission-ui-"))
    with (work / "server.log").open("w") as log:
        server = subprocess.Popen(
            [
                str(ROOT / ".venv/bin/python"),
                "-u",
                __file__,
                "--serve",
                str(work),
                "--port",
                str(args.port),
            ],
            cwd=ROOT,
            stdout=log,
            stderr=log,
        )
        try:
            import urllib.request

            for _ in range(60):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{args.port}/config", timeout=1)
                    break
                except OSError:
                    if server.poll() is not None:
                        raise RuntimeError(
                            f"Server exited; diagnostic log: {work / 'server.log'}"
                        ) from None
                    time.sleep(1)
            run_browser(work, args.output, args.port, args.layout_only)
        finally:
            server.terminate()
            server.wait(timeout=15)
    if not args.layout_only:
        result_path = args.output / "04-final-results.json"
        result = json.loads(result_path.read_text())
        result["cache"]["cache_hit_diagnostic"] = (
            "cache_hit=True" in (work / "server.log").read_text()
        )
        assert result["cache"]["cache_hit_diagnostic"]
        result_path.write_text(json.dumps(result, indent=2))
    print(f"Browser software acceptance passed; evidence: {args.output}; private runtime: {work}")


if __name__ == "__main__":
    main()
