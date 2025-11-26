"""

Document API - High-level API for DOCX document manipulation (Jinja-like).

This module provides a convenient API similar to the old DocQuill library,
but uses existing models and renderers without modifying them.

"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, BinaryIO
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)

from .models.body import Body
from .models.paragraph import Paragraph
from .models.run import Run
from .models.table import Table
from .models.numbering import NumberingGroup
from .models.watermark import Watermark
from .engine.placeholder_engine import PlaceholderEngine, PlaceholderInfo
from .exceptions import DocxInterpreterError


class Document:
    """

    High-level API for DOCX document manipulation.

    Provides convenient methods similar to the old DocQuill library:
    - add_paragraph(), replace_text(), save()
    - fill_placeholders() - Jinja-like placeholder system
    - create_numbered_list(), create_bullet_list()
    - merge(), append(), prepend()

    Uses existing models and renderers without modifying them.

    """
    
    def __init__(self, document_model: Optional[Any] = None) -> None:
        """

        Initializes Document API.

        Args:
        document_model: Optional existing document model

        """
        self._document_model = document_model
        self._body: Optional[Body] = None
        self._placeholder_engine: Optional[PlaceholderEngine] = None
        self._watermarks: List[Any] = []  # List of watermarks
        
        # Initialize body if document model is available
        if document_model:
            self._init_from_model(document_model)
        else:
            # Create empty document
            self._body = Body()
            self._placeholder_engine = PlaceholderEngine(self)
    
    def _init_from_model(self, document_model: Any) -> None:
        """Initializes Document from existing model."""
        # Try to get body from model
        if hasattr(document_model, 'body'):
            self._body = document_model.body
        elif hasattr(document_model, '_body'):
            self._body = document_model._body
        elif hasattr(document_model, 'get_body'):
            self._body = document_model.get_body()
        else:
            # Create new body
            self._body = Body()
        
        self._placeholder_engine = PlaceholderEngine(self)
    
    @classmethod
    def open(cls, file_path: Union[str, Path, BinaryIO]) -> "Document":
        """

        Opens document from DOCX file.

        Args:
        file_path: Path to DOCX file

        Returns:
        Document: Opened document

        """
        # Import parsers
        from .parser.package_reader import PackageReader
        from .parser.xml_parser import XMLParser
        from .models.body import Body
        
        # Open document
        reader = PackageReader(file_path)
        parser = XMLParser(reader)
        
        # Parsuj body
        body = parser.parse_body()
        
        # Create simple document model
        document_model = type('DocumentModel', (), {
            'body': body,
            'parser': parser,
            '_package_reader': reader
        })()
        
        return cls(document_model)
    
    @property
    def body(self) -> Body:
        """Zwraca body dokumentu."""
        if self._body is None:
            self._body = Body()
        return self._body
    
    def add_paragraph(
        self, 
        text: str = "", 
        style: Optional[str] = None
    ) -> Paragraph:
        """
        Dodaje paragraf do dokumentu.
        
        Args:
            text: Tekst paragrafu
            style: Nazwa stylu (np. "Heading1", "Normal")
            
        Returns:
            Paragraph: Utworzony paragraf
        """
        para = Paragraph()
        
        if text:
            run = Run(text=text)
            para.add_run(run)
        
        if style:
            para.set_style({'name': style})
        
        self.body.add_paragraph(para)
        return para
    
    def add_run(
        self, 
        paragraph: Paragraph,
        text: str,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        font_color: Optional[str] = None,
        font_size: Optional[int] = None,
        font_name: Optional[str] = None
    ) -> Run:
        """

        Adds run to paragraph with formatting.

        Args:
        paragraph: Paragraph to add run to
        text: Run text
        bold: Whether bold
        italic: Whether italic
        underline: Whether underlined
        font_color: Font color (e.g. "008000")
        font_size: Font size in points
        font_name: Font name

        Returns:
        Run: Created run

        """
        run = Run(text=text)
        run.bold = bold
        run.italic = italic
        run.underline = underline
        
        if font_color:
            run.color = font_color
        if font_size:
            run.font_size = font_size
        if font_name:
            run.font_name = font_name
        
        paragraph.add_run(run)
        return run
    
    def replace_text(
        self,
        old_text: str,
        new_text: str,
        scope: str = "body",
        case_sensitive: bool = False
    ) -> int:
        """

        Replaces text in document.

        Args:
        old_text: Text to replace
        new_text: New text
        scope: Scope ("body", "headers", "footers", "all")
        case_sensitive: Whether to consider case

        Returns:
        Number of replacements

        """
        replacements = 0
        
        if not case_sensitive:
            # Case-insensitive search
            old_text_lower = old_text.lower()
        
        # Replace in body paragraphs
        if scope in ["body", "all"]:
            paragraphs = self.body.get_paragraphs()
            for para in paragraphs:
                runs = para.runs
                for run in runs:
                    run_text = run.get_text() if hasattr(run, 'get_text') else run.text
                    if not run_text:
                        continue
                    
                    if case_sensitive:
                        if old_text in run_text:
                            new_run_text = run_text.replace(old_text, new_text)
                            if hasattr(run, 'text'):
                                run.text = new_run_text
                            replacements += 1
                    else:
                        if old_text_lower in run_text.lower():
                            # Preserve original case
                            import re
                            pattern = re.compile(re.escape(old_text), re.IGNORECASE)
                            new_run_text = pattern.sub(new_text, run_text)
                            if hasattr(run, 'text'):
                                run.text = new_run_text
                            replacements += 1
        
        return replacements
    
    def fill_placeholders(
        self,
        data: Dict[str, Any],
        multi_pass: bool = False,
        max_passes: int = 5
    ) -> int:
        """

        Fills placeholders in document (Jinja-like).

        Args:
        data: Dictionary {placeholder_name: value}
        multi_pass: Whether to use multi-pass rendering
        max_passes: Maximum number of passes

        Returns:
        Number of replaced placeholders

        Examples:
        >>> doc = Document.open("template.docx")
        >>> doc.fill_placeholders({
        ...     "TEXT:Name": "John Smith",
        ...     "DATE:IssueDate": "2025-10-16",
        ...     "CURRENCY:Amount": 1500.50,
        ...     "QR:OrderCode": "ORDER-123",
        ...     "TABLE:Items": {
        ...         "headers": ["Product", "Qty", "Price"],
        ...         "rows": [["Laptop", "1", "4500"], ["Mouse", "2", "150"]]
        ...     },
        ...     "IMAGE:Logo": "logo.png",
        ...     "LIST:Features": ["Fast", "Reliable", "Secure"]
        ... })

        """
        if self._placeholder_engine is None:
            self._placeholder_engine = PlaceholderEngine(self)
        
        return self._placeholder_engine.fill_placeholders(data, multi_pass, max_passes)
    
    def process_conditional_block(self, block_name: str, show: bool) -> bool:
        """

        Processes conditional block (START_name / END_name).

        Args:
        block_name: Block name
        show: Whether to show block (True) or remove (False)

        Returns:
        True if processed

        """
        if self._placeholder_engine is None:
            self._placeholder_engine = PlaceholderEngine(self)
        
        return self._placeholder_engine.process_conditional_block(block_name, show)
    
    def extract_placeholders(self) -> List[PlaceholderInfo]:
        """

        Extracts all placeholders from document.

        Returns:
        List of PlaceholderInfo objects

        """
        if self._placeholder_engine is None:
            self._placeholder_engine = PlaceholderEngine(self)
        
        return self._placeholder_engine.extract_placeholders()
    
    def add_watermark(
        self,
        text: str,
        angle: float = 45.0,
        opacity: float = 0.5,
        color: str = "#CCCCCC",
        font_size: float = 72.0,
        font_name: str = "Arial"
    ) -> Watermark:
        """

        Adds watermark to document.

        Args:
        text: Watermark text
        angle: Rotation angle in degrees (default 45)
        opacity: Opacity 0.0-1.0 (default 0.5)
        color: Text color (default #CCCCCC)
        font_size: Font size in points (default 72)
        font_name: Font name (default Arial)

        Returns:
        Watermark: Created watermark

        Examples:
        >>> doc = Document.open("template.docx")
        >>> doc.add_watermark("CONFIDENTIAL", angle=45, opacity=0.3)
        >>> doc.add_watermark("DRAFT", color="#FF0000", opacity=0.5)

        """
        watermark = Watermark(
            text=text,
            angle=angle,
            opacity=opacity,
            color=color,
            font_size=font_size,
            font_name=font_name
        )
        self._watermarks.append(watermark)
        return watermark
    
    def get_watermarks(self) -> List[Watermark]:
        """

        Returns list of watermarks in document.

        Returns:
        List of watermarks

        """
        return self._watermarks.copy()
    
    @property
    def watermarks(self) -> List[Watermark]:
        """Returns list of watermarks (property)."""
        return self._watermarks
    
    def create_numbered_list(self) -> NumberingGroup:
        """

        Creates numbered list.

        Returns:
        NumberingGroup: Numbering group

        """
        from .models.numbering import NumberingGroup
        
        group = NumberingGroup()
        # Default numbered list configuration
        group.set_format("decimal")
        
        return group
    
    def create_bullet_list(self) -> NumberingGroup:
        """

        Creates bullet list.

        Returns:
        NumberingGroup: Numbering group

        """
        from .models.numbering import NumberingGroup
        
        group = NumberingGroup()
        # Default bullet list configuration
        group.set_format("bullet")
        
        return group
    
    def save(self, file_path: Union[str, Path]) -> None:
        """

        Saves document to DOCX file.

        Args:
        file_path: Path to output file

        Examples:
        >>> doc.save("output.docx")

        """
        from .export.docx_exporter import DOCXExporter
        
        # If document has _file_path (original file), use it as template
        source_docx_path = None
        if hasattr(self._document_model, '_file_path') and self._document_model._file_path:
            source_docx_path = self._document_model._file_path
        elif hasattr(self._document_model, '_source_docx') and self._document_model._source_docx:
            source_docx_path = self._document_model._source_docx
        
        # Use DOCXExporter to save (with source_docx_path if available)
        exporter = DOCXExporter(self._document_model, source_docx_path=source_docx_path)
        success = exporter.export(file_path)
        
        if not success:
            raise Exception(f"Failed to save document to {file_path}")
    
    def merge(
        self,
        other: Union["Document", str, Path],
        page_break: bool = False
    ) -> None:
        """

        Merges document with another document.

        Args:
        other: Another document (Document, file path, or Path)
        page_break: Whether to add page break before merged document

        """
        from .merger import DocumentMerger, MergeOptions
        
        options = MergeOptions(page_break=page_break)
        merger = DocumentMerger(self)
        merger.merge_full(other, options)
    
    def append(
        self,
        other: Union["Document", str, Path],
        page_break: bool = False
    ) -> None:
        """

        Appends document at the end.

        Args:
        other: Another document (Document, file path, or Path)
        page_break: Whether to add page break

        """
        from .merger import DocumentMerger, MergeOptions
        
        options = MergeOptions(page_break=page_break)
        merger = DocumentMerger(self)
        merger.merge_body(other, options, position="append")
    
    def prepend(
        self,
        other: Union["Document", str, Path],
        page_break: bool = False
    ) -> None:
        """

        Prepends document at the beginning.

        Args:
        other: Another document (Document, file path, or Path)
        page_break: Whether to add page break

        """
        from .merger import DocumentMerger, MergeOptions
        
        options = MergeOptions(page_break=page_break)
        merger = DocumentMerger(self)
        merger.merge_body(other, options, position="prepend")
    
    def merge_selective(
        self,
        sources: Dict[str, Union["Document", str, Path]],
        page_break: bool = False
    ) -> None:
        """

        Advanced selective merging of elements from different documents.

        Args:
        sources: Dictionary specifying sources for each element:
        {
        "body": source_doc1,      # Body from this document
        "headers": source_doc2,    # Headers from this document
        "footers": source_doc3,    # Footers from this document
        "sections": source_doc4,   # Sections from this document
        "styles": source_doc5,     # Styles from this document
        "numbering": source_doc6   # Numbering from this document
        }
        page_break: Whether to add page break before merged elements

        Examples:
        >>> doc = Document.open("template.docx")
        >>> doc.merge_selective({
        ...     "body": "content.docx",
        ...     "headers": "header_template.docx",
        ...     "footers": "footer_template.docx",
        ...     "styles": "style_template.docx"
        ... })

        """
        from .merger import DocumentMerger, MergeOptions
        
        options = MergeOptions(page_break=page_break)
        merger = DocumentMerger(self)
        merger.merge_selective(sources, options)
    
    def merge_headers(
        self,
        source: Union["Document", str, Path],
        header_types: Optional[List[str]] = None
    ) -> None:
        """

        Merges headers from source document.

        Args:
        source: Source document
        header_types: List of header types ("default", "first", "even")

        """
        from .merger import DocumentMerger, MergeOptions
        
        options = MergeOptions()
        merger = DocumentMerger(self)
        merger.merge_headers(source, options, header_types)
    
    def merge_footers(
        self,
        source: Union["Document", str, Path],
        footer_types: Optional[List[str]] = None
    ) -> None:
        """

        Merges footers from source document.

        Args:
        source: Source document
        footer_types: List of footer types ("default", "first", "even")

        """
        from .merger import DocumentMerger, MergeOptions
        
        options = MergeOptions()
        merger = DocumentMerger(self)
        merger.merge_footers(source, options, footer_types)
    
    def merge_sections(
        self,
        source: Union["Document", str, Path],
        copy_properties: bool = True
    ) -> None:
        """

        Merges sections from source document (page properties, margins).

        Args:
        source: Source document
        copy_properties: Whether to copy section properties

        """
        from .merger import DocumentMerger, MergeOptions
        
        options = MergeOptions()
        merger = DocumentMerger(self)
        merger.merge_sections(source, options, copy_properties)
    
    def merge_styles(
        self,
        source: Union["Document", str, Path]
    ) -> None:
        """

        Merges styles from source document.

        Args:
        source: Source document

        """
        from .merger import DocumentMerger, MergeOptions
        
        options = MergeOptions()
        merger = DocumentMerger(self)
        merger.merge_styles(source, options)
    
    def apply_layout(
        self,
        template: Union["Document", str, Path],
        header_types: Optional[List[str]] = None,
        footer_types: Optional[List[str]] = None
    ) -> None:
        """

        Applies layout (headers/footers) from template document.

        Convenience method that combines merge_headers() and merge_footers().

        Args:
        template: Template document with headers/footers
        header_types: List of header types to apply (None = all)
        footer_types: List of footer types to apply (None = all)

        Examples:
        >>> doc.apply_layout("template.docx")
        >>> doc.apply_layout("template.docx", header_types=["default"], footer_types=["default"])

        """
        self.merge_headers(template, header_types)
        self.merge_footers(template, footer_types)
    
    def render_html(
        self,
        output_path: Union[str, Path],
        editable: bool = False
    ) -> None:
        """

        Renders document to HTML.

        Args:
        output_path: Path to output HTML file
        editable: Whether HTML should be editable (contenteditable)

        Note:
        Uses existing HTMLRenderer without modification.

        """
        from .renderers import HTMLRenderer
        
        # Use existing renderer
        renderer = HTMLRenderer(self._document_model or self, editable=editable)
        html_content = renderer.render()
        renderer.save_to_file(html_content, output_path)
    
    def render_pdf(
        self,
        output_path: Union[str, Path],
        engine: str = "reportlab",
        page_size: Optional[Tuple[float, float]] = None,
        margins: Optional[Tuple[float, float, float, float]] = None
    ) -> None:
        """

        Renders document to PDF using PDFCompiler.

        Args:
        output_path: Path to output PDF file
        engine: Rendering engine ("reportlab" or "direct") - currently always uses PDFCompiler
        page_size: Page size in points (width, height), default A4 (595, 842)
        margins: Margins in points (top, bottom, left, right), default (72, 72, 72, 72)

        Examples:
        >>> doc.render_pdf("output.pdf")
        >>> doc.render_pdf("output.pdf", page_size=(595, 842), margins=(72, 72, 72, 72))

        """
        from .engine.layout_pipeline import LayoutPipeline
        from .engine.pdf.pdf_compiler import PDFCompiler
        from .engine.geometry import Size, Margins
        from .engine.page_engine import PageConfig
        
        # Default values
        if page_size is None:
            page_size = (595, 842)  # A4 w punktach
        if margins is None:
            margins = (72, 72, 72, 72)  # 1 cal = 72 punkty
        
        # Get package_reader if available
        package_reader = None
        if hasattr(self._document_model, '_package_reader'):
            package_reader = self._document_model._package_reader
        elif hasattr(self._document_model, 'parser') and hasattr(self._document_model.parser, 'package_reader'):
            package_reader = self._document_model.parser.package_reader
        
        # Create PageConfig
        page_config = PageConfig(
            page_size=Size(page_size[0], page_size[1]),
            base_margins=Margins(
                top=margins[0],
                bottom=margins[1],
                left=margins[2],
                right=margins[3]
            )
        )
        
        # Create adapter for LayoutPipeline
        class DocumentAdapter:
            def __init__(self, body_obj, parser, sections=None):
                self.elements = body_obj.children if hasattr(body_obj, 'children') else []
                self.parser = parser
                self._body = body_obj
                # Copy sections from parameter or try to get from parser
                self._sections = sections or []
                if not self._sections and parser and hasattr(parser, 'parse_sections'):
                    try:
                        self._sections = parser.parse_sections()
                    except Exception:
                        self._sections = []
                self._package_reader = package_reader
                self._header_footer_parser = getattr(parser, 'header_footer_parser', None) if parser else None
            
            def get_body(self):
                return self._body
        
        # Pobierz body i parser
        body = self.body
        parser = None
        if hasattr(self._document_model, 'parser'):
            parser = self._document_model.parser
        elif hasattr(self._document_model, '_parser'):
            parser = self._document_model._parser
        
        # Pobierz sekcje z dokumentu lub parsera
        sections = None
        if hasattr(self._document_model, '_sections') and self._document_model._sections:
            sections = self._document_model._sections
        elif parser and hasattr(parser, 'parse_sections'):
            try:
                sections = parser.parse_sections()
            except Exception:
                sections = []
        
        document_model = DocumentAdapter(body, parser, sections)
        
        # Create LayoutPipeline and process document
        pipeline = LayoutPipeline(page_config)
        unified_layout = pipeline.process(
            document_model,
            apply_headers_footers=True,
            validate=False
        )
        
        # Create PDFCompiler and compile to PDF
        compiler = PDFCompiler(
            output_path=str(output_path),
            page_size=page_size,
            package_reader=package_reader
        )
        
        result_path = compiler.compile(unified_layout)
        
        if not result_path.exists():
            raise Exception(f"Failed to generate PDF: {result_path}")
    
    def update_from_html_file(
        self,
        html_path: Union[str, Path],
        preserve_structure: bool = True
    ) -> None:
        """

        Updates document based on edited HTML file.

        Args:
        html_path: Path to HTML file with edited content
        preserve_structure: Whether to preserve document structure (tables, images, etc.)

        Examples:
        >>> doc = Document.open("template.docx")
        >>> doc.render_html("editable.html", editable=True)
        >>> # ... edit in browser ...
        >>> doc.update_from_html_file("editable.html")
        >>> doc.save("updated.docx")

        """
        from .parser.html_parser import HTMLParser as HTMLDocParser
        from .models.paragraph import Paragraph
        from .models.run import Run
        
        # Parsuj HTML
        parsed_data = HTMLDocParser.parse_file(html_path)
        parsed_paragraphs = parsed_data.get('paragraphs', [])
        parsed_tables = parsed_data.get('tables', [])
        parsed_images = parsed_data.get('images', [])
        
        if not parsed_paragraphs and not parsed_tables and not parsed_images:
            logger.warning("No content found in HTML file")
            return
        
        # Pobierz body dokumentu
        body = self.body
        if not body:
            logger.error("Document body not found")
            return
        
        # If preserve_structure, update only text paragraphs
        # Otherwise replace all body content
        if preserve_structure:
            # Find all text paragraphs in document
            if hasattr(body, 'get_paragraphs'):
                paragraphs = body.get_paragraphs()
            elif hasattr(body, 'children'):
                paragraphs = [child for child in body.children if hasattr(child, '__class__') and 'Paragraph' in child.__class__.__name__]
            else:
                paragraphs = []
            
            # Update existing paragraphs
            for i, para in enumerate(paragraphs):
                if i < len(parsed_paragraphs):
                    parsed_para = parsed_paragraphs[i]
                    self._update_paragraph_from_html(para, parsed_para)
            
            # Add new paragraphs if there are more in HTML
            if len(parsed_paragraphs) > len(paragraphs):
                for i in range(len(paragraphs), len(parsed_paragraphs)):
                    parsed_para = parsed_paragraphs[i]
                    new_para = self._create_paragraph_from_html(parsed_para)
                    if hasattr(body, 'add_paragraph'):
                        body.add_paragraph(new_para)
                    elif hasattr(body, 'add_child'):
                        body.add_child(new_para)
        else:
            # Replace all body content
            # Remove all existing paragraphs
            if hasattr(body, 'children'):
                # Remove only paragraphs, keep tables and other elements
                paragraphs_to_remove = [
                    child for child in body.children
                    if hasattr(child, '__class__') and 'Paragraph' in child.__class__.__name__
                ]
                for para in paragraphs_to_remove:
                    body.children.remove(para)
            
            # Dodaj nowe paragrafy z HTML
            for parsed_para in parsed_paragraphs:
                new_para = self._create_paragraph_from_html(parsed_para)
                if hasattr(body, 'add_paragraph'):
                    body.add_paragraph(new_para)
                elif hasattr(body, 'add_child'):
                    body.add_child(new_para)
            
            # Dodaj tabele z HTML
            for parsed_table in parsed_tables:
                new_table = self._create_table_from_html(parsed_table)
                if hasattr(body, 'add_table'):
                    body.add_table(new_table)
                elif hasattr(body, 'add_child'):
                    body.add_child(new_table)
            
            # Dodaj obrazy z HTML
            for parsed_image in parsed_images:
                new_image = self._create_image_from_html(parsed_image)
                if hasattr(body, 'add_image'):
                    body.add_image(new_image)
                elif hasattr(body, 'add_child'):
                    body.add_child(new_image)
    
    def _update_paragraph_from_html(self, para: Any, parsed_para: Dict[str, Any]) -> None:
        """Updates existing paragraph based on HTML."""
        from .models.run import Run
        
        # Update numbering if paragraph is part of list
        numbering_info = parsed_para.get('numbering')
        if numbering_info:
            numbering_id = numbering_info.get('id')
            level = numbering_info.get('level', 0)
            
            # Try to use existing numbering_id or set directly
            if numbering_id:
                try:
                    para.set_list(level=level, numbering_id=numbering_id)
                except (ValueError, AttributeError):
                    # If set_list doesn't work, set numbering directly
                    if hasattr(para, 'numbering'):
                        para.numbering = {
                            'id': numbering_id,
                            'level': level,
                            'format': numbering_info.get('format', 'decimal')
                        }
        elif hasattr(para, 'numbering'):
            # Remove numbering if not present in HTML
            para.numbering = None
        
        # Clear existing runs
        if hasattr(para, 'runs'):
            para.runs.clear()
        if hasattr(para, 'children'):
            # Remove only runs, keep other elements
            runs_to_remove = [
                child for child in para.children
                if hasattr(child, '__class__') and 'Run' in child.__class__.__name__
            ]
            for run in runs_to_remove:
                para.children.remove(run)
        
        # Dodaj nowe runs z HTML
        for run_data in parsed_para.get('runs', []):
            run = Run()
            run.text = run_data.get('text', '')
            
            # Ustaw formatowanie podstawowe
            if run_data.get('bold'):
                run.bold = True
            if run_data.get('italic'):
                run.italic = True
            if run_data.get('underline'):
                run.underline = True
            
            # Ustaw kolory i czcionki
            if run_data.get('color'):
                color = run_data.get('color')
                # Ensure color is in hex format (RRGGBB) without #
                if color.startswith('#'):
                    color = color[1:]
                # Ustaw kolor
                run.color = color
            
            if run_data.get('font_size'):
                font_size = run_data.get('font_size')
                # font_size can be string (half-points) or int
                if isinstance(font_size, str):
                    try:
                        font_size = int(font_size)
                    except ValueError:
                        font_size = None
                if font_size is not None:
                    run.font_size = font_size
            
            if run_data.get('font_name'):
                font_name = run_data.get('font_name')
                run.font_name = font_name
            
            if hasattr(para, 'add_run'):
                para.add_run(run)
            elif hasattr(para, 'add_child'):
                para.add_child(run)
    
    def _create_paragraph_from_html(self, parsed_para: Dict[str, Any]) -> Any:
        """Tworzy nowy paragraf na podstawie HTML."""
        from .models.paragraph import Paragraph
        from .models.run import Run
        
        para = Paragraph()
        
        # Set numbering if paragraph is part of list
        numbering_info = parsed_para.get('numbering')
        if numbering_info:
            numbering_id = numbering_info.get('id')
            level = numbering_info.get('level', 0)
            
            # Try to use existing numbering_id or create new one
            if numbering_id:
                try:
                    para.set_list(level=level, numbering_id=numbering_id)
                except (ValueError, AttributeError):
                    # If set_list doesn't work, set numbering directly
                    para.numbering = {
                        'id': numbering_id,
                        'level': level,
                        'format': numbering_info.get('format', 'decimal')
                    }
        
        # Dodaj runs
        for run_data in parsed_para.get('runs', []):
            run = Run()
            run.text = run_data.get('text', '')
            
            # Ustaw formatowanie podstawowe
            if run_data.get('bold'):
                run.bold = True
            if run_data.get('italic'):
                run.italic = True
            if run_data.get('underline'):
                run.underline = True
            
            # Ustaw kolory i czcionki
            if run_data.get('color'):
                color = run_data.get('color')
                # Ensure color is in hex format (RRGGBB) without #
                if color.startswith('#'):
                    color = color[1:]
                # Ustaw kolor
                run.color = color
            
            if run_data.get('font_size'):
                font_size = run_data.get('font_size')
                # font_size can be string (half-points) or int
                if isinstance(font_size, str):
                    try:
                        font_size = int(font_size)
                    except ValueError:
                        font_size = None
                if font_size is not None:
                    run.font_size = font_size
            
            if run_data.get('font_name'):
                font_name = run_data.get('font_name')
                run.font_name = font_name
            
            para.add_run(run)
        
        return para
    
    def _create_table_from_html(self, parsed_table: Dict[str, Any]) -> Any:
        """Creates new table based on HTML."""
        from .models.table import Table, TableRow, TableCell
        
        table = Table()
        
        # Dodaj wiersze
        for row_data in parsed_table.get('rows', []):
            row = TableRow()
            
            # Ustaw czy to header row
            if row_data.get('is_header'):
                row.set_header_row(True)
            
            # Add cells
            for cell_data in row_data.get('cells', []):
                cell = TableCell()
                
                # Add paragraphs to cell
                for para_data in cell_data.get('paragraphs', []):
                    para = self._create_paragraph_from_html(para_data)
                    cell.add_paragraph(para)
                
                row.add_cell(cell)
            
            table.add_row(row)
        
        return table
    
    def _create_image_from_html(self, parsed_image: Dict[str, Any]) -> Any:
        """Tworzy nowy obraz na podstawie HTML."""
        from .models.image import Image
        
        image = Image()
        
        # Set image properties
        rel_id = parsed_image.get('rel_id', '')
        if rel_id:
            image.set_rel_id(rel_id)
        
        src = parsed_image.get('src', '')
        if src:
            # If src looks like path, save as part_path
            if '/' in src or '\\' in src or src.startswith('image_'):
                image.set_part_path(src)
        
        width = parsed_image.get('width')
        height = parsed_image.get('height')
        if width and height:
            # Convert px to EMU if needed (1px ≈ 9525 EMU)
            if width < 1000:  # Prawdopodobnie px
                width = int(width * 9525)
            if height < 1000:  # Prawdopodobnie px
                height = int(height * 9525)
            image.set_size(width, height)
        
        alt_text = parsed_image.get('alt', '')
        if alt_text:
            image.alt_text = alt_text
        
        return image

