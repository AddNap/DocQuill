#!/usr/bin/env python3
"""
Przykład użycia nowego wysokopoziomowego API.

Demonstruje prosty interfejs do pracy z dokumentami DOCX.
"""

from pathlib import Path
from docquill import Document

def main():
    """Przykład użycia prostego API."""
    
    # 1. Otwórz dokument
    print("📄 Otwieranie dokumentu...")
    doc = Document('tests/files/Zapytanie_Ofertowe.docx')
    
    # 2. Pobierz model
    print("📋 Pobieranie modelu...")
    model = doc.to_model()
    print(f"   Elementów w modelu: {len(model.elements)}")
    
    # 3. Przetwórz przez pipeline
    print("⚙️  Przetwarzanie przez pipeline...")
    layout = doc.pipeline()
    print(f"   Stron: {len(layout.pages)}")
    print(f"   Bloków: {sum(len(p.blocks) for p in layout.pages)}")
    
    # 4. Renderuj do PDF
    print("📄 Renderowanie do PDF...")
    pdf_path = doc.to_pdf(
        'output/simple_api_example.pdf',
        backend='rust',
        page_size=(595, 842),  # A4
        margins=(72, 72, 72, 72)  # 1 cal z każdej strony
    )
    print(f"   ✅ PDF zapisany: {pdf_path}")
    
    # 5. Renderuj do HTML
    print("🌐 Renderowanie do HTML...")
    html_path = doc.to_html(
        'output/simple_api_example.html',
        editable=False,
        embed_images_as_data_uri=False
    )
    print(f"   ✅ HTML zapisany: {html_path}")
    
    # 6. Normalizuj dokument (opcjonalnie)
    print("🔧 Normalizacja dokumentu...")
    try:
        doc_normalized = doc.normalize('output/simple_api_example_normalized.docx')
        print(f"   ✅ Znormalizowany dokument: {doc_normalized._file_path}")
    except Exception as e:
        print(f"   ⚠️  Normalizacja nieudana: {e}")
    
    print("\n✅ Wszystko gotowe!")


if __name__ == "__main__":
    # Utwórz katalog wyjściowy
    Path('output').mkdir(exist_ok=True)
    
    main()

