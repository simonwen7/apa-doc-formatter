"""Student title-page rules (Phase 2B). Formatting-only SAFE fixes; never invent text."""

from __future__ import annotations

import re

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import (
    effective_bold,
    is_centered,
    line_spacing_is_double,
    set_centered,
    set_double_spacing,
    set_runs_bold,
    space_after_pt,
    clear_extra_paragraph_spacing,
)

SOURCE_TITLE = SourceRef(
    official_resource="APA Style Student Paper Setup Guide; Student title page",
    publication_manual_section=None,
    notes=(
        "Title page includes title, author, affiliation, course, instructor, due date. "
        "Elements are centered and double-spaced. Title is bold and centered. "
        "Student papers do not require a running head."
    ),
    source_verified=True,
)

SOURCE_TITLE_CASE = SourceRef(
    official_resource="APA Style Student Paper Setup Guide; Title Page elements",
    publication_manual_section=None,
    notes="Paper title uses title case. Correcting case would change author text.",
    source_verified=True,
)

MIN_TITLE_CONF = 0.85


def _title_items(context: RuleContext, min_conf: float = MIN_TITLE_CONF):
    for item in context.classified:
        if item.region in {Region.TITLE_PAGE, Region.PAPER_TITLE} and item.confidence >= min_conf:
            if item.text.strip():
                yield item


def _paper_title_items(context: RuleContext, min_conf: float = 0.9):
    for item in context.classified:
        if item.region == Region.PAPER_TITLE and item.confidence >= min_conf and item.text.strip():
            yield item


def _detect_title_double_spacing(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in _title_items(context):
        result = line_spacing_is_double(item.paragraph)
        if result is False:
            issues.append(
                Issue(
                    rule_id="APA7-TITLE-004",
                    category="Title Page",
                    message=f"Title-page paragraph {item.index} should be double-spaced.",
                    expected="double (2.0)",
                    actual="not double",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.96),
                    source=SOURCE_TITLE,
                    paragraph_index=item.index,
                    region=item.region,
                )
            )
    return issues


def _fix_title_double_spacing(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_double_spacing(context.doc.paragraphs[issue.paragraph_index])
    return True


def _detect_title_centered(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in _title_items(context, min_conf=0.88):
        if not is_centered(item.paragraph):
            issues.append(
                Issue(
                    rule_id="APA7-TITLE-005",
                    category="Title Page",
                    message=f"Title-page paragraph {item.index} should be centered.",
                    expected="center",
                    actual=str(item.paragraph.alignment),
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.95),
                    source=SOURCE_TITLE,
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


def _detect_title_vertical_position(context: RuleContext) -> list[Issue]:
    """
    APA places the title ~3–4 double-spaced lines from the top.

    python-docx cannot measure rendered page position. Blank-paragraph insertion
    is forbidden. Therefore this rule is CONDITIONAL / not production SAFE.
    """
    issues: list[Issue] = []
    for item in _paper_title_items(context, min_conf=0.9):
        # If title is the first non-empty paragraph with no prior spacing cue,
        # report conditional guidance only.
        prior_nonempty = [
            c for c in context.classified if c.index < item.index and c.text.strip()
        ]
        if prior_nonempty:
            continue
        issues.append(
            Issue(
                rule_id="APA7-TITLE-006",
                category="Title Page",
                message=(
                    "Paper title should appear about 3–4 double-spaced lines from the "
                    "top of the title page. Automatic vertical placement cannot be "
                    "guaranteed without layout rendering."
                ),
                expected="~3–4 double-spaced lines from top",
                actual="position not verifiable via python-docx",
                location=f"paragraph[{item.index}]",
                severity=Severity.INFO,
                fixability=Fixability.CONDITIONAL,
                can_fix=False,
                confidence=0.6,
                source=SOURCE_TITLE,
                reason_not_fixable=(
                    "Exact title vertical placement requires Word layout/pagination; "
                    "blank-paragraph hacks are forbidden."
                ),
                paragraph_index=item.index,
                region=Region.PAPER_TITLE,
            )
        )
    return issues


def _detect_paper_title_centered(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in _paper_title_items(context):
        if not is_centered(item.paragraph):
            issues.append(
                Issue(
                    rule_id="APA7-TITLE-007",
                    category="Title Page",
                    message="Paper title should be centered.",
                    expected="center",
                    actual=str(item.paragraph.alignment),
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.97),
                    source=SOURCE_TITLE,
                    paragraph_index=item.index,
                    region=Region.PAPER_TITLE,
                )
            )
    return issues


def _detect_paper_title_bold(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in _paper_title_items(context):
        bold = effective_bold(item.paragraph)
        if bold is None:
            # Inherited/unresolved — do not definite-error.
            continue
        if bold is False:
            issues.append(
                Issue(
                    rule_id="APA7-TITLE-008",
                    category="Title Page",
                    message="Paper title should be bold.",
                    expected="bold",
                    actual="not bold",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.96),
                    source=SOURCE_TITLE,
                    paragraph_index=item.index,
                    region=Region.PAPER_TITLE,
                )
            )
    return issues


def _fix_paper_title_bold(context: RuleContext, issue: Issue) -> bool:
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


def _detect_title_case(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in _paper_title_items(context, min_conf=0.85):
        if _looks_like_title_case_violation(item.text):
            issues.append(
                Issue(
                    rule_id="APA7-TITLE-009",
                    category="Title Page",
                    message=(
                        "The paper title may not follow APA title-case capitalization."
                    ),
                    expected="title case",
                    actual="possible sentence case / mixed lowercase",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_TITLE_CASE,
                    reason_not_fixable=(
                        "Correcting capitalization would modify author-written text."
                    ),
                    paragraph_index=item.index,
                    region=Region.PAPER_TITLE,
                )
            )
    return issues


def _detect_title_author_spacing(context: RuleContext) -> list[Issue]:
    """Spacing between title and author via paragraph spacing only."""
    issues: list[Issue] = []
    titles = list(_paper_title_items(context))
    if not titles:
        return issues
    title = titles[0]
    author = next(
        (
            item
            for item in context.classified
            if item.index > title.index
            and item.region == Region.TITLE_PAGE
            and item.title_element == "author"
            and item.confidence >= 0.8
        ),
        None,
    )
    if author is None:
        return issues
    # Extra space_after on title is fine; if huge spacing before author, clear extras only.
    if space_after_pt(title.paragraph) > 24:
        issues.append(
            Issue(
                rule_id="APA7-TITLE-010",
                category="Title Page",
                message="Title-to-author spacing appears excessive.",
                expected="normal double-spaced paragraph spacing",
                actual=f"space_after={space_after_pt(title.paragraph):.1f}pt",
                location=f"paragraph[{title.index}]",
                severity=Severity.WARNING,
                fixability=Fixability.SAFE_AUTO_FIX,
                can_fix=True,
                confidence=0.9,
                source=SOURCE_TITLE,
                paragraph_index=title.index,
                region=Region.PAPER_TITLE,
            )
        )
    return issues


def _fix_title_author_spacing(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    clear_extra_paragraph_spacing(context.doc.paragraphs[issue.paragraph_index])
    set_double_spacing(context.doc.paragraphs[issue.paragraph_index])
    return True


def _detect_author_centered(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for item in context.classified:
        if (
            item.region == Region.TITLE_PAGE
            and item.title_element == "author"
            and item.confidence >= 0.8
            and item.text.strip()
            and not is_centered(item.paragraph)
        ):
            issues.append(
                Issue(
                    rule_id="APA7-TITLE-011",
                    category="Title Page",
                    message="Author name on the title page should be centered.",
                    expected="center",
                    actual=str(item.paragraph.alignment),
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(item.confidence, 0.94),
                    source=SOURCE_TITLE,
                    paragraph_index=item.index,
                    region=Region.TITLE_PAGE,
                )
            )
    return issues


def _detect_missing_title_metadata(context: RuleContext) -> list[Issue]:
    title_items = [
        item
        for item in context.classified
        if item.region in {Region.TITLE_PAGE, Region.PAPER_TITLE} and item.text.strip()
    ]
    if len(title_items) < 2:
        # Not enough structural confidence to claim missing metadata.
        return []

    # Require strong title-page confidence overall.
    avg_conf = sum(i.confidence for i in title_items) / len(title_items)
    if avg_conf < 0.8:
        return []

    elements = {item.title_element for item in title_items if item.title_element}
    texts = " | ".join(item.text.strip().lower() for item in title_items)
    issues: list[Issue] = []

    checks = [
        (
            "APA7-TITLE-012",
            "affiliation",
            r"\b(university|college|department|school|institute|faculty|program|"
            r"centre|center|academy|polytechnic)\b",
            "Affiliation was not clearly detected on the title page.",
            "affiliation" in elements,
        ),
        (
            "APA7-TITLE-013",
            "course",
            r"\b(course|psy(?:ch)?|engl|hist|bio|math|cs|stat|chem|phys)\b|"
            r"[A-Za-z]{2,6}\s*\d{2,4}",
            "Course number/name was not clearly detected on the title page.",
            "course" in elements,
        ),
        (
            "APA7-TITLE-014",
            "instructor",
            r"\b(dr\.|prof\.|professor|instructor)\b",
            "Instructor name was not clearly detected on the title page.",
            "instructor" in elements,
        ),
        (
            "APA7-TITLE-015",
            "due date",
            r"\b(january|february|march|april|may|june|july|august|september|"
            r"october|november|december|jan\.?|feb\.?|mar\.?|apr\.?|jun\.?|"
            r"jul\.?|aug\.?|sep\.?|sept\.?|oct\.?|nov\.?|dec\.?)\b|"
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|"
            r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b|"
            r"\b[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}\b",
            "Assignment due date was not clearly detected on the title page.",
            "due_date" in elements,
        ),
    ]

    for rule_id, _label, pattern, message, has_element in checks:
        if has_element:
            continue
        if re.search(pattern, texts, flags=re.IGNORECASE):
            continue
        issues.append(
            Issue(
                rule_id=rule_id,
                category="Title Page",
                message=message,
                expected="present on student title page",
                actual="not clearly detected",
                location="title_page",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.78,
                source=SOURCE_TITLE,
                reason_not_fixable=(
                    "Generating missing title-page information would invent author content."
                ),
                region=Region.TITLE_PAGE,
            )
        )
    return issues


def _meta_detector(rule_id: str):
    def _detect(context: RuleContext) -> list[Issue]:
        return [i for i in _detect_missing_title_metadata(context) if i.rule_id == rule_id]

    return _detect


_SAFE_FLAGS = dict(
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
        rule_id="APA7-TITLE-004",
        category="Title Page",
        description="Existing title-page material is double-spaced.",
        official_expectation="Double-space the title page",
        source=SOURCE_TITLE,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("TITLE_PAGE", "PAPER_TITLE"),
        detector=_detect_title_double_spacing,
        fixer=_fix_title_double_spacing,
        minimum_confidence=0.85,
        **_SAFE_FLAGS,
    ),
    BaseRule(
        rule_id="APA7-TITLE-005",
        category="Title Page",
        description="Existing student title-page textual elements are centered.",
        official_expectation="Center title-page elements",
        source=SOURCE_TITLE,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("TITLE_PAGE", "PAPER_TITLE"),
        detector=_detect_title_centered,
        fixer=_fix_center,
        minimum_confidence=0.88,
        **_SAFE_FLAGS,
    ),
    BaseRule(
        rule_id="APA7-TITLE-006",
        category="Title Page",
        description="Paper title appears approximately 3–4 double-spaced lines from the top.",
        official_expectation="~3–4 double-spaced lines from top of title page",
        source=SOURCE_TITLE,
        fixability=Fixability.CONDITIONAL,
        applicable_regions=("PAPER_TITLE",),
        detector=_detect_title_vertical_position,
        fixer=None,
        production_supported=False,
        fixer_implemented=False,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-TITLE-007",
        category="Title Page",
        description="Existing paper title centered.",
        official_expectation="Center the paper title",
        source=SOURCE_TITLE,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("PAPER_TITLE",),
        detector=_detect_paper_title_centered,
        fixer=_fix_center,
        minimum_confidence=0.9,
        **_SAFE_FLAGS,
    ),
    BaseRule(
        rule_id="APA7-TITLE-008",
        category="Title Page",
        description="Existing paper title bold.",
        official_expectation="Bold the paper title",
        source=SOURCE_TITLE,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("PAPER_TITLE",),
        detector=_detect_paper_title_bold,
        fixer=_fix_paper_title_bold,
        minimum_confidence=0.9,
        **_SAFE_FLAGS,
    ),
    BaseRule(
        rule_id="APA7-TITLE-009",
        category="Title Page",
        description="Paper title should use title case.",
        official_expectation="Title case for the paper title",
        source=SOURCE_TITLE_CASE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("PAPER_TITLE", "TITLE_PAGE"),
        detector=_detect_title_case,
        fixer=None,
        production_supported=True,
        fixer_implemented=False,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-TITLE-010",
        category="Title Page",
        description="Spacing between existing paper title and author information.",
        official_expectation="Normal double-spaced title page flow",
        source=SOURCE_TITLE,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("PAPER_TITLE",),
        detector=_detect_title_author_spacing,
        fixer=_fix_title_author_spacing,
        minimum_confidence=0.9,
        **_SAFE_FLAGS,
    ),
    BaseRule(
        rule_id="APA7-TITLE-011",
        category="Title Page",
        description="Existing author name formatting centered.",
        official_expectation="Center author name",
        source=SOURCE_TITLE,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("TITLE_PAGE",),
        detector=_detect_author_centered,
        fixer=_fix_center,
        minimum_confidence=0.8,
        **_SAFE_FLAGS,
    ),
    BaseRule(
        rule_id="APA7-TITLE-012",
        category="Title Page",
        description="Affiliation expected on student title page.",
        official_expectation="Include affiliation",
        source=SOURCE_TITLE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TITLE_PAGE",),
        detector=_meta_detector("APA7-TITLE-012"),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-TITLE-013",
        category="Title Page",
        description="Course number/name expected on student title page.",
        official_expectation="Include course number and name",
        source=SOURCE_TITLE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TITLE_PAGE",),
        detector=_meta_detector("APA7-TITLE-013"),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-TITLE-014",
        category="Title Page",
        description="Instructor name expected on student title page.",
        official_expectation="Include instructor name",
        source=SOURCE_TITLE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TITLE_PAGE",),
        detector=_meta_detector("APA7-TITLE-014"),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-TITLE-015",
        category="Title Page",
        description="Assignment due date expected on student title page.",
        official_expectation="Include assignment due date",
        source=SOURCE_TITLE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TITLE_PAGE",),
        detector=_meta_detector("APA7-TITLE-015"),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
]
