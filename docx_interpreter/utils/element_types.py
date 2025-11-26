"""
Element types for DOCX documents.

Provides enums for different element types and categories.
"""

from enum import Enum, auto
from typing import List, Dict, Any


class ElementType(Enum):
    """Element types in DOCX documents."""
    
    # Document structure
    DOCUMENT = "document"
    BODY = "body"
    SECTION = "section"
    PAGE = "page"
    
    # Text elements
    PARAGRAPH = "paragraph"
    RUN = "run"
    TEXT = "text"
    FIELD = "field"
    HYPERLINK = "hyperlink"
    
    # Table elements
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    
    # Graphical elements
    IMAGE = "image"
    TEXTBOX = "textbox"
    SHAPE = "shape"
    SMARTART = "smartart"
    CHART = "chart"
    
    # Layout elements
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    
    # Meta elements
    COMMENT = "comment"
    BOOKMARK = "bookmark"
    CONTROLBOX = "controlbox"
    
    # Style elements
    STYLE_REF = "style_ref"
    RELATION_REF = "relation_ref"
    NUMBERING = "numbering"
    METADATA_REF = "metadata_ref"


class ElementCategory(Enum):
    """Element categories for grouping."""
    
    STRUCTURAL = "structural"
    TEXT = "text"
    TABLE = "table"
    GRAPHICAL = "graphical"
    LAYOUT = "layout"
    META = "meta"
    STYLE = "style"


class ExportFormat(Enum):
    """Supported export formats."""
    
    HTML = "html"
    PDF = "pdf"
    MARKDOWN = "markdown"
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    XLSX = "xlsx"
    TEXT = "text"


class RenderFormat(Enum):
    """Supported render formats."""
    
    HTML = "html"
    PDF = "pdf"
    MARKDOWN = "markdown"
    TEXT = "text"
    TEMPLATE = "template"


class ValidationLevel(Enum):
    """Validation levels."""
    
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class LogLevel(Enum):
    """Log levels."""
    
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class StyleType(Enum):
    """Style types."""
    
    PARAGRAPH = "paragraph"
    CHARACTER = "character"
    TABLE = "table"
    NUMBERING = "numbering"


class TableStyle(Enum):
    """Table styles."""
    
    DEFAULT = "default"
    BORDERED = "bordered"
    GRID = "grid"
    LIST_TABLE = "list_table"
    LIGHT_SHADING = "light_shading"
    MEDIUM_SHADING = "medium_shading"
    DARK_SHADING = "dark_shading"


class Alignment(Enum):
    """Text alignment."""
    
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class VerticalAlignment(Enum):
    """Vertical alignment."""
    
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class FontWeight(Enum):
    """Font weight."""
    
    NORMAL = "normal"
    BOLD = "bold"
    LIGHT = GREY = "light"


class FontStyle(Enum):
    """Font style."""
    
    NORMAL = "normal"
    ITALIC = "italic"
    OBLIQUE = "oblique"


class TextDecoration(Enum):
    """Text decoration."""
    
    NONE = "none"
    UNDERLINE = "underline"
    OVERLINE = "overline"
    LINE_THROUGH = "line_through"


class BorderStyle(Enum):
    """Border styles."""
    
    NONE = "none"
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    DOUBLE = "double"
    GROOVE = "groove"
    RIDGE = "ridge"
    INSET = "inset"
    OUTSET = "outset"


class PageOrientation(Enum):
    """Page orientation."""
    
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class PageSize(Enum):
    """Page sizes."""
    
    A4 = "a4"
    A3 = "a3"
    A5 = "a5"
    LETTER = "letter"
    LEGAL = "legal"
    TABLOID = "tabloid"


class ImageFormat(Enum):
    """Image formats."""
    
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    TIFF = "tiff"
    SVG = "svg"
    WEBP = "webp"


class MediaType(Enum):
    """Media types."""
    
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    EMBEDDED = "embedded"


class RelationshipType(Enum):
    """Relationship types."""
    
    IMAGE = "image"
    HYPERLINK = "hyperlink"
    CHART = "chart"
    EMBEDDED = "embedded"
    EXTERNAL = "external"


class DocumentType(Enum):
    """Document types."""
    
    DOCUMENT = "document"
    TEMPLATE = "template"
    MACRO_ENABLED = "macro_enabled"
    MACRO_ENABLED_TEMPLATE = "macro_enabled_template"


class ComplexityLevel(Enum):
    """Document complexity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReadingDifficulty(Enum):
    """Reading difficulty levels."""
    
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ContentBalance(Enum):
    """Content balance types."""
    
    TEXT_HEAVY = "text_heavy"
    TABLE_HEAVY = "table_heavy"
    IMAGE_HEAVY = "image_heavy"
    MIXED_LAYOUT = "mixed_layout"
    BALANCED = "balanced"


# Element type mappings
ELEMENT_TYPE_MAPPING = {
    ElementType.DOCUMENT: ElementCategory.STRUCTURAL,
    ElementType.BODY: ElementCategory.STRUCTURAL,
    ElementType.SECTION: ElementCategory.STRUCTURAL,
    ElementType.PAGE: ElementCategory.STRUCTURAL,
    
    ElementType.PARAGRAPH: ElementCategory.TEXT,
    ElementType.RUN: ElementCategory.TEXT,
    ElementType.TEXT: ElementCategory.TEXT,
    ElementType.FIELD: ElementCategory.TEXT,
    ElementType.HYPERLINK: ElementCategory.TEXT,
    
    ElementType.TABLE: ElementCategory.TABLE,
    ElementType.TABLE_ROW: ElementCategory.TABLE,
    ElementType.TABLE_CELL: ElementCategory.TABLE,
    
    ElementType.IMAGE: ElementCategory.GRAPHICAL,
    ElementType.TEXTBOX: ElementCategory.GRAPHICAL,
    ElementType.SHAPE: ElementCategory.GRAPHICAL,
    ElementType.SMARTART: ElementCategory.GRAPHICAL,
    ElementType.CHART: ElementCategory.GRAPHICAL,
    
    ElementType.HEADER: ElementCategory.LAYOUT,
    ElementType.FOOTER: ElementCategory.LAYOUT,
    ElementType.FOOTNOTE: ElementCategory.LAYOUT,
    ElementType.ENDNOTE: ElementCategory.LAYOUT,
    
    ElementType.COMMENT: ElementCategory.META,
    ElementType.BOOKMARK: ElementCategory.META,
    ElementType.CONTROLBOX: ElementCategory.META,
    
    ElementType.STYLE_REF: ElementCategory.STYLE,
    ElementType.RELATION_REF: ElementCategory.STYLE,
    ElementType.NUMBERING: ElementCategory.STYLE,
    ElementType.METADATA_REF: ElementCategory.STYLE,
}


def get_element_category(element_type: ElementType) -> ElementCategory:
    """
    Get element category for element type.
    
    Args:
        element_type: Element type
        
    Returns:
        Element category
    """
    return ELEMENT_TYPE_MAPPING.get(element_type, ElementCategory.STRUCTURAL)


def get_elements_by_category(category: ElementCategory) -> List[ElementType]:
    """
    Get all element types for a category.
    
    Args:
        category: Element category
        
    Returns:
        List of element types
    """
    return [element_type for element_type, cat in ELEMENT_TYPE_MAPPING.items() if cat == category]


def is_text_element(element_type: ElementType) -> bool:
    """
    Check if element type is a text element.
    
    Args:
        element_type: Element type
        
    Returns:
        True if text element
    """
    return get_element_category(element_type) == ElementCategory.TEXT


def is_table_element(element_type: ElementType) -> bool:
    """
    Check if element type is a table element.
    
    Args:
        element_type: Element type
        
    Returns:
        True if table element
    """
    return get_element_category(element_type) == ElementCategory.TABLE


def is_graphical_element(element_type: ElementType) -> bool:
    """
    Check if element type is a graphical element.
    
    Args:
        element_type: Element type
        
    Returns:
        True if graphical element
    """
    return get_element_category(element_type) == ElementCategory.GRAPHICAL


def is_structural_element(element_type: ElementType) -> bool:
    """
    Check if element type is a structural element.
    
    Args:
        element_type: Element type
        
    Returns:
        True if structural element
    """
    return get_element_category(element_type) == ElementCategory.STRUCTURAL
