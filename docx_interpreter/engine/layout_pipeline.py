"""
Layout Pipeline - główny punkt wejścia dla całego procesu layoutowania.

Przykład użycia:
    from docx_interpreter.engine.layout_pipeline import LayoutPipeline
    from docx_interpreter.engine.geometry import Size, Margins
    from docx_interpreter.engine.page_engine import PageConfig
    
    # Konfiguracja strony
    page_config = PageConfig(
        page_size=Size(595, 842),  # A4 w punktach
        base_margins=Margins(top=72, bottom=72, left=72, right=72)
    )
    
    # Utwórz pipeline
    pipeline = LayoutPipeline(page_config)
    
    # Przetwórz model dokumentu
    unified_layout = pipeline.process(document_model)
    
    # Użyj UnifiedLayout do renderowania
    compiler.compile(unified_layout)
"""

from typing import Any, Optional, Tuple, List
from .layout_engine import LayoutEngine, LayoutStructure
from .assembler.layout_assembler import LayoutAssembler
from .pagination_manager import PaginationManager, HeaderFooterResolver
from .page_variator import PageVariator
from .layout_validator import LayoutValidator
from .page_engine import PageConfig
from .unified_layout import UnifiedLayout
from .geometry import twips_to_points
from ..media.image_cache import ImageConversionCache


class LayoutPipeline:
    """
    Główny pipeline layoutowania dokumentu.
    
    Przepływ:
    1. DocumentModel → LayoutEngine → LayoutStructure
    2. LayoutStructure → LayoutAssembler → UnifiedLayout
    3. UnifiedLayout → PaginationManager (stosuje nagłówki/stopki)
    4. UnifiedLayout → LayoutValidator (walidacja)
    5. UnifiedLayout → PDFCompiler/DOCXExporter/HTMLRenderer
    """
    
    def __init__(self, page_config: PageConfig, *, target: str = "pdf", resolve_placeholders: Optional[bool] = None):
        """
        Args:
            page_config: Konfiguracja strony (rozmiar, marginesy)
            target: Cel renderowania ("pdf", "html", "docx")
            resolve_placeholders: Czy podstawiać placeholdery (None = automatycznie na podstawie target: False dla "docx", True dla innych)
        """
        self.page_config = page_config
        self.target = str(target or "pdf").lower()
        
        # Automatycznie wyłącz podstawianie placeholderów dla eksportu DOCX
        if resolve_placeholders is None:
            resolve_placeholders = self.target != "docx"
        
        self.layout_engine = LayoutEngine(resolve_placeholders=resolve_placeholders)
        self.layout_assembler = LayoutAssembler(page_config, target=self.target)
        self.layout_structure: Optional[LayoutStructure] = None  # Zapisz ostatnią strukturę
        
        # Image conversion cache for async WMF/EMF conversion during parsing
        self.image_cache = ImageConversionCache(max_workers=4)
        self.image_cache.start()
    
    def process(
        self,
        document_model: Any,
        apply_headers_footers: Optional[bool] = None,
        validate: bool = False
    ) -> UnifiedLayout:
        """
        Przetwarza model dokumentu i zwraca UnifiedLayout.
        
        Args:
            document_model: Model dokumentu (z parsera DOCX)
            apply_headers_footers: Czy stosować nagłówki i stopki
            validate: Czy wykonać walidację (jeśli True, rzuca wyjątki przy błędach)
            
        Returns:
            UnifiedLayout gotowy do renderowania
        """
        # Krok 1: Interpretacja modelu (bez geometrii)
        layout_structure: LayoutStructure = self.layout_engine.build(document_model)
        self.layout_structure = layout_structure  # Zapisz dla debugowania

        header_distance_pt, footer_distance_pt = self._extract_header_footer_distances(document_model)

        if apply_headers_footers is None:
            apply_headers_footers = self.target == "pdf"

        page_variator: Optional[PageVariator] = None
        if self.target == "pdf":
            page_variator = PageVariator(
                layout_structure,
                self.layout_assembler,
                self.page_config,
                header_distance=header_distance_pt,
                footer_distance=footer_distance_pt,
            )
            self.layout_assembler.set_page_variator(page_variator)
        else:
            self.layout_assembler.set_page_variator(None)

        # Krok 2: Obliczanie geometrii i pozycjonowanie
        unified_layout: UnifiedLayout = self.layout_assembler.assemble(layout_structure)
        
        # Krok 3: Stosowanie nagłówków i stopek
        if apply_headers_footers:
            pagination_manager = PaginationManager(
                unified_layout,
                layout_assembler=self.layout_assembler,
                page_variator=page_variator,
            )
            pagination_manager.apply_headers_footers(layout_structure)
        
        # Krok 4: Walidacja (opcjonalna)
        if validate:
            validator = LayoutValidator(unified_layout)
            is_valid, errors, warnings = validator.validate()
            
            if not is_valid:
                error_msg = "\n".join(errors)
                raise ValueError(f"Layout validation failed:\n{error_msg}")
        
        return unified_layout
    
    def process_with_validation(
        self,
        document_model: Any,
        apply_headers_footers: bool = True
    ) -> Tuple[UnifiedLayout, bool, List[str], List[str]]:
        """
        Przetwarza model dokumentu z walidacją.
        
        Args:
            document_model: Model dokumentu (z parsera DOCX)
            apply_headers_footers: Czy stosować nagłówki i stopki
            
        Returns:
            Tuple (UnifiedLayout, is_valid, errors, warnings)
        """
        unified_layout = self.process(document_model, apply_headers_footers, validate=False)
        
        # Walidacja
        validator = LayoutValidator(unified_layout)
        is_valid, errors, warnings = validator.validate()
        
        return unified_layout, is_valid, errors, warnings
    
    def process_with_summary(
        self,
        document_model: Any,
        apply_headers_footers: bool = True
    ) -> Tuple[UnifiedLayout, dict]:
        """
        Przetwarza model dokumentu i zwraca UnifiedLayout z podsumowaniem walidacji.
        
        Args:
            document_model: Model dokumentu (z parsera DOCX)
            apply_headers_footers: Czy stosować nagłówki i stopki
            
        Returns:
            Tuple (UnifiedLayout, summary_dict)
        """
        unified_layout = self.process(document_model, apply_headers_footers, validate=False)
        
        # Walidacja i podsumowanie
        validator = LayoutValidator(unified_layout)
        summary = validator.get_summary()
        
        return unified_layout, summary

    def _extract_header_footer_distances(self, document_model: Any) -> tuple[Optional[float], Optional[float]]:
        header_distance = None
        footer_distance = None

        parser = getattr(document_model, "parser", None)
        if parser and hasattr(parser, "parse_sections"):
            try:
                sections = parser.parse_sections()
            except Exception:
                sections = []
            if sections:
                margins = sections[0].get("margins", {}) or {}
                header_distance = self._twips_to_points_safe(margins.get("header"))
                footer_distance = self._twips_to_points_safe(margins.get("footer"))

        return header_distance, footer_distance

    @staticmethod
    def _twips_to_points_safe(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            if isinstance(value, str):
                value = int(value)
            return twips_to_points(int(value))
        except (ValueError, TypeError):
            return None

