"""Common enumerations used across the DOCX interpreter models."""

from __future__ import annotations

from enum import Enum


class AlignmentType(str, Enum):
    """Text alignment modes supported by Word documents."""

    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    JUSTIFY = "justify"
    DISTRIBUTE = "distribute"
    THAI_DISTRIBUTE = "thai_distribute"
    JUSTIFY_LOW = "justify_low"


class BreakType(str, Enum):
    """Supported break kinds for runs and paragraphs."""

    LINE = "line"
    PAGE = "page"
    COLUMN = "column"
    SECTION = "section"


class ListType(str, Enum):
    """List numbering formats supported during layout."""

    BULLET = "bullet"
    NUMBERED = "numbered"
    MULTILEVEL = "multilevel"
    OUTLINE = "outline"


class StyleType(str, Enum):
    """High-level style families defined by Word processing documents."""

    PARAGRAPH = "paragraph"
    CHARACTER = "character"
    TABLE = "table"
    NUMBERING = "numbering"


class FieldType(str, Enum):
    """Field codes detected inside runs."""

    PAGE = "PAGE"
    NUMPAGES = "NUMPAGES"
    DATE = "DATE"
    TIME = "TIME"
    HYPERLINK = "HYPERLINK"
    AUTHOR = "AUTHOR"


class ImageType(str, Enum):
    """Drawing types encountered in documents."""

    INLINE = "inline"
    ANCHORED = "anchor"
    BACKGROUND = "background"
    SHAPE = "shape"
