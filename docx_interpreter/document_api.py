"""
Document API - Wysokopoziomowe API do manipulacji dokumentami DOCX (Jinja-like).

Ten moduł zapewnia wygodne API podobne do starej biblioteki DocQuill,
ale korzysta z istniejących modeli i rendererów bez ich modyfikacji.
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
    Wysokopoziomowe API do manipulacji dokumentami DOCX.
    
    Zapewnia wygodne metody podobne do starej biblioteki DocQuill:
    - add_paragraph(), replace_text(), save()
    - fill_placeholders() - Jinja-like placeholder system
    - create_numbered_list(), create_bullet_list()
    - merge(), append(), prepend()
    
    Używa istniejących modeli i rendererów bez ich modyfikacji.
    """
    
    def __init__(self, document_model: Optional[Any] = None) -> None:
        """
        Inicjalizuje Document API.
        
        Args:
            document_model: Opcjonalny istniejący model dokumentu
        """
        self._document_model = document_model
        self._body: Optional[Body] = None
        self._placeholder_engine: Optional[PlaceholderEngine] = None
        self._watermarks: List[Any] = []  # Lista watermarków
        
        # Inicjalizuj body jeśli dokument model jest dostępny
        if document_model:
            self._init_from_model(document_model)
        else:
            # Utwórz pusty dokument
            self._body = Body()
            self._placeholder_engine = PlaceholderEngine(self)
    
    def _init_from_model(self, document_model: Any) -> None:
        """Inicjalizuje Document z istniejącego modelu."""
        # Próbuj pobrać body z modelu
        if hasattr(document_model, 'body'):
            self._body = document_model.body
        elif hasattr(document_model, '_body'):
            self._body = document_model._body
        elif hasattr(document_model, 'get_body'):
            self._body = document_model.get_body()
        else:
            # Utwórz nowy body
            self._body = Body()
        
        self._placeholder_engine = PlaceholderEngine(self)
    
    @classmethod
    def open(cls, file_path: Union[str, Path, BinaryIO]) -> "Document":
        """
        Otwiera dokument z pliku DOCX.
        
        Args:
            file_path: Ścieżka do pliku DOCX
            
        Returns:
            Document: Otworzony dokument
        """
        # Import parserów
        from .parser.package_reader import PackageReader
        from .parser.xml_parser import XMLParser
        from .models.body import Body
        
        # Otwórz dokument
        reader = PackageReader(file_path)
        parser = XMLParser(reader)
        
        # Parsuj body
        body = parser.parse_body()
        
        # Utwórz prosty model dokumentu
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
        Dodaje run do paragrafu z formatowaniem.
        
        Args:
            paragraph: Paragraf do którego dodać run
            text: Tekst runa
            bold: Czy pogrubiony
            italic: Czy kursywa
            underline: Czy podkreślony
            font_color: Kolor czcionki (np. "008000")
            font_size: Rozmiar czcionki w punktach
            font_name: Nazwa czcionki
            
        Returns:
            Run: Utworzony run
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
        Zastępuje tekst w dokumencie.
        
        Args:
            old_text: Tekst do zastąpienia
            new_text: Nowy tekst
            scope: Zakres ("body", "headers", "footers", "all")
            case_sensitive: Czy uwzględniać wielkość liter
            
        Returns:
            Liczba zastąpień
        """
        replacements = 0
        
        if not case_sensitive:
            # Case-insensitive search
            old_text_lower = old_text.lower()
        
        # Zastąp w paragrafach body
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
                            # Zachowaj oryginalną wielkość liter
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
        Wypełnia placeholdery w dokumencie (Jinja-like).
        
        Args:
            data: Słownik {placeholder_name: value}
            multi_pass: Czy używać wieloprzebiegowego renderowania
            max_passes: Maksymalna liczba przebiegów
            
        Returns:
            Liczba zastąpionych placeholderów
            
        Examples:
            >>> doc = Document.open("template.docx")
            >>> doc.fill_placeholders({
            ...     "TEXT:Name": "Jan Kowalski",
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
        Przetwarza blok warunkowy (START_nazwa / END_nazwa).
        
        Args:
            block_name: Nazwa bloku
            show: Czy pokazać blok (True) czy usunąć (False)
            
        Returns:
            True jeśli przetworzono
        """
        if self._placeholder_engine is None:
            self._placeholder_engine = PlaceholderEngine(self)
        
        return self._placeholder_engine.process_conditional_block(block_name, show)
    
    def extract_placeholders(self) -> List[PlaceholderInfo]:
        """
        Wyciąga wszystkie placeholdery z dokumentu.
        
        Returns:
            Lista obiektów PlaceholderInfo
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
        Dodaje watermark (znak wodny) do dokumentu.
        
        Args:
            text: Tekst watermarku
            angle: Kąt obrotu w stopniach (domyślnie 45)
            opacity: Przezroczystość 0.0-1.0 (domyślnie 0.5)
            color: Kolor tekstu (domyślnie #CCCCCC)
            font_size: Rozmiar czcionki w punktach (domyślnie 72)
            font_name: Nazwa czcionki (domyślnie Arial)
            
        Returns:
            Watermark: Utworzony watermark
            
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
        Zwraca listę watermarków w dokumencie.
        
        Returns:
            Lista watermarków
        """
        return self._watermarks.copy()
    
    @property
    def watermarks(self) -> List[Watermark]:
        """Zwraca listę watermarków (property)."""
        return self._watermarks
    
    def create_numbered_list(self) -> NumberingGroup:
        """
        Tworzy listę numerowaną.
        
        Returns:
            NumberingGroup: Grupa numeracji
        """
        from .models.numbering import NumberingGroup
        
        group = NumberingGroup()
        # Konfiguracja domyślnej listy numerowanej
        group.set_format("decimal")
        
        return group
    
    def create_bullet_list(self) -> NumberingGroup:
        """
        Tworzy listę punktową.
        
        Returns:
            NumberingGroup: Grupa numeracji
        """
        from .models.numbering import NumberingGroup
        
        group = NumberingGroup()
        # Konfiguracja domyślnej listy punktowej
        group.set_format("bullet")
        
        return group
    
    def save(self, file_path: Union[str, Path]) -> None:
        """
        Zapisuje dokument do pliku DOCX.
        
        Args:
            file_path: Ścieżka do pliku wyjściowego
            
        Examples:
            >>> doc.save("output.docx")
        """
        from .export.docx_exporter import DOCXExporter
        
        # Jeśli dokument ma _file_path (oryginalny plik), użyj go jako szablonu
        source_docx_path = None
        if hasattr(self._document_model, '_file_path') and self._document_model._file_path:
            source_docx_path = self._document_model._file_path
        elif hasattr(self._document_model, '_source_docx') and self._document_model._source_docx:
            source_docx_path = self._document_model._source_docx
        
        # Użyj DOCXExporter do zapisu (z source_docx_path jeśli dostępny)
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
        Łączy dokument z innym dokumentem.
        
        Args:
            other: Inny dokument (Document, ścieżka do pliku, lub Path)
            page_break: Czy dodać podział strony przed połączonym dokumentem
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
        Dodaje dokument na koniec.
        
        Args:
            other: Inny dokument (Document, ścieżka do pliku, lub Path)
            page_break: Czy dodać podział strony
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
        Dodaje dokument na początku.
        
        Args:
            other: Inny dokument (Document, ścieżka do pliku, lub Path)
            page_break: Czy dodać podział strony
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
        Zaawansowane selektywne łączenie elementów z różnych dokumentów.
        
        Args:
            sources: Słownik określający źródła dla każdego elementu:
                    {
                        "body": source_doc1,      # Body z tego dokumentu
                        "headers": source_doc2,    # Headers z tego dokumentu
                        "footers": source_doc3,    # Footers z tego dokumentu
                        "sections": source_doc4,   # Sections z tego dokumentu
                        "styles": source_doc5,     # Styles z tego dokumentu
                        "numbering": source_doc6   # Numbering z tego dokumentu
                    }
            page_break: Czy dodać podział strony przed scalonymi elementami
            
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
        Łączy nagłówki z dokumentu źródłowego.
        
        Args:
            source: Dokument źródłowy
            header_types: Lista typów nagłówków ("default", "first", "even")
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
        Łączy stopki z dokumentu źródłowego.
        
        Args:
            source: Dokument źródłowy
            footer_types: Lista typów stopek ("default", "first", "even")
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
        Łączy sekcje z dokumentu źródłowego (właściwości strony, marginesy).
        
        Args:
            source: Dokument źródłowy
            copy_properties: Czy kopiować właściwości sekcji
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
        Łączy style z dokumentu źródłowego.
        
        Args:
            source: Dokument źródłowy
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
        Aplikuje layout (headers/footers) z dokumentu szablonu.
        
        Convenience method która łączy merge_headers() i merge_footers().
        
        Args:
            template: Dokument szablonu z headers/footers
            header_types: Lista typów nagłówków do aplikacji (None = wszystkie)
            footer_types: Lista typów stopek do aplikacji (None = wszystkie)
            
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
        Renderuje dokument do HTML.
        
        Args:
            output_path: Ścieżka do pliku wyjściowego HTML
            editable: Czy HTML ma być edytowalny (contenteditable)
            
        Note:
            Używa istniejącego HTMLRenderer bez modyfikacji.
        """
        from .renderers import HTMLRenderer
        
        # Użyj istniejącego renderera
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
        Renderuje dokument do PDF używając PDFCompiler.
        
        Args:
            output_path: Ścieżka do pliku wyjściowego PDF
            engine: Silnik renderowania ("reportlab" lub "direct") - obecnie zawsze używa PDFCompiler
            page_size: Rozmiar strony w punktach (width, height), domyślnie A4 (595, 842)
            margins: Marginesy w punktach (top, bottom, left, right), domyślnie (72, 72, 72, 72)
            
        Examples:
            >>> doc.render_pdf("output.pdf")
            >>> doc.render_pdf("output.pdf", page_size=(595, 842), margins=(72, 72, 72, 72))
        """
        from .engine.layout_pipeline import LayoutPipeline
        from .engine.pdf.pdf_compiler import PDFCompiler
        from .engine.geometry import Size, Margins
        from .engine.page_engine import PageConfig
        
        # Domyślne wartości
        if page_size is None:
            page_size = (595, 842)  # A4 w punktach
        if margins is None:
            margins = (72, 72, 72, 72)  # 1 cal = 72 punkty
        
        # Pobierz package_reader jeśli dostępny
        package_reader = None
        if hasattr(self._document_model, '_package_reader'):
            package_reader = self._document_model._package_reader
        elif hasattr(self._document_model, 'parser') and hasattr(self._document_model.parser, 'package_reader'):
            package_reader = self._document_model.parser.package_reader
        
        # Utwórz PageConfig
        page_config = PageConfig(
            page_size=Size(page_size[0], page_size[1]),
            base_margins=Margins(
                top=margins[0],
                bottom=margins[1],
                left=margins[2],
                right=margins[3]
            )
        )
        
        # Utwórz adapter dla LayoutPipeline
        class DocumentAdapter:
            def __init__(self, body_obj, parser, sections=None):
                self.elements = body_obj.children if hasattr(body_obj, 'children') else []
                self.parser = parser
                self._body = body_obj
                # Kopiuj sekcje z parametru lub spróbuj pobrać z parsera
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
        
        # Utwórz LayoutPipeline i przetwórz dokument
        pipeline = LayoutPipeline(page_config)
        unified_layout = pipeline.process(
            document_model,
            apply_headers_footers=True,
            validate=False
        )
        
        # Utwórz PDFCompiler i skompiluj do PDF
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
        Aktualizuje dokument na podstawie edytowanego pliku HTML.
        
        Args:
            html_path: Ścieżka do pliku HTML z edytowaną zawartością
            preserve_structure: Czy zachować strukturę dokumentu (tabele, obrazy, etc.)
            
        Examples:
            >>> doc = Document.open("template.docx")
            >>> doc.render_html("editable.html", editable=True)
            >>> # ... edycja w przeglądarce ...
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
        
        # Jeśli preserve_structure, aktualizuj tylko paragrafy tekstowe
        # W przeciwnym razie zastąp całą zawartość body
        if preserve_structure:
            # Znajdź wszystkie paragrafy tekstowe w dokumencie
            if hasattr(body, 'get_paragraphs'):
                paragraphs = body.get_paragraphs()
            elif hasattr(body, 'children'):
                paragraphs = [child for child in body.children if hasattr(child, '__class__') and 'Paragraph' in child.__class__.__name__]
            else:
                paragraphs = []
            
            # Aktualizuj istniejące paragrafy
            for i, para in enumerate(paragraphs):
                if i < len(parsed_paragraphs):
                    parsed_para = parsed_paragraphs[i]
                    self._update_paragraph_from_html(para, parsed_para)
            
            # Dodaj nowe paragrafy jeśli jest ich więcej w HTML
            if len(parsed_paragraphs) > len(paragraphs):
                for i in range(len(paragraphs), len(parsed_paragraphs)):
                    parsed_para = parsed_paragraphs[i]
                    new_para = self._create_paragraph_from_html(parsed_para)
                    if hasattr(body, 'add_paragraph'):
                        body.add_paragraph(new_para)
                    elif hasattr(body, 'add_child'):
                        body.add_child(new_para)
        else:
            # Zastąp całą zawartość body
            # Usuń wszystkie istniejące paragrafy
            if hasattr(body, 'children'):
                # Usuń tylko paragrafy, zachowaj tabele i inne elementy
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
        """Aktualizuje istniejący paragraf na podstawie HTML."""
        from .models.run import Run
        
        # Aktualizuj numbering jeśli paragraf jest częścią listy
        numbering_info = parsed_para.get('numbering')
        if numbering_info:
            numbering_id = numbering_info.get('id')
            level = numbering_info.get('level', 0)
            
            # Spróbuj użyć istniejącego numbering_id lub ustaw bezpośrednio
            if numbering_id:
                try:
                    para.set_list(level=level, numbering_id=numbering_id)
                except (ValueError, AttributeError):
                    # Jeśli set_list nie działa, ustaw numbering bezpośrednio
                    if hasattr(para, 'numbering'):
                        para.numbering = {
                            'id': numbering_id,
                            'level': level,
                            'format': numbering_info.get('format', 'decimal')
                        }
        elif hasattr(para, 'numbering'):
            # Usuń numbering jeśli nie ma go w HTML
            para.numbering = None
        
        # Wyczyść istniejące runs
        if hasattr(para, 'runs'):
            para.runs.clear()
        if hasattr(para, 'children'):
            # Usuń tylko runs, zachowaj inne elementy
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
                # Upewnij się, że kolor jest w formacie hex (RRGGBB) bez #
                if color.startswith('#'):
                    color = color[1:]
                # Ustaw kolor
                run.color = color
            
            if run_data.get('font_size'):
                font_size = run_data.get('font_size')
                # font_size może być stringiem (half-points) lub intem
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
        
        # Ustaw numbering jeśli paragraf jest częścią listy
        numbering_info = parsed_para.get('numbering')
        if numbering_info:
            numbering_id = numbering_info.get('id')
            level = numbering_info.get('level', 0)
            
            # Spróbuj użyć istniejącego numbering_id lub utwórz nowy
            if numbering_id:
                try:
                    para.set_list(level=level, numbering_id=numbering_id)
                except (ValueError, AttributeError):
                    # Jeśli set_list nie działa, ustaw numbering bezpośrednio
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
                # Upewnij się, że kolor jest w formacie hex (RRGGBB) bez #
                if color.startswith('#'):
                    color = color[1:]
                # Ustaw kolor
                run.color = color
            
            if run_data.get('font_size'):
                font_size = run_data.get('font_size')
                # font_size może być stringiem (half-points) lub intem
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
        """Tworzy nową tabelę na podstawie HTML."""
        from .models.table import Table, TableRow, TableCell
        
        table = Table()
        
        # Dodaj wiersze
        for row_data in parsed_table.get('rows', []):
            row = TableRow()
            
            # Ustaw czy to header row
            if row_data.get('is_header'):
                row.set_header_row(True)
            
            # Dodaj komórki
            for cell_data in row_data.get('cells', []):
                cell = TableCell()
                
                # Dodaj paragrafy do komórki
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
        
        # Ustaw właściwości obrazu
        rel_id = parsed_image.get('rel_id', '')
        if rel_id:
            image.set_rel_id(rel_id)
        
        src = parsed_image.get('src', '')
        if src:
            # Jeśli src wygląda jak ścieżka, zapisz jako part_path
            if '/' in src or '\\' in src or src.startswith('image_'):
                image.set_part_path(src)
        
        width = parsed_image.get('width')
        height = parsed_image.get('height')
        if width and height:
            # Konwertuj px do EMU jeśli potrzeba (1px ≈ 9525 EMU)
            if width < 1000:  # Prawdopodobnie px
                width = int(width * 9525)
            if height < 1000:  # Prawdopodobnie px
                height = int(height * 9525)
            image.set_size(width, height)
        
        alt_text = parsed_image.get('alt', '')
        if alt_text:
            image.alt_text = alt_text
        
        return image

