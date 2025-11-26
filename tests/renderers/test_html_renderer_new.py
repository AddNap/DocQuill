"""
Tests for new HTMLRenderer (simplified API).

Tests for the updated HTMLRenderer with editable support.
"""

import pytest
from unittest.mock import Mock
from pathlib import Path

from docx_interpreter.renderers import HTMLRenderer


@pytest.fixture
def mock_document():
    """Create mock document."""
    doc = Mock()
    doc.metadata = Mock()
    doc.metadata.title = "Test Document"
    doc.get_paragraphs = Mock(return_value=[])
    doc.get_text = Mock(return_value="")
    doc.placeholder_values = {}
    return doc


class TestHTMLRendererNew:
    """Test cases for new HTMLRenderer API."""
    
    def test_init_basic(self, mock_document):
        """Test basic initialization."""
        renderer = HTMLRenderer(mock_document)
        
        assert renderer.document == mock_document
        assert renderer.editable == False
    
    def test_init_editable(self, mock_document):
        """Test initialization with editable option."""
        renderer = HTMLRenderer(mock_document, editable=True)
        
        assert renderer.editable == True
    
    def test_render_basic(self, mock_document):
        """Test basic rendering."""
        renderer = HTMLRenderer(mock_document)
        html_content = renderer.render()
        
        assert html_content is not None
        assert isinstance(html_content, str)
        assert "<!DOCTYPE html>" in html_content
        assert "<html" in html_content
        assert "<body>" in html_content
    
    def test_render_editable(self, mock_document):
        """Test rendering editable HTML."""
        renderer = HTMLRenderer(mock_document, editable=True)
        html_content = renderer.render()
        
        assert "contenteditable=\"true\"" in html_content
        assert "<style>" in html_content
        assert "<script>" in html_content
    
    def test_render_with_paragraphs(self, mock_document):
        """Test rendering with paragraphs."""
        para1 = Mock()
        para1.get_text = Mock(return_value="Paragraph 1")
        para1.runs = []
        
        para2 = Mock()
        para2.get_text = Mock(return_value="Paragraph 2")
        para2.runs = []
        
        mock_document.get_paragraphs = Mock(return_value=[para1, para2])
        
        renderer = HTMLRenderer(mock_document)
        html_content = renderer.render()
        
        assert "Paragraph 1" in html_content
        assert "Paragraph 2" in html_content
    
    def test_render_with_formatting(self, mock_document):
        """Test rendering with formatting."""
        run1 = Mock()
        run1.text = "Bold"
        run1.bold = True
        run1.is_bold = Mock(return_value=True)
        run1.is_italic = Mock(return_value=False)
        run1.is_underline = Mock(return_value=False)
        
        run2 = Mock()
        run2.text = " italic"
        run2.bold = False
        run2.is_bold = Mock(return_value=False)
        run2.is_italic = Mock(return_value=True)
        run2.is_underline = Mock(return_value=False)
        
        para = Mock()
        para.runs = [run1, run2]
        para.get_text = Mock(return_value="Bold italic")
        
        mock_document.get_paragraphs = Mock(return_value=[para])
        
        renderer = HTMLRenderer(mock_document, editable=True)
        html_content = renderer.render()
        
        assert "<strong>" in html_content or "<b>" in html_content
        assert "<em>" in html_content or "<i>" in html_content
    
    def test_save_to_file(self, mock_document, temp_dir):
        """Test saving to file."""
        renderer = HTMLRenderer(mock_document)
        html_content = renderer.render()
        
        output_path = Path(temp_dir) / "test.html"
        success = renderer.save_to_file(html_content, str(output_path))
        
        assert success
        assert output_path.exists()
        assert output_path.read_text(encoding='utf-8') == html_content

