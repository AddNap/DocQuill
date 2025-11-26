#!/usr/bin/env python3
"""Debug script to dump header/footer structure from layout engine and compiler."""

import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docquill.parser.package_reader import PackageReader
from docquill.parser.xml_parser import XMLParser
from docquill.engine.layout_pipeline import LayoutPipeline
from docquill.engine.unified_layout import UnifiedLayout
from docquill.engine.geometry import Size, Margins
from docquill.engine.page_engine import PageConfig
import json

def dump_dict(obj, indent=0):
    """Recursively dump dict/object structure."""
    indent_str = "  " * indent
    if isinstance(obj, dict):
        result = "{\n"
        for key, value in obj.items():
            result += f"{indent_str}  {key}: "
            if isinstance(value, (dict, list)):
                result += dump_dict(value, indent + 1)
            else:
                result += repr(value)
            result += ",\n"
        result += indent_str + "}"
        return result
    elif isinstance(obj, list):
        result = "[\n"
        for item in obj:
            result += indent_str + "  "
            if isinstance(item, (dict, list)):
                result += dump_dict(item, indent + 1)
            else:
                result += repr(item)
            result += ",\n"
        result += indent_str + "]"
        return result
    else:
        return repr(obj)

def main():
    # Wczytaj dokument
    project_root = Path(__file__).parent.parent
    docx_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    if not docx_path.exists():
        print(f"❌ Plik {docx_path} nie istnieje!")
        return
    
    print("🔄 Krok 1: Ładowanie dokumentu...")
    package_reader = PackageReader(str(docx_path))
    xml_parser = XMLParser(package_reader)
    body = xml_parser.parse_body()
    
    print(f"✅ Dokument sparsowany: {len(body.children) if hasattr(body, 'children') else 0} elementów")
    
    # Stwórz model
    class DocumentAdapter:
        def __init__(self, body_obj, parser):
            self.elements = body_obj.children if hasattr(body_obj, 'children') else []
            self.parser = parser
    
    document_model = DocumentAdapter(body, xml_parser)
    
    print("🔄 Krok 2: Przetwarzanie layoutu...")
    page_config = PageConfig(
        page_size=Size(595, 842),  # A4
        base_margins=Margins(top=72, bottom=72, left=72, right=72)
    )
    pipeline = LayoutPipeline(page_config)
    
    layout = pipeline.process(document_model, apply_headers_footers=True, validate=False)
    
    print(f"✅ Layout utworzony: {len(layout.pages)} stron")
    
    # Pobierz LayoutStructure z pipeline (jeśli dostępne)
    layout_structure = pipeline.layout_structure if hasattr(pipeline, 'layout_structure') else None
    
    # Dump headers z LayoutStructure (jeśli dostępne)
    if layout_structure and hasattr(layout_structure, 'headers'):
        print("\n" + "="*80)
        print("📋 HEADERS (from LayoutStructure):")
        print("="*80)
        for header_type, headers in layout_structure.headers.items():
            print(f"\n  Header type: {header_type}")
            for i, header in enumerate(headers):
                print(f"\n  Header {i+1}:")
                print(f"    Type: {header.get('type', 'unknown')}")
                print(f"    Content keys: {list(header.get('content', {}).keys()) if isinstance(header.get('content'), dict) else 'N/A'}")
                if header.get('type') == 'table':
                    rows = header.get('rows', [])
                    print(f"    Rows: {len(rows)}")
                    for j, row in enumerate(rows):
                        # Obsługa obiektów TableRow i dict
                        cells = []
                        if hasattr(row, 'cells'):
                            cells = row.cells
                        elif isinstance(row, dict) and 'cells' in row:
                            cells = row['cells']
                        
                        print(f"      Row {j+1}: {len(cells)} cells")
                        for k, cell in enumerate(cells):
                            cell_text = ""
                            if hasattr(cell, 'get_text'):
                                cell_text = cell.get_text()
                            elif isinstance(cell, dict):
                                cell_text = cell.get('text', cell.get('content', ''))
                            else:
                                cell_text = str(cell)
                            print(f"        Cell {k+1}: {cell_text[:100]}")
                else:
                    content = header.get('content', {})
                    if isinstance(content, dict):
                        text = content.get('text', content.get('content', ''))
                        images = content.get('images', [])
                        print(f"    Text: {text[:100] if text else 'None'}")
                        print(f"    Images: {len(images)}")
                    else:
                        print(f"    Content: {str(content)[:100]}")
    
    # Dump footers z LayoutStructure (jeśli dostępne)
    if layout_structure and hasattr(layout_structure, 'footers'):
        print("\n" + "="*80)
        print("📋 FOOTERS (from LayoutStructure):")
        print("="*80)
        for footer_type, footers in layout_structure.footers.items():
            print(f"\n  Footer type: {footer_type}")
            for i, footer in enumerate(footers):
                print(f"\n  Footer {i+1}:")
                print(f"    Type: {footer.get('type', 'unknown')}")
                print(f"    Content keys: {list(footer.get('content', {}).keys()) if isinstance(footer.get('content'), dict) else 'N/A'}")
                if footer.get('type') == 'table':
                    rows = footer.get('rows', [])
                    print(f"    Rows: {len(rows)}")
                    for j, row in enumerate(rows):
                        # Obsługa obiektów TableRow i dict
                        cells = []
                        if hasattr(row, 'cells'):
                            cells = row.cells
                        elif isinstance(row, dict) and 'cells' in row:
                            cells = row['cells']
                        
                        print(f"      Row {j+1}: {len(cells)} cells")
                        for k, cell in enumerate(cells):
                            cell_text = ""
                            if hasattr(cell, 'get_text'):
                                cell_text = cell.get_text()
                            elif isinstance(cell, dict):
                                cell_text = cell.get('text', cell.get('content', ''))
                            else:
                                cell_text = str(cell)
                            print(f"        Cell {k+1}: {cell_text[:100]}")
                else:
                    content = footer.get('content', {})
                    if isinstance(content, dict):
                        text = content.get('text', content.get('content', ''))
                        images = content.get('images', [])
                        print(f"    Text: {text[:100] if text else 'None'}")
                        print(f"    Images: {len(images)}")
                    else:
                        print(f"    Content: {str(content)[:100]}")
    
    # Dump blocks from UnifiedLayout pages
    print("\n" + "="*80)
    print("📋 BLOCKS ON PAGES (from UnifiedLayout):")
    print("="*80)
    for page_num, page in enumerate(layout.pages, 1):
        print(f"\n  Page {page_num}:")
        header_blocks = [b for b in page.blocks if b.block_type == "header" or (isinstance(b.content, dict) and b.content.get("header_footer_context") == "header")]
        footer_blocks = [b for b in page.blocks if b.block_type == "footer" or (isinstance(b.content, dict) and b.content.get("header_footer_context") == "footer")]
        body_blocks = [b for b in page.blocks if b.block_type not in {"header", "footer"} and not (isinstance(b.content, dict) and b.content.get("header_footer_context") in {"header", "footer"})]
        
        print(f"    Headers: {len(header_blocks)}")
        for i, block in enumerate(header_blocks):
            content = block.content if isinstance(block.content, dict) else {}
            block_type_in_content = content.get("type", "N/A")
            print(f"      Block {i+1}: block_type={block.block_type}, content.type={block_type_in_content}")
            print(f"        Frame: {block.frame}")
            print(f"        Style keys: {list(block.style.keys()) if isinstance(block.style, dict) else 'N/A'}")
            if block_type_in_content == "table":
                rows = content.get("rows", [])
                print(f"        Rows: {len(rows)}")
                for j, row in enumerate(rows):
                    # Obsługa obiektów TableRow i dict
                    cells = []
                    if hasattr(row, 'cells'):
                        cells = row.cells
                    elif isinstance(row, dict) and 'cells' in row:
                        cells = row['cells']
                    
                    print(f"          Row {j+1}: {len(cells)} cells")
                    for k, cell in enumerate(cells):
                        cell_text = ""
                        if hasattr(cell, 'get_text'):
                            cell_text = cell.get_text()
                        elif isinstance(cell, dict):
                            cell_text = cell.get("text", cell.get("content", ""))
                        else:
                            cell_text = str(cell)
                        print(f"            Cell {k+1}: {str(cell_text)[:100]}")
            elif block_type_in_content == "paragraph":
                text = content.get("text", content.get("content", ""))
                images = content.get("images", [])
                print(f"        Text: {str(text)[:100]}")
                print(f"        Images: {len(images)}")
            else:
                print(f"        Content: {str(content)[:150]}")
        
        print(f"    Footers: {len(footer_blocks)}")
        for i, block in enumerate(footer_blocks):
            content = block.content if isinstance(block.content, dict) else {}
            block_type_in_content = content.get("type", "N/A")
            print(f"      Block {i+1}: block_type={block.block_type}, content.type={block_type_in_content}")
            print(f"        Frame: {block.frame}")
            print(f"        Style keys: {list(block.style.keys()) if isinstance(block.style, dict) else 'N/A'}")
            if block_type_in_content == "table":
                rows = content.get("rows", [])
                print(f"        Rows: {len(rows)}")
                for j, row in enumerate(rows):
                    # Obsługa obiektów TableRow i dict
                    cells = []
                    if hasattr(row, 'cells'):
                        cells = row.cells
                    elif isinstance(row, dict) and 'cells' in row:
                        cells = row['cells']
                    
                    print(f"          Row {j+1}: {len(cells)} cells")
                    for k, cell in enumerate(cells):
                        cell_text = ""
                        if hasattr(cell, 'get_text'):
                            cell_text = cell.get_text()
                        elif isinstance(cell, dict):
                            cell_text = cell.get("text", cell.get("content", ""))
                        else:
                            cell_text = str(cell)
                        print(f"            Cell {k+1}: {str(cell_text)[:100]}")
            elif block_type_in_content == "paragraph":
                text = content.get("text", content.get("content", ""))
                print(f"        Text: {str(text)[:100]}")
            else:
                print(f"        Content: {str(content)[:150]}")
        
        print(f"    Body blocks: {len(body_blocks)}")

if __name__ == "__main__":
    main()

