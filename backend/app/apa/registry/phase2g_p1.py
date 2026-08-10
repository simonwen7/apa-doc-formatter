"""Phase 2G P1 AUTHOR-analysis rules (mostly detector-only; never rewrite characters)."""

from __future__ import annotations

import re
from typing import Optional

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.citations import CitationType
from app.apa.parsing.matching import MatchStatus
from app.apa.parsing.reference_entry import ReferenceType
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.citation_reference_matching import _ensure_match_data
from app.apa.registry.references_content import _ensure_analyses

SOURCE_TITLE = SourceRef(
    official_resource="APA Style Student Paper Setup Guide; Student title page",
    publication_manual_section=None,
    notes=(
        "Student title pages may list multiple authors and affiliations. "
        "Forma APA never invents author names, commas, 'and', or superscript markers."
    ),
    source_verified=True,
)

SOURCE_REF = SourceRef(
    official_resource=(
        "APA Style reference examples / Publication Manual (7th ed.) Reference List"
    ),
    publication_manual_section=None,
    notes=(
        "Source-type-aware completeness is reviewed for author action only. "
        "Missing components are never invented."
    ),
    source_verified=True,
)

SOURCE_CITE = SourceRef(
    official_resource=(
        "APA Style in-text citations guidance; Publication Manual (7th ed.) "
        "Works Credited in the Text"
    ),
    publication_manual_section=None,
    notes=(
        "One- and two-author citation forms differ for parenthetical vs narrative "
        "uses. Characters are never rewritten."
    ),
    source_verified=True,
)


def _dedupe_key(reference_index: int, component: str, reason: str) -> tuple:
    return (reference_index, component, reason)


def _detect_multi_author_title_page(context: RuleContext) -> list[Issue]:
    authors = [
        item
        for item in context.classified
        if item.region == Region.TITLE_PAGE
        and item.title_element == "author"
        and item.confidence >= 0.8
        and item.text.strip()
    ]
    affiliations = [
        item
        for item in context.classified
        if item.region == Region.TITLE_PAGE
        and item.title_element == "affiliation"
        and item.confidence >= 0.8
    ]
    issues: list[Issue] = []
    if len(authors) >= 2 and len(affiliations) >= 2:
        issues.append(
            Issue(
                rule_id="APA7-TITLE-MULTI-AFFILIATION",
                category="Title Page",
                message=(
                    "Multiple authors and multiple affiliations appear on the title "
                    "page. Please review whether APA affiliation markers are needed; "
                    "Forma APA never inserts superscript numbers or reassigns authors."
                ),
                expected="clear author–affiliation correspondence when required",
                actual="multiple authors and affiliations detected",
                location="title_page",
                severity=Severity.INFO,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.8,
                source=SOURCE_TITLE,
                reason_not_fixable=(
                    "Inserting affiliation markers or reordering authors would modify text."
                ),
                region=Region.TITLE_PAGE,
            )
        )
    elif len(authors) >= 2:
        # Informational support signal — not an error; used for coverage/tests.
        issues.append(
            Issue(
                rule_id="APA7-TITLE-MULTI-AUTHOR",
                category="Title Page",
                message=(
                    f"Multiple author lines ({len(authors)}) were detected on the "
                    "student title page. Review author order and affiliation grouping "
                    "if needed."
                ),
                expected="author names listed according to APA student title-page guidance",
                actual=f"{len(authors)} author paragraphs detected",
                location="title_page",
                severity=Severity.INFO,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.82,
                source=SOURCE_TITLE,
                reason_not_fixable="Author names and joining punctuation are never rewritten.",
                region=Region.TITLE_PAGE,
            )
        )
    return issues


def _detect_affiliation_structure(context: RuleContext) -> list[Issue]:
    affiliations = [
        item
        for item in context.classified
        if item.region == Region.TITLE_PAGE
        and item.title_element == "affiliation"
        and item.confidence >= 0.84
        and item.text.strip()
    ]
    if not affiliations:
        return []
    issues = []
    for item in affiliations:
        text = item.text.strip()
        # Soft check: academic unit vs institution cues. Do not require "Department".
        has_unit = bool(
            re.search(
                r"\b(department|school|program|faculty|centre|center|college)\b",
                text,
                re.I,
            )
        )
        has_institution = bool(
            re.search(
                r"\b(university|institute|academy|polytechnic|college)\b",
                text,
                re.I,
            )
        )
        if has_institution and not has_unit and "," not in text:
            issues.append(
                Issue(
                    rule_id="APA7-TITLE-AFFILIATION-STRUCTURE",
                    category="Title Page",
                    message=(
                        f"Affiliation on paragraph {item.index} may be missing an "
                        "academic unit (for example a department, school, or program) "
                        "alongside the institution."
                    ),
                    expected="academic unit and institution when required by APA",
                    actual="institution-like affiliation without clear unit cue",
                    location=f"paragraph[{item.index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.72,
                    source=SOURCE_TITLE,
                    reason_not_fixable="Generating department/institution text is never automatic.",
                    paragraph_index=item.index,
                    region=Region.TITLE_PAGE,
                )
            )
    return issues


# Component expectations by reference type (high-confidence only).


def _missing_journal_source(analysis) -> Optional[str]:
    if analysis.journal_span is None and analysis.source_span is None:
        return "journal_or_source"
    if analysis.journal_span is None and analysis.source_span:
        # source present but no journal-like name before comma
        if not re.match(r"\s*[^,]+,", analysis.source_span.text):
            return "journal_name"
    return None


def _missing_book_publisher(analysis) -> Optional[str]:
    if analysis.source_span is None:
        return "publisher_or_source"
    src = analysis.source_span.text
    if not re.search(r"[A-Za-z]", src):
        return "publisher_or_source"
    # Old APA location pattern "City, ST: Publisher" — flag as review only if clear.
    return None


def _missing_webpage_source(analysis) -> Optional[str]:
    if analysis.url_span is None and analysis.source_span is None:
        return "site_or_url"
    return None


def _missing_report_source(analysis) -> Optional[str]:
    if analysis.source_span is None:
        return "publisher_or_source"
    return None


def _missing_preprint_source(analysis) -> Optional[str]:
    text = analysis.raw_text.lower()
    if not re.search(r"preprint|arxiv|psyarxiv|biorxiv|ssrn|osf", text):
        return "repository_or_status"
    return None


def _missing_video_source(analysis) -> Optional[str]:
    if analysis.url_span is None:
        return "url"
    return None


def _missing_social_source(analysis) -> Optional[str]:
    if analysis.url_span is None:
        return "url"
    return None


_COMPLETENESS_CHECKS = {
    ReferenceType.JOURNAL_ARTICLE: ("APA7-REFCONTENT-JOURNAL-SOURCE", _missing_journal_source),
    ReferenceType.BOOK: ("APA7-REFCONTENT-BOOK-SOURCE", _missing_book_publisher),
    ReferenceType.EBOOK: ("APA7-REFCONTENT-BOOK-SOURCE", _missing_book_publisher),
    ReferenceType.WEBPAGE: ("APA7-REFCONTENT-WEBPAGE-SOURCE", _missing_webpage_source),
    ReferenceType.REPORT: ("APA7-REFCONTENT-REPORT-SOURCE", _missing_report_source),
    ReferenceType.GOVERNMENT_REPORT: ("APA7-REFCONTENT-REPORT-SOURCE", _missing_report_source),
    ReferenceType.ORGANIZATION_REPORT: ("APA7-REFCONTENT-REPORT-SOURCE", _missing_report_source),
    ReferenceType.PREPRINT: ("APA7-REFCONTENT-PREPRINT-SOURCE", _missing_preprint_source),
    ReferenceType.ONLINE_VIDEO: ("APA7-REFCONTENT-VIDEO-SOURCE", _missing_video_source),
    ReferenceType.SOCIAL_MEDIA: ("APA7-REFCONTENT-SOCIAL-SOURCE", _missing_social_source),
    ReferenceType.NEWSPAPER_ARTICLE: ("APA7-REFCONTENT-PERIODICAL-SOURCE", _missing_journal_source),
    ReferenceType.MAGAZINE_ARTICLE: ("APA7-REFCONTENT-PERIODICAL-SOURCE", _missing_journal_source),
}


def _detect_source_completeness(context: RuleContext) -> list[Issue]:
    issues = []
    seen: set[tuple] = set()
    for analysis in _ensure_analyses(context):
        if analysis.type_confidence < 0.85:
            continue
        if analysis.reference_type == ReferenceType.UNKNOWN:
            continue
        check = _COMPLETENESS_CHECKS.get(analysis.reference_type)
        if not check:
            continue
        rule_id, fn = check
        missing = fn(analysis)
        if not missing:
            continue
        key = _dedupe_key(analysis.paragraph_index, missing, rule_id)
        if key in seen:
            continue
        seen.add(key)
        issues.append(
            Issue(
                rule_id=rule_id,
                category="Reference Content",
                message=(
                    f"This {analysis.reference_type.value.replace('_', ' ')} reference "
                    f"(paragraph {analysis.paragraph_index}) may be missing "
                    f"{missing.replace('_', ' ')} information."
                ),
                expected=f"complete {analysis.reference_type.value} source elements",
                actual=f"possible missing component: {missing}",
                location=f"paragraph[{analysis.paragraph_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=min(0.86, analysis.type_confidence),
                source=SOURCE_REF,
                reason_not_fixable="Inventing missing source elements would modify author text.",
                paragraph_index=analysis.paragraph_index,
                region=Region.REFERENCE_ENTRY,
                reference_index=analysis.paragraph_index,
                reference_type=analysis.reference_type.value,
            )
        )
    return issues


def _detect_journal_components(context: RuleContext) -> list[Issue]:
    issues = []
    seen: set[tuple] = set()
    for analysis in _ensure_analyses(context):
        if analysis.reference_type != ReferenceType.JOURNAL_ARTICLE:
            continue
        if analysis.type_confidence < 0.85:
            continue
        if analysis.volume_span is None and analysis.source_span:
            key = _dedupe_key(analysis.paragraph_index, "volume", "journal_volume")
            if key not in seen:
                seen.add(key)
                issues.append(
                    Issue(
                        rule_id="APA7-REFCONTENT-JOURNAL-VOLUME",
                        category="Reference Content",
                        message=(
                            f"This journal reference (paragraph {analysis.paragraph_index}) "
                            "may be missing volume/issue information."
                        ),
                        expected="volume (and issue when applicable)",
                        actual="volume/issue not clearly detected",
                        location=f"paragraph[{analysis.paragraph_index}]",
                        severity=Severity.INFO,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.78,
                        source=SOURCE_REF,
                        reason_not_fixable="Adding volume/issue characters is never automatic.",
                        paragraph_index=analysis.paragraph_index,
                        region=Region.REFERENCE_ENTRY,
                        reference_index=analysis.paragraph_index,
                        reference_type=analysis.reference_type.value,
                    )
                )
    return issues


def _detect_publisher_location_legacy(context: RuleContext) -> list[Issue]:
    """APA 7 generally omits publisher location — text change = AUTHOR only."""
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.reference_type not in {ReferenceType.BOOK, ReferenceType.EBOOK}:
            continue
        if analysis.type_confidence < 0.8 or not analysis.source_span:
            continue
        # Pattern like "New York, NY: Publisher"
        if re.search(
            r"\b[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}\s*:",
            analysis.source_span.text,
        ):
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-PUBLISHER-LOCATION",
                    category="Reference Content",
                    message=(
                        f"Book reference paragraph {analysis.paragraph_index} may include "
                        "a publisher location that APA 7 generally no longer requires."
                    ),
                    expected="publisher name without location when APA 7 applies",
                    actual="possible City, ST: Publisher pattern",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_REF,
                    reason_not_fixable="Removing location text would modify author characters.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _detect_one_two_author_citations(context: RuleContext) -> list[Issue]:
    cites, refs, matches = _ensure_match_data(context)
    issues = []
    for cite in cites:
        if cite.confidence < 0.9:
            continue
        authors = [a for a in cite.possible_authors if a and "et al" not in a.lower()]
        # Narrative regex may capture "Smith & Jones" as one token — split for analysis.
        if len(authors) == 1 and re.search(r"\s(?:&|and)\s", authors[0]):
            authors = [
                p.strip()
                for p in re.split(r"\s+&\s+|\s+and\s+", authors[0])
                if p.strip()
            ]
        if cite.citation_type in {CitationType.MULTIPLE_SOURCE, CitationType.GROUP_AUTHOR}:
            continue
        match = next((m for m in matches if m.citation_index == cite.citation_index), None)
        if match and match.status == MatchStatus.AMBIGUOUS:
            continue

        if len(authors) == 1 and cite.citation_type in {
            CitationType.PARENTHETICAL,
            CitationType.NARRATIVE,
            CitationType.DIRECT_QUOTE,
        }:
            issues.append(
                Issue(
                    rule_id="APA7-CITATION-ONE-AUTHOR",
                    category="Citations",
                    message=(
                        f"A one-author citation in paragraph {cite.paragraph_index} was "
                        "detected. Please confirm the author–year form matches the "
                        "corresponding reference."
                    ),
                    expected="consistent one-author APA citation form",
                    actual=cite.citation_type.value,
                    location=f"paragraph[{cite.paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_CITE,
                    reason_not_fixable="Citation characters are never rewritten.",
                    paragraph_index=cite.paragraph_index,
                    region=Region.BODY,
                    citation_index=cite.citation_index,
                    match_status=match.status.value if match else None,
                )
            )
        elif len(authors) == 2:
            raw = cite.raw_text
            is_parenthetical = cite.citation_type == CitationType.PARENTHETICAL or (
                raw.startswith("(") and raw.endswith(")")
            )
            # Parenthetical typically uses & ; narrative typically uses "and".
            if is_parenthetical and re.search(r"\sand\s", raw) and "&" not in raw:
                issues.append(
                    Issue(
                        rule_id="APA7-CITATION-TWO-AUTHOR",
                        category="Citations",
                        message=(
                            f"This two-author citation in paragraph {cite.paragraph_index} "
                            "may not use the expected APA parenthetical author format."
                        ),
                        expected="ampersand (&) joining authors in parenthetical citations",
                        actual="uses 'and' in a parenthetical citation",
                        location=f"paragraph[{cite.paragraph_index}]",
                        severity=Severity.WARNING,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.86,
                        source=SOURCE_CITE,
                        reason_not_fixable="Changing &/and would modify author text.",
                        paragraph_index=cite.paragraph_index,
                        region=Region.BODY,
                        citation_index=cite.citation_index,
                        match_status=match.status.value if match else None,
                    )
                )
            elif (
                cite.citation_type == CitationType.NARRATIVE
                and "&" in raw
                and not re.search(r"\sand\s", raw)
            ):
                issues.append(
                    Issue(
                        rule_id="APA7-CITATION-TWO-AUTHOR",
                        category="Citations",
                        message=(
                            f"This two-author citation in paragraph {cite.paragraph_index} "
                            "may not use the expected APA narrative author format."
                        ),
                        expected="'and' joining authors in narrative citations",
                        actual="uses '&' in a narrative citation",
                        location=f"paragraph[{cite.paragraph_index}]",
                        severity=Severity.WARNING,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.86,
                        source=SOURCE_CITE,
                        reason_not_fixable="Changing &/and would modify author text.",
                        paragraph_index=cite.paragraph_index,
                        region=Region.BODY,
                        citation_index=cite.citation_index,
                        match_status=match.status.value if match else None,
                    )
                )
            else:
                issues.append(
                    Issue(
                        rule_id="APA7-CITATION-TWO-AUTHOR",
                        category="Citations",
                        message=(
                            f"A two-author citation in paragraph {cite.paragraph_index} "
                            "was detected. Please confirm author order and joining form."
                        ),
                        expected="APA two-author parenthetical/narrative form",
                        actual=cite.citation_type.value,
                        location=f"paragraph[{cite.paragraph_index}]",
                        severity=Severity.INFO,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.8,
                        source=SOURCE_CITE,
                        reason_not_fixable="Citation characters are never rewritten.",
                        paragraph_index=cite.paragraph_index,
                        region=Region.BODY,
                        citation_index=cite.citation_index,
                        match_status=match.status.value if match else None,
                    )
                )
    return issues


def _filter(rule_id: str, detector):
    def _inner(context: RuleContext) -> list[Issue]:
        return [i for i in detector(context) if i.rule_id == rule_id]

    return _inner


_AUTHOR = dict(
    fixer=None,
    production_supported=True,
    detector_implemented=True,
    fixer_implemented=False,
    detector_test=True,
)


RULES = [
    BaseRule(
        rule_id="APA7-TITLE-MULTI-AUTHOR",
        category="Title Page",
        description="Multiple author lines detected on student title page.",
        official_expectation="Support multi-author student title pages",
        source=SOURCE_TITLE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TITLE_PAGE",),
        detector=_filter("APA7-TITLE-MULTI-AUTHOR", _detect_multi_author_title_page),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-TITLE-MULTI-AFFILIATION",
        category="Title Page",
        description="Multiple authors with multiple affiliations need review.",
        official_expectation="Author–affiliation correspondence without invented markers",
        source=SOURCE_TITLE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TITLE_PAGE",),
        detector=_filter("APA7-TITLE-MULTI-AFFILIATION", _detect_multi_author_title_page),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-TITLE-AFFILIATION-STRUCTURE",
        category="Title Page",
        description="Affiliation may need academic unit + institution structure.",
        official_expectation="Department/school/program and institution when required",
        source=SOURCE_TITLE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TITLE_PAGE",),
        detector=_detect_affiliation_structure,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-JOURNAL-SOURCE",
        category="Reference Content",
        description="Journal reference may be missing journal/source information.",
        official_expectation="Journal/source present for journal articles",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-JOURNAL-SOURCE", _detect_source_completeness),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-JOURNAL-VOLUME",
        category="Reference Content",
        description="Journal reference may be missing volume/issue.",
        official_expectation="Volume (and issue when applicable)",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_journal_components,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-BOOK-SOURCE",
        category="Reference Content",
        description="Book/ebook may be missing publisher/source.",
        official_expectation="Publisher/source for books",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-BOOK-SOURCE", _detect_source_completeness),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-PUBLISHER-LOCATION",
        category="Reference Content",
        description="Legacy publisher location may need APA 7 review.",
        official_expectation="Publisher without location under APA 7",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_publisher_location_legacy,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-WEBPAGE-SOURCE",
        category="Reference Content",
        description="Webpage reference may be missing site/URL details.",
        official_expectation="Site/source or URL when required",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-WEBPAGE-SOURCE", _detect_source_completeness),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-REPORT-SOURCE",
        category="Reference Content",
        description="Report reference may be missing publisher/source.",
        official_expectation="Publisher/source for reports",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-REPORT-SOURCE", _detect_source_completeness),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-PREPRINT-SOURCE",
        category="Reference Content",
        description="Preprint may be missing repository/status cues.",
        official_expectation="Preprint repository/status structure",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-PREPRINT-SOURCE", _detect_source_completeness),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-VIDEO-SOURCE",
        category="Reference Content",
        description="Online video may be missing URL/platform details.",
        official_expectation="URL for online video references",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-VIDEO-SOURCE", _detect_source_completeness),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-SOCIAL-SOURCE",
        category="Reference Content",
        description="Social-media reference may be missing URL.",
        official_expectation="URL for social-media references",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-SOCIAL-SOURCE", _detect_source_completeness),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-PERIODICAL-SOURCE",
        category="Reference Content",
        description="Newspaper/magazine may be missing source title.",
        official_expectation="Periodical source title",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-PERIODICAL-SOURCE", _detect_source_completeness),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-CITATION-ONE-AUTHOR",
        category="Citations",
        description="One-author citation review.",
        official_expectation="Consistent one-author citation form",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_filter("APA7-CITATION-ONE-AUTHOR", _detect_one_two_author_citations),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-CITATION-TWO-AUTHOR",
        category="Citations",
        description="Two-author citation form review.",
        official_expectation="APA & vs and by citation type",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_filter("APA7-CITATION-TWO-AUTHOR", _detect_one_two_author_citations),
        **_AUTHOR,
    ),
]
