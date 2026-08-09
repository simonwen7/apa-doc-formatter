"""Reference content analysis — AUTHOR_ACTION_REQUIRED only. Never rewrite text."""

from __future__ import annotations

import re

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.reference_entry import ReferenceType, parse_reference_entry
from app.apa.parsing.span_format import apply_format_to_existing_text_span
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import effective_italic

SOURCE_REF_CONTENT = SourceRef(
    official_resource=(
        "APA Style reference examples / Publication Manual (7th ed.) "
        "Reference List and Reference Examples guidance"
    ),
    publication_manual_section=None,
    notes=(
        "Reference content structure varies by source type. Forma APA reports "
        "likely issues for author review and never rewrites reference characters."
    ),
    source_verified=True,
)

SOURCE_REF_ITALICS = SourceRef(
    official_resource="APA Style reference examples — italicization of source titles",
    publication_manual_section=None,
    notes=(
        "Journal titles and some book titles are italicized. Automatic italics "
        "require confident type + exact run-aligned span."
    ),
    source_verified=True,
)


def _ensure_analyses(context: RuleContext):
    if context.reference_analyses:
        return context.reference_analyses
    analyses = []
    for item in context.classified:
        if item.region == Region.REFERENCE_ENTRY and item.text.strip():
            analyses.append(parse_reference_entry(item.index, item.text))
    context.reference_analyses = analyses
    return analyses


def _detect_missing_date(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.type_confidence < 0.85:
            continue
        if analysis.date_span is None:
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-DATE-MISSING",
                    category="Reference Content",
                    message=(
                        f"Reference paragraph {analysis.paragraph_index} may be missing "
                        "a publication date element."
                    ),
                    expected="(Year) after author element",
                    actual="date element not clearly detected",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=min(analysis.type_confidence, 0.88),
                    source=SOURCE_REF_CONTENT,
                    reason_not_fixable="Adding or changing a date would modify author text.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _detect_missing_author(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.type_confidence < 0.85:
            continue
        if analysis.author_span is None:
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-AUTHOR-MISSING",
                    category="Reference Content",
                    message=(
                        f"Reference paragraph {analysis.paragraph_index} may be missing "
                        "a clear author element."
                    ),
                    expected="author element before date",
                    actual="author element not clearly detected",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=min(analysis.type_confidence, 0.86),
                    source=SOURCE_REF_CONTENT,
                    reason_not_fixable="Generating author names would invent content.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _detect_title_case_warning(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.type_confidence < 0.9 or analysis.title_span is None:
            continue
        title = analysis.title_span.text
        words = [w for w in re.findall(r"[A-Za-z0-9']+", title) if w]
        if len(words) < 4:
            continue
        # Sentence case expectation for article titles: many capitals after first may be off.
        caps = sum(1 for w in words[1:] if w[:1].isupper() and len(w) > 3)
        if caps >= max(2, len(words) // 2):
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-TITLE-CASE",
                    category="Reference Content",
                    message=(
                        f"Reference paragraph {analysis.paragraph_index} title capitalization "
                        "may not follow the APA rule for this source type."
                    ),
                    expected="appropriate APA capitalization for source type",
                    actual="possible title-case overuse",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.75,
                    source=SOURCE_REF_CONTENT,
                    reason_not_fixable="Changing capitalization would modify author text.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _detect_doi_url(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.reference_type != ReferenceType.JOURNAL_ARTICLE:
            continue
        if analysis.type_confidence < 0.9:
            continue
        if analysis.doi_span is None and analysis.url_span is None:
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-DOI-MISSING",
                    category="Reference Content",
                    message=(
                        f"Journal reference paragraph {analysis.paragraph_index} may be "
                        "missing a DOI or URL when one is available."
                    ),
                    expected="DOI or URL when available",
                    actual="DOI/URL not clearly detected",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.7,
                    source=SOURCE_REF_CONTENT,
                    reason_not_fixable="Inserting a DOI/URL would invent content.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
        if analysis.doi_span and not re.search(
            r"10\.\d{4,9}/", analysis.doi_span.text
        ):
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-DOI-SUSPICIOUS",
                    category="Reference Content",
                    message=(
                        f"Reference paragraph {analysis.paragraph_index} may contain a "
                        "malformed DOI presentation."
                    ),
                    expected="DOI beginning with 10.",
                    actual="DOI-like text did not match expected pattern",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_REF_CONTENT,
                    reason_not_fixable="Changing DOI characters is never automatic.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _detect_unknown_type(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.reference_type == ReferenceType.UNKNOWN:
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-TYPE-UNKNOWN",
                    category="Reference Content",
                    message=(
                        f"Reference paragraph {analysis.paragraph_index} could not be "
                        "classified confidently by source type."
                    ),
                    expected="recognizable APA reference source type",
                    actual="unknown",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.CONDITIONAL,
                    can_fix=False,
                    confidence=analysis.type_confidence,
                    source=SOURCE_REF_CONTENT,
                    reason_not_fixable="Unknown types must not be force-formatted.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type="unknown",
                )
            )
    return issues


def _detect_journal_italics(context: RuleContext) -> list[Issue]:
    from app.apa.parsing.span_format import can_format_existing_text_span

    issues = []
    for item in context.classified:
        if item.region != Region.REFERENCE_ENTRY or item.confidence < 0.95:
            continue
        analysis = parse_reference_entry(item.index, item.text)
        if (
            analysis.reference_type != ReferenceType.JOURNAL_ARTICLE
            or analysis.type_confidence < 0.9
            or analysis.journal_span is None
        ):
            continue

        dry = can_format_existing_text_span(
            item.paragraph,
            analysis.journal_span.start,
            analysis.journal_span.end,
        )
        if not dry.unsafe_to_format:
            cursor = 0
            already = True
            for run in item.paragraph.runs:
                text = run.text or ""
                start, end = cursor, cursor + len(text)
                cursor = end
                if end <= analysis.journal_span.start or start >= analysis.journal_span.end:
                    continue
                if run.font.italic is not True:
                    already = False
                    break
            if already:
                continue
            issues.append(
                Issue(
                    rule_id="APA7-REFTYPO-JOURNAL-ITALIC",
                    category="References",
                    message=(
                        f"Journal title in reference paragraph {item.index} should be italic."
                    ),
                    expected="italic journal title",
                    actual="journal title not italic",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=min(analysis.type_confidence, 0.95),
                    source=SOURCE_REF_ITALICS,
                    paragraph_index=item.index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=item.index,
                    reference_type=analysis.reference_type.value,
                )
            )
        else:
            if effective_italic(item.paragraph) is True:
                continue
            issues.append(
                Issue(
                    rule_id="APA7-REFTYPO-JOURNAL-ITALIC-AUTHOR",
                    category="Reference Content",
                    message=(
                        f"Journal title in reference paragraph {item.index} may need "
                        "italics, but automatic span formatting was not safe."
                    ),
                    expected="italic journal title",
                    actual="unable to safely auto-format span",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_REF_ITALICS,
                    reason_not_fixable=(
                        "Exact run-aligned italic formatting could not be guaranteed."
                    ),
                    paragraph_index=item.index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=item.index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _fix_journal_italic(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    analysis = parse_reference_entry(issue.paragraph_index, paragraph.text)
    if analysis.journal_span is None:
        return False
    result = apply_format_to_existing_text_span(
        paragraph,
        analysis.journal_span.start,
        analysis.journal_span.end,
        italic=True,
    )
    return bool(result.applied and not result.unsafe_to_format)


def _filter(rule_id: str, detector):
    def _detect(context: RuleContext) -> list[Issue]:
        return [i for i in detector(context) if i.rule_id == rule_id]

    return _detect


RULES = [
    BaseRule(
        rule_id="APA7-REFCONTENT-DATE-MISSING",
        category="Reference Content",
        description="Likely missing reference date element.",
        official_expectation="Include date element when applicable",
        source=SOURCE_REF_CONTENT,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_missing_date,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-AUTHOR-MISSING",
        category="Reference Content",
        description="Likely missing reference author element.",
        official_expectation="Include author element when applicable",
        source=SOURCE_REF_CONTENT,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_missing_author,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-TITLE-CASE",
        category="Reference Content",
        description="Reference title capitalization may need review.",
        official_expectation="APA capitalization for source type",
        source=SOURCE_REF_CONTENT,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_title_case_warning,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-DOI-MISSING",
        category="Reference Content",
        description="Journal reference may be missing DOI/URL.",
        official_expectation="Include DOI or URL when available",
        source=SOURCE_REF_CONTENT,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-DOI-MISSING", _detect_doi_url),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-DOI-SUSPICIOUS",
        category="Reference Content",
        description="DOI presentation may be malformed.",
        official_expectation="Valid DOI presentation",
        source=SOURCE_REF_CONTENT,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-DOI-SUSPICIOUS", _detect_doi_url),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-TYPE-UNKNOWN",
        category="Reference Content",
        description="Reference type could not be classified confidently.",
        official_expectation="Recognizable source type",
        source=SOURCE_REF_CONTENT,
        fixability=Fixability.CONDITIONAL,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_unknown_type,
        fixer=None,
        production_supported=False,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFTYPO-JOURNAL-ITALIC",
        category="References",
        description="Journal title italics when span is safely run-aligned.",
        official_expectation="Italicize journal title",
        source=SOURCE_REF_ITALICS,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFTYPO-JOURNAL-ITALIC", _detect_journal_italics),
        fixer=_fix_journal_italic,
        minimum_confidence=0.9,
        # Production only when fixtures prove whole-run safety; keep gated false by default
        # until fixture demonstrates run-aligned journal span. Detector still emits AUTHOR fallback.
        production_supported=False,
        fixer_implemented=True,
        detector_test=True,
        fixer_test=True,
        text_integrity_test=True,
    ),
    BaseRule(
        rule_id="APA7-REFTYPO-JOURNAL-ITALIC-AUTHOR",
        category="Reference Content",
        description="Journal title may need italics (unsafe to auto-format).",
        official_expectation="Italicize journal title",
        source=SOURCE_REF_ITALICS,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFTYPO-JOURNAL-ITALIC-AUTHOR", _detect_journal_italics),
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
]
