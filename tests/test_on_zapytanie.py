"""Test generujący PDF w trybie direct z pliku Zapytanie Ofertowe."""

import pytest
from pathlib import Path
from docx_interpreter.document import Document
from compiler import PdfCompiler, CompilerOptions


@pytest.mark.integration
def test_generate_direct_pdf_from_zapytanie(sample_docx_path, tmp_path):
    """Test generujący PDF w trybie direct z pliku Zapytanie Ofertowe.
    
    Args:
        sample_docx_path: Fixture zwracająca ścieżkę do pliku Zapytanie_Ofertowe.docx
        tmp_path: Fixture pytest tworząca tymczasowy katalog
    """
    # Ścieżka do pliku wejściowego
    input_path = Path(sample_docx_path)
    assert input_path.exists(), f"Plik wejściowy nie istnieje: {input_path}"
    
    # Ścieżka do pliku wyjściowego
    output_path = tmp_path / "Zapytanie_Ofertowe_direct.pdf"
    
    # Załaduj dokument DOCX
    document = Document.from_file(input_path)
    
    # Opcje kompilatora - używamy trybu "direct" dla pełnej wierności DOCX
    options = CompilerOptions(
        renderer="direct",  # Tryb direct dla najlepszej wierności DOCX
        dpi=72.0,  # Domyślna rozdzielczość
    )
    
    # Utwórz i uruchom kompilator
    compiler = PdfCompiler(document, output_path, options)
    result_path = compiler.compile()
    
    # Sprawdź wyniki
    assert result_path == output_path, "Zwrócona ścieżka nie pasuje do oczekiwanej"
    assert output_path.exists(), f"Plik PDF nie został utworzony: {output_path}"
    assert output_path.stat().st_size > 0, "Plik PDF jest pusty"
    
    print(f"\n✅ PDF wygenerowany pomyślnie: {output_path}")
    print(f"   Rozmiar: {output_path.stat().st_size:,} bajtów")


@pytest.mark.integration
def test_generate_direct_pdf_with_custom_output(sample_docx_path):
    """Test generujący PDF w trybie direct z własną ścieżką wyjściową.
    
    Args:
        sample_docx_path: Fixture zwracająca ścieżkę do pliku Zapytanie_Ofertowe.docx
    """
    # Ścieżka do pliku wejściowego
    input_path = Path(sample_docx_path)
    
    # Ścieżka do pliku wyjściowego w katalogu output
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "Zapytanie_Ofertowe_direct_test.pdf"
    
    # Załaduj dokument DOCX
    document = Document.from_file(input_path)
    
    # Opcje kompilatora - tryb direct
    options = CompilerOptions(
        renderer="direct",
    )
    
    # Utwórz i uruchom kompilator
    compiler = PdfCompiler(document, output_path, options)
    result_path = compiler.compile()
    
    # Sprawdź wyniki
    assert result_path == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    
    print(f"\n✅ PDF wygenerowany pomyślnie: {output_path}")
    print(f"   Rozmiar: {output_path.stat().st_size:,} bajtów")


if __name__ == "__main__":
    # Uruchom testy bezpośrednio
    pytest.main([__file__, "-v", "-s"])

