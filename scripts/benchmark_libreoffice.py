#!/usr/bin/env python3
"""
Benchmark LibreOffice (soffice) DOCX -> PDF conversion.

Runs the command-line converter multiple times and reports timing statistics.
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DOC = PROJECT_ROOT / "tests" / "files" / "Zapytanie_Ofertowe.docx"


def convert_with_soffice(doc_path: Path, output_dir: Path, soffice_path: str) -> float:
    """Convert DOCX to PDF with soffice and return wall-clock duration in seconds."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as tmp_dir:
        t0 = perf_counter()
        result = subprocess.run(
            [
                soffice_path,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp_dir,
                str(doc_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        duration = perf_counter() - t0
        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed (exit={result.returncode}). "
                f"stdout={result.stdout.strip()} stderr={result.stderr.strip()}"
            )
    return duration


def summarize(values: List[float]) -> Dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def print_report(doc_path: Path, times: List[float]) -> None:
    stats = summarize(times)
    print("=" * 80)
    print(f"LibreOffice benchmark: {doc_path}")
    print(f"Iterations: {len(times)}   (times in milliseconds)")
    print("-" * 80)
    print(
        f"Mean: {stats['mean']*1000:8.2f} ms   "
        f"StdDev: {stats['stdev']*1000:8.2f} ms   "
        f"Min: {stats['min']*1000:8.2f} ms   "
        f"Max: {stats['max']*1000:8.2f} ms"
    )
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark LibreOffice DOCX->PDF conversion.")
    parser.add_argument(
        "documents",
        nargs="*",
        type=Path,
        help="DOCX files to convert (default: Zapytanie_Ofertowe.docx)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Measured iterations per document (default: 10)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warm-up runs (not measured) per document (default: 1)",
    )
    parser.add_argument(
        "--soffice",
        type=str,
        default="soffice",
        help="Path to LibreOffice soffice binary (default: soffice on PATH)",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=PROJECT_ROOT / "output" / "benchmark" / "libreoffice",
        help="Working directory for temporary outputs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    docs = args.documents or [DEFAULT_DOC]

    for doc in docs:
        if not doc.exists():
            print(f"❌ Document not found: {doc}")
            continue

        print(
            f"▶ LibreOffice benchmark {doc} "
            f"(warmup={args.warmup}, iterations={args.iterations})"
        )

        for _ in range(max(args.warmup, 0)):
            try:
                convert_with_soffice(doc, args.workdir, args.soffice)
            except Exception as exc:
                print(f"❌ Warm-up failed: {exc}")
                return 1

        measured: List[float] = []
        for _ in range(max(args.iterations, 1)):
            try:
                duration = convert_with_soffice(doc, args.workdir, args.soffice)
                measured.append(duration)
            except Exception as exc:
                print(f"❌ Conversion failed: {exc}")
                return 1

        print_report(doc, measured)

    return 0


if __name__ == "__main__":
    sys.exit(main())

