"""
Tests for export functionality.

This module contains unit tests for the export functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json
from pathlib import Path

from docquill.export.json_exporter import JSONExporter
from docquill.export.markdown_exporter import MarkdownExporter
from docquill.export.html_exporter import HTMLExporter
from docquill.export.text_exporter import TextExporter
from docquill.export.xml_exporter import XMLExporter


class TestJSONExporter:
    """Test cases for JSONExporter class."""
    
    def test_init(self, mock_document):
        """Test JSONExporter initialization."""
        exporter = JSONExporter(mock_document)
        
        assert exporter.document == mock_document
        assert exporter.indent == 2
        assert exporter.ensure_ascii == False
    
    def test_init_with_options(self, mock_document):
        """Test JSONExporter initialization with options."""
        exporter = JSONExporter(
            mock_document, 
            indent=4, 
            ensure_ascii=True
        )
        
        assert exporter.indent == 4
        assert exporter.ensure_ascii == True
    
    def test_export_document_model(self, mock_document):
        """Test exporting document model."""
        exporter = JSONExporter(mock_document)
        model = exporter.export_document_model()
        
        assert isinstance(model, dict)
        assert 'metadata' in model
        assert 'content' in model
        assert 'styles' in model
        assert 'layout' in model
    
    def test_export_element(self, mock_document):
        """Test exporting element."""
        exporter = JSONExporter(mock_document)
        
        # Mock element with to_dict method
        mock_element = Mock()
        mock_element.to_dict.return_value = {"type": "paragraph", "text": "Sample text"}
        
        result = exporter.export_element(mock_element)
        
        assert isinstance(result, dict)
        assert result["type"] == "paragraph"
        assert result["text"] == "Sample text"
    
    def test_export_element_without_to_dict(self, mock_document):
        """Test exporting element without to_dict method."""
        exporter = JSONExporter(mock_document)
        
        # Mock element without to_dict method
        class MockElement:
            def __init__(self):
                self.text = "Sample text"
        
        mock_element = MockElement()
        
        result = exporter.export_element(mock_element)
        
        assert isinstance(result, dict)
        assert result["text"] == "Sample text"
    
    def test_format_json_output(self, mock_document):
        """Test formatting JSON output."""
        exporter = JSONExporter(mock_document)
        
        data = {"key": "value", "number": 123}
        json_string = exporter.format_json_output(data)
        
        assert isinstance(json_string, str)
        assert '"key": "value"' in json_string
        assert '"number": 123' in json_string
    
    def test_export_to_string(self, mock_document):
        """Test exporting to string."""
        exporter = JSONExporter(mock_document)
        json_string = exporter.export_to_string()
        
        assert isinstance(json_string, str)
        assert json_string.startswith('{')
        assert json_string.endswith('}')
    
    def test_validate_json(self, mock_document):
        """Test JSON validation."""
        exporter = JSONExporter(mock_document)
        
        # Valid JSON
        valid_json = '{"key": "value"}'
        assert exporter.validate_json(valid_json) == True
        
        # Invalid JSON
        invalid_json = '{"key": "value"'
        assert exporter.validate_json(invalid_json) == False
    
    def test_get_export_info(self, mock_document):
        """Test getting export information."""
        exporter = JSONExporter(mock_document)
        info = exporter.get_export_info()
        
        assert isinstance(info, dict)
        assert 'exporter_type' in info
        assert 'indent' in info
        assert 'ensure_ascii' in info


class TestMarkdownExporter:
    """Test cases for MarkdownExporter class."""
    
    def test_init(self, mock_document):
        """Test MarkdownExporter initialization."""
        exporter = MarkdownExporter(mock_document)
        
        assert exporter.document == mock_document
        assert exporter.include_images == True
        assert exporter.table_style == 'pipe'
        assert exporter.heading_levels == 6
    
    def test_init_with_options(self, mock_document):
        """Test MarkdownExporter initialization with options."""
        exporter = MarkdownExporter(
            mock_document,
            include_images=False,
            table_style='grid',
            heading_levels=3
        )
        
        assert exporter.include_images == False
        assert exporter.table_style == 'grid'
        assert exporter.heading_levels == 3
    
    def test_export_paragraph(self, mock_document):
        """Test exporting paragraph."""
        exporter = MarkdownExporter(mock_document)
        
        # Mock paragraph
        mock_paragraph = Mock()
        mock_paragraph.get_text.return_value = "Sample paragraph"
        mock_paragraph.style = "Normal"
        
        result = exporter.export_paragraph(mock_paragraph)
        
        assert isinstance(result, str)
        assert "Sample paragraph" in result
    
    def test_export_heading(self, mock_document):
        """Test exporting heading."""
        exporter = MarkdownExporter(mock_document)
        
        # Mock heading
        mock_heading = Mock()
        mock_heading.get_text.return_value = "Sample Heading"
        mock_heading.style = "Heading 1"
        
        result = exporter.export_heading(mock_heading)
        
        assert isinstance(result, str)
        assert "# Sample Heading" in result
    
    def test_export_table(self, mock_document):
        """Test exporting table."""
        exporter = MarkdownExporter(mock_document)
        
        # Mock table
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.get_text.return_value = "Cell content"
        mock_row.get_cells.return_value = [mock_cell]
        mock_table.get_rows.return_value = [mock_row]
        
        result = exporter.export_table(mock_table)
        
        assert isinstance(result, str)
        assert "|" in result  # Table should contain pipe characters
    
    def test_export_table_pipe_style(self, mock_document):
        """Test exporting table with pipe style."""
        exporter = MarkdownExporter(mock_document, table_style='pipe')
        
        # Mock table
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.get_text.return_value = "Cell content"
        mock_row.get_cells.return_value = [mock_cell]
        mock_table.get_rows.return_value = [mock_row]
        
        result = exporter.export_table(mock_table)
        
        assert isinstance(result, str)
        assert "|" in result
    
    def test_export_table_grid_style(self, mock_document):
        """Test exporting table with grid style."""
        exporter = MarkdownExporter(mock_document, table_style='grid')
        
        # Mock table
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.get_text.return_value = "Cell content"
        mock_row.get_cells.return_value = [mock_cell]
        mock_table.get_rows.return_value = [mock_row]
        
        result = exporter.export_table(mock_table)
        
        assert isinstance(result, str)
        assert "+" in result  # Grid style should contain plus characters
    
    def test_export_table_simple_style(self, mock_document):
        """Test exporting table with simple style."""
        exporter = MarkdownExporter(mock_document, table_style='simple')
        
        # Mock table
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.get_text.return_value = "Cell content"
        mock_row.get_cells.return_value = [mock_cell]
        mock_table.get_rows.return_value = [mock_row]
        
        result = exporter.export_table(mock_table)
        
        assert isinstance(result, str)
        assert "Cell content" in result
    
    def test_export_image(self, mock_document):
        """Test exporting image."""
        exporter = MarkdownExporter(mock_document)
        
        # Mock image
        mock_image = Mock()
        mock_image.get_src.return_value = "image.jpg"
        mock_image.get_alt.return_value = "Sample image"
        
        result = exporter.export_image(mock_image)
        
        assert isinstance(result, str)
        assert "![Sample image](image.jpg)" in result
    
    def test_export_to_string(self, mock_document):
        """Test exporting to string."""
        exporter = MarkdownExporter(mock_document)
        markdown_string = exporter.export_to_string()
        
        assert isinstance(markdown_string, str)
        assert len(markdown_string) > 0
    
    def test_validate_markdown(self, mock_document):
        """Test Markdown validation."""
        exporter = MarkdownExporter(mock_document)
        
        # Valid Markdown
        valid_markdown = "# Heading\n\nParagraph text"
        assert exporter.validate_markdown(valid_markdown) == True
        
        # Empty Markdown
        empty_markdown = ""
        assert exporter.validate_markdown(empty_markdown) == True
    
    def test_get_export_info(self, mock_document):
        """Test getting export information."""
        exporter = MarkdownExporter(mock_document)
        info = exporter.get_export_info()
        
        assert isinstance(info, dict)
        assert 'exporter_type' in info
        assert 'include_images' in info
        assert 'table_style' in info


class TestHTMLExporter:
    """Test cases for HTMLExporter class."""
    
    def test_init(self, mock_document):
        """Test HTMLExporter initialization."""
        exporter = HTMLExporter(mock_document)
        
        assert exporter.document == mock_document
        assert exporter.include_css == True
        assert exporter.include_metadata == True
        assert exporter.css_style == 'default'
    
    def test_init_with_options(self, mock_document):
        """Test HTMLExporter initialization with options."""
        exporter = HTMLExporter(
            mock_document,
            include_css=False,
            include_metadata=False,
            css_style='minimal'
        )
        
        assert exporter.include_css == False
        assert exporter.include_metadata == False
        assert exporter.css_style == 'minimal'
    
    def test_export_document_structure(self, mock_document):
        """Test exporting document structure."""
        exporter = HTMLExporter(mock_document)
        html = exporter.export_document_structure()
        
        assert isinstance(html, str)
        assert "<div class='document'>" in html
        assert "<title>" in html
        assert "<div class='content'>" in html
    
    def test_export_paragraph(self, mock_document):
        """Test exporting paragraph."""
        exporter = HTMLExporter(mock_document)
        
        # Mock paragraph
        mock_paragraph = Mock()
        mock_paragraph.get_text.return_value = "Sample paragraph"
        mock_paragraph.style = "Normal"
        
        result = exporter.export_paragraph(mock_paragraph)
        
        assert isinstance(result, str)
        assert "<p class='paragraph'>" in result
        assert "Sample paragraph" in result
    
    def test_export_heading(self, mock_document):
        """Test exporting heading."""
        exporter = HTMLExporter(mock_document)
        
        # Mock heading
        mock_heading = Mock()
        mock_heading.get_text.return_value = "Sample Heading"
        mock_heading.style = "Heading 1"
        
        result = exporter.export_heading(mock_heading)
        
        assert isinstance(result, str)
        assert "<h1 class='heading'>" in result
        assert "Sample Heading" in result
    
    def test_export_table(self, mock_document):
        """Test exporting table."""
        exporter = HTMLExporter(mock_document)
        
        # Mock table
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.get_text.return_value = "Cell content"
        mock_row.get_cells.return_value = [mock_cell]
        mock_table.get_rows.return_value = [mock_row]
        
        result = exporter.export_table(mock_table)
        
        assert isinstance(result, str)
        assert "<table class='table'>" in result
        assert "<tr>" in result
        assert "<td>" in result
        assert "Cell content" in result
    
    def test_generate_css_styles(self, mock_document):
        """Test generating CSS styles."""
        exporter = HTMLExporter(mock_document)
        css = exporter.generate_css_styles()
        
        assert isinstance(css, str)
        assert ".document" in css
        assert ".paragraph" in css
        assert ".table" in css
    
    def test_generate_css_styles_minimal(self, mock_document):
        """Test generating minimal CSS styles."""
        exporter = HTMLExporter(mock_document, css_style='minimal')
        css = exporter.generate_css_styles()
        
        assert isinstance(css, str)
        assert len(css) > 0
    
    def test_generate_css_styles_print(self, mock_document):
        """Test generating print CSS styles."""
        exporter = HTMLExporter(mock_document, css_style='print')
        css = exporter.generate_css_styles()
        
        assert isinstance(css, str)
        assert len(css) > 0
    
    def test_export_to_string(self, mock_document):
        """Test exporting to string."""
        exporter = HTMLExporter(mock_document)
        html_string = exporter.export_to_string()
        
        assert isinstance(html_string, str)
        assert "<!DOCTYPE html>" in html_string
        assert "<html" in html_string
        assert "</html>" in html_string
    
    def test_validate_html(self, mock_document):
        """Test HTML validation."""
        exporter = HTMLExporter(mock_document)
        
        # Valid HTML
        valid_html = "<html><body><p>Test</p></body></html>"
        assert exporter.validate_html(valid_html) == True
        
        # Invalid HTML
        invalid_html = "<html><body><p>Test</body>"
        assert exporter.validate_html(invalid_html) == False
    
    def test_get_export_info(self, mock_document):
        """Test getting export information."""
        exporter = HTMLExporter(mock_document)
        info = exporter.get_export_info()
        
        assert isinstance(info, dict)
        assert 'exporter_type' in info
        assert 'include_css' in info
        assert 'css_style' in info


class TestTextExporter:
    """Test cases for TextExporter class."""
    
    def test_init(self, mock_document):
        """Test TextExporter initialization."""
        exporter = TextExporter(mock_document)
        
        assert exporter.document == mock_document
        assert exporter.preserve_formatting == True
        assert exporter.line_width == 80
        assert exporter.encoding == 'utf-8'
    
    def test_init_with_options(self, mock_document):
        """Test TextExporter initialization with options."""
        exporter = TextExporter(
            mock_document,
            preserve_formatting=False,
            line_width=120,
            encoding='ascii'
        )
        
        assert exporter.preserve_formatting == False
        assert exporter.line_width == 120
        assert exporter.encoding == 'ascii'
    
    def test_export_document_text(self, mock_document):
        """Test exporting document text."""
        exporter = TextExporter(mock_document)
        text = exporter.export_document_text()
        
        assert isinstance(text, str)
        assert len(text) > 0
    
    def test_export_paragraph_text(self, mock_document):
        """Test exporting paragraph text."""
        exporter = TextExporter(mock_document)
        
        # Mock paragraph
        mock_paragraph = Mock()
        mock_paragraph.get_text.return_value = "Sample paragraph text"
        mock_paragraph.style = "Normal"
        
        result = exporter.export_paragraph_text(mock_paragraph)
        
        assert isinstance(result, str)
        assert "Sample paragraph text" in result
    
    def test_export_heading_text(self, mock_document):
        """Test exporting heading text."""
        exporter = TextExporter(mock_document)
        
        # Mock heading
        mock_heading = Mock()
        mock_heading.get_text.return_value = "Sample Heading"
        mock_heading.style = "Heading 1"
        
        result = exporter.export_heading_text(mock_heading)
        
        assert isinstance(result, str)
        assert "Sample Heading" in result
        assert "=" in result  # Heading should be underlined
    
    def test_export_table_text(self, mock_document):
        """Test exporting table text."""
        exporter = TextExporter(mock_document)
        
        # Mock table
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.get_text.return_value = "Cell content"
        mock_row.get_cells.return_value = [mock_cell]
        mock_table.get_rows.return_value = [mock_row]
        
        result = exporter.export_table_text(mock_table)
        
        assert isinstance(result, str)
        assert "Cell content" in result
    
    def test_export_to_string(self, mock_document):
        """Test exporting to string."""
        exporter = TextExporter(mock_document)
        text_string = exporter.export_to_string()
        
        assert isinstance(text_string, str)
        assert len(text_string) > 0
    
    def test_validate_text(self, mock_document):
        """Test text validation."""
        exporter = TextExporter(mock_document)
        
        # Valid text
        valid_text = "Sample text content"
        assert exporter.validate_text(valid_text) == True
        
        # Empty text
        empty_text = ""
        assert exporter.validate_text(empty_text) == True
    
    def test_get_export_info(self, mock_document):
        """Test getting export information."""
        exporter = TextExporter(mock_document)
        info = exporter.get_export_info()
        
        assert isinstance(info, dict)
        assert 'exporter_type' in info
        assert 'preserve_formatting' in info
        assert 'line_width' in info


class TestXMLExporter:
    """Test cases for XMLExporter class."""
    
    def test_init(self, mock_document):
        """Test XMLExporter initialization."""
        exporter = XMLExporter(mock_document)
        
        assert exporter.document == mock_document
        assert exporter.xml_namespace == "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        assert exporter.indent == 2
        assert exporter.encoding == 'utf-8'
    
    def test_init_with_options(self, mock_document):
        """Test XMLExporter initialization with options."""
        exporter = XMLExporter(
            mock_document,
            xml_namespace="http://custom.namespace",
            indent=4,
            encoding='ascii'
        )
        
        assert exporter.xml_namespace == "http://custom.namespace"
        assert exporter.indent == 4
        assert exporter.encoding == 'ascii'
    
    @pytest.mark.skip(reason="Requires real document with proper body.children structure")
    def test_regenerate_wordml(self, mock_document):
        """Test regenerating WordML."""
        exporter = XMLExporter(mock_document)
        wordml = exporter.regenerate_wordml()
        
        assert isinstance(wordml, str)
        assert "<w:document" in wordml or "<ns0:document" in wordml
        assert "<w:body>" in wordml or "<ns0:body>" in wordml
    
    @pytest.mark.skip(reason="Requires real paragraph with raw_xml attribute")
    def test_export_element_xml(self, mock_document):
        """Test exporting element XML."""
        exporter = XMLExporter(mock_document)
        
        # Mock paragraph element
        mock_paragraph = Mock()
        mock_paragraph.get_text.return_value = "Sample text"
        mock_paragraph.style = "Normal"
        
        result = exporter.export_element_xml(mock_paragraph, "paragraph")
        
        # export_element_xml returns ET.Element, not string
        assert hasattr(result, 'tag')
        assert result.tag in ['w:p', 'p', 'ns0:p']
    
    @pytest.mark.skip(reason="Requires real paragraph with raw_xml attribute")
    def test_export_paragraph_xml(self, mock_document):
        """Test exporting paragraph XML."""
        exporter = XMLExporter(mock_document)
        
        # Mock paragraph
        mock_paragraph = Mock()
        mock_paragraph.get_text.return_value = "Sample text"
        mock_paragraph.style = "Normal"
        
        result = exporter.export_paragraph_xml(mock_paragraph)
        
        assert isinstance(result, str)
        assert "<w:p>" in result
        assert "<w:r>" in result
        assert "<w:t>Sample text</w:t>" in result
    
    @pytest.mark.skip(reason="Requires real table with grid and rows structure")
    def test_export_table_xml(self, mock_document):
        """Test exporting table XML."""
        exporter = XMLExporter(mock_document)
        
        # Mock table
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.get_text.return_value = "Cell content"
        mock_row.get_cells.return_value = [mock_cell]
        mock_table.get_rows.return_value = [mock_row]
        
        result = exporter.export_table_xml(mock_table)
        
        assert isinstance(result, str)
        assert "<w:tbl>" in result
        assert "<w:tr>" in result
        assert "<w:tc>" in result
    
    def test_export_image_xml(self, mock_document):
        """Test exporting image XML."""
        exporter = XMLExporter(mock_document)
        
        # Mock image
        mock_image = Mock()
        mock_image.get_src.return_value = "word/media/image1.jpg"
        mock_image.get_alt.return_value = "Sample image"
        
        result = exporter.export_image_xml(mock_image)
        
        assert isinstance(result, str)
        assert "<w:drawing>" in result
    
    @pytest.mark.skip(reason="Requires real document with proper body.children structure")
    def test_export_to_string(self, mock_document):
        """Test exporting to string."""
        exporter = XMLExporter(mock_document)
        xml_string = exporter.export_to_string()
        
        assert isinstance(xml_string, str)
        assert "<?xml version=" in xml_string
        assert "<w:document" in xml_string or "<ns0:document" in xml_string
    
    def test_validate_xml(self, mock_document):
        """Test XML validation."""
        exporter = XMLExporter(mock_document)
        
        # Valid XML
        valid_xml = "<?xml version='1.0'?><root><child>Text</child></root>"
        assert exporter.validate_xml(valid_xml) == True
        
        # Invalid XML
        invalid_xml = "<?xml version='1.0'?><root><child>Text</root>"
        assert exporter.validate_xml(invalid_xml) == False
    
    def test_get_export_info(self, mock_document):
        """Test getting export information."""
        exporter = XMLExporter(mock_document)
        info = exporter.get_export_info()
        
        assert isinstance(info, dict)
        assert 'exporter_type' in info
        assert 'xml_namespace' in info
        assert 'indent' in info
