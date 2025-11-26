#!/usr/bin/env python3
"""Skrypt do generowania normalnego PDF z UnifiedLayout używając nowego systemu."""

import sys
from pathlib import Path

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docquill.parser.package_reader import PackageReader
from docquill.parser.xml_parser import XMLParser
from docquill.engine.layout_pipeline import LayoutPipeline
from docquill.engine.geometry import Size, Margins
from docquill.engine.page_engine import PageConfig
from docquill.renderers.pdf_renderer import PdfRenderer


def main():
    """Generuj normalny PDF z pliku Zapytanie_Ofertowe.docx."""
    # Ścieżki
    input_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    output_path = project_root / "output" / "Zapytanie_Ofertowe_from_layout.pdf"
    
    # Utwórz katalog wyjściowy jeśli potrzeba
    output_path.parent.mkdir(exist_ok=True)
    
    # Sprawdź czy plik wejściowy istnieje
    if not input_path.exists():
        print(f"❌ Błąd: Plik wejściowy nie znaleziony: {input_path}")
        sys.exit(1)
    
    print(f"📄 Plik wejściowy: {input_path}")
    print(f"📄 Plik wyjściowy: {output_path}")
    print()
    
    try:
        # 1. Załaduj i parsuj dokument
        print("🔄 Krok 1: Ładowanie dokumentu...")
        package_reader = PackageReader(input_path)
        xml_parser = XMLParser(package_reader)
        body = xml_parser.parse_body()
        print(f"✅ Dokument sparsowany: {len(body.children)} elementów")
        
        # 2. Utwórz adapter dla LayoutEngine
        print("🔄 Krok 2: Przygotowanie modelu...")
        class DocumentAdapter:
            def __init__(self, body_obj):
                self.elements = body_obj.children if hasattr(body_obj, 'children') else []
        
        document_model = DocumentAdapter(body)
        print(f"✅ Model przygotowany: {len(document_model.elements)} elementów")
        
        # 3. Konfiguracja strony (A4 w punktach)
        print("🔄 Krok 3: Konfiguracja strony...")
        page_config = PageConfig(
            page_size=Size(595, 842),  # A4 w punktach
            base_margins=Margins(top=72, bottom=72, left=72, right=72)
        )
        print("✅ Konfiguracja gotowa")
        
        # 4. Utwórz pipeline i przetwórz dokument
        print("🔄 Krok 4: Przetwarzanie layoutu...")
        pipeline = LayoutPipeline(page_config)
        unified_layout = pipeline.process(
            document_model,
            apply_headers_footers=True,
            validate=False  # Nie waliduj, żeby nie przerywać na błędach
        )
        
        print(f"✅ Layout utworzony: {len(unified_layout.pages)} stron, {sum(len(p.blocks) for p in unified_layout.pages)} bloków")
        
        # 5. Renderuj do PDF używając PdfRenderer
        print("🔄 Krok 5: Renderowanie PDF...")
        
        # PdfRenderer potrzebuje page_size i margins jako tuple/list
        page_size_tuple = (page_config.page_size.width, page_config.page_size.height)
        margins_tuple = (
            page_config.base_margins.top,
            page_config.base_margins.right,
            page_config.base_margins.bottom,
            page_config.base_margins.left
        )
        
        # Utwórz renderer
        pdf_renderer = PdfRenderer(
            page_size=page_size_tuple,
            margins=margins_tuple,
            dpi=72.0
        )
        
        # Renderuj strony z UnifiedLayout
        pdf_renderer.render(unified_layout.pages, str(output_path))
        
        # Sprawdź wynik
        if output_path.exists():
            file_size = output_path.stat().st_size
            print()
            print(f"✅ PDF wygenerowany pomyślnie!")
            print(f"   Plik: {output_path}")
            print(f"   Rozmiar: {file_size:,} bajtów")
            print(f"   Stron: {len(unified_layout.pages)}")
            print()
            print(f"📊 Podsumowanie:")
            print(f"   - Stron: {len(unified_layout.pages)}")
            print(f"   - Bloków: {sum(len(p.blocks) for p in unified_layout.pages)}")
            return 0
        else:
            print(f"❌ Błąd: Plik nie został utworzony")
            return 1
            
    except Exception as e:
        print(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
