# Pozostałe Zadania - Co Jeszcze Brakuje

## ✅ Zaimplementowane

### PlaceholderEngine (Jinja-like)
- ✅ 20+ typów placeholderów z formatowaniem
- ✅ Custom blocks (QR, TABLE, IMAGE, LIST)
- ✅ Conditional blocks (START_/END_)
- ✅ Multi-pass rendering

### DocumentMerger
- ✅ Pełne i selektywne scalanie dokumentów
- ✅ Obsługa relacji OPC (RelationshipMerger)
- ✅ Rozwiązywanie konfliktów stylów i numeracji

### Document API
- ✅ Wysokopoziomowe API (add_paragraph, replace_text, fill_placeholders)
- ✅ Proste API (convenience functions)
- ✅ Integracja z istniejącymi rendererami

## ⚠️ Do Dokończenia

### 1. DOCX Export (save()) - **✅ ZAIMPLEMENTOWANE**

**Status:** ✅ Podstawowa implementacja gotowa

**Co zostało zaimplementowane:**
- ✅ `DOCXExporter` - klasa do zapisu pakietu DOCX (ZIP) z wszystkimi częściami
- ✅ Generowanie `document.xml` z modeli (używa XMLExporter)
- ✅ Kopiowanie `styles.xml`, `numbering.xml`, `settings.xml` z oryginalnego dokumentu
- ✅ Generowanie plików `.rels` dla wszystkich relacji
- ✅ Generowanie `[Content_Types].xml`
- ✅ Kopiowanie media (obrazy) do pakietu
- ✅ Kopiowanie headers/footers z relacjami

**Co zostało ulepszone:**
- ✅ Generowanie `styles.xml` z modeli (używa `StyleNormalizer` z `normalize.py`)
- ✅ Generowanie `numbering.xml` z modeli (używa `NumberingNormalizer` z `normalize.py`)
- ✅ Automatyczne wykrywanie i kopiowanie media z relacjami

**Co może wymagać dopracowania:**
- ⚠️ Automatyczne tworzenie relacji dla nowych obrazów dodanych przez API (częściowo)
- ⚠️ Aktualizacja rel_id w XML podczas zapisu dla nowych elementów

**Priorytet:** 🟢 Niski - podstawowa funkcjonalność działa

### 2. Pełna Implementacja Custom Blocks - **✅ ZAIMPLEMENTOWANE**

**Status:** ✅ Podstawowa implementacja gotowa

**Co zostało zaimplementowane:**

#### insert_table()
- ✅ Pełna implementacja z dostępem do `body.children`
- ✅ Wstawianie tabeli w miejsce paragrafu lub po paragrafie
- ✅ Tworzenie tabeli z headers i rows
- ⚠️ Integracja z numbering system dla stylów tabel (może wymagać dopracowania)

#### insert_list()
- ✅ Pełna implementacja z dostępem do `body.children`
- ✅ Wstawianie paragrafów listy w miejsce paragrafu lub po paragrafie
- ✅ Integracja z numbering system (używa `set_list()`)
- ✅ Obsługa bullet i numbered lists
- ⚠️ Automatyczne tworzenie numbering_id (obecnie używa domyślnego)

#### insert_qr_code() / insert_image()
- ✅ Podstawowa implementacja
- ✅ Wstawianie obrazów do runów
- ⚠️ Pełna integracja z media system i relacjami (wymaga dopracowania dla nowych obrazów)

**Co może wymagać dopracowania:**
- ⚠️ Automatyczne tworzenie numbering_id dla list (obecnie używa domyślnego)
- ⚠️ Generowanie relacji dla nowych obrazów dodanych przez API

**Priorytet:** 🟢 Niski - podstawowa funkcjonalność działa

### 3. PDF Render Integration - **✅ ZAIMPLEMENTOWANE**

**Status:** ✅ Integracja z PDFCompiler gotowa

**Co zostało zaimplementowane:**
- ✅ Integracja `Document.render_pdf()` z PDFCompiler
- ✅ Użycie LayoutPipeline do stworzenia UnifiedLayout
- ✅ Przekazywanie dokumentu do PDFCompiler
- ✅ Obsługa opcji renderowania (page_size, margins)
- ✅ Automatyczne wykrywanie package_reader dla obrazów

**Priorytet:** ✅ Zakończone

### 4. HTML Workflow (update_from_html_file) - **✅ ZAIMPLEMENTOWANE**

**Status:** ✅ Dwukierunkowa konwersja zaimplementowana

**Co zostało zaimplementowane:**
- ✅ Rozszerzony HTMLRenderer o opcję `editable=True` z contenteditable
- ✅ Renderowanie formatowania (bold, italic, underline) w HTML
- ✅ Parser HTML (`HTMLParser`) który parsuje edytowany HTML
- ✅ Metoda `update_from_html_file()` do aktualizacji dokumentu z HTML
- ✅ Zachowanie podstawowego formatowania podczas konwersji HTML → DOCX
- ✅ JavaScript do zapisywania zmian w localStorage
- ✅ Obsługa skrótów klawiszowych (Ctrl+B, Ctrl+I, Ctrl+U)

**Priorytet:** ✅ Zakończone

### 5. RelationshipMerger - Pełna Implementacja Zapisu - **✅ ZAIMPLEMENTOWANE**

**Status:** ✅ Podstawowa implementacja gotowa

**Co zostało zaimplementowane:**
- ✅ `_copy_part_content()` - zapis części do wewnętrznej struktury
- ✅ `_add_relationship()` - zapis relacji do wewnętrznej struktury
- ✅ `_write_content_types()` - zapis typów zawartości do wewnętrznej struktury
- ✅ `get_copied_parts()` - zwraca skopiowane części do zapisu
- ✅ `get_relationships_to_write()` - zwraca relacje do zapisu
- ✅ `get_content_types_to_write()` - zwraca typy zawartości do zapisu

**Co może wymagać dopracowania:**
- ⚠️ Integracja z DOCXExporter - wykorzystanie danych z RelationshipMerger podczas eksportu
- ⚠️ Aktualizacja rel_id w XML podczas scalania (częściowo zaimplementowane)

**Priorytet:** 🟡 Średni - podstawowa funkcjonalność działa, wymaga integracji z eksporterem

### 6. apply_layout() - **✅ ZAIMPLEMENTOWANE**

**Status:** ✅ Metoda zaimplementowana

**Co zostało zaimplementowane:**
- ✅ Metoda `Document.apply_layout()` która aplikuje headers/footers z template
- ✅ Convenience method łącząca `merge_headers()` i `merge_footers()`
- ✅ Obsługa selektywnego aplikowania typów headers/footers

**Priorytet:** ✅ Zakończone

### 7. set_list() na Paragraph - **✅ ZAIMPLEMENTOWANE**

**Status:** ✅ Metoda zaimplementowana

**Co zostało zaimplementowane:**
- ✅ Metoda `Paragraph.set_list(level, numbering_id)` do ustawiania numeracji
- ✅ Obsługa różnych typów numbering_id (string, int, NumberingGroup)
- ✅ Automatyczne ustawianie numbering w style
- ✅ Integracja z numbering system

**Priorytet:** ✅ Zakończone

## 📊 Podsumowanie Priorytetów

| Zadanie | Priorytet | Szacowany czas | Status |
|---------|-----------|----------------|--------|
| **PackageWriter (DOCX export)** | 🟢 Niski | - | ✅ Podstawowa implementacja |
| **RelationshipMerger - zapis** | 🟡 Średni | - | ✅ Podstawowa implementacja |
| **Custom blocks - dopracowanie** | 🟢 Niski | - | ✅ Podstawowa implementacja |
| **PDF render integration** | ✅ | - | ✅ Zaimplementowane |
| **set_list() na Paragraph** | ✅ | - | ✅ Zaimplementowane |
| **apply_layout()** | ✅ | - | ✅ Zaimplementowane |
| **HTML workflow** | ✅ | - | ✅ Zaimplementowane |

## 🎯 Rekomendowany Plan Działania

### Faza 1 - Krytyczne (1-2 dni)
1. ✅ **PackageWriter** - podstawowa implementacja zapisu DOCX z relacjami (gotowe)
2. **RelationshipMerger - zapis** - dokończenie zapisu relacji do plików

### Faza 2 - Ważne (zakończone)
3. ✅ **set_list()** - metoda na Paragraph (gotowe)
4. ✅ **PDF render integration** - integracja z PDF compiler (gotowe)
5. ✅ **Custom blocks** - dopracowanie insert_table() i insert_list() (gotowe)

### Faza 3 - Nice to Have (2-3 dni)
6. ✅ **apply_layout()** - convenience method (gotowe)
7. **HTML workflow** - dwukierunkowa konwersja (opcjonalne)

## 📝 Uwagi

- **Renderery pozostają bez zmian** - wszystkie nowe funkcje używają istniejących rendererów
- **Modele są gotowe** - Paragraph, Run, Table, Body są w pełni funkcjonalne
- **Parsery są gotowe** - PackageReader, XMLParser działają poprawnie
- **Główny brak** - PackageWriter do zapisu DOCX z relacjami

