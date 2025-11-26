#!/usr/bin/env python3
"""Skrypt testowy do wizualizacji layoutu z debug_compiler."""

import sys
import logging
from pathlib import Path

# Konfiguruj logowanie
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

# Dodaj ścieżkę do modułów
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Importy z parsera i engine
from docquill.parser.package_reader import PackageReader
from docquill.parser.xml_parser import XMLParser
from docquill.engine.layout_pipeline import LayoutPipeline
from docquill.engine.geometry import Size, Margins
from docquill.engine.page_engine import PageConfig
from docquill.engine.pdfcompiler.debug_compiler import DebugPDFCompiler


def main():
    """Generuj debug PDF z layoutu dla Zapytanie_Ofertowe."""
    # Ścieżki
    input_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    output_path = project_root / "output" / "test_debug_layout.pdf"
    
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
        # Załaduj dokument przez parser
        print("🔄 Ładowanie dokumentu...")
        package_reader = PackageReader(input_path)
        xml_parser = XMLParser(package_reader)
        
        print("🔄 Parsowanie dokumentu...")
        body = xml_parser.parse_body()
        print(f"✅ Dokument sparsowany")
        
        # Utwórz adapter dla LayoutEngine (oczekuje model z atrybutem "elements" i "parser")
        class DocumentAdapter:
            def __init__(self, body_obj, parser):
                # Pobierz elementy z body
                if hasattr(body_obj, 'children'):
                    self.elements = body_obj.children
                elif hasattr(body_obj, 'content_order'):
                    self.elements = body_obj.content_order
                else:
                    self.elements = []
                # Dodaj parser, żeby LayoutEngine mógł parsować nagłówki i stopki
                self.parser = parser
        
        document_model = DocumentAdapter(body, xml_parser)
        print(f"✅ Przygotowano {len(document_model.elements)} elementów do layoutowania")
        
        # Konfiguracja strony (A4 w punktach)
        # Pobierz marginesy z DOCX (jeśli są dostępne)
        from docquill.engine.geometry import twips_to_points
        sections = xml_parser.parse_sections()
        margins = Margins(top=72, bottom=72, left=72, right=72)  # Domyślne marginesy (1 cal = 72 punkty)
        
        if sections and len(sections) > 0:
            section = sections[0]  # Użyj pierwszej sekcji
            if 'margins' in section:
                docx_margins = section['margins']
                # Konwertuj marginesy z twips na punkty
                # Marginesy mogą być int lub string, więc konwertuj na int
                def get_margin_twips(key, default=1440):
                    val = docx_margins.get(key, default)
                    if isinstance(val, str):
                        try:
                            return int(val)
                        except (ValueError, TypeError):
                            return default
                    return int(val) if val is not None else default
                
                margins = Margins(
                    top=twips_to_points(get_margin_twips('top', 1440)),  # 1440 twips = 72 punkty (domyślnie)
                    bottom=twips_to_points(get_margin_twips('bottom', 1440)),
                    left=twips_to_points(get_margin_twips('left', 1440)),
                    right=twips_to_points(get_margin_twips('right', 1440))
                )
                print(f"   Marginesy z DOCX: top={margins.top:.1f}, bottom={margins.bottom:.1f}, left={margins.left:.1f}, right={margins.right:.1f} pt")
        
        page_config = PageConfig(
            page_size=Size(595, 842),  # A4 w punktach
            base_margins=margins
        )
        
        # Utwórz pipeline
        print("🔄 Tworzenie layout pipeline...")
        pipeline = LayoutPipeline(page_config)
        
        # Przetwórz dokument
        print("🔄 Przetwarzanie layoutu...")
        unified_layout, summary = pipeline.process_with_summary(document_model, apply_headers_footers=True)
        
        print(f"✅ Layout utworzony:")
        print(f"   - Stron: {summary['total_pages']}")
        print(f"   - Bloków: {summary['total_blocks']}")
        print(f"   - Błędów: {summary['total_errors']}")
        print(f"   - Ostrzeżeń: {summary['total_warnings']}")
        
        if summary['total_errors'] > 0:
            print()
            print("⚠️  Błędy walidacji:")
            for error in summary['errors'][:5]:  # Pokaż pierwsze 5
                print(f"   - {error}")
            if len(summary['errors']) > 5:
                print(f"   ... i {len(summary['errors']) - 5} więcej")
        
        if summary['total_warnings'] > 0:
            print()
            print("⚠️  Ostrzeżenia:")
            for warning in summary['warnings'][:5]:  # Pokaż pierwsze 5
                print(f"   - {warning}")
            if len(summary['warnings']) > 5:
                print(f"   ... i {len(summary['warnings']) - 5} więcej")
        
        # Generuj debug PDF
        print()
        print("🔄 Generowanie debug PDF...")
        debug_compiler = DebugPDFCompiler(
            str(output_path),
            package_reader=package_reader  # Przekaż package_reader do rozwiązywania ścieżek obrazów
        )
        debug_compiler.compile(unified_layout)
        
        # Sprawdź wynik
        if output_path.exists():
            file_size = output_path.stat().st_size
            print()
            print(f"✅ Debug PDF wygenerowany pomyślnie!")
            print(f"   Plik: {output_path}")
            print(f"   Rozmiar: {file_size:,} bajtów")
            print()
            print(f"📊 Podsumowanie layoutu:")
            print(f"   - Stron: {summary['total_pages']}")
            print(f"   - Bloków: {summary['total_blocks']}")
            print(f"   - Walidacja: {'✅ OK' if summary['is_valid'] else '❌ Błędy'}")
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

