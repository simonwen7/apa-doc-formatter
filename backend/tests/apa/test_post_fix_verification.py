from app.apa.engine.fixer import fix_document_path


def test_post_fix_verification_zero_safe(failing_docx, tmp_path):
    output = tmp_path / "fixed.docx"
    result = fix_document_path(str(failing_docx), str(output))
    verification = result["verification"]

    assert verification["text_integrity_ok"] is True
    assert verification["verified"] is True
    assert verification["safe_issues_after"] == 0
    assert verification["remaining_safe_rule_ids"] == []
    assert verification["safe_issues_before"] > 0
    assert verification["fixes_applied"] > 0
