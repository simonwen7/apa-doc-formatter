from __future__ import annotations

from typing import TYPE_CHECKING

from app.apa.profile import PROFILE_ID

if TYPE_CHECKING:
    from app.apa.registry.base import BaseRule


def _modules():
    from app.apa.registry import (
        abstract,
        appendices,
        block_quotes,
        body,
        citation_reference_matching,
        citations,
        equations,
        figures,
        global_format,
        headings,
        lists,
        phase2f_p0,
        references_content,
        references_format,
        tables,
        title_page,
    )

    return (
        global_format,
        title_page,
        body,
        abstract,
        headings,
        block_quotes,
        references_format,
        references_content,
        citations,
        citation_reference_matching,
        tables,
        figures,
        appendices,
        lists,
        equations,
        phase2f_p0,
    )


def all_rules(profile: str = PROFILE_ID) -> list["BaseRule"]:
    rules: list = []
    for module in _modules():
        rules.extend(getattr(module, "RULES", []))
    return [rule for rule in rules if rule.profile == profile]


def get_rule(rule_id: str, profile: str = PROFILE_ID):
    for rule in all_rules(profile):
        if rule.rule_id == rule_id:
            return rule
    return None


def production_safe_rules(profile: str = PROFILE_ID):
    return [
        rule
        for rule in all_rules(profile)
        if rule.production_supported
        and rule.source.source_verified
        and rule.fixability.value == "SAFE_AUTO_FIX"
        and rule.fixer_implemented
    ]


def coverage_report(profile: str = PROFILE_ID) -> list[dict]:
    report = []
    for rule in all_rules(profile):
        needs_preservation = rule.rule_id.startswith(
            ("APA7-TABLE", "APA7-FIGURE", "APA7-APPENDIX", "APA7-LIST", "APA7-EQUATION")
        )
        production_supported = bool(
            rule.production_supported
            and rule.source.source_verified
            and rule.detector_implemented
            and (
                rule.fixability.value != "SAFE_AUTO_FIX"
                or (
                    rule.fixer_implemented
                    and rule.passing_fixture
                    and rule.failing_fixture
                    and rule.detector_test
                    and rule.fixer_test
                    and rule.post_fix_test
                    and rule.text_integrity_test
                    and rule.idempotency_test
                    and (rule.preservation_test or not needs_preservation)
                )
            )
        )
        report.append(
            {
                "rule_id": rule.rule_id,
                "fixability": rule.fixability.value,
                "source_verified": rule.source.source_verified,
                "source_reference": rule.source.official_resource,
                "source_description": rule.source.notes,
                "detector_implemented": rule.detector_implemented,
                "fixer_implemented": rule.fixer_implemented,
                "passing_fixture": rule.passing_fixture,
                "failing_fixture": rule.failing_fixture,
                "detector_test": rule.detector_test,
                "fixer_test": rule.fixer_test,
                "post_fix_test": rule.post_fix_test,
                "text_integrity_test": rule.text_integrity_test,
                "idempotency_test": rule.idempotency_test,
                "preservation_test": rule.preservation_test,
                "production_supported": production_supported,
            }
        )
    return report
