#!/usr/bin/env python3
"""Dump layout engine structure for debugging."""

import json
from pathlib import Path
from docx_interpreter.document import Document
from docx_interpreter.engine import DocumentEngine
from docx_interpreter.engine.geometry import Size, Margins


def format_value(value):
    """Format value for JSON serialization."""
    if hasattr(value, '__dict__'):
        return str(value)
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [format_value(v) for v in value]
    if isinstance(value, dict):
        return {k: format_value(v) for k, v in value.items()}
    return str(value)


def dump_layout_block(block, block_idx):
    """Dump a layout block structure."""
    block_data = {
        "block_index": block_idx,
        "block_type": block.block_type,
        "frame": {
            "x": block.frame.x,
            "y": block.frame.y,
            "width": block.frame.width,
            "height": block.frame.height,
        },
        "style": format_value(block.style),
    }
    
    # Handle content
    content = block.content
    if isinstance(content, dict):
        block_data["content_type"] = "dict"
        block_data["content_keys"] = list(content.keys())
        
        # Special handling for textbox (has positioned_elements)
        if block.block_type == "textbox" and "positioned_elements" in content:
            positioned_elements = content.get("positioned_elements", [])
            block_data["positioned_elements_count"] = len(positioned_elements)
            block_data["positioned_elements"] = []
            
            for elem_idx, elem_data in enumerate(positioned_elements):
                if isinstance(elem_data, dict):
                    elem_block = elem_data.get("element")
                    if elem_block:
                        # Recursively dump the nested block
                        nested_block_data = dump_layout_block(elem_block, elem_idx)
                        nested_block_data["position_in_textbox"] = {
                            "x": elem_data.get("x"),
                            "y": elem_data.get("y"),
                            "width": elem_data.get("width"),
                            "height": elem_data.get("height"),
                        }
                        block_data["positioned_elements"].append(nested_block_data)
                    else:
                        block_data["positioned_elements"].append({
                            "element_index": elem_idx,
                            "raw": format_value(elem_data)
                        })
            
            # Also extract text from nested elements
            full_text_parts = []
            for elem_data in positioned_elements:
                if isinstance(elem_data, dict):
                    elem_block = elem_data.get("element")
                    if elem_block and hasattr(elem_block, "content"):
                        nested_content = elem_block.content
                        if isinstance(nested_content, dict):
                            nested_text = nested_content.get("text", "")
                            if nested_text:
                                full_text_parts.append(nested_text)
            
            block_data["full_text"] = " ".join(full_text_parts)
            block_data["full_text_length"] = len(block_data["full_text"])
            block_data["lines_count"] = sum(
                1 for elem_data in positioned_elements 
                if isinstance(elem_data, dict) and elem_data.get("element")
            )
        else:
            # Regular content (paragraphs, tables, etc.)
            # Full text
            full_text = content.get("text", "")
            block_data["full_text"] = full_text
            block_data["full_text_length"] = len(full_text)
            
            # Lines
            lines = content.get("lines", [])
            block_data["lines_count"] = len(lines)
            block_data["lines"] = []
            
            for line_idx, line_entry in enumerate(lines):
                if isinstance(line_entry, dict):
                    line_data = {
                        "line_index": line_idx,
                        "text": line_entry.get("text", ""),
                        "text_length": len(line_entry.get("text", "")),
                    }
                    
                    # Layout info
                    line_layout = line_entry.get("layout")
                    if line_layout:
                        line_data["layout"] = {
                            "width": getattr(line_layout, "width", None),
                            "height": getattr(line_layout, "height", None),
                            "ascent": getattr(line_layout, "ascent", None),
                            "font_size": getattr(line_layout, "font_size", None),
                        }
                    
                    # Other line properties
                    for key in ["offset_top", "offset_baseline", "hyphenated", "start", "end"]:
                        if key in line_entry:
                            line_data[key] = line_entry[key]
                    
                    block_data["lines"].append(line_data)
                else:
                    block_data["lines"].append({"line_index": line_idx, "raw": str(line_entry)})
            
            # Runs
            runs = content.get("runs", [])
            if runs:
                block_data["runs_count"] = len(runs)
            
            # Other content keys
            for key in ["usable_width", "line_spacing"]:
                if key in content:
                    block_data[key] = content[key]
                
    elif hasattr(content, "runs"):
        block_data["content_type"] = "model_object"
        block_data["content_class"] = content.__class__.__name__
        # Try to get text from runs
        full_text = "".join(getattr(run, "text", "") for run in content.runs if hasattr(run, "text"))
        block_data["full_text"] = full_text
        block_data["full_text_length"] = len(full_text)
    else:
        block_data["content_type"] = "unknown"
        block_data["content"] = str(content)
    
    return block_data


def main():
    """Main function to dump layout."""
    input_path = Path("tests/files/Zapytanie_Ofertowe.docx")
    output_path = Path("output/layout_dump.json")
    
    print(f"Loading document: {input_path}")
    doc = Document.from_file(input_path)
    
    print("Building layout...")
    engine = DocumentEngine(
        page_size=Size(595.28, 841.89),
        margins=Margins(50, 50, 50, 50)
    )
    pages = engine.build_layout(doc)
    
    print(f"Layout built: {len(pages)} pages")
    
    # Dump structure
    dump_data = {
        "pages_count": len(pages),
        "pages": []
    }
    
    for page_idx, page in enumerate(pages):
        page_data = {
            "page_number": page.number,
            "size": {
                "width": page.size.width,
                "height": page.size.height,
            },
            "blocks_count": len(page.blocks),
            "blocks": []
        }
        
        # Analyze blocks
        for block_idx, block in enumerate(page.blocks):
            block_data = dump_layout_block(block, block_idx)
            page_data["blocks"].append(block_data)
        
        dump_data["pages"].append(page_data)
    
    # Save to JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dump_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Layout dump saved to: {output_path}")
    
    # Print summary
    print("\n=== SUMMARY ===")
    total_paragraphs = 0
    single_line_paragraphs = 0
    multi_line_paragraphs = 0
    
    for page in dump_data["pages"]:
        for block in page["blocks"]:
            if block["block_type"] == "paragraph":
                total_paragraphs += 1
                lines_count = block.get("lines_count", 0)
                if lines_count == 1:
                    single_line_paragraphs += 1
                    full_text_length = block.get("full_text_length", 0)
                    if full_text_length > 80:
                        # This might be a problem
                        print(f"⚠️  Single-line paragraph with {full_text_length} chars: {block['full_text'][:60]}...")
                elif lines_count > 1:
                    multi_line_paragraphs += 1
    
    print(f"\nTotal paragraphs: {total_paragraphs}")
    print(f"Single-line paragraphs: {single_line_paragraphs}")
    print(f"Multi-line paragraphs: {multi_line_paragraphs}")
    
    # Find problematic paragraphs
    print("\n=== PROBLEMATIC PARAGRAPHS ===")
    problem_count = 0
    for page_idx, page in enumerate(dump_data["pages"]):
        for block_idx, block in enumerate(page["blocks"]):
            if block["block_type"] == "paragraph":
                lines_count = block.get("lines_count", 0)
                full_text_length = block.get("full_text_length", 0)
                block_width = block["frame"]["width"]
                
                if lines_count == 1 and full_text_length > 80 and block_width > 200:
                    problem_count += 1
                    print(f"\nPage {page_idx + 1}, Block {block_idx}:")
                    print(f"  Text length: {full_text_length}")
                    print(f"  Block width: {block_width:.2f}")
                    print(f"  Lines: {lines_count}")
                    if block["lines"]:
                        line = block["lines"][0]
                        line_width = line.get("layout", {}).get("width")
                        if line_width:
                            print(f"  Line width: {line_width:.2f}")
                            if line_width < block_width * 0.5:
                                print(f"  ⚠️  Line is much narrower than block - should be broken!")
                    print(f"  Text preview: {block['full_text'][:100]}...")


if __name__ == "__main__":
    main()

