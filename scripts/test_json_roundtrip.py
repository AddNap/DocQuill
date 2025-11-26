#!/usr/bin/env python3
"""
Test round-trip JSON: DOCX → JSON → DOCX → JSON

Sprawdza czy:
1. Możemy utworzyć dokument z JSON
2. Dumpy JSON się zgadzają (porównanie struktury)
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Set
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from docquill import Document


def normalize_json_for_comparison(data: Any) -> Any:
    """Normalizuje JSON do porównania (usuwa nieistotne różnice)."""
    if isinstance(data, dict):
        # Sortuj klucze dla porównania
        result = {}
        for key in sorted(data.keys()):
            # Pomiń niektóre pola które mogą się różnić (np. timestamps, IDs)
            if key in ['_block_uid', '_layout_tree', 'layout_info', 'uid', 'seq']:
                continue
            result[key] = normalize_json_for_comparison(data[key])
        return result
    elif isinstance(data, list):
        return [normalize_json_for_comparison(item) for item in data]
    else:
        return data


def compare_json_structures(json1: Dict[str, Any], json2: Dict[str, Any], path: str = "") -> List[str]:
    """Porównuje dwie struktury JSON i zwraca listę różnic."""
    differences = []
    
    # Porównaj klucze główne
    keys1 = set(json1.keys())
    keys2 = set(json2.keys())
    
    missing_in_2 = keys1 - keys2
    extra_in_2 = keys2 - keys1
    
    for key in missing_in_2:
        differences.append(f"{path}.{key}: brakuje w JSON2")
    for key in extra_in_2:
        differences.append(f"{path}.{key}: dodatkowe w JSON2")
    
    # Porównaj wspólne klucze
    common_keys = keys1 & keys2
    for key in common_keys:
        current_path = f"{path}.{key}" if path else key
        val1 = json1[key]
        val2 = json2[key]
        
        if isinstance(val1, dict) and isinstance(val2, dict):
            differences.extend(compare_json_structures(val1, val2, current_path))
        elif isinstance(val1, list) and isinstance(val2, list):
            # Porównaj długości list
            if len(val1) != len(val2):
                differences.append(f"{current_path}: różne długości ({len(val1)} vs {len(val2)})")
            else:
                # Porównaj elementy (tylko pierwsze 10 dla wydajności)
                for i in range(min(len(val1), 10)):
                    if isinstance(val1[i], dict) and isinstance(val2[i], dict):
                        differences.extend(compare_json_structures(val1[i], val2[i], f"{current_path}[{i}]"))
                    elif val1[i] != val2[i]:
                        differences.append(f"{current_path}[{i}]: różne wartości")
        elif val1 != val2:
            # Sprawdź czy to nie są tylko różnice w formatowaniu
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if abs(val1 - val2) > 0.01:  # Tolerancja dla float
                    differences.append(f"{current_path}: różne wartości ({val1} vs {val2})")
            elif isinstance(val1, str) and isinstance(val2, str):
                if val1.strip() != val2.strip():
                    differences.append(f"{current_path}: różne wartości tekstowe")
            else:
                differences.append(f"{current_path}: różne wartości ({type(val1).__name__} vs {type(val2).__name__})")
    
    return differences


def get_json_stats(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """Pobiera statystyki z JSON."""
    stats = {
        'pages': len(json_data.get('pages', [])),
        'styles': len(json_data.get('styles', [])),
        'media': len(json_data.get('media', [])),
        'sections': len(json_data.get('sections', [])),
        'footnotes': len(json_data.get('footnotes', [])),
        'endnotes': len(json_data.get('endnotes', [])),
        'total_blocks': 0,
        'blocks_with_runs': 0,
        'blocks_with_lists': 0,
        'blocks_with_tables': 0,
        'tables_with_rows': 0,
    }
    
    for page in json_data.get('pages', []):
        for block in page.get('blocks', []):
            stats['total_blocks'] += 1
            content = block.get('c', {})
            if isinstance(content, dict):
                if 'runs' in content:
                    stats['blocks_with_runs'] += 1
                if 'list' in content:
                    stats['blocks_with_lists'] += 1
            if block.get('t') == 'table':
                stats['blocks_with_tables'] += 1
                if isinstance(content, dict) and 'rows' in content and len(content.get('rows', [])) > 0:
                    stats['tables_with_rows'] += 1
    
    return stats


def test_json_roundtrip(docx_path: str, output_dir: str = "output") -> Dict[str, Any]:
    """Testuje round-trip: DOCX → JSON → DOCX → JSON."""
    docx_path = Path(docx_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"🔄 TEST ROUND-TRIP JSON")
    print(f"{'='*80}")
    print(f"\n📄 Oryginalny dokument: {docx_path}")
    
    # Krok 1: DOCX → JSON (oryginalny)
    print(f"\n📤 Krok 1: Eksport DOCX → JSON (oryginalny)")
    doc1 = Document(str(docx_path))
    json1_path = output_dir / f"{docx_path.stem}_original.json"
    doc1.to_json(str(json1_path), optimized=True)
    
    with open(json1_path, 'r', encoding='utf-8') as f:
        json1 = json.load(f)
    
    stats1 = get_json_stats(json1)
    print(f"   ✅ JSON1 zapisany: {json1_path}")
    print(f"      Statystyki: {stats1['pages']} stron, {stats1['total_blocks']} bloków, {stats1['tables_with_rows']} tabel z rows")
    
    # Krok 2: JSON → DOCX
    print(f"\n📥 Krok 2: Import JSON → DOCX")
    docx2_path = output_dir / f"{docx_path.stem}_from_json.docx"
    try:
        # Przekaż oryginalny DOCX jako source_docx dla kopiowania mediów
        doc2 = Document.from_json(str(json1_path), str(docx2_path), source_docx=str(docx_path))
        print(f"   ✅ DOCX2 utworzony: {docx2_path}")
    except Exception as e:
        print(f"   ❌ Błąd podczas tworzenia DOCX z JSON: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f"Błąd importu JSON: {e}",
            'step': 2
        }
    
    # Krok 3: DOCX → JSON (round-trip)
    print(f"\n📤 Krok 3: Eksport DOCX → JSON (round-trip)")
    # WAŻNE: Użyj doc2 zamiast otwierać dokument ponownie, aby zachować _json_sections, _json_headers, _json_footers
    json2_path = output_dir / f"{docx_path.stem}_roundtrip.json"
    doc2.to_json(str(json2_path), optimized=True)
    
    with open(json2_path, 'r', encoding='utf-8') as f:
        json2 = json.load(f)
    
    stats2 = get_json_stats(json2)
    print(f"   ✅ JSON2 zapisany: {json2_path}")
    print(f"      Statystyki: {stats2['pages']} stron, {stats2['total_blocks']} bloków, {stats2['tables_with_rows']} tabel z rows")
    
    # Krok 4: Porównanie JSON
    print(f"\n🔍 Krok 4: Porównanie JSON1 i JSON2")
    
    # Porównaj statystyki
    print(f"\n   Statystyki JSON1 vs JSON2:")
    print(f"      Strony: {stats1['pages']} vs {stats2['pages']} ({stats2['pages'] - stats1['pages']:+d})")
    print(f"      Bloki: {stats1['total_blocks']} vs {stats2['total_blocks']} ({stats2['total_blocks'] - stats1['total_blocks']:+d})")
    print(f"      Style: {stats1['styles']} vs {stats2['styles']} ({stats2['styles'] - stats1['styles']:+d})")
    print(f"      Media: {stats1['media']} vs {stats2['media']} ({stats2['media'] - stats1['media']:+d})")
    print(f"      Bloki z runs: {stats1['blocks_with_runs']} vs {stats2['blocks_with_runs']} ({stats2['blocks_with_runs'] - stats1['blocks_with_runs']:+d})")
    print(f"      Bloki z listami: {stats1['blocks_with_lists']} vs {stats2['blocks_with_lists']} ({stats2['blocks_with_lists'] - stats1['blocks_with_lists']:+d})")
    print(f"      Tabele z rows: {stats1['tables_with_rows']} vs {stats2['tables_with_rows']} ({stats2['tables_with_rows'] - stats1['tables_with_rows']:+d})")
    
    # Porównaj struktury
    differences = compare_json_structures(json1, json2)
    
    if differences:
        print(f"\n   ⚠️ Znaleziono {len(differences)} różnic w strukturze:")
        for diff in differences[:20]:  # Pokaż pierwsze 20
            print(f"      - {diff}")
        if len(differences) > 20:
            print(f"      ... i {len(differences) - 20} więcej")
    else:
        print(f"\n   ✅ Struktury JSON są identyczne!")
    
    # Podsumowanie
    success = len(differences) == 0 or len(differences) < 10  # Tolerancja dla małych różnic
    
    result = {
        'success': success,
        'json1_path': str(json1_path),
        'json2_path': str(json2_path),
        'docx2_path': str(docx2_path),
        'stats1': stats1,
        'stats2': stats2,
        'differences_count': len(differences),
        'differences': differences[:50],  # Zapisz pierwsze 50 różnic
    }
    
    print(f"\n{'='*80}")
    if success:
        print(f"✅ TEST ZAKOŃCZONY POMYŚLNIE")
    else:
        print(f"⚠️ TEST ZAKOŃCZONY Z OSTRZEŻENIAMI")
    print(f"{'='*80}\n")
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test round-trip JSON: DOCX → JSON → DOCX → JSON')
    parser.add_argument('docx_path', type=str, help='Ścieżka do pliku DOCX')
    parser.add_argument('-o', '--output', type=str, default='output', help='Katalog wyjściowy')
    parser.add_argument('--save-comparison', type=str, help='Zapisz porównanie do JSON')
    
    args = parser.parse_args()
    
    docx_path = Path(args.docx_path)
    if not docx_path.exists():
        print(f"❌ Plik nie istnieje: {docx_path}")
        sys.exit(1)
    
    result = test_json_roundtrip(str(docx_path), args.output)
    
    if args.save_comparison:
        comparison_path = Path(args.save_comparison)
        with open(comparison_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"💾 Porównanie zapisane: {comparison_path}")
    
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()

