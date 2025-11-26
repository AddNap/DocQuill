"""
Tests for HTMLRenderer.

Tests for the HTMLRenderer with editable support.
"""

import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path

from docx_interpreter.renderers import HTMLRenderer


class TestHTMLRendererNew:
    """Test cases for HTMLRenderer API."""
    
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
        assert "<html" in html_content
    
    def test_render_editable(self, mock_document):
        """Test rendering editable HTML."""
        renderer = HTMLRenderer(mock_document, editable=True)
        html_content = renderer.render()
        
        assert "contenteditable" in html_content
    
    def test_render_with_paragraphs(self, mock_document):
        """Test rendering with paragraphs."""
        para1 = Mock()
        para1.get_text = Mock(return_value="Paragraph 1")
        para1.runs = []
        para1.text = "Paragraph 1"
        para1.numbering = None
        para1.children = []
    
        para2 = Mock()
        para2.get_text = Mock(return_value="Paragraph 2")
        para2.runs = []
        para2.text = "Paragraph 2"
        para2.numbering = None
        para2.children = []
    
        mock_document.get_paragraphs = Mock(return_value=[para1, para2])
        mock_document.get_text = Mock(return_value="")
        mock_document.placeholder_values = {}
    
        renderer = HTMLRenderer(mock_document, editable=False)
        html_content = renderer.render()
        
        assert html_content is not None
        assert isinstance(html_content, str)
    
    def test_render_with_formatting(self, mock_document):
        """Test rendering with formatting."""
        run = Mock()
        run.text = "Bold text"
        run.bold = True
        run.italic = False
        run.underline = False
        run.color = None
        run.font_size = None
        run.font_name = None
        run.children = []
        run.image = None
        run.textbox = None
        run.footnote_refs = []
        run.endnote_refs = []
        
        para = Mock()
        para.get_text = Mock(return_value="Bold text")
        para.runs = [run]
        para.text = "Bold text"
        para.numbering = None
        para.children = []
        para.alignment = None
        para.borders = None
        para.background = None
        para.shadow = None
        para.spacing_before = None
        para.spacing_after = None
        para.left_indent = None
        para.right_indent = None
        
        mock_document.get_paragraphs = Mock(return_value=[para])
        mock_document.placeholder_values = {}
        
        renderer = HTMLRenderer(mock_document, editable=True)
        html_content = renderer.render()
        
        assert html_content is not None
        assert isinstance(html_content, str)
    
    def test_save_to_file(self, mock_document, temp_dir):
        """Test saving HTML to file."""
        renderer = HTMLRenderer(mock_document)
        html_content = renderer.render()
        
        output_path = temp_dir / "output.html"
        result = renderer.save_to_file(html_content, output_path)
        
        assert result == True
        assert output_path.exists()
        assert output_path.stat().st_size > 0
