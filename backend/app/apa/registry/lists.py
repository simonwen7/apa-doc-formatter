"""List / seriation rules (Phase 2D). Never rewrite numbering characters or bullets."""

from __future__ import annotations

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.lists import analyze_lists
from app.apa.registry.base import BaseRule, RuleContext

SOURCE_LISTS = SourceRef(
    official_resource=(
        "APA Style guidance on lists / seriation; Publication Manual (7th ed.) "
        "Mechanics of Style"
    ),
    publication_manual_section=None,
    notes=(
        "APA provides guidance for numbered, bulleted, and lettered lists. "
        "Forma APA never converts prose into lists, never renumbers items, and never "
        "rewrites bullet or numbering characters. Word numbering XML must be preserved."
    ),
    source_verified=True,
)


def _ensure_lists(context: RuleContext):
    if context.list_analyses:
        return context.list_analyses
    context.list_analyses = analyze_lists(context.doc)
    return context.list_analyses


def _detect_list_indent_policy(context: RuleContext) -> list[Issue]:
    """Registry policy only — do not emit per-document issues."""
    _ensure_lists(context)
    return []


def _detect_plain_prose_not_list(context: RuleContext) -> list[Issue]:
    _ensure_lists(context)
    return []


def _detect_list_text_policy(context: RuleContext) -> list[Issue]:
    """Registry policy only — do not emit per-document issues."""
    _ensure_lists(context)
    return []


RULES = [
    BaseRule(
        rule_id="APA7-LIST-INDENT",
        category="Lists",
        description="List indentation via numbering XML unsupported for auto-fix",
        official_expectation="Preserve Word list numbering; avoid unsafe indent rewrites",
        source=SOURCE_LISTS,
        fixability=Fixability.UNSUPPORTED,
        applicable_regions=(Region.LIST_ITEM.value,),
        detector=_detect_list_indent_policy,
        production_supported=False,
    ),
    BaseRule(
        rule_id="APA7-LIST-NO-TEXT-REWRITE",
        category="Lists",
        description="Never rewrite list numbering or bullet characters",
        official_expectation="List markers and item text preserved exactly",
        source=SOURCE_LISTS,
        fixability=Fixability.UNSUPPORTED,
        applicable_regions=(Region.LIST_ITEM.value,),
        detector=_detect_list_text_policy,
        production_supported=False,
    ),
    BaseRule(
        rule_id="APA7-LIST-PLAIN-PROSE-GUARD",
        category="Lists",
        description="Plain numbered prose is not treated as Word lists",
        official_expectation="Require Word numbering objects for list classification",
        source=SOURCE_LISTS,
        fixability=Fixability.UNSUPPORTED,
        applicable_regions=(Region.BODY.value, Region.LIST_ITEM.value),
        detector=_detect_plain_prose_not_list,
        production_supported=False,
        detector_implemented=True,
    ),
]
