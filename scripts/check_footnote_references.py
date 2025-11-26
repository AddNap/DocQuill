#!/usr/bin/env python3
"""Sprawdź czy footnote references są poprawnie parsowane i mają numery."""

import sys
from pathlib import Path

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docquill.parser.package_reader import PackageReader
from docquill.parser.xml_parser import XMLParser
from docquill.parser.notes_parser import NotesParser
from docquill.renderers.footnote_renderer import FootnoteRenderer


def check_footnote_references():
    """Sprawdź footnote references w dokumencie."""
    input_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    
    print(f"📄 Ładowanie dokumentu: {input_path}")
    package_reader = PackageReader(input_path)
    xml_parser = XMLParser(package_reader)
    body = xml_parser.parse_body()
    
    # Parsuj footnotes
    notes_parser = NotesParser(package_reader)
    footnotes = notes_parser.get_footnotes() or {}
    endnotes = notes_parser.get_endnotes() or {}
    footnote_renderer = FootnoteRenderer(footnotes, endnotes)
    
    print(f"\n📋 Parsowane footnotes: {len(footnotes)}")
    print(f"📋 Parsowane endnotes: {len(endnotes)}")
    
    # Szukaj słowa "unieważnienie" i sprawdź footnote references
    print("\n🔍 Szukanie słowa 'unieważnienie' i footnote references...")
    
    found_word = False
    footnote_refs_found = []
    
    # Przejdź przez wszystkie paragrafy
    for element in body.children:
        if hasattr(element, 'children') or hasattr(element, 'runs'):
            runs = getattr(element, 'children', []) or getattr(element, 'runs', [])
            for run in runs:
                # Sprawdź tekst
                run_text = ""
                if hasattr(run, 'text'):
                    run_text = run.text or ""
                elif hasattr(run, 'get_text'):
                    run_text = run.get_text() or ""
                
                # Sprawdź czy zawiera "unieważnienie"
                if "unieważnienie" in run_text.lower():
                    found_word = True
                    print(f"\n✅ Znaleziono słowo 'unieważnienie' w runie:")
                    print(f"   Tekst: {run_text[:100]}")
                    
                    # Sprawdź footnote references
                    footnote_refs = getattr(run, 'footnote_refs', [])
                    endnote_refs = getattr(run, 'endnote_refs', [])
                    
                    if footnote_refs:
                        print(f"   📌 Footnote refs: {footnote_refs}")
                        for ref_id in footnote_refs:
                            num = footnote_renderer.get_footnote_number(str(ref_id))
                            print(f"      - ID: {ref_id}, Numer: {num}")
                            footnote_refs_found.append((ref_id, num))
                    else:
                        print(f"   ⚠️  Brak footnote_refs w runie")
                    
                    if endnote_refs:
                        print(f"   📌 Endnote refs: {endnote_refs}")
                        for ref_id in endnote_refs:
                            num = footnote_renderer.get_endnote_number(str(ref_id))
                            print(f"      - ID: {ref_id}, Numer: {num}")
                    
                    # Sprawdź style
                    if hasattr(run, 'style'):
                        style = run.style
                        if isinstance(style, dict):
                            print(f"   🎨 Style: {style}")
                            if 'run_style' in style:
                                print(f"      - run_style: {style['run_style']}")
                            if 'vertical_align' in style:
                                print(f"      - vertical_align: {style['vertical_align']}")
                            if 'superscript' in style:
                                print(f"      - superscript: {style['superscript']}")
                
                # Sprawdź też czy run ma tylko footnote_refs bez tekstu
                footnote_refs = getattr(run, 'footnote_refs', [])
                if footnote_refs and not run_text:
                    print(f"\n📌 Run z footnote_refs (bez tekstu):")
                    print(f"   Footnote refs: {footnote_refs}")
                    for ref_id in footnote_refs:
                        num = footnote_renderer.get_footnote_number(str(ref_id))
                        print(f"      - ID: {ref_id}, Numer: {num}")
                        footnote_refs_found.append((ref_id, num))
                    
                    # Sprawdź style
                    if hasattr(run, 'style'):
                        style = run.style
                        if isinstance(style, dict):
                            print(f"   🎨 Style: {style}")
    
    if not found_word:
        print("\n⚠️  Nie znaleziono słowa 'unieważnienie' w dokumencie")
    
    # Sprawdź wszystkie runs z footnote references
    print("\n" + "="*80)
    print("📋 WSZYSTKIE RUNS Z FOOTNOTE REFERENCES:")
    print("="*80)
    
    total_footnote_runs = 0
    for element in body.children:
        if hasattr(element, 'children') or hasattr(element, 'runs'):
            runs = getattr(element, 'children', []) or getattr(element, 'runs', [])
            for run in runs:
                footnote_refs = getattr(run, 'footnote_refs', [])
                endnote_refs = getattr(run, 'endnote_refs', [])
                
                if footnote_refs or endnote_refs:
                    total_footnote_runs += 1
                    run_text = ""
                    if hasattr(run, 'text'):
                        run_text = run.text or ""
                    elif hasattr(run, 'get_text'):
                        run_text = run.get_text() or ""
                    
                    print(f"\nRun #{total_footnote_runs}:")
                    print(f"   Tekst: '{run_text[:50]}'")
                    if footnote_refs:
                        print(f"   Footnote refs: {footnote_refs}")
                        for ref_id in footnote_refs:
                            num = footnote_renderer.get_footnote_number(str(ref_id))
                            print(f"      - ID: {ref_id}, Numer: {num}")
                    if endnote_refs:
                        print(f"   Endnote refs: {endnote_refs}")
                        for ref_id in endnote_refs:
                            num = footnote_renderer.get_endnote_number(str(ref_id))
                            print(f"      - ID: {ref_id}, Numer: {num}")
                    
                    # Sprawdź style
                    if hasattr(run, 'style'):
                        style = run.style
                        if isinstance(style, dict):
                            print(f"   Style keys: {list(style.keys())}")
                            if 'run_style' in style:
                                print(f"      - run_style: {style['run_style']}")
    
    print(f"\n📊 Podsumowanie:")
    print(f"   - Znaleziono runs z footnote references: {total_footnote_runs}")
    print(f"   - Znaleziono słowo 'unieważnienie': {'Tak' if found_word else 'Nie'}")
    print(f"   - Footnote refs przy 'unieważnienie': {len(footnote_refs_found)}")
    
    return footnote_refs_found


if __name__ == "__main__":
    check_footnote_references()

