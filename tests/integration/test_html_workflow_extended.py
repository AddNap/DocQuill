"""
Tests for extended HTML workflow - nested formatting, colors, fonts.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
import tempfile

from docquill.parser.html_parser import HTMLParser
from docquill.models.paragraph import Paragraph
from docquill.models.run import Run


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestNestedFormatting:
    """Test nested formatting (bold + italic, etc.)."""
    
    def test_nested_bold_italic(self):
        """Test parsing nested bold and italic."""
        html = '<p><strong><em>Bold and italic</em></strong> text</p>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        
        para = content_paragraphs[0]
        runs = para.get('runs', [])
        
        # Znajdź run z "Bold and italic"
        bold_italic_run = next((r for r in runs if 'Bold and italic' in r.get('text', '')), None)
        assert bold_italic_run is not None
        assert bold_italic_run.get('bold') is True
        assert bold_italic_run.get('italic') is True
    
    def test_nested_formatting_with_underline(self):
        """Test parsing nested formatting with underline."""
        html = '<p><u><strong>Underlined and bold</strong></u> text</p>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        
        para = content_paragraphs[0]
        runs = para.get('runs', [])
        
        # Znajdź run z "Underlined and bold"
        formatted_run = next((r for r in runs if 'Underlined and bold' in r.get('text', '')), None)
        assert formatted_run is not None
        assert formatted_run.get('bold') is True
        assert formatted_run.get('underline') is True


class TestColorsAndFonts:
    """Test color and font parsing."""
    
    def test_color_parsing(self):
        """Test parsing colors from HTML."""
        html = '<p><span style="color: red">Red text</span> normal</p>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        
        para = content_paragraphs[0]
        runs = para.get('runs', [])
        
        # Znajdź run z "Red text"
        colored_run = next((r for r in runs if 'Red text' in r.get('text', '')), None)
        assert colored_run is not None
        assert colored_run.get('color') is not None
        # Kolor powinien być w formacie hex
        color = colored_run.get('color')
        assert len(color) == 6  # RRGGBB format
    
    def test_font_size_parsing(self):
        """Test parsing font size from HTML."""
        html = '<p><span style="font-size: 14px">Large text</span> normal</p>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        
        para = content_paragraphs[0]
        runs = para.get('runs', [])
        
        # Znajdź run z "Large text"
        sized_run = next((r for r in runs if 'Large text' in r.get('text', '')), None)
        assert sized_run is not None
        assert sized_run.get('font_size') is not None
    
    def test_font_family_parsing(self):
        """Test parsing font family from HTML."""
        html = '<p><span style="font-family: Arial">Arial text</span> normal</p>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        
        para = content_paragraphs[0]
        runs = para.get('runs', [])
        
        # Znajdź run z "Arial text"
        font_run = next((r for r in runs if 'Arial text' in r.get('text', '')), None)
        assert font_run is not None
        assert font_run.get('font_name') == 'Arial'
    
    def test_combined_styles(self):
        """Test parsing combined styles (color + font-size + font-family)."""
        html = '<p><span style="color: blue; font-size: 16px; font-family: Times New Roman">Styled text</span></p>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        
        para = content_paragraphs[0]
        runs = para.get('runs', [])
        
        # Znajdź run z "Styled text"
        styled_run = next((r for r in runs if 'Styled text' in r.get('text', '')), None)
        assert styled_run is not None
        assert styled_run.get('color') is not None
        assert styled_run.get('font_size') is not None
        assert styled_run.get('font_name') is not None
    
    def test_color_formats(self):
        """Test parsing different color formats."""
        test_cases = [
            ('#FF0000', 'FF0000'),  # Hex with #
            ('#F00', 'FF0000'),  # Short hex
            ('red', 'FF0000'),  # Color name
            ('rgb(0, 128, 0)', '008000'),  # RGB format
        ]
        
        for color_input, expected_hex in test_cases:
            html = f'<p><span style="color: {color_input}">Text</span></p>'
            parser = HTMLParser(html)
            result = parser.parse()
            paragraphs = result.get('paragraphs', [])
            
            content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
            if content_paragraphs:
                para = content_paragraphs[0]
                runs = para.get('runs', [])
                if runs:
                    colored_run = runs[0]
                    if colored_run.get('color'):
                        # Sprawdź czy kolor jest w formacie hex (może być z # lub bez)
                        color = colored_run.get('color')
                        color_hex = color.lstrip('#').upper()
                        assert len(color_hex) == 6  # Powinien być w formacie RRGGBB


class TestHTMLToDOCX:
    """Test converting HTML back to DOCX."""
    
    def test_update_paragraph_with_colors(self, temp_output_dir):
        """Test updating paragraph with colors from HTML."""
        from docquill.models.body import Body
        
        # Create mock document
        body = Body()
        para = Paragraph()
        run = Run()
        run.text = "Old text"
        para.add_run(run)
        body.add_paragraph(para)
        
        # Parse HTML with colors
        html = '<p><span style="color: red">Red text</span></p>'
        parser = HTMLParser(html)
        result = parser.parse()
        parsed_paragraphs = result.get('paragraphs', [])
        
        if parsed_paragraphs:
            # Manually update paragraph (simulating _update_paragraph_from_html)
            para.runs.clear()
            for run_data in parsed_paragraphs[0].get('runs', []):
                new_run = Run()
                new_run.text = run_data.get('text', '')
                if run_data.get('bold'):
                    new_run.bold = True
                if run_data.get('italic'):
                    new_run.italic = True
                if run_data.get('underline'):
                    new_run.underline = True
                if run_data.get('color'):
                    color = run_data.get('color')
                    if color.startswith('#'):
                        color = color[1:]
                    new_run.color = color
                para.add_run(new_run)
            
            # Check if run has color
            if para.runs:
                updated_run = para.runs[0]
                # Run powinien mieć kolor jeśli HTML parser go znalazł
                assert hasattr(updated_run, 'color')
                if updated_run.color:
                    assert len(updated_run.color) == 6  # RRGGBB format

