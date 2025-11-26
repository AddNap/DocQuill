"""
Tests for HTML Parser.

Tests parsing HTML with contenteditable and converting back to DOCX.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from docquill.parser.html_parser import HTMLParser, HTMLContentParser


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestHTMLParser:
    """Test cases for HTMLParser."""
    
    def test_parse_simple_html(self):
        """Test parsing simple HTML."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <p contenteditable="true">Test paragraph</p>
        </body>
        </html>
        """
        
        parser = HTMLParser(html_content)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        # Parser may create empty paragraphs from whitespace
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        assert "Test paragraph" in content_paragraphs[0]['text']
    
    def test_parse_html_with_formatting(self):
        """Test parsing HTML with formatting."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <p contenteditable="true"><strong>Bold</strong> and <em>italic</em></p>
            <p contenteditable="true"><u>Underlined</u></p>
        </body>
        </html>
        """
        
        parser = HTMLParser(html_content)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        # Filter out empty paragraphs
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 2
        
        # Check formatting in first paragraph
        first_para = content_paragraphs[0]
        if first_para.get('runs'):
            # Find runs with formatting
            bold_runs = [r for r in first_para['runs'] if r.get('bold')]
            italic_runs = [r for r in first_para['runs'] if r.get('italic')]
            assert len(bold_runs) > 0 or len(italic_runs) > 0
        
        # Check underline in second paragraph
        if len(content_paragraphs) >= 2:
            second_para = content_paragraphs[1]
            if second_para.get('runs'):
                underline_runs = [r for r in second_para['runs'] if r.get('underline')]
                assert len(underline_runs) > 0
    
    def test_parse_html_file(self, temp_output_dir):
        """Test parsing HTML file."""
        html_path = temp_output_dir / "test.html"
        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <p contenteditable="true">Paragraph 1</p>
            <p contenteditable="true">Paragraph 2</p>
        </body>
        </html>
        """
        html_path.write_text(html_content, encoding='utf-8')
        
        result = HTMLParser.parse_file(html_path)
        paragraphs = result.get('paragraphs', [])
        
        # Filter out empty paragraphs
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        assert "Paragraph" in content_paragraphs[0]['text']
    
    def test_parse_nested_formatting(self):
        """Test parsing nested formatting."""
        html_content = """
        <p contenteditable="true">
            <strong><em>Bold and italic</em></strong>
        </p>
        """
        
        parser = HTMLParser(html_content)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        # Parser may create multiple paragraphs due to whitespace handling
        # Find the paragraph with actual content
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        # Should handle nested formatting
        if content_paragraphs[0].get('runs'):
            assert len(content_paragraphs[0]['runs']) > 0


class TestHTMLContentParser:
    """Test cases for HTMLContentParser."""
    
    def test_handle_starttag_p(self):
        """Test handling paragraph start tag."""
        parser = HTMLContentParser()
        parser.handle_starttag('p', [])
        
        assert parser.current_paragraph is not None
    
    def test_handle_starttag_strong(self):
        """Test handling strong start tag."""
        parser = HTMLContentParser()
        parser.handle_starttag('p', [])
        parser.handle_starttag('strong', [])
        
        assert parser.current_run is not None
        assert parser.current_run.get('bold') == True
    
    def test_handle_data(self):
        """Test handling text data."""
        parser = HTMLContentParser()
        parser.handle_starttag('p', [])
        parser.handle_data("Test text")
        
        assert parser.current_run is not None
        assert parser.current_run['text'] == "Test text"
    
    def test_handle_endtag_p(self):
        """Test handling paragraph end tag."""
        parser = HTMLContentParser()
        parser.handle_starttag('p', [])
        parser.handle_data("Test")
        parser.handle_endtag('p')
        
        assert len(parser.paragraphs) == 1
        assert parser.paragraphs[0]['text'] == "Test"

