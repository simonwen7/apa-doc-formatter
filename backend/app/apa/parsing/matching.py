"""Citation ↔ reference correspondence (non-destructive)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.apa.parsing.citations import CitationCandidate
from app.apa.parsing.group_authors import (
    authors_alias_match,
    collect_group_author_identities,
    looks_like_group_author_name,
)
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
    if "," in value:
        return re.sub(r"[^a-z0-9\s]", " ", value.split(",", 1)[0].lower()).strip()
    parts = v.split()
    return parts[0] if parts else v


def _ref_author_key(ref: ReferenceEntryAnalysis) -> str:
    if ref.author_span:
        return _norm_author(ref.author_span.text)
    return _norm_author(ref.raw_text[:60])


def _ref_author_display(ref: ReferenceEntryAnalysis) -> str:
    if ref.author_span:
        return ref.author_span.text.strip()
    return (ref.raw_text or "")[:80].strip()


def _ref_year(ref: ReferenceEntryAnalysis) -> Optional[str]:
    if not ref.date_span:
        return None
    m = re.search(r"(\d{4}[a-z]?|n\.d\.)", ref.date_span.text, re.I)
    return m.group(1).lower() if m else None


def _year_base(year: Optional[str]) -> Optional[str]:
    if not year:
        return None
    y = year.lower().strip()
    if y == "n.d.":
        return "n.d."
    m = re.match(r"(\d{4})", y)
    return m.group(1) if m else y


def _year_suffix(year: Optional[str]) -> Optional[str]:
    if not year:
        return None
    m = re.match(r"\d{4}([a-z])$", year.lower())
    return m.group(1) if m else None


def match_citations_to_references(
    citations: list[CitationCandidate],
    references: list[ReferenceEntryAnalysis],
) -> list[MatchResult]:
    results: list[MatchResult] = []
    matched_ref_indexes: set[int] = set()

    cite_texts = [c.raw_text for c in citations]
    ref_authors = [_ref_author_display(r) for r in references]
    identities = collect_group_author_identities(cite_texts, ref_authors)

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

        cite_authors = [a for a in cite.possible_authors if a]
        cite_year = cite.possible_year.lower()
        cite_year_base = _year_base(cite_year)
        candidates: list[tuple[ReferenceEntryAnalysis, float, str]] = []

        for ref in references:
            ref_year = _ref_year(ref)
            ref_year_base = _year_base(ref_year)
            if not ref_year_base or ref_year_base != cite_year_base:
                continue
            if not cite_authors:
                # No-author / title-based citation — mark ambiguous, not missing.
                continue

            best_conf = 0.0
            best_reason = ""
            ref_display = _ref_author_display(ref)
            ref_key = _ref_author_key(ref)
            for author in cite_authors:
                ok, conf, reason = authors_alias_match(author, ref_display, identities)
                if ok and conf > best_conf:
                    best_conf, best_reason = conf, reason
                ca = _norm_author(author)
                if ca and (ref_key == ca or ref_key.startswith(ca) or ca.startswith(ref_key)):
                    if 0.88 > best_conf:
                        best_conf, best_reason = 0.88, "author_year_key"

            if best_conf >= 0.7:
                # Prefer exact year+suffix match when both have suffixes.
                cite_suf = _year_suffix(cite_year)
                ref_suf = _year_suffix(ref_year)
                if cite_suf and ref_suf and cite_suf != ref_suf:
                    continue
                if cite_suf and ref_suf and cite_suf == ref_suf:
                    best_conf = min(0.95, best_conf + 0.05)
                    best_reason = best_reason + "+year_suffix"
                candidates.append((ref, best_conf, best_reason))

        if not cite_authors and looks_like_group_author_name(cite.raw_text):
            results.append(
                MatchResult(
                    status=MatchStatus.AMBIGUOUS,
                    citation_index=cite.citation_index,
                    confidence=0.6,
                    reason="no_author_parse_incomplete",
                )
            )
            continue

        if not cite_authors:
            results.append(
                MatchResult(
                    status=MatchStatus.AMBIGUOUS,
                    citation_index=cite.citation_index,
                    confidence=0.55,
                    reason="citation_author_not_parsed",
                )
            )
            continue

        if len(candidates) == 1:
            ref, conf, reason = candidates[0]
            matched_ref_indexes.add(ref.paragraph_index)
            results.append(
                MatchResult(
                    status=MatchStatus.MATCHED,
                    citation_index=cite.citation_index,
                    reference_index=ref.paragraph_index,
                    confidence=conf,
                    reason=reason,
                )
            )
        elif len(candidates) > 1:
            results.append(
                MatchResult(
                    status=MatchStatus.AMBIGUOUS,
                    citation_index=cite.citation_index,
                    confidence=0.72,
                    reason="multiple_reference_candidates",
                )
            )
        else:
            # Definite missing only when citation parse is strong.
            conf = 0.9 if cite.confidence >= 0.9 else 0.75
            status = (
                MatchStatus.CITATION_WITHOUT_REFERENCE
                if conf >= 0.9
                else MatchStatus.AMBIGUOUS
            )
            results.append(
                MatchResult(
                    status=status,
                    citation_index=cite.citation_index,
                    confidence=conf,
                    reason="no_matching_reference"
                    if status == MatchStatus.CITATION_WITHOUT_REFERENCE
                    else "uncertain_no_match",
                )
            )

    for ref in references:
        if ref.paragraph_index in matched_ref_indexes:
            continue
        if any(
            r.status == MatchStatus.MATCHED and r.reference_index == ref.paragraph_index
            for r in results
        ):
            continue
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
                confidence=0.82,
                reason="no_matching_citation",
            )
        )

    return results
