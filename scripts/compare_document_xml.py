"""
Porównuje oryginalny word/document.xml z wygenerowanym.
Normalizuje pliki XML, aby uniknąć różnic w formatowaniu.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import zipfile
from typing import Dict, List, Tuple, Set
from collections import defaultdict


def normalize_xml(xml_content: bytes) -> ET.Element:
    """Normalizuje XML - parsuje i zwraca root element."""
    try:
        root = ET.fromstring(xml_content)
        return root
    except ET.ParseError as e:
        print(f"❌ Błąd parsowania XML: {e}")
        return None


def normalize_attributes(elem: ET.Element) -> Dict[str, str]:
    """Zwraca posortowane atrybuty elementu."""
    return dict(sorted(elem.attrib.items()))


def get_element_path(elem: ET.Element, path: str = "") -> str:
    """Zwraca ścieżkę XPath do elementu."""
    if path:
        return f"{path}/{elem.tag}"
    return elem.tag


def normalize_tag(tag: str) -> str:
    """Normalizuje tag XML (usuwa namespace jeśli jest w nawiasach)."""
    if '}' in tag:
        return tag.split('}')[1]
    return tag


def compare_elements(
    elem1: ET.Element,
    elem2: ET.Element,
    path: str = "",
    differences: List[str] = None
) -> bool:
    """Porównuje dwa elementy XML rekurencyjnie."""
    if differences is None:
        differences = []
    
    path1 = get_element_path(elem1, path)
    path2 = get_element_path(elem2, path)
    
    # Porównaj tagi (znormalizowane)
    tag1 = normalize_tag(elem1.tag)
    tag2 = normalize_tag(elem2.tag)
    
    if tag1 != tag2:
        differences.append(f"❌ Różne tagi w {path}: '{tag1}' vs '{tag2}'")
        return False
    
    # Porównaj atrybuty
    attrs1 = normalize_attributes(elem1)
    attrs2 = normalize_attributes(elem2)
    
    if attrs1 != attrs2:
        missing_in_2 = set(attrs1.keys()) - set(attrs2.keys())
        missing_in_1 = set(attrs2.keys()) - set(attrs1.keys())
        different_values = {
            k: (attrs1[k], attrs2[k])
            for k in set(attrs1.keys()) & set(attrs2.keys())
            if attrs1[k] != attrs2[k]
        }
        
        if missing_in_2:
            differences.append(f"⚠️ Brakujące atrybuty w elem2 {path}: {missing_in_2}")
        if missing_in_1:
            differences.append(f"⚠️ Dodatkowe atrybuty w elem2 {path}: {missing_in_1}")
        if different_values:
            for k, (v1, v2) in different_values.items():
                differences.append(f"⚠️ Różne wartości atrybutu {k} w {path}: '{v1}' vs '{v2}'")
    
    # Porównaj tekst
    text1 = (elem1.text or "").strip()
    text2 = (elem2.text or "").strip()
    if text1 != text2:
        # Ignoruj różnice w białych znakach, ale raportuj różnice w treści
        if text1 and text2:
            differences.append(f"⚠️ Różny tekst w {path}: '{text1[:50]}...' vs '{text2[:50]}...'")
    
    # Porównaj tail
    tail1 = (elem1.tail or "").strip()
    tail2 = (elem2.tail or "").strip()
    if tail1 != tail2:
        # Ignoruj różnice w tail (zwykle białe znaki)
        pass
    
    # Porównaj dzieci
    children1 = list(elem1)
    children2 = list(elem2)
    
    if len(children1) != len(children2):
        differences.append(
            f"❌ Różna liczba dzieci w {path}: {len(children1)} vs {len(children2)}"
        )
        # Porównaj te, które się zgadzają
        min_len = min(len(children1), len(children2))
        for i in range(min_len):
            compare_elements(children1[i], children2[i], f"{path}/{tag1}[{i}]", differences)
        return False
    
    # Porównaj wszystkie dzieci
    all_match = True
    for i, (child1, child2) in enumerate(zip(children1, children2)):
        if not compare_elements(child1, child2, f"{path}/{tag1}[{i}]", differences):
            all_match = False
    
    return all_match and attrs1 == attrs2 and text1 == text2


def get_element_statistics(root: ET.Element, stats: Dict[str, int] = None) -> Dict[str, int]:
    """Zbiera statystyki o elementach XML."""
    if stats is None:
        stats = defaultdict(int)
    
    tag = normalize_tag(root.tag)
    stats[tag] += 1
    
    for child in root:
        get_element_statistics(child, stats)
    
    return stats


def compare_document_xml(original_docx: Path, generated_docx: Path) -> None:
    """Porównuje word/document.xml z dwóch plików DOCX."""
    print("=" * 80)
    print("PORÓWNANIE word/document.xml")
    print("=" * 80)
    print()
    
    # Wczytaj oba pliki
    try:
        with zipfile.ZipFile(original_docx, 'r') as orig_zip:
            orig_xml = orig_zip.read('word/document.xml')
        
        with zipfile.ZipFile(generated_docx, 'r') as gen_zip:
            gen_xml = gen_zip.read('word/document.xml')
    except KeyError as e:
        print(f"❌ Błąd: Nie znaleziono word/document.xml w jednym z plików: {e}")
        return
    except Exception as e:
        print(f"❌ Błąd podczas wczytywania plików: {e}")
        return
    
    print(f"📄 Oryginalny: {original_docx.name}")
    print(f"   Rozmiar XML: {len(orig_xml):,} bajtów")
    print(f"📄 Wygenerowany: {generated_docx.name}")
    print(f"   Rozmiar XML: {len(gen_xml):,} bajtów")
    print()
    
    # Parsuj XML
    orig_root = normalize_xml(orig_xml)
    gen_root = normalize_xml(gen_xml)
    
    if orig_root is None or gen_root is None:
        print("❌ Nie można sparsować jednego z plików XML")
        return
    
    # Statystyki
    print("=" * 80)
    print("STATYSTYKI ELEMENTÓW")
    print("=" * 80)
    print()
    
    orig_stats = get_element_statistics(orig_root)
    gen_stats = get_element_statistics(gen_root)
    
    all_tags = sorted(set(orig_stats.keys()) | set(gen_stats.keys()))
    
    print(f"{'Tag':<40} {'Oryginalny':<15} {'Wygenerowany':<15} {'Status':<10}")
    print("-" * 80)
    
    for tag in all_tags:
        orig_count = orig_stats.get(tag, 0)
        gen_count = gen_stats.get(tag, 0)
        status = "✅" if orig_count == gen_count else "⚠️"
        print(f"{tag:<40} {orig_count:<15} {gen_count:<15} {status:<10}")
    
    print()
    
    # Porównanie strukturalne
    print("=" * 80)
    print("PORÓWNANIE STRUKTURALNE")
    print("=" * 80)
    print()
    
    differences = []
    is_identical = compare_elements(orig_root, gen_root, "", differences)
    
    if is_identical:
        print("✅ Pliki XML są identyczne strukturalnie i semantycznie!")
    else:
        print(f"⚠️ Znaleziono {len(differences)} różnic:")
        print()
        for i, diff in enumerate(differences[:50], 1):  # Pokaż pierwsze 50 różnic
            print(f"{i}. {diff}")
        
        if len(differences) > 50:
            print(f"\n... i {len(differences) - 50} więcej różnic")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Użycie: python compare_document_xml.py <oryginalny.docx> <wygenerowany.docx>")
        sys.exit(1)
    
    original_docx = Path(sys.argv[1])
    generated_docx = Path(sys.argv[2])
    
    if not original_docx.exists():
        print(f"❌ Nie znaleziono pliku: {original_docx}")
        sys.exit(1)
    
    if not generated_docx.exists():
        print(f"❌ Nie znaleziono pliku: {generated_docx}")
        sys.exit(1)
    
    compare_document_xml(original_docx, generated_docx)

