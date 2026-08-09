"""Table formatting / detection rules (Phase 2D). Never invent labels or rewrite cell text."""

from __future__ import annotations

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.tables import analyze_tables
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import (
    clear_extra_paragraph_spacing,
    effective_bold,
    effective_italic,
    is_left_aligned_or_default,
    set_left_aligned,
    set_runs_bold,
    set_runs_italic,
    set_flush_left_no_first_indent,
)

SOURCE_TABLES = SourceRef(
    official_resource=(
        "APA Style Table Setup Guide; Publication Manual (7th ed.) Tables and Figures"
    ),
    publication_manual_section=None,
    notes=(
        "Table number appears above the table in bold, flush left, using Arabic numerals. "
        "Table title appears below the number in italic title case, flush left. "
        "Notes appear below the table. Call out every table in text by number. "
        "Do not invent table numbers, titles, notes, or callouts."
    ),
    source_verified=True,
)

SAFE_CONF = 0.95


def _ensure_tables(context: RuleContext):
    if context.table_analyses:
        return context.table_analyses
    context.table_analyses = analyze_tables(context.doc)
    return context.table_analyses


def _detect_number_format(context: RuleContext) -> list[Issue]:
    issues = []
    for table in _ensure_tables(context):
        if not table.is_apa_candidate or table.number_paragraph_index is None:
            continue
        if table.confidence < SAFE_CONF:
            continue
        paragraph = context.doc.paragraphs[table.number_paragraph_index]
        bold = effective_bold(paragraph)
        left = is_left_aligned_or_default(paragraph)
        if bold is False or not left:
            issues.append(
                Issue(
                    rule_id="APA7-TABLE-NUMBER-FORMAT",
                    category="Tables",
                    message=(
                        f"Table number at paragraph {table.number_paragraph_index} should be "
                        "bold and flush left."
                    ),
                    expected="bold, flush left",
                    actual="incorrect formatting",
                    location=f"paragraph[{table.number_paragraph_index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=table.confidence,
                    source=SOURCE_TABLES,
                    paragraph_index=table.number_paragraph_index,
                    section_index=table.table_index,
                    region=Region.TABLE_NUMBER,
                )
            )
    return issues


def _fix_number_format(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    set_runs_bold(paragraph, True)
    set_left_aligned(paragraph)
    set_flush_left_no_first_indent(paragraph)
    clear_extra_paragraph_spacing(paragraph)
    return True


def _detect_title_format(context: RuleContext) -> list[Issue]:
    issues = []
    for table in _ensure_tables(context):
        if not table.is_apa_candidate or table.title_paragraph_index is None:
            continue
        if table.confidence < SAFE_CONF or table.number_paragraph_index is None:
            continue
        if "title_without_confident_number" in table.warnings:
            continue
        paragraph = context.doc.paragraphs[table.title_paragraph_index]
        italic = effective_italic(paragraph)
        left = is_left_aligned_or_default(paragraph)
        if italic is False or not left:
            issues.append(
                Issue(
                    rule_id="APA7-TABLE-TITLE-FORMAT",
                    category="Tables",
                    message=(
                        f"Table title at paragraph {table.title_paragraph_index} should be "
                        "italic and flush left."
                    ),
                    expected="italic, flush left",
                    actual="incorrect formatting",
                    location=f"paragraph[{table.title_paragraph_index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=table.confidence,
                    source=SOURCE_TABLES,
                    paragraph_index=table.title_paragraph_index,
                    section_index=table.table_index,
                    region=Region.TABLE_TITLE,
                )
            )
    return issues


def _fix_title_format(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    set_runs_italic(paragraph, True)
    set_left_aligned(paragraph)
    set_flush_left_no_first_indent(paragraph)
    clear_extra_paragraph_spacing(paragraph)
    return True


def _detect_missing_number(context: RuleContext) -> list[Issue]:
    issues = []
    for table in _ensure_tables(context):
        # Only report for multi-cell non-layout tables that look scholarly but lack numbers.
        if table.is_apa_candidate:
            continue
        if "uncaptioned_grid_table" not in table.warnings:
            continue
        if table.row_count < 2 or table.column_count < 2:
            continue
        issues.append(
            Issue(
                rule_id="APA7-TABLE-NUMBER-MISSING",
                category="Tables",
                message=(
                    f"Table {table.table_index} appears to be a data table without a "
                    "detectable table number. Add an author-written Table N label."
                ),
                expected="Table N above table",
                actual="missing",
                location=f"table[{table.table_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.7,
                source=SOURCE_TABLES,
                reason_not_fixable="Must not invent table numbers",
                section_index=table.table_index,
                region=Region.TABLE,
            )
        )
    return issues


def _detect_missing_title(context: RuleContext) -> list[Issue]:
    issues = []
    for table in _ensure_tables(context):
        if not table.is_apa_candidate or table.confidence < 0.9:
            continue
        if table.number_paragraph_index is not None and table.title_paragraph_index is None:
            issues.append(
                Issue(
                    rule_id="APA7-TABLE-TITLE-MISSING",
                    category="Tables",
                    message=(
                        f"Table {table.number_value or table.table_index} has a number but "
                        "no confidently associated title."
                    ),
                    expected="italic title below table number",
                    actual="missing",
                    location=f"table[{table.table_index}]",
                    severity=Severity.WARNING,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=table.confidence,
                    source=SOURCE_TABLES,
                    reason_not_fixable="Must not invent table titles",
                    paragraph_index=table.number_paragraph_index,
                    section_index=table.table_index,
                    region=Region.TABLE_TITLE,
                )
            )
    return issues


def _detect_callout_missing(context: RuleContext) -> list[Issue]:
    issues = []
    for table in _ensure_tables(context):
        if not table.is_apa_candidate or table.number_value is None:
            continue
        if table.callout_locations:
            continue
        issues.append(
            Issue(
                rule_id="APA7-TABLE-CALLOUT-MISSING",
                category="Tables",
                message=(
                    f"Table {table.number_value} does not appear to be mentioned in the text. "
                    "Refer to every table by number."
                ),
                expected=f"in-text callout to Table {table.number_value}",
                actual="no callout detected",
                location=f"table[{table.table_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.85,
                source=SOURCE_TABLES,
                reason_not_fixable="Must not insert callout prose",
                section_index=table.table_index,
                region=Region.TABLE,
            )
        )
    return issues


def _detect_note_format(context: RuleContext) -> list[Issue]:
    issues = []
    for table in _ensure_tables(context):
        if not table.is_apa_candidate or table.confidence < SAFE_CONF:
            continue
        for n_idx in table.note_paragraph_indices:
            paragraph = context.doc.paragraphs[n_idx]
            if not is_left_aligned_or_default(paragraph):
                issues.append(
                    Issue(
                        rule_id="APA7-TABLE-NOTE-FORMAT",
                        category="Tables",
                        message=f"Table note at paragraph {n_idx} should be flush left.",
                        expected="flush left",
                        actual="not flush left",
                        location=f"paragraph[{n_idx}]",
                        severity=Severity.ERROR,
                        fixability=Fixability.SAFE_AUTO_FIX,
                        can_fix=True,
                        confidence=table.confidence,
                        source=SOURCE_TABLES,
                        paragraph_index=n_idx,
                        section_index=table.table_index,
                        region=Region.TABLE_NOTE,
                    )
                )
    return issues


def _fix_note_format(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    set_left_aligned(paragraph)
    set_flush_left_no_first_indent(paragraph)
    return True


def _detect_borders_full_grid(context: RuleContext) -> list[Issue]:
    issues = []
    for table in _ensure_tables(context):
        if not table.is_apa_candidate:
            continue
        if table.merged_cells or table.border_state != "full_grid":
            continue
        issues.append(
            Issue(
                rule_id="APA7-TABLE-BORDERS-FULL-GRID",
                category="Tables",
                message=(
                    f"Table {table.table_index} appears to use full-grid borders. "
                    "APA tables typically use limited horizontal rules; review manually."
                ),
                expected="minimal horizontal rules",
                actual="full_grid",
                location=f"table[{table.table_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.75,
                source=SOURCE_TABLES,
                reason_not_fixable="Automatic border rewriting risks destroying semantic grouping",
                section_index=table.table_index,
                region=Region.TABLE,
            )
        )
    return issues


def _detect_borders_complex(context: RuleContext) -> list[Issue]:
    issues = []
    for table in _ensure_tables(context):
        if not table.is_apa_candidate:
            continue
        if not (table.merged_cells or table.border_state == "unknown"):
            continue
        issues.append(
            Issue(
                rule_id="APA7-TABLE-BORDERS-COMPLEX",
                category="Tables",
                message=(
                    f"Table {table.table_index} has complex or uncertain borders; "
                    "automatic border restyling is not applied."
                ),
                expected="APA-compatible minimal rules when structure is clear",
                actual=table.border_state,
                location=f"table[{table.table_index}]",
                severity=Severity.INFO,
                fixability=Fixability.UNSUPPORTED,
                can_fix=False,
                confidence=0.6,
                source=SOURCE_TABLES,
                reason_not_fixable="Border changes require confident structure; never rebuild tables",
                section_index=table.table_index,
                region=Region.TABLE,
            )
        )
    return issues


def _detect_placement(context: RuleContext) -> list[Issue]:
    tables = [t for t in _ensure_tables(context) if t.is_apa_candidate]
    if not tables:
        return []
    return [
        Issue(
            rule_id="APA7-TABLE-PLACEMENT",
            category="Tables",
            message=(
                "Table placement may be embedded after callout or after the reference list; "
                "instructor requirements vary. Forma APA does not move tables."
            ),
            expected="instructor-approved placement",
            actual="not auto-evaluated for relocation",
            location="document",
            severity=Severity.INFO,
            fixability=Fixability.CONDITIONAL,
            can_fix=False,
            confidence=0.5,
            source=SOURCE_TABLES,
            reason_not_fixable="Moving tables would relocate user content",
            region=Region.TABLE,
        )
    ]


def _detect_body_spacing_policy(context: RuleContext) -> list[Issue]:
    if not _ensure_tables(context):
        return []
    return [
        Issue(
            rule_id="APA7-TABLE-BODY-SPACING",
            category="Tables",
            message=(
                "APA allows table body spacing to vary for readability. "
                "Forma APA does not force double spacing inside table cells."
            ),
            expected="readable table spacing",
            actual="not auto-forced to double",
            location="tables",
            severity=Severity.INFO,
            fixability=Fixability.UNSUPPORTED,
            can_fix=False,
            confidence=1.0,
            source=SOURCE_TABLES,
            reason_not_fixable="Forcing cell spacing risks readability and is not required",
            region=Region.TABLE,
        )
    ]


RULES = [
    BaseRule(
        rule_id="APA7-TABLE-NUMBER-FORMAT",
        category="Tables",
        description="Table number bold and flush left",
        official_expectation="Table number above table, bold, flush left, Arabic numerals",
        source=SOURCE_TABLES,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.TABLE_NUMBER.value,),
        detector=_detect_number_format,
        fixer=_fix_number_format,
        minimum_confidence=SAFE_CONF,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
        preservation_test=True,
    ),
    BaseRule(
        rule_id="APA7-TABLE-TITLE-FORMAT",
        category="Tables",
        description="Table title italic and flush left",
        official_expectation="Table title italic, flush left, below number",
        source=SOURCE_TABLES,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.TABLE_TITLE.value,),
        detector=_detect_title_format,
        fixer=_fix_title_format,
        minimum_confidence=SAFE_CONF,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
        preservation_test=True,
    ),
    BaseRule(
        rule_id="APA7-TABLE-NOTE-FORMAT",
        category="Tables",
        description="Existing table note flush left",
        official_expectation="Table notes flush left below table",
        source=SOURCE_TABLES,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.TABLE_NOTE.value,),
        detector=_detect_note_format,
        fixer=_fix_note_format,
        minimum_confidence=SAFE_CONF,
        production_supported=True,
        fixer_implemented=True,
        passing_fixture=True,
        failing_fixture=True,
        detector_test=True,
        fixer_test=True,
        post_fix_test=True,
        text_integrity_test=True,
        idempotency_test=True,
        preservation_test=True,
    ),
    BaseRule(
        rule_id="APA7-TABLE-NUMBER-MISSING",
        category="Tables",
        description="Missing table number requires author action",
        official_expectation="Every table has a Table N label",
        source=SOURCE_TABLES,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.TABLE.value,),
        detector=_detect_missing_number,
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-TABLE-TITLE-MISSING",
        category="Tables",
        description="Missing table title requires author action",
        official_expectation="Every table has a descriptive title",
        source=SOURCE_TABLES,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.TABLE_TITLE.value,),
        detector=_detect_missing_title,
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-TABLE-CALLOUT-MISSING",
        category="Tables",
        description="Missing table callout requires author action",
        official_expectation="Refer to every table by number in text",
        source=SOURCE_TABLES,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.TABLE.value,),
        detector=_detect_callout_missing,
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-TABLE-BORDERS-FULL-GRID",
        category="Tables",
        description="Full-grid borders need author review",
        official_expectation="APA tables generally use limited horizontal rules",
        source=SOURCE_TABLES,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.TABLE.value,),
        detector=_detect_borders_full_grid,
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-TABLE-BORDERS-COMPLEX",
        category="Tables",
        description="Complex table borders unsupported for auto-fix",
        official_expectation="Preserve complex table structure",
        source=SOURCE_TABLES,
        fixability=Fixability.UNSUPPORTED,
        applicable_regions=(Region.TABLE.value,),
        detector=_detect_borders_complex,
        production_supported=False,
        detector_implemented=True,
    ),
    BaseRule(
        rule_id="APA7-TABLE-PLACEMENT",
        category="Tables",
        description="Table placement is instructor-dependent",
        official_expectation="Embed after callout or place after references per instructor",
        source=SOURCE_TABLES,
        fixability=Fixability.CONDITIONAL,
        applicable_regions=(Region.TABLE.value,),
        detector=_detect_placement,
        production_supported=False,
    ),
    BaseRule(
        rule_id="APA7-TABLE-BODY-SPACING",
        category="Tables",
        description="Do not force double spacing in table bodies",
        official_expectation="Table body spacing may vary for readability",
        source=SOURCE_TABLES,
        fixability=Fixability.UNSUPPORTED,
        applicable_regions=(Region.TABLE.value,),
        detector=_detect_body_spacing_policy,
        production_supported=False,
    ),
]
