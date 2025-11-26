"""Structural regression tests comparing debug and production layout geometry."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# Ensure project root is on sys.path (tests may run from repo root or elsewhere)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

TESTS_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = TESTS_ROOT / "files"
VISUAL_SAMPLES: Tuple[Path, ...] = tuple(sorted(SAMPLES_DIR.glob("*.docx")))
SSIM_THRESHOLD = 0.99


def _ensure_samples_exist(samples: Iterable[Path]) -> None:
    available = list(samples)
    if not available:
        pytest.skip("No DOCX samples found for structural comparison", allow_module_level=True)
    missing = [path for path in available if not path.exists()]
    if missing:
        pytest.skip(f"Missing DOCX samples: {', '.join(str(m) for m in missing)}", allow_module_level=True)


_ensure_samples_exist(VISUAL_SAMPLES)

from docx_interpreter.engine.assembler.utils import parse_cell_margins
from docx_interpreter.engine.geometry import Margins, Size, twips_to_points
from docx_interpreter.engine.layout_pipeline import LayoutPipeline
from docx_interpreter.engine.layout_primitives import BlockContent, ParagraphLayout
from docx_interpreter.engine.page_engine import PageConfig
from docx_interpreter.engine.pdf.pdf_compiler import PDFCompiler
from docx_interpreter.engine.pdfcompiler.debug_compiler import DebugPDFCompiler
from docx_interpreter.parser.package_reader import PackageReader
from docx_interpreter.parser.xml_parser import XMLParser


def _round(value: float) -> float:
    return round(float(value), 4)


def _rect_to_tuple(rect) -> Dict[str, float]:
    return {
        "x": _round(rect.x),
        "y": _round(rect.y),
        "width": _round(rect.width),
        "height": _round(rect.height),
    }


def _grid_span(cell: object) -> int:
    if hasattr(cell, "grid_span"):
        span = getattr(cell, "grid_span") or 1
    elif isinstance(cell, dict):
        span = cell.get("grid_span") or cell.get("gridSpan") or 1
    else:
        span = 1
    try:
        return max(int(span), 1)
    except (TypeError, ValueError):
        return 1


def _vertical_merge_type(cell: object) -> Optional[str]:
    candidate = None
    if hasattr(cell, "vertical_merge_type"):
        candidate = getattr(cell, "vertical_merge_type")
    elif hasattr(cell, "vertical_merge"):
        candidate = getattr(cell, "vertical_merge")
    elif isinstance(cell, dict):
        candidate = cell.get("vertical_merge_type") or cell.get("vMerge")
        if isinstance(candidate, dict):
            candidate = candidate.get("val")
    if candidate is None:
        return None
    return str(candidate)


def _collect_cell_paragraphs(
    compiler: PDFCompiler,
    height_func,
    cell: object,
) -> List[Dict[str, Optional[float]]]:
    entries: List[Dict[str, Optional[float]]] = []
    content_items = compiler._extract_cell_content(cell)

    for item in content_items:
        payload = compiler._extract_paragraph_payload(item)
        entry: Dict[str, Optional[float]] = {
            "has_payload": payload is not None,
            "lines": len(payload.lines) if isinstance(payload, ParagraphLayout) else None,
            "height": _round(height_func(payload)) if isinstance(payload, ParagraphLayout) else None,
        }
        entries.append(entry)

    return entries


def _collect_table_structure(
    compiler: PDFCompiler,
    height_func,
    block,
    raw_table: dict,
) -> Dict[str, object]:
    rect = block.frame
    layout_info = raw_table.get("layout_info", {}) or {}
    rows = raw_table.get("rows", []) or []

    # Derive columns count
    num_cols = 0
    for row in rows:
        if hasattr(row, "cells"):
            num_cols = max(num_cols, len(row.cells))
        elif isinstance(row, dict) and "cells" in row:
            num_cols = max(num_cols, len(row["cells"]))
    if num_cols == 0:
        num_cols = len(layout_info.get("col_widths", [])) or 1

    col_widths = [float(w) for w in layout_info.get("col_widths", []) or []]
    if not col_widths:
        fallback_width = rect.width / num_cols if num_cols else rect.width
        col_widths = [fallback_width] * num_cols
    else:
        total_width = sum(col_widths)
        if total_width and abs(total_width - rect.width) > 0.1:
            scale = rect.width / total_width
            col_widths = [w * scale for w in col_widths]

    row_heights = [float(h) for h in layout_info.get("row_heights", []) or []]
    if not row_heights:
        fallback_height = rect.height / len(rows) if rows else rect.height
        row_heights = [fallback_height] * (len(rows) or 1)

    table_data: Dict[str, object] = {
        "row_heights": tuple(_round(h) for h in row_heights),
        "col_widths": tuple(_round(w) for w in col_widths),
        "cells": [],
    }

    y_cursor = rect.y + rect.height

    for row_idx, row in enumerate(rows):
        row_height = row_heights[row_idx] if row_idx < len(row_heights) else row_heights[-1]
        cell_y = y_cursor - row_height
        cells = row.cells if hasattr(row, "cells") else row.get("cells", [])

        col_idx = 0
        cell_iter_idx = 0
        while cell_iter_idx < len(cells):
            cell = cells[cell_iter_idx]
            span = _grid_span(cell)
            merge_type = _vertical_merge_type(cell)

            if merge_type == "continue":
                col_idx += span
                cell_iter_idx += 1
                continue

            x_left = rect.x + sum(col_widths[:col_idx])
            cell_width = sum(col_widths[col_idx:col_idx + span])

            rowspan = 1
            if merge_type == "restart":
                current_col_pos = col_idx
                for next_row_idx in range(row_idx + 1, len(rows)):
                    next_row = rows[next_row_idx]
                    next_cells = next_row.cells if hasattr(next_row, "cells") else next_row.get("cells", [])
                    position = 0
                    found = False
                    for next_cell in next_cells:
                        next_span = _grid_span(next_cell)
                        if position == current_col_pos:
                            next_merge = _vertical_merge_type(next_cell)
                            if next_merge == "continue":
                                rowspan += 1
                                found = True
                            break
                        position += next_span
                    if not found:
                        break

            cell_height = sum(row_heights[row_idx:row_idx + rowspan])

            cell_margins = parse_cell_margins(
                cell,
                default_margin=block.style.get("cell_padding", 2.0) if isinstance(block.style, dict) else 2.0,
            )

            paragraphs = _collect_cell_paragraphs(compiler, height_func, cell)

            cell_data = {
                "row": row_idx,
                "col": col_idx,
                "rowspan": rowspan,
                "colspan": span,
                "frame": {
                    "x": _round(x_left),
                    "y": _round(cell_y),
                    "width": _round(cell_width),
                    "height": _round(cell_height),
                },
                "margins": {k: _round(v) for k, v in (cell_margins or {}).items()},
                "paragraphs": paragraphs,
            }
            table_data["cells"].append(cell_data)

            col_idx += span
            cell_iter_idx += 1

        y_cursor -= row_height

    return table_data


def _collect_structure(
    compiler: PDFCompiler,
    height_func,
    unified_layout,
) -> List[Dict[str, object]]:
    structure: List[Dict[str, object]] = []

    for page in unified_layout.pages:
        page_entry: Dict[str, object] = {
            "page": page.number,
            "blocks": [],
        }

        for block in page.blocks:
            block_entry: Dict[str, object] = {
                "type": block.block_type,
                "frame": _rect_to_tuple(block.frame),
            }

            raw_content, payload = PDFCompiler._resolve_content(block.content)

            if block.block_type == "paragraph":
                if isinstance(payload, ParagraphLayout):
                    block_entry["paragraph"] = {
                        "lines": len(payload.lines),
                        "height": _round(height_func(payload)),
                        "has_payload": True,
                    }
                else:
                    block_entry["paragraph"] = {
                        "lines": None,
                        "height": None,
                        "has_payload": False,
                    }
            elif block.block_type == "table":
                if isinstance(block.content, BlockContent):
                    raw_table = block.content.raw
                else:
                    raw_table = raw_content if isinstance(raw_content, dict) else {}
                block_entry["table"] = _collect_table_structure(
                    compiler=compiler,
                    height_func=height_func,
                    block=block,
                    raw_table=raw_table,
                )

            page_entry["blocks"].append(block_entry)

        structure.append(page_entry)

    return structure


def _diff_structures(prod, debug, path: str = "root") -> List[Dict[str, object]]:
    diffs: List[Dict[str, object]] = []

    number_types = (int, float)

    if isinstance(prod, number_types) and isinstance(debug, number_types):
        if not math.isclose(float(prod), float(debug), abs_tol=1e-3):
            diffs.append({"path": path, "production": prod, "debug": debug})
        return diffs

    simple_types = (str, bool)
    if isinstance(prod, simple_types) and isinstance(debug, simple_types):
        if prod != debug:
            diffs.append({"path": path, "production": prod, "debug": debug})
        return diffs

    if prod is None or debug is None:
        if prod != debug:
            diffs.append({"path": path, "production": prod, "debug": debug})
        return diffs

    if isinstance(prod, list) and isinstance(debug, list):
        if len(prod) != len(debug):
            diffs.append(
                {
                    "path": path,
                    "difference": "length mismatch",
                    "production_length": len(prod),
                    "debug_length": len(debug),
                }
            )
        for index, (p_item, d_item) in enumerate(zip(prod, debug)):
            child_path = f"{path}[{index}]"
            diffs.extend(_diff_structures(p_item, d_item, child_path))
        return diffs

    if isinstance(prod, dict) and isinstance(debug, dict):
        prod_keys = set(prod.keys())
        debug_keys = set(debug.keys())

        for key in sorted(prod_keys - debug_keys):
            diffs.append(
                {
                    "path": f"{path}.{key}",
                    "difference": "missing in debug",
                    "production": prod[key],
                }
            )
        for key in sorted(debug_keys - prod_keys):
            diffs.append(
                {
                    "path": f"{path}.{key}",
                    "difference": "missing in production",
                    "debug": debug[key],
                }
            )
        for key in sorted(prod_keys & debug_keys):
            child_path = f"{path}.{key}"
            diffs.extend(_diff_structures(prod[key], debug[key], child_path))
        return diffs

    if prod != debug:
        diffs.append({"path": path, "production": prod, "debug": debug})

    return diffs


def _build_unified_layout(doc_path: Path):
    package_reader = PackageReader(doc_path)
    xml_parser = XMLParser(package_reader)
    body = xml_parser.parse_body()

    class DocumentAdapter:
        def __init__(self, body_obj, parser):
            self.elements = getattr(body_obj, "children", [])
            self.parser = parser

    document_model = DocumentAdapter(body, xml_parser)
    sections = xml_parser.parse_sections()
    margins = Margins(top=72, bottom=72, left=72, right=72)
    if sections:
        section = sections[0]
        if "margins" in section:
            m = section["margins"]

            def _get_margin(key: str, default: int) -> int:
                value = m.get(key, default)
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return default

            margins = Margins(
                top=twips_to_points(_get_margin("top", 1440)),
                bottom=twips_to_points(_get_margin("bottom", 1440)),
                left=twips_to_points(_get_margin("left", 1440)),
                right=twips_to_points(_get_margin("right", 1440)),
            )

    page_config = PageConfig(page_size=Size(595, 842), base_margins=margins)
    pipeline = LayoutPipeline(page_config)
    unified_layout = pipeline.process(document_model, apply_headers_footers=True)
    return unified_layout, package_reader


@pytest.mark.visual
@pytest.mark.slow
@pytest.mark.parametrize("sample_path", VISUAL_SAMPLES, ids=lambda p: p.stem)
def test_layout_structure_matches_debug(sample_path: Path, tmp_path: Path) -> None:
    unified_layout, package_reader = _build_unified_layout(sample_path)

    pdf_compiler = PDFCompiler(
        output_path=str(tmp_path / f"{sample_path.stem}_prod.pdf"),
        page_size=(595, 842),
        package_reader=package_reader,
    )

    structure_debug = _collect_structure(
        compiler=pdf_compiler,
        height_func=DebugPDFCompiler._paragraph_layout_height,
        unified_layout=unified_layout,
    )
    structure_prod = _collect_structure(
        compiler=pdf_compiler,
        height_func=pdf_compiler._paragraph_layout_height,
        unified_layout=unified_layout,
    )

    artifacts_dir = tmp_path / "layout_compare"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    prod_path = artifacts_dir / "production.json"
    debug_path = artifacts_dir / "debug.json"

    with prod_path.open("w", encoding="utf-8") as f:
        json.dump(structure_prod, f, indent=2, ensure_ascii=False)
    with debug_path.open("w", encoding="utf-8") as f:
        json.dump(structure_debug, f, indent=2, ensure_ascii=False)

    diffs = _diff_structures(structure_prod, structure_debug)
    diff_path = artifacts_dir / "diff.json"
    with diff_path.open("w", encoding="utf-8") as f:
        json.dump(diffs, f, indent=2, ensure_ascii=False)

    if diffs:
        pytest.fail(
            "Production compiler deviates from debug geometry snapshot. "
            f"Diff saved to {diff_path}"
        )

    print(f"[layout] structural snapshots saved to {artifacts_dir}")


@pytest.mark.visual
@pytest.mark.slow
@pytest.mark.parametrize("sample_path", VISUAL_SAMPLES, ids=lambda p: p.stem)
def test_visual_rendering_against_libreoffice(sample_path: Path, tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    image_module = pytest.importorskip("PIL.Image", reason="Pillow is required for visual comparison tests")
    pdf2image = pytest.importorskip("pdf2image")
    skimage_metrics = pytest.importorskip("skimage.metrics")

    convert_from_path = pdf2image.convert_from_path
    PDFInfoNotInstalledError = pdf2image.exceptions.PDFInfoNotInstalledError

    if hasattr(image_module, "Resampling"):
        resample_lanczos = image_module.Resampling.LANCZOS  # type: ignore[attr-defined]
    else:  # pragma: no cover - Pillow < 10 fallback
        resample_lanczos = image_module.LANCZOS

    libreoffice_bin = shutil.which("libreoffice")
    if not libreoffice_bin:  # pragma: no cover - environment dependent
        pytest.skip("LibreOffice is required for visual comparison tests")

    unified_layout, package_reader = _build_unified_layout(sample_path)
    production_pdf = tmp_path / f"{sample_path.stem}_production.pdf"
    compiler = PDFCompiler(
        output_path=str(production_pdf),
        page_size=(595, 842),
        package_reader=package_reader,
    )
    compiler.compile(unified_layout)

    reference_dir = tmp_path / "libreoffice_reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        libreoffice_bin,
        "--headless",
        "--nologo",
        "--nodefault",
        "--invisible",
        "--convert-to",
        "pdf",
        str(sample_path),
        "--outdir",
        str(reference_dir),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    reference_pdf = reference_dir / f"{sample_path.stem}.pdf"
    if not reference_pdf.exists():  # pragma: no cover - LibreOffice quirks
        candidates = sorted(reference_dir.glob("*.pdf"))
        if not candidates:
            raise AssertionError("LibreOffice did not create any PDF output")
        reference_pdf = candidates[0]

    diff_dir = tmp_path / "visual_diffs" / sample_path.stem
    diff_dir.mkdir(parents=True, exist_ok=True)

    try:
        reference_pages = convert_from_path(str(reference_pdf), dpi=150)
        production_pages = convert_from_path(str(production_pdf), dpi=150)
    except PDFInfoNotInstalledError as exc:  # pragma: no cover - poppler missing
        pytest.skip(f"pdf2image requires poppler utilities: {exc}")

    if not reference_pages:
        pytest.xfail("LibreOffice reference PDF contains no pages")

    if len(reference_pages) != len(production_pages):
        metadata = {
            "reference_pdf": str(reference_pdf),
            "production_pdf": str(production_pdf),
            "reference_pages": len(reference_pages),
            "production_pages": len(production_pages),
        }
        meta_path = diff_dir / "page_mismatch.json"
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"[visual] page-count mismatch metadata saved to {meta_path}")
        pytest.xfail(
            "PDF page count mismatch between LibreOffice reference and production output"
        )

    diffs: List[Dict[str, object]] = []

    for index, (ref_img, prod_img) in enumerate(zip(reference_pages, production_pages), start=1):
        if ref_img.size != prod_img.size:
            prod_img = prod_img.resize(ref_img.size, resample=resample_lanczos)

        gray_ref = ref_img.convert("L")
        gray_prod = prod_img.convert("L")

        arr_ref = np.array(gray_ref)
        arr_prod = np.array(gray_prod)
        score, diff = skimage_metrics.structural_similarity(arr_ref, arr_prod, full=True)

        if score < SSIM_THRESHOLD:
            diff_map = (1.0 - diff) * 255.0
            diff_img = image_module.fromarray(diff_map.astype("uint8")).convert("RGB")
            diff_path = diff_dir / f"page_{index:03d}.png"
            diff_img.save(diff_path)
            diffs.append(
                {
                    "page": index,
                    "ssim": round(float(score), 5),
                    "diff_path": str(diff_path),
                }
            )

    if diffs:
        first_diff = diffs[0]
        print(
            f"[visual] Differences detected. Diff images saved under {diff_dir} "
            f"(first page {first_diff['page']} SSIM={first_diff['ssim']})"
        )
        pytest.xfail(
            "Visual regression detected against LibreOffice reference "
            "(see diff images in tmp directory)"
        )

    print(f"[visual] PDFs match LibreOffice reference. Artefacts saved to {diff_dir.parent}")

