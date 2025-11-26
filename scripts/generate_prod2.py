#!/usr/bin/env python3
"""Skrypt do generowania produkcyjnego PDF z UnifiedLayout używając nowego PDFCompiler."""

import sys
import logging
from pathlib import Path

# Ustaw poziom logowania na INFO, aby zobaczyć logi KROK
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docx_interpreter.parser.package_reader import PackageReader
from docx_interpreter.parser.xml_parser import XMLParser
from docx_interpreter.engine.layout_pipeline import LayoutPipeline
from docx_interpreter.engine.geometry import Size, Margins
from docx_interpreter.engine.page_engine import PageConfig
from docx_interpreter.engine.pdf.pdf_compiler import PDFCompiler


def main():
    """Generuj produkcyjny PDF z pliku Zapytanie_Ofertowe.docx."""
    # Ścieżki
    input_path = project_root / "tests" / "files" / "Document 7.docx"
    output_path = project_root / "output" / "Dok_7_prod.pdf"
    
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
            def __init__(self, body_obj, parser):
                self.elements = body_obj.children if hasattr(body_obj, 'children') else []
                self.parser = parser  # Dodaj parser do parsowania headers/footers
        
        document_model = DocumentAdapter(body, xml_parser)
        print(f"✅ Model przygotowany: {len(document_model.elements)} elementów")
        
        # 3. Konfiguracja strony (A4 w punktach)
        print("🔄 Krok 3: Konfiguracja strony...")
        
        # Pobierz marginesy z DOCX (jeśli są dostępne)
        from docx_interpreter.engine.geometry import twips_to_points
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
            else:
                print("   Używam domyślnych marginesów (nie znaleziono w DOCX)")
        else:
            print("   Używam domyślnych marginesów (nie znaleziono sekcji)")
        
        page_config = PageConfig(
            page_size=Size(595, 842),  # A4 w punktach
            base_margins=margins
        )
        print("✅ Konfiguracja gotowa")
        
        # 4. Utwórz pipeline i przetwórz dokument
        print("🔄 Krok 4: Przetwarzanie layoutu...")
        pipeline = LayoutPipeline(page_config)
        # Przekaż package_reader do assemblera dla footnotes/endnotes
        pipeline.layout_assembler.package_reader = package_reader
        # Re-inicjalizuj footnote_renderer z package_reader
        if hasattr(pipeline.layout_assembler, 'footnote_renderer') and package_reader:
            try:
                from docx_interpreter.parser.notes_parser import NotesParser
                from docx_interpreter.renderers.footnote_renderer import FootnoteRenderer
                notes_parser = NotesParser(package_reader)
                footnotes = notes_parser.get_footnotes() or {}
                endnotes = notes_parser.get_endnotes() or {}
                pipeline.layout_assembler.footnote_renderer = FootnoteRenderer(footnotes, endnotes)
            except Exception:
                pass
        unified_layout = pipeline.process(
            document_model,
            apply_headers_footers=True,
            validate=False  # Nie waliduj, żeby nie przerywać na błędach
        )
        
        print(f"✅ Layout utworzony: {len(unified_layout.pages)} stron, {sum(len(p.blocks) for p in unified_layout.pages)} bloków")
        
        # 5. Renderuj do PDF używając produkcyjnego PDFCompiler
        print("🔄 Krok 5: Renderowanie produkcyjnego PDF...")
        
        # Przygotuj footnote_renderer jeśli dostępny
        footnote_renderer = None
        if hasattr(pipeline.layout_assembler, 'footnote_renderer'):
            footnote_renderer = pipeline.layout_assembler.footnote_renderer
        
        # Utwórz PDFCompiler z package_reader i footnote_renderer
        compiler = PDFCompiler(
            output_path=str(output_path),
            page_size=(595, 842),  # A4 w punktach
            package_reader=package_reader,  # Przekaż package_reader do rozwiązywania ścieżek obrazów
            footnote_renderer=footnote_renderer  # Przekaż footnote_renderer do renderowania odwołań
        )
        
        # Kompiluj UnifiedLayout do PDF
        result_path = compiler.compile(unified_layout)
        
        # Sprawdź wynik
        if result_path.exists():
            file_size = result_path.stat().st_size
            print()
            print(f"✅ Produkcyjny PDF wygenerowany pomyślnie!")
            print(f"   Plik: {result_path}")
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

