"""Figure formatting / detection rules (Phase 2D). Never invent labels or alter image bytes."""

from __future__ import annotations

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.figures import analyze_figures
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import (
    clear_extra_paragraph_spacing,
    effective_bold,
    effective_italic,
    is_left_aligned_or_default,
    set_flush_left_no_first_indent,
    set_left_aligned,
    set_runs_bold,
    set_runs_italic,
)

SOURCE_FIGURES = SourceRef(
    official_resource=(
        "APA Style Figure Setup Guide; Publication Manual (7th ed.) Tables and Figures"
    ),
    publication_manual_section=None,
    notes=(
        "Figure number appears above the figure in bold, flush left. "
        "Figure title appears below the number in italic title case, flush left. "
        "Notes may appear below the figure. Call out every figure by number. "
        "Do not invent figure numbers, titles, notes, callouts, or alt text. "
        "Do not modify image binary content."
    ),
    source_verified=True,
)

SAFE_CONF = 0.95


def _ensure_figures(context: RuleContext):
    if context.figure_analyses:
        return context.figure_analyses
    context.figure_analyses = analyze_figures(context.doc)
    return context.figure_analyses


def _detect_number_format(context: RuleContext) -> list[Issue]:
    issues = []
    for fig in _ensure_figures(context):
        if not fig.is_apa_candidate or fig.number_paragraph_index is None:
            continue
        if fig.confidence < SAFE_CONF:
            continue
        paragraph = context.doc.paragraphs[fig.number_paragraph_index]
        bold = effective_bold(paragraph)
        left = is_left_aligned_or_default(paragraph)
        if bold is False or not left:
            issues.append(
                Issue(
                    rule_id="APA7-FIGURE-NUMBER-FORMAT",
                    category="Figures",
                    message=(
                        f"Figure number at paragraph {fig.number_paragraph_index} should be "
                        "bold and flush left."
                    ),
                    expected="bold, flush left",
                    actual="incorrect formatting",
                    location=f"paragraph[{fig.number_paragraph_index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=fig.confidence,
                    source=SOURCE_FIGURES,
                    paragraph_index=fig.number_paragraph_index,
                    section_index=fig.figure_index,
                    region=Region.FIGURE_NUMBER,
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
    for fig in _ensure_figures(context):
        if not fig.is_apa_candidate or fig.title_paragraph_index is None:
            continue
        if fig.confidence < SAFE_CONF or fig.number_paragraph_index is None:
            continue
        if "title_without_confident_number" in fig.warnings:
            continue
        paragraph = context.doc.paragraphs[fig.title_paragraph_index]
        italic = effective_italic(paragraph)
        left = is_left_aligned_or_default(paragraph)
        if italic is False or not left:
            issues.append(
                Issue(
                    rule_id="APA7-FIGURE-TITLE-FORMAT",
                    category="Figures",
                    message=(
                        f"Figure title at paragraph {fig.title_paragraph_index} should be "
                        "italic and flush left."
                    ),
                    expected="italic, flush left",
                    actual="incorrect formatting",
                    location=f"paragraph[{fig.title_paragraph_index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=fig.confidence,
                    source=SOURCE_FIGURES,
                    paragraph_index=fig.title_paragraph_index,
                    section_index=fig.figure_index,
                    region=Region.FIGURE_TITLE,
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


def _detect_missing_number_title(context: RuleContext) -> list[Issue]:
    issues = []
    for fig in _ensure_figures(context):
        if fig.is_apa_candidate:
            if fig.title_paragraph_index is None and fig.number_paragraph_index is not None:
                issues.append(
                    Issue(
                        rule_id="APA7-FIGURE-TITLE-MISSING",
                        category="Figures",
                        message=(
                            f"Figure {fig.number_value or fig.figure_index} has a number but "
                            "no confidently associated title."
                        ),
                        expected="italic title below figure number",
                        actual="missing",
                        location=f"figure[{fig.figure_index}]",
                        severity=Severity.WARNING,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=fig.confidence,
                        source=SOURCE_FIGURES,
                        reason_not_fixable="Must not invent figure titles",
                        paragraph_index=fig.number_paragraph_index,
                        section_index=fig.figure_index,
                        region=Region.FIGURE_TITLE,
                    )
                )
            continue
        # Uncaptioned images that look like candidates for author review only when not decorative.
        if "likely_decorative_or_logo" in fig.warnings:
            continue
        if "uncaptioned_image" in fig.warnings or "floating_uncaptioned_image" in fig.warnings:
            issues.append(
                Issue(
                    rule_id="APA7-FIGURE-NUMBER-MISSING",
                    category="Figures",
                    message=(
                        f"Image at paragraph {fig.image_paragraph_index} may be an APA figure "
                        "without a detectable figure number."
                    ),
                    expected="Figure N above figure",
                    actual="missing",
                    location=f"paragraph[{fig.image_paragraph_index}]",
                    severity=Severity.INFO,
                    fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                    can_fix=False,
                    confidence=0.55,
                    source=SOURCE_FIGURES,
                    reason_not_fixable="Must not invent figure numbers; may not be a figure",
                    paragraph_index=fig.image_paragraph_index,
                    section_index=fig.figure_index,
                    region=Region.FIGURE,
                )
            )
    return issues


def _detect_callout_missing(context: RuleContext) -> list[Issue]:
    issues = []
    for fig in _ensure_figures(context):
        if not fig.is_apa_candidate or fig.number_value is None:
            continue
        if fig.callout_locations:
            continue
        issues.append(
            Issue(
                rule_id="APA7-FIGURE-CALLOUT-MISSING",
                category="Figures",
                message=(
                    f"Figure {fig.number_value} does not appear to be mentioned in the text."
                ),
                expected=f"in-text callout to Figure {fig.number_value}",
                actual="no callout detected",
                location=f"figure[{fig.figure_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.85,
                source=SOURCE_FIGURES,
                reason_not_fixable="Must not insert callout prose",
                section_index=fig.figure_index,
                region=Region.FIGURE,
            )
        )
    return issues


def _detect_note_format(context: RuleContext) -> list[Issue]:
    issues = []
    for fig in _ensure_figures(context):
        if not fig.is_apa_candidate or fig.confidence < SAFE_CONF:
            continue
        for n_idx in fig.note_paragraph_indices:
            paragraph = context.doc.paragraphs[n_idx]
            if not is_left_aligned_or_default(paragraph):
                issues.append(
                    Issue(
                        rule_id="APA7-FIGURE-NOTE-FORMAT",
                        category="Figures",
                        message=f"Figure note at paragraph {n_idx} should be flush left.",
                        expected="flush left",
                        actual="not flush left",
                        location=f"paragraph[{n_idx}]",
                        severity=Severity.ERROR,
                        fixability=Fixability.SAFE_AUTO_FIX,
                        can_fix=True,
                        confidence=fig.confidence,
                        source=SOURCE_FIGURES,
                        paragraph_index=n_idx,
                        section_index=fig.figure_index,
                        region=Region.FIGURE_NOTE,
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


def _detect_alt_text(context: RuleContext) -> list[Issue]:
    issues = []
    for fig in _ensure_figures(context):
        if not fig.is_apa_candidate:
            continue
        if fig.alt_text_available:
            continue
        issues.append(
            Issue(
                rule_id="APA7-FIGURE-ALT-TEXT",
                category="Figures",
                message=(
                    f"Figure {fig.number_value or fig.figure_index} may lack a useful "
                    "alternative description. Review accessibility needs."
                ),
                expected="useful alternative description when required",
                actual="alt text not detected",
                location=f"figure[{fig.figure_index}]",
                severity=Severity.INFO,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.7,
                source=SOURCE_FIGURES,
                reason_not_fixable="Must not invent alt text for user figures",
                section_index=fig.figure_index,
                region=Region.FIGURE,
            )
        )
    return issues


def _detect_legend_embedded(context: RuleContext) -> list[Issue]:
    if not _ensure_figures(context):
        return []
    return [
        Issue(
            rule_id="APA7-FIGURE-LEGEND-EMBEDDED",
            category="Figures",
            message=(
                "Figure legends embedded inside image pixels cannot be automatically corrected."
            ),
            expected="external detectable legend text when editable",
            actual="unsupported for image-embedded legends",
            location="figures",
            severity=Severity.INFO,
            fixability=Fixability.UNSUPPORTED,
            can_fix=False,
            confidence=1.0,
            source=SOURCE_FIGURES,
            reason_not_fixable="Cannot edit text inside image binaries",
            region=Region.FIGURE_LEGEND,
        )
    ]


RULES = [
    BaseRule(
        rule_id="APA7-FIGURE-NUMBER-FORMAT",
        category="Figures",
        description="Figure number bold and flush left",
        official_expectation="Figure number above figure, bold, flush left",
        source=SOURCE_FIGURES,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.FIGURE_NUMBER.value,),
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
        rule_id="APA7-FIGURE-TITLE-FORMAT",
        category="Figures",
        description="Figure title italic and flush left",
        official_expectation="Figure title italic, flush left, below number",
        source=SOURCE_FIGURES,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.FIGURE_TITLE.value,),
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
        rule_id="APA7-FIGURE-NOTE-FORMAT",
        category="Figures",
        description="Existing figure note flush left",
        official_expectation="Figure notes flush left below figure",
        source=SOURCE_FIGURES,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.FIGURE_NOTE.value,),
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
        rule_id="APA7-FIGURE-NUMBER-MISSING",
        category="Figures",
        description="Possible figure without number",
        official_expectation="Figure N label above figure",
        source=SOURCE_FIGURES,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.FIGURE.value,),
        detector=lambda ctx: [
            i for i in _detect_missing_number_title(ctx) if i.rule_id == "APA7-FIGURE-NUMBER-MISSING"
        ],
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-FIGURE-TITLE-MISSING",
        category="Figures",
        description="Missing figure title",
        official_expectation="Descriptive italic title below figure number",
        source=SOURCE_FIGURES,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.FIGURE_TITLE.value,),
        detector=lambda ctx: [
            i for i in _detect_missing_number_title(ctx) if i.rule_id == "APA7-FIGURE-TITLE-MISSING"
        ],
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-FIGURE-CALLOUT-MISSING",
        category="Figures",
        description="Missing figure callout",
        official_expectation="Refer to every figure by number in text",
        source=SOURCE_FIGURES,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.FIGURE.value,),
        detector=_detect_callout_missing,
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-FIGURE-ALT-TEXT",
        category="Figures",
        description="Accessibility alternative description review",
        official_expectation="Provide useful alternative descriptions when required",
        source=SOURCE_FIGURES,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.FIGURE.value,),
        detector=_detect_alt_text,
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-FIGURE-LEGEND-EMBEDDED",
        category="Figures",
        description="Embedded image legends unsupported",
        official_expectation="Editable legend text outside image when possible",
        source=SOURCE_FIGURES,
        fixability=Fixability.UNSUPPORTED,
        applicable_regions=(Region.FIGURE_LEGEND.value,),
        detector=_detect_legend_embedded,
        production_supported=False,
    ),
]
