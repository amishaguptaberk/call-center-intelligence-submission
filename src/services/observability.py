from __future__ import annotations

import json

from sqlalchemy import func, select

from src.database.connection import session_scope
from src.database.models import AuditLogEntry, CallAnalysis


def get_observability_dashboard() -> tuple[str, str, list[list[str]]]:
    with session_scope() as session:
        audits = session.scalars(
            select(AuditLogEntry).order_by(AuditLogEntry.timestamp.desc()).limit(20)
        ).all()
        analyses = session.scalars(select(CallAnalysis)).all()

        action_counts = dict(
            session.execute(
                select(AuditLogEntry.action, func.count()).group_by(AuditLogEntry.action)
            ).all()
        )
        completed = action_counts.get("completed", 0)
        failed = action_counts.get("failed", 0)
        flagged = action_counts.get("flagged_for_review", 0)
        audit_count = sum(action_counts.values())
        completed_ids = set(
            session.scalars(
                select(AuditLogEntry.call_id).where(AuditLogEntry.action == "completed")
            )
        )
        scores: list[float] = []
        flags = 0
        for item in analyses:
            try:
                qa = json.loads(item.qa_json)
                if item.call_id in completed_ids:
                    scores.append(float(qa["overall_score"]))
                flags += len(qa.get("compliance_flags") or [])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

        outcomes = completed + failed + flagged
        total = outcomes
        success_rate = f"{completed / outcomes * 100:.0f}%" if outcomes else "—"
        average = f"{sum(scores) / len(scores):.2f}" if scores else "—"
        metrics = (
            '<div class="metric-grid">'
            f"<div><span>Total calls</span><strong>{total}</strong></div>"
            f"<div><span>Completed</span><strong>{completed}</strong></div>"
            f"<div><span>Success rate</span><strong>{success_rate}</strong></div>"
            f"<div><span>Average QA (completed)</span><strong>{average}</strong></div>"
            f"<div><span>Needs review</span><strong>{flagged}</strong></div>"
            f"<div><span>Failed</span><strong>{failed}</strong></div>"
            f"<div><span>Compliance flags</span><strong>{flags}</strong></div>"
            f"<div><span>Audit events</span><strong>{audit_count}</strong></div>"
            "</div>"
        )
        rows = [
            [
                a.timestamp.strftime("%Y-%m-%d %H:%M"),
                a.call_id[:12],
                a.action.replace("_", " ").title(),
                _details(a.details),
            ]
            for a in audits
        ]
    return metrics, _langsmith_status(), rows


def _details(raw: str | None) -> str:
    if not raw:
        return "—"
    try:
        value = json.loads(raw)
        return " · ".join(
            f"{k.replace('_', ' ')}: {v if v is not None else 'not available'}"
            for k, v in value.items()
        )
    except (TypeError, json.JSONDecodeError):
        return raw


def _langsmith_status() -> str:
    import os

    enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
    return (
        "**Tracing enabled** · [Open LangSmith](https://smith.langchain.com/)."
        if enabled
        else "**Tracing local only** · Set `LANGCHAIN_TRACING_V2=true` to connect LangSmith."
    )
