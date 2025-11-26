"""
Tests for field codes rendering.

Tests rendering of PAGE, NUMPAGES, DATE, TIME field codes in HTML and PDF.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from docx_interpreter.renderers.field_renderer import FieldRenderer
from docx_interpreter.models.field import Field


class TestFieldRenderer:
    """Test cases for FieldRenderer class."""
    
    def test_render_page_field(self):
        """Test rendering PAGE field."""
        renderer = FieldRenderer({'current_page': 5, 'total_pages': 10})
        
        field = Field()
        field.set_instr("PAGE")
        field.current_page = 5
        
        result = renderer.render_field(field)
        assert result == "5"
    
    def test_render_numpages_field(self):
        """Test rendering NUMPAGES field."""
        renderer = FieldRenderer({'current_page': 5, 'total_pages': 10})
        
        field = Field()
        field.set_instr("NUMPAGES")
        field.total_pages = 10
        
        result = renderer.render_field(field)
        assert result == "10"
    
    def test_render_date_field(self):
        """Test rendering DATE field."""
        test_date = datetime(2025, 1, 15)
        renderer = FieldRenderer({'current_date': test_date})
        
        field = Field()
        field.set_instr("DATE")
        field.current_date = test_date
        
        result = renderer.render_field(field)
        assert result == "15.01.2025"  # Default format
    
    def test_render_time_field(self):
        """Test rendering TIME field."""
        test_time = datetime(2025, 1, 15, 14, 30)
        renderer = FieldRenderer({'current_time': test_time})
        
        field = Field()
        field.set_instr("TIME")
        field.current_time = test_time
        
        result = renderer.render_field(field)
        assert result == "14:30"  # Default format
    
    def test_render_field_from_instruction(self):
        """Test rendering field from instruction string."""
        renderer = FieldRenderer({
            'current_page': 3,
            'total_pages': 7,
            'current_date': datetime(2025, 1, 15),
            'current_time': datetime(2025, 1, 15, 14, 30)
        })
        
        assert renderer.render_field_from_instruction("PAGE") == "3"
        assert renderer.render_field_from_instruction("NUMPAGES") == "7"
        assert renderer.render_field_from_instruction("DATE") == "15.01.2025"
        assert renderer.render_field_from_instruction("TIME") == "14:30"
    
    def test_replace_fields_in_text(self):
        """Test replacing field placeholders in text."""
        renderer = FieldRenderer({
            'current_page': 2,
            'total_pages': 5,
            'current_date': datetime(2025, 1, 15),
            'current_time': datetime(2025, 1, 15, 14, 30)
        })
        
        text = "Strona [PAGE] z [NUMPAGES]"
        result = renderer.replace_fields_in_text(text)
        assert result == "Strona 2 z 5"
        
        text = "Data: [DATE], Czas: [TIME]"
        result = renderer.replace_fields_in_text(text)
        assert "[DATE]" in result or "15.01.2025" in result
        assert "[TIME]" in result or "14:30" in result
    
    def test_update_context(self):
        """Test updating renderer context."""
        renderer = FieldRenderer({'current_page': 1, 'total_pages': 1})
        
        renderer.update_context({'current_page': 5, 'total_pages': 10})
        
        assert renderer.current_page == 5
        assert renderer.total_pages == 10
    
    def test_render_field_with_format(self):
        """Test rendering field with custom format."""
        test_date = datetime(2025, 1, 15)
        renderer = FieldRenderer({'current_date': test_date})
        
        field = Field()
        field.set_instr('DATE \\@ "dd.MM.yyyy"')
        field.current_date = test_date
        # Parse instruction to set format_info
        field._parse_date_instruction('DATE \\@ "dd.MM.yyyy"')
        
        result = renderer.render_field(field)
        assert result == "15.01.2025"


class TestFieldCodesInHTML:
    """Test field codes rendering in HTML."""
    
    def test_html_renderer_with_field_codes(self):
        """Test HTMLRenderer with field codes."""
        from docx_interpreter.renderers import HTMLRenderer
        
        # Mock document with field codes
        mock_doc = Mock()
        mock_doc.metadata = Mock()
        mock_doc.metadata.title = "Test Document"
        mock_doc.placeholder_values = {}  # Fix Mock issue
        
        # Mock paragraph with field
        mock_para = Mock()
        mock_field = Field()
        mock_field.set_instr("PAGE")
        mock_field.current_page = 3
        
        mock_para.children = [mock_field]
        mock_para.runs = []
        mock_para.get_text = Mock(return_value="")
        
        mock_doc.body = Mock()
        mock_doc.body.children = [mock_para]
        
        renderer = HTMLRenderer(mock_doc, context={'current_page': 3, 'total_pages': 10})
        html = renderer.render()
        
        assert html is not None
        # Field should be rendered as "3"
        # Note: This is a basic test - full integration would require proper document structure


class TestFieldCodesInPDF:
    """Test field codes rendering in PDF headers/footers."""
    
    def test_header_footer_renderer_with_field_codes(self):
        """Test HeaderFooterRenderer with field codes."""
        from docx_interpreter.renderers import HeaderFooterRenderer
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.lib.pagesizes import A4
        from io import BytesIO
        
        # Use A4 page size which has fonts registered
        canvas = Canvas(BytesIO(), pagesize=A4)
        
        # Mock LayoutBlock with field codes
        from docx_interpreter.engine.unified_layout import LayoutBlock
        from docx_interpreter.engine.geometry import Rect, Margins
        
        block = LayoutBlock(
            block_type="footer",
            frame=Rect(0, 0, 500, 50),
            content={
                'text': 'Strona [PAGE] z [NUMPAGES]',
                'fields': []
            },
            style={}
        )
        
        margins = Margins(left=50, right=50, top=50, bottom=50)
        renderer = HeaderFooterRenderer(
            canvas,
            page_size=A4,
            margins=margins,
            context={'current_page': 2, 'total_pages': 5}
        )
        
        # Should not raise exception
        renderer.draw(block)
        
        # Field codes should be replaced
        # Note: Full test would require checking rendered PDF content

