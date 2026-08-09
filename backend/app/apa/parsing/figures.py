"""Figure region modeling for APA Phase 2D (read-only analysis)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from docx import Document
from docx.oxml.ns import qn

_FIGURE_NUMBER_RE = re.compile(r"^figure\s+(\d+)\s*$", re.I)
_FIGURE_NUMBER_INLINE_RE = re.compile(r"^figure\s+(\d+)\b", re.I)
_NOTE_RE = re.compile(r"^note\.\s*", re.I)
_CALLOUT_RE = re.compile(r"\b(?:see\s+)?figure\s+(\d+)\b", re.I)
_LOGO_HINTS = re.compile(r"\b(logo|icon|signature|header|watermark)\b", re.I)


@dataclass
class FigureAnalysis:
    figure_index: int
    confidence: float
    is_apa_candidate: bool
    number_paragraph_index: Optional[int] = None
    title_paragraph_index: Optional[int] = None
    image_paragraph_index: Optional[int] = None
    image_relationship_id: Optional[str] = None
    note_paragraph_indices: list[int] = field(default_factory=list)
    callout_locations: list[int] = field(default_factory=list)
    inline_or_floating: str = "unknown"  # inline|floating|unknown
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text_available: bool = False
    warnings: list[str] = field(default_factory=list)
    number_text: Optional[str] = None
    number_value: Optional[int] = None
    evidence: list[str] = field(default_factory=list)


def _drawing_info(paragraph) -> tuple[bool, Optional[str], Optional[int], Optional[int], bool, str]:
    """Return (has_drawing, rId, cx, cy, alt_text, inline_or_floating)."""
    try:
        p = paragraph._p
    except Exception:
        return False, None, None, None, False, "unknown"

    drawings = p.findall(".//" + qn("w:drawing"))
    if not drawings:
        # Some images use VML w:pict / v:imagedata (namespace not in python-docx nsmap).
        vml_imagedata = "{urn:schemas-microsoft-com:vml}imagedata"
        imagedata = p.findall(".//" + vml_imagedata)
        if not imagedata:
            return False, None, None, None, False, "unknown"
        r_id = imagedata[0].get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        return True, r_id, None, None, False, "unknown"

    drawing = drawings[0]
    inline = drawing.find(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline") is not None
    anchor = drawing.find(".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor") is not None
    mode = "inline" if inline else ("floating" if anchor else "unknown")

    a_blip = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    blip = drawing.find(".//" + a_blip)
    r_id = None
    if blip is not None:
        r_id = blip.get(qn("r:embed")) or blip.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        )

    cx = cy = None
    extent = drawing.find(
        ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent"
    )
    if extent is not None:
        try:
            cx = int(extent.get("cx") or 0) or None
            cy = int(extent.get("cy") or 0) or None
        except Exception:
            pass

    alt = False
    doc_pr = drawing.find(
        ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"
    )
    if doc_pr is not None:
        descr = doc_pr.get("descr") or ""
        title = doc_pr.get("title") or ""
        alt = bool(descr.strip() or title.strip())

    return True, r_id, cx, cy, alt, mode


def analyze_figures(doc: Document) -> list[FigureAnalysis]:
    callouts_by_number: dict[int, list[int]] = {}
    for index, paragraph in enumerate(doc.paragraphs):
        text = (paragraph.text or "").strip()
        if _FIGURE_NUMBER_RE.match(text) or (
            _FIGURE_NUMBER_INLINE_RE.match(text) and len(text.split()) <= 4
        ):
            continue
        for match in _CALLOUT_RE.finditer(paragraph.text or ""):
            num = int(match.group(1))
            callouts_by_number.setdefault(num, []).append(index)

    analyses: list[FigureAnalysis] = []
    figure_counter = 0
    paragraphs = list(doc.paragraphs)

    for index, paragraph in enumerate(paragraphs):
        has_drawing, r_id, cx, cy, alt, mode = _drawing_info(paragraph)
        if not has_drawing:
            continue

        evidence: list[str] = ["has_drawing"]
        warnings: list[str] = []
        number_idx = None
        title_idx = None
        number_text = None
        number_value = None
        note_indices: list[int] = []

        # Preceding paragraphs for number/title.
        prev = paragraphs[index - 1] if index > 0 else None
        prev2 = paragraphs[index - 2] if index > 1 else None
        if prev is not None:
            t1 = prev.text.strip()
            if _FIGURE_NUMBER_RE.match(t1) or (
                _FIGURE_NUMBER_INLINE_RE.match(t1) and len(t1.split()) <= 4
            ):
                number_idx = index - 1
                number_text = t1
                m = _FIGURE_NUMBER_INLINE_RE.match(t1)
                number_value = int(m.group(1)) if m else None
                evidence.append("number_immediately_above")
            elif prev2 is not None and _FIGURE_NUMBER_RE.match(prev2.text.strip()):
                number_idx = index - 2
                number_text = prev2.text.strip()
                number_value = int(_FIGURE_NUMBER_RE.match(number_text).group(1))
                title_idx = index - 1
                evidence.extend(["number_two_above", "title_immediately_above"])
            elif t1 and not _NOTE_RE.match(t1):
                title_idx = index - 1
                evidence.append("possible_title_above_no_number")
                warnings.append("title_without_confident_number")

            if (
                title_idx is None
                and number_idx is not None
                and index - 1 != number_idx
                and t1
                and not _NOTE_RE.match(t1)
            ):
                title_idx = index - 1
                evidence.append("title_after_number")

        # Notes after image.
        for j in range(index + 1, min(len(paragraphs), index + 4)):
            n_text = paragraphs[j].text.strip()
            if not n_text:
                continue
            if _NOTE_RE.match(n_text):
                note_indices.append(j)
                evidence.append("note_below")
            else:
                break

        # False-positive controls: decorative / logo-like images.
        nearby_text = " ".join(
            paragraphs[k].text
            for k in range(max(0, index - 2), min(len(paragraphs), index + 2))
        )
        decorative_hint = bool(_LOGO_HINTS.search(nearby_text))
        small = False
        if cx is not None and cy is not None:
            # EMUs; ~1 inch = 914400
            small = cx < 914400 and cy < 914400
            if small:
                warnings.append("small_image")
                evidence.append("small_dimensions")

        is_apa = False
        confidence = 0.4
        if number_idx is not None:
            is_apa = True
            confidence = 0.95
            evidence.append("apa_number_signal")
        elif decorative_hint or small:
            is_apa = False
            confidence = 0.25
            warnings.append("likely_decorative_or_logo")
        elif mode == "floating" and number_idx is None:
            is_apa = False
            confidence = 0.35
            warnings.append("floating_uncaptioned_image")
        else:
            # Uncaptioned inline image — do not force figure formatting.
            is_apa = False
            confidence = 0.45
            warnings.append("uncaptioned_image")

        callouts = callouts_by_number.get(number_value or -1, []) if number_value else []

        analyses.append(
            FigureAnalysis(
                figure_index=figure_counter,
                confidence=confidence,
                is_apa_candidate=is_apa,
                number_paragraph_index=number_idx,
                title_paragraph_index=title_idx,
                image_paragraph_index=index,
                image_relationship_id=r_id,
                note_paragraph_indices=note_indices,
                callout_locations=callouts,
                inline_or_floating=mode,
                width=cx,
                height=cy,
                alt_text_available=alt,
                warnings=warnings,
                number_text=number_text,
                number_value=number_value,
                evidence=evidence,
            )
        )
        figure_counter += 1

    return analyses
