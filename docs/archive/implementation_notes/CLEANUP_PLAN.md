# Plan Sprzątania Projektu

## Pliki do Usunięcia

### 1. Stare Parsery (_old) ✅ BEZPIECZNE
- `docx_interpreter/parser/style_parser_old.py` - nieużywany
- `docx_interpreter/parser/numbering_parser_old.py` - nieużywany

### 2. Stare Testy ✅ BEZPIECZNE
- `test_old_library.py` - testy starej biblioteki
- `test_old_library_advanced.py` - zaawansowane testy starej biblioteki
- `test_output_old.docx` - wyjście ze starych testów
- `test_output_old.html` - wyjście ze starych testów

### 3. Puste/Stare Katalogi ✅ BEZPIECZNE
- `docx_interpreter/Layout_engine/` - pusty katalog

### 4. Pliki Debug/Tymczasowe ✅ BEZPIECZNE
- `debug_output.log` - plik logów
- `debug_document_structure.py` - skrypt debugujący

### 5. Pliki Tymczasowe w Root ✅ BEZPIECZNE
- `test_list_check.html` - plik tymczasowy
- `test_with_elements.docx` - plik testowy w root (powinien być w tests/files/)

### 6. Pliki ZIP ✅ BEZPIECZNE
- `docx_interpreter.zip` - archiwum, niepotrzebne w repo

### 7. Testy w Root (do przeniesienia lub usunięcia) ⚠️ SPRAWDZIĆ
- `test_new_architecture.py`
- `test_improved_architecture.py`
- `test_improved_layout_engine.py`
- `test_improved_universal_renderer.py`
- `test_new_features_universal_renderer.py`
- `test_new_pdf_engine.py`
- `test_pdf_debug.py`
- `test_pdf_engine.py`
- `test_pdf_render.py`
- `test_pdf_renderer.py`
- `test_pdf_simple.py`
- `test_renderer_improved.py`
- `test_docx_rebuild.py`

### 8. Duplikaty Modułów ⚠️ SPRAWDZIĆ
- `docx_interpreter/layout/layout_engine.py` vs `docx_interpreter/layout_engine.py`
- `docx_interpreter/new_architecture.py` - prawdopodobnie stary test

### 9. Stary Renderer ⚠️ SPRAWDZIĆ
- `tests/_old_rend/` - stary renderer, cały katalog

### 10. Pliki _enhanced ⚠️ UŻYWANE
- `docx_interpreter/parser/style_parser_enhanced.py` - sprawdzić czy używany
- `docx_interpreter/parser/numbering_parser_enhanced.py` - sprawdzić czy używany
- `docx_interpreter/export/json_exporter_enhanced.py` - **UŻYWANY** w __init__.py (nie usuwać!)

### 11. generate_dumps.py ⚠️ SPRAWDZIĆ
- `generate_dumps.py` - używa starego layout_engine, sprawdzić czy potrzebny

