"""Reference-entry structural parsing (read-only; never mutates documents)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ReferenceType(str, Enum):
    JOURNAL_ARTICLE = "journal_article"
    BOOK = "book"
    EBOOK = "ebook"
    EDITED_CHAPTER = "edited_book_chapter"
    NEWSPAPER_ARTICLE = "newspaper_article"
    MAGAZINE_ARTICLE = "magazine_article"
    WEBPAGE = "webpage"
    GOVERNMENT_REPORT = "government_report"
    ORGANIZATION_REPORT = "organization_report"
    REPORT = "report"  # generic report fallback
    PREPRINT = "preprint"
    THESIS = "thesis_dissertation"
    CONFERENCE = "conference"
    DATASET = "dataset"
    SOFTWARE = "software"
    AUDIOVISUAL = "audiovisual"
    ONLINE_VIDEO = "online_video"
    SOCIAL_MEDIA = "social_media"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TextSpan:
    start: int
    end: int
    text: str


@dataclass
class ReferenceEntryAnalysis:
    paragraph_index: int
    raw_text: str
    reference_type: ReferenceType = ReferenceType.UNKNOWN
    type_confidence: float = 0.0
    author_span: Optional[TextSpan] = None
    date_span: Optional[TextSpan] = None
    title_span: Optional[TextSpan] = None
    source_span: Optional[TextSpan] = None
    journal_span: Optional[TextSpan] = None
    volume_span: Optional[TextSpan] = None
    issue_span: Optional[TextSpan] = None
    page_span: Optional[TextSpan] = None
    doi_span: Optional[TextSpan] = None
    url_span: Optional[TextSpan] = None
    parse_warnings: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    @property
    def sort_key(self) -> str:
        """Temporary comparison key only — never written back to the document."""
        author = (self.author_span.text if self.author_span else self.raw_text[:40]).lower()
        year = ""
        if self.date_span:
            m = re.search(r"\d{4}", self.date_span.text)
            year = m.group(0) if m else ""
        return re.sub(r"[^a-z0-9]+", " ", f"{author} {year}").strip()


_DOI_RE = re.compile(
    r"(?:https?://doi\.org/|doi:\s*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
    re.I,
)
_URL_RE = re.compile(r"https?://[^\s]+", re.I)
_AUTHOR_DATE_RE = re.compile(
    r"^(?P<author>.+?)\s*\((?P<date>\d{4}[a-z]?|n\.d\.)(?:[^)]*)?\)\.\s*(?P<rest>.+)$",
    re.S,
)

_YOUTUBE_RE = re.compile(r"youtube\.com|youtu\.be", re.I)
_SOCIAL_RE = re.compile(
    r"\b(twitter|x\.com|facebook|instagram|tiktok|reddit|linkedin)\b",
    re.I,
)
_PREPRINT_RE = re.compile(
    r"\b(preprint|psyarxiv|arxiv|biorxiv|ssrn|osf\.io|medrxiv)\b",
    re.I,
)
_NEWSPAPER_RE = re.compile(
    r"\b(the\s+new\s+york\s+times|washington\s+post|the\s+guardian|wall\s+street\s+journal|"
    r"usa\s+today|los\s+angeles\s+times|chicago\s+tribune|newspaper)\b",
    re.I,
)
_MAGAZINE_RE = re.compile(
    r"\b(time|newsweek|the\s+atlantic|the\s+new\s+yorker|scientific\s+american|"
    r"national\s+geographic|magazine)\b",
    re.I,
)
_GOV_RE = re.compile(
    r"\b(u\.?s\.?\s+department|government|ministry|agency|bureau|national\s+institute|"
    r"centers?\s+for\s+disease|world\s+health\s+organization)\b",
    re.I,
)


def _span(text: str, start: int, end: int) -> TextSpan:
    return TextSpan(start=start, end=end, text=text[start:end])


def classify_reference_type(text: str) -> tuple[ReferenceType, float, list[str]]:
    """Conservative multi-signal classification. Ambiguous → UNKNOWN."""
    evidence: list[str] = []
    lower = text.lower()
    candidates: list[tuple[ReferenceType, float, str]] = []

    if _DOI_RE.search(text) and re.search(r",\s*\d+\(\d+\)", text):
        candidates.append((ReferenceType.JOURNAL_ARTICLE, 0.92, "doi+volume_issue"))
    elif re.search(r"\b\d+\(\d+\),\s*(?:\d|Article|e\d)", text, re.I):
        candidates.append((ReferenceType.JOURNAL_ARTICLE, 0.86, "volume_issue_pages"))

    if re.search(r"\bin\s+.+\(eds?\.\)", lower):
        candidates.append((ReferenceType.EDITED_CHAPTER, 0.9, "in_editors"))

    if re.search(r"\b(doctoral dissertation|master'?s thesis)\b", lower):
        candidates.append((ReferenceType.THESIS, 0.93, "thesis_label"))

    if _PREPRINT_RE.search(text):
        candidates.append((ReferenceType.PREPRINT, 0.9, "preprint_marker"))

    if _YOUTUBE_RE.search(text) or re.search(r"\[video\]", lower):
        candidates.append((ReferenceType.ONLINE_VIDEO, 0.9, "online_video_marker"))
    elif re.search(r"\b(video|film|podcast|audio)\b", lower) and _URL_RE.search(text):
        candidates.append((ReferenceType.AUDIOVISUAL, 0.8, "audiovisual_label"))

    if _SOCIAL_RE.search(text) and (
        "@" in text or re.search(r"\[(tweet|status|post|update)\]", lower)
    ):
        candidates.append((ReferenceType.SOCIAL_MEDIA, 0.88, "social_media_marker"))

    if _NEWSPAPER_RE.search(text) and re.search(
        r"\(\d{4},\s*(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)",
        lower,
    ):
        candidates.append((ReferenceType.NEWSPAPER_ARTICLE, 0.9, "newspaper+full_date"))
    elif _NEWSPAPER_RE.search(text):
        candidates.append((ReferenceType.NEWSPAPER_ARTICLE, 0.78, "newspaper_name"))

    if _MAGAZINE_RE.search(text) and re.search(
        r"\(\d{4},\s*(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)",
        lower,
    ):
        candidates.append((ReferenceType.MAGAZINE_ARTICLE, 0.88, "magazine+full_date"))
    elif _MAGAZINE_RE.search(text) and "magazine" in lower:
        candidates.append((ReferenceType.MAGAZINE_ARTICLE, 0.8, "magazine_label"))

    if re.search(r"\b(e-?book|kindle|epub)\b", lower) or (
        re.search(r"https?://", lower)
        and re.search(r":\s*[A-Z]", text)
        and not _DOI_RE.search(text)
        and re.search(r"\b(press|publishers?|books?)\b", lower)
    ):
        if re.search(r"\b(e-?book|kindle|epub)\b", lower):
            candidates.append((ReferenceType.EBOOK, 0.88, "ebook_label"))
        elif re.search(r"https?://", lower) and re.search(
            r"\b(press|publishers?)\b", lower
        ):
            candidates.append((ReferenceType.EBOOK, 0.78, "ebook_url_publisher"))

    if re.search(r"\b(report|technical report)\b", lower):
        if _GOV_RE.search(text):
            candidates.append((ReferenceType.GOVERNMENT_REPORT, 0.88, "gov_report"))
        elif re.search(
            r"\b(association|organization|organisation|foundation|institute)\b",
            lower,
        ):
            candidates.append(
                (ReferenceType.ORGANIZATION_REPORT, 0.84, "org_report")
            )
        else:
            candidates.append((ReferenceType.REPORT, 0.8, "report_label"))

    if re.search(r"\b(conference|proceedings)\b", lower):
        candidates.append((ReferenceType.CONFERENCE, 0.8, "conference_label"))
    if re.search(r"\b(dataset|data set)\b", lower):
        candidates.append((ReferenceType.DATASET, 0.85, "dataset_label"))
    if re.search(r"\b(software|computer software|mobile app)\b", lower):
        candidates.append((ReferenceType.SOFTWARE, 0.85, "software_label"))

    if (
        re.search(r"\b(retrieved|http)", lower)
        and not _DOI_RE.search(text)
        and not any(
            c[0]
            in {
                ReferenceType.ONLINE_VIDEO,
                ReferenceType.SOCIAL_MEDIA,
                ReferenceType.EBOOK,
                ReferenceType.PREPRINT,
                ReferenceType.NEWSPAPER_ARTICLE,
                ReferenceType.MAGAZINE_ARTICLE,
            }
            for c in candidates
        )
    ):
        candidates.append((ReferenceType.WEBPAGE, 0.8, "retrieved_or_url"))

    if (
        re.search(r":\s*[A-Z]", text)
        and not _DOI_RE.search(text)
        and not any(
            c[0]
            in {
                ReferenceType.EBOOK,
                ReferenceType.REPORT,
                ReferenceType.GOVERNMENT_REPORT,
                ReferenceType.ORGANIZATION_REPORT,
            }
            for c in candidates
        )
    ):
        candidates.append((ReferenceType.BOOK, 0.75, "publisher_pattern"))
    elif (
        re.search(r"\b(press|publishers?|books?)\b", lower)
        and not _DOI_RE.search(text)
        and not re.search(r"\d+\(\d+\)", text)
        and not any(
            c[0]
            in {
                ReferenceType.EBOOK,
                ReferenceType.REPORT,
                ReferenceType.GOVERNMENT_REPORT,
                ReferenceType.ORGANIZATION_REPORT,
                ReferenceType.JOURNAL_ARTICLE,
                ReferenceType.WEBPAGE,
            }
            for c in candidates
        )
    ):
        candidates.append((ReferenceType.BOOK, 0.8, "publisher_name"))

    if not candidates:
        return ReferenceType.UNKNOWN, 0.4, evidence

    # If top two are close and different, stay UNKNOWN.
    candidates.sort(key=lambda t: t[1], reverse=True)
    best = candidates[0]
    if len(candidates) > 1 and candidates[1][1] >= best[1] - 0.05 and candidates[1][0] != best[0]:
        evidence.extend([best[2], candidates[1][2], "ambiguous_type"])
        return ReferenceType.UNKNOWN, 0.45, evidence

    evidence.append(best[2])
    return best[0], best[1], evidence


def parse_reference_entry(paragraph_index: int, text: str) -> ReferenceEntryAnalysis:
    analysis = ReferenceEntryAnalysis(paragraph_index=paragraph_index, raw_text=text)
    if not text.strip():
        analysis.parse_warnings.append("empty")
        return analysis

    ref_type, conf, evidence = classify_reference_type(text)
    analysis.reference_type = ref_type
    analysis.type_confidence = conf
    analysis.evidence.extend(evidence)

    m = _AUTHOR_DATE_RE.match(text.strip())
    if m:
        author = m.group("author")
        date = m.group("date")
        rest = m.group("rest")
        a_start = text.find(author)
        if a_start >= 0:
            analysis.author_span = _span(text, a_start, a_start + len(author))
        # Find full parenthetical date token
        d_match = re.search(r"\((?:\d{4}[a-z]?|n\.d\.)[^)]*\)", text)
        if d_match:
            analysis.date_span = _span(text, d_match.start(), d_match.end())
        rest_start = text.find(rest)
        if rest_start >= 0:
            title_end_rel = rest.find(".")
            if title_end_rel > 0:
                analysis.title_span = _span(text, rest_start, rest_start + title_end_rel)
                source_start = rest_start + title_end_rel + 1
                while source_start < len(text) and text[source_start] == " ":
                    source_start += 1
                if source_start < len(text):
                    analysis.source_span = _span(text, source_start, len(text))
    else:
        analysis.parse_warnings.append("author_date_pattern_unrecognized")

    doi = _DOI_RE.search(text)
    if doi:
        analysis.doi_span = _span(text, doi.start(), doi.end())

    url = _URL_RE.search(text)
    if url is not None:
        if analysis.doi_span is None or not (
            url.start() >= analysis.doi_span.start and url.end() <= analysis.doi_span.end
        ):
            if "doi.org" in url.group(0).lower() and analysis.doi_span is not None:
                pass
            else:
                analysis.url_span = _span(text, url.start(), url.end())

    if analysis.source_span:
        source = analysis.source_span.text
        pm = re.search(r"(\d+)[-–](\d+)|Article\s+\w+|e\d+", source, re.I)
        if pm:
            p_abs = text.find(pm.group(0), analysis.source_span.start)
            if p_abs >= 0:
                analysis.page_span = _span(text, p_abs, p_abs + len(pm.group(0)))

    if (
        analysis.reference_type == ReferenceType.JOURNAL_ARTICLE
        and analysis.title_span
        and analysis.source_span
    ):
        source = analysis.source_span.text
        jm = re.match(r"\s*([^,]+),", source)
        if jm:
            j_text = jm.group(1).strip()
            j_abs = text.find(j_text, analysis.source_span.start)
            if j_abs >= 0:
                analysis.journal_span = _span(text, j_abs, j_abs + len(j_text))
                analysis.evidence.append("journal_span")

        vm = re.search(r"(\d+)\((\d+)\)", source)
        if vm:
            v_abs = text.find(vm.group(0), analysis.source_span.start)
            if v_abs >= 0:
                analysis.volume_span = _span(text, v_abs, v_abs + len(vm.group(1)))
                issue_start = v_abs + len(vm.group(1)) + 1
                analysis.issue_span = _span(
                    text, issue_start, issue_start + len(vm.group(2))
                )

    return analysis


def approximate_author_count(author_text: str) -> Optional[int]:
    """Best-effort author count from a reference author span (never written back)."""
    if not author_text or not author_text.strip():
        return None
    text = author_text.strip()
    if re.search(r"\bet\s+al\.?\b", text, re.I):
        return 3  # at least three signaled
    # "Surname, A. A., Surname, B. B., & Surname, C. C."
    # Count surname-like tokens before commas that look like initials groups.
    surname_hits = re.findall(
        r"[A-Z][A-Za-z'’\-]+,\s*(?:[A-Z]\.\s*)+",
        text,
    )
    if len(surname_hits) >= 2:
        return len(surname_hits)
    parts = re.split(r"\s+&\s+|\s+and\s+", text)
    if len(parts) >= 2:
        # Expand each side if it contains multiple surname patterns.
        total = 0
        for part in parts:
            hits = re.findall(r"[A-Z][A-Za-z'’\-]+,\s*(?:[A-Z]\.\s*)+", part)
            total += max(1, len(hits)) if part.strip() else 0
        return max(total, len(parts))
    commas = text.count(",")
    if commas >= 2:
        return max(1, (commas + 1) // 2)
    return 1
