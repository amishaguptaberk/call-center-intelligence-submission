from src.graph.state import (
    ActionItem,
    ComplianceFlag,
    Entity,
    QADimensionScore,
    QAScoreResult,
    ResolutionStatus,
    SummaryResult,
)
from src.utils.formatters import format_qa, format_summary, secs_to_mmss


def test_secs_to_mmss_uses_flooring_and_zero_padding():
    assert secs_to_mmss(0.99) == "00:00"
    assert secs_to_mmss(65.9) == "01:05"


def test_format_summary_includes_action_items_entities_and_empty_defaults():
    summary = SummaryResult(
        call_id="c1",
        call_purpose="Billing question",
        key_discussion_points=["Question", "Review", "Next step"],
        action_items=[ActionItem(description="Call back", owner="Agent", deadline="tomorrow")],
        resolution_status=ResolutionStatus.RESOLVED,
        sentiment_trajectory="improving",
        entities=[Entity(name="Acme", type="company")],
    )
    rendered = format_summary(summary)
    assert "## Call Summary" in rendered
    assert "- Call back (Owner: Agent, Deadline: tomorrow)" in rendered
    assert "- Acme (company)" in rendered
    assert "Resolved" in rendered
    assert rendered.index("### Next steps") < rendered.index("Discussion points")

    empty = summary.model_copy(update={"action_items": [], "entities": []})
    empty_rendered = format_summary(empty)
    assert "- No action items." in empty_rendered
    assert "- No entities identified." in empty_rendered


def test_format_qa_renders_scores_and_compliance_severity():
    qa = QAScoreResult(
        call_id="c1",
        dimension_scores=[
            QADimensionScore(dimension="professionalism", score=4, justification="clear"),
            QADimensionScore(dimension="empathy", score=3, justification="respectful"),
            QADimensionScore(dimension="problem_resolution", score=5, justification="resolved"),
            QADimensionScore(dimension="compliance", score=4, justification="verified"),
            QADimensionScore(dimension="communication_clarity", score=4, justification="concise"),
        ],
        overall_score=4.0,
        compliance_flags=[
            ComplianceFlag(
                description="Verification was skipped",
                severity="high",
                timestamp_reference="00:12",
            )
        ],
    )
    rendered = format_qa(qa)
    assert "### Overall Score: 4.00/5.00" in rendered
    assert "| Problem Resolution | **5/5** |" in rendered
    assert "<summary>Problem Resolution · 5/5</summary>" in rendered
    assert "🔶 **High** [00:12]: Verification was skipped" in rendered
    assert "Coaching tips were not generated" in rendered
    qa.dimension_scores[0].coaching_tip = "At 00:12, explain the next step before proceeding."
    qa.dimension_scores[
        1
    ].coaching_tip = "Ask about the impact of the delay <before> offering a solution."
    coached = format_qa(qa)
    assert "&lt;before&gt;" in coached
    assert coached.index("Ask about the impact") < coached.index("At 00:12, explain")


def test_all_compliance_severity_icons():
    qa = QAScoreResult(
        call_id="c1",
        dimension_scores=[
            QADimensionScore(dimension=name, score=3, justification="Evidence")
            for name in (
                "professionalism",
                "empathy",
                "problem_resolution",
                "compliance",
                "communication_clarity",
            )
        ],
        overall_score=3,
        compliance_flags=[
            ComplianceFlag(
                description="Observed violation",
                severity=severity,
                timestamp_reference="01:30",
            )
            for severity in ("low", "medium", "high", "critical")
        ],
    )
    rendered = format_qa(qa)
    for severity, icon in (
        ("Low", "ℹ️"),
        ("Medium", "⚠️"),
        ("High", "🔶"),
        ("Critical", "🔴"),
    ):
        assert f"{icon} **{severity}** [01:30]: Observed violation" in rendered
