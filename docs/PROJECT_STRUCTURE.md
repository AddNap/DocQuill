# Struktura Projektu DocQuill

## 📁 Organizacja Katalogów

```
DocQuill/
├── README.md                          # Główny README projektu
├── compiler/                          # Kompilator PDF
│   ├── __init__.py
│   ├── cli.py                         # CLI kompilatora
│   ├── pdf_compiler.py                # Główny kompilator PDF
│   ├── preprocessor.py                # Preprocessor
│   ├── compilation_context.py         # Kontekst kompilacji
│   ├── diagnostics.py                 # Diagnostyka
│   └── backends/                      # Backendy renderowania
│       ├── pdf_backend.py             # Backend PDF
│       └── pdf/                       # Direct PDF writer
│           ├── direct_writer.py
│           └── __init__.py
│
├── docx_interpreter/                  # Główny pakiet
│   ├── __init__.py                    # Eksport głównych klas
│   ├── document.py                    # Klasa Document
│   ├── context.py                     # DocumentContext
│   ├── cli.py                         # CLI interpretera
│   │
│   ├── engine/                        # Silnik layoutu
│   │   ├── layout_engine.py           # DocumentEngine (główny)
│   │   ├── base_engine.py             # Bazowe klasy (LayoutPage, LayoutBlock)
│   │   ├── paragraph_engine.py        # Silnik paragrafów
│   │   ├── table_engine.py            # Silnik tabel
│   │   ├── image_engine.py            # Silnik obrazów
│   │   ├── paginator.py               # Paginacja
│   │   ├── line_breaker.py            # Łamanie linii
│   │   ├── numbering_formatter.py     # Formatowanie numeracji
│   │   ├── placeholder_resolver.py    # Rozwiązywanie placeholderów
│   │   ├── styles_bridge.py           # Most między stylami
│   │   ├── font_resolver.py           # Rozwiązywanie fontów
│   │   ├── geometry.py                # Geometria (Size, Margins, Rect)
│   │   └── text_metrics/              # Metryki tekstu
│   │       ├── text_metrics_engine.py
│   │       ├── font_loader.py
│   │       ├── glyph_metrics.py
│   │       ├── harfbuzz_shaper.py
│   │       └── __init__.py
│   │
│   ├── parser/                        # Parsery DOCX
│   │   ├── package_reader.py          # Czytanie pakietów DOCX
│   │   ├── xml_parser.py              # Parser XML
│   │   ├── style_parser.py            # Parser stylów
│   │   ├── numbering_parser.py        # Parser numeracji
│   │   ├── table_parser.py            # Parser tabel
│   │   ├── header_footer_parser.py    # Parser header/footer
│   │   ├── drawing_parser.py          # Parser rysunków
│   │   ├── field_parser.py            # Parser field codes
│   │   ├── font_parser.py             # Parser fontów
│   │   └── ... (inne parsery)
│   │
│   ├── renderers/                     # Renderery
│   │   ├── base_renderer.py           # Bazowy renderer
│   │   ├── pdf_renderer.py            # Renderer PDF (ReportLab)
│   │   ├── text_renderer.py           # Renderer tekstu
│   │   ├── table_renderer.py           # Renderer tabel
│   │   ├── image_renderer.py          # Renderer obrazów
│   │   ├── header_footer_renderer.py  # Renderer header/footer
│   │   ├── list_renderer.py           # Renderer list
│   │   ├── render_utils.py            # Narzędzia renderowania
│   │   └── diagnostics.py              # Diagnostyka renderowania
│   │
│   ├── models/                        # Modele danych
│   │   ├── paragraph.py               # Model paragrafu
│   │   ├── table.py                    # Model tabeli
│   │   ├── run.py                      # Model runu
│   │   ├── image.py                    # Model obrazu
│   │   ├── textbox.py                  # Model textboxu
│   │   └── ... (inne modele)
│   │
│   ├── layout/                        # Layout (struktura dokumentu)
│   │   ├── page.py                     # Model strony
│   │   ├── section.py                  # Model sekcji
│   │   ├── body.py                     # Model body
│   │   ├── header.py                   # Model header
│   │   ├── footer.py                   # Model footer
│   │   ├── pagination_manager.py       # Menadżer paginacji
│   │   └── numbering_resolver.py       # Resolver numeracji
│   │
│   ├── styles/                        # Style i tematy
│   │   ├── style_manager.py           # Menadżer stylów
│   │   ├── style_resolver.py          # Resolver stylów
│   │   └── defaults.py                # Domyślne style
│   │
│   ├── export/                        # Eksport do różnych formatów
│   │   ├── json_exporter.py
│   │   ├── json_exporter_enhanced.py
│   │   ├── html_exporter.py
│   │   ├── xml_exporter.py
│   │   └── ... (inne eksportery)
│   │
│   ├── utils/                         # Narzędzia pomocnicze
│   │   ├── units.py                    # Konwersja jednostek
│   │   ├── color_utils.py             # Narzędzia kolorów
│   │   ├── xml_utils.py                # Narzędzia XML
│   │   └── ... (inne utils)
│   │
│   └── ... (inne moduły: pdf_engine, pdf_integration, etc.)
│
├── tests/                             # Testy
│   ├── __init__.py
│   ├── conftest.py                    # Fixtures pytest
│   ├── pytest.ini                     # Konfiguracja pytest
│   ├── run_tests.py                   # Skrypt uruchamiania testów
│   ├── requirements.txt               # Zależności testowe
│   ├── README.md                      # Dokumentacja testów
│   ├── files/                         # Pliki testowe
│   │   └── Zapytanie_Ofertowe.docx    # Główny plik testowy
│   ├── parsers/                       # Testy parserów
│   ├── renderers/                     # Testy rendererów
│   ├── engines/                        # Testy silników
│   └── Interpreter/                   # Testy integracyjne
│
├── docs/                              # Dokumentacja
│   ├── README.md                       # Ten plik
│   ├── ARCHITECTURE_PLAN.md           # Plan architektury
│   ├── PROJECT_REVIEW.md              # Ocena projektu
│   ├── ENGINE_COMPILER_COMMUNICATION.md # Komunikacja Engine ↔ Compiler
│   └── ... (inne dokumenty .md)
│
├── scripts/                           # Skrypty pomocnicze
│   ├── benchmark.py                   # Benchmark wydajności
│   ├── layout_comparison_analysis.py  # Analiza porównawcza layoutu
│   └── renderer_comparison_analysis.py # Analiza porównawcza rendererów
│
├── tools/                             # Narzędzia
│   └── docx_interpreter.zip           # Archiwum (jeśli istnieje)
│
├── output/                            # Wyniki generowania
│   ├── tests/                         # Wyniki testów (PDFy, HTML)
│   ├── images/                        # Obrazy
│   └── media/                         # Media
│
└── ... (inne pliki konfiguracyjne)
```

## 🔄 Przepływ Danych

### Główny Workflow PDF

```
DOCX File
    ↓
Document.parse()          # docx_interpreter/document.py
    ↓
DocumentModel              # Modele danych
    ↓
PdfCompiler.compile()      # compiler/pdf_compiler.py
    ↓
Preprocessor               # compiler/preprocessor.py
    ↓
DocumentEngine.build_layout()  # docx_interpreter/engine/layout_engine.py
    ↓
List[LayoutPage]          # LayoutPages z LayoutBlocks
    ↓
PdfBackend.render()       # compiler/backends/pdf_backend.py
    ↓
PDF File
```

### Komponenty

1. **compiler/** - Orkiestracja kompilacji PDF
2. **docx_interpreter/engine/** - Obliczanie layoutu
3. **docx_interpreter/renderers/** - Renderowanie (używane przez PdfBackend w trybie "reportlab")
4. **compiler/backends/** - Backendy renderowania (direct/reportlab)

## 📝 Uwagi

- **README.md** - w root, główny plik dokumentacji projektu
- **docs/** - wszystkie dokumenty techniczne i statusowe
- **scripts/** - skrypty analityczne i benchmarkowe
- **tools/** - narzędzia pomocnicze (archiwa, itp.)
- **tests/** - wszystkie testy w jednym miejscu
- **output/** - wygenerowane pliki (może być w .gitignore)

