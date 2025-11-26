#!/usr/bin/env python3
"""
Eksportuje pipeline (UnifiedLayout) do JSON i ocenia przydatność dla analizy przez AI.

Używa Document API do przetworzenia dokumentu przez pipeline i wyeksportowania
UnifiedLayout do JSON formatu.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import asdict, is_dataclass

# Dodaj ścieżkę do projektu
sys.path.insert(0, str(Path(__file__).parent.parent))

from docx_interpreter import Document
from docx_interpreter.engine.unified_layout import UnifiedLayout, LayoutPage, LayoutBlock
from docx_interpreter.engine.geometry import Rect, Size, Margins
from docx_interpreter.engine.layout_pipeline import LayoutPipeline
from docx_interpreter.engine.page_engine import PageConfig
from docx_interpreter.parser.package_reader import PackageReader
from docx_interpreter.parser.xml_parser import XMLParser


def serialize_dataclass(obj: Any) -> Any:
    """Serializuje dataclass do dict, obsługując zagnieżdżone struktury."""
    if is_dataclass(obj):
        result = {}
        for field_name, field_value in obj.__dict__.items():
            result[field_name] = serialize_dataclass(field_value)
        return result
    elif isinstance(obj, (list, tuple)):
        return [serialize_dataclass(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: serialize_dataclass(value) for key, value in obj.items()}
    elif hasattr(obj, '__dict__'):
        # Dla obiektów które nie są dataclass, ale mają __dict__
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith('_'):
                result[key] = serialize_dataclass(value)
        return result
    else:
        # Podstawowe typy
        return obj


def unified_layout_to_dict(unified_layout: UnifiedLayout) -> Dict[str, Any]:
    """Konwertuje UnifiedLayout do słownika."""
    pages_data = []
    
    for page in unified_layout.pages:
        page_dict = {
            'page_number': page.number,
            'size': {
                'width': page.size.width,
                'height': page.size.height
            },
            'margins': {
                'top': page.margins.top,
                'bottom': page.margins.bottom,
                'left': page.margins.left,
                'right': page.margins.right
            },
            'skip_headers_footers': page.skip_headers_footers,
            'blocks': []
        }
        
        for block in page.blocks:
            block_dict = {
                'block_type': block.block_type,
                'page_number': block.page_number,
                'source_uid': block.source_uid,
                'sequence': block.sequence,
                'frame': {
                    'x': block.frame.x,
                    'y': block.frame.y,
                    'width': block.frame.width,
                    'height': block.frame.height
                },
                'style': serialize_content(block.style) if block.style else {},
                'content': serialize_content(block.content)
            }
            page_dict['blocks'].append(block_dict)
        
        pages_data.append(page_dict)
    
    return {
        'metadata': {
            'total_pages': len(unified_layout.pages),
            'current_page': unified_layout.current_page,
            'format_version': '1.0',
            'source': 'DocQuill LayoutPipeline'
        },
        'pages': pages_data
    }


def serialize_content(content: Any) -> Any:
    """Serializuje zawartość bloku (może być różnego typu)."""
    if content is None:
        return None
    
    if isinstance(content, str):
        return {'type': 'text', 'value': content}
    
    if isinstance(content, dict):
        # Jeśli to już dict, serializuj rekurencyjnie
        result = {}
        for key, value in content.items():
            result[key] = serialize_content(value)
        return result
    
    if isinstance(content, list):
        return [serialize_content(item) for item in content]
    
    # Obsługa BlockContent
    if hasattr(content, 'payload') and hasattr(content, 'raw'):
        # BlockContent ma payload i raw
        payload = content.payload
        raw = content.raw
        
        result = {
            'type': 'BlockContent',
            'payload': serialize_content(payload),
            'raw': serialize_content(raw)
        }
        
        # Spróbuj wyciągnąć tekst z payload
        if hasattr(payload, 'data') and isinstance(payload.data, dict):
            text = payload.data.get('text', '')
            if text:
                result['text'] = text
            result['data'] = serialize_content(payload.data)
        
        # Dla ParagraphLayout - wyciągnij tekst z linii
        if hasattr(payload, 'lines'):
            text_parts = []
            for line in payload.lines:
                if hasattr(line, 'items'):
                    for item in line.items:
                        if hasattr(item, 'data') and isinstance(item.data, dict):
                            item_text = item.data.get('text', '')
                            if item_text:
                                text_parts.append(item_text)
            if text_parts:
                result['text'] = ' '.join(text_parts)
        
        # Dla TableLayout - wyciągnij tekst z komórek
        if hasattr(payload, 'rows'):
            table_text = []
            for row in payload.rows:
                row_text = []
                for cell in row:
                    if hasattr(cell, 'blocks'):
                        for block in cell.blocks:
                            block_text = extract_text_from_block(block)
                            if block_text:
                                row_text.append(block_text)
                if row_text:
                    table_text.append(' | '.join(row_text))
            if table_text:
                result['table_text'] = table_text
        
        return result
    
    # Dla obiektów z payload (GenericLayout, ParagraphLayout, etc.)
    if hasattr(content, 'payload'):
        return serialize_content(content.payload)
    
    # Dla obiektów z data (GenericLayout)
    if hasattr(content, 'data'):
        data = content.data
        result = {'type': type(content).__name__}
        if isinstance(data, dict):
            result['data'] = serialize_content(data)
            # Wyciągnij tekst jeśli dostępny
            if 'text' in data:
                result['text'] = data['text']
        return result
    
    # Dla obiektów - spróbuj wyciągnąć tekst lub serializować
    if hasattr(content, 'get_text'):
        text = content.get_text()
        return {'type': type(content).__name__, 'text': text}
    
    if hasattr(content, '__dict__'):
        result = {'type': type(content).__name__}
        for key, value in content.__dict__.items():
            if not key.startswith('_'):
                result[key] = serialize_content(value)
        return result
    
    return str(content)


def extract_text_from_block(block: Any) -> str:
    """Wyciąga tekst z bloku (ParagraphLayout, GenericLayout, etc.)."""
    if block is None:
        return ""
    
    # Dla ParagraphLayout
    if hasattr(block, 'lines'):
        text_parts = []
        for line in block.lines:
            if hasattr(line, 'items'):
                for item in line.items:
                    if hasattr(item, 'data') and isinstance(item.data, dict):
                        text = item.data.get('text', '')
                        if text:
                            text_parts.append(text)
        return ' '.join(text_parts)
    
    # Dla GenericLayout
    if hasattr(block, 'data') and isinstance(block.data, dict):
        return block.data.get('text', '')
    
    # Dla dict
    if isinstance(block, dict):
        return block.get('text', '')
    
    return ""


def analyze_ai_readiness(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analizuje JSON pod kątem przydatności dla analizy przez AI."""
    analysis = {
        'overall_score': 0,
        'strengths': [],
        'weaknesses': [],
        'recommendations': [],
        'structure_analysis': {},
        'content_analysis': {}
    }
    
    # Sprawdź czy to zoptymalizowana wersja (v2.0)
    is_optimized = json_data.get('version') == '2.0' or json_data.get('format') == 'optimized_pipeline'
    
    # Analiza struktury
    structure_score = 0
    structure_notes = []
    
    # 1. Hierarchiczna struktura
    if 'pages' in json_data and isinstance(json_data['pages'], list):
        structure_score += 2
        structure_notes.append("✅ Hierarchiczna struktura (pages → blocks)")
    else:
        structure_notes.append("❌ Brak hierarchicznej struktury")
    
    # 2. Metadata
    if 'metadata' in json_data:
        structure_score += 1
        structure_notes.append("✅ Metadata dostępna")
    else:
        structure_notes.append("⚠️ Brak metadata")
    
    # 3. Typy elementów
    if 'pages' in json_data:
        block_types = set()
        for page in json_data['pages']:
            if 'blocks' in page:
                for block in page['blocks']:
                    # Obsługa zarówno starej jak i nowej struktury
                    block_type = block.get('block_type') or block.get('t', 'unknown')
                    if block_type != 'unknown':
                        block_types.add(block_type)
        
        if len(block_types) > 0:
            structure_score += 1
            structure_notes.append(f"✅ Różnorodne typy bloków: {', '.join(sorted(block_types))}")
    
    # 4. Pozycjonowanie
    has_positioning = False
    if 'pages' in json_data:
        for page in json_data['pages']:
            if 'blocks' in page:
                for block in page['blocks']:
                    # Obsługa zarówno starej jak i nowej struktury (frame lub f)
                    if 'frame' in block or 'f' in block:
                        has_positioning = True
                        break
    
    if has_positioning:
        structure_score += 2
        structure_notes.append("✅ Informacje o pozycjonowaniu (frame)")
    else:
        structure_notes.append("❌ Brak informacji o pozycjonowaniu")
    
    # 5. Stylowanie
    has_styling = False
    if 'pages' in json_data:
        for page in json_data['pages']:
            if 'blocks' in page:
                for block in page['blocks']:
                    # Obsługa zarówno starej jak i nowej struktury (style, s, lub styles w root)
                    if 'style' in block and block['style']:
                        has_styling = True
                        break
                    elif 's' in block and block['s'] is not None:
                        has_styling = True
                        break
        
        # Sprawdź czy są style w root
        if 'styles' in json_data and len(json_data['styles']) > 0:
            has_styling = True
    
    if has_styling:
        structure_score += 1
        structure_notes.append("✅ Informacje o stylowaniu (z deduplikacją)")
    else:
        structure_notes.append("⚠️ Ograniczone informacje o stylowaniu")
    
    analysis['structure_analysis'] = {
        'score': structure_score,
        'max_score': 7,
        'notes': structure_notes
    }
    
    # Analiza zawartości
    content_score = 0
    content_notes = []
    
    # 1. Tekst
    text_blocks = 0
    total_text_length = 0
    
    if 'pages' in json_data:
        for page in json_data['pages']:
            if 'blocks' in page:
                for block in page['blocks']:
                    # Obsługa zarówno starej jak i nowej struktury (content lub c)
                    content = block.get('content') or block.get('c', {})
                    if isinstance(content, dict):
                        # Rekurencyjne wyszukiwanie tekstu
                        def extract_text(obj, depth=0):
                            if depth > 3:
                                return ''
                            if isinstance(obj, str):
                                return obj
                            if isinstance(obj, dict):
                                if 'text' in obj:
                                    text = obj['text']
                                    if isinstance(text, str) and text:
                                        return text
                                # Rekurencyjnie przeszukaj
                                for v in obj.values():
                                    result = extract_text(v, depth + 1)
                                    if result:
                                        return result
                            if isinstance(obj, list):
                                for item in obj:
                                    result = extract_text(item, depth + 1)
                                    if result:
                                        return result
                            return ''
                        
                        text = extract_text(content)
                        if text:
                            text_blocks += 1
                            total_text_length += len(text)
                    elif isinstance(content, str):
                        text_blocks += 1
                        total_text_length += len(content)
    
    if text_blocks > 0:
        content_score += 2
        content_notes.append(f"✅ Tekst dostępny ({text_blocks} bloków, {total_text_length} znaków)")
    else:
        content_notes.append("❌ Brak tekstu w blokach")
    
    # 2. Tabele
    table_blocks = 0
    if 'pages' in json_data:
        for page in json_data['pages']:
            if 'blocks' in page:
                for block in page['blocks']:
                    # Obsługa zarówno starej jak i nowej struktury
                    block_type = block.get('block_type') or block.get('t', '')
                    if block_type == 'table':
                        table_blocks += 1
    
    if table_blocks > 0:
        content_score += 1
        content_notes.append(f"✅ Tabele dostępne ({table_blocks} tabel)")
    else:
        content_notes.append("⚠️ Brak tabel")
    
    # 3. Obrazy i media
    image_blocks = 0
    blocks_with_media = 0
    media_count = 0
    
    # Sprawdź sekcję media
    if 'media' in json_data and len(json_data['media']) > 0:
        media_count = len(json_data['media'])
        # Policz bloki z referencją do media (pole 'm')
        if 'pages' in json_data:
            for page in json_data['pages']:
                if 'blocks' in page:
                    for block in page['blocks']:
                        # Obsługa zarówno starej jak i nowej struktury
                        block_type = block.get('block_type') or block.get('t', '')
                        if block_type in ('image', 'drawing'):
                            image_blocks += 1
                        # Sprawdź referencję do media (pole 'm')
                        if 'm' in block or 'media_id' in block:
                            blocks_with_media += 1
    
    if media_count > 0 or blocks_with_media > 0 or image_blocks > 0:
        content_score += 1
        if media_count > 0:
            content_notes.append(f"✅ Obrazy dostępne (sekcja media: {media_count} obrazów, {blocks_with_media} referencji)")
        elif image_blocks > 0:
            content_notes.append(f"✅ Obrazy dostępne ({image_blocks} bloków obrazów)")
        else:
            content_notes.append(f"✅ Obrazy dostępne ({blocks_with_media} referencji do media)")
    else:
        content_notes.append("⚠️ Brak obrazów")
    
    # 4. Struktura semantyczna
    has_semantic_structure = False
    if 'pages' in json_data:
        for page in json_data['pages']:
            if 'blocks' in page:
                for block in page['blocks']:
                    # Obsługa zarówno starej jak i nowej struktury
                    if (block.get('source_uid') or block.get('uid') or 
                        block.get('sequence') is not None or block.get('seq') is not None):
                        has_semantic_structure = True
                        break
    
    if has_semantic_structure:
        content_score += 1
        content_notes.append("✅ Struktura semantyczna (source_uid, sequence)")
    else:
        content_notes.append("⚠️ Ograniczona struktura semantyczna")
    
    analysis['content_analysis'] = {
        'score': content_score,
        'max_score': 5,
        'notes': content_notes,
        'statistics': {
            'text_blocks': text_blocks,
            'total_text_length': total_text_length,
            'table_blocks': table_blocks,
            'image_blocks': image_blocks,
            'media_count': media_count,
            'blocks_with_media': blocks_with_media
        }
    }
    
    # Dodatkowa analiza struktury dokumentu
    structure_notes = analysis['structure_analysis']['notes']
    
    # Sprawdź mapowanie header/footer
    pages_with_headers = 0
    pages_with_footers = 0
    if 'pages' in json_data:
        for page in json_data['pages']:
            if 'h' in page and len(page['h']) > 0:
                pages_with_headers += 1
            if 'f' in page and len(page['f']) > 0:
                pages_with_footers += 1
    
    if pages_with_headers > 0 or pages_with_footers > 0:
        structure_notes.append(f"✅ Mapowanie header/footer ({pages_with_headers} stron z headerami, {pages_with_footers} z footerami)")
    
    # Sprawdź sekcję media
    if 'media' in json_data and len(json_data['media']) > 0:
        structure_notes.append(f"✅ Sekcja media z deduplikacją ({len(json_data['media'])} obrazów)")
    
    # Sprawdź sekcję styles
    if 'styles' in json_data and len(json_data['styles']) > 0:
        structure_notes.append(f"✅ Sekcja styles z deduplikacją ({len(json_data['styles'])} stylów)")
    
    analysis['structure_analysis']['notes'] = structure_notes
    
    # Obliczanie ogólnego wyniku
    total_score = structure_score + content_score
    max_total_score = 12
    overall_score = (total_score / max_total_score) * 10
    
    analysis['overall_score'] = round(overall_score, 1)
    
    # Mocne strony
    if structure_score >= 5:
        analysis['strengths'].append("Dobra struktura hierarchiczna")
    if has_positioning:
        analysis['strengths'].append("Pełne informacje o pozycjonowaniu")
    if text_blocks > 0:
        analysis['strengths'].append("Dostępny tekst do analizy")
    if has_styling:
        analysis['strengths'].append("Informacje o stylowaniu")
    
    # Słabe strony
    if structure_score < 4:
        analysis['weaknesses'].append("Ograniczona struktura danych")
    if not has_positioning:
        analysis['weaknesses'].append("Brak informacji o pozycjonowaniu")
    if text_blocks == 0:
        analysis['weaknesses'].append("Brak tekstu do analizy")
    if not has_styling:
        analysis['weaknesses'].append("Ograniczone informacje o stylowaniu")
    
    # Rekomendacje
    if overall_score >= 8:
        analysis['recommendations'].append("✅ JSON jest bardzo dobrze przygotowany do analizy przez AI")
    elif overall_score >= 6:
        analysis['recommendations'].append("✅ JSON jest dobrze przygotowany, ale można ulepszyć")
    else:
        analysis['recommendations'].append("⚠️ JSON wymaga ulepszeń dla lepszej analizy AI")
    
    if not has_positioning:
        analysis['recommendations'].append("Dodaj więcej informacji o pozycjonowaniu elementów")
    
    if text_blocks == 0:
        analysis['recommendations'].append("Upewnij się, że tekst jest dostępny w blokach")
    
    if not has_styling:
        analysis['recommendations'].append("Dodaj więcej informacji o stylowaniu (kolory, czcionki, formatowanie)")
    
    analysis['recommendations'].append("Rozważ dodanie metadanych o strukturze dokumentu (nagłówki, sekcje)")
    analysis['recommendations'].append("Rozważ dodanie informacji o relacjach między elementami")
    
    return analysis


def main():
    """Główna funkcja skryptu."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Eksportuje pipeline (UnifiedLayout) do JSON i ocenia przydatność dla AI"
    )
    parser.add_argument(
        'docx_file',
        type=str,
        help='Ścieżka do pliku DOCX'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Ścieżka do pliku wyjściowego JSON (domyślnie: <nazwa_dokumentu>_pipeline.json)'
    )
    parser.add_argument(
        '--analysis',
        action='store_true',
        help='Wygeneruj również plik z analizą przydatności dla AI'
    )
    parser.add_argument(
        '--optimized',
        action='store_true',
        default=True,
        help='Użyj zoptymalizowanej wersji JSON (deduplikacja stylów, kompaktowa struktura)'
    )
    parser.add_argument(
        '--include-raw',
        action='store_true',
        help='Dołącz surowe dane content (zwiększa rozmiar)'
    )
    
    args = parser.parse_args()
    
    docx_path = Path(args.docx_file)
    if not docx_path.exists():
        print(f"❌ Plik nie znaleziony: {docx_path}")
        sys.exit(1)
    
    # Określ ścieżkę wyjściową
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = docx_path.parent / f"{docx_path.stem}_pipeline.json"
    
    print(f"📄 Otwieranie dokumentu: {docx_path}")
    
    try:
        # Otwórz dokument przez API
        doc = Document(docx_path)
        
        print("🔄 Przetwarzanie przez pipeline i eksport do JSON...")
        
        # Użyj nowego API do eksportu JSON
        json_data = doc.to_json(
            output_path=output_path,
            optimized=args.optimized,
            include_raw_content=args.include_raw
        )
        
        print(f"✅ JSON wygenerowany: {output_path}")
        if output_path.exists():
            print(f"   Rozmiar: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        # Analiza przydatności dla AI
        if args.analysis:
            print("\n🤖 Analiza przydatności dla AI...")
            analysis = analyze_ai_readiness(json_data)
            
            analysis_path = output_path.parent / f"{output_path.stem}_ai_analysis.json"
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            
            print(f"\n📊 Wyniki analizy:")
            print(f"   Ogólna ocena: {analysis['overall_score']}/10")
            print(f"   Struktura: {analysis['structure_analysis']['score']}/{analysis['structure_analysis']['max_score']}")
            print(f"   Zawartość: {analysis['content_analysis']['score']}/{analysis['content_analysis']['max_score']}")
            
            if analysis['strengths']:
                print(f"\n✅ Mocne strony:")
                for strength in analysis['strengths']:
                    print(f"   - {strength}")
            
            if analysis['weaknesses']:
                print(f"\n⚠️ Słabe strony:")
                for weakness in analysis['weaknesses']:
                    print(f"   - {weakness}")
            
            if analysis['recommendations']:
                print(f"\n💡 Rekomendacje:")
                for rec in analysis['recommendations']:
                    print(f"   - {rec}")
            
            print(f"\n💾 Analiza zapisana: {analysis_path}")
        
        # Podsumowanie
        print(f"\n📈 Statystyki:")
        print(f"   Stron: {len(json_data['pages'])}")
        total_blocks = sum(len(page.get('blocks', [])) for page in json_data['pages'])
        print(f"   Bloków: {total_blocks}")
        
        block_types = {}
        for page in json_data['pages']:
            for block in page.get('blocks', []):
                # Obsługa zarówno starej jak i nowej struktury
                block_type = block.get('block_type') or block.get('t', 'unknown')
                block_types[block_type] = block_types.get(block_type, 0) + 1
        
        if block_types:
            print(f"   Typy bloków:")
            for block_type, count in sorted(block_types.items()):
                print(f"     - {block_type}: {count}")
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

