"""Centralized effective Word formatting resolution.

Microsoft Word formatting is hierarchical. Direct paragraph/run properties of
``None`` mean inherit — never treat inherit as APA-compliant by itself.

Resolution order (conservative):
  DIRECT → PARAGRAPH_STYLE → BASE_STYLE chain → DOC_DEFAULT → WORD_DEFAULT

ECMA-376 / WordprocessingML (``w:spacing`` / ``@w:line``): when line spacing is
never specified anywhere in the style hierarchy (including empty
``w:pPrDefault``), consumers shall apply single (no additional) line spacing.
See OOXML Part 1 §17.3.1.33. That deterministic root is ``WORD_DEFAULT``, not
``UNKNOWN``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, Optional

from docx.enum.text import WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Length, Twips
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from app.apa.profile import DOUBLE_LINE_SPACING, HANGING_INDENT_INCHES


class FormatSource(str, Enum):
    DIRECT = "DIRECT"
    PARAGRAPH_STYLE = "PARAGRAPH_STYLE"
    BASE_STYLE = "BASE_STYLE"
    DOC_DEFAULT = "DOC_DEFAULT"
    WORD_DEFAULT = "WORD_DEFAULT"
    THEME = "THEME"
    UNKNOWN = "UNKNOWN"


# ECMA-376 §17.3.1.33: absent line spacing in the full hierarchy → single.
WORD_DEFAULT_LINE_SPACING_MULTIPLE = 1.0
# Absent indent attributes → no indent (flush).
WORD_DEFAULT_INDENT_INCHES = 0.0


class FormatVerdict(str, Enum):
    VERIFIED_COMPLIANT = "VERIFIED_COMPLIANT"
    VERIFIED_VIOLATION = "VERIFIED_VIOLATION"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class ResolvedValue:
    value: Any
    source: FormatSource

    @property
    def resolved(self) -> bool:
        return self.source != FormatSource.UNKNOWN and self.value is not None


@dataclass(frozen=True)
class EffectiveParagraphFormat:
    line_spacing_multiple: ResolvedValue  # float multiple (2.0 = double) or None
    line_spacing_rule: ResolvedValue
    space_before_pt: ResolvedValue
    space_after_pt: ResolvedValue
    first_line_indent_inches: ResolvedValue
    left_indent_inches: ResolvedValue
    alignment: ResolvedValue
    style_name: Optional[str]


@dataclass(frozen=True)
class EffectiveRunFormat:
    font_family: ResolvedValue
    font_size_pt: ResolvedValue
    bold: ResolvedValue
    italic: ResolvedValue
    color_rgb: ResolvedValue


def walk_style_chain(style) -> Iterator[Any]:
    seen: set[int] = set()
    current = style
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = getattr(current, "base_style", None)


def _length_inches(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value.inches)
    except Exception:
        return None


def _length_pt(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value.pt)
    except Exception:
        return None


def _line_spacing_as_multiple(spacing, rule) -> Optional[float]:
    """Normalize python-docx line spacing to a line multiple when possible."""
    if rule == WD_LINE_SPACING.DOUBLE:
        return DOUBLE_LINE_SPACING
    if rule == WD_LINE_SPACING.SINGLE:
        return 1.0
    if rule == WD_LINE_SPACING.ONE_POINT_FIVE:
        return 1.5
    if isinstance(spacing, float):
        return float(spacing)
    if spacing is None and rule is None:
        return None
    try:
        if hasattr(spacing, "pt") and spacing.pt is not None:
            # Exact point spacing: APA double ≈ 24pt for 12pt font.
            return float(spacing.pt) / 12.0
    except Exception:
        pass
    if spacing == DOUBLE_LINE_SPACING:
        return DOUBLE_LINE_SPACING
    return None


def _read_ppr_spacing_multiple(pPr) -> Optional[float]:
    if pPr is None:
        return None
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        return None
    line = spacing.get(qn("w:line"))
    line_rule = spacing.get(qn("w:lineRule"))
    if line is None:
        return None
    try:
        line_val = int(line)
    except ValueError:
        return None
    # Word: auto line is 240ths of a line.
    if line_rule in (None, "auto"):
        return line_val / 240.0
    if line_rule == "exact" or line_rule == "atLeast":
        # twips → points → approx multiple at 12pt
        return (line_val / 20.0) / 12.0
    return None


def _doc_defaults_element(paragraph: Paragraph):
    try:
        styles_el = paragraph.part.document.styles.element
    except Exception:
        return None
    return styles_el.find(qn("w:docDefaults"))


def _doc_default_paragraph_spacing(paragraph: Paragraph) -> Optional[float]:
    doc_defaults = _doc_defaults_element(paragraph)
    if doc_defaults is None:
        return None
    ppr_default = doc_defaults.find(qn("w:pPrDefault"))
    if ppr_default is None:
        return None
    pPr = ppr_default.find(qn("w:pPr"))
    return _read_ppr_spacing_multiple(pPr)


def _doc_defaults_inspectable(paragraph: Paragraph) -> bool:
    """True when styles.xml docDefaults can be read (even if empty)."""
    return _doc_defaults_element(paragraph) is not None


def _doc_default_space_before_after(paragraph: Paragraph) -> tuple[Optional[float], Optional[float]]:
    try:
        styles_el = paragraph.part.document.styles.element
    except Exception:
        return None, None
    doc_defaults = styles_el.find(qn("w:docDefaults"))
    if doc_defaults is None:
        return None, None
    ppr_default = doc_defaults.find(qn("w:pPrDefault"))
    if ppr_default is None:
        return None, None
    pPr = ppr_default.find(qn("w:pPr"))
    if pPr is None:
        return None, None
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        return None, None
    before = spacing.get(qn("w:before"))
    after = spacing.get(qn("w:after"))

    def twips_to_pt(raw: Optional[str]) -> Optional[float]:
        if raw is None:
            return None
        try:
            return int(raw) / 20.0
        except ValueError:
            return None

    return twips_to_pt(before), twips_to_pt(after)


def _doc_default_font(paragraph: Paragraph) -> tuple[Optional[str], Optional[float]]:
    try:
        styles_el = paragraph.part.document.styles.element
    except Exception:
        return None, None
    doc_defaults = styles_el.find(qn("w:docDefaults"))
    if doc_defaults is None:
        return None, None
    rpr_default = doc_defaults.find(qn("w:rPrDefault"))
    if rpr_default is None:
        return None, None
    rPr = rpr_default.find(qn("w:rPr"))
    if rPr is None:
        return None, None
    name = None
    rfonts = rPr.find(qn("w:rFonts"))
    if rfonts is not None:
        name = (
            rfonts.get(qn("w:ascii"))
            or rfonts.get(qn("w:hAnsi"))
            or rfonts.get(qn("w:eastAsia"))
        )
    size_pt = None
    sz = rPr.find(qn("w:sz"))
    if sz is not None and sz.get(qn("w:val")):
        try:
            size_pt = int(sz.get(qn("w:val"))) / 2.0
        except ValueError:
            size_pt = None
    return name, size_pt


def resolve_effective_paragraph_format(paragraph: Paragraph) -> EffectiveParagraphFormat:
    fmt = paragraph.paragraph_format
    style_name = None
    try:
        style_name = paragraph.style.name if paragraph.style else None
    except Exception:
        style_name = None

    # --- line spacing ---
    # Sources: DIRECT → style/basedOn → docDefaults → WORD_DEFAULT (ECMA single).
    direct_mult = _line_spacing_as_multiple(fmt.line_spacing, fmt.line_spacing_rule)
    if direct_mult is not None or fmt.line_spacing_rule is not None:
        line_spacing = ResolvedValue(direct_mult, FormatSource.DIRECT)
        line_rule = ResolvedValue(fmt.line_spacing_rule, FormatSource.DIRECT)
    else:
        line_spacing = ResolvedValue(None, FormatSource.UNKNOWN)
        line_rule = ResolvedValue(None, FormatSource.UNKNOWN)
        try:
            styles = list(walk_style_chain(paragraph.style))
        except Exception:
            styles = []
        for index, style in enumerate(styles):
            spf = style.paragraph_format
            mult = _line_spacing_as_multiple(spf.line_spacing, spf.line_spacing_rule)
            if mult is not None or spf.line_spacing_rule is not None:
                source = (
                    FormatSource.PARAGRAPH_STYLE if index == 0 else FormatSource.BASE_STYLE
                )
                line_spacing = ResolvedValue(mult, source)
                line_rule = ResolvedValue(spf.line_spacing_rule, source)
                break
        if line_spacing.source == FormatSource.UNKNOWN:
            default_mult = _doc_default_paragraph_spacing(paragraph)
            if default_mult is not None:
                line_spacing = ResolvedValue(default_mult, FormatSource.DOC_DEFAULT)
                line_rule = ResolvedValue(None, FormatSource.DOC_DEFAULT)
        if line_spacing.source == FormatSource.UNKNOWN and _doc_defaults_inspectable(
            paragraph
        ):
            # Full hierarchy inspected; no w:line anywhere → Word single spacing.
            line_spacing = ResolvedValue(
                WORD_DEFAULT_LINE_SPACING_MULTIPLE, FormatSource.WORD_DEFAULT
            )
            line_rule = ResolvedValue(WD_LINE_SPACING.SINGLE, FormatSource.WORD_DEFAULT)

    # --- space before/after ---
    def resolve_space(attr: str) -> ResolvedValue:
        direct = getattr(fmt, attr)
        if direct is not None:
            return ResolvedValue(_length_pt(direct), FormatSource.DIRECT)
        try:
            styles = list(walk_style_chain(paragraph.style))
        except Exception:
            styles = []
        for index, style in enumerate(styles):
            value = getattr(style.paragraph_format, attr)
            if value is not None:
                source = (
                    FormatSource.PARAGRAPH_STYLE if index == 0 else FormatSource.BASE_STYLE
                )
                return ResolvedValue(_length_pt(value), source)
        before_def, after_def = _doc_default_space_before_after(paragraph)
        default = before_def if attr == "space_before" else after_def
        if default is not None:
            return ResolvedValue(default, FormatSource.DOC_DEFAULT)
        # Explicit absence after full walk ≈ 0 for APA "no extra spacing" checks,
        # but mark as DOC_DEFAULT/unknown carefully: treat as resolved 0 only when
        # style chain was inspectable.
        if styles is not None:
            return ResolvedValue(0.0, FormatSource.PARAGRAPH_STYLE)
        return ResolvedValue(None, FormatSource.UNKNOWN)

    space_before = resolve_space("space_before")
    space_after = resolve_space("space_after")

    # --- indents ---
    def resolve_indent(attr: str) -> ResolvedValue:
        direct = getattr(fmt, attr)
        if direct is not None:
            return ResolvedValue(_length_inches(direct), FormatSource.DIRECT)
        try:
            styles = list(walk_style_chain(paragraph.style))
        except Exception:
            styles = []
        for index, style in enumerate(styles):
            value = getattr(style.paragraph_format, attr)
            if value is not None:
                source = (
                    FormatSource.PARAGRAPH_STYLE if index == 0 else FormatSource.BASE_STYLE
                )
                return ResolvedValue(_length_inches(value), source)
        if _doc_defaults_inspectable(paragraph):
            # Absent indent in hierarchy → Word flush (0).
            return ResolvedValue(
                WORD_DEFAULT_INDENT_INCHES, FormatSource.WORD_DEFAULT
            )
        return ResolvedValue(None, FormatSource.UNKNOWN)

    first_indent = resolve_indent("first_line_indent")
    left_indent = resolve_indent("left_indent")

    # --- alignment ---
    if fmt.alignment is not None:
        alignment = ResolvedValue(fmt.alignment, FormatSource.DIRECT)
    else:
        alignment = ResolvedValue(None, FormatSource.UNKNOWN)
        try:
            styles = list(walk_style_chain(paragraph.style))
        except Exception:
            styles = []
        for index, style in enumerate(styles):
            if style.paragraph_format.alignment is not None:
                source = (
                    FormatSource.PARAGRAPH_STYLE if index == 0 else FormatSource.BASE_STYLE
                )
                alignment = ResolvedValue(style.paragraph_format.alignment, source)
                break

    return EffectiveParagraphFormat(
        line_spacing_multiple=line_spacing,
        line_spacing_rule=line_rule,
        space_before_pt=space_before,
        space_after_pt=space_after,
        first_line_indent_inches=first_indent,
        left_indent_inches=left_indent,
        alignment=alignment,
        style_name=style_name,
    )


def resolve_effective_run_format(run: Run, paragraph: Paragraph) -> EffectiveRunFormat:
    font = run.font

    def from_run_or_styles(getter) -> ResolvedValue:
        direct = getter(font)
        if direct is not None:
            return ResolvedValue(direct, FormatSource.DIRECT)
        try:
            styles = list(walk_style_chain(paragraph.style))
        except Exception:
            styles = []
        for index, style in enumerate(styles):
            value = getter(style.font) if style.font else None
            if value is not None:
                source = (
                    FormatSource.PARAGRAPH_STYLE if index == 0 else FormatSource.BASE_STYLE
                )
                return ResolvedValue(value, source)
        return ResolvedValue(None, FormatSource.UNKNOWN)

    family = from_run_or_styles(lambda f: f.name if f else None)
    size = from_run_or_styles(lambda f: f.size.pt if f and f.size else None)
    bold = from_run_or_styles(lambda f: f.bold if f else None)
    italic = from_run_or_styles(lambda f: f.italic if f else None)

    color_val = None
    color_source = FormatSource.UNKNOWN
    try:
        if font.color and font.color.rgb is not None:
            color_val = str(font.color.rgb)
            color_source = FormatSource.DIRECT
    except Exception:
        pass
    if color_val is None:
        try:
            for index, style in enumerate(walk_style_chain(paragraph.style)):
                if style.font and style.font.color and style.font.color.rgb is not None:
                    color_val = str(style.font.color.rgb)
                    color_source = (
                        FormatSource.PARAGRAPH_STYLE
                        if index == 0
                        else FormatSource.BASE_STYLE
                    )
                    break
        except Exception:
            pass

    if family.source == FormatSource.UNKNOWN or size.source == FormatSource.UNKNOWN:
        def_name, def_size = _doc_default_font(paragraph)
        if family.source == FormatSource.UNKNOWN and def_name:
            family = ResolvedValue(def_name, FormatSource.DOC_DEFAULT)
        if size.source == FormatSource.UNKNOWN and def_size is not None:
            size = ResolvedValue(def_size, FormatSource.DOC_DEFAULT)

    return EffectiveRunFormat(
        font_family=family,
        font_size_pt=size,
        bold=bold,
        italic=italic,
        color_rgb=ResolvedValue(color_val, color_source if color_val else FormatSource.UNKNOWN),
    )


def line_spacing_verdict(paragraph: Paragraph) -> FormatVerdict:
    eff = resolve_effective_paragraph_format(paragraph)
    mult = eff.line_spacing_multiple.value
    if mult is None:
        return FormatVerdict.UNRESOLVED
    if abs(float(mult) - DOUBLE_LINE_SPACING) < 0.05:
        return FormatVerdict.VERIFIED_COMPLIANT
    return FormatVerdict.VERIFIED_VIOLATION


def hanging_indent_verdict(paragraph: Paragraph) -> FormatVerdict:
    eff = resolve_effective_paragraph_format(paragraph)
    left = eff.left_indent_inches.value
    first = eff.first_line_indent_inches.value
    # Ordinary positive first-line indent is never a hanging indent.
    if first is not None and float(first) > 0.01:
        return FormatVerdict.VERIFIED_VIOLATION
    if left is None or first is None:
        return FormatVerdict.UNRESOLVED
    if (
        abs(float(left) - HANGING_INDENT_INCHES) < 0.01
        and abs(float(first) + HANGING_INDENT_INCHES) < 0.01
    ):
        return FormatVerdict.VERIFIED_COMPLIANT
    return FormatVerdict.VERIFIED_VIOLATION
