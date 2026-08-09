"""In-text citation detection (read-only). Never mutates documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CitationType(str, Enum):
    PARENTHETICAL = "PARENTHETICAL_CITATION"
    NARRATIVE = "NARRATIVE_CITATION"
    DIRECT_QUOTE = "DIRECT_QUOTE_CITATION"
    MULTIPLE_SOURCE = "MULTIPLE_SOURCE_CITATION"
    GROUP_AUTHOR = "GROUP_AUTHOR_CITATION"
    UNKNOWN = "UNKNOWN_CITATION"


@dataclass
class CitationCandidate:
    citation_index: int
    paragraph_index: int
    start: int
    end: int
    raw_text: str
    citation_type: CitationType
    confidence: float
    possible_authors: list[str] = field(default_factory=list)
    possible_year: Optional[str] = None
    possible_locator: Optional[str] = None
    evidence: list[str] = field(default_factory=list)
    is_personal_communication: bool = False


# Parenthetical citation-like: (Author, 2020) or (Author & Author, 2020, p. 12)
_PAREN_CIT_RE = re.compile(
    r"\((?P<body>"
    r"[^()]*?"
    r"(?:\d{4}[a-z]?|n\.d\.)"
    r"[^()]*?"
    r")\)"
)

# Narrative: Author (2020) or Author and Author (2020)
_NARR_CIT_RE = re.compile(
    r"\b(?P<author>[A-Z][A-Za-z'’-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’-]+)?(?:\s+et\s+al\.)?)"
    r"\s*\((?P<year>\d{4}[a-z]?|n\.d\.)(?P<extra>[^)]*)\)"
)

_LOCATOR_RE = re.compile(
    r"\b(p{1,2}\.\s*\d|para\.\s*\d|paras\.\s*\d|section|secs?\.)",
    re.I,
)

# False-positive guards
_STATS_RE = re.compile(r"\b(p\s*[<>=]|n\s*=|df\s*=|α\s*=|f\s*\(|t\s*\()", re.I)
_MATH_YEARISH = re.compile(r"^\s*\d+(\.\d+)?\s*[,\s]*\d+(\.\d+)?\s*$")


def _looks_like_false_positive(body: str) -> bool:
    b = body.strip()
    if _STATS_RE.search(b):
        return True
    if re.fullmatch(r"[\d\s,.\-+/%]+", b):
        return True
    if re.search(r"\b(e\.g\.|i\.e\.|see also|vs\.|versus)\b", b, re.I) and not re.search(
        r"\d{4}", b
    ):
        return True
    if not re.search(r"[A-Za-z]{2,}", b):
        return True
    # Year-first parentheticals like "(2020 was difficult)" are not citations.
    if re.match(r"^\(?\s*\d{4}", b) and "personal communication" not in b.lower():
        return True
    # Require an author-like token before the year for ordinary citations.
    if "personal communication" not in b.lower():
        if not re.search(
            r"[A-Za-z][A-Za-z'’\-\.]+.+(?:\d{4}[a-z]?|n\.d\.)",
            b,
        ):
            return True
    return False


def _parse_authors_year(body: str) -> tuple[list[str], Optional[str], Optional[str]]:
    year = None
    ym = re.search(r"(\d{4}[a-z]?|n\.d\.)", body)
    if ym:
        year = ym.group(1)
    locator = None
    lm = _LOCATOR_RE.search(body)
    if lm:
        locator = body[lm.start() :].strip(" ,;")
    author_part = body
    if ym:
        author_part = body[: ym.start()].rstrip(" ,;")
    # Split multiple works on semicolon for primary author extraction only.
    first = author_part.split(";")[0]
    authors = [a.strip() for a in re.split(r"\s+&\s+|\s+and\s+", first) if a.strip()]
    return authors, year, locator


def extract_citations_from_paragraph(
    paragraph_index: int,
    text: str,
    start_index: int = 0,
) -> list[CitationCandidate]:
    found: list[CitationCandidate] = []
    citation_index = start_index

    for m in _PAREN_CIT_RE.finditer(text):
        body = m.group("body")
        if _looks_like_false_positive(body):
            continue
        authors, year, locator = _parse_authors_year(body)
        if year is None:
            continue
        ctype = CitationType.PARENTHETICAL
        conf = 0.9
        evidence = ["parenthetical_year"]
        if ";" in body and re.search(r"\d{4}", body.split(";", 1)[-1]):
            ctype = CitationType.MULTIPLE_SOURCE
            evidence.append("semicolon_multiple")
            conf = 0.88
        if any(
            re.search(r"\b(university|association|organization|institute|centers?\b)", a, re.I)
            for a in authors
        ) or (authors and authors[0][:1].isupper() and " " in authors[0] and not re.search(r"\.", authors[0])):
            # Heuristic group author (weak)
            if authors and not re.search(r"^[A-Z][a-z]+,\s*[A-Z]\.", authors[0]):
                if len(authors[0].split()) >= 2 and not re.search(r",", authors[0]):
                    ctype = CitationType.GROUP_AUTHOR
                    evidence.append("group_author_heuristic")
        if locator:
            evidence.append("locator")
        personal = bool(re.search(r"personal communication", body, re.I))
        if personal:
            evidence.append("personal_communication")
            conf = 0.95

        # Direct quote cue: quotation marks near citation in paragraph
        window_start = max(0, m.start() - 80)
        nearby = text[window_start : m.end()]
        if ("“" in nearby or '"' in nearby or "‘" in nearby or "'" in nearby) and locator:
            ctype = CitationType.DIRECT_QUOTE
            evidence.append("quote_marks_near_locator")
            conf = max(conf, 0.92)

        found.append(
            CitationCandidate(
                citation_index=citation_index,
                paragraph_index=paragraph_index,
                start=m.start(),
                end=m.end(),
                raw_text=m.group(0),
                citation_type=ctype,
                confidence=conf,
                possible_authors=authors,
                possible_year=year,
                possible_locator=locator,
                evidence=evidence,
                is_personal_communication=personal,
            )
        )
        citation_index += 1

    for m in _NARR_CIT_RE.finditer(text):
        # Skip if this year paren was already captured as parenthetical span.
        if any(c.start <= m.start(2) < c.end for c in found):
            continue
        author = m.group("author")
        year = m.group("year")
        extra = m.group("extra") or ""
        locator = None
        lm = _LOCATOR_RE.search(extra)
        if lm:
            locator = extra[lm.start() :].strip(" ,;")
        ctype = CitationType.NARRATIVE
        evidence = ["narrative_author_year"]
        conf = 0.9
        if locator:
            ctype = CitationType.DIRECT_QUOTE
            evidence.append("locator")
            conf = 0.92
        found.append(
            CitationCandidate(
                citation_index=citation_index,
                paragraph_index=paragraph_index,
                start=m.start(),
                end=m.end(),
                raw_text=m.group(0),
                citation_type=ctype,
                confidence=conf,
                possible_authors=[author],
                possible_year=year,
                possible_locator=locator,
                evidence=evidence,
            )
        )
        citation_index += 1

    found.sort(key=lambda c: c.start)
    # Re-index after sort
    for i, c in enumerate(found):
        c.citation_index = start_index + i
    return found


def extract_document_citations(paragraphs: list[tuple[int, str]]) -> list[CitationCandidate]:
    all_cites: list[CitationCandidate] = []
    for index, text in paragraphs:
        all_cites.extend(
            extract_citations_from_paragraph(index, text, start_index=len(all_cites))
        )
    return all_cites
