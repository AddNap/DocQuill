#!/usr/bin/env python3
"""Export paragraph indent metrics for a DOCX test case."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docx_interpreter.engine.geometry import Margins, Size, twips_to_points
from docx_interpreter.engine.layout_pipeline import LayoutPipeline
from docx_interpreter.engine.page_engine import PageConfig
from docx_interpreter.parser.package_reader import PackageReader
from docx_interpreter.parser.xml_parser import XMLParser


class DocumentAdapter:
    def __init__(self, body_obj: Any, parser: XMLParser):
        if hasattr(body_obj, "children"):
            self.elements = body_obj.children
        elif hasattr(body_obj, "content_order"):
            self.elements = body_obj.content_order
        else:
            self.elements = []
        self.parser = parser


def _resolve_margins(xml_parser: XMLParser) -> Margins:
    sections = xml_parser.parse_sections()
    margins = Margins(top=72, bottom=72, left=72, right=72)
    if not sections:
        return margins

    section = sections[0]
    docx_margins = section.get("margins", {})

    def _get_margin_twips(key: str, default: int = 1440) -> int:
        val = docx_margins.get(key, default)
        if isinstance(val, str):
            try:
                return int(val)
            except (ValueError, TypeError):
                return default
        if isinstance(val, (int, float)):
            return int(val)
        return default

    return Margins(
        top=twips_to_points(_get_margin_twips("top")),
        bottom=twips_to_points(_get_margin_twips("bottom")),
        left=twips_to_points(_get_margin_twips("left")),
        right=twips_to_points(_get_margin_twips("right")),
    )


def collect_paragraph_metrics(doc_path: Path) -> list[Dict[str, Any]]:
    package_reader = PackageReader(doc_path)
    xml_parser = XMLParser(package_reader)
    body = xml_parser.parse_body()
    document_model = DocumentAdapter(body, xml_parser)

    margins = _resolve_margins(xml_parser)
    page_config = PageConfig(page_size=Size(595, 842), base_margins=margins)
    pipeline = LayoutPipeline(page_config)
    layout, _ = pipeline.process_with_summary(document_model, apply_headers_footers=True)

    rows: list[Dict[str, Any]] = []
    index = 0
    for page in layout.pages:
        for block in page.blocks:
            if block.block_type != "paragraph":
                continue
            raw = block.content.raw if hasattr(block.content, "raw") else {}
            indent = raw.get("indent", {}) if isinstance(raw, dict) else {}
            marker = raw.get("marker") if isinstance(raw, dict) else None
            numbering = raw.get("numbering") if isinstance(raw, dict) else None

            left_pt = float(indent.get("left_pt", 0.0) or 0.0)
            left_cm = left_pt / 28.3464566929

            rows.append(
                {
                    "paragraph_index": index,
                    "page": page.number,
                    "block_x_pt": round(block.frame.x, 2),
                    "block_width_pt": round(block.frame.width, 2),
                    "left_indent_pt": left_pt,
                    "left_indent_cm": round(left_cm, 3),
                    "first_line_pt": indent.get("first_line_pt", 0.0) or 0.0,
                    "hanging_pt": indent.get("hanging_pt", 0.0) or 0.0,
                    "number_position_pt": indent.get("number_position_pt", 0.0) or 0.0,
                    "text_position_pt": indent.get("text_position_pt", 0.0) or 0.0,
                    "has_marker": bool(marker),
                    "marker_text": marker.get("text") if marker else "",
                    "hidden_marker": numbering.get("hidden_marker") if isinstance(numbering, dict) else "",
                }
            )
            index += 1

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Export paragraph indent metrics")
    parser.add_argument("docx", type=Path, help="Path to the DOCX input file")
    parser.add_argument("output", type=Path, help="Path to the CSV file to create")
    args = parser.parse_args()

    rows = collect_paragraph_metrics(args.docx)
    fieldnames = list(rows[0].keys()) if rows else []

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} paragraphs to {args.output}")


if __name__ == "__main__":
    main()

