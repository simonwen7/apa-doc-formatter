"""Group-author identity helpers (in-memory only; never written to DOCX)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GroupAuthorIdentity:
    full_name: str
    abbreviation: Optional[str] = None
    confidence: float = 0.0
    source_location: str = ""
    evidence: list[str] = field(default_factory=list)


_INTRO_ABBREV_RE = re.compile(
    r"(?P<full>[A-Z][^()]{2,80}?)\s*\((?P<abbr>[A-Z]{2,12})\)",
)

# Common acronyms that should NOT auto-alias without explicit introduction.
_GENERIC_ACRONYMS = frozenset(
    {
        "APA",
        "USA",
        "US",
        "UK",
        "UN",
        "WHO",
        "NASA",
        "FBI",
        "CIA",
        "ADHD",
        "IQ",
        "GPA",
        "PDF",
        "DOI",
        "URL",
        "HTML",
        "HTTP",
        "COVID",
    }
)


def _norm(value: str) -> str:
    v = value.lower()
    v = re.sub(r"[^a-z0-9\s]", " ", v)
    return re.sub(r"\s+", " ", v).strip()


def looks_like_group_author_name(name: str) -> bool:
    text = (name or "").strip()
    if not text:
        return False
    if re.search(r"\b(et\s+al\.?)\b", text, re.I):
        return False
    # Person-like "Surname, A. A."
    if re.match(r"^[A-Z][a-zA-Z'’-]+,\s*[A-Z]\.", text):
        return False
    if re.search(
        r"\b(university|association|organization|organisation|institute|center|centre|"
        r"department|ministry|office|agency|society|foundation|college|school|"
        r"administration|commission|council|bureau)\b",
        text,
        re.I,
    ):
        return True
    # Multi-word capitalized phrase without commas (e.g., "World Health Organization")
    tokens = text.split()
    if len(tokens) >= 2 and "," not in text and all(
        t[:1].isupper() or t.lower() in {"of", "and", "the", "for", "on"} for t in tokens
    ):
        return True
    return False


def extract_introduced_abbreviation(text: str) -> Optional[GroupAuthorIdentity]:
    """Detect Full Name (ABBR) introduction patterns in prose/citation."""
    m = _INTRO_ABBREV_RE.search(text or "")
    if not m:
        return None
    full = m.group("full").strip(" ,;")
    abbr = m.group("abbr").strip()
    if abbr.upper() in _GENERIC_ACRONYMS and not looks_like_group_author_name(full):
        return None
    if not looks_like_group_author_name(full) and len(full.split()) < 2:
        return None
    return GroupAuthorIdentity(
        full_name=full,
        abbreviation=abbr,
        confidence=0.9,
        source_location="inline_introduction",
        evidence=["full_name_abbr_intro"],
    )


def collect_group_author_identities(
    citation_texts: list[str],
    reference_author_texts: list[str],
) -> list[GroupAuthorIdentity]:
    identities: list[GroupAuthorIdentity] = []
    seen: set[tuple[str, str]] = set()

    for text in citation_texts + reference_author_texts:
        intro = extract_introduced_abbreviation(text)
        if intro and intro.abbreviation:
            key = (_norm(intro.full_name), intro.abbreviation.upper())
            if key not in seen:
                seen.add(key)
                identities.append(intro)

    for author in reference_author_texts:
        if not looks_like_group_author_name(author):
            continue
        # Derive initials acronym only when multi-word organization-like.
        words = [
            w
            for w in re.findall(r"[A-Za-z]+", author)
            if w.lower() not in {"of", "and", "the", "for", "on", "in"}
        ]
        if len(words) < 2:
            continue
        abbr = "".join(w[0].upper() for w in words)
        if len(abbr) < 2 or abbr in _GENERIC_ACRONYMS:
            continue
        key = (_norm(author), abbr)
        if key in seen:
            continue
        # Low confidence — only useful when citation uses same abbreviation AND
        # introduction evidence exists elsewhere, or exact abbr match with high
        # overlap. Mark as tentative.
        identities.append(
            GroupAuthorIdentity(
                full_name=author,
                abbreviation=abbr,
                confidence=0.55,
                source_location="reference_derived",
                evidence=["derived_initialism"],
            )
        )
        seen.add(key)
    return identities


def authors_alias_match(
    cite_author: str,
    ref_author: str,
    identities: list[GroupAuthorIdentity],
) -> tuple[bool, float, str]:
    """Return (matched, confidence, reason). Comparison only."""
    ca = _norm(cite_author)
    ra = _norm(ref_author)
    if not ca or not ra:
        return False, 0.0, ""
    if ca == ra or ca.startswith(ra) or ra.startswith(ca):
        return True, 0.9, "direct_author_key"
    for identity in identities:
        full = _norm(identity.full_name)
        abbr = (identity.abbreviation or "").upper()
        if identity.confidence < 0.85:
            # Derived-only aliases require exact abbreviation citation + full ref.
            if ca == abbr.lower() and (ra == full or full.startswith(ra) or ra.startswith(full)):
                return True, 0.7, "tentative_abbr_alias"
            continue
        if ca == abbr.lower() and (ra == full or full.startswith(ra) or ra.startswith(full)):
            return True, min(0.92, identity.confidence + 0.02), "introduced_abbr_alias"
        if ca == full and ra == full:
            return True, 0.93, "group_full_name"
    return False, 0.0, ""
