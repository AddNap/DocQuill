# Brakujące funkcje w nowym API DocQuill

Lista funkcjonalności dostępnych w bibliotece, ale jeszcze nie zaimplementowanych w nowym wysokopoziomowym API.

**Status:** Większość funkcji została już dodana! ✅

## ✅ Zaimplementowane

- ✅ Watermarks - `add_watermark()`, `get_watermarks()`, `watermarks` property
- ✅ Zaawansowane merge - `merge_sections()`, `merge_styles()`
- ✅ Metadata - `get_metadata()`, `metadata` property, `get_title()`, `get_author()`, etc.
- ✅ Walidacja - `validate_layout()` z wynikami
- ✅ Wewnętrzne obiekty - `pipeline`, `package_reader`, `xml_parser`, `layout` properties
- ✅ Informacje o dokumencie - `get_stats()`, `get_sections()`, `get_styles()`, `get_numbering()`

## ❌ Jeszcze brakuje

## ❌ Jeszcze brakuje

### 1. Eksport do innych formatów (pomijamy - użytkownik jeszcze nie dodał importu)

**Brakuje:**
- `doc.to_xlsx(output_path, **options)` - Eksport do XLSX
- `doc.to_xml(output_path, **options)` - Eksport do XML
- `doc.to_json(output_path, **options)` - Eksport do JSON
- `doc.to_markdown(output_path, **options)` - Eksport do Markdown
- `doc.to_csv(output_path, **options)` - Eksport do CSV
- `doc.to_text(output_path, **options)` - Eksport do zwykłego tekstu

**Uwaga:** Te funkcje będą dodane gdy użytkownik zaimplementuje import i obsługę innych formatów.

---

### 2. Eksport do stringów (bez zapisu do pliku)

**Brakuje:**
- `doc.to_html_string(**options)` - Zwraca HTML jako string
- `doc.to_xml_string(**options)` - Zwraca XML jako string
- `doc.to_json_string(**options)` - Zwraca JSON jako string
- `doc.to_markdown_string(**options)` - Zwraca Markdown jako string

**Dostępne w:** 
- `HTMLExporter.export_to_string()`
- `XMLExporter.export_to_string()`
- `JSONExporter.export_to_string()`
- `MarkdownExporter.export_to_string()`

**Przykład użycia:**
```python
html_content = doc.to_html_string(editable=False)
xml_content = doc.to_xml_string(namespace='w')
json_content = doc.to_json_string()
```

---

### 3. Zaawansowane opcje renderowania

**Brakuje:**
- `doc.to_pdf()` - opcja `include_metadata` - Czy dołączyć metadane do PDF
- `doc.to_pdf()` - opcja `include_bookmarks` - Czy dodać zakładki (outline)
- `doc.to_html()` - opcja `include_css` - Czy dołączyć CSS
- `doc.to_html()` - opcja `css_style` - Styl CSS ('default', 'minimal', 'print')

**Przykład użycia:**
```python
doc.to_pdf('output.pdf', include_metadata=True, include_bookmarks=True)
doc.to_html('output.html', include_css=True, css_style='print')
```

---

## 📊 Podsumowanie

| Kategoria | Status | Liczba |
|-----------|--------|--------|
| ✅ Watermarks | Zaimplementowane | 3 metody |
| ✅ Merge operations | Zaimplementowane | 2 metody |
| ❌ Export formats | Pomijamy (użytkownik jeszcze nie dodał) | 6 formatów |
| ✅ Metadata | Zaimplementowane | 10+ metod |
| ✅ Walidacja | Zaimplementowane | 1 metoda |
| ✅ Wewnętrzne obiekty | Zaimplementowane | 4 properties |
| ✅ Informacje | Zaimplementowane | 4 metody |
| ❌ String export | Brakuje | 4 metody |
| ❌ Opcje renderowania | Brakuje | 4 opcje |

**Zaimplementowane: ~24 funkcje/metody** ✅  
**Jeszcze brakuje: ~14 funkcji/metod** (głównie eksport i opcje renderowania)

---

## 🎯 Rekomendacje implementacji

### Wysoki priorytet:
1. **Export formats** - `to_xlsx()`, `to_xml()`, `to_json()`, `to_markdown()`, `to_csv()`, `to_text()`
2. **Metadata** - `get_metadata()`, podstawowe gettery

### Średni priorytet:
3. **Watermarks** - `add_watermark()`, `get_watermarks()`
4. **Walidacja** - `validate_layout()` z wynikami
5. **String export** - `to_html_string()`, `to_xml_string()`, etc.

### Niski priorytet:
6. **Merge operations** - `merge_sections()`, `merge_styles()`
7. **Wewnętrzne obiekty** - properties dla pipeline, package_reader, etc.
8. **Informacje** - `get_stats()`, `get_sections()`, etc.

