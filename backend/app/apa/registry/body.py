"""First body-page structural rules (Phase 2B)."""

from __future__ import annotations

import re

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import (
    effective_bold,
    is_centered,
    page_break_before,
    set_centered,
    set_page_break_before,
    set_runs_bold,
)

SOURCE_BODY = SourceRef(
    official_resource="APA Style Student Paper Setup Guide; page order / text",
    publication_manual_section=None,
    notes=(
        "After the title page, the text begins on a new page. Student papers often "
        "repeat the paper title at the top of the first text page (centered, bold, "
        "title case). An Introduction heading is not required."
    ),
    source_verified=True,
)


def _first_bodyish_index(context: RuleContext) -> int | None:
    for item in context.classified:
        if item.region in {
            Region.BODY,
            Region.BODY_TITLE,
            Region.LEVEL_1_HEADING,
            Region.LEVEL_2_HEADING,
            Region.LEVEL_3_HEADING,
            Region.ABSTRACT_HEADING,
        } and item.text.strip():
            return item.index
    return None


def _detect_body_new_page(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    idx = _first_bodyish_index(context)
    if idx is None or idx == 0:
        return issues
    item = context.classified[idx]
    if item.confidence < 0.9:
        return issues
    # Abstract starting bodyish is handled by abstract rules.
    if item.region == Region.ABSTRACT_HEADING:
        return issues
    if page_break_before(item.paragraph) is True:
        return issues
    issues.append(
        Issue(
            rule_id="APA7-BODY-001",
            category="Body",
            message="Body text should begin on a new page after the title page.",
            expected="page_break_before=True on first body paragraph",
            actual="no page break before first body content",
            location=f"paragraph[{idx}]",
            severity=Severity.ERROR,
            fixability=Fixability.SAFE_AUTO_FIX,
            can_fix=True,
            confidence=min(item.confidence, 0.95),
            source=SOURCE_BODY,
            paragraph_index=idx,
            region=item.region,
        )
    )
    return issues


def _fix_body_new_page(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_page_break_before(context.doc.paragraphs[issue.paragraph_index], True)
    return True


def _paper_title_text(context: RuleContext) -> str | None:
    for item in context.classified:
        if item.region == Region.PAPER_TITLE and item.text.strip():
            return item.text.strip()
    return None


def _detect_missing_body_title(context: RuleContext) -> list[Issue]:
    title = _paper_title_text(context)
    if not title:
        return []
    for item in context.classified:
        if item.region == Region.BODY_TITLE:
            return []
    # Only emit when we confidently have a title page + body.
    has_body = any(i.region == Region.BODY and i.confidence >= 0.9 for i in context.classified)
    has_title = any(
        i.region == Region.PAPER_TITLE and i.confidence >= 0.9 for i in context.classified
    )
    if not (has_body and has_title):
        return []
    return [
        Issue(
            rule_id="APA7-BODY-002",
            category="Body",
            message="Paper title should appear at the top of the first body page.",
            expected="repeated paper title on first text page",
            actual="not detected",
            location="body_start",
            severity=Severity.WARNING,
            fixability=Fixability.AUTHOR_ACTION_REQUIRED,
            can_fix=False,
            confidence=0.82,
            source=SOURCE_BODY,
            reason_not_fixable="Inserting or copying the title would invent document content.",
            region=Region.BODY,
        )
    ]


def _detect_body_title_centered(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in context.classified:
        if item.region != Region.BODY_TITLE or item.confidence < 0.9:
            continue
        if not is_centered(item.paragraph):
            issues.append(
                Issue(
                    rule_id="APA7-BODY-003",
                    category="Body",
                    message="Repeated paper title on the body page should be centered.",
                    expected="center",
                    actual=str(item.paragraph.alignment),
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.96),
                    source=SOURCE_BODY,
                    paragraph_index=item.index,
                    region=Region.BODY_TITLE,
                )
            )
    return issues


def _fix_center(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_centered(context.doc.paragraphs[issue.paragraph_index])
    return True


def _detect_body_title_bold(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in context.classified:
        if item.region != Region.BODY_TITLE or item.confidence < 0.9:
            continue
        bold = effective_bold(item.paragraph)
        if bold is False:
            issues.append(
                Issue(
                    rule_id="APA7-BODY-004",
                    category="Body",
                    message="Repeated paper title on the body page should be bold.",
                    expected="bold",
                    actual="not bold",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.96),
                    source=SOURCE_BODY,
                    paragraph_index=item.index,
                    region=Region.BODY_TITLE,
                )
            )
    return issues


def _fix_bold(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    if not paragraph.runs:
        return False
    set_runs_bold(paragraph, True)
    return True


def _looks_like_title_case_violation(text: str) -> bool:
    words = [w for w in re.findall(r"[A-Za-z0-9']+", text) if w]
    if len(words) < 3:
        return False
    lowercase = sum(1 for w in words[1:] if w.islower() and len(w) > 3)
    return lowercase >= max(2, len(words) // 3)


def _detect_body_title_case(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in context.classified:
        if item.region != Region.BODY_TITLE:
            continue
        if _looks_like_title_case_violation(item.text):
            issues.append(
                Issue(
                    rule_id="APA7-BODY-005",
                    category="Body",
                    message="Repeated paper title may not use APA title case.",
                    expected="title case",
                    actual="possible sentence case / mixed lowercase",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_BODY,
                    reason_not_fixable="Changing capitalization would modify author text.",
                    paragraph_index=item.index,
                    region=Region.BODY_TITLE,
                )
            )
    return issues


def _detect_introduction_policy(context: RuleContext) -> list[Issue]:
    """Introduction is never required. Optionally note if present (informational)."""
    # Do not emit errors for absence. Return empty by design.
    return []


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
        rule_id="APA7-BODY-001",
        category="Body",
        description="Body starts on a new page after required front matter.",
        official_expectation="Text begins on a new page after the title page",
        source=SOURCE_BODY,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("BODY", "BODY_TITLE", "LEVEL_1_HEADING"),
        detector=_detect_body_new_page,
        fixer=_fix_body_new_page,
        minimum_confidence=0.9,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-BODY-002",
        category="Body",
        description="Paper title should appear at top of first body page.",
        official_expectation="Repeated paper title on first text page",
        source=SOURCE_BODY,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_detect_missing_body_title,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-BODY-003",
        category="Body",
        description="Existing repeated paper title centered.",
        official_expectation="Centered body-page title",
        source=SOURCE_BODY,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("BODY_TITLE",),
        detector=_detect_body_title_centered,
        fixer=_fix_center,
        minimum_confidence=0.9,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-BODY-004",
        category="Body",
        description="Existing repeated paper title bold.",
        official_expectation="Bold body-page title",
        source=SOURCE_BODY,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("BODY_TITLE",),
        detector=_detect_body_title_bold,
        fixer=_fix_bold,
        minimum_confidence=0.9,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-BODY-005",
        category="Body",
        description="Repeated title should use title case.",
        official_expectation="Title case",
        source=SOURCE_BODY,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY_TITLE",),
        detector=_detect_body_title_case,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-BODY-006",
        category="Body",
        description="Introduction heading is not required for student papers.",
        official_expectation="No required Introduction heading",
        source=SOURCE_BODY,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_detect_introduction_policy,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
]
