"""

Simple high-level API for DocQuill.

Main entry point for users - simple and intuitive interface.

Usage example:
>>> from docquill import Document
>>> 
>>> # Open document
>>> doc = Document('file.docx')
>>> 
>>> # Get model
>>> model = doc.to_model()
>>> 
>>> # Process through pipeline
>>> layout = doc.pipeline()
>>> 
>>> # Render to PDF
>>> doc.to_pdf('output.pdf', backend='rust')
>>> 
>>> # Render to HTML
>>> doc.to_html('output.html')
>>> 
>>> # Normalize document
>>> doc_normalized = doc.normalize('normalized.docx')

"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Import main classes
from .document_api import Document as DocumentAPI
from .engine.placeholder_engine import PlaceholderEngine, PlaceholderInfo
from .merger import DocumentMerger, MergeOptions

# Re-export dla wygody
__all__ = [
    "Document",
    "open_document",
    "create_document",
    "fill_template",
    "merge_documents",
    "render_to_html",
    "render_to_pdf",
]


class Document:
    """

    Simple high-level API for working with DOCX documents.

    Main class for users - simple and intuitive interface.

    Examples:
    >>> from docquill import Document
    >>> 
    >>> # Open document
    >>> doc = Document('file.docx')
    >>> 
    >>> # Get model
    >>> model = doc.to_model()
    >>> 
    >>> # Process through pipeline
    >>> layout = doc.pipeline()
    >>> 
    >>> # Render to PDF
    >>> doc.to_pdf('output.pdf', backend='rust')
    >>> 
    >>> # Render to HTML
    >>> doc.to_html('output.html')
    >>> 
    >>> # Normalize document
    >>> doc_normalized = doc.normalize('normalized.docx')

    """
    
    def __init__(
        self,
        file_path: Optional[Union[str, Path]] = None,
        document_model: Optional[Any] = None
    ):
        """

        Creates a new document or opens from file.

        Args:
        file_path: Path to DOCX file (optional)
        document_model: Optional existing document model (optional)

        Examples:
        >>> doc = Document('file.docx')
        >>> doc = Document()  # Empty document

        """
        self._file_path = Path(file_path) if file_path else None
        self._package_reader = None
        self._xml_parser = None
        self._body = None
        self._sections = None
        self._model = None
        self._pipeline = None
        self._unified_layout = None
        
        if file_path:
            self._load_document()
        elif document_model:
            self._api = DocumentAPI(document_model)
        else:
            self._api = DocumentAPI()
    
    def _load_document(self):
        """Loads document from file."""
        if not self._file_path or not self._file_path.exists():
            raise FileNotFoundError(f"Dokument nie znaleziony: {self._file_path}")
        
        from .parser.package_reader import PackageReader
        from .parser.xml_parser import XMLParser
        
        self._package_reader = PackageReader(self._file_path)
        self._xml_parser = XMLParser(self._package_reader)
        self._body = self._xml_parser.parse_body()
        self._sections = self._xml_parser.parse_sections()
        
        # Create adapter for DocumentAPI
        class DocumentAdapter:
            def __init__(self, body_obj, parser, sections=None):
                self.elements = body_obj.children if hasattr(body_obj, 'children') else []
                self.parser = parser
                self._sections = sections or []
        
        self._model = DocumentAdapter(self._body, self._xml_parser, self._sections)
        # Add _file_path to model so DocumentAPI.save() can use it as template
        if hasattr(self._model, '__dict__'):
            self._model._file_path = self._file_path
        self._api = DocumentAPI(self._model)
    
    @classmethod
    def open(cls, file_path: Union[str, Path]) -> "Document":
        """

        Opens document from DOCX file (alternative method).

        Args:
        file_path: Path to DOCX file

        Returns:
        Document: Opened document

        Examples:
        >>> doc = Document.open("template.docx")

        """
        return cls(file_path)
    
    @classmethod
    def create(cls) -> "Document":
        """

        Creates a new empty document.

        Returns:
        Document: New empty document

        Examples:
        >>> doc = Document.create()
        >>> doc.add_paragraph("Title", style="Heading1")

        """
        doc = cls()
        # Create empty model for new documents
        from .models.body import Body
        
        class EmptyModel:
            def __init__(self):
                self.elements = []
                self.parser = None
                self._sections = []
                self.body = Body()
        
        doc._model = EmptyModel()
        doc._body = doc._model.body
        return doc
    
    def to_model(self) -> Any:
        """

        Returns document model (body, headers, footers).

        Returns:
        Document model from parser

        Examples:
        >>> model = doc.to_model()
        >>> print(model.elements)  # List of elements

        """
        if self._model is None:
            raise ValueError("Dokument nie został załadowany. Użyj Document('plik.docx')")
        return self._model
    
    def pipeline(
        self,
        page_size: Optional[Tuple[float, float]] = None,
        margins: Optional[Tuple[float, float, float, float]] = None,
        apply_headers_footers: bool = True,
        validate: bool = False,
        target: str = "pdf"
    ):
        """

        Processes document through layout engine and assembler.

        Args:
        page_size: Page size (width, height) in points. Default A4 (595, 842)
        margins: Margins (top, bottom, left, right) in points. Default (72, 72, 72, 72)
        apply_headers_footers: Whether to apply headers and footers
        validate: Whether to perform validation
        target: Rendering target ("pdf", "html", "docx")

        Returns:
        UnifiedLayout: Processed layout ready for rendering

        Examples:
        >>> layout = doc.pipeline()
        >>> layout = doc.pipeline(page_size=(842, 595), margins=(50, 50, 50, 50))

        """
        from .engine.layout_pipeline import LayoutPipeline
        from .engine.geometry import Size, Margins, twips_to_points
        from .engine.page_engine import PageConfig
        from .parser.image_preconverter import preconvert_images_from_model
        from .media import MediaConverter
        
        if self._model is None:
            raise ValueError("Dokument nie został załadowany. Użyj Document('plik.docx')")
        
        # Konfiguracja strony
        if page_size is None:
            page_size = (595.0, 842.0)  # A4
        
        if margins is None:
            # Get margins from DOCX or use defaults
            page_margins = Margins(top=72, bottom=72, left=72, right=72)
            if self._sections and len(self._sections) > 0:
                section = self._sections[0]
                if 'margins' in section:
                    docx_margins = section['margins']
                    def get_margin_twips(key, default=1440):
                        val = docx_margins.get(key, default)
                        if isinstance(val, str):
                            try:
                                return int(val)
                            except (ValueError, TypeError):
                                return default
                        return int(val) if val is not None else default
                    
                    page_margins = Margins(
                        top=twips_to_points(get_margin_twips('top', 1440)),
                        bottom=twips_to_points(get_margin_twips('bottom', 1440)),
                        left=twips_to_points(get_margin_twips('left', 1440)),
                        right=twips_to_points(get_margin_twips('right', 1440))
                    )
        else:
            page_margins = Margins(top=margins[0], bottom=margins[1], left=margins[2], right=margins[3])
        
        page_config = PageConfig(
            page_size=Size(page_size[0], page_size[1]),
            base_margins=page_margins
        )
        
        # Create pipeline
        self._pipeline = LayoutPipeline(page_config, target=target)
        
        # Image preconversion
        if self._package_reader:
            self._xml_parser.image_cache = self._pipeline.image_cache
            media_converter = MediaConverter()
            preconvert_images_from_model(self._body, self._package_reader, self._pipeline.image_cache, media_converter)
            
            # Image preconversion from headers and footers
            if hasattr(self._xml_parser, 'parse_header'):
                header_body = self._xml_parser.parse_header()
                if header_body:
                    preconvert_images_from_model(header_body, self._package_reader, self._pipeline.image_cache, media_converter)
            
            if hasattr(self._xml_parser, 'parse_footer'):
                footer_body = self._xml_parser.parse_footer()
                if footer_body:
                    preconvert_images_from_model(footer_body, self._package_reader, self._pipeline.image_cache, media_converter)
            
            # Waiting for image conversion
            self._pipeline.image_cache.wait_for_all(timeout=60.0)
        
        # Przetwarzanie
        self._pipeline.layout_assembler.package_reader = self._package_reader
        
        # Prepare footnote_renderer if available
        if self._package_reader:
            try:
                from .parser.notes_parser import NotesParser
                from .renderers.footnote_renderer import FootnoteRenderer
                notes_parser = NotesParser(self._package_reader)
                footnotes = notes_parser.get_footnotes() or {}
                endnotes = notes_parser.get_endnotes() or {}
                self._pipeline.layout_assembler.footnote_renderer = FootnoteRenderer(footnotes, endnotes)
            except Exception:
                pass
        
        self._unified_layout = self._pipeline.process(
            self._model,
            apply_headers_footers=apply_headers_footers,
            validate=validate
        )
        
        return self._unified_layout
    
    def to_pdf(
        self,
        output_path: Union[str, Path],
        *,
        backend: str = "rust",
        page_size: Optional[Tuple[float, float]] = None,
        margins: Optional[Tuple[float, float, float, float]] = None,
        parallelism: int = 1,
        watermark_opacity: Optional[float] = None,
        apply_headers_footers: bool = True,
        validate: bool = False
    ) -> Path:
        """

        Renders document to PDF.

        Args:
        output_path: Path to output PDF file
        backend: Rendering engine ("rust" or "reportlab")
        page_size: Page size (width, height) in points
        margins: Margins (top, bottom, left, right) in points
        parallelism: Number of processes (1 = sequential)
        watermark_opacity: Watermark opacity (0.0-1.0)
        apply_headers_footers: Whether to apply headers and footers
        validate: Whether to perform validation

        Returns:
        Path: Path to generated PDF file

        Examples:
        >>> doc.to_pdf('output.pdf', backend='rust')
        >>> doc.to_pdf('output.pdf', backend='rust', page_size=(842, 595), margins=(50, 50, 50, 50))

        """
        from .engine.pdf.pdf_compiler import PDFCompiler
        
        # If layout has not been processed yet, do it now
        if self._unified_layout is None:
            self.pipeline(
                page_size=page_size,
                margins=margins,
                apply_headers_footers=apply_headers_footers,
                validate=validate,
                target="pdf"
            )
        
        # Przygotuj footnote_renderer
        footnote_renderer = None
        if self._pipeline and hasattr(self._pipeline.layout_assembler, 'footnote_renderer'):
            footnote_renderer = self._pipeline.layout_assembler.footnote_renderer
        
        # Renderowanie
        compiler = PDFCompiler(
            output_path=str(output_path),
            page_size=page_size or (595, 842),
            package_reader=self._package_reader,
            footnote_renderer=footnote_renderer,
            image_cache=self._pipeline.image_cache if self._pipeline else None,
            use_rust=(backend == "rust"),
            parallelism=parallelism,
            watermark_opacity=watermark_opacity
        )
        
        result_path = compiler.compile(self._unified_layout)
        return result_path
    
    @classmethod
    def from_json(
        cls,
        json_path: Union[str, Path],
        output_docx: Optional[Union[str, Path]] = None,
        source_docx: Optional[Union[str, Path]] = None
    ) -> "Document":
        """

        Creates Document from JSON (reverse of to_json process).

        Uses approach similar to normalize_docx:
        1. JSON → UnifiedLayout (deserialization)
        2. UnifiedLayout → Document Model (simplified conversion)
        3. Document Model → DOCX (via DOCXExporter)

        Args:
        json_path: Path to JSON file
        output_docx: Optional path to save DOCX (if None, creates with suffix)
        source_docx: Optional path to original DOCX (for copying media)

        Returns:
        Document: New document from JSON

        Examples:
        >>> doc = Document.from_json('document.json', 'output.docx')
        >>> doc = Document.from_json('document.json')  # Creates document_from_json.docx

        """
        from .importers.pipeline_json_importer import PipelineJSONImporter
        from .export.docx_exporter import DOCXExporter
        
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"Plik JSON nie istnieje: {json_path}")
        
        # Importuj JSON
        importer = PipelineJSONImporter(json_path=json_path, source_docx_path=source_docx)
        
        # Konwertuj do Document Model
        model = importer.to_document_model()
        
        # Add importer to model so DOCXExporter can access media_list
        if hasattr(model, '__dict__'):
            model._importer = importer
            # Also add source_docx if provided (for copying media)
            if source_docx:
                model._source_docx = Path(source_docx)
        
        # Zapisz do DOCX
        if output_docx is None:
            output_docx = json_path.with_name(f"{json_path.stem}_from_json.docx")
        
        # Pass source_docx_path to exporter to use as template
        exporter = DOCXExporter(model, source_docx_path=source_docx)
        success = exporter.export(output_docx)
        
        if not success:
            raise RuntimeError(f"Nie udało się zapisać DOCX: {output_docx}")
        
        # Return Document with model (don't open DOCX again as it loses content)
        # Create Document with model directly
        doc = cls.__new__(cls)  # Create instance without calling __init__
        doc._file_path = Path(output_docx)
        doc._model = model
        doc._body = model.body
        doc._sections = getattr(model, '_sections', [])
        doc._package_reader = None  # We don't have package_reader for documents from JSON
        doc._xml_parser = None
        doc._pipeline = None
        doc._unified_layout = None
        doc._api = None
        
        # IMPORTANT: Preserve information from JSON (sections, headers, footers) in document,
        # so they are available during JSON export
        if hasattr(importer, 'json_data'):
            doc._json_data = importer.json_data
            doc._json_sections = importer.json_data.get('sections', [])
            doc._json_headers = importer.json_data.get('headers', {})
            doc._json_footers = importer.json_data.get('footers', {})
        
        # Ustaw _api z modelem
        from .api import DocumentAPI
        doc._api = DocumentAPI(model)
        
        return doc
    
    def to_json(
        self,
        output_path: Optional[Union[str, Path]] = None,
        *,
        optimized: bool = True,
        include_raw_content: bool = False,
        page_size: Optional[Tuple[float, float]] = None,
        margins: Optional[Tuple[float, float, float, float]] = None,
    ) -> Dict[str, Any]:
        """

        Exports document to JSON (from pipeline).

        Args:
        output_path: Path to output file (optional, if None returns dict)
        optimized: Whether to use optimized version (style deduplication, compact structure)
        include_raw_content: Whether to include raw content data (increases size)
        page_size: Page size (width, height) in points
        margins: Margins (top, bottom, left, right) in points

        Returns:
        Dictionary with JSON data or None if saved to file

        Examples:
        >>> doc = Document('file.docx')
        >>> doc.to_json('output.json')
        >>> json_data = doc.to_json()  # Returns dict

        """
        # Ensure pipeline has been run
        if self._unified_layout is None:
            # Call pipeline() method directly (not property)
            from .engine.layout_pipeline import LayoutPipeline
            from .engine.geometry import Size, Margins
            from .engine.page_engine import PageConfig
            from .parser.image_preconverter import preconvert_images_from_model
            from .media import MediaConverter
            
            # Konfiguracja strony
            if page_size is None:
                page_size = (595.0, 842.0)  # A4
            
            if margins is None:
                page_margins = Margins(top=72, bottom=72, left=72, right=72)
            else:
                page_margins = Margins(top=margins[0], bottom=margins[1], left=margins[2], right=margins[3])
            
            page_config = PageConfig(
                page_size=Size(page_size[0], page_size[1]),
                base_margins=page_margins
            )
            
            # Create pipeline
            self._pipeline = LayoutPipeline(page_config, target="pdf")
            
            # Image preconversion
            if self._package_reader:
                self._xml_parser.image_cache = self._pipeline.image_cache
                media_converter = MediaConverter()
                preconvert_images_from_model(self._body, self._package_reader, self._pipeline.image_cache, media_converter)
                
                if hasattr(self._xml_parser, 'parse_header'):
                    header_body = self._xml_parser.parse_header()
                    if header_body:
                        preconvert_images_from_model(header_body, self._package_reader, self._pipeline.image_cache, media_converter)
                
                if hasattr(self._xml_parser, 'parse_footer'):
                    footer_body = self._xml_parser.parse_footer()
                    if footer_body:
                        preconvert_images_from_model(footer_body, self._package_reader, self._pipeline.image_cache, media_converter)
                
                self._pipeline.image_cache.wait_for_all(timeout=60.0)
            
            # Przetwarzanie
            self._pipeline.layout_assembler.package_reader = self._package_reader
            
            # Prepare footnote_renderer if available
            if self._package_reader:
                try:
                    from .parser.notes_parser import NotesParser
                    from .renderers.footnote_renderer import FootnoteRenderer
                    notes_parser = NotesParser(self._package_reader)
                    footnotes = notes_parser.get_footnotes() or {}
                    endnotes = notes_parser.get_endnotes() or {}
                    self._pipeline.layout_assembler.footnote_renderer = FootnoteRenderer(footnotes, endnotes)
                except Exception:
                    pass
            
            # For documents from JSON, ensure model has body with children
            # LayoutPipeline oczekuje modelu z atrybutem 'elements'
            if not hasattr(self._model, 'elements'):
                # Create adapter if model has body instead of elements
                class DocumentAdapter:
                    def __init__(self, model):
                        # Pobierz elementy z body.children
                        if hasattr(model, 'body') and hasattr(model.body, 'children'):
                            self.elements = model.body.children if isinstance(model.body.children, (list, tuple)) else list(model.body.children) if model.body.children else []
                        elif hasattr(model, 'body'):
                            # If body has no children, try paragraphs + tables + images
                            elements = []
                            if hasattr(model.body, 'paragraphs'):
                                elements.extend(model.body.paragraphs if isinstance(model.body.paragraphs, (list, tuple)) else list(model.body.paragraphs) if model.body.paragraphs else [])
                            if hasattr(model.body, 'tables'):
                                elements.extend(model.body.tables if isinstance(model.body.tables, (list, tuple)) else list(model.body.tables) if model.body.tables else [])
                            if hasattr(model.body, 'images'):
                                elements.extend(model.body.images if isinstance(model.body.images, (list, tuple)) else list(model.body.images) if model.body.images else [])
                            self.elements = elements
                        else:
                            self.elements = []
                        # Parser may be in model or importer
                        self.parser = getattr(model, '_xml_parser', None) or (getattr(model, '_importer', None) and getattr(model._importer, '_xml_parser', None))
                        # Kopiuj sekcje z modelu
                        self._sections = getattr(model, '_sections', None) or getattr(model, '_json_sections', None) or []
                
                # Use adapter if model has no elements
                model_to_process = DocumentAdapter(self._model)
            else:
                model_to_process = self._model
            
            # Dla eksportu JSON, nie stosuj headers/footers - eksportuj z LayoutStructure
            # to preserve body/headers/footers separation (footer tables won't be confused with body tables)
            self._unified_layout = self._pipeline.process(
                model_to_process,
                apply_headers_footers=False,  # Nie stosuj headers/footers dla JSON
                validate=False
            )
        
        if self._unified_layout is None:
            raise ValueError("Nie udało się przetworzyć dokumentu przez pipeline")
        
        if optimized:
            from .export.pipeline_json_exporter import OptimizedPipelineJSONExporter
            exporter = OptimizedPipelineJSONExporter(
                include_raw_content=include_raw_content,
                package_reader=self._package_reader,
                xml_parser=self._xml_parser,
                document=self
            )
            # Export from LayoutStructure instead of UnifiedLayout to preserve body/headers/footers separation
            layout_structure = self._pipeline.layout_structure
            if layout_structure:
                result = exporter.export_from_layout_structure(
                    layout_structure,
                    self._unified_layout,  # We use UnifiedLayout only for page geometry
                    Path(output_path) if output_path else None
                )
            else:
                # Fallback to old method if layout_structure is not available
                result = exporter.export(
                    self._unified_layout,
                    Path(output_path) if output_path else None
                )
        else:
            # Stara wersja (bez optymalizacji)
            from .export.json_exporter_enhanced import JSONExporterEnhanced
            # TODO: Implementacja dla non-optimized
            raise NotImplementedError("Non-optimized export not yet implemented")
        
        # Always return result (even if saved to file)
        return result
    
    def to_html(
        self,
        output_path: Union[str, Path],
        *,
        editable: bool = False,
        page_size: Optional[Tuple[float, float]] = None,
        margins: Optional[Tuple[float, float, float, float]] = None,
        apply_headers_footers: bool = False,
        validate: bool = False,
        embed_images_as_data_uri: bool = False,
        page_max_width: float = 960.0
    ) -> Path:
        """

        Renders document to HTML.

        Args:
        output_path: Path to output HTML file
        editable: Whether HTML should be editable (contenteditable)
        page_size: Page size (width, height) in points
        margins: Margins (top, bottom, left, right) in points
        apply_headers_footers: Whether to apply headers and footers
        validate: Whether to perform validation
        embed_images_as_data_uri: Whether to embed images as data URI
        page_max_width: Maximum page width in CSS (px)

        Returns:
        Path: Path to generated HTML file

        Examples:
        >>> doc.to_html('output.html')
        >>> doc.to_html('output.html', editable=True)

        """
        from .engine.html.html_compiler import HTMLCompiler, HTMLCompilerConfig
        
        # If layout has not been processed yet, do it now
        if self._unified_layout is None:
            self.pipeline(
                page_size=page_size,
                margins=margins,
                apply_headers_footers=apply_headers_footers,
                validate=validate,
                target="html"
            )
        
        # Konfiguracja HTML
        config = HTMLCompilerConfig(
            output_path=Path(output_path),
            embed_images_as_data_uri=embed_images_as_data_uri,
            page_max_width=page_max_width
        )
        
        # Renderowanie
        compiler = HTMLCompiler(config)
        result_path = compiler.compile(self._unified_layout, output_path=output_path)
        return result_path
    
    def normalize(
        self,
        output_path: Optional[Union[str, Path]] = None
    ) -> "Document":
        """

        Normalizes document (cleans styles, merges runs, fixes formatting).

        Args:
        output_path: Path to save normalized document. 
        If None, creates file with "_normalized" suffix

        Returns:
        Document: New normalized document

        Examples:
        >>> doc_normalized = doc.normalize('normalized.docx')
        >>> doc_normalized = doc.normalize()  # Creates file with "_normalized" suffix

        """
        try:
            from .normalize import normalize_docx
        except ImportError:
            raise ImportError("Funkcja normalize_docx nie jest dostępna")
        
        if self._file_path is None:
            raise ValueError("Normalizacja wymaga załadowanego dokumentu z pliku")
        
        normalized_path = normalize_docx(
            self._file_path,
            output_path=output_path
        )
        
        # Return new Document with normalized file
        return Document(normalized_path)
    
    # Delegation to DocumentAPI for remaining methods
    @property
    def body(self):
        """Zwraca body dokumentu."""
        return self._api.body
    
    def add_paragraph(
        self,
        text: str = "",
        style: Optional[str] = None
    ):
        """Dodaje paragraf do dokumentu."""
        return self._api.add_paragraph(text, style)
    
    def add_run(
        self,
        paragraph,
        text: str,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        font_color: Optional[str] = None,
        font_size: Optional[int] = None,
        font_name: Optional[str] = None
    ):
        """Dodaje run do paragrafu z formatowaniem."""
        return self._api.add_run(
            paragraph, text, bold, italic, underline,
            font_color, font_size, font_name
        )
    
    def replace_text(
        self,
        old_text: str,
        new_text: str,
        scope: str = "body",
        case_sensitive: bool = False
    ) -> int:
        """Replaces text in document."""
        return self._api.replace_text(old_text, new_text, scope, case_sensitive)
    
    def fill_placeholders(
        self,
        data: Dict[str, Any],
        multi_pass: bool = False,
        max_passes: int = 5
    ) -> int:
        """Fills placeholders in document (Jinja-like)."""
        return self._api.fill_placeholders(data, multi_pass, max_passes)
    
    def process_conditional_block(self, block_name: str, show: bool) -> bool:
        """Przetwarza blok warunkowy (START_nazwa / END_nazwa)."""
        return self._api.process_conditional_block(block_name, show)
    
    def create_numbered_list(self):
        """Creates numbered list."""
        return self._api.create_numbered_list()
    
    def create_bullet_list(self):
        """Creates bullet list."""
        return self._api.create_bullet_list()
    
    def merge(
        self,
        other: Union["Document", str, Path],
        page_break: bool = False
    ) -> None:
        """Merges document with another document."""
        self._api.merge(other, page_break)
    
    def append(
        self,
        other: Union["Document", str, Path],
        page_break: bool = False
    ) -> None:
        """Dodaje dokument na koniec."""
        self._api.append(other, page_break)
    
    def prepend(
        self,
        other: Union["Document", str, Path],
        page_break: bool = False
    ) -> None:
        """Prepends document at the beginning."""
        self._api.prepend(other, page_break)
    
    def merge_selective(
        self,
        sources: Dict[str, Union["Document", str, Path]],
        page_break: bool = False
    ) -> None:
        """Advanced selective merging of elements from different documents."""
        self._api.merge_selective(sources, page_break)
    
    def merge_headers(
        self,
        source: Union["Document", str, Path],
        header_types: Optional[List[str]] = None
    ) -> None:
        """Merges headers from source document."""
        self._api.merge_headers(source, header_types)
    
    def merge_footers(
        self,
        source: Union["Document", str, Path],
        footer_types: Optional[List[str]] = None
    ) -> None:
        """Merges footers from source document."""
        self._api.merge_footers(source, footer_types)
    
    def apply_layout(
        self,
        template: Union[str, Path, "Document"],
        header_types: Optional[List[str]] = None,
        footer_types: Optional[List[str]] = None
    ) -> None:
        """Aplikuje layout (headers/footers) z template."""
        return self._api.apply_layout(template, header_types, footer_types)
    
    def save(self, file_path: Union[str, Path]) -> None:
        """Zapisuje dokument do pliku DOCX."""
        self._api.save(file_path)
    
    def render_html(
        self,
        output_path: Union[str, Path],
        editable: bool = False
    ) -> None:
        """Renders document to HTML (legacy - use to_html())."""
        return self.to_html(output_path, editable=editable)
    
    def render_pdf(
        self,
        output_path: Union[str, Path],
        engine: str = "reportlab"
    ) -> None:
        """Renders document to PDF (legacy - use to_pdf())."""
        backend = "rust" if engine == "rust" else "reportlab"
        return self.to_pdf(output_path, backend=backend)
    
    def extract_placeholders(self) -> List[PlaceholderInfo]:
        """Extracts all placeholders from document."""
        return self._api.extract_placeholders()
    
    def update_from_html_file(
        self,
        html_path: Union[str, Path],
        preserve_structure: bool = True
    ) -> None:
        """Aktualizuje dokument na podstawie edytowanego pliku HTML."""
        return self._api.update_from_html_file(html_path, preserve_structure)
    
    # ======================================================================
    # Watermarks
    # ======================================================================
    
    def add_watermark(
        self,
        text: str,
        angle: float = 45.0,
        opacity: float = 0.5,
        color: str = "#CCCCCC",
        font_size: float = 72.0,
        font_name: str = "Arial"
    ):
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
        >>> doc.add_watermark("CONFIDENTIAL", angle=45, opacity=0.3)
        >>> doc.add_watermark("DRAFT", color="#FF0000", opacity=0.5)

        """
        return self._api.add_watermark(text, angle, opacity, color, font_size, font_name)
    
    def get_watermarks(self) -> List[Any]:
        """

        Returns list of watermarks in document.

        Returns:
        List of watermarks

        """
        return self._api.get_watermarks()
    
    @property
    def watermarks(self) -> List[Any]:
        """Returns list of watermarks (property)."""
        return self._api.watermarks
    
    # ======================================================================
    # Zaawansowane merge operacje
    # ======================================================================
    
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

        Examples:
        >>> doc.merge_sections("template.docx", copy_properties=True)

        """
        return self._api.merge_sections(source, copy_properties)
    
    def merge_styles(
        self,
        source: Union["Document", str, Path]
    ) -> None:
        """

        Merges styles from source document.

        Args:
        source: Source document

        Examples:
        >>> doc.merge_styles("style_template.docx")

        """
        return self._api.merge_styles(source)
    
    # ======================================================================
    # Metadata
    # ======================================================================
    
    def get_metadata(self) -> Dict[str, Any]:
        """

        Gets document metadata.

        Returns:
        Dictionary with metadata (core_properties, app_properties, custom_properties)

        Examples:
        >>> metadata = doc.get_metadata()
        >>> print(metadata['core_properties']['title'])

        """
        if self._package_reader is None:
            raise ValueError("Dokument nie został załadowany. Użyj Document('plik.docx')")
        return self._package_reader.get_metadata()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Zwraca metadane dokumentu (property)."""
        return self.get_metadata()
    
    def get_title(self) -> Optional[str]:
        """Returns document title."""
        metadata = self.get_metadata()
        return metadata.get('core_properties', {}).get('title')
    
    def get_author(self) -> Optional[str]:
        """Zwraca autora dokumentu."""
        metadata = self.get_metadata()
        return metadata.get('core_properties', {}).get('author')
    
    def get_subject(self) -> Optional[str]:
        """Zwraca temat dokumentu."""
        metadata = self.get_metadata()
        return metadata.get('core_properties', {}).get('subject')
    
    def get_keywords(self) -> Optional[str]:
        """Returns document keywords."""
        metadata = self.get_metadata()
        return metadata.get('core_properties', {}).get('keywords')
    
    def get_description(self) -> Optional[str]:
        """Zwraca opis dokumentu."""
        metadata = self.get_metadata()
        return metadata.get('core_properties', {}).get('description')
    
    # ======================================================================
    # Walidacja
    # ======================================================================
    
    def validate_layout(
        self,
        page_size: Optional[Tuple[float, float]] = None,
        margins: Optional[Tuple[float, float, float, float]] = None,
        apply_headers_footers: bool = True
    ) -> Tuple[Any, bool, List[str], List[str]]:
        """

        Validates document layout and returns results.

        Args:
        page_size: Page size (width, height) in points
        margins: Margins (top, bottom, left, right) in points
        apply_headers_footers: Whether to apply headers and footers

        Returns:
        Tuple (UnifiedLayout, is_valid, errors, warnings)

        Examples:
        >>> layout, is_valid, errors, warnings = doc.validate_layout()
        >>> if not is_valid:
        ...     print("Errors:", errors)
        ...     print("Warnings:", warnings)

        """
        from .engine.layout_pipeline import LayoutPipeline
        from .engine.geometry import Size, Margins, twips_to_points
        from .engine.page_engine import PageConfig
        
        if self._model is None:
            raise ValueError("Dokument nie został załadowany. Użyj Document('plik.docx')")
        
        # Konfiguracja strony (podobnie jak w pipeline())
        if page_size is None:
            page_size = (595.0, 842.0)  # A4
        
        if margins is None:
            page_margins = Margins(top=72, bottom=72, left=72, right=72)
            if self._sections and len(self._sections) > 0:
                section = self._sections[0]
                if 'margins' in section:
                    docx_margins = section['margins']
                    def get_margin_twips(key, default=1440):
                        val = docx_margins.get(key, default)
                        if isinstance(val, str):
                            try:
                                return int(val)
                            except (ValueError, TypeError):
                                return default
                        return int(val) if val is not None else default
                    
                    page_margins = Margins(
                        top=twips_to_points(get_margin_twips('top', 1440)),
                        bottom=twips_to_points(get_margin_twips('bottom', 1440)),
                        left=twips_to_points(get_margin_twips('left', 1440)),
                        right=twips_to_points(get_margin_twips('right', 1440))
                    )
        else:
            page_margins = Margins(top=margins[0], bottom=margins[1], left=margins[2], right=margins[3])
        
        page_config = PageConfig(
            page_size=Size(page_size[0], page_size[1]),
            base_margins=page_margins
        )
        
        # Create pipeline and use process_with_validation
        pipeline = LayoutPipeline(page_config)
        pipeline.layout_assembler.package_reader = self._package_reader
        
        unified_layout, is_valid, errors, warnings = pipeline.process_with_validation(
            self._model,
            apply_headers_footers=apply_headers_footers
        )
        
        return unified_layout, is_valid, errors, warnings
    
    # ======================================================================
    # Properties for accessing internal objects
    # ======================================================================
    
    @property
    def layout_pipeline(self) -> Optional[Any]:
        """

        Returns LayoutPipeline object (if created).

        Returns:
        LayoutPipeline or None

        """
        return self._pipeline
    
    @property
    def package_reader(self) -> Optional[Any]:
        """
        Zwraca obiekt PackageReader.
        
        Returns:
            PackageReader lub None
        """
        return self._package_reader
    
    @property
    def xml_parser(self) -> Optional[Any]:
        """
        Zwraca obiekt XMLParser.
        
        Returns:
            XMLParser lub None
        """
        return self._xml_parser
    
    @property
    def layout(self) -> Optional[Any]:
        """

        Returns UnifiedLayout (if processed).

        Returns:
        UnifiedLayout or None

        """
        return self._unified_layout
    
    # ======================================================================
    # Informacje o dokumencie
    # ======================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """

        Returns document statistics.

        Returns:
        Dictionary with statistics (paragraphs, tables, images, etc.)

        Examples:
        >>> stats = doc.get_stats()
        >>> print(f"Paragraphs: {stats['paragraphs']}")
        >>> print(f"Tables: {stats['tables']}")

        """
        if self._body is None:
            return {
                'paragraphs': 0,
                'tables': 0,
                'images': 0,
                'total_elements': 0
            }
        
        stats = {
            'paragraphs': 0,
            'tables': 0,
            'images': 0,
            'total_elements': 0
        }
        
        # Licz elementy w body
        if hasattr(self._body, 'children'):
            for child in self._body.children:
                stats['total_elements'] += 1
                child_type = type(child).__name__
                if child_type == 'Paragraph':
                    stats['paragraphs'] += 1
                elif child_type == 'Table':
                    stats['tables'] += 1
                elif hasattr(child, 'get_src') or hasattr(child, 'image_path'):
                    stats['images'] += 1
        
        # Add statistics from metadata if available
        try:
            metadata = self.get_metadata()
            app_props = metadata.get('app_properties', {})
            if app_props:
                stats['pages'] = app_props.get('pages', 0)
                stats['words'] = app_props.get('words', 0)
                stats['characters'] = app_props.get('characters', 0)
        except Exception:
            pass
        
        return stats
    
    def get_sections(self) -> List[Dict[str, Any]]:
        """

        Returns list of document sections.

        Returns:
        List of sections with properties (margins, page_size, etc.)

        Examples:
        >>> sections = doc.get_sections()
        >>> print(f"Number of sections: {len(sections)}")

        """
        if self._sections is None:
            return []
        return self._sections.copy() if isinstance(self._sections, list) else [self._sections]
    
    def get_styles(self) -> Dict[str, Any]:
        """

        Returns information about styles in document.

        Returns:
        Dictionary with styles

        Examples:
        >>> styles = doc.get_styles()
        >>> print(f"Available styles: {list(styles.keys())}")

        """
        if self._xml_parser is None:
            return {}
        
        try:
            if hasattr(self._xml_parser, 'style_parser'):
                style_parser = self._xml_parser.style_parser
                if hasattr(style_parser, 'styles'):
                    return style_parser.styles.copy() if isinstance(style_parser.styles, dict) else {}
        except Exception:
            pass
        
        return {}
    
    def get_numbering(self) -> Dict[str, Any]:
        """

        Returns information about numbering in document.

        Returns:
        Dictionary with numbering information

        Examples:
        >>> numbering = doc.get_numbering()
        >>> print(f"Number of numbering definitions: {len(numbering.get('definitions', []))}")

        """
        if self._xml_parser is None:
            return {}
        
        try:
            if hasattr(self._xml_parser, 'numbering_parser'):
                numbering_parser = self._xml_parser.numbering_parser
                if hasattr(numbering_parser, 'abstract_numberings'):
                    return {
                        'abstract_numberings': numbering_parser.abstract_numberings.copy() if hasattr(numbering_parser.abstract_numberings, 'copy') else numbering_parser.abstract_numberings,
                        'numbering_instances': numbering_parser.numbering_instances.copy() if hasattr(numbering_parser.numbering_instances, 'copy') else numbering_parser.numbering_instances
                    }
        except Exception:
            pass
        
        return {}


# Convenience functions for even simpler usage
def open_document(file_path: Union[str, Path]) -> Document:
    """Otwiera dokument z pliku DOCX (convenience function)."""
    return Document.open(file_path)


def create_document() -> Document:
    """Tworzy nowy pusty dokument (convenience function)."""
    return Document.create()


def fill_template(
    template_path: Union[str, Path],
    data: Dict[str, Any],
    output_path: Union[str, Path],
    multi_pass: bool = False
) -> Document:
    """Fills template with placeholders and returns document (convenience function)."""
    doc = Document.open(template_path)
    doc.fill_placeholders(data, multi_pass=multi_pass)
    if output_path:
        doc.save(output_path)
    return doc


def merge_documents(
    target_path: Union[str, Path],
    source_paths: List[Union[str, Path]],
    output_path: Union[str, Path],
    page_breaks: bool = True
) -> Document:
    """Merges multiple documents into one (convenience function)."""
    doc = Document.open(target_path)
    for source_path in source_paths:
        doc.append(source_path, page_break=page_breaks)
    doc.save(output_path)
    return doc


def render_to_html(
    docx_path: Union[str, Path],
    html_path: Union[str, Path],
    editable: bool = False
) -> None:
    """Renderuje DOCX do HTML (convenience function)."""
    doc = Document.open(docx_path)
    doc.to_html(html_path, editable=editable)


def render_to_pdf(
    docx_path: Union[str, Path],
    pdf_path: Union[str, Path],
    backend: str = "rust"
) -> None:
    """Renderuje DOCX do PDF (convenience function)."""
    doc = Document.open(docx_path)
    doc.to_pdf(pdf_path, backend=backend)
