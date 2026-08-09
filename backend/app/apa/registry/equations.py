"""Equation rules (Phase 2D). Preserve OMML; never rewrite equation content."""

from __future__ import annotations

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.equations import analyze_equations
from app.apa.registry.base import BaseRule, RuleContext

SOURCE_EQ = SourceRef(
    official_resource=(
        "APA Style guidance on equations; Publication Manual (7th ed.) Mechanics of Style"
    ),
    publication_manual_section=None,
    notes=(
        "Equation content, numbering, punctuation, and notation frequently require "
        "author judgment. Forma APA detects OMML equations and preserves them exactly. "
        "Mathematical content changes are unsupported."
    ),
    source_verified=True,
)


def _ensure_equations(context: RuleContext):
    if context.equation_analyses:
        return context.equation_analyses
    context.equation_analyses = analyze_equations(context.doc)
    return context.equation_analyses


def _detect_equation_preserve(context: RuleContext) -> list[Issue]:
    eqs = _ensure_equations(context)
    if not eqs:
        return []
    return [
        Issue(
            rule_id="APA7-EQUATION-CONTENT",
            category="Equations",
            message=(
                f"Detected {len(eqs)} Word equation(s). Equation content is preserved and "
                "not automatically rewritten."
            ),
            expected="author-reviewed equation content/numbering",
            actual="OMML preserved; content not auto-fixed",
            location="equations",
            severity=Severity.INFO,
            fixability=Fixability.UNSUPPORTED,
            can_fix=False,
            confidence=1.0,
            source=SOURCE_EQ,
            reason_not_fixable="Equation meaning/numbering changes are unsupported",
            region=Region.UNKNOWN,
        )
    ]


RULES = [
    BaseRule(
        rule_id="APA7-EQUATION-CONTENT",
        category="Equations",
        description="Equation OMML preserved; content unsupported for auto-fix",
        official_expectation="Preserve equations; do not rewrite mathematical content",
        source=SOURCE_EQ,
        fixability=Fixability.UNSUPPORTED,
        applicable_regions=(Region.UNKNOWN.value,),
        detector=_detect_equation_preserve,
        production_supported=False,
    ),
]
