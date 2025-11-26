#!/usr/bin/env python3
"""
Porównuje oryginalny DOCX z DOCX wygenerowanym z JSON (round-trip).

Pokazuje co zostało utracone podczas konwersji DOCX → JSON → DOCX.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from docquill import Document
from docquill.parser import PackageReader, XMLParser


def extract_document_info(docx_path: Path) -> Dict[str, Any]:
    """Wyciąga informacje o dokumencie."""
    info = {
        'path': str(docx_path),
        'size': docx_path.stat().st_size if docx_path.exists() else 0,
        'paragraphs': [],
        'tables': [],
        'images': [],
        'headers': [],
        'footers': [],
        'styles': set(),
        'text_length': 0,
        'total_elements': 0
    }
    
    try:
        # Użyj bezpośrednio parsera zamiast Document API (bardziej niezawodne)
        from docquill.parser import PackageReader, XMLParser
        
        package_reader = PackageReader(docx_path)
        parser = XMLParser(package_reader)
        body = parser.parse_body()
        
        # Pobierz elementy z body.children (to jest główne źródło)
        elements = []
        if hasattr(body, 'children'):
            children_value = body.children
            # children jest listą z Models - zawsze konwertuj na listę
            if children_value is not None:
                elements = list(children_value) if not isinstance(children_value, list) else children_value
        elif hasattr(body, 'elements'):
            elements_value = body.elements
            if elements_value is not None:
                elements = list(elements_value) if not isinstance(elements_value, list) else elements_value
        
        # Pobierz też headers/footers
        headers_dict = {}
        footers_dict = {}
        if hasattr(parser, 'header_footer_parser'):
            hf_parser = parser.header_footer_parser
            if hasattr(hf_parser, 'parse_headers'):
                headers_dict = hf_parser.parse_headers() or {}
            if hasattr(hf_parser, 'parse_footers'):
                footers_dict = hf_parser.parse_footers() or {}
        
        # Upewnij się, że elements jest listą
        if elements and not isinstance(elements, (list, tuple)):
            try:
                elements = list(elements)
            except:
                try:
                    elements = [e for e in elements]
                except:
                    elements = []
        
        # Debug
        if not elements:
            print(f"⚠️ Brak elementów w body (type: {type(body)}, has children: {hasattr(body, 'children')})")
            if hasattr(body, 'children'):
                print(f"   body.children type: {type(body.children)}, len: {len(body.children) if hasattr(body.children, '__len__') else 'N/A'}")
        
        for element in elements:
            info['total_elements'] += 1
            
            # Sprawdź typ elementu
            elem_type = type(element).__name__.lower()
            has_runs = hasattr(element, 'runs')
            has_rows = hasattr(element, 'rows')
            has_get_text = hasattr(element, 'get_text')
            
            # Paragraph
            if 'paragraph' in elem_type or (has_runs and 'table' not in elem_type):
                para_info = {
                    'id': getattr(element, 'id', 'N/A'),
                    'text': '',
                    'style': getattr(element, 'style', {}),
                    'runs_count': 0
                }
                
                # Wyciągnij tekst
                if hasattr(element, 'get_text'):
                    para_info['text'] = element.get_text()
                elif hasattr(element, 'runs'):
                    para_info['runs_count'] = len(element.runs)
                    text_parts = []
                    for run in element.runs:
                        if hasattr(run, 'text'):
                            text_parts.append(run.text)
                    para_info['text'] = ' '.join(text_parts)
                elif hasattr(element, 'text'):
                    para_info['text'] = str(element.text)
                
                info['paragraphs'].append(para_info)
                info['text_length'] += len(para_info['text'])
                
                # Style
                if isinstance(para_info['style'], dict):
                    style_name = para_info['style'].get('style_name')
                    if style_name:
                        info['styles'].add(style_name)
            
            # Table
            elif 'table' in elem_type or hasattr(element, 'rows'):
                table_info = {
                    'id': getattr(element, 'id', 'N/A'),
                    'rows_count': len(element.rows) if hasattr(element, 'rows') else 0,
                    'cells_count': sum(len(row) for row in element.rows) if hasattr(element, 'rows') else 0
                }
                info['tables'].append(table_info)
        
        # Sprawdź też bezpośrednio body.paragraphs i body.tables (jeśli dostępne)
        if hasattr(body, 'paragraphs'):
            for para in body.paragraphs:
                if para not in elements:  # Unikaj duplikatów
                    para_info = {
                        'id': getattr(para, 'id', 'N/A'),
                        'text': para.get_text() if hasattr(para, 'get_text') else '',
                        'style': getattr(para, 'style', {}),
                        'runs_count': len(para.runs) if hasattr(para, 'runs') else 0
                    }
                    info['paragraphs'].append(para_info)
                    info['text_length'] += len(para_info['text'])
        
        if hasattr(body, 'tables'):
            for table in body.tables:
                if table not in elements:  # Unikaj duplikatów
                    table_info = {
                        'id': getattr(table, 'id', 'N/A'),
                        'rows_count': len(table.rows) if hasattr(table, 'rows') else 0,
                        'cells_count': sum(len(row) for row in table.rows) if hasattr(table, 'rows') else 0
                    }
                    info['tables'].append(table_info)
        
        # Headers/Footers - użyj z parsera jeśli dostępne
        if headers_dict:
            for header_type, headers in headers_dict.items():
                for header in headers:
                    if isinstance(header, dict):
                        header_info = {
                            'type': header_type,
                            'elements': len(header.get('content', []))
                        }
                    else:
                        header_info = {
                            'type': header_type,
                            'elements': len(getattr(header, 'children', []))
                        }
                    info['headers'].append(header_info)
        elif hasattr(model, 'headers'):
            for header_type, headers in model.headers.items():
                for header in headers:
                    header_info = {
                        'type': header_type,
                        'elements': len(getattr(header, 'children', []))
                    }
                    info['headers'].append(header_info)
        
        if footers_dict:
            for footer_type, footers in footers_dict.items():
                for footer in footers:
                    if isinstance(footer, dict):
                        footer_info = {
                            'type': footer_type,
                            'elements': len(footer.get('content', []))
                        }
                    else:
                        footer_info = {
                            'type': footer_type,
                            'elements': len(getattr(footer, 'children', []))
                        }
                    info['footers'].append(footer_info)
        elif hasattr(model, 'footers'):
            for footer_type, footers in model.footers.items():
                for footer in footers:
                    footer_info = {
                        'type': footer_type,
                        'elements': len(getattr(footer, 'children', []))
                    }
                    info['footers'].append(footer_info)
        
        info['styles'] = list(info['styles'])
        
    except Exception as e:
        info['error'] = str(e)
    
    return info


def compare_documents(original_path: Path, roundtrip_path: Path) -> Dict[str, Any]:
    """Porównuje dwa dokumenty."""
    print(f"📄 Analizowanie oryginalnego: {original_path}")
    original = extract_document_info(original_path)
    
    print(f"📄 Analizowanie round-trip: {roundtrip_path}")
    roundtrip = extract_document_info(roundtrip_path)
    
    comparison = {
        'original': original,
        'roundtrip': roundtrip,
        'differences': {}
    }
    
    # Porównaj podstawowe statystyki
    differences = comparison['differences']
    
    # Rozmiar pliku
    size_diff = roundtrip['size'] - original['size']
    size_diff_pct = (size_diff / original['size'] * 100) if original['size'] > 0 else 0
    differences['file_size'] = {
        'original': original['size'],
        'roundtrip': roundtrip['size'],
        'difference': size_diff,
        'difference_pct': round(size_diff_pct, 2)
    }
    
    # Liczba elementów
    differences['total_elements'] = {
        'original': original['total_elements'],
        'roundtrip': roundtrip['total_elements'],
        'lost': original['total_elements'] - roundtrip['total_elements']
    }
    
    # Paragrafy
    differences['paragraphs'] = {
        'original': len(original['paragraphs']),
        'roundtrip': len(roundtrip['paragraphs']),
        'lost': len(original['paragraphs']) - len(roundtrip['paragraphs'])
    }
    
    # Tabele
    differences['tables'] = {
        'original': len(original['tables']),
        'roundtrip': len(roundtrip['tables']),
        'lost': len(original['tables']) - len(roundtrip['tables'])
    }
    
    # Tekst
    text_diff = original['text_length'] - roundtrip['text_length']
    text_diff_pct = (text_diff / original['text_length'] * 100) if original['text_length'] > 0 else 0
    differences['text'] = {
        'original': original['text_length'],
        'roundtrip': roundtrip['text_length'],
        'lost': text_diff,
        'lost_pct': round(text_diff_pct, 2)
    }
    
    # Style
    original_styles = set(original['styles'])
    roundtrip_styles = set(roundtrip['styles'])
    differences['styles'] = {
        'original': len(original_styles),
        'roundtrip': len(roundtrip_styles),
        'lost': original_styles - roundtrip_styles,
        'gained': roundtrip_styles - original_styles
    }
    
    # Headers/Footers
    differences['headers'] = {
        'original': len(original['headers']),
        'roundtrip': len(roundtrip['headers']),
        'lost': len(original['headers']) - len(roundtrip['headers'])
    }
    
    differences['footers'] = {
        'original': len(original['footers']),
        'roundtrip': len(roundtrip['footers']),
        'lost': len(original['footers']) - len(roundtrip['footers'])
    }
    
    # Dodaj informacje o błędach
    if 'error' in original:
        differences['original_error'] = original['error']
    if 'error' in roundtrip:
        differences['roundtrip_error'] = roundtrip['error']
    
    # Porównaj paragrafy szczegółowo
    para_comparison = []
    max_compare = min(len(original['paragraphs']), len(roundtrip['paragraphs']), 20)
    for i in range(max_compare):
        orig_para = original['paragraphs'][i]
        rt_para = roundtrip['paragraphs'][i] if i < len(roundtrip['paragraphs']) else None
        
        if rt_para:
            para_diff = {
                'index': i,
                'original_text': orig_para['text'][:100],
                'roundtrip_text': rt_para['text'][:100],
                'text_match': orig_para['text'] == rt_para['text'],
                'text_length_diff': len(orig_para['text']) - len(rt_para['text']),
                'runs_diff': orig_para['runs_count'] - rt_para['runs_count']
            }
            para_comparison.append(para_diff)
    
    differences['paragraph_details'] = para_comparison
    
    return comparison


def print_comparison(comparison: Dict[str, Any]):
    """Wyświetla porównanie."""
    diff = comparison['differences']
    
    print("\n" + "="*80)
    print("📊 PORÓWNANIE ROUND-TRIP")
    print("="*80)
    
    # Rozmiar pliku
    print(f"\n📦 Rozmiar pliku:")
    print(f"   Oryginalny: {diff['file_size']['original']:,} bajtów")
    print(f"   Round-trip: {diff['file_size']['roundtrip']:,} bajtów")
    print(f"   Różnica: {diff['file_size']['difference']:+,} bajtów ({diff['file_size']['difference_pct']:+.2f}%)")
    
    # Elementy
    print(f"\n📋 Elementy:")
    print(f"   Oryginalny: {diff['total_elements']['original']} elementów")
    print(f"   Round-trip: {diff['total_elements']['roundtrip']} elementów")
    print(f"   Utracone: {diff['total_elements']['lost']} elementów")
    
    # Paragrafy
    print(f"\n📝 Paragrafy:")
    print(f"   Oryginalny: {diff['paragraphs']['original']} paragrafów")
    print(f"   Round-trip: {diff['paragraphs']['roundtrip']} paragrafów")
    print(f"   Utracone: {diff['paragraphs']['lost']} paragrafów")
    
    # Tabele
    print(f"\n📊 Tabele:")
    print(f"   Oryginalny: {diff['tables']['original']} tabel")
    print(f"   Round-trip: {diff['tables']['roundtrip']} tabel")
    print(f"   Utracone: {diff['tables']['lost']} tabel")
    
    # Tekst
    print(f"\n📄 Tekst:")
    print(f"   Oryginalny: {diff['text']['original']:,} znaków")
    print(f"   Round-trip: {diff['text']['roundtrip']:,} znaków")
    print(f"   Utracone: {diff['text']['lost']:,} znaków ({diff['text']['lost_pct']:.2f}%)")
    
    # Style
    print(f"\n🎨 Style:")
    print(f"   Oryginalny: {diff['styles']['original']} stylów")
    print(f"   Round-trip: {diff['styles']['roundtrip']} stylów")
    if diff['styles']['lost']:
        print(f"   Utracone style: {list(diff['styles']['lost'])[:10]}")
    if diff['styles']['gained']:
        print(f"   Dodane style: {list(diff['styles']['gained'])[:10]}")
    
    # Headers/Footers
    print(f"\n📑 Headers/Footers:")
    print(f"   Headers: {diff['headers']['original']} → {diff['headers']['roundtrip']} (utracone: {diff['headers']['lost']})")
    print(f"   Footers: {diff['footers']['original']} → {diff['footers']['roundtrip']} (utracone: {diff['footers']['lost']})")
    
    # Szczegóły paragrafów
    if diff['paragraph_details']:
        print(f"\n🔍 Szczegóły paragrafów (pierwsze 10):")
        matches = sum(1 for p in diff['paragraph_details'] if p['text_match'])
        print(f"   Zgodnych tekstów: {matches}/{len(diff['paragraph_details'])}")
        
        for para in diff['paragraph_details'][:5]:
            if not para['text_match']:
                print(f"\n   Paragraf {para['index']}:")
                print(f"      Oryginalny: {para['original_text']}...")
                print(f"      Round-trip: {para['roundtrip_text']}...")
                print(f"      Różnica długości: {para['text_length_diff']} znaków")
                print(f"      Różnica runs: {para['runs_diff']}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Porównuje DOCX przed i po round-trip')
    parser.add_argument('original_docx', type=str, help='Oryginalny plik DOCX')
    parser.add_argument('roundtrip_docx', type=str, help='DOCX wygenerowany z JSON (round-trip)')
    parser.add_argument('-o', '--output', type=str, help='Zapisz porównanie do JSON')
    
    args = parser.parse_args()
    
    original_path = Path(args.original_docx)
    roundtrip_path = Path(args.roundtrip_docx)
    
    if not original_path.exists():
        print(f"❌ Oryginalny plik nie istnieje: {original_path}")
        sys.exit(1)
    
    if not roundtrip_path.exists():
        print(f"❌ Round-trip plik nie istnieje: {roundtrip_path}")
        sys.exit(1)
    
    # Porównaj
    comparison = compare_documents(original_path, roundtrip_path)
    
    # Wyświetl
    print_comparison(comparison)
    
    # Zapisz do JSON jeśli podano
    if args.output:
        output_path = Path(args.output)
        # Konwertuj sets na lists dla JSON
        comparison_json = json.loads(json.dumps(comparison, default=str))
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(comparison_json, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Porównanie zapisane: {output_path}")


if __name__ == '__main__':
    main()

