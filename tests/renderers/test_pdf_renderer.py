"""
Tests for PDFRenderer class.

This module contains unit tests for the PDFRenderer functionality.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from docx_interpreter.renderers.pdf_renderer import PDFRenderer


class TestPDFRenderer:
    """Test cases for PDFRenderer class."""
    
    def test_init_with_document(self, mock_document):
        """Test PDFRenderer initialization with document."""
        renderer = PDFRenderer(mock_document)
        
        assert renderer.document == mock_document
        assert renderer.page_size == 'A4'
        assert renderer.font_family == 'Helvetica'
        assert renderer.font_size == 12
        assert renderer.include_images == True
    
    def test_init_with_options(self, mock_document):
        """Test PDFRenderer initialization with custom options."""
        options = {
            'page_size': 'Letter',
            'font_family': 'Times-Roman',
            'font_size': 14,
            'include_images': False,
            'image_quality': 80
        }
        
        renderer = PDFRenderer(mock_document, render_options=options)
        
        assert renderer.page_size == 'Letter'
        assert renderer.font_family == 'Times-Roman'
        assert renderer.font_size == 14
        assert renderer.include_images == False
        assert renderer.image_quality == 80
    
    def test_render_basic_document(self, mock_document):
        """Test rendering basic document."""
        renderer = PDFRenderer(mock_document)
        pdf_content = renderer.render()
        
        assert pdf_content is not None
        assert isinstance(pdf_content, bytes)
        assert len(pdf_content) > 0
        assert b"%PDF-1.4" in pdf_content
    
    def test_render_header(self, mock_document):
        """Test rendering header."""
        renderer = PDFRenderer(mock_document)
        
        # Mock header
        mock_header = Mock()
        mock_header.get_text.return_value = "Header Text"
        
        header_content = renderer.render_header(mock_header)
        
        assert header_content is not None
        assert "Header: Header Text" in header_content
    
    def test_render_footer(self, mock_document):
        """Test rendering footer."""
        renderer = PDFRenderer(mock_document)
        
        # Mock footer
        mock_footer = Mock()
        mock_footer.get_text.return_value = "Footer Text"
        
        footer_content = renderer.render_footer(mock_footer)
        
        assert footer_content is not None
        assert "Footer: Footer Text" in footer_content
    
    def test_render_body(self, mock_document):
        """Test rendering body."""
        renderer = PDFRenderer(mock_document)
        
        # Mock body with paragraphs
        mock_body = Mock()
        mock_paragraph = Mock()
        mock_paragraph.get_text.return_value = "Paragraph text"
        mock_body.get_paragraphs.return_value = [mock_paragraph]
        mock_body.get_tables.return_value = []
        mock_body.get_images.return_value = []
        
        body_content = renderer.render_body(mock_body)
        
        assert body_content is not None
        assert "Paragraph text" in body_content
    
    def test_render_paragraph(self, mock_document):
        """Test rendering paragraph."""
        renderer = PDFRenderer(mock_document)
        
        # Mock paragraph
        mock_paragraph = Mock()
        mock_paragraph.get_text.return_value = "Sample paragraph text"
        mock_paragraph.style = "Normal"
        
        paragraph_content = renderer.render_paragraph(mock_paragraph)
        
        assert paragraph_content is not None
        assert "Sample paragraph text" in paragraph_content
        assert paragraph_content.endswith("\n\n")
    
    def test_render_table(self, mock_document):
        """Test rendering table."""
        renderer = PDFRenderer(mock_document)
        
        # Mock table
        mock_table = Mock()
        mock_row = Mock()
        mock_cell = Mock()
        mock_cell.get_text.return_value = "Cell content"
        mock_row.get_cells.return_value = [mock_cell]
        mock_table.get_rows.return_value = [mock_row]
        
        table_content = renderer.render_table(mock_table)
        
        assert table_content is not None
        assert "Table Header:" in table_content
        assert "Cell content" in table_content
    
    def test_render_image(self, mock_document):
        """Test rendering image."""
        renderer = PDFRenderer(mock_document)
        
        # Mock image
        mock_image = Mock()
        mock_image.get_src.return_value = "image.jpg"
        mock_image.get_alt.return_value = "Sample image"
        mock_image.get_width.return_value = "300"
        mock_image.get_height.return_value = "200"
        
        image_content = renderer.render_image(mock_image)
        
        assert image_content is not None
        assert "[Image: Sample image" in image_content
        assert "(src: image.jpg)" in image_content
        assert "(width: 300)" in image_content
        assert "(height: 200)" in image_content
    
    def test_initialize_page_dimensions(self, mock_document):
        """Test page dimensions initialization."""
        renderer = PDFRenderer(mock_document)
        
        # Test A4 dimensions
        assert renderer.page_width == 595
        assert renderer.page_height == 842
        
        # Test different page size
        renderer.set_page_size('Letter')
        assert renderer.page_width == 612
        assert renderer.page_height == 792
    
    def test_generate_pdf_start(self, mock_document):
        """Test PDF document start generation."""
        renderer = PDFRenderer(mock_document)
        pdf_start = renderer._generate_pdf_start()
        
        assert pdf_start is not None
        assert "%PDF-1.4" in pdf_start
        assert "/Type /Catalog" in pdf_start
        assert "/Pages" in pdf_start
    
    def test_generate_pdf_end(self, mock_document):
        """Test PDF document end generation."""
        renderer = PDFRenderer(mock_document)
        pdf_end = renderer._generate_pdf_end()
        
        assert pdf_end is not None
        assert "%%EOF" in pdf_end
        assert "xref" in pdf_end
        assert "trailer" in pdf_end
    
    def test_apply_text_formatting(self, mock_document):
        """Test text formatting application."""
        renderer = PDFRenderer(mock_document)
        
        # Test bold formatting
        mock_element = Mock()
        mock_element.style = "bold"
        
        formatted_text = renderer._apply_text_formatting("Bold text", mock_element)
        assert "**Bold text**" in formatted_text
        
        # Test italic formatting
        mock_element.style = "italic"
        formatted_text = renderer._apply_text_formatting("Italic text", mock_element)
        assert "*Italic text*" in formatted_text
    
    def test_save_to_file(self, mock_document, temp_dir):
        """Test saving PDF to file."""
        renderer = PDFRenderer(mock_document)
        pdf_content = renderer.render()
        
        output_path = temp_dir / "test.pdf"
        success = renderer.save_to_file(pdf_content, str(output_path))
        
        assert success
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        # Verify content
        with open(output_path, 'rb') as f:
            saved_content = f.read()
        assert saved_content == pdf_content
    
    def test_get_supported_formats(self, mock_document):
        """Test getting supported formats."""
        renderer = PDFRenderer(mock_document)
        formats = renderer.get_supported_formats()
        
        assert isinstance(formats, list)
        assert 'pdf' in formats
        assert len(formats) == 1
    
    def test_set_page_size(self, mock_document):
        """Test setting page size."""
        renderer = PDFRenderer(mock_document)
        renderer.set_page_size('A3')
        
        assert renderer.page_size == 'A3'
        assert renderer.get_render_option('page_size') == 'A3'
        assert renderer.page_width == 842
        assert renderer.page_height == 1191
    
    def test_set_margins(self, mock_document):
        """Test setting page margins."""
        renderer = PDFRenderer(mock_document)
        new_margins = {'top': 100, 'bottom': 100, 'left': 100, 'right': 100}
        renderer.set_margins(new_margins)
        
        assert renderer.margins == new_margins
        assert renderer.get_render_option('margins') == new_margins
    
    def test_set_font(self, mock_document):
        """Test setting font family and size."""
        renderer = PDFRenderer(mock_document)
        renderer.set_font('Courier', 16)
        
        assert renderer.font_family == 'Courier'
        assert renderer.font_size == 16
        assert renderer.get_render_option('font_family') == 'Courier'
        assert renderer.get_render_option('font_size') == 16
    
    def test_set_line_height(self, mock_document):
        """Test setting line height."""
        renderer = PDFRenderer(mock_document)
        renderer.set_line_height(1.5)
        
        assert renderer.line_height == 1.5
        assert renderer.get_render_option('line_height') == 1.5
    
    def test_set_image_quality(self, mock_document):
        """Test setting image quality."""
        renderer = PDFRenderer(mock_document)
        renderer.set_image_quality(90)
        
        assert renderer.image_quality == 90
        assert renderer.get_render_option('image_quality') == 90
    
    def test_set_image_quality_bounds(self, mock_document):
        """Test image quality bounds."""
        renderer = PDFRenderer(mock_document)
        
        # Test lower bound
        renderer.set_image_quality(0)
        assert renderer.image_quality == 1
        
        # Test upper bound
        renderer.set_image_quality(150)
        assert renderer.image_quality == 100
    
    def test_set_table_style(self, mock_document):
        """Test setting table style."""
        renderer = PDFRenderer(mock_document)
        renderer.set_table_style('grid')
        
        assert renderer.table_style == 'grid'
        assert renderer.get_render_option('table_style') == 'grid'
    
    def test_renderer_info(self, mock_document):
        """Test getting renderer information."""
        renderer = PDFRenderer(mock_document)
        info = renderer.get_renderer_info()
        
        assert isinstance(info, dict)
        assert 'renderer_type' in info
        assert 'document_type' in info
        assert 'render_options' in info
        assert info['renderer_type'] == 'PDFRenderer'
    
    def test_validation(self, mock_document):
        """Test renderer validation."""
        renderer = PDFRenderer(mock_document)
        
        # Test valid options
        valid_options = ['page_size', 'font_family']
        assert renderer.validate_render_options(valid_options) == True
        
        # Test invalid options
        invalid_options = ['nonexistent_option']
        assert renderer.validate_render_options(invalid_options) == False
    
    def test_error_handling(self):
        """Test error handling in PDFRenderer."""
        # Test with None document
        with pytest.raises(ValueError):
            PDFRenderer(None)
        
        # Test with invalid output path
        mock_document = Mock()
        renderer = PDFRenderer(mock_document)
        
        with pytest.raises(ValueError):
            renderer.save_to_file("content", None)
    
    def test_render_empty_document(self):
        """Test rendering empty document."""
        mock_document = Mock()
        mock_document.get_header.return_value = None
        mock_document.get_footer.return_value = None
        mock_document.get_body.return_value = None
        
        renderer = PDFRenderer(mock_document)
        pdf_content = renderer.render()
        
        assert pdf_content is not None
        assert b"%PDF-1.4" in pdf_content
    
    def test_page_sizes(self, mock_document):
        """Test different page sizes."""
        renderer = PDFRenderer(mock_document)
        
        # Test A4
        renderer.set_page_size('A4')
        assert renderer.page_width == 595
        assert renderer.page_height == 842
        
        # Test A3
        renderer.set_page_size('A3')
        assert renderer.page_width == 842
        assert renderer.page_height == 1191
        
        # Test A5
        renderer.set_page_size('A5')
        assert renderer.page_width == 420
        assert renderer.page_height == 595
        
        # Test Letter
        renderer.set_page_size('Letter')
        assert renderer.page_width == 612
        assert renderer.page_height == 792
        
        # Test Legal
        renderer.set_page_size('Legal')
        assert renderer.page_width == 612
        assert renderer.page_height == 1008
        
        # Test invalid size (should default to A4)
        renderer.set_page_size('Invalid')
        assert renderer.page_width == 595
        assert renderer.page_height == 842
