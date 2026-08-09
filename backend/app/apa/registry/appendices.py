"""Appendix formatting / detection rules (Phase 2D). Never invent or rename labels."""

from __future__ import annotations

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.appendices import analyze_appendices
from app.apa.registry.base import BaseRule, RuleContext
from app.apa.registry.formatting import (
    clear_extra_paragraph_spacing,
    effective_bold,
    is_centered,
    page_break_before,
    set_centered,
    set_page_break_before,
    set_runs_bold,
)

SOURCE_APPENDIX = SourceRef(
    official_resource=(
        "APA Style student-paper guidance; Publication Manual (7th ed.) "
        "Paper Elements and Format / Appendices"
    ),
    publication_manual_section=None,
    notes=(
        "Each appendix begins on a separate page. The appendix label (Appendix or "
        "Appendix A, B, ...) and appendix title are typically centered and bold. "
        "Do not invent, rename, or reorder appendix labels. Refer to appendices in text."
    ),
    source_verified=True,
)

SAFE_CONF = 0.92


def _ensure_appendices(context: RuleContext):
    if context.appendix_analyses:
        return context.appendix_analyses
    context.appendix_analyses = analyze_appendices(context.doc)
    return context.appendix_analyses


def _detect_label_format(context: RuleContext) -> list[Issue]:
    issues = []
    for apx in _ensure_appendices(context):
        if apx.label_paragraph_index is None or apx.confidence < SAFE_CONF:
            continue
        paragraph = context.doc.paragraphs[apx.label_paragraph_index]
        bold = effective_bold(paragraph)
        centered = is_centered(paragraph)
        if bold is False or not centered:
            issues.append(
                Issue(
                    rule_id="APA7-APPENDIX-LABEL-FORMAT",
                    category="Appendices",
                    message=(
                        f"Appendix label at paragraph {apx.label_paragraph_index} should be "
                        "centered and bold."
                    ),
                    expected="centered, bold",
                    actual="incorrect formatting",
                    location=f"paragraph[{apx.label_paragraph_index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=apx.confidence,
                    source=SOURCE_APPENDIX,
                    paragraph_index=apx.label_paragraph_index,
                    section_index=apx.appendix_index,
                    region=Region.APPENDIX_LABEL,
                )
            )
    return issues


def _fix_label_format(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    set_runs_bold(paragraph, True)
    set_centered(paragraph)
    clear_extra_paragraph_spacing(paragraph)
    return True


def _detect_title_format(context: RuleContext) -> list[Issue]:
    issues = []
    for apx in _ensure_appendices(context):
        if apx.title_paragraph_index is None or apx.confidence < SAFE_CONF:
            continue
        paragraph = context.doc.paragraphs[apx.title_paragraph_index]
        bold = effective_bold(paragraph)
        centered = is_centered(paragraph)
        if bold is False or not centered:
            issues.append(
                Issue(
                    rule_id="APA7-APPENDIX-TITLE-FORMAT",
                    category="Appendices",
                    message=(
                        f"Appendix title at paragraph {apx.title_paragraph_index} should be "
                        "centered and bold."
                    ),
                    expected="centered, bold",
                    actual="incorrect formatting",
                    location=f"paragraph[{apx.title_paragraph_index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=apx.confidence,
                    source=SOURCE_APPENDIX,
                    paragraph_index=apx.title_paragraph_index,
                    section_index=apx.appendix_index,
                    region=Region.APPENDIX_TITLE,
                )
            )
    return issues


def _fix_title_format(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    paragraph = context.doc.paragraphs[issue.paragraph_index]
    set_runs_bold(paragraph, True)
    set_centered(paragraph)
    clear_extra_paragraph_spacing(paragraph)
    return True


def _detect_page_break(context: RuleContext) -> list[Issue]:
    issues = []
    for apx in _ensure_appendices(context):
        if apx.label_paragraph_index is None or apx.confidence < SAFE_CONF:
            continue
        paragraph = context.doc.paragraphs[apx.label_paragraph_index]
        if page_break_before(paragraph) is not True:
            issues.append(
                Issue(
                    rule_id="APA7-APPENDIX-PAGE-BREAK",
                    category="Appendices",
                    message=(
                        f"Appendix at paragraph {apx.label_paragraph_index} should begin "
                        "on a new page."
                    ),
                    expected="page break before appendix label",
                    actual="missing page_break_before",
                    location=f"paragraph[{apx.label_paragraph_index}]",
                    severity=Severity.ERROR,
                    fixability=Fixability.SAFE_AUTO_FIX,
                    can_fix=True,
                    confidence=apx.confidence,
                    source=SOURCE_APPENDIX,
                    paragraph_index=apx.label_paragraph_index,
                    section_index=apx.appendix_index,
                    region=Region.APPENDIX_LABEL,
                )
            )
    return issues


def _fix_page_break(context: RuleContext, issue: Issue) -> bool:
    if issue.paragraph_index is None:
        return False
    set_page_break_before(context.doc.paragraphs[issue.paragraph_index], True)
    return True


def _detect_callout_missing(context: RuleContext) -> list[Issue]:
    issues = []
    for apx in _ensure_appendices(context):
        if apx.confidence < 0.9:
            continue
        if apx.callout_locations:
            continue
        issues.append(
            Issue(
                rule_id="APA7-APPENDIX-CALLOUT-MISSING",
                category="Appendices",
                message=(
                    f"Appendix '{apx.label_text}' does not appear to be mentioned in the text."
                ),
                expected="in-text appendix callout",
                actual="no callout detected",
                location=f"appendix[{apx.appendix_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.8,
                source=SOURCE_APPENDIX,
                reason_not_fixable="Must not insert appendix callout text",
                paragraph_index=apx.label_paragraph_index,
                section_index=apx.appendix_index,
                region=Region.APPENDIX,
            )
        )
    return issues


def _detect_order_issues(context: RuleContext) -> list[Issue]:
    issues = []
    appendices = _ensure_appendices(context)
    letters = [a.label_letter for a in appendices if a.label_letter]
    if len(letters) != len(set(letters)):
        issues.append(
            Issue(
                rule_id="APA7-APPENDIX-DUPLICATE-LABEL",
                category="Appendices",
                message="Duplicate appendix labels detected. Review appendix labeling.",
                expected="unique appendix labels",
                actual="duplicate labels",
                location="appendices",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.9,
                source=SOURCE_APPENDIX,
                reason_not_fixable="Must not rename or relabel appendices",
                region=Region.APPENDIX,
            )
        )
    # Alphabetical order check only — never reorder.
    sorted_letters = sorted(letters)
    if letters and letters != sorted_letters:
        issues.append(
            Issue(
                rule_id="APA7-APPENDIX-ORDER",
                category="Appendices",
                message=(
                    "Appendix labels may be out of alphabetical order. "
                    "Forma APA will not reorder appendix content."
                ),
                expected="alphabetical appendix labels when lettered",
                actual="possible out-of-order labels",
                location="appendices",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.75,
                source=SOURCE_APPENDIX,
                reason_not_fixable="Must not reorder user appendix content",
                region=Region.APPENDIX,
            )
        )
    return issues


RULES = [
    BaseRule(
        rule_id="APA7-APPENDIX-LABEL-FORMAT",
        category="Appendices",
        description="Appendix label centered and bold",
        official_expectation="Appendix label centered and bold",
        source=SOURCE_APPENDIX,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.APPENDIX_LABEL.value,),
        detector=_detect_label_format,
        fixer=_fix_label_format,
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
        rule_id="APA7-APPENDIX-TITLE-FORMAT",
        category="Appendices",
        description="Appendix title centered and bold",
        official_expectation="Appendix title centered and bold",
        source=SOURCE_APPENDIX,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.APPENDIX_TITLE.value,),
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
        rule_id="APA7-APPENDIX-PAGE-BREAK",
        category="Appendices",
        description="Appendix begins on a new page",
        official_expectation="Each appendix starts on a separate page",
        source=SOURCE_APPENDIX,
        fixability=Fixability.SAFE_AUTO_FIX,
        applicable_regions=(Region.APPENDIX_LABEL.value,),
        detector=_detect_page_break,
        fixer=_fix_page_break,
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
        rule_id="APA7-APPENDIX-CALLOUT-MISSING",
        category="Appendices",
        description="Missing appendix callout",
        official_expectation="Refer to appendices in text where appropriate",
        source=SOURCE_APPENDIX,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.APPENDIX.value,),
        detector=_detect_callout_missing,
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-APPENDIX-DUPLICATE-LABEL",
        category="Appendices",
        description="Duplicate appendix labels",
        official_expectation="Unique appendix labels",
        source=SOURCE_APPENDIX,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.APPENDIX.value,),
        detector=lambda ctx: [
            i for i in _detect_order_issues(ctx) if i.rule_id == "APA7-APPENDIX-DUPLICATE-LABEL"
        ],
        production_supported=True,
    ),
    BaseRule(
        rule_id="APA7-APPENDIX-ORDER",
        category="Appendices",
        description="Appendix order analysis only",
        official_expectation="Letter appendices in order; do not auto-reorder",
        source=SOURCE_APPENDIX,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=(Region.APPENDIX.value,),
        detector=lambda ctx: [
            i for i in _detect_order_issues(ctx) if i.rule_id == "APA7-APPENDIX-ORDER"
        ],
        production_supported=True,
    ),
]
