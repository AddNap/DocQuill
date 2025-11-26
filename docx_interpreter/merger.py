"""
Zaawansowany Document Merger - scalanie dokumentów DOCX z możliwością selektywnego łączenia elementów.

Umożliwia:
- Łączenie całych dokumentów (jak docx-compose)
- Selektywne łączenie elementów:
  - Body (paragrafy, tabele) z jednego dokumentu
  - Headers (default, first, even) z innego
  - Footers (default, first, even) z jeszcze innego
  - Sections z właściwościami strony
  - Styles/Themes
  - Numbering
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, Set
from pathlib import Path
import copy
import logging

from .models.body import Body
from .models.paragraph import Paragraph
from .models.table import Table
from .layout.section import Section
from .layout.header import Header, HeaderType
from .layout.footer import Footer, FooterType

logger = logging.getLogger(__name__)

# Import relationship merger jeśli dostępny
try:
    from .merger.relationship_merger import RelationshipMerger
except ImportError:
    try:
        from docx_interpreter.merger.relationship_merger import RelationshipMerger
    except ImportError:
        RelationshipMerger = None


class MergeOptions:
    """Opcje scalania dokumentów."""
    
    def __init__(
        self,
        page_break: bool = False,
        resolve_style_conflicts: bool = True,
        resolve_numbering_conflicts: bool = True,
        preserve_formatting: bool = True,
        merge_media: bool = True
    ):
        """
        Inicjalizuje opcje scalania.
        
        Args:
            page_break: Czy dodać podział strony przed scalonymi elementami
            resolve_style_conflicts: Czy automatycznie rozwiązywać konflikty stylów
            resolve_numbering_conflicts: Czy automatycznie rozwiązywać konflikty numeracji
            preserve_formatting: Czy zachować formatowanie
            merge_media: Czy łączyć media (obrazy, etc.)
        """
        self.page_break = page_break
        self.resolve_style_conflicts = resolve_style_conflicts
        self.resolve_numbering_conflicts = resolve_numbering_conflicts
        self.preserve_formatting = preserve_formatting
        self.merge_media = merge_media


class DocumentMerger:
    """
    Zaawansowany engine do scalania dokumentów DOCX.
    
    Umożliwia zarówno pełne scalanie dokumentów jak i selektywne łączenie
    poszczególnych elementów (body, headers, footers, sections, styles, numbering).
    """
    
    def __init__(self, target_document: Any) -> None:
        """
        Inicjalizuje merger.
        
        Args:
            target_document: Dokument docelowy (do którego będą dodawane elementy)
        """
        self.target = target_document
        self._style_id_mapping: Dict[str, str] = {}
        self._numbering_id_mapping: Dict[int, int] = {}
        self._relationship_merger: Optional[Any] = None
        
        # Pobierz PackageReader dla dokumentu docelowego jeśli dostępny
        self._target_package_reader = self._get_package_reader(target_document)
    
    def merge_full(
        self,
        source_document: Union[Any, str, Path],
        options: Optional[MergeOptions] = None
    ) -> None:
        """
        Łączy cały dokument z dokumentem źródłowym (jak docx-compose).
        
        Zachowuje wszystkie relacje OPC, kopiuje części i aktualizuje zależności.
        
        Args:
            source_document: Dokument źródłowy (Document, ścieżka, lub Path)
            options: Opcje scalania
            
        Examples:
            >>> merger = DocumentMerger(target_doc)
            >>> merger.merge_full(source_doc, MergeOptions(page_break=True))
        """
        if options is None:
            options = MergeOptions()
        
        source = self._load_document(source_document)
        
        # Inicjalizuj relationship merger jeśli dostępny
        source_package_reader = self._get_package_reader(source)
        if RelationshipMerger and self._target_package_reader and source_package_reader:
            self._relationship_merger = RelationshipMerger(
                self._target_package_reader,
                source_package_reader
            )
        
        # Scal body (z relacjami)
        self.merge_body(source, options)
        
        # Scal headers i footers (z relacjami)
        self.merge_headers(source, options)
        self.merge_footers(source, options)
        
        # Scal sekcje
        self.merge_sections(source, options)
        
        # Scal style i numbering
        if options.resolve_style_conflicts:
            self.merge_styles(source, options)
        if options.resolve_numbering_conflicts:
            self.merge_numbering(source, options)
        
        # Scal media (z relacjami)
        if options.merge_media:
            self.merge_media(source, options)
        
        # Aktualizuj [Content_Types].xml
        if self._relationship_merger:
            self._relationship_merger.update_content_types()
    
    def merge_body(
        self,
        source_document: Union[Any, str, Path],
        options: Optional[MergeOptions] = None,
        position: str = "append"
    ) -> None:
        """
        Łączy tylko body (paragrafy, tabele) z dokumentu źródłowego.
        
        Args:
            source_document: Dokument źródłowy
            options: Opcje scalania
            position: Pozycja dodania ("append", "prepend", "insert")
            
        Examples:
            >>> merger = DocumentMerger(target_doc)
            >>> merger.merge_body(source_doc, MergeOptions(page_break=True))
        """
        if options is None:
            options = MergeOptions()
        
        source = self._load_document(source_document)
        source_body = self._get_body(source)
        target_body = self._get_body(self.target)
        
        if not source_body or not target_body:
            logger.warning("Cannot merge body: source or target body not found")
            return
        
        # Pobierz elementy z source body
        source_paragraphs = self._get_paragraphs(source_body)
        source_tables = self._get_tables(source_body)
        
        # Dodaj page break jeśli wymagane
        if options.page_break and position == "append":
            if source_paragraphs:
                # Dodaj page break przed pierwszym paragrafem
                first_para = source_paragraphs[0]
                if hasattr(first_para, 'spacing_before'):
                    first_para.spacing_before = (first_para.spacing_before or 0) + 1440  # 1 cal
        
        # Kopiuj paragrafy
        for para in source_paragraphs:
            new_para = self._deep_copy_paragraph(para)
            if position == "append":
                target_body.add_paragraph(new_para)
            elif position == "prepend":
                # Prepend wymaga dostępu do listy children
                if hasattr(target_body, 'children'):
                    target_body.children.insert(0, new_para)
                else:
                    target_body.add_paragraph(new_para)
        
        # Kopiuj tabele
        for table in source_tables:
            new_table = self._deep_copy_table(table)
            if position == "append":
                target_body.add_table(new_table)
            elif position == "prepend":
                if hasattr(target_body, 'children'):
                    target_body.children.insert(0, new_table)
                else:
                    target_body.add_table(new_table)
    
    def merge_headers(
        self,
        source_document: Union[Any, str, Path],
        options: Optional[MergeOptions] = None,
        header_types: Optional[List[str]] = None
    ) -> None:
        """
        Łączy nagłówki z dokumentu źródłowego.
        
        Args:
            source_document: Dokument źródłowy
            options: Opcje scalania
            header_types: Lista typów nagłówków do scalenia (None = wszystkie)
                         Możliwe wartości: "default", "first", "even"
                         
        Examples:
            >>> merger = DocumentMerger(target_doc)
            >>> # Scal tylko default header
            >>> merger.merge_headers(source_doc, header_types=["default"])
            >>> # Scal wszystkie nagłówki
            >>> merger.merge_headers(source_doc)
        """
        if options is None:
            options = MergeOptions()
        
        source = self._load_document(source_document)
        
        # Pobierz sekcje z obu dokumentów
        target_sections = self._get_sections(self.target)
        source_sections = self._get_sections(source)
        
        if not target_sections:
            logger.warning("Target document has no sections")
            return
        
        if not source_sections:
            logger.warning("Source document has no sections")
            return
        
        # Domyślnie scal wszystkie typy
        if header_types is None:
            header_types = ["default", "first", "even"]
        
        # Scal nagłówki z pierwszej sekcji source do pierwszej sekcji target
        target_section = target_sections[0]
        source_section = source_sections[0]
        
        source_headers = self._get_headers(source_section)
        
        for header_type_str in header_types:
            header_type = self._parse_header_type(header_type_str)
            if header_type and header_type.value in source_headers:
                source_header = source_headers[header_type.value]
                if source_header:
                    # Skopiuj header
                    new_header = self._deep_copy_header(source_header)
                    target_section.headers[header_type.value] = new_header
    
    def merge_footers(
        self,
        source_document: Union[Any, str, Path],
        options: Optional[MergeOptions] = None,
        footer_types: Optional[List[str]] = None
    ) -> None:
        """
        Łączy stopki z dokumentu źródłowego.
        
        Args:
            source_document: Dokument źródłowy
            options: Opcje scalania
            footer_types: Lista typów stopek do scalenia (None = wszystkie)
                         Możliwe wartości: "default", "first", "even"
                         
        Examples:
            >>> merger = DocumentMerger(target_doc)
            >>> # Scal tylko default footer
            >>> merger.merge_footers(source_doc, footer_types=["default"])
        """
        if options is None:
            options = MergeOptions()
        
        source = self._load_document(source_document)
        
        # Pobierz sekcje
        target_sections = self._get_sections(self.target)
        source_sections = self._get_sections(source)
        
        if not target_sections or not source_sections:
            return
        
        # Domyślnie scal wszystkie typy
        if footer_types is None:
            footer_types = ["default", "first", "even"]
        
        target_section = target_sections[0]
        source_section = source_sections[0]
        
        source_footers = self._get_footers(source_section)
        
        for footer_type_str in footer_types:
            footer_type = self._parse_footer_type(footer_type_str)
            if footer_type and footer_type.value in source_footers:
                source_footer = source_footers[footer_type.value]
                if source_footer:
                    new_footer = self._deep_copy_footer(source_footer)
                    target_section.footers[footer_type.value] = new_footer
    
    def merge_sections(
        self,
        source_document: Union[Any, str, Path],
        options: Optional[MergeOptions] = None,
        copy_properties: bool = True
    ) -> None:
        """
        Łączy sekcje z dokumentu źródłowego (właściwości strony, marginesy, etc.).
        
        Args:
            source_document: Dokument źródłowy
            options: Opcje scalania
            copy_properties: Czy kopiować właściwości sekcji (rozmiar strony, marginesy)
                            
        Examples:
            >>> merger = DocumentMerger(target_doc)
            >>> merger.merge_sections(source_doc, copy_properties=True)
        """
        if options is None:
            options = MergeOptions()
        
        source = self._load_document(source_document)
        
        target_sections = self._get_sections(self.target)
        source_sections = self._get_sections(source)
        
        if not target_sections or not source_sections:
            return
        
        if copy_properties:
            # Skopiuj właściwości z pierwszej sekcji source do pierwszej sekcji target
            target_section = target_sections[0]
            source_section = source_sections[0]
            
            # Kopiuj właściwości strony
            target_section.page_width = source_section.page_width
            target_section.page_height = source_section.page_height
            target_section.orientation = source_section.orientation
            
            # Kopiuj marginesy
            target_section.margin_top = source_section.margin_top
            target_section.margin_bottom = source_section.margin_bottom
            target_section.margin_left = source_section.margin_left
            target_section.margin_right = source_section.margin_right
            
            # Kopiuj właściwości kolumn
            target_section.column_layout = source_section.column_layout
            target_section.column_count = source_section.column_count
            target_section.column_spacing = source_section.column_spacing
    
    def merge_styles(
        self,
        source_document: Union[Any, str, Path],
        options: Optional[MergeOptions] = None
    ) -> None:
        """
        Łączy style z dokumentu źródłowego, rozwiązując konflikty.
        
        Args:
            source_document: Dokument źródłowy
            options: Opcje scalania
        """
        if options is None:
            options = MergeOptions()
        
        source = self._load_document(source_document)
        
        # Pobierz style z obu dokumentów
        target_styles = self._get_styles(self.target)
        source_styles = self._get_styles(source)
        
        if not target_styles:
            target_styles = {}
        if not source_styles:
            return
        
        # Rozwiąż konflikty stylów
        for style_id, style_data in source_styles.items():
            if style_id in target_styles:
                # Konflikt - dodaj suffix
                new_style_id = f"{style_id}_merged"
                self._style_id_mapping[style_id] = new_style_id
                target_styles[new_style_id] = copy.deepcopy(style_data)
            else:
                # Brak konfliktu - dodaj bezpośrednio
                target_styles[style_id] = copy.deepcopy(style_data)
    
    def merge_numbering(
        self,
        source_document: Union[Any, str, Path],
        options: Optional[MergeOptions] = None
    ) -> None:
        """
        Łączy numerację z dokumentu źródłowego, rozwiązując konflikty.
        
        Args:
            source_document: Dokument źródłowy
            options: Opcje scalania
        """
        if options is None:
            options = MergeOptions()
        
        source = self._load_document(source_document)
        
        # Pobierz numbering z obu dokumentów
        target_numbering = self._get_numbering(self.target)
        source_numbering = self._get_numbering(source)
        
        if not target_numbering or not source_numbering:
            return
        
        # Rozwiąż konflikty numbering IDs
        # TODO: Pełna implementacja wymaga dostępu do numbering system
        logger.info("Numbering merge - basic implementation")
    
    def merge_media(
        self,
        source_document: Union[Any, str, Path],
        options: Optional[MergeOptions] = None
    ) -> None:
        """
        Łączy media (obrazy, etc.) z dokumentu źródłowego wraz z relacjami.
        
        Args:
            source_document: Dokument źródłowy
            options: Opcje scalania
        """
        if options is None:
            options = MergeOptions()
        
        source = self._load_document(source_document)
        
        if not self._relationship_merger:
            logger.warning("RelationshipMerger not available - media merge limited")
            return
        
        # Pobierz wszystkie obrazy z dokumentu źródłowego
        source_body = self._get_body(source)
        if not source_body:
            return
        
        # Znajdź wszystkie obrazy w paragrafach i tabelach
        paragraphs = self._get_paragraphs(source_body)
        for para in paragraphs:
            runs = self._get_runs(para)
            for run in runs:
                if hasattr(run, 'image') and run.image:
                    # Pobierz rel_id z obrazu
                    if hasattr(run.image, 'rel_id') and run.image.rel_id:
                        # Skopiuj media wraz z relacjami
                        new_rel_id = self._relationship_merger.copy_media_with_relationships(
                            run.image.rel_id,
                            "document"
                        )
                        # TODO: Zaktualizuj rel_id w run.image w docelowym dokumencie
        
        # Znajdź obrazy w tabelach
        tables = self._get_tables(source_body)
        for table in tables:
            rows = self._get_table_rows(table)
            for row in rows:
                cells = self._get_row_cells(row)
                for cell in cells:
                    cell_paragraphs = self._get_paragraphs(cell)
                    for para in cell_paragraphs:
                        runs = self._get_runs(para)
                        for run in runs:
                            if hasattr(run, 'image') and run.image:
                                if hasattr(run.image, 'rel_id') and run.image.rel_id:
                                    new_rel_id = self._relationship_merger.copy_media_with_relationships(
                                        run.image.rel_id,
                                        "document"
                                    )
    
    def merge_selective(
        self,
        sources: Dict[str, Union[Any, str, Path]],
        options: Optional[MergeOptions] = None
    ) -> None:
        """
        Zaawansowane selektywne łączenie elementów z różnych dokumentów.
        
        Args:
            sources: Słownik określający źródła dla każdego elementu:
                    {
                        "body": source_doc1,      # Body z tego dokumentu
                        "headers": source_doc2,  # Headers z tego dokumentu
                        "footers": source_doc3,   # Footers z tego dokumentu
                        "sections": source_doc4,   # Sections z tego dokumentu
                        "styles": source_doc5,    # Styles z tego dokumentu
                        "numbering": source_doc6   # Numbering z tego dokumentu
                    }
            options: Opcje scalania
            
        Examples:
            >>> merger = DocumentMerger(target_doc)
            >>> merger.merge_selective({
            ...     "body": "content.docx",
            ...     "headers": "header_template.docx",
            ...     "footers": "footer_template.docx",
            ...     "styles": "style_template.docx"
            ... })
        """
        if options is None:
            options = MergeOptions()
        
        # Scal body
        if "body" in sources:
            self.merge_body(sources["body"], options)
        
        # Scal headers
        if "headers" in sources:
            header_types = sources.get("header_types", None)
            self.merge_headers(sources["headers"], options, header_types)
        
        # Scal footers
        if "footers" in sources:
            footer_types = sources.get("footer_types", None)
            self.merge_footers(sources["footers"], options, footer_types)
        
        # Scal sections
        if "sections" in sources:
            copy_props = sources.get("copy_section_properties", True)
            self.merge_sections(sources["sections"], options, copy_props)
        
        # Scal styles
        if "styles" in sources:
            self.merge_styles(sources["styles"], options)
        
        # Scal numbering
        if "numbering" in sources:
            self.merge_numbering(sources["numbering"], options)
        
        # Scal media
        if "media" in sources:
            self.merge_media(sources["media"], options)
    
    # Helper methods
    def _load_document(self, source: Union[Any, str, Path]) -> Any:
        """Ładuje dokument jeśli podano ścieżkę."""
        if isinstance(source, (str, Path)):
            # Import Document API
            from .document_api import Document
            return Document.open(source)
        return source
    
    def _get_body(self, document: Any) -> Optional[Body]:
        """Pobiera body z dokumentu."""
        if hasattr(document, 'body'):
            return document.body
        elif hasattr(document, '_body'):
            return document._body
        elif hasattr(document, 'get_body'):
            return document.get_body()
        return None
    
    def _get_paragraphs(self, body: Body) -> List[Paragraph]:
        """Pobiera paragrafy z body."""
        if hasattr(body, 'get_paragraphs'):
            return list(body.get_paragraphs() or [])
        elif hasattr(body, 'paragraphs'):
            return list(body.paragraphs or [])
        elif hasattr(body, 'children'):
            from .models.paragraph import Paragraph
            return [c for c in body.children if isinstance(c, Paragraph)]
        return []
    
    def _get_tables(self, body: Body) -> List[Table]:
        """Pobiera tabele z body."""
        if hasattr(body, 'get_tables'):
            return list(body.get_tables() or [])
        elif hasattr(body, 'tables'):
            return list(body.tables or [])
        elif hasattr(body, 'children'):
            from .models.table import Table
            return [c for c in body.children if isinstance(c, Table)]
        return []
    
    def _get_sections(self, document: Any) -> List[Section]:
        """Pobiera sekcje z dokumentu."""
        body = self._get_body(document)
        if body and hasattr(body, 'sections'):
            return list(body.sections or [])
        elif hasattr(document, 'sections'):
            return list(document.sections or [])
        return []
    
    def _get_headers(self, section: Section) -> Dict[str, Header]:
        """Pobiera nagłówki z sekcji."""
        if hasattr(section, 'headers'):
            return section.headers
        return {}
    
    def _get_footers(self, section: Section) -> Dict[str, Footer]:
        """Pobiera stopki z sekcji."""
        if hasattr(section, 'footers'):
            return section.footers
        return {}
    
    def _get_styles(self, document: Any) -> Optional[Dict[str, Any]]:
        """Pobiera style z dokumentu."""
        if hasattr(document, 'styles'):
            return document.styles
        elif hasattr(document, '_styles'):
            return document._styles
        return None
    
    def _get_numbering(self, document: Any) -> Optional[Any]:
        """Pobiera numbering z dokumentu."""
        if hasattr(document, 'numbering'):
            return document.numbering
        elif hasattr(document, '_numbering'):
            return document._numbering
        return None
    
    def _get_package_reader(self, document: Any) -> Optional[Any]:
        """Pobiera PackageReader z dokumentu jeśli dostępny."""
        # Sprawdź różne możliwe lokalizacje PackageReader
        if hasattr(document, 'package_reader'):
            return document.package_reader
        elif hasattr(document, '_package_reader'):
            return document._package_reader
        elif hasattr(document, '_document_model'):
            doc_model = document._document_model
            if hasattr(doc_model, 'package_reader'):
                return doc_model.package_reader
        elif hasattr(document, 'parser'):
            parser = document.parser
            if hasattr(parser, 'package_reader'):
                return parser.package_reader
        
        # Jeśli dokument jest ścieżką, utwórz PackageReader
        if isinstance(document, (str, Path)):
            from .parser.package_reader import PackageReader
            try:
                return PackageReader(document)
            except Exception:
                pass
        
        return None
    
    def _parse_header_type(self, header_type_str: str) -> Optional[HeaderType]:
        """Parsuje typ nagłówka."""
        mapping = {
            "default": HeaderType.DEFAULT,
            "first": HeaderType.FIRST_PAGE,
            "even": HeaderType.EVEN_PAGE,
            "odd": HeaderType.ODD_PAGE
        }
        return mapping.get(header_type_str.lower())
    
    def _parse_footer_type(self, footer_type_str: str) -> Optional[FooterType]:
        """Parsuje typ stopki."""
        mapping = {
            "default": FooterType.DEFAULT,
            "first": FooterType.FIRST_PAGE,
            "even": FooterType.EVEN_PAGE,
            "odd": FooterType.ODD_PAGE
        }
        return mapping.get(footer_type_str.lower())
    
    def _deep_copy_paragraph(self, para: Paragraph) -> Paragraph:
        """Głęboka kopia paragrafu."""
        new_para = copy.deepcopy(para)
        return new_para
    
    def _deep_copy_table(self, table: Table) -> Table:
        """Głęboka kopia tabeli."""
        new_table = copy.deepcopy(table)
        return new_table
    
    def _deep_copy_header(self, header: Header) -> Header:
        """Głęboka kopia nagłówka."""
        new_header = copy.deepcopy(header)
        return new_header
    
    def _deep_copy_footer(self, footer: Footer) -> Footer:
        """Głęboka kopia stopki."""
        new_footer = copy.deepcopy(footer)
        return new_footer

