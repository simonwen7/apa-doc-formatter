"""Citation ↔ reference correspondence (non-destructive)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.apa.parsing.citations import CitationCandidate
from app.apa.parsing.reference_entry import ReferenceEntryAnalysis


class MatchStatus(str, Enum):
    MATCHED = "MATCHED"
    CITATION_WITHOUT_REFERENCE = "CITATION_WITHOUT_REFERENCE"
    REFERENCE_NOT_CITED = "REFERENCE_NOT_CITED"
    AMBIGUOUS = "AMBIGUOUS"
    EXEMPT_OR_SPECIAL_CASE = "EXEMPT_OR_SPECIAL_CASE"


@dataclass
class MatchResult:
    status: MatchStatus
    citation_index: Optional[int] = None
    reference_index: Optional[int] = None
    confidence: float = 0.0
    reason: str = ""


def _norm_author(value: str) -> str:
    v = value.lower()
    v = re.sub(r"\bet\s+al\.?\b", "", v)
    v = re.sub(r"[^a-z0-9\s]", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    # Prefer surname token (first token for "Surname, A. A." or last for narrative)
    if "," in value:
        return re.sub(r"[^a-z0-9\s]", " ", value.split(",", 1)[0].lower()).strip()
    parts = v.split()
    return parts[0] if parts else v


def _ref_author_key(ref: ReferenceEntryAnalysis) -> str:
    if ref.author_span:
        return _norm_author(ref.author_span.text)
    return _norm_author(ref.raw_text[:60])


def _ref_year(ref: ReferenceEntryAnalysis) -> Optional[str]:
    if not ref.date_span:
        return None
    m = re.search(r"(\d{4}[a-z]?|n\.d\.)", ref.date_span.text, re.I)
    return m.group(1).lower() if m else None


def match_citations_to_references(
    citations: list[CitationCandidate],
    references: list[ReferenceEntryAnalysis],
) -> list[MatchResult]:
    results: list[MatchResult] = []
    matched_ref_indexes: set[int] = set()

    for cite in citations:
        if cite.is_personal_communication:
            results.append(
                MatchResult(
                    status=MatchStatus.EXEMPT_OR_SPECIAL_CASE,
                    citation_index=cite.citation_index,
                    confidence=0.95,
                    reason="personal_communication",
                )
            )
            continue

        if cite.confidence < 0.85 or not cite.possible_year:
            results.append(
                MatchResult(
                    status=MatchStatus.AMBIGUOUS,
                    citation_index=cite.citation_index,
                    confidence=cite.confidence,
                    reason="low_confidence_citation",
                )
            )
            continue

        cite_authors = [_norm_author(a) for a in cite.possible_authors if a]
        cite_year = cite.possible_year.lower()
        candidates = []
        for ref in references:
            if ref.type_confidence < 0.5 and ref.reference_type.value == "unknown":
                # Still allow author/year match on unknown type.
                pass
            ref_author = _ref_author_key(ref)
            ref_year = _ref_year(ref)
            if not ref_year or ref_year != cite_year:
                continue
            if not cite_authors:
                continue
            if any(
                ref_author == ca or ref_author.startswith(ca) or ca.startswith(ref_author)
                for ca in cite_authors
            ):
                candidates.append(ref)

        if len(candidates) == 1:
            matched_ref_indexes.add(candidates[0].paragraph_index)
            results.append(
                MatchResult(
                    status=MatchStatus.MATCHED,
                    citation_index=cite.citation_index,
                    reference_index=candidates[0].paragraph_index,
                    confidence=0.9,
                    reason="author_year_match",
                )
            )
        elif len(candidates) > 1:
            results.append(
                MatchResult(
                    status=MatchStatus.AMBIGUOUS,
                    citation_index=cite.citation_index,
                    confidence=0.7,
                    reason="multiple_reference_candidates",
                )
            )
        else:
            results.append(
                MatchResult(
                    status=MatchStatus.CITATION_WITHOUT_REFERENCE,
                    citation_index=cite.citation_index,
                    confidence=0.85,
                    reason="no_matching_reference",
                )
            )

    for ref in references:
        if ref.paragraph_index in matched_ref_indexes:
            continue
        # If any MATCHED already linked this ref via another citation path, skip.
        if any(
            r.status == MatchStatus.MATCHED and r.reference_index == ref.paragraph_index
            for r in results
        ):
            continue
        # Only flag when reference parse is decently confident.
        if ref.author_span is None or ref.date_span is None:
            results.append(
                MatchResult(
                    status=MatchStatus.AMBIGUOUS,
                    reference_index=ref.paragraph_index,
                    confidence=0.55,
                    reason="reference_parse_incomplete",
                )
            )
            continue
        results.append(
            MatchResult(
                status=MatchStatus.REFERENCE_NOT_CITED,
                reference_index=ref.paragraph_index,
                confidence=0.8,
                reason="no_matching_citation",
            )
        )

    return results
