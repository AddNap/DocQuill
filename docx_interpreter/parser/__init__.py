"""
Parser module for DOCX XML parsing.

This module contains all components responsible for parsing XML content
from DOCX files, including package reading, XML parsing, and specialized
parsers for different document elements.
"""

from .package_reader import PackageReader
from .xml_parser import XMLParser
from .relationships import RelationshipManager
from .settings_parser import SettingsParser
from .header_footer_parser import HeaderFooterParser
from .notes_parser import NotesParser
from .hyperlink_parser import HyperlinkParser
from .table_parser import TableParser
from .font_parser import FontParser
from .validator import DocumentValidator

try:
    from .html_parser import HTMLParser, HTMLContentParser
    _html_parser_available = True
except ImportError:
    _html_parser_available = False
    HTMLParser = None
    HTMLContentParser = None

__all__ = [
    "PackageReader",
    "XMLParser",
    "RelationshipManager",
    "SettingsParser",
    "HeaderFooterParser",
    "NotesParser",
    "HyperlinkParser",
    "TableParser",
    "FontParser",
    "DocumentValidator",
]

if _html_parser_available:
    __all__.extend(["HTMLParser", "HTMLContentParser"])
