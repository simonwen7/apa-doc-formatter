"""Citation ↔ reference matching issues (AUTHOR_ACTION_REQUIRED)."""

from __future__ import annotations

from app.apa.models import Fixability, Issue, Region, Severity, SourceRef
from app.apa.parsing.citations import extract_document_citations
from app.apa.parsing.matching import MatchStatus, match_citations_to_references
from app.apa.parsing.reference_entry import parse_reference_entry
from app.apa.registry.base import BaseRule, RuleContext

SOURCE_MATCH = SourceRef(
    official_resource=(
        "APA Style guidance on citations and reference lists; Publication Manual "
        "(7th ed.) Works Credited in the Text / Reference List"
    ),
    publication_manual_section=None,
    notes=(
        "Citations and references should correspond. Personal communications and "
        "certain special cases are exempt from reference-list inclusion. "
        "Forma APA never generates or deletes citations/references."
    ),
    source_verified=True,
)


def _ensure_match_data(context: RuleContext):
    if context.match_results:
        return context.citations, context.reference_analyses, context.match_results

    refs = []
    for item in context.classified:
        if item.region == Region.REFERENCE_ENTRY and item.text.strip():
            refs.append(parse_reference_entry(item.index, item.text))
    context.reference_analyses = refs

    paras = [
        (item.index, item.text)
        for item in context.classified
        if item.region in {Region.BODY, Region.BLOCK_QUOTE, Region.ABSTRACT}
        and item.text.strip()
    ]
    cites = extract_document_citations(paras)
    context.citations = cites
    context.match_results = match_citations_to_references(cites, refs)
    return cites, refs, context.match_results


def _detect_citation_without_reference(context: RuleContext) -> list[Issue]:
    _cites, _refs, matches = _ensure_match_data(context)
    issues = []
    for match in matches:
        if match.status != MatchStatus.CITATION_WITHOUT_REFERENCE:
            continue
        if match.confidence < 0.8:
            continue
        cite = next(
            (c for c in context.citations if c.citation_index == match.citation_index),
            None,
        )
        if cite is None:
            continue
        issues.append(
            Issue(
                rule_id="APA7-MATCH-CITATION-WITHOUT-REF",
                category="Citation Matching",
                message=(
                    f"A citation in paragraph {cite.paragraph_index} may not match an "
                    "entry in the reference list."
                ),
                expected="corresponding reference-list entry",
                actual="no confident reference match",
                location=f"paragraph[{cite.paragraph_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=match.confidence,
                source=SOURCE_MATCH,
                reason_not_fixable="Generating a reference entry would invent content.",
                paragraph_index=cite.paragraph_index,
                region=Region.BODY,
                citation_index=cite.citation_index,
                match_status=match.status.value,
            )
        )
    return issues


def _detect_reference_not_cited(context: RuleContext) -> list[Issue]:
    _cites, _refs, matches = _ensure_match_data(context)
    issues = []
    for match in matches:
        if match.status != MatchStatus.REFERENCE_NOT_CITED:
            continue
        if match.confidence < 0.8 or match.reference_index is None:
            continue
        issues.append(
            Issue(
                rule_id="APA7-MATCH-REF-NOT-CITED",
                category="Citation Matching",
                message=(
                    f"Reference paragraph {match.reference_index} may not be cited "
                    "in the text."
                ),
                expected="corresponding in-text citation",
                actual="no confident citation match",
                location=f"paragraph[{match.reference_index}]",
                severity=Severity.WARNING,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=match.confidence,
                source=SOURCE_MATCH,
                reason_not_fixable="Deleting or rewriting references is never automatic.",
                paragraph_index=match.reference_index,
                region=Region.REFERENCE_ENTRY,
                reference_index=match.reference_index,
                match_status=match.status.value,
            )
        )
    return issues


def _detect_personal_communication_exempt(context: RuleContext) -> list[Issue]:
    _cites, _refs, matches = _ensure_match_data(context)
    issues = []
    for match in matches:
        if match.status != MatchStatus.EXEMPT_OR_SPECIAL_CASE:
            continue
        cite = next(
            (c for c in context.citations if c.citation_index == match.citation_index),
            None,
        )
        if cite is None:
            continue
        issues.append(
            Issue(
                rule_id="APA7-MATCH-PERSONAL-COMM-EXEMPT",
                category="Citation Matching",
                message=(
                    f"A personal communication citation in paragraph {cite.paragraph_index} "
                    "is treated as exempt from reference-list matching."
                ),
                expected="personal communications cited in text only",
                actual="exempt/special case",
                location=f"paragraph[{cite.paragraph_index}]",
                severity=Severity.INFO,
                fixability=Fixability.AUTHOR_ACTION_REQUIRED,
                can_fix=False,
                confidence=match.confidence,
                source=SOURCE_MATCH,
                reason_not_fixable="Informational exemption; no automatic change.",
                paragraph_index=cite.paragraph_index,
                region=Region.BODY,
                citation_index=cite.citation_index,
                match_status=match.status.value,
            )
        )
    return issues


RULES = [
    BaseRule(
        rule_id="APA7-MATCH-CITATION-WITHOUT-REF",
        category="Citation Matching",
        description="Citation may lack a corresponding reference.",
        official_expectation="Each citation has a matching reference unless exempt",
        source=SOURCE_MATCH,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_detect_citation_without_reference,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-MATCH-REF-NOT-CITED",
        category="Citation Matching",
        description="Reference may not be cited in text.",
        official_expectation="Each reference is cited in text unless special case",
        source=SOURCE_MATCH,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("REFERENCE_ENTRY",),
        detector=_detect_reference_not_cited,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
    BaseRule(
        rule_id="APA7-MATCH-PERSONAL-COMM-EXEMPT",
        category="Citation Matching",
        description="Personal communication exemption notice.",
        official_expectation="Personal communications are cited in text only",
        source=SOURCE_MATCH,
        fixability=Fixability.AUTHOR_ACTION_REQUIRED,
        applicable_regions=("BODY",),
        detector=_detect_personal_communication_exempt,
        fixer=None,
        production_supported=True,
        detector_test=True,
    ),
]
