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
    DOUBLE_LINE_SPACING,
    FIRST_LINE_INDENT_INCHES,
    HANGING_INDENT_INCHES,
)


def _walk_style_chain(style):
    seen = set()
    current = style
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = getattr(current, "base_style", None)


def effective_font_name(paragraph: Paragraph) -> Optional[str]:
    """Resolve a concrete font name when possible; None means uncertain."""
    for run in paragraph.runs:
        if run.text and run.text.strip() and run.font.name:
            return run.font.name
    try:
        for style in _walk_style_chain(paragraph.style):
            if style.font and style.font.name:
                return style.font.name
    except Exception:
        pass
    return None


def effective_font_size_pt(paragraph: Paragraph) -> Optional[float]:
    for run in paragraph.runs:
        if run.text and run.text.strip() and run.font.size:
            return run.font.size.pt
    try:
        for style in _walk_style_chain(paragraph.style):
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
        for style in _walk_style_chain(paragraph.style):
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
        for style in _walk_style_chain(paragraph.style):
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


def is_apa_valid_typography(paragraph: Paragraph) -> Optional[bool]:
    name = effective_font_name(paragraph)
    size = effective_font_size_pt(paragraph)
    if name is None or size is None:
        return None
    key = (name.strip().lower(), int(round(size)))
    for valid_name, valid_size in APA_VALID_FONTS:
        if key[0] == valid_name and abs(key[1] - valid_size) < 0.6:
            return True
    return False


def line_spacing_is_double(paragraph: Paragraph) -> Optional[bool]:
    spacing = paragraph.paragraph_format.line_spacing
    rule = paragraph.paragraph_format.line_spacing_rule

    if spacing is None and rule is None:
        return None

    if rule == WD_LINE_SPACING.DOUBLE:
        return True

    if isinstance(spacing, float):
        return abs(spacing - DOUBLE_LINE_SPACING) < 0.05

    try:
        if hasattr(spacing, "pt") and spacing.pt is not None:
            return abs(float(spacing.pt) - 24.0) < 0.6
    except Exception:
        pass

    if spacing == DOUBLE_LINE_SPACING:
        return True

    return False


def set_double_spacing(paragraph: Paragraph) -> None:
    fmt = paragraph.paragraph_format
    fmt.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    fmt.line_spacing = DOUBLE_LINE_SPACING


def space_before_pt(paragraph: Paragraph) -> float:
    value = paragraph.paragraph_format.space_before
    return value.pt if value else 0.0


def space_after_pt(paragraph: Paragraph) -> float:
    value = paragraph.paragraph_format.space_after
    return value.pt if value else 0.0


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
    indent = paragraph.paragraph_format.first_line_indent
    if indent is None:
        return None
    return indent.inches


def set_first_line_indent(paragraph: Paragraph) -> None:
    paragraph.paragraph_format.first_line_indent = Inches(FIRST_LINE_INDENT_INCHES)
    paragraph.paragraph_format.left_indent = None


def clear_first_line_indent(paragraph: Paragraph) -> None:
    paragraph.paragraph_format.first_line_indent = Inches(0)


def is_hanging_indent(paragraph: Paragraph) -> Optional[bool]:
    fmt = paragraph.paragraph_format
    left = fmt.left_indent
    first = fmt.first_line_indent
    if left is None or first is None:
        return None
    return (
        abs(left.inches - HANGING_INDENT_INCHES) < 0.01
        and abs(first.inches + HANGING_INDENT_INCHES) < 0.01
    )


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
