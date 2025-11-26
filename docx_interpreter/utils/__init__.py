"""
Utils module for DOCX document utilities.

This module contains all utility functions and helper classes
for DOCX document processing.
"""

from .units import UnitsConverter
from .xml_utils import XMLUtils
from .color_utils import ColorUtils
from .logger import get_logger
from .rich_logger import RichLogger, get_rich_logger, setup_logging
from .validators import DocumentValidators
from .enums import (
    AlignmentType,
    BreakType,
    ListType,
    StyleType,
    FieldType,
    ImageType
)
from .element_types import (
    ElementType,
    ElementCategory,
    ExportFormat,
    RenderFormat,
    ValidationLevel,
    LogLevel,
    StyleType as ElementStyleType,
    TableStyle,
    Alignment,
    VerticalAlignment,
    FontWeight,
    FontStyle,
    TextDecoration,
    BorderStyle,
    PageOrientation,
    PageSize,
    ImageFormat,
    MediaType,
    RelationshipType,
    DocumentType,
    ComplexityLevel,
    ReadingDifficulty,
    ContentBalance
)
from .exceptions import (
    DocumentError,
    ParsingError,
    PackageError,
    RelationshipError,
    SectionParsingError
)
from .id_manager import IDManager
from .cache import Cache

__all__ = [
    "UnitsConverter",
    "XMLUtils",
    "ColorUtils",
    "get_logger",
    "RichLogger",
    "get_rich_logger",
    "setup_logging",
    "DocumentValidators",
    "AlignmentType",
    "BreakType",
    "ListType",
    "StyleType",
    "FieldType",
    "ImageType",
    "ElementType",
    "ElementCategory",
    "ExportFormat",
    "RenderFormat",
    "ValidationLevel",
    "LogLevel",
    "ElementStyleType",
    "TableStyle",
    "Alignment",
    "VerticalAlignment",
    "FontWeight",
    "FontStyle",
    "TextDecoration",
    "BorderStyle",
    "PageOrientation",
    "PageSize",
    "ImageFormat",
    "MediaType",
    "RelationshipType",
    "DocumentType",
    "ComplexityLevel",
    "ReadingDifficulty",
    "ContentBalance",
    "DocumentError",
    "ParsingError",
    "PackageError",
    "RelationshipError",
    "SectionParsingError",
    "IDManager",
    "Cache",
]
