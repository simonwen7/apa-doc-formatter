"""APA 7 Student Paper profile constants."""

from __future__ import annotations

PROFILE_ID = "apa7_student"
PROFILE_LABEL = "APA 7 Student Paper"

# Page format (Publication Manual / Student Paper Setup Guide)
MARGIN_INCHES = 1.0
DOUBLE_LINE_SPACING = 2.0
FIRST_LINE_INDENT_INCHES = 0.5
HANGING_INDENT_INCHES = 0.5

# APA 7 permits multiple fonts. Do not treat non-TNR as invalid.
APA_VALID_FONTS = {
    ("times new roman", 12),
    ("arial", 11),
    ("calibri", 11),
    ("georgia", 11),
    ("lucida sans unicode", 10),
    ("computer modern", 10),
}

DEFAULT_SAFE_CONFIDENCE = 0.95
HIGH_SAFE_CONFIDENCE = 0.99
