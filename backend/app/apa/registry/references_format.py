from __future__ import annotations

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import (
    clear_extra_paragraph_spacing,
    effective_bold,
    is_centered,
    is_hanging_indent,
    line_spacing_is_double,
    page_break_before,
    set_centered,
    set_double_spacing,
    set_flush_left_no_first_indent,
    set_hanging_indent,
    set_page_break_before,
    set_runs_bold,
    space_after_pt,
    space_before_pt,
)

SOURCE_REFS = SourceRef(
    official_resource="APA Style Student Paper Setup Guide; Publication Manual (7th ed.), Reference List",
    publication_manual_section=None,
    notes=(
        "Reference list is double-spaced; first line flush left; "
        "hanging indent 0.5 in for continuation lines."
    ),
    source_verified=True,
)


def _ref_entries(context: RuleContext, min_confidence: float = 0.95):
    for item in context.classified:
        if (
            item.region == Region.REFERENCE_ENTRY
            and item.confidence >= min_confidence
            and item.text.strip()
        ):
            yield item


def _detect_ref_double_spacing(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in _ref_entries(context):
        result = line_spacing_is_double(item.paragraph)
        if result is False:
            issues.append(
                Issue(
                    rule_id="APA7-REFERENCE-005",
                    category="References",
                    message=f"Reference paragraph {item.index} should be double-spaced.",
                    expected="double (2.0)",
                    actual="not double",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.97),
                    source=SOURCE_REFS,
                    paragraph_index=item.index,
                    region=Region.REFERENCE_ENTRY,
                )
            )
    return issues


def _fix_ref_double_spacing(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_double_spacing(context.doc.paragraphs[issue.paragraph_index])
    return True


def _detect_ref_extra_spacing(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in _ref_entries(context):
        before = space_before_pt(item.paragraph)
        after = space_after_pt(item.paragraph)
        if before > 0.5 or after > 0.5:
            issues.append(
                Issue(
                    rule_id="APA7-REFERENCE-006",
                    category="References",
                    message=(
                        f"Reference paragraph {item.index} should not include "
                        "extra paragraph spacing."
                    ),
                    expected="0 pt before/after",
                    actual=f"{before:.1f}/{after:.1f} pt",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.96),
                    source=SOURCE_REFS,
                    paragraph_index=item.index,
                    region=Region.REFERENCE_ENTRY,
                )
            )
    return issues


def _fix_ref_extra_spacing(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    clear_extra_paragraph_spacing(context.doc.paragraphs[issue.paragraph_index])
    return True


def _detect_hanging_indent(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in _ref_entries(context):
        result = is_hanging_indent(item.paragraph)
        if result is False or result is None:
            issues.append(
                Issue(
                    rule_id="APA7-REFERENCE-008",
                    category="References",
                    message=(
                        f"Reference paragraph {item.index} should use a "
                        "0.5-inch hanging indent."
                    ),
                    expected="left 0.5 in; first-line -0.5 in",
                    actual="missing or incorrect hanging indent",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.96),
                    source=SOURCE_REFS,
                    paragraph_index=item.index,
                    region=Region.REFERENCE_ENTRY,
                )
            )
    return issues


def _fix_hanging_indent(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    set_hanging_indent(paragraph)
    return True


def _detect_flush_first_line(context: RuleContext) -> list[Issue]:
    """
    APA7-REFERENCE-009: first line flush left is implied by hanging indent.
    Kept as explicit rule for coverage/reporting; fixer applies hanging indent.
    """
    # Avoid duplicate user-facing noise when 008 already covers the same root cause.
    # Detector returns empty; rule remains registered for coverage metadata.
    return []


def _detect_refs_new_page(context: RuleContext) -> list[Issue]:
    issues = []
    for item in context.classified:
        if item.region != Region.REFERENCES_HEADING or item.confidence < 0.95:
            continue
        if item.index == 0:
            continue
        if page_break_before(item.paragraph) is True:
            continue
        issues.append(
            Issue(
                rule_id="APA7-REFERENCE-001",
                category="References",
                message="References list should begin on a new page.",
                expected="page_break_before on References heading",
                actual="no page break before References",
                location=f"paragraph[{item.index}]",
                severity=Severity.ERROR,
                fixability=Fixability.SAFE_AUTO_FIX,
                can_fix=True,
                confidence=min(item.confidence, 0.97),
                source=SOURCE_REFS,
                paragraph_index=item.index,
                region=Region.REFERENCES_HEADING,
            )
        )
    return issues


def _fix_refs_new_page(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_page_break_before(context.doc.paragraphs[issue.paragraph_index], True)
    return True


def _detect_refs_heading_format(context: RuleContext) -> list[Issue]:
    issues = []
    for item in context.classified:
        if item.region != Region.REFERENCES_HEADING or item.confidence < 0.95:
            continue
        if not is_centered(item.paragraph):
            issues.append(
                Issue(
                    rule_id="APA7-REFERENCE-002",
                    category="References",
                    message='Existing "References" heading should be centered.',
                    expected="center",
                    actual=str(item.paragraph.alignment),
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_REFS,
                    paragraph_index=item.index,
                    region=Region.REFERENCES_HEADING,
                )
            )
        if effective_bold(item.paragraph) is False:
            issues.append(
                Issue(
                    rule_id="APA7-REFERENCE-003",
                    category="References",
                    message='Existing "References" heading should be bold.',
                    expected="bold",
                    actual="not bold",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_REFS,
                    paragraph_index=item.index,
                    region=Region.REFERENCES_HEADING,
                )
            )
    return issues


def _fix_refs_center(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_centered(context.doc.paragraphs[issue.paragraph_index])
    return True


def _fix_refs_bold(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    if not paragraph.runs:
        return False
    set_runs_bold(paragraph, True)
    return True


def _detect_alpha_order(context: RuleContext) -> list[Issue]:
    """Alphabetical order analysis only — never reorder paragraphs."""
    from app.apa.parsing.reference_entry import parse_reference_entry

    entries = [
        parse_reference_entry(item.index, item.text)
        for item in context.classified
        if item.region == Region.REFERENCE_ENTRY
        and item.confidence >= 0.95
        and item.text.strip()
    ]
    if len(entries) < 2:
        return []
    keys = [e.sort_key for e in entries]
    if keys == sorted(keys):
        return []
    return [
        Issue(
            rule_id="APA7-REFERENCE-ALPHA",
            category="Reference Content",
            message=(
                "Reference-list entries may not be in alphabetical order. "
                "Please review and reorder them if needed."
            ),
            expected="alphabetical order by author surname",
            actual="possible out-of-order entries",
            location="references",
            severity=Severity.WARNING,
            fixability=Fixability.AUTHOR_ACTION_REQUIRED,
            can_fix=False,
            confidence=0.8,
            source=SOURCE_REFS,
            reason_not_fixable="Reordering paragraphs changes document structure.",
            region=Region.REFERENCE_ENTRY,
        )
    ]


RULES = [
    BaseRule(
        rule_id="APA7-REFERENCE-001",
        category="References",
        description="Reference list begins on a new page.",
        official_expectation="References start on a new page",
        source=SOURCE_REFS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("REFERENCES_HEADING",),
        detector=_detect_refs_new_page,
        fixer=_fix_refs_new_page,
        minimum_confidence=0.95,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-002",
        category="References",
        description='Existing "References" heading centered.',
        official_expectation="Centered References heading",
        source=SOURCE_REFS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("REFERENCES_HEADING",),
        detector=lambda ctx: [
            i for i in _detect_refs_heading_format(ctx) if i.rule_id == "APA7-REFERENCE-002"
        ],
        fixer=_fix_refs_center,
        minimum_confidence=0.95,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-003",
        category="References",
        description='Existing "References" heading bold.',
        official_expectation="Bold References heading",
        source=SOURCE_REFS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("REFERENCES_HEADING",),
        detector=lambda ctx: [
            i for i in _detect_refs_heading_format(ctx) if i.rule_id == "APA7-REFERENCE-003"
        ],
        fixer=_fix_refs_bold,
        minimum_confidence=0.95,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-005",
        category="References",
        description="Reference entries should be double-spaced.",
        official_expectation="Double-space the reference list",
        source=SOURCE_REFS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_ref_double_spacing,
        fixer=_fix_ref_double_spacing,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-006",
        category="References",
        description="Reference entries should not include extra paragraph spacing.",
        official_expectation="No extra before/after spacing in reference list",
        source=SOURCE_REFS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_ref_extra_spacing,
        fixer=_fix_ref_extra_spacing,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-007",
        category="References",
        description=(
            "DEPRECATED alias: reference-list spacing consistency is covered by "
            "APA7-REFERENCE-005 and APA7-REFERENCE-006. Retained only for coverage "
            "compatibility; detector intentionally empty."
        ),
        official_expectation="Consistent double spacing throughout references",
        source=SOURCE_REFS,
        fixability=Fixability.UNSUPPORTED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=lambda context: [],  # deprecated duplicate of 005/006
        fixer=None,
        production_supported=False,
        fixer_implemented=False,
        detector_implemented=False,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-008",
        category="References",
        description="Reference entries use a 0.5-inch hanging indent.",
        official_expectation="Hanging indent of 0.5 in",
        source=SOURCE_REFS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_hanging_indent,
        fixer=_fix_hanging_indent,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-009",
        category="References",
        description="Reference first line flush left (via hanging indent).",
        official_expectation="First line flush left",
        source=SOURCE_REFS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_flush_first_line,
        fixer=_fix_hanging_indent,
        production_supported=False,  # deduped into 008 for user-facing issues
        fixer_implemented=True,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-ALPHA",
        category="Reference Content",
        description="Reference list alphabetical order (never auto-reordered).",
        official_expectation="Alphabetical order by author",
        source=SOURCE_REFS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_alpha_order,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
]
