"""APA parsing helpers (read-only)."""

from app.apa.parsing.appendices import AppendixAnalysis, analyze_appendices
from app.apa.parsing.citations import CitationCandidate, CitationType, extract_document_citations
from app.apa.parsing.docx_objects import DocumentPreservationReport, compare_document_preservation
from app.apa.parsing.equations import EquationAnalysis, analyze_equations, equation_xml_fingerprint
from app.apa.parsing.figures import FigureAnalysis, analyze_figures
from app.apa.parsing.lists import ListItemAnalysis, analyze_lists
from app.apa.parsing.matching import MatchStatus, match_citations_to_references
from app.apa.parsing.reference_entry import (
    ReferenceEntryAnalysis,
    ReferenceType,
    parse_reference_entry,
)
from app.apa.parsing.span_format import apply_format_to_existing_text_span
from app.apa.parsing.tables import TableAnalysis, analyze_tables

__all__ = [
    "AppendixAnalysis",
    "CitationCandidate",
    "CitationType",
    "DocumentPreservationReport",
    "EquationAnalysis",
    "FigureAnalysis",
    "ListItemAnalysis",
    "MatchStatus",
    "ReferenceEntryAnalysis",
    "ReferenceType",
    "TableAnalysis",
    "analyze_appendices",
    "analyze_equations",
    "analyze_figures",
    "analyze_lists",
    "analyze_tables",
    "apply_format_to_existing_text_span",
    "compare_document_preservation",
    "equation_xml_fingerprint",
    "extract_document_citations",
    "match_citations_to_references",
    "parse_reference_entry",
]
