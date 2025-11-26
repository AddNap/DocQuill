"""
DOCX Interpreter - Comprehensive DOCX parsing and interpretation library.

This package provides a complete solution for parsing, interpreting, and rendering
Microsoft Word DOCX documents. It handles all aspects of DOCX files including:

- XML parsing and document structure extraction
- Style and theme management
- Layout and pagination
- Media handling (images, drawings, SmartArt)
- Metadata extraction
- Export to various formats (HTML, PDF, DOCX)

Main Components:
- Document: Central controller class
- Parser: XML parsing layer
- Models: Semantic document models
- Layout: Page and section management
- Media: Multimedia handling
- Styles: Style and theme management
- Metadata: Document properties
- Renderers: Export functionality
- Utils: Helper utilities
"""

# Core imports - optional to allow partial imports
try:
    from .document import Document
except ImportError:
    Document = None

# Exceptions - always available
from .exceptions import (
    DocxInterpreterError,
    ParsingError,
    LayoutError,
    RenderingError,
    FontError,
    StyleError,
    NumberingError,
    GeometryError,
    MediaError,
    CompilationError,
)

try:
    from .parser import PackageReader, XMLParser
except ImportError:
    PackageReader = None
    XMLParser = None

try:
    from .normalize import normalize_docx
except ImportError:
    normalize_docx = None

# PDF Engine imports - optional
try:
    from .pdf_engine import (
        PDFEngine, 
        PageSize, 
        Alignment, 
        FontWeight, 
        FontStyle,
        FontInfo,
        TextLine,
        PageGeometry,
        TableGeometry,
        render_docx_to_pdf,
        create_pdf_engine
    )
except ImportError:
    # PDF engine not available
    PDFEngine = None
    PageSize = None
    Alignment = None
    FontWeight = None
    FontStyle = None
    FontInfo = None
    TextLine = None
    PageGeometry = None
    TableGeometry = None
    render_docx_to_pdf = None
    create_pdf_engine = None

# PDF Integration imports - optional
try:
    from .pdf_integration import (
        DOCXInterpreterPDFRenderer,
        ParagraphAdapter,
        TableAdapter,
        render_docx_file_to_pdf,
        create_pdf_renderer
    )
except ImportError:
    DOCXInterpreterPDFRenderer = None
    ParagraphAdapter = None
    TableAdapter = None
    render_docx_file_to_pdf = None
    create_pdf_renderer = None

__version__ = "1.0.0"
__author__ = "DocQuill Team"

# Document API imports - Jinja-like functionality
try:
    from .document_api import Document as DocumentAPI
except ImportError:
    DocumentAPI = None

# Simple High-Level API - główny punkt wejścia dla użytkowników
try:
    from .api import (
        Document,
        open_document,
        create_document,
        fill_template,
        merge_documents,
        render_to_html,
        render_to_pdf,
    )
except ImportError:
    Document = None
    open_document = None
    create_document = None
    fill_template = None
    merge_documents = None
    render_to_html = None
    render_to_pdf = None

# Placeholder Engine imports
try:
    from .engine.placeholder_engine import PlaceholderEngine, PlaceholderInfo
except ImportError:
    PlaceholderEngine = None
    PlaceholderInfo = None

# Document Merger imports
try:
    from .merger import DocumentMerger, MergeOptions
except ImportError:
    DocumentMerger = None
    MergeOptions = None

__all__ = [
    # Simple High-Level API (główny punkt wejścia)
    "Document",           # Główna klasa Document
    "open_document",     # Convenience function
    "create_document",   # Convenience function
    "fill_template",    # Convenience function
    "merge_documents",   # Convenience function
    "render_to_html",    # Convenience function
    "render_to_pdf",     # Convenience function
    
    # Advanced API
    "DocumentAPI",       # Zaawansowane Document API
    "PackageReader", 
    "XMLParser",
    
    # Placeholder Engine (Jinja-like)
    "PlaceholderEngine",
    "PlaceholderInfo",
    
    # Document Merger (docx-compose like)
    "DocumentMerger",
    "MergeOptions",
    
    # PDF Engine
    "PDFEngine",
    "PageSize",
    "Alignment", 
    "FontWeight",
    "FontStyle",
    "FontInfo",
    "TextLine",
    "PageGeometry", 
    "TableGeometry",
    "render_docx_to_pdf",
    "create_pdf_engine",
    
    # PDF Integration
    "DOCXInterpreterPDFRenderer",
    "ParagraphAdapter",
    "TableAdapter", 
    "render_docx_file_to_pdf",
    "create_pdf_renderer",
    
    # Exceptions
    "DocxInterpreterError",
    "ParsingError",
    "LayoutError",
    "RenderingError",
    "FontError",
    "StyleError",
    "NumberingError",
    "GeometryError",
    "MediaError",
    "CompilationError",

    # Maintenance utilities
    "normalize_docx",
]

# CLI entry point
def main():
    """CLI entry point."""
    from .cli import main as cli_main
    cli_main()
