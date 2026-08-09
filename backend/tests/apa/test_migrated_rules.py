"""Per-rule detector/fixer/integrity checks for Phase 2A production SAFE rules."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from app.apa.engine.analyzer import analyze_document_path
from app.apa.engine.fixer import fix_document_path
from app.apa.registry import get_rule
from app.apa.text_integrity import assert_text_integrity, snapshot_user_text


PRODUCTION_SAFE_RULE_IDS = (
    "APA7-GLOBAL-001",
    "APA7-GLOBAL-004",
    "APA7-GLOBAL-005",
    "APA7-GLOBAL-007",
    "APA7-GLOBAL-009",
    "APA7-GLOBAL-010",
    "APA7-REFERENCE-005",
    "APA7-REFERENCE-006",
    "APA7-REFERENCE-008",
)


def _issues_for(path: Path, rule_id: str) -> list:
    analysis = analyze_document_path(str(path))
    return [i for i in analysis.safe_auto_fix if i.rule_id == rule_id]


def test_each_production_safe_rule_detects_on_failing(failing_docx):
    for rule_id in PRODUCTION_SAFE_RULE_IDS:
        if rule_id == "APA7-GLOBAL-007":
            # Failing fixture uses justify; covered by GLOBAL-009 instead.
            assert not _issues_for(failing_docx, rule_id)
            continue
        assert _issues_for(failing_docx, rule_id), f"{rule_id} should detect"


def test_each_production_safe_rule_absent_on_golden(golden_docx):
    for rule_id in PRODUCTION_SAFE_RULE_IDS:
        assert not _issues_for(golden_docx, rule_id), f"{rule_id} should be clean"


def test_each_production_safe_rule_fixes_and_verifies(failing_docx, tmp_path):
    before = snapshot_user_text(Document(str(failing_docx)))
    output = tmp_path / "fixed.docx"
    result = fix_document_path(str(failing_docx), str(output))
    assert result["verification"]["verified"] is True
    assert result["verification"]["safe_issues_after"] == 0
    after = snapshot_user_text(Document(str(output)))
    assert_text_integrity(before, after)

    for rule_id in PRODUCTION_SAFE_RULE_IDS:
        assert not _issues_for(output, rule_id), f"{rule_id} remaining after fix"
        rule = get_rule(rule_id)
        assert rule is not None
        assert rule.fixer is not None
        assert rule.source.source_verified is True
