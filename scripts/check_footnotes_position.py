#!/usr/bin/env python3
"""
Skrypt do sprawdzania gdzie lądują footnotes/endnotes w strukturze layoutu.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docquill.parser.package_reader import PackageReader
from docquill.parser.notes_parser import NotesParser
from docquill.parser.xml_parser import XMLParser
from docquill.engine.layout_pipeline import LayoutPipeline
from docquill.engine.geometry import Size, Margins
from docquill.engine.page_engine import PageConfig
import json


def main():
    """Sprawdź pozycjonowanie footnotes/endnotes."""
    doc_path = Path('tests/files/Zapytanie_Ofertowe_test.docx')
    if not doc_path.exists():
        doc_path = Path('tests/files/Zapytanie_Ofertowe.docx')
    
    if not doc_path.exists():
        print(f"❌ Dokument nie istnieje: {doc_path}")
        return
    
    print("=" * 80)
    print("ANALIZA POZYCJONOWANIA FOOTNOTES/ENDNOTES W LAYOUT")
    print("=" * 80)
    
    # 1. Parsuj footnotes/endnotes
    package_reader = PackageReader(doc_path)
    notes_parser = NotesParser(package_reader)
    footnotes = notes_parser.get_footnotes()
    endnotes = notes_parser.get_endnotes()
    
    print(f"\n📋 FOOTNOTES w parserze: {len(footnotes)}")
    print(f"📋 ENDNOTES w parserze: {len(endnotes)}")
    
    if not footnotes and not endnotes:
        print("\n⚠️  Dokument nie ma footnotes/endnotes - sprawdzam strukturę layoutu...")
    
    # 2. Zbuduj layout
    xml_parser = XMLParser(package_reader)
    body = xml_parser.parse_body()
    
    page_config = PageConfig(page_size=Size(595.28, 841.89), base_margins=Margins(50, 50, 50, 50))
    # Przekaż package_reader do assemblera przez page_config
    if hasattr(page_config, '__dict__'):
        page_config.__dict__['package_reader'] = package_reader
    
    pipeline = LayoutPipeline(page_config, target="pdf")
    unified = pipeline.process(body)
    
    # 3. Analizuj bloki
    dump_data = {
        'footnotes_in_parser': len(footnotes),
        'endnotes_in_parser': len(endnotes),
        'pages': []
    }
    
    for page in unified.pages:
        page_data = {
            'page_number': page.number,
            'page_height': page.size.height,
            'margins': {
                'top': page.margins.top,
                'bottom': page.margins.bottom,
                'left': page.margins.left,
                'right': page.margins.right,
            },
            'blocks': []
        }
        
        footnotes_blocks = []
        footer_blocks = []
        
        for block in page.blocks:
            block_data = {
                'block_type': block.block_type,
                'frame': {
                    'x': block.frame.x,
                    'y': block.frame.y,
                    'width': block.frame.width,
                    'height': block.frame.height,
                },
            }
            
            # Oblicz pozycje względem strony
            block_bottom_y = block.frame.y  # Od dołu strony (PDF coordinates)
            block_top_y = block.frame.y + block.frame.height  # Od dołu strony
            block_data['position_from_bottom'] = {
                'bottom_edge': block_bottom_y,
                'top_edge': block_top_y,
            }
            block_data['position_from_top'] = {
                'top_edge': page.size.height - block_top_y,
                'bottom_edge': page.size.height - block_bottom_y,
            }
            
            if block.block_type == 'footnotes':
                footnotes_blocks.append(block_data)
                content = block.content if isinstance(block.content, dict) else {}
                block_data['footnotes_count'] = len(content.get('footnotes', []))
                if content.get('footnotes'):
                    first_fn = content['footnotes'][0]
                    block_data['first_footnote'] = {
                        'id': first_fn.get('id', '?'),
                        'number': first_fn.get('number', '?'),
                        'content_preview': str(first_fn.get('content', ''))[:100],
                    }
            elif block.block_type == 'footer':
                footer_blocks.append(block_data)
            
            page_data['blocks'].append(block_data)
        
        page_data['footnotes_blocks'] = footnotes_blocks
        page_data['footer_blocks'] = footer_blocks
        
        dump_data['pages'].append(page_data)
        
        # Wyświetl analizę
        if footnotes_blocks or footer_blocks:
            print(f"\n📄 Page {page.number}:")
            print(f"   Page height: {page.size.height:.1f}pt")
            print(f"   Margins: top={page.margins.top:.1f}, bottom={page.margins.bottom:.1f}")
            
            if footer_blocks:
                for fb in footer_blocks:
                    bottom = fb['position_from_bottom']['bottom_edge']
                    top = fb['position_from_bottom']['top_edge']
                    print(f"\n   Footer block:")
                    print(f"     Bottom edge (from page bottom): {bottom:.1f}pt")
                    print(f"     Top edge (from page bottom): {top:.1f}pt")
                    print(f"     Height: {fb['frame']['height']:.1f}pt")
            
            if footnotes_blocks:
                for fnb in footnotes_blocks:
                    bottom = fnb['position_from_bottom']['bottom_edge']
                    top = fnb['position_from_bottom']['top_edge']
                    print(f"\n   Footnotes block:")
                    print(f"     Bottom edge (from page bottom): {bottom:.1f}pt")
                    print(f"     Top edge (from page bottom): {top:.1f}pt")
                    print(f"     Height: {fnb['frame']['height']:.1f}pt")
                    print(f"     Footnotes count: {fnb.get('footnotes_count', 0)}")
                    
                    if footer_blocks:
                        fb = footer_blocks[0]
                        footer_top = fb['position_from_bottom']['top_edge']
                        gap = bottom - footer_top
                        print(f"\n     Gap (footnotes bottom - footer top): {gap:.1f}pt")
                        if gap < 0:
                            print(f"     ⚠️  PROBLEM: Footnotes są POD footer!")
                        elif gap == 0:
                            print(f"     ✅ Footnotes są dokładnie nad footer")
                        else:
                            print(f"     ✅ Footnotes są nad footer")
            
            # Sprawdź wszystkie typy bloków
            block_types = {}
            for block in page.blocks:
                bt = block.block_type
                block_types[bt] = block_types.get(bt, 0) + 1
            
            print(f"\n   Block types on page: {dict(block_types)}")
    
    # Zapisz dump
    dump_path = Path('output/footnotes_position_analysis.json')
    dump_path.parent.mkdir(exist_ok=True)
    with open(dump_path, 'w', encoding='utf-8') as f:
        json.dump(dump_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n✅ Analiza zapisana do: {dump_path}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

