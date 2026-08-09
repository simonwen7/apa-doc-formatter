"""Reference-entry structural parsing (read-only; never mutates documents)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ReferenceType(str, Enum):
    JOURNAL_ARTICLE = "journal_article"
    BOOK = "book"
    EDITED_CHAPTER = "edited_book_chapter"
    WEBPAGE = "webpage"
    REPORT = "report"
    THESIS = "thesis_dissertation"
    CONFERENCE = "conference"
    DATASET = "dataset"
    AUDIOVISUAL = "audiovisual"
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
    r"^(?P<author>.+?)\s*\((?P<date>\d{4}[a-z]?|n\.d\.)\)\.\s*(?P<rest>.+)$",
    re.S,
)


def _span(text: str, start: int, end: int) -> TextSpan:
    return TextSpan(start=start, end=end, text=text[start:end])


def classify_reference_type(text: str) -> tuple[ReferenceType, float, list[str]]:
    evidence: list[str] = []
    lower = text.lower()

    if _DOI_RE.search(text) and re.search(r",\s*\d+\(\d+\)", text):
        evidence.extend(["doi", "volume_issue_pattern"])
        return ReferenceType.JOURNAL_ARTICLE, 0.92, evidence
    if re.search(r"\b\d+\(\d+\),\s*\d+", text):
        evidence.append("volume_issue_pages")
        return ReferenceType.JOURNAL_ARTICLE, 0.86, evidence
    if re.search(r"\bin\s+.+\(eds?\.\)", lower):
        evidence.append("in_editors")
        return ReferenceType.EDITED_CHAPTER, 0.9, evidence
    if re.search(r"\b(doctoral dissertation|master'?s thesis)\b", lower):
        evidence.append("thesis_label")
        return ReferenceType.THESIS, 0.93, evidence
    if re.search(r"\b(retrieved|http)", lower) and not _DOI_RE.search(text):
        evidence.append("retrieved_or_url")
        return ReferenceType.WEBPAGE, 0.8, evidence
    if re.search(r"\b(report|technical report)\b", lower):
        evidence.append("report_label")
        return ReferenceType.REPORT, 0.82, evidence
    if re.search(r"\b(conference|proceedings)\b", lower):
        evidence.append("conference_label")
        return ReferenceType.CONFERENCE, 0.8, evidence
    if re.search(r"\b(dataset|data set)\b", lower):
        evidence.append("dataset_label")
        return ReferenceType.DATASET, 0.85, evidence
    if re.search(r"\b(video|film|podcast|audio)\b", lower):
        evidence.append("audiovisual_label")
        return ReferenceType.AUDIOVISUAL, 0.8, evidence
    if re.search(r":\s*[A-Z]", text) and not _DOI_RE.search(text):
        evidence.append("publisher_pattern")
        return ReferenceType.BOOK, 0.75, evidence

    return ReferenceType.UNKNOWN, 0.4, evidence


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
        d_token = f"({date})"
        d_start = text.find(d_token)
        if d_start >= 0:
            analysis.date_span = _span(text, d_start, d_start + len(d_token))
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
