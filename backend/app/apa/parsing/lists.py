"""List / seriation detection for APA Phase 2D (read-only; never rewrite numbering)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from docx import Document
from docx.oxml.ns import qn

_PLAIN_NUMBERED_PROSE = re.compile(r"^\d+\.\s+\S")


@dataclass
class ListItemAnalysis:
    paragraph_index: int
    list_type: str  # NUMBERED_LIST|BULLETED_LIST|LETTERED_INLINE_LIST|UNKNOWN_LIST|PLAIN_NUMBERED_PROSE
    confidence: float
    num_id: Optional[int] = None
    ilvl: Optional[int] = None
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _numpr(paragraph) -> tuple[Optional[int], Optional[int]]:
    try:
        p_pr = paragraph._p.pPr
        if p_pr is None or p_pr.numPr is None:
            return None, None
        num_pr = p_pr.numPr
        num_id = int(num_pr.numId.val) if num_pr.numId is not None else None
        ilvl = int(num_pr.ilvl.val) if num_pr.ilvl is not None else 0
        return num_id, ilvl
    except Exception:
        return None, None


def _abstract_num_format(doc: Document, num_id: Optional[int]) -> Optional[str]:
    """Best-effort bullet vs decimal from numbering part."""
    if num_id is None:
        return None
    try:
        numbering_part = doc.part.numbering_part
        if numbering_part is None:
            return None
        # Resolve numId -> abstractNumId -> lvl -> numFmt
        root = numbering_part._element
        abstract_id = None
        for num in root.findall(qn("w:num")):
            if int(num.get(qn("w:numId"))) == num_id:
                abs_node = num.find(qn("w:abstractNumId"))
                if abs_node is not None:
                    abstract_id = int(abs_node.get(qn("w:val")))
                break
        if abstract_id is None:
            return None
        for abs_num in root.findall(qn("w:abstractNum")):
            if int(abs_num.get(qn("w:abstractNumId"))) != abstract_id:
                continue
            lvl = abs_num.find(qn("w:lvl"))
            if lvl is None:
                return None
            fmt = lvl.find(qn("w:numFmt"))
            if fmt is None:
                return None
            return (fmt.get(qn("w:val")) or "").lower()
    except Exception:
        return None
    return None


def analyze_lists(doc: Document) -> list[ListItemAnalysis]:
    analyses: list[ListItemAnalysis] = []
    for index, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        num_id, ilvl = _numpr(paragraph)
        if num_id is not None:
            fmt = _abstract_num_format(doc, num_id)
            if fmt in {"bullet"}:
                list_type = "BULLETED_LIST"
            elif fmt in {"decimal", "lowerletter", "upperletter", "lowerroman", "upperroman"}:
                list_type = "NUMBERED_LIST"
            else:
                list_type = "NUMBERED_LIST" if fmt else "UNKNOWN_LIST"
            analyses.append(
                ListItemAnalysis(
                    paragraph_index=index,
                    list_type=list_type,
                    confidence=0.95 if fmt else 0.85,
                    num_id=num_id,
                    ilvl=ilvl,
                    evidence=["word_numbering", f"fmt:{fmt or 'unknown'}"],
                )
            )
            continue

        # Plain prose that starts with "1." is NOT a Word list.
        if _PLAIN_NUMBERED_PROSE.match(text):
            analyses.append(
                ListItemAnalysis(
                    paragraph_index=index,
                    list_type="PLAIN_NUMBERED_PROSE",
                    confidence=0.9,
                    evidence=["plain_text_number_prefix"],
                    warnings=["not_word_numbering"],
                )
            )
    return analyses
