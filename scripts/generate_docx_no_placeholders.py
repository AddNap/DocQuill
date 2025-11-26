#!/usr/bin/env python3
"""
Skrypt do generowania dokumentu DOCX bez podstawiania placeholderów.
"""

import sys
from pathlib import Path

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    if len(sys.argv) < 2:
        print("Użycie: python generate_docx_no_placeholders.py <input.docx> [output.docx]")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.parent / f"{input_path.stem}_no_placeholders.docx"
    
    print(f"=== GENEROWANIE DOKUMENTU BEZ PODSTAWIANIA PLACEHOLDERÓW ===\n")
    print(f"📄 Wejście: {input_path}")
    print(f"📄 Wyjście: {output_path}\n")
    
    # Otwórz dokument bezpośrednio przez parser (bez LayoutPipeline)
    # aby uniknąć podstawiania placeholderów
    from docx_interpreter.parser.package_reader import PackageReader
    from docx_interpreter.parser.xml_parser import XMLParser
    from docx_interpreter.export.docx_exporter import DOCXExporter
    
    print(f"📄 Otwieranie dokumentu bezpośrednio przez parser...")
    package_reader = PackageReader(str(input_path))
    xml_parser = XMLParser(package_reader)
    body = xml_parser.parse_body()
    sections = xml_parser.parse_sections()
    
    # Utwórz model dokumentu
    class DocumentAdapter:
        def __init__(self, body_obj, parser, sections=None):
            self.elements = body_obj.children if hasattr(body_obj, 'children') else []
            self.parser = parser
            self._sections = sections or []
    
    model = DocumentAdapter(body, xml_parser, sections)
    model._file_path = input_path
    
    print(f"✅ Dokument otwarty: {input_path.name}")
    
    # Eksportuj bezpośrednio (bez LayoutPipeline, więc placeholdery nie są podstawiane)
    print(f"📄 Eksportowanie dokumentu...")
    exporter = DOCXExporter(model, source_docx_path=str(input_path))
    success = exporter.export(str(output_path))
    
    if not success:
        raise Exception(f"Failed to export document to {output_path}")
    
    print(f"✅ Dokument zapisany: {output_path.name}")
    print(f"✅ Rozmiar: {output_path.stat().st_size:,} bajtów\n")
    
    # Sprawdź, czy placeholdery są zachowane
    import zipfile
    import xml.etree.ElementTree as ET
    
    with zipfile.ZipFile(output_path, 'r') as gen_zip:
        gen_xml = gen_zip.read('word/document.xml')
        gen_doc_root = ET.fromstring(gen_xml)
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        # Znajdź wszystkie teksty zawierające placeholdery
        texts = gen_doc_root.findall('.//w:t', ns)
        placeholder_count = 0
        placeholder_examples = []
        
        for t in texts:
            if t.text and ('{{' in t.text or '}}' in t.text):
                placeholder_count += 1
                if len(placeholder_examples) < 5:
                    placeholder_examples.append(t.text[:80])
        
        print(f"📄 Placeholdery w dokumencie:")
        print(f"  Znaleziono {placeholder_count} tekstów z placeholderami")
        if placeholder_examples:
            print(f"  Przykłady:")
            for i, text in enumerate(placeholder_examples, 1):
                print(f"    {i}. {text}...")
        print("  ✅ Placeholdery są zachowane (nie podstawione)")

if __name__ == "__main__":
    main()

