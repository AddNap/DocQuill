# DocQuill / DoclingForge 2.0 – Kompletny Opis Projektu

> Ten dokument stanowi jedną, skondensowaną referencję opisującą architekturę, modele danych, pipeline’y, API, technologie, zastosowania AI, konkurencję oraz potencjał biznesowy biblioteki. Można go skopiować w całości i przekazać interesariuszom lub partnerom.

---

## 1. Cel i Zakres
- **DocQuill** (znany też jako DoclingForge 2.0) to zaawansowana biblioteka Python do pełnej obsługi dokumentów DOCX – od parsowania, przez manipulację modelem i pipeline layoutu, aż po renderowanie HTML/PDF z wydajnym backendem w Rust.
- Projekt działa pod licencją **MIT** i jest dostępny przez `pip install docx-interpreter`.
- Wyróżniki:
  - 20+ typów placeholderów Jinja-like (w tym tekst, daty, waluty, listy, tabele, QR, watermarks).
  - Selektory do scalania dokumentów (body, headers, footers, style) z zachowaniem relacji OPC.
  - Dwukierunkowy workflow: DOCX ⇄ HTML (edytowalny), JSON layout ⇄ DOCX (importer pipeline).
  - Renderowanie PDF zarówno w czystym Pythonie (ReportLab) jak i przez szybki backend Rust.
  - Eksport layoutu w formacie „optimized_pipeline” przygotowany do analizy i modyfikacji przez AI.

---

## 2. Struktura Repozytorium
- `docx_interpreter/` – główny pakiet:
  - `parser/` – PackageReader, XMLParser, style/numbering parser, obsługa drawings, footnotes itd.
  - `engine/` – LayoutPipeline, geometry, paginacja, placeholder resolver, text metrics (HarfBuzz, font loader).
  - `models/` – Body, Paragraph, Run, Table, Image, TextBox, Section itp.
  - `renderers/` – renderery PDF/HTML/list/headers/footers + narzędzia diagnostyczne.
  - `export/` – JSON/HTML/XML eksportery.
  - `importers/pipeline_json_importer.py` – importer JSON → UnifiedLayout → Document Model → DOCX.
  - `styles/`, `layout/`, `utils/`, `media/`, `plugin_system.py`, `document_api.py`, `api.py`.
- `compiler/` – PDFCompiler, preprocessor, diagnostyka, backendy.
- `pdf_renderer_rust/` – moduł Rust (PyO3 + `pdf-writer`) renderujący UnifiedLayout w trybie natywnym.
- `scripts/` – generatory PDF/HTML, benchmarki, testy integracyjne.
- `docs/` – rozbudowana dokumentacja (API, architektura, porównania rynkowe, analizy AI, statusy).
- `output/` – przykładowe wyniki (np. `zapytanie_pipeline_final.json`, PDF/HTML, analizy AI).

### Kluczowe pliki dokumentacyjne
- `README.md` – wprowadzenie, funkcje, przykłady użycia, typy placeholderów, szybki start.
- `docs/API_GUIDE.md` – opis metod `Document` i convenience functions.
- `docs/PROJECT_STRUCTURE.md` – szczegółowy opis modułów i workflow.
- `docs/COMPETITION_ANALYSIS.md` – analiza konkurencji (python-docx, Aspose, Mammoth, Pandoc, wrappery .NET/Java itp.).
- `docs/ENGINE_FEATURES_ANALYSIS.md`, `PDF_ENGINE_STATUS.md`, `RUST_RENDERER_*` – status silników i pracy nad backendem Rust.

---

## 3. Model Danych i Pipeline

### 3.1 Document Model (Parser Layer)
- Parser (`XMLParser`) wykorzystuje wzorzec fabryki (TAG_MAP) i obsługuje:
  - paragrafy, runy, tabele, obrazy (wp:anchor/wp:inline, VML watermarki), textboxes (AlternateContent, VML, DrawingML), field codes (`fldSimple`, `fldChar`), footnotes/endnotes, bookmarks, hyperlinki, SDT, sekcje (sectPr), nagłówki/stopki, metadata (core/app/custom), docGrid, numerację, style, shading, borders, commentary.
  - Każdy element zachowuje surowy XML (np. `Paragraph.raw_xml`, `Run.raw_xml`) na potrzeby lossless round-trip.
  - Parsowane są właściwości formatowania: spacing, justification, indentation, numbering, shading, fonts, highlight, superscript/subscript, kerning, języki, layout kolumn (cols), docGrid, page size/margins.

### 3.2 LayoutPipeline
- Przyjmuje Document Model i konwertuje go do UnifiedLayout (listy stron z blokami i ramkami).
- Uwzględnia:
  - PageConfig (rozmiar strony, marginesy bazowe, wczytywane z sekcji DOCX).
  - Placeholder resolver, line breaker, numbering formatter, text metrics (HarfBuzz), paginację, footnote renderer (NotesParser → FootnoteRenderer).
  - Asynchroniczną prekonwersję WMF/EMF z cachingiem (MediaConverter + image_cache).
  - Walidację elementów (opcjonalną).

### 3.3 UnifiedLayout i JSON
- `UnifiedLayout` zawiera listę `LayoutPage`, każda strona ma `LayoutBlock` z ramką (`Rect`) i typem (`paragraph`, `table`, `image`, `decorator`, `header`, `footer`, `footnotes`, `endnotes` itd.).
- Eksport „optimized_pipeline” deduplikuje `styles` i `media`, przechowuje `source_uid`, `sequence`, pozycje i informacje stylów. W sample (`output/zapytanie_pipeline_final.json`):
  - `metadata.total_pages = 9`, `styles` – 114 stylów, `media` – 9 obrazów, `pages` – ramki w punktach.
  - Dane gotowe do analizy AI (pozycjonowanie, typy bloków, tekst, listy, tabele).
- `PipelineJSONImporter` potrafi odczytać JSON w dwóch formatach (nowy – body/headers/footers; stary – pages/blocks), przywrócić Document Model, uzupełnić nagłówki/stopki na podstawie oryginalnych relacji OPC i powtórnie wyeksportować do DOCX.

### 3.4 Renderowanie
- **PDFCompiler**:
  - Przyjmuje UnifiedLayout i render_timings.
  - Konfigurowalny backend: ReportLab (Python) lub `pdf_renderer_rust` (domyślnie, sekwencyjny, `parallelism=1` domyślnie, bo overhead).
  - Obsługuje watermarki (globalne `watermark_opacity` lub z layoutu), footnotes, odwołania, style.
- **HTML**:
  - `doc.render_html(..., editable=True/False)` – generuje edytowalny lub read-only HTML z CSS, możliwością embeddowania obrazów.
  - `doc.update_from_html_file(...)` – reverse transform, by HTML edytowany w przeglądarce sprowadzić z powrotem do Document Model.
- **DOCX**:
  - `doc.save()`, `normalize()`, scalanie (`merge`, `merge_selective`, `merge_headers`, `merge_footers`), numeracja, listy itp.

### 3.5 Pipeline Profiling i Skrypty
- `scripts/generate_pdf_production.py` – główny skrypt produkcyjny: ładowanie DOCX, margin detection, pipeline, prekonwersja obrazów, oczekiwanie na cache, render PDF, timingi, opcjonalne profilowanie cProfile.
- Profilowanie: `--profile`, `--profile-output`, `--profile-lines` (cProfile + pstats, w tym filtry „rust”).
- Benchmarki i logi w `benchmark_pdf_*.log`, `output/benchmark/`.

---

## 4. API i Wysokopoziomowe Funkcje

### 4.1 Klasa `Document`
- Konstrukcja: `Document('file.docx')`, `Document.open(...)`, `Document.create()`.
- Główne metody:
  - `to_model()` – zwraca model z parsera.
  - `pipeline(page_size, margins, apply_headers_footers, validate, target)` – buduje UnifiedLayout.
  - `to_pdf(output_path, backend='rust', page_size, margins, parallelism, watermark_opacity, apply_headers_footers)` – generuje PDF.
  - `to_html(output_path, editable, embed_images_as_data_uri, apply_headers_footers)` – generuje HTML.
  - `normalize(output_path)` – oczyszcza dokument (runs, style).
  - `fill_placeholders(dict)` – wstawia dane do placeholderów (tekst, daty, waluty, tabele, listy, QR, obrazy, warunkowe bloki START_/END_).
  - `render_pdf`, `render_html`, `update_from_html_file`, `validate_layout`, `get_metadata`, `get_stats`, `get_sections`, `get_styles`, `get_numbering`, `add_watermark`, `get_watermarks`.
  - `merge`, `merge_selective`, `merge_headers`, `merge_footers`, `append`, `prepend`, `replace_text`, `process_conditional_block`, `extract_placeholders`, `save`.

### 4.2 Convenience API
- `fill_template`, `merge_documents`, `render_to_pdf`, `render_to_html`, `open_document`, `create_document` (jednolinijkowe wywołania).
- Wsparcie dla list numerowanych/punktowanych, edycji runów (bold/italic/underline/color/font), tabel (nagłówki, komórki, rowspan/colspan, borders), metadata, watermarków.

### 4.3 Typy Placeholderów
- 20+ typów, m.in.: TEXT, DATE, CURRENCY, PHONE, QR, TABLE, IMAGE, LIST, CONDITIONAL, a także START_/END_ bloków (np. `{{ START_SpecialOffer }}` → `process_conditional_block("SpecialOffer", show=True/False)`).
- Format: `{{ TYPE:Key }}` (np. `{{ TEXT:Name }}`, `{{ DATE:IssueDate }}`, `{{ TABLE:Items }}`).

---

## 5. Technologie i Implementacja
- **Python 3** – główne API, parser, layout, ReportLab backend, CLI, skrypty.
- **Rust (PyO3)** – `pdf_renderer_rust`: rendering PDF z `pdf-writer`, docelowo z obsługą fontów, obrazów, multi-line text layout, rounded rectangles (TODO list w README).
- **HarfBuzz** – shaping tekstu w LayoutPipeline (metryki, ligatury).
- **Media pipeline** – asynchroniczna konwersja WMF/EMF, caching obrazów.
- **Profilowanie** – `cProfile`, `pstats`, logowanie timingu poszczególnych etapów (doc_load, preconvert, layout, image_wait, render, total).
- **Testy** – `tests/` z plikami DOCX (np. `Zapytanie_Ofertowe.docx`), testy parserów/renderów/engine, coverage w `htmlcov/`.

---

## 6. Workflow AI i JSON
- Eksport JSON (`zapytanie_pipeline_final.json`) zawiera:
  - `metadata` (liczba stron, źródło, current_page), `styles` (deduplikowane definicje), `media` (referencje do obrazów), `pages` (lista bloków z `frame`, `block_type`, `content`, `style`, `source_uid`, `sequence`, flagami header/footer).
  - Tekst w blokach (`runs`, `list`, `paragraph_properties`), tabele (`rows`, `columns`, `borders`, `cell_margins`), obrazy (media_id, ścieżki, rozmiary).
- Analiza AI (`zapytanie_pipeline_final_ai_analysis.json`) ocenia dane na 10/10 (kompletna struktura, pozycje, tekst, stylowanie, semantyka).
- Potencjalne kroki AI:
  1. Eksport layoutu do JSON.
  2. Analiza/edycja przez model (np. wypełnienie braków, poprawki redakcyjne, tagowanie sekcji, transformacje layoutu).
  3. Import JSON → UnifiedLayout → Document Model → DOCX/PDF.
  4. Opcjonalnie HTML round-trip i z powrotem do DOCX.
- Możliwości: QA layout-aware, ekstrakcja danych, automatyczne uzupełnianie formularzy, generowanie raportów, adaptacja layoutu, walidacja spójności, generowanie datasetów multimodalnych (tekst + koordynaty + styl).

---

## 7. Zgodność, Jakość i Diagnostyka
- Parser zachowuje wszystkie elementy WordprocessingML (w tym te rzadko obsługiwane: footnote/endnote, VML, AlternateContent, docGrid, sekcje, numbering, shading, Watermarks).
- Layout pipeline przelicza marginesy i page size na podstawie sekcji (wyciąga twips i konwertuje na punkty).
- Renderery odzwierciedlają style, spacing, listy, tabelaryczne edges, watermarki.
- W `docs/ENGINE_FEATURES_ANALYSIS.md`, `PDF_ENGINE_STATUS.md`, `RUST_RENDERER_*` opisana jest zgodność, braki i roadmapa.
- CLI/skripty logują etapy i timingi, profilowanie cProfile/użycie pstats (w tym filtr „rust”).

---

## 8. Konkurencja i Pozycja Rynkowa
- `docs/COMPETITION_ANALYSIS.md` porównuje DocQuill z:
  - **python-docx** – bardzo popularna, ale obsługuje ~20% DOCX (brak footnotes, textboxes, field codes, watermarks, renderowania PDF/HTML, placeholderów, mergers). DocQuill pokrywa wszystkie te elementy.
  - **Aspose.Words / Spire.Doc / GroupDocs / Syncfusion** – wrappery .NET/Java, płatne (999 USD+/rok), wymagają dodatkowych środowisk, brak Pythonic API i placeholder engine.
  - **Mammoth** – konwersja DOCX→HTML, bez edycji DOCX/Tables/PDF.
  - **Pandoc** – potężna konwersja formatów, ale brak manipulacji DOCX i placeholderów.
  - **LibreOffice API** – pełne możliwości, ale ciężkie, wolniejsze, trudne w automatyzacji, brak placeholder engine.
- Wniosek: **DocQuill jest jedyną natywną, open-source’ową biblioteką Python z pełną obsługą DOCX i renderowaniem PDF/HTML** oraz dodatkowymi funkcjami (placeholder engine, document merger, JSON pipeline, AI ready). To umożliwia pozycjonowanie projektu jako alternatywy dla drogich SDK i jako warstwa automatyzacji on-premise.

---

## 9. Czynniki Biznesowe i Monetyzacja
- Potencjalne modele:
  - **Licencje / subskrypcje** za zaawansowane dodatki (np. profesjonalny backend Rust, hostowane API, gotowe szablony branżowe, integracje CRM/ERP).
  - **Wsparcie i SLA** dla firm (integracja, custom features, migracja).
  - **Wdrożenia AI** – projektowanie procesów „document intelligence” dla finansów, prawa, administracji (generowanie ofert, audyty, weryfikacja RFP, raporty).
  - **Hosted SaaS** – pipeline DOCX→PDF/HTML z REST API, rozliczanie per dokument (0.05–0.50 USD/dok) lub w pakietach (np. 199 USD/mies. za unlimited self-host + support).
  - **Konsulting** – integracje specyficzne (wartość kontraktów rzędu 3–50 tys. USD).
- Mimo że projekt jest jednoosobowy, zakres funkcji jest porównywalny z komercyjnymi SDK, więc produkt ma realną wartość rynkową. Warunek: skupienie na segmencie (np. oferty B2B, kancelarie, urzędy) i budowa historii sukcesów / community.

---

## 10. Przykładowy Workflow Produkcyjny
1. Uruchom `scripts/generate_pdf_production.py`:
   - Wczytuje `tests/files/Zapytanie_Ofertowe.docx`.
   - Wykrywa marginesy z sekcji DOCX (konwersja twips → pt).
   - Tworzy `LayoutPipeline`, prekonwertuje obrazy (body + header + footer), ustawia footnote renderer, przetwarza layout, czeka na cache obrazów, raportuje liczbę stron/bloków, loguje timingi.
   - Wybiera backend (Rust domyślnie) i kompiluje PDF → `output/Zapytanie_Ofertowe_production.pdf`.
   - Opcjonalnie działa z profilowaniem (`--profile`) i zapisuje `profile_stats.prof`.
2. Eksport JSON layoutu:
   - `doc.export_layout('zapytanie_pipeline_final.json', format='optimized_pipeline')` (przykładowy plik w repo).
3. Analiza AI (np. `docs/AI_ANALYSIS_JSON_EVALUATION.md`) – ocena jakości danych, statystyki tekstu, liczba bloków.
4. Import JSON → UnifiedLayout → Document Model → DOCX (np. w workflow rewizyjnym AI).

---

## 11. Najważniejsze Artefakty Referencyjne
- `README.md` – przegląd funkcji, przykłady kodu.
- `docs/API_GUIDE.md` – opis metod `Document` i convenience API.
- `docx_interpreter/parser/xml_parser.py` – najważniejszy parser (2886 linii) obsługujący wszystkie elementy DOCX.
- `docx_interpreter/importers/pipeline_json_importer.py` – JSON importer (1246 linii) zapewniający dwukierunkowy przepływ.
- `scripts/generate_pdf_production.py` – w pełni opisany pipeline produkcyjny.
- `output/zapytanie_pipeline_final.json` – przykład layoutu A4 z 9 stronami, 114 stylami, 9 mediami.
- `output/zapytanie_pipeline_final_ai_analysis.json` – ocena JSON przez pipeline AI (10/10).
- `docs/COMPETITION_ANALYSIS.md` – tabele porównawcze z python-docx, Aspose, wrapperami .NET, Pandoc, Mammoth itd.
- `pdf_renderer_rust/README.md` – opis backendu Rust i TODO listy (font loading, obrazki, multi-line text).

---

## 12. Podsumowanie
DocQuill/DoclingForge 2.0 to unikatowy projekt łączący:
- Kompletny parser DOCX z zachowaniem pełnej semantyki i stylów.
- Pipeline layoutu gotowy na generację PDF/HTML (z dwoma backendami) oraz round-trip HTML i JSON.
- Narzędzia do integracji z AI (eksport layoutu, importer JSON, metadane layoutu, prekonwersja obrazów).
- Rozbudowane API wysokiego poziomu do template’ów, placeholderów, list, merge’ów, metadata, normalizacji, walidacji.
- Bogatą dokumentację i benchmarki porównawcze, które pokazują przewagę nad popularnymi i komercyjnymi rozwiązaniami.

Dzięki temu biblioteka może służyć jako:
- Podstawowy silnik generowania dokumentów w firmach (oferty, raporty, umowy, korespondencja na bazie template’ów).
- Warstwa automatyzacji AI (extraction, redaction, tagging, auto-fill, generowanie datasetów multimodalnych).
- Otwarte narzędzie dla społeczności Python, które wypełnia lukę między prostymi bibliotekami (python-docx) a drogimi, zamkniętymi SDK (.NET/Java).

---

_Opracował: **GPT-5.1 Codex** na podstawie repozytorium `/home/napir/Projects/DoclingForge.2.0` (listopad 2025)._

