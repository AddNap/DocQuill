# Analiza Brakujących Funkcjonalności - Porównanie z Starą Biblioteką

## 📋 Podsumowanie

Obecna biblioteka `DocQuill.2.0` ma solidne fundamenty (parsowanie, modele, rendering), ale **brakuje jej wielu funkcjonalności Jinja-like**, które były w starej wersji `DocQuill`.

## 🔴 Krytyczne Braki - Placeholder API (Jinja-like)

### 1. **Brak Pełnego PlaceholderEngine**

**Stara biblioteka miała:**
- `PlaceholderEngine` z 20+ typami placeholderów
- Automatyczne formatowanie dla różnych typów
- Custom blocks (QR, TABLE, IMAGE, LIST)
- Conditional blocks (START_/END_)

**Obecna biblioteka ma tylko:**
- Podstawowy `PlaceholderResolver` (tylko `{{ TYPE:Key }}`)
- Brak formatowania automatycznego
- Brak custom blocks
- Brak conditional blocks

**Brakujące typy placeholderów:**
- ✅ TEXT (podstawowy - działa)
- ❌ DATE - formatowanie dat (np. `DATE:IssueDate` → `16.10.2025`)
- ❌ TIME - formatowanie czasu
- ❌ DATETIME - formatowanie daty i czasu
- ❌ CURRENCY - formatowanie waluty (np. `CURRENCY:Amount` → `1 500,50 PLN`)
- ❌ NUMBER - formatowanie liczb z separatorami
- ❌ PERCENT - formatowanie procentów
- ❌ PHONE - formatowanie telefonów (np. `PHONE:Contact` → `+48 123 456 789`)
- ❌ EMAIL - walidacja i formatowanie emaili
- ❌ BOOLEAN - formatowanie boolean (Tak/Nie)
- ❌ QR - generowanie kodów QR jako obrazy
- ❌ TABLE - wstawianie tabel z danych
- ❌ IMAGE - wstawianie obrazów z plików
- ❌ LIST - wstawianie list (bullet/numbered)
- ❌ CHECKBOX - checkboxy
- ❌ SIGNATURE - podpisy
- ❌ BARCODE - kody kreskowe
- ❌ HYPERLINK - linki
- ❌ ADDRESS - adresy

### 2. **Brak Metod fill_placeholders()**

**Stara biblioteka:**
```python
doc.fill_placeholders({
    "TEXT:Name": "Jan Kowalski",
    "DATE:IssueDate": "2025-10-16",
    "CURRENCY:Amount": 1500.50,
    "QR:OrderCode": "ORDER-123",
    "TABLE:Items": {"headers": [...], "rows": [...]},
    "IMAGE:Logo": "logo.png",
    "LIST:Features": ["Fast", "Reliable"]
}, multi_pass=True)
```

**Obecna biblioteka:**
- ❌ Brak metody `fill_placeholders()` na Document
- ❌ Brak multi-pass rendering
- ❌ Brak automatycznego formatowania

### 3. **Brak Conditional Blocks**

**Stara biblioteka:**
```python
doc.process_conditional_block("SpecialOffer", show=True)  # Pokaż sekcję
doc.process_conditional_block("Discount", show=False)    # Ukryj sekcję
```

**Obecna biblioteka:**
- ❌ Brak obsługi `START_` / `END_` markerów
- ❌ Brak metody `process_conditional_block()`

## 🔴 Krytyczne Braki - Document Editing API

### 4. **Brak Wysokopoziomowego API do Edycji**

**Stara biblioteka miała:**
```python
doc = Document()
doc.body.add_paragraph("Tytuł", "Heading1")
p = doc.body.add_paragraph("Tekst")
p.add_run("bold", bold=True)
doc.replace_text("stary", "nowy")
doc.save("output.docx")
```

**Obecna biblioteka:**
- ✅ Ma modele (Paragraph, Run, Body)
- ❌ Brak wysokopoziomowego API `Document.add_paragraph()`
- ❌ Brak `Document.replace_text()`
- ❌ Brak `Document.save()`
- ❌ Brak `Document.body.add_paragraph()` z stylem

### 5. **Brak Document Merging**

**Stara biblioteka:**
```python
main_doc = Document.open("main.docx")
main_doc.append("appendix.docx", page_break=True)
main_doc.prepend("cover.docx", page_break=True)
main_doc.apply_layout("template.docx")
main_doc.merge(doc2, page_break=True)
```

**Obecna biblioteka:**
- ❌ Brak `Document.append()`
- ❌ Brak `Document.prepend()`
- ❌ Brak `Document.merge()`
- ❌ Brak `Document.apply_layout()`
- ❌ Brak rozwiązywania konfliktów stylów przy merge

## 🟡 Średnie Braki - Formatowanie i Style

### 6. **Brak Zaawansowanego Formatowania**

**Stara biblioteka:**
```python
p.add_run("tekst", bold=True, italic=True, font_color="008000")
p.set_list(level=0, numbering_id=numbered_list.num_id)
```

**Obecna biblioteka:**
- ✅ Ma modele z właściwościami formatowania
- ❌ Brak wygodnych metod `add_run()` z parametrami
- ❌ Brak `set_list()` na Paragraph

### 7. **Brak Tworzenia List**

**Stara biblioteka:**
```python
numbered_list = doc.create_numbered_list()
bullet_list = doc.create_bullet_list()
p.set_list(level=0, numbering_id=numbered_list.num_id)
```

**Obecna biblioteka:**
- ✅ Ma NumberingFormatter
- ❌ Brak `Document.create_numbered_list()`
- ❌ Brak `Document.create_bullet_list()`

## 🟢 Mniejsze Braki - HTML Workflow

### 8. **Brak Dwukierunkowej Konwersji HTML**

**Stara biblioteka:**
```python
doc.render_html("output.html", editable=True)
# ... użytkownik edytuje w przeglądarce ...
doc.update_from_html_file("output.html")
doc.save("updated.docx")
```

**Obecna biblioteka:**
- ✅ Ma HTMLRenderer
- ❌ Brak `render_html()` z opcją `editable`
- ❌ Brak `update_from_html_file()`
- ❌ Brak workflow edycji HTML → DOCX

## 📊 Podsumowanie Statystyczne

| Kategoria | Stara Biblioteka | Obecna Biblioteka | Status |
|-----------|------------------|-------------------|--------|
| **Typy placeholderów** | 20+ | 1 (podstawowy) | ❌ 5% |
| **Formatowanie automatyczne** | ✅ Tak | ❌ Nie | ❌ 0% |
| **Custom blocks** | ✅ QR, TABLE, IMAGE, LIST | ❌ Brak | ❌ 0% |
| **Conditional blocks** | ✅ START_/END_ | ❌ Brak | ❌ 0% |
| **Document editing API** | ✅ Pełne API | ⚠️ Tylko modele | ⚠️ 30% |
| **Document merging** | ✅ Pełne API | ❌ Brak | ❌ 0% |
| **List creation** | ✅ API | ⚠️ Tylko formatter | ⚠️ 40% |
| **HTML workflow** | ✅ Dwukierunkowy | ⚠️ Tylko render | ⚠️ 50% |

## 🎯 Priorytety Implementacji

### Priorytet 1 - Placeholder Engine (Jinja-like)
1. ✅ Rozszerzyć `PlaceholderResolver` → `PlaceholderEngine`
2. ✅ Dodać formatowanie automatyczne (DATE, CURRENCY, PHONE, etc.)
3. ✅ Dodać custom blocks (QR, TABLE, IMAGE, LIST)
4. ✅ Dodać conditional blocks (START_/END_)
5. ✅ Dodać `Document.fill_placeholders()`

### Priorytet 2 - Document Editing API
1. ✅ Dodać `Document.add_paragraph()`
2. ✅ Dodać `Document.replace_text()`
3. ✅ Dodać `Document.save()`
4. ✅ Dodać `Paragraph.add_run()` z parametrami
5. ✅ Dodać `Document.create_numbered_list()` / `create_bullet_list()`

### Priorytet 3 - Document Merging
1. ✅ Dodać `Document.merge()`
2. ✅ Dodać `Document.append()` / `prepend()`
3. ✅ Dodać rozwiązywanie konfliktów stylów

### Priorytet 4 - HTML Workflow
1. ✅ Dodać `render_html()` z `editable=True`
2. ✅ Dodać `update_from_html_file()`

## 📝 Plik Źródłowy do Implementacji

Główny plik starej biblioteki z pełną implementacją:
- `_old/DocQuill/src/doclingforge/core/placeholder.py` - PlaceholderEngine (1280 linii)
- `_old/DocQuill/src/doclingforge/core/document.py` - Document API (2000+ linii)
- `_old/DocQuill/src/doclingforge/core/merger.py` - Document merging

## 🔗 Związane Dokumenty

- `_old/DocQuill/README.md` - Dokumentacja starej biblioteki
- `_old/DocQuill/PLACEHOLDER_API_IMPLEMENTATION_SUMMARY.md` - Szczegóły placeholder API
- `docs/OLD_LIBRARY_TEST_REPORT.md` - Testy starej biblioteki

