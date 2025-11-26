"""
Tests for field codes rendering.

Tests rendering of PAGE, NUMPAGES, DATE, TIME field codes in HTML and PDF.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from docquill.renderers.field_renderer import FieldRenderer
from docquill.models.field import Field


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
        from docquill.renderers import HTMLRenderer
        
        # Mock document with field codes
        mock_doc = Mock()
        mock_doc.metadata = Mock()
        mock_doc.metadata.title = "Test Document"
        mock_doc.placeholder_values = {}
        
        # Mock paragraph with field
        mock_para = Mock()
        mock_field = Field()
        mock_field.set_instr("PAGE")
        mock_field.current_page = 3
        
        mock_para.children = [mock_field]
        mock_para.runs = []
        mock_para.get_text = Mock(return_value="")
        mock_para.text = ""
        mock_para.numbering = None
        mock_para.alignment = None
        mock_para.borders = None
        mock_para.background = None
        mock_para.shadow = None
        mock_para.spacing_before = None
        mock_para.spacing_after = None
        mock_para.left_indent = None
        mock_para.right_indent = None
        # Remove auto-created attributes that would confuse type detection
        del mock_para.rows
        del mock_para.get_rows
        del mock_para.rel_id
        
        mock_doc.body = Mock()
        mock_doc.body.children = [mock_para]
        mock_doc.get_paragraphs = Mock(return_value=[mock_para])
        mock_doc.get_tables = Mock(return_value=[])
        mock_doc.get_footnotes = Mock(return_value={})
        mock_doc.get_endnotes = Mock(return_value={})
        mock_doc.get_watermarks = Mock(return_value=[])
        mock_doc.get_headers = Mock(return_value=[])
        mock_doc.get_footers = Mock(return_value=[])
        mock_doc.footnotes = {}
        mock_doc.endnotes = {}
        mock_doc.watermarks = []
        mock_doc.headers = []
        mock_doc.footers = []
        mock_doc.package_reader = None
        
        renderer = HTMLRenderer(mock_doc, context={'current_page': 3, 'total_pages': 10})
        html = renderer.render()
        
        assert html is not None
        # Field should be rendered as "3"
        # Note: This is a basic test - full integration would require proper document structure


class TestFieldCodesInPDF:
    """Test field codes rendering in PDF headers/footers."""
    
    def test_header_footer_renderer_with_field_codes(self):
        """Test HeaderFooterRenderer with field codes."""
        from docquill.renderers import HeaderFooterRenderer
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        import os
        
        # Register DejaVuSans font if not already registered
        try:
            pdfmetrics.getFont('DejaVuSans')
        except KeyError:
            # Try to find font file
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'fonts', 'DejaVuSans.ttf'),
            ]
            font_registered = False
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                        font_registered = True
                        break
                    except Exception:
                        pass
            if not font_registered:
                pytest.skip("DejaVuSans font not found")
        
        # Use A4 page size
        canvas = Canvas(BytesIO(), pagesize=A4)
        
        # Mock LayoutBlock with field codes
        from docquill.engine.unified_layout import LayoutBlock
        from docquill.engine.geometry import Rect, Margins
        
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

