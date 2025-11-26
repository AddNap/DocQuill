#!/usr/bin/env python3
"""Benchmark generate_pdf_production.py dla wybranych backendów z rozbiciem czasowym."""

import argparse
import statistics
import subprocess
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def parse_timings(stdout: str) -> dict[str, float]:
    """Wyciągnij linię TIMINGS:... ze stdout i zwróć dict."""
    timings = {}
    for line in stdout.splitlines():
        if line.startswith("TIMINGS:"):
            _, payload = line.split(":", 1)
            for part in payload.split(","):
                if not part:
                    continue
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                try:
                    timings[key.strip()] = float(value)
                except ValueError:
                    continue
        elif line.startswith("RUST_TIMINGS:"):
            # Parse Rust-specific timings
            _, payload = line.split(":", 1)
            for part in payload.split(","):
                if not part:
                    continue
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                try:
                    # Prefix Rust timings with "rust_" to distinguish them
                    timings[f"rust_{key.strip()}"] = float(value)
                except ValueError:
                    continue
        elif line.startswith("RENDER_DETAILS:"):
            # Parse detailed render timings (format: key=total(avg=avg,count=count))
            _, payload = line.split(":", 1)
            for part in payload.split(","):
                if not part:
                    continue
                if "=" not in part:
                    continue
                # Format: key=total(avg=avg,count=count) or key=total
                key_part, value_part = part.split("=", 1)
                key = key_part.strip()
                # Extract total time (before parenthesis if present)
                if "(" in value_part:
                    total_value = value_part.split("(")[0]
                else:
                    total_value = value_part
                try:
                    # Key already includes "render_" prefix, so use as-is
                    timings[key] = float(total_value)
                except ValueError:
                    continue
    return timings

def summarize(name: str, samples: list[float]) -> None:
    print(f"{name:>12}: min={min(samples):.2f}s  max={max(samples):.2f}s  avg={statistics.mean(samples):.2f}s  median={statistics.median(samples):.2f}s")
    if len(samples) > 1:
        print(f"{'':>12}  stdev={statistics.pstdev(samples):.2f}s")

def run_benchmark(backends: list[str], runs: int) -> int:
    script = project_root / "scripts" / "generate_pdf_production.py"
    if not script.exists():
        print(f"❌ Nie znaleziono {script}")
        return 1

    results: dict[str, list[float]] = {b: [] for b in backends}
    stage_results: dict[str, dict[str, list[float]]] = {b: {} for b in backends}

    for backend in backends:
        print(f"\n🚀 Backend: {backend} (runs={runs})")
        for i in range(1, runs + 1):
            cmd = [sys.executable, str(script), "--backend", backend]
            start = time.perf_counter()
            proc = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=600,
            )
            elapsed = time.perf_counter() - start
            if proc.returncode != 0:
                print(f"  Run {i:02d}: ❌ (exit {proc.returncode})")
                print(proc.stderr[:400])
                return proc.returncode
            results[backend].append(elapsed)
            stage_map = parse_timings(proc.stdout)
            for key, value in stage_map.items():
                stage_results[backend].setdefault(key, []).append(value)
            print(f"  Run {i:02d}: ✅ {elapsed:.2f}s")

    print("\n============================================")
    print("📊 PODSUMOWANIE")
    print("============================================\n")
    for backend in backends:
        print(f"Backend {backend}:")
        summarize("Total", results[backend])
        
        # Show first run vs subsequent runs (warmup analysis)
        if len(results[backend]) > 1:
            first_run = results[backend][0]
            subsequent_runs = results[backend][1:]
            avg_subsequent = statistics.mean(subsequent_runs)
            warmup_overhead = first_run - avg_subsequent
            print(f"  Warmup analysis:")
            print(f"    - First run: {first_run:.2f}s")
            print(f"    - Avg subsequent: {avg_subsequent:.2f}s")
            if warmup_overhead > 0:
                print(f"    - Warmup overhead: +{warmup_overhead:.2f}s ({warmup_overhead/avg_subsequent*100:.1f}%)")
            else:
                print(f"    - Warmup overhead: {warmup_overhead:.2f}s")
        
        if stage_results[backend]:
            print("  Rozbicie etapów:")
            # Group timings: regular first (doc_load, layout, render, total), then detailed render, then Rust-specific
            regular_keys = [k for k in sorted(stage_results[backend]) 
                          if not k.startswith("rust_") and not k.startswith("render_")]
            render_detail_keys = [k for k in sorted(stage_results[backend]) 
                                if k.startswith("render_") and k not in ["render"]]
            rust_keys = [k for k in sorted(stage_results[backend]) if k.startswith("rust_")]
            
            for key in regular_keys:
                summarize(f"- {key}", stage_results[backend][key])
            
            if render_detail_keys:
                print("  Szczegółowe czasy renderowania:")
                for key in render_detail_keys:
                    # Remove "render_" prefix for display
                    display_key = key.replace("render_", "")
                    summarize(f"  - {display_key}", stage_results[backend][key])
            
            if rust_keys:
                print("  Szczegółowe czasy Rust:")
                for key in rust_keys:
                    # Remove "rust_" prefix for display
                    display_key = key.replace("rust_", "")
                    summarize(f"  - {display_key}", stage_results[backend][key])
        print()

    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark PDF renderera.")
    parser.add_argument("--runs", type=int, default=20, help="Liczba uruchomień na backend.")
    parser.add_argument(
        "--backend",
        choices=["rust", "reportlab", "both"],
        default="both",
        help="Który backend benchmarkować.",
    )
    args = parser.parse_args()
    backends = ["rust", "reportlab"] if args.backend == "both" else [args.backend]
    sys.exit(run_benchmark(backends, args.runs))
