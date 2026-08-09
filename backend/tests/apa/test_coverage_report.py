import json
from pathlib import Path

from app.apa.registry import coverage_report


def test_write_coverage_report(tmp_path):
    report = coverage_report()
    out = Path(__file__).resolve().parents[2] / "app" / "apa" / "rule_coverage.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert out.exists()

    supported_safe = [
        row
        for row in report
        if row["fixability"] == "SAFE_AUTO_FIX" and row["production_supported"]
    ]
    assert supported_safe
    for row in supported_safe:
        assert row["source_verified"] is True
        assert row["fixer_implemented"] is True
        assert row["detector_test"] is True
        assert row["fixer_test"] is True
        assert row["post_fix_test"] is True
        assert row["text_integrity_test"] is True
