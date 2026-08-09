from app.apa.engine.analyzer import analyze_document_path
from app.apa.models import Fixability
from app.apa.registry import production_safe_rules


PRODUCTION_SAFE_IDS = {rule.rule_id for rule in production_safe_rules()}


def test_golden_has_zero_production_safe_issues(golden_docx):
    analysis = analyze_document_path(str(golden_docx))
    remaining = [
        issue.rule_id
        for issue in analysis.safe_auto_fix
        if issue.rule_id in PRODUCTION_SAFE_IDS
    ]
    assert remaining == []


def test_failing_document_detects_safe_issues(failing_docx):
    analysis = analyze_document_path(str(failing_docx))
    ids = {issue.rule_id for issue in analysis.safe_auto_fix}
    assert "APA7-GLOBAL-001" in ids
    assert "APA7-GLOBAL-004" in ids
    assert "APA7-GLOBAL-005" in ids
    assert "APA7-GLOBAL-009" in ids
    assert "APA7-GLOBAL-010" in ids
    assert "APA7-REFERENCE-005" in ids
    assert "APA7-REFERENCE-008" in ids


def test_failing_document_has_author_action_issues(failing_docx):
    analysis = analyze_document_path(str(failing_docx))
    assert analysis.author_action_count > 0
    assert all(
        issue.fixability == Fixability.AUTHOR_ACTION_REQUIRED
        and issue.can_fix is False
        for issue in analysis.author_action_required
    )
