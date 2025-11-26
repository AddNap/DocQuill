#!/usr/bin/env python3
"""
Benchmark the DocQuill pipeline step-by-step.

Measures wall-clock time for the major stages:
  - DOCX package loading
  - XML parsing (body + sections)
  - LayoutEngine build (logical structure)
  - LayoutAssembler assemble (geometry + pagination-ready layout)
  - PaginationManager headers/footers application
  - PDFCompiler compilation

Results are reported per document with aggregates across iterations.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional

# Ensure project modules resolve correctly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from docquill.parser.package_reader import PackageReader
from docquill.parser.xml_parser import XMLParser
from docquill.engine.layout_pipeline import LayoutPipeline
from docquill.engine.geometry import Margins, Size, twips_to_points
from docquill.engine.page_engine import PageConfig
from docquill.engine.pagination_manager import PaginationManager
from docquill.engine.page_variator import PageVariator
from docquill.engine.pdf.pdf_compiler import PDFCompiler


DEFAULT_DOC = PROJECT_ROOT / "tests" / "files" / "Zapytanie_Ofertowe.docx"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "benchmark"


@dataclass(slots=True)
class BenchmarkIteration:
    step_times: Dict[str, float]
    total_time: float


def _resolve_margins(sections: Optional[List[dict]]) -> Margins:
    """Resolve page margins (points) from DOCX section data."""
    if not sections:
        return Margins(top=72, bottom=72, left=72, right=72)

    margins_data = sections[0].get("margins", {}) if isinstance(sections[0], dict) else {}

    def _twips(key: str, default: int = 1440) -> int:
        value = margins_data.get(key, default)
        if isinstance(value, str):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        if value is None:
            return default
        return int(value)

    return Margins(
        top=twips_to_points(_twips("top")),
        bottom=twips_to_points(_twips("bottom")),
        left=twips_to_points(_twips("left")),
        right=twips_to_points(_twips("right")),
    )


class DocumentAdapter:
    """Minimal adapter expected by LayoutEngine & LayoutAssembler."""

    def __init__(self, body, parser: XMLParser):
        self.elements = body.children if hasattr(body, "children") else []
        self.parser = parser


def run_iteration(doc_path: Path, output_dir: Path, parallelism: int) -> BenchmarkIteration:
    """Run a single benchmark iteration and return timing data per step."""
    step_times: Dict[str, float] = {}
    iteration_start = perf_counter()

    # Package loading
    t0 = perf_counter()
    package_reader = PackageReader(str(doc_path))
    step_times["package_reader_init"] = perf_counter() - t0

    xml_parser = XMLParser(package_reader)

    # Body parsing
    t0 = perf_counter()
    body = xml_parser.parse_body()
    step_times["parse_body"] = perf_counter() - t0

    # Sections parsing (margins, header/footer distances)
    t0 = perf_counter()
    sections = xml_parser.parse_sections()
    step_times["parse_sections"] = perf_counter() - t0

    document_model = DocumentAdapter(body, xml_parser)

    # Page configuration
    margins = _resolve_margins(sections)
    page_config = PageConfig(page_size=Size(595, 842), base_margins=margins)
    pipeline = LayoutPipeline(page_config)

    # LayoutEngine build
    t0 = perf_counter()
    layout_structure = pipeline.layout_engine.build(document_model)
    step_times["layout_engine_build"] = perf_counter() - t0

    header_dist, footer_dist = pipeline._extract_header_footer_distances(document_model)  # type: ignore[attr-defined]
    page_variator = PageVariator(
        layout_structure,
        pipeline.layout_assembler,
        page_config,
        header_distance=header_dist,
        footer_distance=footer_dist,
    )
    pipeline.layout_assembler.set_page_variator(page_variator)

    # LayoutAssembler assemble
    t0 = perf_counter()
    unified_layout = pipeline.layout_assembler.assemble(layout_structure)
    step_times["layout_assembler_assemble"] = perf_counter() - t0

    # Pagination application
    t0 = perf_counter()
    pagination_manager = PaginationManager(
        unified_layout,
        layout_assembler=pipeline.layout_assembler,
        page_variator=page_variator,
    )
    pagination_manager.apply_headers_footers(layout_structure)
    step_times["pagination_apply"] = perf_counter() - t0

    # PDF compilation (write to a temporary file inside output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output_dir,
        suffix=".pdf",
        delete=False,
    ) as tmp_file:
        temp_pdf_path = Path(tmp_file.name)

    try:
        t0 = perf_counter()
        compiler = PDFCompiler(
            output_path=temp_pdf_path,
            page_size=(page_config.page_size.width, page_config.page_size.height),
            package_reader=package_reader,
            parallelism=parallelism,
        )
        compiler.compile(unified_layout)
        step_times["pdf_compile"] = perf_counter() - t0
    finally:
        temp_pdf_path.unlink(missing_ok=True)

    total_time = perf_counter() - iteration_start
    return BenchmarkIteration(step_times=step_times, total_time=total_time)


def summarize_iterations(iterations: List[BenchmarkIteration]) -> Dict[str, Dict[str, float]]:
    """Aggregate iteration results step-by-step (mean/min/max/std)."""
    if not iterations:
        return {}

    step_names = iterations[0].step_times.keys()
    summary: Dict[str, Dict[str, float]] = {}

    for step in step_names:
        values = [it.step_times[step] for it in iterations]
        summary[step] = {
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }

    totals = [it.total_time for it in iterations]
    summary["total"] = {
        "mean": statistics.mean(totals),
        "min": min(totals),
        "max": max(totals),
        "stdev": statistics.stdev(totals) if len(totals) > 1 else 0.0,
    }
    return summary


def print_report(doc_path: Path, iterations: List[BenchmarkIteration]) -> None:
    """Pretty-print benchmark results for a document."""
    summary = summarize_iterations(iterations)
    if not summary:
        print(f"No iterations collected for {doc_path}")
        return

    print("=" * 80)
    print(f"Benchmark results for: {doc_path}")
    print(f"Iterations: {len(iterations)} (mean ± stdev, min … max)  [times in milliseconds]")
    print("-" * 80)

    header = f"{'Step':35} {'Mean':>12} {'StdDev':>12} {'Min':>12} {'Max':>12}"
    print(header)
    print("-" * len(header))

    for step, stats in summary.items():
        mean_ms = stats["mean"] * 1000
        std_ms = stats["stdev"] * 1000
        min_ms = stats["min"] * 1000
        max_ms = stats["max"] * 1000
        print(
            f"{step:35} {mean_ms:12.2f} {std_ms:12.2f} {min_ms:12.2f} {max_ms:12.2f}"
        )

    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark DocQuill pipeline steps.")
    parser.add_argument(
        "documents",
        nargs="*",
        type=Path,
        help="DOCX files to benchmark (default: Zapytanie_Ofertowe.docx).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of measured iterations per document (default: 3).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warm-up iterations (not measured) per document (default: 1).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for temporary benchmark artifacts (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        default=1,
        help="Number of processes for PDF rendering (default: 1 = sequential).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    documents = args.documents or [DEFAULT_DOC]

    for doc in documents:
        if not doc.exists():
            print(f"❌ Document not found: {doc}")
            continue

        print(
            f"▶ Benchmarking {doc} "
            f"(warmup={args.warmup}, iterations={args.iterations}, parallelism={args.parallelism})"
        )

        # Warm-up
        for _ in range(max(args.warmup, 0)):
            run_iteration(doc, args.output_dir, args.parallelism)

        measured_iterations: List[BenchmarkIteration] = []
        for _ in range(max(args.iterations, 1)):
            measured_iterations.append(run_iteration(doc, args.output_dir, args.parallelism))

        print_report(doc, measured_iterations)

    return 0


if __name__ == "__main__":
    sys.exit(main())

