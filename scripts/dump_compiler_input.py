#!/usr/bin/env python3
"""Dump compiler input data before rendering."""

import json
from pathlib import Path
from docx_interpreter.document import Document
from docx_interpreter.engine import SimpleLayoutEngine
from docx_interpreter.engine.geometry import Size, Margins


def format_value(value, max_depth=3, current_depth=0):
    """Format a value for JSON serialization."""
    if current_depth >= max_depth:
        return "..."
    
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    elif isinstance(value, dict):
        return {k: format_value(v, max_depth, current_depth + 1) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [format_value(item, max_depth, current_depth + 1) for item in value[:10]]  # Limit to first 10 items
    elif hasattr(value, '__dict__'):
        return format_value(value.__dict__, max_depth, current_depth + 1)
    else:
        return str(value)


def dump_block_content(block, block_idx, page_idx):
    """Dump block content for compiler."""
    block_data = {
        "block_index": block_idx,
        "block_type": block.block_type,
        "frame": {
            "x": block.frame.x,
            "y": block.frame.y,
            "width": block.frame.width,
            "height": block.frame.height,
        },
        "style": block.style or {},
    }
    
    if block.block_type == 'paragraph':
        content = block.content
        block_data["content_type"] = type(content).__name__
        
        if isinstance(content, dict):
            block_data["content_keys"] = list(content.keys())
            block_data["has_lines"] = "lines" in content
            block_data["has_text"] = "text" in content
            
            if "lines" in content:
                lines = content.get("lines", [])
                block_data["lines_count"] = len(lines)
                block_data["lines"] = []
                
                for line_idx, line_entry in enumerate(lines):
                    if isinstance(line_entry, dict):
                        line_data = {
                            "line_index": line_idx,
                            "keys": list(line_entry.keys()),
                            "text": line_entry.get("text", ""),
                            "text_length": len(line_entry.get("text", "")),
                            "offset_top": line_entry.get("offset_top"),
                            "offset_baseline": line_entry.get("offset_baseline"),
                        }
                        
                        # Get layout info
                        line_layout = line_entry.get("layout")
                        if line_layout:
                            if isinstance(line_layout, dict):
                                line_data["layout"] = {
                                    "width": line_layout.get("width"),
                                    "height": line_layout.get("height"),
                                    "ascent": line_layout.get("ascent"),
                                    "font_size": line_layout.get("font_size"),
                                }
                            elif hasattr(line_layout, "__dict__"):
                                line_data["layout"] = {
                                    "width": getattr(line_layout, "width", None),
                                    "height": getattr(line_layout, "height", None),
                                    "ascent": getattr(line_layout, "ascent", None),
                                    "font_size": getattr(line_layout, "font_size", None),
                                }
                            else:
                                line_data["layout"] = str(line_layout)
                        else:
                            line_data["layout"] = None
                        
                        block_data["lines"].append(line_data)
                
                if "text" in content:
                    full_text = content.get("text", "")
                    block_data["full_text"] = full_text
                    block_data["full_text_length"] = len(full_text)
                    
                    # Check if lines use full_text instead of fragments
                    if lines:
                        for line_idx, line_entry in enumerate(lines):
                            if isinstance(line_entry, dict):
                                line_text = line_entry.get("text", "")
                                if line_text == full_text and len(full_text) > 50:
                                    block_data.setdefault("warnings", []).append(
                                        f"Line {line_idx} uses full_text instead of fragment (length: {len(line_text)})"
                                    )
        elif hasattr(content, "runs"):
            block_data["content"] = "model-based (has runs)"
            block_data["warnings"] = ["Model-based content - should be converted to dict with lines"]
    
    elif block.block_type == 'image':
        content = block.content
        block_data["content_type"] = type(content).__name__
        
        if isinstance(content, dict):
            block_data["content_keys"] = list(content.keys())
            block_data["part_path"] = content.get("part_path")
            block_data["rel_id"] = content.get("rel_id")
            block_data["position"] = content.get("position")
            block_data["width"] = content.get("width")
            block_data["height"] = content.get("height")
        elif hasattr(content, "__dict__"):
            # Try to extract image data from object attributes
            block_data["part_path"] = getattr(content, "part_path", None)
            block_data["rel_id"] = getattr(content, "rel_id", None)
            block_data["position"] = getattr(content, "position", None)
            if hasattr(content, "width"):
                block_data["width"] = getattr(content, "width", None)
            if hasattr(content, "height"):
                block_data["height"] = getattr(content, "height", None)
            # Try to serialize position if it's a dict
            position = getattr(content, "position", None)
            if isinstance(position, dict):
                block_data["position"] = {
                    "x": position.get("x"),
                    "y": position.get("y"),
                    "x_rel": position.get("x_rel"),
                    "y_rel": position.get("y_rel"),
                }
        else:
            block_data["content"] = str(content)
    
    elif block.block_type == 'table':
        content = block.content
        block_data["content_type"] = type(content).__name__
        
        if isinstance(content, dict):
            block_data["content_keys"] = list(content.keys())
            rows = content.get("rows", [])
            block_data["rows_count"] = len(rows)
            cells = content.get("cells", [])
            block_data["cells_count"] = len(cells)
            grid_lines = content.get("grid_lines", [])
            block_data["grid_lines_count"] = len(grid_lines)
            if rows and isinstance(rows[0], dict):
                block_data["columns_count"] = len(rows[0].get("cells", []))
            elif rows and hasattr(rows[0], "cells"):
                block_data["columns_count"] = len(getattr(rows[0], "cells", []))
            else:
                # Try to get columns from cells
                if cells:
                    # Count unique col_idx values
                    col_indices = set()
                    for cell_data in cells:
                        if isinstance(cell_data, dict):
                            col_idx = cell_data.get("col_idx", -1)
                            if col_idx >= 0:
                                col_indices.add(col_idx)
                        elif hasattr(cell_data, "col_idx"):
                            col_idx = getattr(cell_data, "col_idx", -1)
                            if col_idx >= 0:
                                col_indices.add(col_idx)
                    block_data["columns_count"] = len(col_indices) if col_indices else 0
                else:
                    block_data["columns_count"] = 0
            # Store actual content for debugging (preserve full structure)
            # But limit size to avoid huge JSON files
            if cells and len(cells) > 0:
                # Store first cell as sample
                first_cell_sample = cells[0] if isinstance(cells[0], dict) else str(cells[0])[:100]
                block_data["content_sample"] = {"first_cell": first_cell_sample}
            if grid_lines and len(grid_lines) > 0:
                # Store first grid line as sample
                first_line_sample = grid_lines[0] if isinstance(grid_lines[0], dict) else str(grid_lines[0])[:100]
                block_data["content_sample"] = block_data.get("content_sample", {})
                block_data["content_sample"]["first_grid_line"] = first_line_sample
            # Keep original content reference (will be serialized by json.dump)
            block_data["content"] = content
        elif hasattr(content, "rows"):
            rows = getattr(content, "rows", [])
            block_data["rows_count"] = len(rows) if rows else 0
            if rows and len(rows) > 0:
                first_row = rows[0]
                if hasattr(first_row, "cells"):
                    cells = getattr(first_row, "cells", [])
                    block_data["columns_count"] = len(cells) if cells else 0
                elif isinstance(first_row, dict):
                    block_data["columns_count"] = len(first_row.get("cells", []))
                else:
                    block_data["columns_count"] = 0
            else:
                block_data["columns_count"] = 0
            block_data["content"] = "model-based (has rows/cells)"
        else:
            block_data["content"] = "unknown table structure"
    
    elif block.block_type == 'textbox':
        content = block.content
        block_data["content_type"] = type(content).__name__
        
        if isinstance(content, dict):
            block_data["content_keys"] = list(content.keys())
            block_data["has_text"] = "text" in content or "lines" in content
        elif hasattr(content, "__dict__"):
            block_data["content"] = "model-based"
    
    return block_data


def validate_footer_blocks(page_data: dict, page_number: int, page_height: float = 841.89) -> dict:
    """
    Validate footer structure for a specific page.
    
    Expected footer elements (in order bottom-up):
    1. Table with logo and project description (~14.37 cm width)
    2. Paragraph with page number (PAGE/NUMPAGES)
    3. Anchored image (rId2) - bottom right corner
    4. Textbox with absolute position - bottom margin
    
    Returns:
        Validation report with errors and warnings
    """
    # Convert units: 1 cm = 28.35 pt, 1 dxa = 1/20 pt
    CM_TO_PT = 28.35
    DXA_TO_PT = 1.0 / 20.0
    
    # Expected dimensions (from DOCX spec)
    EXPECTED_TABLE_WIDTH = 8163 * DXA_TO_PT  # ~408.15 pt ≈ 14.37 cm
    EXPECTED_TABLE_CELL1_WIDTH = 4656 * DXA_TO_PT  # ~232.8 pt ≈ 8.20 cm
    EXPECTED_TABLE_CELL2_WIDTH = 3506 * DXA_TO_PT  # ~175.3 pt ≈ 6.18 cm
    
    # Expected image rId2: X=4589780 EMU (~12.75 cm), Y=9825990 EMU (~27.29 cm)
    # 1 EMU = 1/914400 inch, 1 inch = 72 pt
    EMU_TO_PT = 72.0 / 914400.0
    EXPECTED_IMAGE_X = 4589780 * EMU_TO_PT  # ~361.0 pt ≈ 12.75 cm
    EXPECTED_IMAGE_Y = 9825990 * EMU_TO_PT  # ~773.4 pt ≈ 27.29 cm (from top)
    EXPECTED_IMAGE_WIDTH = 1231265 * EMU_TO_PT  # ~96.9 pt ≈ 3.42 cm
    EXPECTED_IMAGE_HEIGHT = 849630 * EMU_TO_PT  # ~66.9 pt ≈ 2.36 cm
    
    # Expected textbox: X=-4445 EMU (~-0.01 cm), Y=9822180 EMU (~27.27 cm)
    EXPECTED_TEXTBOX_X = -4445 * EMU_TO_PT  # ~-0.35 pt ≈ -0.01 cm
    EXPECTED_TEXTBOX_Y = 9822180 * EMU_TO_PT  # ~773.2 pt ≈ 27.27 cm (from top)
    EXPECTED_TEXTBOX_WIDTH = 4269740 * EMU_TO_PT  # ~336.2 pt ≈ 11.86 cm
    EXPECTED_TEXTBOX_HEIGHT = 538480 * EMU_TO_PT  # ~42.4 pt ≈ 1.50 cm
    
    TOLERANCE = 5.0  # 5 pt tolerance for positions and dimensions
    
    report = {
        "page_number": page_number,
        "valid": True,
        "errors": [],
        "warnings": [],
        "found_elements": {
            "table": None,
            "page_number_paragraph": None,
            "anchored_image": None,
            "textbox": None,
        }
    }
    
    # Collect footer blocks
    # Footer area is roughly bottom 150 pt of page (footer margin + content)
    footer_area_threshold = page_height - 150
    
    footer_blocks = []
    for block in page_data.get("blocks", []):
        block_type = block.get("block_type")
        frame = block.get("frame", {})
        y = frame.get("y", 0)
        
        # Include all blocks with block_type == "footer" (they're explicitly marked as footer)
        if block_type == "footer":
            footer_blocks.append(block)
        # Include tables, images, textboxes in footer area (Y > threshold)
        elif block_type in ("table", "image", "textbox") and y > footer_area_threshold:
            footer_blocks.append(block)
    
    # Sort by Y position (bottom to top)
    footer_blocks.sort(key=lambda b: b.get("frame", {}).get("y", 0), reverse=True)
    
    # Find table
    for block in footer_blocks:
        if block.get("block_type") == "table":
            frame = block.get("frame", {})
            width = frame.get("width", 0)
            if abs(width - EXPECTED_TABLE_WIDTH) <= TOLERANCE:
                report["found_elements"]["table"] = {
                    "block_index": block.get("block_index"),
                    "frame": frame,
                    "width_match": abs(width - EXPECTED_TABLE_WIDTH) <= TOLERANCE,
                }
                break
    
    # Find page number paragraph (should contain "Strona" or be a placeholder)
    for block in footer_blocks:
        if block.get("block_type") in ("paragraph", "footer"):
            # Check full_text directly (from dump_block_content)
            text = block.get("full_text", "")
            if not text:
                # Check lines if available
                lines = block.get("lines", [])
                if lines:
                    text = " ".join(line.get("text", "") for line in lines if isinstance(line, dict))
            
            if isinstance(text, str) and ("Strona" in text or "PAGE" in text.upper() or "NUMPAGES" in text.upper()):
                report["found_elements"]["page_number_paragraph"] = {
                    "block_index": block.get("block_index"),
                    "frame": block.get("frame", {}),
                    "text_preview": text[:50] if text else None,
                }
                break
    
    # Find anchored image (rId2)
    for block in footer_blocks:
        if block.get("block_type") == "image":
            # Read rel_id directly from dump_block_content output
            rel_id = block.get("rel_id")
            
            frame = block.get("frame", {})
            x = frame.get("x", 0)
            y = frame.get("y", 0)
            width = frame.get("width", 0)
            height = frame.get("height", 0)
            
            # Check if position matches expected rId2 (bottom right)
            x_match = abs(x - EXPECTED_IMAGE_X) <= TOLERANCE
            y_match = abs(y - EXPECTED_IMAGE_Y) <= TOLERANCE
            width_match = abs(width - EXPECTED_IMAGE_WIDTH) <= TOLERANCE
            height_match = abs(height - EXPECTED_IMAGE_HEIGHT) <= TOLERANCE
            
            if x_match or y_match or (rel_id == "rId2"):
                report["found_elements"]["anchored_image"] = {
                    "block_index": block.get("block_index"),
                    "frame": frame,
                    "rel_id": rel_id,
                    "position_match": x_match and y_match,
                    "size_match": width_match and height_match,
                }
                break
    
    # Find textbox
    for block in footer_blocks:
        if block.get("block_type") == "textbox":
            frame = block.get("frame", {})
            x = frame.get("x", 0)
            y = frame.get("y", 0)
            width = frame.get("width", 0)
            height = frame.get("height", 0)
            
            x_match = abs(x - EXPECTED_TEXTBOX_X) <= TOLERANCE
            y_match = abs(y - EXPECTED_TEXTBOX_Y) <= TOLERANCE
            width_match = abs(width - EXPECTED_TEXTBOX_WIDTH) <= TOLERANCE
            height_match = abs(height - EXPECTED_TEXTBOX_HEIGHT) <= TOLERANCE
            
            if x_match or y_match:
                report["found_elements"]["textbox"] = {
                    "block_index": block.get("block_index"),
                    "frame": frame,
                    "position_match": x_match and y_match,
                    "size_match": width_match and height_match,
                }
                break
    
    # Validation checks
    if not report["found_elements"]["table"]:
        report["valid"] = False
        report["errors"].append("Missing footer table with logo and project description")
    elif not report["found_elements"]["table"]["width_match"]:
        report["warnings"].append(
            f"Table width mismatch: expected ~{EXPECTED_TABLE_WIDTH:.1f} pt, "
            f"got {report['found_elements']['table']['frame'].get('width', 0):.1f} pt"
        )
    
    if not report["found_elements"]["page_number_paragraph"]:
        report["valid"] = False
        report["errors"].append("Missing page number paragraph")
    
    if not report["found_elements"]["anchored_image"]:
        report["valid"] = False
        report["errors"].append("Missing anchored image (rId2) in bottom right corner")
    elif report["found_elements"]["anchored_image"]:
        img = report["found_elements"]["anchored_image"]
        if not img.get("position_match"):
            report["warnings"].append(
                f"Image position mismatch: expected X~{EXPECTED_IMAGE_X:.1f} pt, Y~{EXPECTED_IMAGE_Y:.1f} pt, "
                f"got X={img['frame'].get('x', 0):.1f} pt, Y={img['frame'].get('y', 0):.1f} pt"
            )
        if not img.get("size_match"):
            report["warnings"].append(
                f"Image size mismatch: expected {EXPECTED_IMAGE_WIDTH:.1f}×{EXPECTED_IMAGE_HEIGHT:.1f} pt, "
                f"got {img['frame'].get('width', 0):.1f}×{img['frame'].get('height', 0):.1f} pt"
            )
    
    if not report["found_elements"]["textbox"]:
        report["valid"] = False
        report["errors"].append("Missing textbox with absolute position")
    elif report["found_elements"]["textbox"]:
        tb = report["found_elements"]["textbox"]
        if not tb.get("position_match"):
            report["warnings"].append(
                f"Textbox position mismatch: expected X~{EXPECTED_TEXTBOX_X:.1f} pt, Y~{EXPECTED_TEXTBOX_Y:.1f} pt, "
                f"got X={tb['frame'].get('x', 0):.1f} pt, Y={tb['frame'].get('y', 0):.1f} pt"
            )
        if not tb.get("size_match"):
            report["warnings"].append(
                f"Textbox size mismatch: expected {EXPECTED_TEXTBOX_WIDTH:.1f}×{EXPECTED_TEXTBOX_HEIGHT:.1f} pt, "
                f"got {tb['frame'].get('width', 0):.1f}×{tb['frame'].get('height', 0):.1f} pt"
            )
    
    # Check order (bottom-up: table should be highest Y, page number below, image/textbox at bottom)
    if len(footer_blocks) >= 2:
        ys = [(b.get("frame", {}).get("y", 0), b.get("block_type")) for b in footer_blocks]
        ys_sorted = sorted(ys, key=lambda x: x[0], reverse=True)  # Bottom to top
        
        # Table should be above page number paragraph
        table_y = None
        page_num_y = None
        for y, bt in ys_sorted:
            if bt == "table" and table_y is None:
                table_y = y
            elif bt in ("paragraph", "footer") and page_num_y is None:
                page_num_y = y
        
        if table_y is not None and page_num_y is not None:
            if page_num_y > table_y:  # Page number below table (higher Y = lower on page)
                report["warnings"].append("Order issue: page number paragraph should be below table (higher Y)")
    
    return report


def main():
    input_path = Path('tests/files/Zapytanie_Ofertowe.docx')
    output_dir = Path('output')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'compiler_input_dump.json'
    
    doc = Document.from_file(input_path)
    engine = SimpleLayoutEngine(
        page_size=Size(595.28, 841.89),
        margins=Margins(50, 50, 50, 50)
    )
    pages = engine.build_layout(doc)
    
    dump_data = {
        "document_name": input_path.name,
        "total_pages": len(pages),
        "pages": []
    }
    
    total_paragraphs = 0
    total_headers = 0
    total_footers = 0
    total_tables = 0
    total_images = 0
    paragraphs_with_lines = 0
    paragraphs_with_full_text_lines = 0
    
    print('Dumping compiler input data:')
    footer_validation_reports = []
    
    for page_idx, page in enumerate(pages):
        page_data = {
            "page_number": page_idx + 1,
            "header_height": getattr(page, "header_height", 0.0),
            "footer_height": getattr(page, "footer_height", 0.0),
            "blocks": []
        }
        
        for block_idx, block in enumerate(page.blocks):
            block_data = dump_block_content(block, block_idx, page_idx)
            
            # Count by type
            if block.block_type == 'paragraph':
                total_paragraphs += 1
            elif block.block_type == 'header':
                total_headers += 1
            elif block.block_type == 'footer':
                total_footers += 1
            elif block.block_type == 'table':
                total_tables += 1
            elif block.block_type == 'image':
                total_images += 1
            
            page_data["blocks"].append(block_data)
        
        dump_data["pages"].append(page_data)
        
        # Validate footer for this page
        page_height = getattr(page, "size", Size(595.28, 841.89)).height
        validation_report = validate_footer_blocks(page_data, page_idx + 1, page_height)
        footer_validation_reports.append(validation_report)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dump_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nDump saved to {output_path}")
    print(f"Total pages: {len(pages)}")
    print(f"Total paragraphs: {total_paragraphs}")
    print(f"Total headers: {total_headers}")
    print(f"Total footers: {total_footers}")
    print(f"Total tables: {total_tables}")
    print(f"Total images: {total_images}")
    print(f"Paragraphs with lines: {paragraphs_with_lines}")
    print(f"Paragraphs with full_text lines: {paragraphs_with_full_text_lines}")
    
    # Footer validation report
    print("\n" + "="*80)
    print("FOOTER VALIDATION REPORT")
    print("="*80)
    
    valid_pages = sum(1 for r in footer_validation_reports if r.get("valid"))
    invalid_pages = len(footer_validation_reports) - valid_pages
    
    print(f"\nValid footers: {valid_pages}/{len(footer_validation_reports)}")
    print(f"Invalid footers: {invalid_pages}/{len(footer_validation_reports)}")
    
    if invalid_pages > 0:
        print("\n⚠️  INVALID FOOTERS:")
        for report in footer_validation_reports:
            if not report.get("valid"):
                print(f"\n  Page {report['page_number']}:")
                for error in report.get("errors", []):
                    print(f"    ❌ {error}")
                for warning in report.get("warnings", []):
                    print(f"    ⚠️  {warning}")
    
    # Show warnings for all pages
    pages_with_warnings = [r for r in footer_validation_reports if r.get("warnings")]
    if pages_with_warnings:
        print("\n⚠️  PAGES WITH WARNINGS:")
        for report in pages_with_warnings:
            print(f"\n  Page {report['page_number']}:")
            for warning in report.get("warnings", []):
                print(f"    ⚠️  {warning}")
    
    # Summary of found elements
    print("\n📊 FOOTER ELEMENTS SUMMARY:")
    element_counts = {
        "table": sum(1 for r in footer_validation_reports if r.get("found_elements", {}).get("table")),
        "page_number_paragraph": sum(1 for r in footer_validation_reports if r.get("found_elements", {}).get("page_number_paragraph")),
        "anchored_image": sum(1 for r in footer_validation_reports if r.get("found_elements", {}).get("anchored_image")),
        "textbox": sum(1 for r in footer_validation_reports if r.get("found_elements", {}).get("textbox")),
    }
    for element_name, count in element_counts.items():
        status = "✅" if count == len(footer_validation_reports) else "⚠️"
        print(f"  {status} {element_name}: {count}/{len(footer_validation_reports)} pages")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

