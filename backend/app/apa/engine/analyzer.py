from __future__ import annotations

from docx import Document

from app.apa.engine.classifier import classify_document
from app.apa.models import AnalysisResult, Fixability, Issue
from app.apa.profile import PROFILE_ID
from app.apa.registry import all_rules
from app.apa.registry.base import RuleContext


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

    return result


def analyze_document_path(path: str, template_id: str = PROFILE_ID) -> AnalysisResult:
    doc = Document(path)
    return analyze_document(doc, template_id=template_id)
