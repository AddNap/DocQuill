"""Test generujący PDF z pliku Zapytanie Ofertowe używając nowego systemu layoutowania."""

import pytest
from pathlib import Path
import sys

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docx_interpreter.parser.package_reader import PackageReader
from docx_interpreter.parser.xml_parser import XMLParser
from docx_interpreter.engine.layout_pipeline import LayoutPipeline
from docx_interpreter.engine.geometry import Size, Margins
from docx_interpreter.engine.page_engine import PageConfig
from docx_interpreter.renderers.pdf_renderer import PdfRenderer


@pytest.fixture
def sample_docx_path():
    """Fixture zwracająca ścieżkę do pliku Zapytanie_Ofertowe.docx."""
    path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    if not path.exists():
        pytest.skip(f"Plik testowy nie znaleziony: {path}")
    return str(path)


@pytest.mark.integration
def test_generate_pdf_from_layout_new_system(sample_docx_path, tmp_path):
    """Test generujący PDF używając nowego systemu layoutowania (LayoutPipeline + UnifiedLayout).
    
    Args:
        sample_docx_path: Fixture zwracająca ścieżkę do pliku Zapytanie_Ofertowe.docx
        tmp_path: Fixture pytest tworząca tymczasowy katalog
    """
    # Ścieżka do pliku wejściowego
    input_path = Path(sample_docx_path)
    assert input_path.exists(), f"Plik wejściowy nie istnieje: {input_path}"
    
    # Ścieżka do pliku wyjściowego
    output_path = tmp_path / "Zapytanie_Ofertowe_new_layout.pdf"
    
    # 1. Załaduj i parsuj dokument
    package_reader = PackageReader(input_path)
    xml_parser = XMLParser(package_reader)
    body = xml_parser.parse_body()
    
    # 2. Utwórz adapter dla LayoutEngine
    class DocumentAdapter:
        def __init__(self, body_obj):
            self.elements = body_obj.children if hasattr(body_obj, 'children') else []
    
    document_model = DocumentAdapter(body)
    
    # 3. Konfiguracja strony
    page_config = PageConfig(
        page_size=Size(595, 842),  # A4 w punktach
        base_margins=Margins(top=72, bottom=72, left=72, right=72)
    )
    
    # 4. Utwórz pipeline i przetwórz dokument
    pipeline = LayoutPipeline(page_config)
    unified_layout = pipeline.process(
        document_model,
        apply_headers_footers=True,
        validate=False
    )
    
    # 5. Renderuj do PDF
    page_size_tuple = (page_config.page_size.width, page_config.page_size.height)
    margins_tuple = (
        page_config.base_margins.top,
        page_config.base_margins.right,
        page_config.base_margins.bottom,
        page_config.base_margins.left
    )
    
    pdf_renderer = PdfRenderer(
        page_size=page_size_tuple,
        margins=margins_tuple,
        dpi=72.0
    )
    
    pdf_renderer.render(unified_layout.pages, str(output_path))
    
    # Sprawdź wyniki
    assert output_path.exists(), f"Plik PDF nie został utworzony: {output_path}"
    assert output_path.stat().st_size > 0, "Plik PDF jest pusty"
    
    print(f"\n✅ PDF wygenerowany pomyślnie: {output_path}")
    print(f"   Rozmiar: {output_path.stat().st_size:,} bajtów")
    print(f"   Stron: {len(unified_layout.pages)}")


@pytest.mark.integration
def test_generate_pdf_from_layout_custom_output(sample_docx_path):
    """Test generujący PDF z własną ścieżką wyjściową używając nowego systemu layoutowania.
    
    Args:
        sample_docx_path: Fixture zwracająca ścieżkę do pliku Zapytanie_Ofertowe.docx
    """
    # Ścieżka do pliku wejściowego
    input_path = Path(sample_docx_path)
    
    # Ścieżka do pliku wyjściowego w katalogu output
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "Zapytanie_Ofertowe_new_layout_test.pdf"
    
    # 1. Załaduj i parsuj dokument
    package_reader = PackageReader(input_path)
    xml_parser = XMLParser(package_reader)
    body = xml_parser.parse_body()
    
    # 2. Utwórz adapter dla LayoutEngine
    class DocumentAdapter:
        def __init__(self, body_obj):
            self.elements = body_obj.children if hasattr(body_obj, 'children') else []
    
    document_model = DocumentAdapter(body)
    
    # 3. Konfiguracja strony
    page_config = PageConfig(
        page_size=Size(595, 842),  # A4 w punktach
        base_margins=Margins(top=72, bottom=72, left=72, right=72)
    )
    
    # 4. Utwórz pipeline i przetwórz dokument
    pipeline = LayoutPipeline(page_config)
    unified_layout = pipeline.process(
        document_model,
        apply_headers_footers=True,
        validate=False
    )
    
    # 5. Renderuj do PDF
    page_size_tuple = (page_config.page_size.width, page_config.page_size.height)
    margins_tuple = (
        page_config.base_margins.top,
        page_config.base_margins.right,
        page_config.base_margins.bottom,
        page_config.base_margins.left
    )
    
    pdf_renderer = PdfRenderer(
        page_size=page_size_tuple,
        margins=margins_tuple,
        dpi=72.0
    )
    
    pdf_renderer.render(unified_layout.pages, str(output_path))
    
    # Sprawdź wyniki
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    
    print(f"\n✅ PDF wygenerowany pomyślnie: {output_path}")
    print(f"   Rozmiar: {output_path.stat().st_size:,} bajtów")
    print(f"   Stron: {len(unified_layout.pages)}")


if __name__ == "__main__":
    # Uruchom testy bezpośrednio
    pytest.main([__file__, "-v", "-s"])

