"""APA heading Levels 1–5 (Phase 2B). Formatting-only SAFE fixes; never change text."""

from __future__ import annotations

import re

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import (
    effective_bold,
    effective_italic,
    first_line_indent_inches,
    is_centered,
    is_left_aligned_or_default,
    is_non_default_text_color,
    set_centered,
    set_left_aligned,
    set_level4_or_5_indent,
    set_runs_bold,
    set_runs_italic,
)

SOURCE_HEADINGS = SourceRef(
    official_resource="APA Style Headings guidance; Publication Manual (7th ed.) headings",
    publication_manual_section=None,
    notes=(
        "Level 1: centered, bold, title case. "
        "Level 2: flush left, bold, title case. "
        "Level 3: flush left, bold italic, title case. "
        "Level 4: indented, bold, title case, period; text continues same line. "
        "Level 5: indented, bold italic, title case, period; text continues same line. "
        "Do not invent the incorrect 24pt before/after spacing rule."
    ),
    source_verified=True,
)

LEVEL_REGIONS = {
    1: Region.LEVEL_1_HEADING,
    2: Region.LEVEL_2_HEADING,
    3: Region.LEVEL_3_HEADING,
    4: Region.LEVEL_4_HEADING,
    5: Region.LEVEL_5_HEADING,
}

SAFE_HEADING_CONF = 0.95


def _level_items(context: RuleContext, level: int, min_conf: float = SAFE_HEADING_CONF):
    region = LEVEL_REGIONS[level]
    for item in context.classified:
        if item.region == region and item.confidence >= min_conf and item.text.strip():
            yield item


def _looks_like_title_case_violation(text: str) -> bool:
    # Strip trailing period for Levels 4/5 before checking.
    check = text[:-1] if text.endswith(".") else text
    words = [w for w in re.findall(r"[A-Za-z0-9']+", check) if w]
    if len(words) < 2:
        return False
    lowercase = sum(1 for w in words[1:] if w.islower() and len(w) > 3)
    return lowercase >= max(1, len(words) // 3)


def _heading_text_portion(text: str) -> str:
    """Best-effort heading label before continuing body text (Levels 4/5)."""
    if "." in text:
        return text.split(".", 1)[0] + "."
    return text


def _detect_level1_center(context: RuleContext) -> list[Issue]:
    issues = []
    for item in _level_items(context, 1):
        if not is_centered(item.paragraph):
            issues.append(
                Issue(
                    rule_id="APA7-HEADING1-CENTER",
                    category="Headings",
                    message=f"Level 1 heading (paragraph {item.index}) should be centered.",
                    expected="center",
                    actual=str(item.paragraph.alignment),
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_1_HEADING,
                )
            )
    return issues


def _detect_level1_bold(context: RuleContext) -> list[Issue]:
    issues = []
    for item in _level_items(context, 1):
        if effective_bold(item.paragraph) is False:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING1-BOLD",
                    category="Headings",
                    message=f"Level 1 heading (paragraph {item.index}) should be bold.",
                    expected="bold",
                    actual="not bold",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_1_HEADING,
                )
            )
    return issues


def _detect_level2_left(context: RuleContext) -> list[Issue]:
    issues = []
    for item in _level_items(context, 2):
        if not is_left_aligned_or_default(item.paragraph):
            issues.append(
                Issue(
                    rule_id="APA7-HEADING2-LEFT",
                    category="Headings",
                    message=f"Level 2 heading (paragraph {item.index}) should be flush left.",
                    expected="left",
                    actual=str(item.paragraph.alignment),
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_2_HEADING,
                )
            )
    return issues


def _detect_level2_bold(context: RuleContext) -> list[Issue]:
    issues = []
    for item in _level_items(context, 2):
        if effective_bold(item.paragraph) is False:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING2-BOLD",
                    category="Headings",
                    message=f"Level 2 heading (paragraph {item.index}) should be bold.",
                    expected="bold",
                    actual="not bold",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_2_HEADING,
                )
            )
    return issues


def _detect_level3_format(context: RuleContext) -> list[Issue]:
    issues = []
    for item in _level_items(context, 3):
        if not is_left_aligned_or_default(item.paragraph):
            issues.append(
                Issue(
                    rule_id="APA7-HEADING3-LEFT",
                    category="Headings",
                    message=f"Level 3 heading (paragraph {item.index}) should be flush left.",
                    expected="left",
                    actual=str(item.paragraph.alignment),
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_3_HEADING,
                )
            )
        if effective_bold(item.paragraph) is False:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING3-BOLD",
                    category="Headings",
                    message=f"Level 3 heading (paragraph {item.index}) should be bold.",
                    expected="bold",
                    actual="not bold",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_3_HEADING,
                )
            )
        if effective_italic(item.paragraph) is False:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING3-ITALIC",
                    category="Headings",
                    message=f"Level 3 heading (paragraph {item.index}) should be italic.",
                    expected="italic",
                    actual="not italic",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.98),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_3_HEADING,
                )
            )
    return issues


def _detect_level4_safe_format(context: RuleContext) -> list[Issue]:
    """Format-only when Level 4 is a single paragraph (heading+body same line)."""
    issues = []
    for item in _level_items(context, 4, min_conf=0.95):
        text = item.text.strip()
        # Split-paragraph unsafe structure: short heading-like line without period
        # and next paragraph continuing — AUTHOR handled separately.
        indent = first_line_indent_inches(item.paragraph)
        if indent is None or abs(indent - 0.5) > 0.05:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING4-INDENT",
                    category="Headings",
                    message=f"Level 4 heading (paragraph {item.index}) should be indented 0.5 in.",
                    expected="0.5 in first-line indent",
                    actual="missing/incorrect indent",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.97),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_4_HEADING,
                )
            )
        if effective_bold(item.paragraph) is False:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING4-BOLD",
                    category="Headings",
                    message=f"Level 4 heading (paragraph {item.index}) should be bold.",
                    expected="bold",
                    actual="not bold",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.97),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_4_HEADING,
                )
            )
        if not text.endswith("."):
            issues.append(
                Issue(
                    rule_id="APA7-HEADING4-PERIOD",
                    category="Headings",
                    message=(
                        f"Level 4 heading (paragraph {item.index}) should end with a "
                        "period before continuing text."
                    ),
                    expected="heading ends with period",
                    actual="no trailing period on heading label",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.9,
                    source=SOURCE_HEADINGS,
                    reason_not_fixable="Adding a period would modify author-written text.",
                    paragraph_index=item.index,
                    region=Region.LEVEL_4_HEADING,
                )
            )
        if _looks_like_title_case_violation(_heading_text_portion(text)):
            issues.append(
                Issue(
                    rule_id="APA7-HEADING4-TITLECASE",
                    category="Headings",
                    message=f"Level 4 heading (paragraph {item.index}) may not use title case.",
                    expected="title case",
                    actual="possible non-title-case",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_HEADINGS,
                    reason_not_fixable="Changing capitalization would modify author text.",
                    paragraph_index=item.index,
                    region=Region.LEVEL_4_HEADING,
                )
            )
    return issues


def _detect_level5_safe_format(context: RuleContext) -> list[Issue]:
    issues = []
    for item in _level_items(context, 5, min_conf=0.95):
        text = item.text.strip()
        indent = first_line_indent_inches(item.paragraph)
        if indent is None or abs(indent - 0.5) > 0.05:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING5-INDENT",
                    category="Headings",
                    message=f"Level 5 heading (paragraph {item.index}) should be indented 0.5 in.",
                    expected="0.5 in first-line indent",
                    actual="missing/incorrect indent",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.97),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_5_HEADING,
                )
            )
        if effective_bold(item.paragraph) is False:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING5-BOLD",
                    category="Headings",
                    message=f"Level 5 heading (paragraph {item.index}) should be bold.",
                    expected="bold",
                    actual="not bold",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.97),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_5_HEADING,
                )
            )
        if effective_italic(item.paragraph) is False:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING5-ITALIC",
                    category="Headings",
                    message=f"Level 5 heading (paragraph {item.index}) should be italic.",
                    expected="italic",
                    actual="not italic",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.97),
                    source=SOURCE_HEADINGS,
                    paragraph_index=item.index,
                    region=Region.LEVEL_5_HEADING,
                )
            )
        if not text.endswith("."):
            # For same-line structure, period may be mid-paragraph after heading label.
            heading_part = text.split(" ", 3)[0:3]
            _ = heading_part
            if ". " not in text and not text.endswith("."):
                issues.append(
                    Issue(
                        rule_id="APA7-HEADING5-PERIOD",
                        category="Headings",
                        message=(
                            f"Level 5 heading (paragraph {item.index}) should include a "
                            "period after the heading label."
                        ),
                        expected="heading label ends with period",
                        actual="period not detected",
                        location=f"paragraph[{item.index}]",
                        severity=Severity.WARNING,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.85,
                        source=SOURCE_HEADINGS,
                        reason_not_fixable="Adding a period would modify author-written text.",
                        paragraph_index=item.index,
                        region=Region.LEVEL_5_HEADING,
                    )
                )
    return issues


def _detect_split_level4_or_5(context: RuleContext) -> list[Issue]:
    """
    If a Level 4/5 style heading is a short standalone paragraph and the next
    paragraph looks like continuing body, merging would be required → AUTHOR.
    """
    issues = []
    for item in context.classified:
        if item.region not in {Region.LEVEL_4_HEADING, Region.LEVEL_5_HEADING}:
            continue
        if item.confidence < 0.9:
            continue
        text = item.text.strip()
        if len(text) > 80 and ". " in text:
            continue  # likely same-paragraph structure
        nxt = next((c for c in context.classified if c.index == item.index + 1), None)
        if nxt is None or not nxt.text.strip():
            continue
        if nxt.region != Region.BODY:
            continue
        # Standalone heading + following body paragraph = unsafe to merge.
        rule_id = (
            "APA7-HEADING4-STRUCTURE"
            if item.region == Region.LEVEL_4_HEADING
            else "APA7-HEADING5-STRUCTURE"
        )
        issues.append(
            Issue(
                rule_id=rule_id,
                category="Headings",
                message=(
                    f"Level {'4' if '4' in rule_id else '5'} heading appears split across "
                    "paragraphs. Correct APA structure keeps heading and body text on "
                    "the same line."
                ),
                expected="same-paragraph heading + body text",
                actual="heading paragraph followed by separate body paragraph",
                location=f"paragraph[{item.index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.9,
                source=SOURCE_HEADINGS,
                reason_not_fixable=(
                    "Merging paragraphs would rewrite document structure/content."
                ),
                paragraph_index=item.index,
                region=item.region,
            )
        )
    return issues


def _detect_heading_title_case(context: RuleContext) -> list[Issue]:
    issues = []
    for level, region in LEVEL_REGIONS.items():
        if level >= 4:
            continue  # handled in level4/5 detectors
        for item in _level_items(context, level, min_conf=0.9):
            if _looks_like_title_case_violation(item.text):
                issues.append(
                    Issue(
                        rule_id=f"APA7-HEADING{level}-TITLECASE",
                        category="Headings",
                        message=(
                            f"Level {level} heading (paragraph {item.index}) may not "
                            "use APA title case."
                        ),
                        expected="title case",
                        actual="possible non-title-case",
                        location=f"paragraph[{item.index}]",
                        severity=Severity.WARNING,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.8,
                        source=SOURCE_HEADINGS,
                        reason_not_fixable="Changing capitalization would modify author text.",
                        paragraph_index=item.index,
                        region=region,
                    )
                )
    return issues


def _detect_low_confidence_heading(context: RuleContext) -> list[Issue]:
    issues = []
    for item in context.classified:
        if item.region != Region.HEADING:
            continue
        if item.confidence >= SAFE_HEADING_CONF:
            continue
        issues.append(
            Issue(
                rule_id="APA7-HEADING-UNCERTAIN",
                category="Headings",
                message=(
                    f"Paragraph {item.index} may be a heading, but classification "
                    "confidence is not high enough to modify it automatically."
                ),
                expected="confident heading level classification",
                actual=f"confidence={item.confidence:.2f}",
                location=f"paragraph[{item.index}]",
                severity=Severity.INFO,
                fixability=Fixability.CONDITIONAL,
                can_fix=False,
                confidence=item.confidence,
                source=SOURCE_HEADINGS,
                reason_not_fixable="Low-confidence classification must not trigger auto-fix.",
                paragraph_index=item.index,
                region=Region.HEADING,
            )
        )
    return issues


def _detect_heading_nonstandard_color(context: RuleContext) -> list[Issue]:
    """Surface decorative/non-black heading color conservatively (not SAFE)."""
    issues: list[Issue] = []
    heading_regions = {
        Region.HEADING,
        Region.LEVEL_1_HEADING,
        Region.LEVEL_2_HEADING,
        Region.LEVEL_3_HEADING,
        Region.LEVEL_4_HEADING,
        Region.LEVEL_5_HEADING,
        Region.BODY_TITLE,
    }
    for item in context.classified:
        if item.region not in heading_regions or not item.text.strip():
            continue
        if item.confidence < 0.85:
            continue
        colored = is_non_default_text_color(item.paragraph)
        if colored is True:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING-COLOR",
                    category="Headings",
                    message=(
                        f"Heading paragraph {item.index} uses non-standard text color. "
                        "APA student papers typically use black text; instructor "
                        "templates may intentionally use color."
                    ),
                    expected="standard black text (or instructor-approved styling)",
                    actual="non-default effective text color",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.CONDITIONAL,
                    can_fix=False,
                    confidence=min(item.confidence, 0.85),
                    source=SOURCE_HEADINGS,
                    reason_not_fixable=(
                        "Automatic color normalization may conflict with instructor "
                        "template requirements."
                    ),
                    paragraph_index=item.index,
                    region=item.region,
                )
            )
    return issues


def _fix_center(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_centered(context.doc.paragraphs[issue.paragraph_index])
    return True


def _fix_left(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_left_aligned(context.doc.paragraphs[issue.paragraph_index])
    return True


def _fix_bold(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    if not paragraph.runs:
        return False
    set_runs_bold(paragraph, True)
    return True


def _fix_italic(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    if not paragraph.runs:
        return False
    set_runs_italic(paragraph, True)
    return True


def _fix_indent(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_level4_or_5_indent(context.doc.paragraphs[issue.paragraph_index])
    return True


def _filter(rule_id: str, detector):
    def _detect(context: RuleContext) -> list[Issue]:
        return [i for i in detector(context) if i.rule_id == rule_id]

    return _detect


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
        rule_id="APA7-HEADING1-CENTER",
        category="Headings",
        description="Level 1 heading centered.",
        official_expectation="Centered Level 1 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_1_HEADING",),
        detector=_detect_level1_center,
        fixer=_fix_center,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING1-BOLD",
        category="Headings",
        description="Level 1 heading bold.",
        official_expectation="Bold Level 1 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_1_HEADING",),
        detector=_detect_level1_bold,
        fixer=_fix_bold,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING1-TITLECASE",
        category="Headings",
        description="Level 1 heading title case.",
        official_expectation="Title case",
        source=SOURCE_HEADINGS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_1_HEADING",),
        detector=_filter("APA7-HEADING1-TITLECASE", _detect_heading_title_case),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-HEADING2-LEFT",
        category="Headings",
        description="Level 2 heading flush left.",
        official_expectation="Flush left Level 2 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_2_HEADING",),
        detector=_detect_level2_left,
        fixer=_fix_left,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING2-BOLD",
        category="Headings",
        description="Level 2 heading bold.",
        official_expectation="Bold Level 2 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_2_HEADING",),
        detector=_detect_level2_bold,
        fixer=_fix_bold,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING2-TITLECASE",
        category="Headings",
        description="Level 2 heading title case.",
        official_expectation="Title case",
        source=SOURCE_HEADINGS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_2_HEADING",),
        detector=_filter("APA7-HEADING2-TITLECASE", _detect_heading_title_case),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-HEADING3-LEFT",
        category="Headings",
        description="Level 3 heading flush left.",
        official_expectation="Flush left Level 3 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_3_HEADING",),
        detector=_filter("APA7-HEADING3-LEFT", _detect_level3_format),
        fixer=_fix_left,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING3-BOLD",
        category="Headings",
        description="Level 3 heading bold.",
        official_expectation="Bold Level 3 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_3_HEADING",),
        detector=_filter("APA7-HEADING3-BOLD", _detect_level3_format),
        fixer=_fix_bold,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING3-ITALIC",
        category="Headings",
        description="Level 3 heading italic.",
        official_expectation="Italic Level 3 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_3_HEADING",),
        detector=_filter("APA7-HEADING3-ITALIC", _detect_level3_format),
        fixer=_fix_italic,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING3-TITLECASE",
        category="Headings",
        description="Level 3 heading title case.",
        official_expectation="Title case",
        source=SOURCE_HEADINGS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_3_HEADING",),
        detector=_filter("APA7-HEADING3-TITLECASE", _detect_heading_title_case),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-HEADING4-INDENT",
        category="Headings",
        description="Level 4 heading 0.5-inch indent.",
        official_expectation="Indented Level 4 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_4_HEADING",),
        detector=_filter("APA7-HEADING4-INDENT", _detect_level4_safe_format),
        fixer=_fix_indent,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING4-BOLD",
        category="Headings",
        description="Level 4 heading bold.",
        official_expectation="Bold Level 4 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_4_HEADING",),
        detector=_filter("APA7-HEADING4-BOLD", _detect_level4_safe_format),
        fixer=_fix_bold,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING4-PERIOD",
        category="Headings",
        description="Level 4 heading ends with period.",
        official_expectation="Period after Level 4 heading label",
        source=SOURCE_HEADINGS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_4_HEADING",),
        detector=_filter("APA7-HEADING4-PERIOD", _detect_level4_safe_format),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-HEADING4-STRUCTURE",
        category="Headings",
        description="Level 4 split-paragraph structure requires author action.",
        official_expectation="Same-line Level 4 heading + body",
        source=SOURCE_HEADINGS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_4_HEADING",),
        detector=_filter("APA7-HEADING4-STRUCTURE", _detect_split_level4_or_5),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-HEADING5-INDENT",
        category="Headings",
        description="Level 5 heading 0.5-inch indent.",
        official_expectation="Indented Level 5 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_5_HEADING",),
        detector=_filter("APA7-HEADING5-INDENT", _detect_level5_safe_format),
        fixer=_fix_indent,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING5-BOLD",
        category="Headings",
        description="Level 5 heading bold.",
        official_expectation="Bold Level 5 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_5_HEADING",),
        detector=_filter("APA7-HEADING5-BOLD", _detect_level5_safe_format),
        fixer=_fix_bold,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING5-ITALIC",
        category="Headings",
        description="Level 5 heading italic.",
        official_expectation="Italic Level 5 heading",
        source=SOURCE_HEADINGS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("LEVEL_5_HEADING",),
        detector=_filter("APA7-HEADING5-ITALIC", _detect_level5_safe_format),
        fixer=_fix_italic,
        minimum_confidence=SAFE_HEADING_CONF,
        **_SAFE,
    ),
    BaseRule(
        rule_id="APA7-HEADING5-PERIOD",
        category="Headings",
        description="Level 5 heading ends with period.",
        official_expectation="Period after Level 5 heading label",
        source=SOURCE_HEADINGS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_5_HEADING",),
        detector=_filter("APA7-HEADING5-PERIOD", _detect_level5_safe_format),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-HEADING5-STRUCTURE",
        category="Headings",
        description="Level 5 split-paragraph structure requires author action.",
        official_expectation="Same-line Level 5 heading + body",
        source=SOURCE_HEADINGS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_5_HEADING",),
        detector=_filter("APA7-HEADING5-STRUCTURE", _detect_split_level4_or_5),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-HEADING-UNCERTAIN",
        category="Headings",
        description="Low-confidence heading candidates are not auto-fixed.",
        official_expectation="Confident classification before formatting",
        source=SOURCE_HEADINGS,
        fixability=Fixability.CONDITIONAL,
        applicable_regions=("HEADING",),
        detector=_detect_low_confidence_heading,
        fixer=None,
        production_supported=False,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-HEADING-COLOR",
        category="Headings",
        description="Non-standard heading text color is surfaced conservatively.",
        official_expectation="Black text unless instructor template requires otherwise",
        source=SOURCE_HEADINGS,
        fixability=Fixability.CONDITIONAL,
        applicable_regions=(
            "HEADING",
            "LEVEL_1_HEADING",
            "LEVEL_2_HEADING",
            "LEVEL_3_HEADING",
            "LEVEL_4_HEADING",
            "LEVEL_5_HEADING",
            "BODY_TITLE",
        ),
        detector=_detect_heading_nonstandard_color,
        fixer=None,
        production_supported=True,
        fixer_implemented=False,
        detector_test=True,
    ),
]
