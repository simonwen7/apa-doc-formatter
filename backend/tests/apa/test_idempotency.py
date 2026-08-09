from app.apa.engine.analyzer import analyze_document_path
from app.apa.engine.fixer import fix_document_path
from app.apa.registry import production_safe_rules


PRODUCTION_SAFE_IDS = {rule.rule_id for rule in production_safe_rules()}


def test_fix_is_idempotent(failing_docx, tmp_path):
    first_out = tmp_path / "fixed1.docx"
    second_out = tmp_path / "fixed2.docx"

    first = fix_document_path(str(failing_docx), str(first_out))
    assert first["verification"]["verified"] is True

    second = fix_document_path(str(first_out), str(second_out))
    assert second["verification"]["verified"] is True
    assert second["verification"]["safe_issues_before"] == 0
    assert second["fixed_counts"]["safe_rules_applied"] == 0

    analysis = analyze_document_path(str(second_out))
    remaining = [
        issue.rule_id
        for issue in analysis.safe_auto_fix
        if issue.rule_id in PRODUCTION_SAFE_IDS
    ]
    assert remaining == []
