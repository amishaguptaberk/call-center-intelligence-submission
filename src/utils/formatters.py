from html import escape

from src.graph.state import QAScoreResult, SummaryResult


def secs_to_mmss(seconds: float) -> str:
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    remaining_seconds = total_seconds % 60

    return f"{minutes:02d}:{remaining_seconds:02d}"


def format_summary(summary: SummaryResult) -> str:
    lines = [
        "## Call Summary",
        "",
        summary.call_purpose,
        "",
        f"**Outcome:** {summary.resolution_status.value.replace('_', ' ').title()}",
        "",
        f"**Customer sentiment:** {summary.sentiment_trajectory}",
        "",
        "### Next steps",
    ]

    if summary.action_items:
        for item in summary.action_items:
            line = f"- {item.description} (Owner: {item.owner}"

            if item.deadline:
                line += f", Deadline: {item.deadline}"

            line += ")"
            lines.append(line)
    else:
        lines.append("- No action items.")

    lines.extend(
        [
            "",
            "<details><summary>Discussion points</summary>",
            "",
        ]
    )
    for point in summary.key_discussion_points:
        lines.append(f"- {point}")
    lines.extend(
        [
            "",
            "</details>",
            "",
            "<details><summary>People and organizations</summary>",
            "",
        ]
    )

    if summary.entities:
        for entity in summary.entities:
            lines.append(f"- {entity.name} ({entity.type})")
    else:
        lines.append("- No entities identified.")

    lines.extend(["", "</details>"])
    return "\n".join(lines)


def format_qa(qa: QAScoreResult) -> str:
    lines = [
        "## QA Evaluation",
        "",
        f"### Overall Score: {qa.overall_score:.2f}/5.00",
        "",
        "| Dimension | Score |",
        "| :--- | ---: |",
    ]

    for dimension in qa.dimension_scores:
        name = dimension.dimension.replace("_", " ").title()
        lines.append(f"| {name} | **{dimension.score}/5** |")

    lines.extend(["", "### Coaching priorities", ""])
    tips = [dimension for dimension in qa.dimension_scores if dimension.coaching_tip]
    if tips:
        ranked = sorted(tips, key=lambda item: item.score)
        for dimension in ranked[:2]:
            name = dimension.dimension.replace("_", " ").title()
            label = "Keep doing" if dimension.score == 5 else "Next step"
            lines.append(
                f'<div class="coaching-item"><strong>{escape(name)} · {dimension.score}/5</strong><p>{label}: {escape(dimension.coaching_tip)}</p></div>'
            )
        if len(ranked) > 2:
            lines.extend(
                [
                    "",
                    f"<details><summary>More coaching tips ({len(ranked) - 2})</summary>",
                    "",
                ]
            )
            for dimension in ranked[2:]:
                name = dimension.dimension.replace("_", " ").title()
                label = "Keep doing" if dimension.score == 5 else "Next step"
                lines.append(
                    f'<div class="coaching-item"><strong>{escape(name)} · {dimension.score}/5</strong><p>{label}: {escape(dimension.coaching_tip)}</p></div>'
                )
            lines.extend(["", "</details>"])
    else:
        lines.append(
            "Coaching tips were not generated for this report. Analyze the call again to include them."
        )
    lines.extend(["", "### Compliance findings", ""])
    if not qa.compliance_flags:
        lines.append('<p class="quiet-result">No compliance issues detected.</p>')
    else:
        severity_icons = {"low": "ℹ️", "medium": "⚠️", "high": "🔶", "critical": "🔴"}
        for flag in qa.compliance_flags:
            icon = severity_icons.get(flag.severity, "⚪")
            lines.append(
                f"- {icon} **{flag.severity.title()}** [{flag.timestamp_reference}]: {flag.description}"
            )
    lines.extend(
        [
            "",
            "### Score explanations",
            "",
            "Expand a dimension to review the supporting evidence.",
            "",
        ]
    )
    for dimension in qa.dimension_scores:
        name = dimension.dimension.replace("_", " ").title()
        lines.extend(
            [
                f"<details><summary>{escape(name)} · {dimension.score}/5</summary>",
                f"<p>{escape(dimension.justification)}</p>",
                "</details>",
                "",
            ]
        )
    return "\n".join(lines)
