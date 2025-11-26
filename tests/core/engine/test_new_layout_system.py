"""
Testy dla nowego systemu layoutowania (LayoutPipeline + UnifiedLayout).

Testuje pełny pipeline:
- LayoutEngine → LayoutStructure
- LayoutAssembler → UnifiedLayout
- DebugPDFCompiler → PDF
"""

import sys
from pathlib import Path

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docquill.parser.package_reader import PackageReader
from docquill.parser.xml_parser import XMLParser
from docquill.engine.layout_pipeline import LayoutPipeline
from docquill.engine.geometry import Size, Margins
from docquill.engine.page_engine import PageConfig
from docquill.engine.pdfcompiler.debug_compiler import DebugPDFCompiler


def test_zapytanie_ofertowe():
    """Test layoutowania pliku Zapytanie_Ofertowe.docx."""
    # Ścieżki
    input_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    output_path = project_root / "output" / "test_new_layout_debug.pdf"
    
    # Sprawdź czy plik istnieje
    if not input_path.exists():
        print(f"⚠️  Plik testowy nie znaleziony: {input_path}")
        print("   Pomijam test.")
        return
    
    print(f"📄 Test: Zapytanie_Ofertowe.docx")
    print(f"📄 Output: {output_path}")
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
        
        # 3. Konfiguracja strony
        print("🔄 Krok 3: Konfiguracja strony...")
        page_config = PageConfig(
            page_size=Size(595, 842),  # A4 w punktach
            base_margins=Margins(top=72, bottom=72, left=72, right=72)
        )
        print("✅ Konfiguracja gotowa")
        
        # 4. Utwórz pipeline
        print("🔄 Krok 4: Tworzenie layout pipeline...")
        pipeline = LayoutPipeline(page_config)
        print("✅ Pipeline utworzony")
        
        # 5. Przetwórz dokument
        print("🔄 Krok 5: Przetwarzanie layoutu...")
        unified_layout, summary = pipeline.process_with_summary(
            document_model,
            apply_headers_footers=True
        )
        
        print(f"✅ Layout utworzony:")
        print(f"   - Stron: {summary['total_pages']}")
        print(f"   - Bloków: {summary['total_blocks']}")
        print(f"   - Błędów: {summary['total_errors']}")
        print(f"   - Ostrzeżeń: {summary['total_warnings']}")
        
        if summary['total_errors'] > 0:
            print()
            print("⚠️  Błędy walidacji:")
            for error in summary['errors'][:3]:
                print(f"   - {error}")
        
        # 6. Generuj debug PDF
        print()
        print("🔄 Krok 6: Generowanie debug PDF...")
        output_path.parent.mkdir(exist_ok=True)
        debug_compiler = DebugPDFCompiler(str(output_path))
        debug_compiler.compile(unified_layout)
        
        if output_path.exists():
            file_size = output_path.stat().st_size
            print()
            print(f"✅ Test zakończony sukcesem!")
            print(f"   Plik: {output_path}")
            print(f"   Rozmiar: {file_size:,} bajtów")
            print(f"   Stron: {summary['total_pages']}")
            print(f"   Bloków: {summary['total_blocks']}")
            return True
        else:
            print("❌ Błąd: Plik PDF nie został utworzony")
            return False
            
    except Exception as e:
        print(f"❌ Błąd podczas testu: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_zapytanie_ofertowe()
    sys.exit(0 if success else 1)

