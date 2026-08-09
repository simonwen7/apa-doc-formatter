from app.apa.models import Fixability
from app.apa.registry import all_rules, coverage_report, get_rule


def test_registry_contains_phase2a_rules():
    ids = {rule.rule_id for rule in all_rules()}
    for rule_id in (
        "APA7-GLOBAL-001",
        "APA7-GLOBAL-004",
        "APA7-GLOBAL-005",
        "APA7-GLOBAL-007",
        "APA7-GLOBAL-009",
        "APA7-GLOBAL-010",
        "APA7-REFERENCE-005",
        "APA7-REFERENCE-006",
        "APA7-REFERENCE-008",
        "APA7-TITLE-009",
    ):
        assert rule_id in ids


def test_author_action_rules_have_no_fixer():
    for rule in all_rules():
        if rule.fixability == Fixability.AUTHOR_ACTION_REQUIRED:
            assert rule.fixer is None
            assert rule.fixer_implemented is False


def test_safe_rules_have_verified_sources():
    for rule in all_rules():
        if rule.production_supported and rule.fixability == Fixability.SAFE_AUTO_FIX:
            assert rule.source.source_verified is True
            assert rule.fixer is not None


def test_coverage_report_shape():
    report = coverage_report()
    assert isinstance(report, list)
    assert report
    assert "rule_id" in report[0]
    assert "production_supported" in report[0]


def test_get_rule():
    rule = get_rule("APA7-GLOBAL-001")
    assert rule is not None
    assert rule.rule_id == "APA7-GLOBAL-001"
