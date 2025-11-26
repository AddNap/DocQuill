"""Tests for new pdfcompiler architecture."""

import pytest
from pathlib import Path
from docx_interpreter.document import Document
from docx_interpreter.engine.base_engine import LayoutPage, LayoutBlock
from docx_interpreter.engine.geometry import Rect, Size, Margins

from compiler import PdfCompiler, CompilerOptions
from pdfcompiler import PDFCompiler


@pytest.mark.integration
def test_pdfcompiler_basic(tmp_path):
    """Test basic PDF generation with new pdfcompiler."""
    output_path = tmp_path / "test_pdfcompiler.pdf"
    
    # Create a simple layout page
    page_size = Size(width=595.28, height=841.89)  # A4
    margins = Margins(top=72.0, right=72.0, bottom=72.0, left=72.0)
    
    layout_page = LayoutPage(
        number=1,
        size=page_size,
        margins=margins,
    )
    
    # Create a simple paragraph block
    paragraph_block = LayoutBlock(
        frame=Rect(x=72.0, y=700.0, width=451.28, height=20.0),
        content={
            "text": "Hello, World!",
            "lines": [
                {
                    "text": "Hello, World!",
                    "line_height": 12.0,
                }
            ],
            "runs": [],
        },
        style={
            "font_name": "Helvetica",
            "font_size": 12.0,
            "color": "#000000",
        },
        block_type="paragraph",
    )
    
    layout_page.add_block(paragraph_block)
    
    # Compile using new pdfcompiler
    compiler = PDFCompiler(output_path)
    result = compiler.compile([layout_page])
    
    # Verify
    assert result == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    
    print(f"\n✅ PDF generated: {output_path}")
    print(f"   Size: {output_path.stat().st_size:,} bytes")


@pytest.mark.integration
def test_pdfcompiler_via_compiler(sample_docx_path, tmp_path):
    """Test new pdfcompiler via PdfCompiler wrapper."""
    input_path = Path(sample_docx_path)
    output_path = tmp_path / "test_pdfcompiler_via_compiler.pdf"
    
    # Load document
    document = Document.from_file(input_path)
    
    # Use new pdfcompiler backend
    options = CompilerOptions(
        renderer="pdfcompiler",  # Use new architecture
    )
    
    compiler = PdfCompiler(document, output_path, options)
    result = compiler.compile()
    
    # Verify
    assert result == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    
    print(f"\n✅ PDF generated via PdfCompiler: {output_path}")
    print(f"   Size: {output_path.stat().st_size:,} bytes")


@pytest.mark.integration
def test_pdfcompiler_fonts(tmp_path):
    """Test font registry in pdfcompiler."""
    from pdfcompiler.resources import PdfFontRegistry
    
    registry = PdfFontRegistry()
    
    # Register fonts
    font1 = registry.register_font("Arial", bold=False, italic=False)
    font2 = registry.register_font("Arial", bold=True, italic=False)
    font3 = registry.register_font("Arial", bold=False, italic=True)
    font4 = registry.register_font("Arial", bold=True, italic=True)
    
    # Verify aliases
    assert font1.alias == "/F1"
    assert font2.alias == "/F2"
    assert font3.alias == "/F3"
    assert font4.alias == "/F4"
    
    # Verify same font variant returns same object
    font1_again = registry.register_font("Arial", bold=False, italic=False)
    assert font1_again is font1
    
    # Get resources
    resources = registry.get_resources_dict()
    assert len(resources) == 4
    
    print(f"\n✅ Font registry test passed")
    print(f"   Registered fonts: {len(resources)}")


@pytest.mark.integration
def test_pdfcompiler_text_rendering(tmp_path):
    """Test text rendering with decorators."""
    from pdfcompiler.resources import PdfFontRegistry
    from pdfcompiler.text_renderer import PdfTextRenderer
    from pdfcompiler.objects import PdfStream
    
    registry = PdfFontRegistry()
    renderer = PdfTextRenderer(registry)
    
    stream = PdfStream()
    
    # Render text with different styles
    renderer.render_run(
        stream,
        text="Hello",
        x=100.0,
        y=700.0,
        style={
            "font_name": "Helvetica",
            "font_size": 12.0,
            "color": "#000000",
        },
    )
    
    renderer.render_run(
        stream,
        text="Bold",
        x=150.0,
        y=700.0,
        style={
            "font_name": "Helvetica",
            "font_size": 12.0,
            "bold": True,
            "color": "#000000",
        },
    )
    
    renderer.render_run(
        stream,
        text="Italic",
        x=200.0,
        y=700.0,
        style={
            "font_name": "Helvetica",
            "font_size": 12.0,
            "italic": True,
            "color": "#000000",
        },
    )
    
    # Verify stream has commands
    content = stream.get_content()
    assert "BT" in content
    assert "ET" in content
    assert "Tf" in content
    
    print(f"\n✅ Text rendering test passed")
    print(f"   Stream length: {len(content)} characters")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

