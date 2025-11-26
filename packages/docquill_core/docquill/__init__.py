"""
DocQuill - Professional DOCX document processing library.

This package provides a complete solution for parsing, interpreting, and rendering
Microsoft Word DOCX documents with AI-ready JSON export and round-trip editing.

Features:
- Full DOCX parsing (headers, footers, tables, images, styles, numbering)
- Round-trip editing: DOCX → HTML → DOCX with formatting preservation
- AI-ready JSON export for ML/NLP workflows
- PDF rendering (Python/ReportLab or high-performance Rust backend)
- HTML export (static or editable)
- Placeholder engine (20+ types for document automation)
- Document merging with OPC relationship handling

Quick Start:
    from docquill import Document
    
    doc = Document.open("document.docx")
    doc.to_pdf("output.pdf")
    doc.to_html("output.html")
    
    # AI-ready JSON
    layout = doc.pipeline()
    json_data = layout.to_json()
"""

from .version import __version__, __version_info__

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

# Core imports - optional to allow partial imports
try:
    from .document import Document
except ImportError:
    Document = None

try:
    from .parser import PackageReader, XMLParser
except ImportError:
    PackageReader = None
    XMLParser = None

try:
    from .normalize import normalize_docx
except ImportError:
    normalize_docx = None

# Simple High-Level API - main entry point for users
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

# Document API imports - Jinja-like functionality
try:
    from .document_api import Document as DocumentAPI
except ImportError:
    DocumentAPI = None

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

__author__ = "AddNap"

__all__ = [
    # Version
    "__version__",
    "__version_info__",
    
    # Simple High-Level API (main entry point)
    "Document",
    "open_document",
    "create_document",
    "fill_template",
    "merge_documents",
    "render_to_html",
    "render_to_pdf",
    
    # Advanced API
    "DocumentAPI",
    "PackageReader", 
    "XMLParser",
    
    # Placeholder Engine
    "PlaceholderEngine",
    "PlaceholderInfo",
    
    # Document Merger
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

    # Utilities
    "normalize_docx",
]


def main():
    """CLI entry point."""
    from .cli import main as cli_main
    cli_main()
