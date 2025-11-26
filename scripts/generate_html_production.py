#!/usr/bin/env python3
"""
Skrypt do generowania produkcyjnego HTML z UnifiedLayout używając nowego HTMLCompiler.

Struktura i przepływ są celowo zbliżone do `generate_pdf_production.py`, aby ułatwić
utrzymanie obu ścieżek renderowania.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docx_interpreter.parser.package_reader import PackageReader
from docx_interpreter.parser.xml_parser import XMLParser
from docx_interpreter.engine.layout_pipeline import LayoutPipeline
from docx_interpreter.engine.geometry import Size, Margins, twips_to_points
from docx_interpreter.engine.page_engine import PageConfig
from docx_interpreter.engine.html import HTMLCompiler, HTMLCompilerConfig


def _read_margins_from_docx(xml_parser: XMLParser) -> Margins:
    """
    Pomocnicza funkcja do pobrania marginesów z dokumentu DOCX.
    """
    sections = xml_parser.parse_sections()
    if not sections:
        return Margins(top=72, bottom=72, left=72, right=72)

    section = sections[0]
    margins_data = section.get("margins") if isinstance(section, dict) else None
    if not margins_data:
        return Margins(top=72, bottom=72, left=72, right=72)

    def _get_margin_twips(key: str, default: int = 1440) -> int:
        raw = margins_data.get(key, default)
        if isinstance(raw, str):
            try:
                raw = int(raw)
            except (TypeError, ValueError):
                return default
        if raw is None:
            return default
        return int(raw)

    return Margins(
        top=twips_to_points(_get_margin_twips("top")),
        bottom=twips_to_points(_get_margin_twips("bottom")),
        left=twips_to_points(_get_margin_twips("left")),
        right=twips_to_points(_get_margin_twips("right")),
    )


def main() -> int:
    """Generuj HTML z przykładowego dokumentu DOCX."""
    input_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    output_path = project_root / "output" / "Zapytanie_Ofertowe_production.html"

    output_path.parent.mkdir(exist_ok=True)

    if not input_path.exists():
        print(f"❌ Błąd: Plik wejściowy nie znaleziony: {input_path}")
        return 1

    print(f"📄 Plik wejściowy: {input_path}")
    print(f"📄 Plik wyjściowy: {output_path}")
    print()

    try:
        # 1. Załaduj i sparsuj dokument
        print("🔄 Krok 1: Ładowanie dokumentu...")
        package_reader = PackageReader(input_path)
        xml_parser = XMLParser(package_reader)
        body = xml_parser.parse_body()
        print(f"✅ Dokument sparsowany: {len(body.children)} elementów")

        # 2. Utwórz adapter dokumentu
        print("🔄 Krok 2: Przygotowanie modelu...")

        class DocumentAdapter:
            def __init__(self, body_obj, parser):
                self.elements = body_obj.children if hasattr(body_obj, "children") else []
                self.parser = parser

        document_model = DocumentAdapter(body, xml_parser)
        print(f"✅ Model przygotowany: {len(document_model.elements)} elementów")

        # 3. Konfiguracja strony
        print("🔄 Krok 3: Konfiguracja strony...")
        margins = _read_margins_from_docx(xml_parser)
        page_config = PageConfig(page_size=Size(595, 842), base_margins=margins)
        print(
            f"✅ Konfiguracja: marginesy (top={margins.top:.1f}, bottom={margins.bottom:.1f}, "
            f"left={margins.left:.1f}, right={margins.right:.1f})"
        )

        # 4. Przetwarzanie layoutu
        print("🔄 Krok 4: Przetwarzanie layoutu...")
        pipeline = LayoutPipeline(page_config, target="html")
        unified_layout = pipeline.process(
            document_model,
            apply_headers_footers=True,
            validate=False,
        )
        total_blocks = sum(len(p.blocks) for p in unified_layout.pages)
        print(f"✅ Layout utworzony: {len(unified_layout.pages)} stron, {total_blocks} bloków")

        # 5. Renderowanie HTML
        print("🔄 Krok 5: Renderowanie HTML...")
        compiler = HTMLCompiler(
            HTMLCompilerConfig(
                output_path=output_path,
                title="Zapytanie ofertowe (HTML Preview)",
                embed_default_styles=True,
            ),
            package_reader=package_reader,
        )
        result_path = compiler.compile(unified_layout)

        if result_path.exists():
            file_size = result_path.stat().st_size
            print()
            print("✅ HTML wygenerowany pomyślnie!")
            print(f"   Plik: {result_path}")
            print(f"   Rozmiar: {file_size:,} bajtów")
            print(f"   Stron (layout): {len(unified_layout.pages)}")
            print()
            print("📊 Podsumowanie:")
            print(f"   - Stron: {len(unified_layout.pages)}")
            print(f"   - Bloków: {total_blocks}")
            return 0

        print("❌ Błąd: Plik HTML nie został utworzony")
        return 1

    except Exception as exc:  # pragma: no cover - diagnostyka ręczna
        print(f"❌ Błąd: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

