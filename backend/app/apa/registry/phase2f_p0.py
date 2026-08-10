"""Phase 2F P0 AUTHOR-analysis rules (detector-only; never rewrite characters)."""

from __future__ import annotations

import re

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.appendices import analyze_appendices
from app.apa.parsing.citations import CitationType
from app.apa.parsing.figures import analyze_figures
from app.apa.parsing.group_authors import (
    extract_introduced_abbreviation,
    looks_like_group_author_name,
)
from app.apa.parsing.matching import MatchStatus, _ref_year, _year_base, _year_suffix
from app.apa.parsing.tables import analyze_tables
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.citation_reference_matching import _ensure_match_data
from app.apa.registry.citations import _ensure_citations
from app.apa.registry.headings import (
    LEVEL_REGIONS,
    _level_items,
    _looks_like_title_case_violation,
)
from app.apa.registry.references_content import _ensure_analyses

SOURCE_CITE = SourceRef(
    official_resource=(
        "APA Style in-text citations guidance; Publication Manual (7th ed.) "
        "Works Credited in the Text"
    ),
    publication_manual_section=None,
    notes=(
        "Group authors, no-author works, no-date works, and same-year letter "
        "disambiguation are analyzed for author review. Forma APA never rewrites "
        "citation or reference characters."
    ),
    source_verified=True,
)

SOURCE_REF = SourceRef(
    official_resource=(
        "APA Style reference list / DOI and URL guidance; Publication Manual "
        "(7th ed.) Reference List"
    ),
    publication_manual_section=None,
    notes=(
        "DOI presentation commonly uses the https://doi.org/ form. URL and DOI "
        "characters are never rewritten by Fix."
    ),
    source_verified=True,
)

SOURCE_HEAD = SourceRef(
    official_resource="APA Style Headings guidance; Publication Manual (7th ed.) headings",
    publication_manual_section=None,
    notes="Heading hierarchy and title case are author-reviewed; levels are never auto-changed.",
    source_verified=True,
)

SOURCE_TF = SourceRef(
    official_resource=(
        "APA Style Table Setup Guide / Figure Setup Guide; Publication Manual "
        "(7th ed.) Tables and Figures"
    ),
    publication_manual_section=None,
    notes=(
        "Table/figure title case and column/stub completeness are author-reviewed. "
        "Appendix-specific identifiers are analyzed but never rewritten."
    ),
    source_verified=True,
)

SOURCE_MATCH = SourceRef(
    official_resource=(
        "APA Style guidance on citations and reference lists; Publication Manual "
        "(7th ed.) Works Credited in the Text / Reference List"
    ),
    publication_manual_section=None,
    notes=(
        "Ambiguous matches and personal-communication exemptions are reported "
        "conservatively. Personal communications generally do not appear in the "
        "reference list."
    ),
    source_verified=True,
)


def _detect_ambiguous_match(context: RuleContext) -> list[Issue]:
    _cites, _refs, matches = _ensure_match_data(context)
    issues = []
    for match in matches:
        if match.status != MatchStatus.AMBIGUOUS:
            continue
        if match.citation_index is None:
            continue
        cite = next(
            (c for c in context.citations if c.citation_index == match.citation_index),
            None,
        )
        if cite is None:
            continue
        issues.append(
            Issue(
                rule_id="APA7-MATCH-AMBIGUOUS",
                category="Citation Matching",
                message=(
                    f"A citation in paragraph {cite.paragraph_index} may match more than "
                    "one reference entry (or could not be matched confidently) and should "
                    "be reviewed."
                ),
                expected="unique confident citation↔reference correspondence",
                actual=match.reason or "ambiguous",
                location=f"paragraph[{cite.paragraph_index}]",
                severity=Severity.INFO,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=min(0.75, match.confidence or 0.7),
                source=SOURCE_MATCH,
                reason_not_fixable="Ambiguous matches must not be auto-resolved.",
                paragraph_index=cite.paragraph_index,
                region=Region.BODY,
                citation_index=cite.citation_index,
                match_status=match.status.value,
            )
        )
    return issues


def _detect_personal_comm_in_references(context: RuleContext) -> list[Issue]:
    cites, refs, _matches = _ensure_match_data(context)
    personal_cites = [c for c in cites if c.is_personal_communication]
    issues = []
    for ref in refs:
        text = (ref.raw_text or "").lower()
        if "personal communication" not in text:
            continue
        # High confidence when citation also identifies personal communication,
        # or when the reference entry itself explicitly labels it.
        confidence = 0.92 if personal_cites else 0.9
        issues.append(
            Issue(
                rule_id="APA7-MATCH-PERSONAL-COMM-IN-REFS",
                category="Citation Matching",
                message=(
                    f"Reference paragraph {ref.paragraph_index} appears to describe a "
                    "personal communication. APA generally excludes personal "
                    "communications from the reference list."
                ),
                expected="personal communications cited in text only",
                actual="possible personal communication in reference list",
                location=f"paragraph[{ref.paragraph_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=confidence,
                source=SOURCE_MATCH,
                reason_not_fixable="Deleting reference entries is never automatic.",
                paragraph_index=ref.paragraph_index,
                region=Region.REFERENCE_ENTRY,
                reference_index=ref.paragraph_index,
                match_status=MatchStatus.EXEMPT_OR_SPECIAL_CASE.value,
            )
        )
    return issues


def _detect_group_author_review(context: RuleContext) -> list[Issue]:
    issues = []
    for cite in _ensure_citations(context):
        if cite.citation_type != CitationType.GROUP_AUTHOR and not any(
            looks_like_group_author_name(a) for a in cite.possible_authors
        ):
            continue
        intro = extract_introduced_abbreviation(cite.raw_text)
        if intro:
            continue  # introduction present in this span
        # Later-only abbreviation without known intro in document → review.
        authors = cite.possible_authors
        if authors and re.fullmatch(r"[A-Z]{2,12}", authors[0].strip()):
            issues.append(
                Issue(
                    rule_id="APA7-CITATION-GROUP-AUTHOR",
                    category="Citations",
                    message=(
                        f"A group-author citation in paragraph {cite.paragraph_index} "
                        "uses an abbreviation that may need review for a prior "
                        "full-name introduction."
                    ),
                    expected="introduce group author abbreviation where APA requires it",
                    actual="abbreviation without clear introduction in this citation",
                    location=f"paragraph[{cite.paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.78,
                    source=SOURCE_CITE,
                    reason_not_fixable="Inserting/expanding abbreviations would modify text.",
                    paragraph_index=cite.paragraph_index,
                    region=Region.BODY,
                    citation_index=cite.citation_index,
                )
            )
    return issues


def _detect_same_year_suffix(context: RuleContext) -> list[Issue]:
    cites, refs, matches = _ensure_match_data(context)
    issues = []
    # Group references by author key + year base
    buckets: dict[tuple[str, str], list] = {}
    for ref in refs:
        year = _ref_year(ref)
        base = _year_base(year)
        if not base or base == "n.d.":
            continue
        author = (ref.author_span.text if ref.author_span else "")[:80]
        if not author:
            continue
        key_author = re.sub(r"[^a-z0-9]+", " ", author.lower()).strip()
        buckets.setdefault((key_author, base), []).append(ref)

    for (_author, _year), group in buckets.items():
        if len(group) < 2:
            continue
        suffixes = {_year_suffix(_ref_year(r)) for r in group}
        if None in suffixes and len(group) >= 2:
            for ref in group:
                issues.append(
                    Issue(
                        rule_id="APA7-REFCONTENT-SAME-YEAR-SUFFIX",
                        category="Reference Content",
                        message=(
                            f"Reference paragraph {ref.paragraph_index} appears to share "
                            "an author and year with another entry and may need a "
                            "year-letter suffix (a, b, ...) for disambiguation."
                        ),
                        expected="disambiguating year letter when required",
                        actual="same-author same-year entries without clear suffixes",
                        location=f"paragraph[{ref.paragraph_index}]",
                        severity=Severity.WARNING,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.86,
                        source=SOURCE_CITE,
                        reason_not_fixable="Appending year letters would modify author text.",
                        paragraph_index=ref.paragraph_index,
                        region=Region.REFERENCE_ENTRY,
                        reference_index=ref.paragraph_index,
                    )
                )

    # Citation/reference suffix inconsistency when uniquely matched
    for match in matches:
        if match.status != MatchStatus.MATCHED:
            continue
        cite = next((c for c in cites if c.citation_index == match.citation_index), None)
        ref = next((r for r in refs if r.paragraph_index == match.reference_index), None)
        if cite is None or ref is None or not cite.possible_year:
            continue
        cs = _year_suffix(cite.possible_year)
        rs = _year_suffix(_ref_year(ref))
        if cs and rs and cs != rs:
            issues.append(
                Issue(
                    rule_id="APA7-CITATION-YEAR-SUFFIX-MISMATCH",
                    category="Citations",
                    message=(
                        f"A citation in paragraph {cite.paragraph_index} appears to use a "
                        "year letter that may not match the corresponding reference."
                    ),
                    expected="consistent year-letter suffix across citation and reference",
                    actual="possible suffix mismatch",
                    location=f"paragraph[{cite.paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.88,
                    source=SOURCE_CITE,
                    reason_not_fixable="Changing year characters is never automatic.",
                    paragraph_index=cite.paragraph_index,
                    region=Region.BODY,
                    citation_index=cite.citation_index,
                    reference_index=ref.paragraph_index,
                    match_status=match.status.value,
                )
            )
    return issues


def _detect_no_date_review(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        text = analysis.raw_text or ""
        has_nd = bool(re.search(r"\(n\.d\.\)", text, re.I))
        has_year = bool(re.search(r"\(\d{4}[a-z]?\)", text))
        if has_nd or has_year:
            continue
        # Author-like start but no date parenthesis — may need n.d. or a date.
        if analysis.author_span and analysis.date_span is None:
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-NO-DATE-REVIEW",
                    category="Reference Content",
                    message=(
                        f"Reference paragraph {analysis.paragraph_index} may be missing a "
                        "date element. If no date is available, APA uses n.d."
                    ),
                    expected="(year) or (n.d.) when applicable",
                    actual="date element not clearly detected",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.72,
                    source=SOURCE_CITE,
                    reason_not_fixable="Inserting n.d. or a year would modify author text.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _detect_no_author_review(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.author_span is not None:
            continue
        if analysis.type_confidence < 0.7:
            continue
        # Title-first / no-author pattern: starts with quote or italic-like title then date
        text = (analysis.raw_text or "").strip()
        if re.match(r"^[\"“].+\(\d{4}|n\.d\.\)", text):
            # Valid-looking no-author — no warning
            continue
        if analysis.date_span and analysis.title_span:
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-NO-AUTHOR-REVIEW",
                    category="Reference Content",
                    message=(
                        f"Reference paragraph {analysis.paragraph_index} may use a "
                        "no-author format or may be missing an author element. Please review."
                    ),
                    expected="author element or valid APA no-author title format",
                    actual="author element not clearly detected",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.7,
                    source=SOURCE_CITE,
                    reason_not_fixable="Inventing an author name is never automatic.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _detect_same_author_order(context: RuleContext) -> list[Issue]:
    refs = _ensure_analyses(context)
    issues = []
    # Within same first-author key, years should be non-decreasing by base year then suffix.
    by_author: dict[str, list] = {}
    for ref in refs:
        if not ref.author_span:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", ref.author_span.text.lower()).strip()
        key = key.split(",")[0].strip()
        by_author.setdefault(key, []).append(ref)

    for author, group in by_author.items():
        if len(group) < 2:
            continue
        years = []
        for ref in group:
            y = _ref_year(ref)
            base = _year_base(y)
            if not base or base == "n.d.":
                years.append((9999, _year_suffix(y) or "", ref))
            else:
                years.append((int(base), _year_suffix(y) or "", ref))
        ordered = sorted(years, key=lambda t: (t[0], t[1]))
        actual = [(t[0], t[1]) for t in years]
        expected = [(t[0], t[1]) for t in ordered]
        if actual != expected:
            issues.append(
                Issue(
                    rule_id="APA7-REFERENCE-SAME-AUTHOR-ORDER",
                    category="Reference Content",
                    message=(
                        f"References for author '{author[:40]}' may be out of APA "
                        "same-author chronological order."
                    ),
                    expected="same-author works ordered by year (and year letter)",
                    actual="possible out-of-order same-author entries",
                    location=f"paragraph[{group[0].paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.84,
                    source=SOURCE_REF,
                    reason_not_fixable="Reordering reference paragraphs is never automatic.",
                    paragraph_index=group[0].paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=group[0].paragraph_index,
                )
            )
    return issues


def _detect_doi_presentation(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.doi_span is None:
            continue
        text = analysis.doi_span.text.strip()
        if re.search(r"10\.\d{4,9}/", text) and not re.search(
            r"https?://doi\.org/", text, re.I
        ):
            # Present as doi:10... or bare 10... — APA 7 prefers https://doi.org/
            if re.match(r"(?i)doi:\s*10\.", text) or re.match(r"10\.\d{4,9}/", text):
                issues.append(
                    Issue(
                        rule_id="APA7-REFCONTENT-DOI-PRESENTATION",
                        category="Reference Content",
                        message=(
                            f"Reference paragraph {analysis.paragraph_index} may not use "
                            "the expected https://doi.org/ DOI presentation."
                        ),
                        expected="https://doi.org/10.... form when presenting a DOI",
                        actual="DOI detected without https://doi.org/ prefix",
                        location=f"paragraph[{analysis.paragraph_index}]",
                        severity=Severity.INFO,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.85,
                        source=SOURCE_REF,
                        reason_not_fixable="Changing DOI characters is never automatic.",
                        paragraph_index=analysis.paragraph_index,
                        region=Region.REFERENCE_ENTRY,
                        reference_index=analysis.paragraph_index,
                        reference_type=analysis.reference_type.value,
                    )
                )
    return issues


def _detect_url_presentation(context: RuleContext) -> list[Issue]:
    issues = []
    for analysis in _ensure_analyses(context):
        if analysis.url_span is None:
            continue
        url = analysis.url_span.text.strip()
        # Trailing period often accidental in prose-like refs
        if url.endswith(".") and "doi.org" not in url.lower():
            issues.append(
                Issue(
                    rule_id="APA7-REFCONTENT-URL-PRESENTATION",
                    category="Reference Content",
                    message=(
                        f"Reference paragraph {analysis.paragraph_index} may include "
                        "a URL with trailing punctuation that should be reviewed."
                    ),
                    expected="URL presentation without unintended trailing punctuation",
                    actual="URL appears to end with a period",
                    location=f"paragraph[{analysis.paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_REF,
                    reason_not_fixable="Changing URL characters is never automatic.",
                    paragraph_index=analysis.paragraph_index,
                    region=Region.REFERENCE_ENTRY,
                    reference_index=analysis.paragraph_index,
                    reference_type=analysis.reference_type.value,
                )
            )
    return issues


def _detect_heading_hierarchy(context: RuleContext) -> list[Issue]:
    issues = []
    seq: list[tuple[int, int, float]] = []  # level, index, conf
    for item in context.classified:
        if item.heading_level is None:
            continue
        if item.region not in LEVEL_REGIONS.values() and item.region != Region.HEADING:
            continue
        if item.region in {
            Region.REFERENCES_HEADING,
            Region.ABSTRACT_HEADING,
            Region.APPENDIX_LABEL,
        }:
            continue
        if item.confidence < 0.9:
            continue
        seq.append((item.heading_level, item.index, item.confidence))

    prev_level = None
    for level, index, conf in seq:
        if prev_level is not None and level > prev_level + 1:
            issues.append(
                Issue(
                    rule_id="APA7-HEADING-HIERARCHY",
                    category="Headings",
                    message=(
                        f"Heading at paragraph {index} appears to skip a level "
                        f"(from Level {prev_level} to Level {level}) and may need review."
                    ),
                    expected="heading levels advance without skips",
                    actual=f"possible skip {prev_level}→{level}",
                    location=f"paragraph[{index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=min(0.85, conf),
                    source=SOURCE_HEAD,
                    reason_not_fixable="Changing heading levels/styles automatically is unsafe.",
                    paragraph_index=index,
                    region=LEVEL_REGIONS.get(level, Region.HEADING),
                )
            )
        prev_level = level
    return issues


def _detect_heading45_title_case(context: RuleContext) -> list[Issue]:
    issues = []
    for level in (4, 5):
        for item in _level_items(context, level, min_conf=0.9):
            heading_part = item.text.split(".", 1)[0] if "." in item.text else item.text
            if _looks_like_title_case_violation(heading_part):
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
                        source=SOURCE_HEAD,
                        reason_not_fixable="Changing capitalization would modify author text.",
                        paragraph_index=item.index,
                        region=LEVEL_REGIONS[level],
                    )
                )
    return issues


def _detect_table_figure_title_case(context: RuleContext) -> list[Issue]:
    issues = []
    if not context.table_analyses:
        context.table_analyses = analyze_tables(context.doc)
    if not context.figure_analyses:
        context.figure_analyses = analyze_figures(context.doc)

    for table in context.table_analyses:
        if not table.is_apa_candidate or table.title_paragraph_index is None:
            continue
        if table.confidence < 0.95:
            continue
        text = context.doc.paragraphs[table.title_paragraph_index].text
        if _looks_like_title_case_violation(text):
            issues.append(
                Issue(
                    rule_id="APA7-TABLE-TITLE-CASE",
                    category="Tables",
                    message=(
                        f"Table title at paragraph {table.title_paragraph_index} may not "
                        "use APA title case."
                    ),
                    expected="title case",
                    actual="possible non-title-case",
                    location=f"paragraph[{table.title_paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.82,
                    source=SOURCE_TF,
                    reason_not_fixable="Changing capitalization would modify author text.",
                    paragraph_index=table.title_paragraph_index,
                    section_index=table.table_index,
                    region=Region.TABLE_TITLE,
                )
            )

    for fig in context.figure_analyses:
        if not fig.is_apa_candidate or fig.title_paragraph_index is None:
            continue
        if fig.confidence < 0.95:
            continue
        text = context.doc.paragraphs[fig.title_paragraph_index].text
        if _looks_like_title_case_violation(text):
            issues.append(
                Issue(
                    rule_id="APA7-FIGURE-TITLE-CASE",
                    category="Figures",
                    message=(
                        f"Figure title at paragraph {fig.title_paragraph_index} may not "
                        "use APA title case."
                    ),
                    expected="title case",
                    actual="possible non-title-case",
                    location=f"paragraph[{fig.title_paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.82,
                    source=SOURCE_TF,
                    reason_not_fixable="Changing capitalization would modify author text.",
                    paragraph_index=fig.title_paragraph_index,
                    section_index=fig.figure_index,
                    region=Region.FIGURE_TITLE,
                )
            )
    return issues


def _detect_table_column_headings(context: RuleContext) -> list[Issue]:
    issues = []
    if not context.table_analyses:
        context.table_analyses = analyze_tables(context.doc)
    for table in context.table_analyses:
        if not table.is_apa_candidate or table.confidence < 0.95:
            continue
        if table.merged_cells or table.row_count < 2 or table.column_count < 2:
            continue
        doc_table = context.doc.tables[table.table_index]
        header_cells = [c.text.strip() for c in doc_table.rows[0].cells]
        if any(not h for h in header_cells):
            issues.append(
                Issue(
                    rule_id="APA7-TABLE-COLUMN-HEADING",
                    category="Tables",
                    message=(
                        f"Table {table.table_index} appears to be missing one or more "
                        "column/stub heading labels."
                    ),
                    expected="heading text for each column including stub",
                    actual="empty header cell(s) detected",
                    location=f"table[{table.table_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_TF,
                    reason_not_fixable="Inventing heading text is never automatic.",
                    section_index=table.table_index,
                    region=Region.TABLE,
                )
            )
    return issues


_APPENDIX_TABLE_RE = re.compile(r"^table\s+([A-Z])(\d+)\s*$", re.I)
_APPENDIX_FIGURE_RE = re.compile(r"^figure\s+([A-Z])(\d+)\s*$", re.I)


def _detect_appendix_object_numbering(context: RuleContext) -> list[Issue]:
    issues = []
    if not context.appendix_analyses:
        context.appendix_analyses = analyze_appendices(context.doc)
    if not context.table_analyses:
        context.table_analyses = analyze_tables(context.doc)
    if not context.figure_analyses:
        context.figure_analyses = analyze_figures(context.doc)

    appendix_letters = {
        a.label_letter.upper()
        for a in context.appendix_analyses
        if a.label_letter and a.confidence >= 0.9
    }
    if not appendix_letters and not context.appendix_analyses:
        return []

    for table in context.table_analyses:
        if table.number_paragraph_index is None or not table.number_text:
            continue
        # Only analyze when table number is inside/after an appendix region.
        near_appendix = any(
            a.label_paragraph_index is not None
            and table.number_paragraph_index >= a.label_paragraph_index
            for a in context.appendix_analyses
            if a.confidence >= 0.9
        )
        if not near_appendix:
            continue
        m = _APPENDIX_TABLE_RE.match(table.number_text.strip())
        if not m:
            # Uses Table 1 style inside appendix — may need Table A1
            if re.match(r"^table\s+\d+\s*$", table.number_text.strip(), re.I):
                issues.append(
                    Issue(
                        rule_id="APA7-APPENDIX-TABLE-NUMBERING",
                        category="Appendices",
                        message=(
                            f"A table number at paragraph {table.number_paragraph_index} "
                            "appears inside an appendix and may need appendix-specific "
                            "numbering (for example, Table A1)."
                        ),
                        expected="appendix-specific table identifier when applicable",
                        actual=table.number_text,
                        location=f"paragraph[{table.number_paragraph_index}]",
                        severity=Severity.WARNING,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.8,
                        source=SOURCE_TF,
                        reason_not_fixable="Changing table identifiers would modify author text.",
                        paragraph_index=table.number_paragraph_index,
                        section_index=table.table_index,
                        region=Region.TABLE_NUMBER,
                    )
                )
            continue
        letter = m.group(1).upper()
        if appendix_letters and letter not in appendix_letters:
            issues.append(
                Issue(
                    rule_id="APA7-APPENDIX-TABLE-NUMBERING",
                    category="Appendices",
                    message=(
                        f"Table identifier '{table.number_text}' may not match the "
                        "detected appendix label letter."
                    ),
                    expected="table letter consistent with appendix label",
                    actual=table.number_text,
                    location=f"paragraph[{table.number_paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.78,
                    source=SOURCE_TF,
                    reason_not_fixable="Changing table identifiers would modify author text.",
                    paragraph_index=table.number_paragraph_index,
                    section_index=table.table_index,
                    region=Region.TABLE_NUMBER,
                )
            )

    for fig in context.figure_analyses:
        if fig.number_paragraph_index is None or not fig.number_text:
            continue
        near_appendix = any(
            a.label_paragraph_index is not None
            and fig.number_paragraph_index >= a.label_paragraph_index
            for a in context.appendix_analyses
            if a.confidence >= 0.9
        )
        if not near_appendix:
            continue
        if re.match(r"^figure\s+\d+\s*$", fig.number_text.strip(), re.I):
            issues.append(
                Issue(
                    rule_id="APA7-APPENDIX-FIGURE-NUMBERING",
                    category="Appendices",
                    message=(
                        f"A figure number at paragraph {fig.number_paragraph_index} "
                        "appears inside an appendix and may need appendix-specific "
                        "numbering (for example, Figure A1)."
                    ),
                    expected="appendix-specific figure identifier when applicable",
                    actual=fig.number_text,
                    location=f"paragraph[{fig.number_paragraph_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.8,
                    source=SOURCE_TF,
                    reason_not_fixable="Changing figure identifiers would modify author text.",
                    paragraph_index=fig.number_paragraph_index,
                    section_index=fig.figure_index,
                    region=Region.FIGURE_NUMBER,
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
        rule_id="APA7-MATCH-AMBIGUOUS",
        category="Citation Matching",
        description="Ambiguous citation↔reference correspondence.",
        official_expectation="Unique match or careful author review",
        source=SOURCE_MATCH,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_detect_ambiguous_match,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-MATCH-PERSONAL-COMM-IN-REFS",
        category="Citation Matching",
        description="Personal communication appears in reference list.",
        official_expectation="Personal communications generally omitted from references",
        source=SOURCE_MATCH,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_personal_comm_in_references,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-CITATION-GROUP-AUTHOR",
        category="Citations",
        description="Group-author abbreviation introduction review.",
        official_expectation="Introduce group-author abbreviations where required",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_detect_group_author_review,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-SAME-YEAR-SUFFIX",
        category="Reference Content",
        description="Same-author same-year may need year letter.",
        official_expectation="Use a, b, ... year letters when required",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_filter("APA7-REFCONTENT-SAME-YEAR-SUFFIX", _detect_same_year_suffix),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-CITATION-YEAR-SUFFIX-MISMATCH",
        category="Citations",
        description="Citation/reference year-letter inconsistency.",
        official_expectation="Consistent year-letter suffixes",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_filter("APA7-CITATION-YEAR-SUFFIX-MISMATCH", _detect_same_year_suffix),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-NO-DATE-REVIEW",
        category="Reference Content",
        description="Possible missing date / n.d. review.",
        official_expectation="Include date or n.d. when applicable",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_no_date_review,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-NO-AUTHOR-REVIEW",
        category="Reference Content",
        description="Possible no-author format or missing author.",
        official_expectation="Author element or valid no-author format",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_no_author_review,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFERENCE-SAME-AUTHOR-ORDER",
        category="Reference Content",
        description="Same-author reference chronological order review.",
        official_expectation="Same-author works ordered by year",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_same_author_order,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-DOI-PRESENTATION",
        category="Reference Content",
        description="DOI presentation may need https://doi.org/ form.",
        official_expectation="https://doi.org/ DOI presentation",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_doi_presentation,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-REFCONTENT-URL-PRESENTATION",
        category="Reference Content",
        description="URL presentation may need review.",
        official_expectation="Clean URL presentation",
        source=SOURCE_REF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_url_presentation,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-HEADING-HIERARCHY",
        category="Headings",
        description="Possible skipped heading level.",
        official_expectation="Heading levels without skips",
        source=SOURCE_HEAD,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("HEADING",),
        detector=_detect_heading_hierarchy,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-HEADING4-TITLECASE",
        category="Headings",
        description="Level 4 title-case review.",
        official_expectation="Level 4 title case",
        source=SOURCE_HEAD,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_4_HEADING",),
        detector=_filter("APA7-HEADING4-TITLECASE", _detect_heading45_title_case),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-HEADING5-TITLECASE",
        category="Headings",
        description="Level 5 title-case review.",
        official_expectation="Level 5 title case",
        source=SOURCE_HEAD,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("LEVEL_5_HEADING",),
        detector=_filter("APA7-HEADING5-TITLECASE", _detect_heading45_title_case),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-TABLE-TITLE-CASE",
        category="Tables",
        description="Table title-case review.",
        official_expectation="Table title in title case",
        source=SOURCE_TF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TABLE_TITLE",),
        detector=_filter("APA7-TABLE-TITLE-CASE", _detect_table_figure_title_case),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-FIGURE-TITLE-CASE",
        category="Figures",
        description="Figure title-case review.",
        official_expectation="Figure title in title case",
        source=SOURCE_TF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("FIGURE_TITLE",),
        detector=_filter("APA7-FIGURE-TITLE-CASE", _detect_table_figure_title_case),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-TABLE-COLUMN-HEADING",
        category="Tables",
        description="Missing table column/stub heading text.",
        official_expectation="Column and stub headings present",
        source=SOURCE_TF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TABLE",),
        detector=_detect_table_column_headings,
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-APPENDIX-TABLE-NUMBERING",
        category="Appendices",
        description="Appendix table numbering review.",
        official_expectation="Appendix-specific table identifiers when applicable",
        source=SOURCE_TF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("TABLE_NUMBER", "APPENDIX"),
        detector=_filter("APA7-APPENDIX-TABLE-NUMBERING", _detect_appendix_object_numbering),
        **_AUTHOR,
    ),
    BaseRule(
        rule_id="APA7-APPENDIX-FIGURE-NUMBERING",
        category="Appendices",
        description="Appendix figure numbering review.",
        official_expectation="Appendix-specific figure identifiers when applicable",
        source=SOURCE_TF,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("FIGURE_NUMBER", "APPENDIX"),
        detector=_filter("APA7-APPENDIX-FIGURE-NUMBERING", _detect_appendix_object_numbering),
        **_AUTHOR,
    ),
]
