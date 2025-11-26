#!/usr/bin/env python3
"""
Skrypt do importu JSON do DOCX.

Demonstruje odwrócenie procesu: JSON → UnifiedLayout → Document Model → DOCX
"""

import sys
import argparse
from pathlib import Path

# Dodaj ścieżkę do modułów
sys.path.insert(0, str(Path(__file__).parent.parent))

from docx_interpreter.importers.pipeline_json_importer import PipelineJSONImporter
from docx_interpreter.export.docx_exporter import DOCXExporter


def main():
    parser = argparse.ArgumentParser(description='Import JSON do DOCX')
    parser.add_argument('json_path', type=str, help='Ścieżka do pliku JSON')
    parser.add_argument('-o', '--output', type=str, help='Ścieżka do pliku wyjściowego DOCX')
    parser.add_argument('--from-unified-layout', action='store_true',
                       help='Użyj UnifiedLayout jako pośredniego formatu')
    
    args = parser.parse_args()
    
    json_path = Path(args.json_path)
    if not json_path.exists():
        print(f"❌ Plik JSON nie istnieje: {json_path}")
        sys.exit(1)
    
    output_path = Path(args.output) if args.output else json_path.with_suffix('.docx')
    
    print(f"📄 Otwieranie JSON: {json_path}")
    
    try:
        # Załaduj JSON
        importer = PipelineJSONImporter(json_path=json_path)
        
        if args.from_unified_layout:
            # JSON → UnifiedLayout → Document Model
            print("🔄 Konwertowanie JSON → UnifiedLayout → Document Model...")
            unified_layout = importer.to_unified_layout()
            print(f"✅ UnifiedLayout: {len(unified_layout.pages)} stron")
            
            # TODO: UnifiedLayout → Document Model (wymaga implementacji)
            print("⚠️ Konwersja UnifiedLayout → Document Model nie jest jeszcze w pełni zaimplementowana")
            print("   UnifiedLayout ma pozycjonowanie i paginację, które nie są w Document Model")
            print("   Użyj --direct-mode dla bezpośredniej konwersji JSON → Document Model")
            sys.exit(1)
        else:
            # JSON → Document Model (bezpośrednio)
            print("🔄 Konwertowanie JSON → Document Model...")
            model = importer.to_document_model()
            
            # Sprawdź strukturę modelu
            if hasattr(model, 'body'):
                elements_count = len(model.body.children) if hasattr(model.body, 'children') else 0
                paragraphs_count = len(model.body.paragraphs) if hasattr(model.body, 'paragraphs') else 0
                tables_count = len(model.body.tables) if hasattr(model.body, 'tables') else 0
                print(f"✅ Document Model: {elements_count} elementów ({paragraphs_count} paragrafów, {tables_count} tabel)")
            else:
                elements_count = len(getattr(model, 'elements', []))
                print(f"✅ Document Model: {elements_count} elementów")
            
            # Document Model → DOCX
            print("🔄 Eksportowanie Document Model → DOCX...")
            exporter = DOCXExporter(model)
            success = exporter.export(output_path)
            
            if success:
                print(f"✅ DOCX wygenerowany: {output_path}")
                print(f"   Rozmiar: {output_path.stat().st_size / 1024:.2f} KB")
            else:
                print(f"❌ Błąd podczas eksportu do DOCX")
                sys.exit(1)
    
    except Exception as e:
        print(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

