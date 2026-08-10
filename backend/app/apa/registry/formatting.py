"""Shared formatting helpers that never rewrite user-authored characters."""

from __future__ import annotations

from typing import Optional

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from docx.text.paragraph import Paragraph

from app.apa.profile import (
    APA_VALID_FONTS,
    DEFAULT_APA_FONT_NAME,
    DEFAULT_APA_FONT_SIZE_PT,
    DOUBLE_LINE_SPACING,
    FIRST_LINE_INDENT_INCHES,
    HANGING_INDENT_INCHES,
)
from app.apa.registry.effective_format import (
    FormatSource,
    FormatVerdict,
    hanging_indent_verdict,
    line_spacing_verdict,
    resolve_effective_run_format,
    walk_style_chain,
    resolve_effective_paragraph_format,
)


def _walk_style_chain(style):
    return walk_style_chain(style)


def effective_font_name(paragraph: Paragraph) -> Optional[str]:
    """Resolve a concrete font name when possible; None means uncertain."""
    for run in paragraph.runs:
        if run.text and run.text.strip():
            resolved = resolve_effective_run_format(run, paragraph).font_family
            if resolved.value:
                return str(resolved.value)
    try:
        for style in walk_style_chain(paragraph.style):
            if style.font and style.font.name:
                return style.font.name
    except Exception:
        pass
    return None


def effective_font_size_pt(paragraph: Paragraph) -> Optional[float]:
    for run in paragraph.runs:
        if run.text and run.text.strip():
            resolved = resolve_effective_run_format(run, paragraph).font_size_pt
            if resolved.value is not None:
                return float(resolved.value)
    try:
        for style in walk_style_chain(paragraph.style):
            if style.font and style.font.size:
                return style.font.size.pt
    except Exception:
        pass
    return None


def effective_bold(paragraph: Paragraph) -> Optional[bool]:
    """True/False when resolvable; None means inherited/uncertain."""
    values = []
    for run in paragraph.runs:
        if run.text and run.text.strip():
            values.append(run.font.bold)
    if values:
        if any(v is True for v in values):
            return True
        if all(v is False for v in values):
            return False
    try:
        for style in walk_style_chain(paragraph.style):
            if style.font and style.font.bold is not None:
                return bool(style.font.bold)
    except Exception:
        pass
    if values and all(v is None for v in values):
        return None
    if values and all(v is False or v is None for v in values) and any(
        v is False for v in values
    ):
        return False
    return None


def effective_italic(paragraph: Paragraph) -> Optional[bool]:
    values = []
    for run in paragraph.runs:
        if run.text and run.text.strip():
            values.append(run.font.italic)
    if values:
        if any(v is True for v in values):
            return True
        if all(v is False for v in values):
            return False
    try:
        for style in walk_style_chain(paragraph.style):
            if style.font and style.font.italic is not None:
                return bool(style.font.italic)
    except Exception:
        pass
    if values and all(v is None for v in values):
        return None
    if values and all(v is False or v is None for v in values) and any(
        v is False for v in values
    ):
        return False
    return None


def set_runs_bold(paragraph: Paragraph, bold: bool = True) -> None:
    """Toggle bold on existing runs only — never rewrite run text."""
    if not paragraph.runs:
        return
    for run in paragraph.runs:
        run.font.bold = bold


def set_runs_italic(paragraph: Paragraph, italic: bool = True) -> None:
    if not paragraph.runs:
        return
    for run in paragraph.runs:
        run.font.italic = italic


def set_runs_apa_font(paragraph: Paragraph) -> None:
    """Apply canonical APA font on existing runs only — never rewrite text."""
    if not paragraph.runs:
        return
    for run in paragraph.runs:
        if run.text is None:
            continue
        run.font.name = DEFAULT_APA_FONT_NAME
        run.font.size = Pt(DEFAULT_APA_FONT_SIZE_PT)
        try:
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.insert(0, rFonts)
            for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                rFonts.set(qn(attr), DEFAULT_APA_FONT_NAME)
        except Exception:
            pass


def _font_pair_valid(name: str, size: float) -> bool:
    key = (name.strip().lower(), int(round(size)))
    for valid_name, valid_size in APA_VALID_FONTS:
        if key[0] == valid_name and abs(key[1] - valid_size) < 0.6:
            return True
    return False


def is_apa_valid_typography(paragraph: Paragraph) -> Optional[bool]:
    """
    True when every text-bearing run resolves to an APA-allowed font+size.
    False when any run confidently violates.
    None when any relevant run is unresolved (never treat as compliant).
    """
    text_runs = [run for run in paragraph.runs if run.text and run.text.strip()]
    if not text_runs:
        name = effective_font_name(paragraph)
        size = effective_font_size_pt(paragraph)
        if name is None or size is None:
            return None
        return _font_pair_valid(name, size)

    saw_unresolved = False
    for run in text_runs:
        eff = resolve_effective_run_format(run, paragraph)
        name = eff.font_family.value
        size = eff.font_size_pt.value
        if name is None or size is None:
            saw_unresolved = True
            continue
        if not _font_pair_valid(str(name), float(size)):
            return False
    if saw_unresolved:
        return None
    return True


def line_spacing_is_double(paragraph: Paragraph) -> Optional[bool]:
    """
    Effective double-spacing check.

    True/False when spacing can be resolved through direct/style/docDefaults.
    None when unresolved — callers must NOT treat None as compliant.
    """
    verdict = line_spacing_verdict(paragraph)
    if verdict == FormatVerdict.VERIFIED_COMPLIANT:
        return True
    if verdict == FormatVerdict.VERIFIED_VIOLATION:
        return False
    return None


def set_double_spacing(paragraph: Paragraph) -> None:
    fmt = paragraph.paragraph_format
    fmt.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    fmt.line_spacing = DOUBLE_LINE_SPACING


def space_before_pt(paragraph: Paragraph) -> float:
    eff = resolve_effective_paragraph_format(paragraph)
    value = eff.space_before_pt.value
    return float(value) if value is not None else 0.0


def space_after_pt(paragraph: Paragraph) -> float:
    eff = resolve_effective_paragraph_format(paragraph)
    value = eff.space_after_pt.value
    return float(value) if value is not None else 0.0


def clear_extra_paragraph_spacing(paragraph: Paragraph) -> None:
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)


def is_left_aligned_or_default(paragraph: Paragraph) -> bool:
    return paragraph.alignment in (None, WD_ALIGN_PARAGRAPH.LEFT)


def is_centered(paragraph: Paragraph) -> bool:
    return paragraph.alignment == WD_ALIGN_PARAGRAPH.CENTER


def is_fully_justified(paragraph: Paragraph) -> bool:
    return paragraph.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY


def set_left_aligned(paragraph: Paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT


def set_centered(paragraph: Paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def first_line_indent_inches(paragraph: Paragraph) -> Optional[float]:
    eff = resolve_effective_paragraph_format(paragraph)
    value = eff.first_line_indent_inches.value
    return float(value) if value is not None else None


def set_first_line_indent(paragraph: Paragraph) -> None:
    paragraph.paragraph_format.first_line_indent = Inches(FIRST_LINE_INDENT_INCHES)
    paragraph.paragraph_format.left_indent = None


def clear_first_line_indent(paragraph: Paragraph) -> None:
    paragraph.paragraph_format.first_line_indent = Inches(0)


def is_hanging_indent(paragraph: Paragraph) -> Optional[bool]:
    """
    Effective hanging-indent check.

    Positive first-line indent is never hanging. Unresolved → None (not compliant).
    """
    verdict = hanging_indent_verdict(paragraph)
    if verdict == FormatVerdict.VERIFIED_COMPLIANT:
        return True
    if verdict == FormatVerdict.VERIFIED_VIOLATION:
        return False
    return None


def set_hanging_indent(paragraph: Paragraph) -> None:
    fmt = paragraph.paragraph_format
    fmt.left_indent = Inches(HANGING_INDENT_INCHES)
    fmt.first_line_indent = Inches(-HANGING_INDENT_INCHES)


def set_flush_left_no_first_indent(paragraph: Paragraph) -> None:
    fmt = paragraph.paragraph_format
    fmt.left_indent = Inches(0)
    fmt.first_line_indent = Inches(0)


def set_level4_or_5_indent(paragraph: Paragraph) -> None:
    paragraph.paragraph_format.first_line_indent = Inches(FIRST_LINE_INDENT_INCHES)


def set_page_break_before(paragraph: Paragraph, value: bool = True) -> None:
    paragraph.paragraph_format.page_break_before = value


def page_break_before(paragraph: Paragraph) -> Optional[bool]:
    return paragraph.paragraph_format.page_break_before


def ensure_right_tab_stop(paragraph: Paragraph, position_twips: int = 9360) -> None:
    """Ensure a right-aligned tab near the right margin. Does not alter run text."""
    p_pr = paragraph._p.get_or_add_pPr()
    tabs = p_pr.find(qn("w:tabs"))
    if tabs is None:
        tabs = OxmlElement("w:tabs")
        p_pr.append(tabs)
    for tab in tabs.findall(qn("w:tab")):
        if tab.get(qn("w:val")) == "right":
            return
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(position_twips))
    tabs.append(tab)


def effective_text_color_rgb(paragraph: Paragraph) -> Optional[str]:
    for run in paragraph.runs:
        if not (run.text and run.text.strip()):
            continue
        color = resolve_effective_run_format(run, paragraph).color_rgb
        if color.value:
            return str(color.value)
    return None


def is_non_default_text_color(paragraph: Paragraph) -> Optional[bool]:
    """
    True when a resolvable non-black/auto color is present.
    None when color cannot be resolved.
    """
    found = False
    unresolved = False
    for run in paragraph.runs:
        if not (run.text and run.text.strip()):
            continue
        color = resolve_effective_run_format(run, paragraph).color_rgb
        if color.source == FormatSource.UNKNOWN or color.value is None:
            unresolved = True
            continue
        found = True
        rgb = str(color.value).upper()
        if rgb not in {"000000", "BLACK"}:
            return True
    if found:
        return False
    return None if unresolved else False
