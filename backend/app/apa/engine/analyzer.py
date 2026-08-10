from __future__ import annotations

from docx import Document

from app.apa.engine.classifier import classify_document
from app.apa.models import AnalysisResult, Fixability, Issue, Region
from app.apa.profile import PROFILE_ID
from app.apa.registry import all_rules
from app.apa.registry.base import RuleContext
from app.apa.registry.effective_format import (
    FormatVerdict,
    hanging_indent_verdict,
    line_spacing_verdict,
)


def _dedupe_issues(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple] = set()
    unique: list[Issue] = []
    for issue in issues:
        key = (
            issue.rule_id,
            issue.paragraph_index,
            issue.section_index,
            issue.location,
            issue.message,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique


def _count_major_formatting_verification(classified) -> tuple[int, int]:
    """
    Count major applicable formatting properties that were resolved vs unresolved.

    Currently tracks effective line spacing for confident BODY paragraphs and
    effective line spacing + hanging indent for confident REFERENCE_ENTRY
    paragraphs. Compliant and violating resolutions both count as verified.
    """
    verified = 0
    unresolved = 0
    for item in classified:
        if not item.text.strip():
            continue
        if item.region == Region.BODY and item.confidence >= 0.85:
            verdict = line_spacing_verdict(item.paragraph)
            if verdict == FormatVerdict.UNRESOLVED:
                unresolved += 1
            else:
                verified += 1
        elif item.region == Region.REFERENCE_ENTRY and item.confidence >= 0.95:
            spacing = line_spacing_verdict(item.paragraph)
            if spacing == FormatVerdict.UNRESOLVED:
                unresolved += 1
            else:
                verified += 1
            hanging = hanging_indent_verdict(item.paragraph)
            if hanging == FormatVerdict.UNRESOLVED:
                unresolved += 1
            else:
                verified += 1
    return verified, unresolved


def analyze_document(
    doc: Document,
    template_id: str = PROFILE_ID,
) -> AnalysisResult:
    classified = classify_document(doc)
    context = RuleContext(doc=doc, classified=classified, template_id=template_id)

    result = AnalysisResult(template_id=template_id)
    collected: list[Issue] = []

    for rule in all_rules(template_id):
        detected = rule.detect(context)
        collected.extend(detected)

    for issue in _dedupe_issues(collected):
        if issue.fixability == Fixability.SAFE_AUTO_FIX and issue.can_fix:
            result.safe_auto_fix.append(issue)
        elif issue.fixability == Fixability.AUTHOR_ACTION_REQUIRED:
            result.author_action_required.append(issue)
        elif issue.fixability == Fixability.CONDITIONAL:
            result.uncertain.append(issue)
        else:
            result.unsupported.append(issue)

    verified, unresolved = _count_major_formatting_verification(classified)
    result.verified_formatting_check_count = verified
    result.unresolved_formatting_check_count = unresolved
    return result


def analyze_document_path(path: str, template_id: str = PROFILE_ID) -> AnalysisResult:
    doc = Document(path)
    return analyze_document(doc, template_id=template_id)
