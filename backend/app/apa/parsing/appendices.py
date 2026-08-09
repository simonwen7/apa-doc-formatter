"""Appendix region modeling for APA Phase 2D (read-only analysis)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from docx import Document

_APPENDIX_LABEL_RE = re.compile(
    r"^appendix(?:\s+([A-Z]|[0-9]+))?\s*$",
    re.I,
)
_APPENDIX_WORD_RE = re.compile(r"\bappendix(?:\s+[A-Z])?\b", re.I)
_CALLOUT_RE = re.compile(r"\b(?:see\s+)?appendix(?:\s+([A-Z]|[0-9]+))?\b", re.I)


@dataclass
class AppendixAnalysis:
    appendix_index: int
    confidence: float
    label_paragraph_index: Optional[int] = None
    title_paragraph_index: Optional[int] = None
    body_paragraph_indices: list[int] = field(default_factory=list)
    label_text: Optional[str] = None
    label_letter: Optional[str] = None
    callout_locations: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


def analyze_appendices(doc: Document) -> list[AppendixAnalysis]:
    paragraphs = list(doc.paragraphs)
    # Find References boundary — appendices typically follow references.
    ref_start = None
    for index, paragraph in enumerate(paragraphs):
        if paragraph.text.strip().lower() == "references":
            ref_start = index
            break

    callouts: list[tuple[int, Optional[str]]] = []
    for index, paragraph in enumerate(paragraphs):
        for match in _CALLOUT_RE.finditer(paragraph.text or ""):
            # Skip the appendix labels themselves.
            if _APPENDIX_LABEL_RE.match(paragraph.text.strip()):
                continue
            callouts.append((index, match.group(1)))

    analyses: list[AppendixAnalysis] = []
    label_indices: list[int] = []
    for index, paragraph in enumerate(paragraphs):
        text = paragraph.text.strip()
        if not _APPENDIX_LABEL_RE.match(text):
            continue
        # Avoid false positives: "Appendix" mid-sentence prose already excluded by ^$.
        # Prefer post-references; pre-reference exact "Appendix" alone is still candidate
        # but lower confidence unless styled as heading.
        label_indices.append(index)

    for a_index, label_idx in enumerate(label_indices):
        text = paragraphs[label_idx].text.strip()
        m = _APPENDIX_LABEL_RE.match(text)
        letter = m.group(1).upper() if m and m.group(1) else None
        evidence = ["exact_appendix_label"]
        warnings: list[str] = []
        confidence = 0.92

        style = ""
        try:
            style = (paragraphs[label_idx].style.name or "").lower()
        except Exception:
            pass
        if style.startswith("heading"):
            confidence = 0.97
            evidence.append("heading_style")

        if ref_start is not None and label_idx > ref_start:
            confidence = max(confidence, 0.96)
            evidence.append("after_references")
        elif ref_start is not None and label_idx < ref_start:
            confidence = min(confidence, 0.75)
            warnings.append("appendix_before_references")
            evidence.append("before_references")

        # Title: next non-empty paragraph that is not another appendix label / References.
        title_idx = None
        body_indices: list[int] = []
        next_label = label_indices[a_index + 1] if a_index + 1 < len(label_indices) else len(paragraphs)
        for j in range(label_idx + 1, next_label):
            t = paragraphs[j].text.strip()
            if not t:
                continue
            if title_idx is None and not _APPENDIX_LABEL_RE.match(t) and t.lower() != "references":
                title_idx = j
                evidence.append("title_following_label")
                continue
            if title_idx is not None:
                body_indices.append(j)

        # Callouts for this appendix.
        related_callouts: list[int] = []
        for c_idx, c_letter in callouts:
            if letter is None and c_letter is None:
                related_callouts.append(c_idx)
            elif letter and c_letter and letter == c_letter.upper():
                related_callouts.append(c_idx)
            elif letter is None and c_letter:
                related_callouts.append(c_idx)

        analyses.append(
            AppendixAnalysis(
                appendix_index=a_index,
                confidence=confidence,
                label_paragraph_index=label_idx,
                title_paragraph_index=title_idx,
                body_paragraph_indices=body_indices,
                label_text=text,
                label_letter=letter,
                callout_locations=related_callouts,
                warnings=warnings,
                evidence=evidence,
            )
        )

    return analyses


def looks_like_appendix_prose_mention(text: str) -> bool:
    """True when 'appendix' appears but is not a standalone label."""
    stripped = (text or "").strip()
    if _APPENDIX_LABEL_RE.match(stripped):
        return False
    return bool(_APPENDIX_WORD_RE.search(stripped))
