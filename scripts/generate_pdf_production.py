#!/usr/bin/env python3
"""Skrypt do generowania produkcyjnego PDF z UnifiedLayout używając nowego PDFCompiler."""

import sys
import logging
import argparse
import time
import io
import contextlib
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
    parser = argparse.ArgumentParser(description="Generuj produkcyjny PDF z wykorzystaniem rustowego renderera.")
    parser.add_argument(
        "--watermark-opacity",
        type=float,
        default=None,
        help="Wymuś globalny poziom krycia dla wszystkich watermarków (0.0-1.0).",
    )
    parser.add_argument(
        "--backend",
        choices=["rust", "reportlab"],
        default="rust",
        help="Wybierz silnik renderujący (domyślnie rust).",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Włącz profilowanie (cProfile) - pokaże top funkcje zajmujące najwięcej czasu.",
    )
    parser.add_argument(
        "--profile-output",
        type=str,
        default=None,
        help="Zapisz profil do pliku (domyślnie: profile_stats.prof).",
    )
    parser.add_argument(
        "--profile-lines",
        type=int,
        default=30,
        help="Liczba top funkcji do wyświetlenia (domyślnie 30).",
    )
    args = parser.parse_args()
    # Ścieżki
    input_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    output_path = project_root / "output" / "Zapytanie_Ofertowe_production.pdf"
    
    # Utwórz katalog wyjściowy jeśli potrzeba
    output_path.parent.mkdir(exist_ok=True)
    
    # Sprawdź czy plik wejściowy istnieje
    if not input_path.exists():
        print(f"❌ Błąd: Plik wejściowy nie znaleziony: {input_path}")
        sys.exit(1)
    
    print(f"📄 Plik wejściowy: {input_path}")
    print(f"📄 Plik wyjściowy: {output_path}")
    print()
    
    timings: dict[str, float] = {}
    total_start = time.perf_counter()

    try:
        # 1. Załaduj i parsuj dokument
        print("🔄 Krok 1: Ładowanie dokumentu...")
        t0 = time.perf_counter()
        package_reader = PackageReader(input_path)
        xml_parser = XMLParser(package_reader)
        timings["doc_load"] = time.perf_counter() - t0
        
        # 2. Konfiguracja strony (A4 w punktach) - PRZED utworzeniem pipeline
        print("🔄 Krok 2: Konfiguracja strony...")
        
        # Pobierz marginesy z DOCX (jeśli są dostępne)
        from docx_interpreter.engine.geometry import twips_to_points
        t0 = time.perf_counter()
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
        
        
        # Utwórz pipeline z właściwą konfiguracją strony
        pipeline = LayoutPipeline(page_config)
        
        # Przekaż image_cache do parsera
        xml_parser.image_cache = pipeline.image_cache
        
        body = xml_parser.parse_body()
        timings["doc_load"] += time.perf_counter() - t0
        print(f"✅ Dokument sparsowany: {len(body.children)} elementów")
        
        # Prekonwertuj obrazy WMF/EMF asynchronicznie
        from docx_interpreter.parser.image_preconverter import preconvert_images_from_model
        from docx_interpreter.media import MediaConverter
        media_converter = MediaConverter()
        t0 = time.perf_counter()
        preconvert_images_from_model(body, package_reader, pipeline.image_cache, media_converter)
        
        # Prekonwertuj obrazy z headerów i footerów (jeśli istnieją)
        if hasattr(xml_parser, 'parse_header'):
            header_body = xml_parser.parse_header()
            if header_body:
                preconvert_images_from_model(header_body, package_reader, pipeline.image_cache, media_converter)
        
        if hasattr(xml_parser, 'parse_footer'):
            footer_body = xml_parser.parse_footer()
            if footer_body:
                preconvert_images_from_model(footer_body, package_reader, pipeline.image_cache, media_converter)
        timings["preconvert"] = time.perf_counter() - t0
        
        print("✅ Prekonwersja obrazów WMF/EMF uruchomiona asynchronicznie")
        
        # 3. Utwórz adapter dla LayoutEngine
        print("🔄 Krok 3: Przygotowanie modelu...")
        class DocumentAdapter:
            def __init__(self, body_obj, parser):
                self.elements = body_obj.children if hasattr(body_obj, 'children') else []
                self.parser = parser  # Dodaj parser do parsowania headers/footers
        
        document_model = DocumentAdapter(body, xml_parser)
        print(f"✅ Model przygotowany: {len(document_model.elements)} elementów")
        
        # 4. Przetwórz dokument
        print("🔄 Krok 4: Przetwarzanie layoutu...")
        # Pipeline już utworzony wcześniej, użyj tego samego
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
        t0 = time.perf_counter()
        unified_layout = pipeline.process(
            document_model,
            apply_headers_footers=True,
            validate=False  # Nie waliduj, żeby nie przerywać na błędach
        )
        timings["layout"] = time.perf_counter() - t0
        
        # Poczekaj na zakończenie konwersji obrazów przed renderowaniem
        print("🔄 Oczekiwanie na zakończenie konwersji obrazów...")
        t0 = time.perf_counter()
        pipeline.image_cache.wait_for_all(timeout=60.0)
        timings["image_wait"] = time.perf_counter() - t0
        print("✅ Konwersja obrazów zakończona")
        
        print(f"✅ Layout utworzony: {len(unified_layout.pages)} stron, {sum(len(p.blocks) for p in unified_layout.pages)} bloków")
        
        # 5. Renderuj do PDF używając produkcyjnego PDFCompiler
        print("🔄 Krok 5: Renderowanie produkcyjnego PDF...")
        
        # Przygotuj footnote_renderer jeśli dostępny
        footnote_renderer = None
        if hasattr(pipeline.layout_assembler, 'footnote_renderer'):
            footnote_renderer = pipeline.layout_assembler.footnote_renderer
        
        # Utwórz PDFCompiler z package_reader i footnote_renderer
        # Użyj Rust renderera z wielowątkowością
        use_rust_backend = args.backend == "rust"
        print(f"   Backend: {'Rust' if use_rust_backend else 'ReportLab'}")

        t0 = time.perf_counter()
        compiler = PDFCompiler(
            output_path=str(output_path),
            page_size=(595, 842),  # A4 w punktach
            package_reader=package_reader,  # Przekaż package_reader do rozwiązywania ścieżek obrazów
            footnote_renderer=footnote_renderer,  # Przekaż footnote_renderer do renderowania odwołań
            use_rust=use_rust_backend,  # Użyj wybranego renderera
            parallelism=1,  # Wyłączone - sequential rendering jest szybszy (brak overhead thread synchronization)
            watermark_opacity=args.watermark_opacity,
        )
        
        # Utwórz słownik dla szczegółowych czasów renderowania (Dict[str, List[float]])
        render_timings: dict[str, list[float]] = {}
        
        # Kompiluj UnifiedLayout do PDF z przekazaniem render_timings
        result_path = compiler.compile(unified_layout, timings=render_timings)
        timings["render"] = time.perf_counter() - t0
        
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
            total_time = time.perf_counter() - total_start
            timings["total"] = total_time
            print("\n⏱️ Timingi (s):")
            for key in ("doc_load", "preconvert", "layout", "image_wait", "render", "total"):
                if key in timings:
                    print(f"   {key:11s}: {timings[key]:.3f}")
            timings_line = ",".join(f"{k}={timings[k]:.6f}" for k in sorted(timings))
            print(f"TIMINGS:{timings_line}")
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
    # Check if profiling is requested
    if "--profile" in sys.argv:
        import cProfile
        import pstats
        import io
        
        # Parse args to get profile settings
        parser = argparse.ArgumentParser()
        parser.add_argument("--profile", action="store_true")
        parser.add_argument("--profile-output", type=str, default="profile_stats.prof")
        parser.add_argument("--profile-lines", type=int, default=50)
        parser.add_argument("--watermark-opacity", type=float, default=None)
        parser.add_argument("--backend", choices=["rust", "reportlab"], default="rust")
        profile_args = parser.parse_args()
        
        # Create profiler
        profiler = cProfile.Profile()
        
        # Run main with profiling
        profiler.enable()
        try:
            exit_code = main()
        finally:
            profiler.disable()
        
        # Save profile
        profile_output = profile_args.profile_output or "profile_stats.prof"
        profiler.dump_stats(profile_output)
        
        # Print statistics
        print("\n" + "="*80)
        print("📊 PROFILOWANIE - TOP FUNKCJE (by cumulative time)")
        print("="*80)
        
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        
        # Create string buffer for output and redirect stdout
        stats_stream = io.StringIO()
        with contextlib.redirect_stdout(stats_stream):
            stats.print_stats(profile_args.profile_lines)
        stats_output = stats_stream.getvalue()
        
        # Print to console
        print(stats_output)
        
        # Also print by total time (time spent in function itself)
        print("\n" + "="*80)
        print("📊 TOP FUNKCJE (by total time - time in function itself)")
        print("="*80)
        stats.sort_stats('tottime')
        stats_stream2 = io.StringIO()
        with contextlib.redirect_stdout(stats_stream2):
            stats.print_stats(profile_args.profile_lines)
        print(stats_stream2.getvalue())
        
        # Print Rust-specific functions if available
        print("\n" + "="*80)
        print("📊 TOP FUNKCJE RUST (filtrowane)")
        print("="*80)
        stats.sort_stats('tottime')
        stats_stream3 = io.StringIO()
        # Filter to show only Rust-related functions
        with contextlib.redirect_stdout(stats_stream3):
            stats.print_stats('rust', profile_args.profile_lines)
        rust_output = stats_stream3.getvalue()
        if rust_output.strip():
            print(rust_output)
        else:
            print("   (Brak funkcji zawierających 'rust' w nazwie)")
        
        print(f"\n💾 Profil zapisany do: {profile_output}")
        print("   Możesz przeanalizować go używając: python -m pstats", profile_output)
        print("   Lub: snakeviz", profile_output, "(jeśli zainstalowane)")
        
        sys.exit(exit_code)
    else:
        sys.exit(main())

