#!/usr/bin/env python3
"""Benchmark script for WMF/EMF converter performance."""

import sys
import time
import statistics
from pathlib import Path

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docquill.media import MediaConverter


def benchmark_converter(wmf_path: Path, iterations: int = 100):
    """
    Benchmark WMF/EMF converter.
    
    Args:
        wmf_path: Path to WMF/EMF file
        iterations: Number of conversion iterations
    """
    if not wmf_path.exists():
        print(f"❌ Błąd: Plik nie znaleziony: {wmf_path}")
        return
    
    print(f"🚀 Rozpoczynam benchmark konwertera WMF/EMF")
    print(f"📄 Plik: {wmf_path}")
    print(f"🔄 Iteracje: {iterations}")
    print()
    
    # Load WMF file
    print("📥 Ładowanie pliku WMF...")
    wmf_data = wmf_path.read_bytes()
    print(f"✅ Załadowano {len(wmf_data):,} bajtów")
    print()
    
    # Initialize converter
    converter = MediaConverter(enable_cache=False)  # Disable cache for fair benchmark
    
    # Get image dimensions (optional, can be None)
    # For benchmark, we'll use default dimensions
    width_px = None
    height_px = None
    
    # Warm-up conversion (to initialize Java daemon, etc.)
    print("🔥 Rozgrzewka (1 konwersja)...")
    try:
        warmup_result = converter.convert_emf_to_png(wmf_data, width=width_px, height=height_px)
        if warmup_result:
            print(f"✅ Rozgrzewka zakończona, wynik: {len(warmup_result):,} bajtów PNG")
        else:
            print("⚠️  Rozgrzewka nie zwróciła wyniku")
    except Exception as e:
        print(f"❌ Błąd podczas rozgrzewki: {e}")
        return
    print()
    
    # Benchmark conversions with detailed timing
    print(f"⏱️  Rozpoczynam {iterations} iteracji konwersji...")
    times = []
    java_times = []
    python_times = []
    svg_to_png_times = []
    errors = 0
    
    for i in range(iterations):
        try:
            t0 = time.time()
            
            # Try to get detailed timing from converter
            # We'll measure the full conversion time
            result = converter.convert_emf_to_png(wmf_data, width=width_px, height=height_px)
            elapsed = time.time() - t0
            
            if result:
                times.append(elapsed)
                if (i + 1) % 10 == 0:
                    print(f"✅ Iteracja {i+1}/{iterations}: {elapsed:.3f}s, wynik: {len(result):,} bajtów")
            else:
                errors += 1
                print(f"❌ Iteracja {i+1}/{iterations}: Konwersja zwróciła None")
        except Exception as e:
            errors += 1
            print(f"❌ Iteracja {i+1}/{iterations}: Błąd - {e}")
    
    print()
    print("=" * 80)
    print("📊 WYNIKI BENCHMARK KONWERTERA WMF/EMF")
    print("=" * 80)
    print(f"✅ Sukcesy: {len(times)}/{iterations}")
    print(f"❌ Błędy: {errors}/{iterations}")
    print()
    
    if times:
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        median_time = statistics.median(times)
        
        if len(times) > 1:
            stdev_time = statistics.stdev(times)
        else:
            stdev_time = 0.0
        
        print(f"⏱️  CZASY KONWERSJI:")
        print(f"   Średni: {avg_time:.3f}s")
        print(f"   Mediana: {median_time:.3f}s")
        print(f"   Min: {min_time:.3f}s")
        print(f"   Max: {max_time:.3f}s")
        print(f"   Odchylenie std: {stdev_time:.3f}s")
        print()
        
        # Calculate throughput
        conversions_per_second = 1.0 / avg_time if avg_time > 0 else 0
        print(f"📈 PRZEPUSTOWOŚĆ:")
        print(f"   Konwersje/sekundę: {conversions_per_second:.2f}")
        print()
        
        # Show percentiles
        if len(times) >= 10:
            sorted_times = sorted(times)
            p50 = sorted_times[int(len(sorted_times) * 0.50)]
            p90 = sorted_times[int(len(sorted_times) * 0.90)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
            
            print(f"📊 PERCENTYLE:")
            print(f"   P50 (mediana): {p50:.3f}s")
            print(f"   P90: {p90:.3f}s")
            print(f"   P95: {p95:.3f}s")
            print(f"   P99: {p99:.3f}s")
            print()
        
        # Show first few and last few times
        print(f"📋 PRZYKŁADOWE CZASY:")
        print(f"   Pierwsze 5: {[f'{t:.3f}s' for t in times[:5]]}")
        if len(times) > 10:
            print(f"   Ostatnie 5: {[f'{t:.3f}s' for t in times[-5:]]}")
        print()
        
        # Analyze conversion method used
        print(f"🔍 ANALIZA METODY KONWERSJI:")
        print(f"   (Sprawdź logi powyżej, aby zobaczyć używaną metodę)")
        print(f"   - Java converter: Szybszy, wymaga Java")
        print(f"   - Python emf2svg: Wolniejszy, ale nie wymaga Java")
        print(f"   - LibreOffice: Fallback, najwolniejszy")
        print()
        
        # Calculate total time
        total_time = sum(times)
        print(f"⏱️  CAŁKOWITY CZAS:")
        print(f"   Suma wszystkich konwersji: {total_time:.3f}s")
        print(f"   Dla {iterations} obrazów w dokumencie: {total_time * iterations:.3f}s")
    else:
        print("❌ Brak udanych konwersji do analizy")
    
    print("=" * 80)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark WMF/EMF converter")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to WMF/EMF file (if not provided, searches in tests/files)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of conversion iterations (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Find WMF file
    if args.file:
        wmf_path = Path(args.file)
    else:
        # Search in tests/files
        files_dir = project_root / "tests" / "files"
        wmf_files = list(files_dir.glob("*.wmf")) + list(files_dir.glob("*.emf"))
        
        if not wmf_files:
            print(f"❌ Błąd: Nie znaleziono plików WMF/EMF w {files_dir}")
            print(f"   Użyj --file <ścieżka> aby wskazać plik")
            return 1
        
        if len(wmf_files) > 1:
            print(f"⚠️  Znaleziono {len(wmf_files)} plików WMF/EMF, używam pierwszego:")
            for f in wmf_files:
                print(f"   - {f}")
            print()
        
        wmf_path = wmf_files[0]
    
    benchmark_converter(wmf_path, iterations=args.iterations)
    return 0


if __name__ == "__main__":
    sys.exit(main())

