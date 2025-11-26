#!/usr/bin/env python3
"""
Test eksportu DOCX z użyciem szablonu new_doc.docx
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from docquill import Document

def test_template_export(docx_path: str, output_path: str = None):
    """Testuje eksport DOCX z użyciem szablonu."""
    docx_path = Path(docx_path)
    
    if not docx_path.exists():
        print(f"❌ Plik nie istnieje: {docx_path}")
        return False
    
    if output_path is None:
        output_path = docx_path.parent / f"{docx_path.stem}_with_template.docx"
    else:
        output_path = Path(output_path)
    
    print(f"\n{'='*80}")
    print(f"🧪 TEST EKSPORTU Z SZABLONEM")
    print(f"{'='*80}")
    print(f"\n📄 Oryginalny dokument: {docx_path}")
    print(f"📄 Szablon: docx_interpreter/export/new_doc.docx")
    print(f"📄 Wyjściowy dokument: {output_path}")
    
    try:
        # Krok 1: Załaduj dokument
        print(f"\n📥 Krok 1: Ładowanie dokumentu...")
        doc = Document(str(docx_path))
        print(f"   ✅ Dokument załadowany")
        
        # Krok 2: Eksport do DOCX (użyje szablonu automatycznie)
        print(f"\n📤 Krok 2: Eksport do DOCX z szablonem...")
        doc.save(str(output_path))
        print(f"   ✅ DOCX wyeksportowany: {output_path}")
        
        # Krok 3: Sprawdź czy plik istnieje i ma poprawny rozmiar
        if output_path.exists():
            size = output_path.stat().st_size
            print(f"   ✅ Plik istnieje, rozmiar: {size:,} bajtów")
            
            # Krok 4: Sprawdź zawartość ZIP
            import zipfile
            with zipfile.ZipFile(output_path, 'r') as zip_file:
                files = zip_file.namelist()
                print(f"\n📦 Zawartość DOCX ({len(files)} plików):")
                
                # Sprawdź kluczowe pliki
                required_files = [
                    '[Content_Types].xml',
                    '_rels/.rels',
                    'word/document.xml',
                    'word/styles.xml',
                    'word/settings.xml',
                    'word/theme/theme1.xml',
                    'word/fontTable.xml',
                    'word/webSettings.xml',
                    'word/_rels/document.xml.rels'
                ]
                
                print(f"\n   Kluczowe pliki:")
                for req_file in required_files:
                    if req_file in files:
                        print(f"      ✅ {req_file}")
                    else:
                        print(f"      ❌ {req_file} - BRAK!")
                
                # Sprawdź czy document.xml ma zawartość
                try:
                    doc_xml = zip_file.read('word/document.xml').decode('utf-8')
                    if len(doc_xml) > 100:
                        print(f"\n   ✅ word/document.xml ma zawartość ({len(doc_xml)} znaków)")
                        # Sprawdź czy ma podstawową strukturę
                        if '<w:document' in doc_xml and '<w:body' in doc_xml:
                            print(f"      ✅ Ma poprawną strukturę XML")
                        else:
                            print(f"      ⚠️ Brak podstawowej struktury XML")
                    else:
                        print(f"\n   ⚠️ word/document.xml jest zbyt krótki ({len(doc_xml)} znaków)")
                except Exception as e:
                    print(f"\n   ❌ Błąd podczas czytania document.xml: {e}")
                
                # Sprawdź styles.xml
                try:
                    styles_xml = zip_file.read('word/styles.xml').decode('utf-8')
                    if len(styles_xml) > 100:
                        print(f"   ✅ word/styles.xml ma zawartość ({len(styles_xml)} znaków)")
                    else:
                        print(f"   ⚠️ word/styles.xml jest zbyt krótki")
                except Exception as e:
                    print(f"   ⚠️ Brak styles.xml lub błąd: {e}")
            
            print(f"\n{'='*80}")
            print(f"✅ TEST ZAKOŃCZONY POMYŚLNIE")
            print(f"{'='*80}\n")
            return True
        else:
            print(f"\n   ❌ Plik nie został utworzony!")
            return False
            
    except Exception as e:
        print(f"\n   ❌ Błąd podczas eksportu: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test eksportu DOCX z szablonem')
    parser.add_argument('docx_path', type=str, help='Ścieżka do pliku DOCX')
    parser.add_argument('-o', '--output', type=str, help='Ścieżka do pliku wyjściowego')
    
    args = parser.parse_args()
    
    success = test_template_export(args.docx_path, args.output)
    sys.exit(0 if success else 1)

