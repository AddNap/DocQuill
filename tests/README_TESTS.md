# Dokumentacja Testów

## Struktura testów

### Nowe testy (dla nowych funkcjonalności)

1. **test_document_api.py** - Testy dla wysokopoziomowego Document API
   - Otwieranie dokumentów
   - Dodawanie paragrafów
   - Zamiana tekstu
   - Wypełnianie placeholderów
   - Renderowanie HTML/PDF
   - Scalanie dokumentów

2. **test_placeholder_engine.py** - Testy dla PlaceholderEngine
   - Ekstrakcja placeholderów
   - Klasyfikacja typów
   - Wypełnianie różnych typów placeholderów
   - Custom blocks (QR, TABLE, LIST, IMAGE)

3. **test_merger.py** - Testy dla DocumentMerger
   - Pełne scalanie
   - Selektywne scalanie
   - Scalanie headers/footers/styles

4. **test_html_parser.py** - Testy dla HTML Parser
   - Parsowanie HTML z contenteditable
   - Obsługa formatowania
   - Konwersja HTML → DOCX

5. **test_html_renderer.py** (zaktualizowany) - Testy dla HTMLRenderer
   - Renderowanie podstawowe
   - Renderowanie edytowalne
   - Formatowanie

### Zaktualizowane testy

- **tests/Interpreter/test_document.py** - Zaktualizowane importy
- **tests/conftest.py** - Dodane nowe fixtures

## Uruchamianie testów

### Wszystkie testy
```bash
python3 -m pytest tests/ -v
```

### Tylko nowe testy
```bash
python3 -m pytest tests/test_document_api.py tests/test_placeholder_engine.py tests/test_merger.py tests/test_html_parser.py -v
```

### Tylko testy rendererów
```bash
python3 -m pytest tests/renderers/ -v
```

### Z pokryciem kodu
```bash
python3 -m pytest tests/ --cov=docx_interpreter --cov-report=html
```

### Tylko szybkie testy (bez integracyjnych)
```bash
python3 -m pytest tests/ -m "not slow" -v
```

## Wymagania

- Python 3.10+
- pytest
- Pliki testowe w `tests/files/` (opcjonalne - testy mogą być pomijane)

## Status

- ✅ Nowe testy dodane
- ✅ Stare testy zaktualizowane
- ⚠️ Niektóre testy wymagają plików testowych (są pomijane jeśli brakuje)

## Uwagi

- Testy używają `pytest.skip()` jeśli brakuje plików testowych
- Niektóre testy używają mocków i nie wymagają rzeczywistych plików
- Testy PDF wymagają ReportLab
- Testy HTML wymagają podstawowych bibliotek Python

