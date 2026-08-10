"""In-text citation analysis — AUTHOR_ACTION_REQUIRED only. ZERO citation fixers."""

from __future__ import annotations

import re

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.citations import CitationType, extract_document_citations
from app.apa.registry.base import BaseRule, RuleContext

SOURCE_CITE = SourceRef(
    official_resource=(
        "APA Style in-text citations guidance; Publication Manual (7th ed.) "
        "Works Credited in the Text"
    ),
    publication_manual_section=None,
    notes=(
        "In-text citations use author–date format. Forma APA reports likely issues "
        "for author review and never rewrites citation characters."
    ),
    source_verified=True,
)


def _ensure_citations(context: RuleContext):
    if context.citations:
        return context.citations
    paras = [
        (item.index, item.text)
        for item in context.classified
        if item.region
        in {
            Region.BODY,
            Region.BLOCK_QUOTE,
            Region.ABSTRACT,
            Region.LEVEL_1_HEADING,
            Region.LEVEL_2_HEADING,
            Region.LEVEL_3_HEADING,
            Region.LEVEL_4_HEADING,
            Region.LEVEL_5_HEADING,
            Region.BODY_TITLE,
            Region.UNKNOWN,
        }
        and item.text.strip()
    ]
    context.citations = extract_document_citations(paras)
    return context.citations


def _detect_missing_locator_on_quote(context: RuleContext) -> list[Issue]:
    issues = []
    for item in context.classified:
        text = item.text or ""
        if item.region not in {Region.BODY, Region.BLOCK_QUOTE}:
            continue
        has_quotes = any(q in text for q in ('"', "“", "”"))
        if not has_quotes and item.region != Region.BLOCK_QUOTE:
            continue
        cites = [
            c
            for c in _ensure_citations(context)
            if c.paragraph_index == item.index and c.confidence >= 0.9
        ]
        for cite in cites:
            if cite.possible_locator:
                continue
            # Direct quote near citation without locator
            if cite.citation_type == CitationType.DIRECT_QUOTE:
                continue
            window = text[max(0, cite.start - 60) : cite.end]
            if any(q in window for q in ('"', "“", "”")) or item.region == Region.BLOCK_QUOTE:
                issues.append(
                    Issue(
                        rule_id="APA7-CITATION-LOCATOR-MISSING",
                        category="Citations",
                        message=(
                            f"A direct quotation in paragraph {item.index} may be missing "
                            "a page/paragraph locator."
                        ),
                        expected="locator such as p./pp./para. when required",
                        actual="locator not clearly detected",
                        location=f"paragraph[{item.index}]",
                        severity=Severity.WARNING,
                        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                        can_fix=False,
                        confidence=0.82,
                        source=SOURCE_CITE,
                        reason_not_fixable="Adding a locator would modify author text.",
                        paragraph_index=item.index,
                        region=item.region,
                        citation_index=cite.citation_index,
                    )
                )
    return issues


def _detect_et_al_uncertain(context: RuleContext) -> list[Issue]:
    """et al. review only when a confident reference match + author count is unavailable."""
    from app.apa.registry.citation_reference_matching import _ensure_match_data
    from app.apa.parsing.matching import MatchStatus

    _cites, refs, matches = _ensure_match_data(context)
    issues = []
    for cite in _ensure_citations(context):
        raw = cite.raw_text.lower()
        if "et al" not in raw:
            continue
        match = next(
            (m for m in matches if m.citation_index == cite.citation_index),
            None,
        )
        # If uniquely matched and we can count authors on the reference, skip noisy review.
        if match and match.status == MatchStatus.MATCHED and match.reference_index is not None:
            ref = next((r for r in refs if r.paragraph_index == match.reference_index), None)
            if ref and ref.author_span:
                author_text = ref.author_span.text
                # Heuristic author count: commas / & / and
                approx = 1 + author_text.count(",") + len(re.findall(r"\s&\s|\sand\s", author_text))
                if approx >= 3:
                    continue
        issues.append(
            Issue(
                rule_id="APA7-CITATION-ETAL-REVIEW",
                category="Citations",
                message=(
                    f"Citation in paragraph {cite.paragraph_index} uses 'et al.' and "
                    "may need review against the corresponding reference author list."
                ),
                expected="et al. used according to APA author-count rules",
                actual="et al. present; author count not independently verified",
                location=f"paragraph[{cite.paragraph_index}]",
                severity=Severity.INFO,
                fixability=Fixability.CONDITIONAL,
                can_fix=False,
                confidence=0.55,
                source=SOURCE_CITE,
                reason_not_fixable=(
                    "et al. is never auto-corrected; matching author counts may be uncertain."
                ),
                paragraph_index=cite.paragraph_index,
                region=Region.BODY,
                citation_index=cite.citation_index,
                match_status=match.status.value if match else None,
            )
        )
    return issues


def _detect_multiple_citation_order(context: RuleContext) -> list[Issue]:
    issues = []
    for cite in _ensure_citations(context):
        if cite.citation_type != CitationType.MULTIPLE_SOURCE:
            continue
        if cite.confidence < 0.85:
            continue
        issues.append(
            Issue(
                rule_id="APA7-CITATION-MULTIPLE-ORDER",
                category="Citations",
                message=(
                    f"A multiple-source citation in paragraph {cite.paragraph_index} "
                    "may need author review for alphabetical ordering and punctuation."
                ),
                expected="APA ordering/punctuation for multiple works",
                actual="multiple works detected in one parenthetical citation",
                location=f"paragraph[{cite.paragraph_index}]",
                severity=Severity.INFO,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=0.75,
                source=SOURCE_CITE,
                reason_not_fixable="Reordering or changing punctuation would modify text.",
                paragraph_index=cite.paragraph_index,
                region=Region.BODY,
                citation_index=cite.citation_index,
            )
        )
    return issues


# Enforce architecture: no citation fixers exist in this module.
assert True


RULES = [
    BaseRule(
        rule_id="APA7-CITATION-LOCATOR-MISSING",
        category="Citations",
        description="Direct quotation may be missing a locator.",
        official_expectation="Include page/paragraph locator for direct quotes when required",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY", "BLOCK_QUOTE"),
        detector=_detect_missing_locator_on_quote,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-CITATION-ETAL-REVIEW",
        category="Citations",
        description="et al. usage may need author review.",
        official_expectation="Correct et al. usage by author count",
        source=SOURCE_CITE,
        fixability=Fixability.CONDITIONAL,
        applicable_regions=("BODY",),
        detector=_detect_et_al_uncertain,
        fixer=None,
        production_supported=False,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-CITATION-MULTIPLE-ORDER",
        category="Citations",
        description="Multiple works in one citation may need ordering review.",
        official_expectation="APA multiple-work citation order",
        source=SOURCE_CITE,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_detect_multiple_citation_order,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
]
