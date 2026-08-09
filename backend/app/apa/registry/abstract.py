"""Conditional Abstract / Keywords rules (Phase 2B).

Absence of Abstract/Keywords is NOT an error for ordinary student papers.
"""

from __future__ import annotations

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import (
    clear_first_line_indent,
    effective_bold,
    first_line_indent_inches,
    is_centered,
    line_spacing_is_double,
    page_break_before,
    set_centered,
    set_double_spacing,
    set_page_break_before,
    set_runs_bold,
)

SOURCE_ABSTRACT = SourceRef(
    official_resource="APA Style Student Paper Setup Guide; abstract (when used)",
    publication_manual_section=None,
    notes=(
        "Abstracts are not required for all student papers. When an abstract is "
        "included: begin on a new page; center and bold the label Abstract; "
        "abstract text is double-spaced with no first-line indent."
    ),
    source_verified=True,
)


def _abstract_heading(context: RuleContext):
    for item in context.classified:
        if item.region == Region.ABSTRACT_HEADING and item.confidence >= 0.95:
            return item
    return None


def _abstract_body_items(context: RuleContext):
    for item in context.classified:
        if item.region == Region.ABSTRACT and item.confidence >= 0.85 and item.text.strip():
            yield item


def _detect_abstract_new_page(context: RuleContext) -> list[Issue]:
    heading = _abstract_heading(context)
    if heading is None or heading.index == 0:
        return []
    if page_break_before(heading.paragraph) is True:
        return []
    return [
        Issue(
            rule_id="APA7-ABSTRACT-001",
            category="Abstract",
            message="Abstract should begin on its own page.",
            expected="page_break_before on Abstract heading",
            actual="no page break before Abstract",
            location=f"paragraph[{heading.index}]",
            severity=Severity.ERROR,
            fixability=Fixability.SAFE_AUTO_FIX,
            can_fix=True,
            confidence=min(heading.confidence, 0.97),
            source=SOURCE_ABSTRACT,
            paragraph_index=heading.index,
            region=Region.ABSTRACT_HEADING,
        )
    ]


def _detect_abstract_label_center(context: RuleContext) -> list[Issue]:
    heading = _abstract_heading(context)
    if heading is None:
        return []
    if is_centered(heading.paragraph):
        return []
    return [
        Issue(
            rule_id="APA7-ABSTRACT-002",
            category="Abstract",
            message='Existing "Abstract" label should be centered.',
            expected="center",
            actual=str(heading.paragraph.alignment),
            location=f"paragraph[{heading.index}]",
            severity=Severity.ERROR,
            fixability=Fixability.SAFE_AUTO_FIX,
            can_fix=True,
            confidence=min(heading.confidence, 0.98),
            source=SOURCE_ABSTRACT,
            paragraph_index=heading.index,
            region=Region.ABSTRACT_HEADING,
        )
    ]


def _detect_abstract_label_bold(context: RuleContext) -> list[Issue]:
    heading = _abstract_heading(context)
    if heading is None:
        return []
    if effective_bold(heading.paragraph) is not False:
        return []
    return [
        Issue(
            rule_id="APA7-ABSTRACT-003",
            category="Abstract",
            message='Existing "Abstract" label should be bold.',
            expected="bold",
            actual="not bold",
            location=f"paragraph[{heading.index}]",
            severity=Severity.ERROR,
            fixability=Fixability.SAFE_AUTO_FIX,
            can_fix=True,
            confidence=min(heading.confidence, 0.98),
            source=SOURCE_ABSTRACT,
            paragraph_index=heading.index,
            region=Region.ABSTRACT_HEADING,
        )
    ]


def _detect_abstract_no_indent(context: RuleContext) -> list[Issue]:
    issues = []
    for item in _abstract_body_items(context):
        indent = first_line_indent_inches(item.paragraph)
        if indent is not None and abs(indent) > 0.01:
            issues.append(
                Issue(
                    rule_id="APA7-ABSTRACT-005",
                    category="Abstract",
                    message=f"Abstract paragraph {item.index} should not be indented.",
                    expected="0 in first-line indent",
                    actual=f"{indent:.3f} in",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.96),
                    source=SOURCE_ABSTRACT,
                    paragraph_index=item.index,
                    region=Region.ABSTRACT,
                )
            )
    return issues


def _detect_abstract_double(context: RuleContext) -> list[Issue]:
    issues = []
    for item in _abstract_body_items(context):
        result = line_spacing_is_double(item.paragraph)
        if result is False:
            issues.append(
                Issue(
                    rule_id="APA7-ABSTRACT-006",
                    category="Abstract",
                    message=f"Abstract paragraph {item.index} should be double-spaced.",
                    expected="double (2.0)",
                    actual="not double",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.96),
                    source=SOURCE_ABSTRACT,
                    paragraph_index=item.index,
                    region=Region.ABSTRACT,
                )
            )
    return issues


def _fix_page_break(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_page_break_before(context.doc.paragraphs[issue.paragraph_index], True)
    return True


def _fix_center(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_centered(context.doc.paragraphs[issue.paragraph_index])
    return True


def _fix_bold(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    if not paragraph.runs:
        return False
    set_runs_bold(paragraph, True)
    return True


def _fix_no_indent(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    clear_first_line_indent(context.doc.paragraphs[issue.paragraph_index])
    return True


def _fix_double(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_double_spacing(context.doc.paragraphs[issue.paragraph_index])
    return True


_SAFE = dict(
    production_supported=True,
    fixer_implemented=True,
    passing_fixture=True,
    failing_fixture=True,
    detector_test=True,
    fixer_test=True,
    post_fix_test=True,
    text_integrity_test=True,
    idempotency_test=True,
)

RULES = [
    BaseRule(
        rule_id="APA7-ABSTRACT-001",
        category="Abstract",
        description="Abstract begins on its own page (when present).",
        official_expectation="Abstract on its own page",
        source=SOURCE_ABSTRACT,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("ABSTRACT_HEADING",),
        detector=_detect_abstract_new_page,
        fixer=_fix_page_break,
        minimum_confidence=0.95,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-ABSTRACT-002",
        category="Abstract",
        description='Existing "Abstract" label centered.',
        official_expectation="Centered Abstract label",
        source=SOURCE_ABSTRACT,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("ABSTRACT_HEADING",),
        detector=_detect_abstract_label_center,
        fixer=_fix_center,
        minimum_confidence=0.95,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-ABSTRACT-003",
        category="Abstract",
        description='Existing "Abstract" label bold.',
        official_expectation="Bold Abstract label",
        source=SOURCE_ABSTRACT,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("ABSTRACT_HEADING",),
        detector=_detect_abstract_label_bold,
        fixer=_fix_bold,
        minimum_confidence=0.95,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-ABSTRACT-005",
        category="Abstract",
        description="Abstract first line is not indented.",
        official_expectation="No first-line indent in abstract",
        source=SOURCE_ABSTRACT,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("ABSTRACT",),
        detector=_detect_abstract_no_indent,
        fixer=_fix_no_indent,
        minimum_confidence=0.85,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-ABSTRACT-006",
        category="Abstract",
        description="Abstract double-spaced.",
        official_expectation="Double-space abstract text",
        source=SOURCE_ABSTRACT,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("ABSTRACT",),
        detector=_detect_abstract_double,
        fixer=_fix_double,
        minimum_confidence=0.85,
        **_SAFE,
    ),
]
