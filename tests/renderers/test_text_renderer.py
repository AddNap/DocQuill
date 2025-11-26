"""
Tests for TextRenderer class.

This module contains unit tests for TextRenderer functionality
to increase test coverage from 7% to higher levels.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

from docx_interpreter.renderers.text_renderer import TextRenderer
from docx_interpreter.engine.unified_layout import LayoutBlock
from docx_interpreter.engine.geometry import Rect, Margins


class TestTextRenderer:
    """Test cases for TextRenderer class."""
    
    @pytest.fixture
    def mock_canvas(self):
        """Create a mock ReportLab canvas."""
        canvas = Mock(spec=Canvas)
        canvas._fontname = "DejaVuSans"
        canvas._fontsize = 12
        canvas.stringWidth = Mock(return_value=100.0)
        canvas.drawString = Mock()
        canvas.drawRightString = Mock()
        canvas.drawCentredString = Mock()
        canvas.setFont = Mock()
        canvas.setFillColor = Mock()
        canvas.setStrokeColor = Mock()
        canvas.saveState = Mock()
        canvas.restoreState = Mock()
        return canvas
    
    @pytest.fixture
    def text_renderer(self, mock_canvas):
        """Create TextRenderer instance."""
        return TextRenderer(mock_canvas, page_size=A4, margins=Margins(72, 72, 72, 72))
    
    @pytest.fixture
    def sample_block(self):
        """Create a sample LayoutBlock for testing."""
        block = Mock(spec=LayoutBlock)
        block.frame = Rect(100, 100, 400, 200)
        block.style = {}
        block.content = {"lines": [{"text": "Test line", "offset_baseline": 0.0}]}
        return block
    
    def test_init(self, mock_canvas):
        """Test TextRenderer initialization."""
        renderer = TextRenderer(mock_canvas, page_size=A4)
        
        assert renderer.canvas == mock_canvas
        assert renderer.page_size == A4
        assert renderer.margins is None
    
    def test_init_with_margins(self, mock_canvas):
        """Test TextRenderer initialization with margins."""
        margins = Margins(50, 50, 50, 50)
        renderer = TextRenderer(mock_canvas, margins=margins)
        
        assert renderer.margins == margins
    
    def test_init_with_footnote_renderer(self, mock_canvas):
        """Test TextRenderer initialization with footnote renderer."""
        footnote_renderer = Mock()
        renderer = TextRenderer(mock_canvas, footnote_renderer=footnote_renderer)
        
        assert renderer.footnote_renderer == footnote_renderer
    
    def test_draw_with_simple_text(self, text_renderer, sample_block):
        """Test drawing simple text block."""
        sample_block.content = {"text": "Simple text"}
        
        text_renderer.draw(sample_block)
        
        # Verify canvas methods were called
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_lines(self, text_renderer, sample_block):
        """Test drawing block with lines."""
        sample_block.content = {
            "lines": [
                {"text": "Line 1", "offset_baseline": 0.0},
                {"text": "Line 2", "offset_baseline": 20.0}
            ]
        }
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_alignment_left(self, text_renderer, sample_block):
        """Test drawing with left alignment."""
        sample_block.style = {"alignment": "left"}
        sample_block.content = {"text": "Left aligned"}
        
        text_renderer.draw(sample_block)
        
        text_renderer.canvas.drawString.assert_called()
    
    def test_draw_with_alignment_center(self, text_renderer, sample_block):
        """Test drawing with center alignment."""
        sample_block.style = {"alignment": "center"}
        sample_block.content = {"text": "Center aligned"}
        
        text_renderer.draw(sample_block)
        
        # Should use drawCentredString or calculate center position
        assert text_renderer.canvas.drawString.called or text_renderer.canvas.drawCentredString.called
    
    def test_draw_with_alignment_right(self, text_renderer, sample_block):
        """Test drawing with right alignment."""
        sample_block.style = {"alignment": "right"}
        sample_block.content = {"text": "Right aligned"}
        
        text_renderer.draw(sample_block)
        
        # Should use drawRightString or calculate right position
        assert text_renderer.canvas.drawString.called or text_renderer.canvas.drawRightString.called
    
    def test_draw_with_alignment_justify(self, text_renderer, sample_block):
        """Test drawing with justify alignment."""
        sample_block.style = {"alignment": "justify"}
        sample_block.content = {"text": "Justified text with multiple words"}
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_runs(self, text_renderer, sample_block):
        """Test drawing block with runs."""
        sample_block.content = {
            "lines": [{"text": "Text with runs", "offset_baseline": 0.0}],
            "runs": [
                {"text": "Text ", "style": {}},
                {"text": "with ", "style": {"bold": True}},
                {"text": "runs", "style": {"italic": True}}
            ],
            "run_map": [{"start": 0, "end": 5}, {"start": 5, "end": 10}, {"start": 10, "end": 14}]
        }
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called
    
    def test_draw_with_marker(self, text_renderer, sample_block):
        """Test drawing block with list marker."""
        sample_block.content = {
            "text": "List item",
            "marker": {"text": "•", "style": {}}
        }
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_padding(self, text_renderer, sample_block):
        """Test drawing block with padding."""
        sample_block.style = {
            "padding": {"top": 10, "right": 10, "bottom": 10, "left": 10}
        }
        sample_block.content = {"text": "Text with padding"}
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_background(self, text_renderer, sample_block):
        """Test drawing block with background color."""
        sample_block.style = {
            "background": {"fill": "#FF0000"}
        }
        sample_block.content = {"text": "Text with background"}
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_border(self, text_renderer, sample_block):
        """Test drawing block with border."""
        sample_block.style = {
            "border": {"width": 1, "color": "#000000"}
        }
        sample_block.content = {"text": "Text with border"}
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_shadow(self, text_renderer, sample_block):
        """Test drawing block with shadow."""
        sample_block.style = {
            "shadow": {"enabled": True}
        }
        sample_block.content = {"text": "Text with shadow"}
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_string_payload(self, text_renderer, sample_block):
        """Test drawing block with string payload."""
        sample_block.content = "Simple string content"
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_iterable_payload(self, text_renderer, sample_block):
        """Test drawing block with iterable payload."""
        sample_block.content = ["Line 1", "Line 2", "Line 3"]
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_line_spacing(self, text_renderer, sample_block):
        """Test drawing block with custom line spacing."""
        sample_block.content = {
            "lines": [
                {"text": "Line 1", "offset_baseline": 0.0},
                {"text": "Line 2", "offset_baseline": 20.0}
            ],
            "line_spacing": 1.5
        }
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_is_justify_alignment(self):
        """Test _is_justify_alignment static method."""
        assert TextRenderer._is_justify_alignment("justify") is True
        assert TextRenderer._is_justify_alignment("left") is False
        assert TextRenderer._is_justify_alignment("center") is False
        assert TextRenderer._is_justify_alignment("right") is False
    
    def test_last_text_line_index(self):
        """Test _last_text_line_index static method."""
        lines = [
            {"text": "Line 1"},
            {"text": "Line 2"},
            {"text": ""},  # Empty line
            {"text": "Line 4"}
        ]
        
        index = TextRenderer._last_text_line_index(lines)
        
        assert index == 3  # Last non-empty line
    
    def test_last_text_line_index_empty(self):
        """Test _last_text_line_index with empty lines."""
        lines = [
            {"text": ""},
            {"text": ""}
        ]
        
        index = TextRenderer._last_text_line_index(lines)
        
        assert index == -1  # No text lines
    
    def test_char_for_glyph(self):
        """Test _char_for_glyph static method."""
        text = "Hello"
        
        assert TextRenderer._char_for_glyph(0, text) == "H"
        assert TextRenderer._char_for_glyph(4, text) == "o"
        assert TextRenderer._char_for_glyph(10, text) is None  # Out of range
    
    def test_translated_frame(self, text_renderer, sample_block):
        """Test _translated_frame method."""
        # When margins is None, frame should be unchanged
        text_renderer.margins = None
        frame = text_renderer._translated_frame(sample_block)
        
        assert isinstance(frame, Rect)
        assert frame.x == sample_block.frame.x
        assert frame.y == sample_block.frame.y
        assert frame.width == sample_block.frame.width
        assert frame.height == sample_block.frame.height
    
    def test_translated_frame_with_margins(self, mock_canvas):
        """Test _translated_frame with margins."""
        margins = Margins(50, 50, 50, 50)
        renderer = TextRenderer(mock_canvas, margins=margins)
        
        block = Mock(spec=LayoutBlock)
        block.frame = Rect(100, 100, 400, 200)
        
        frame = renderer._translated_frame(block)
        
        assert isinstance(frame, Rect)
    
    def test_apply_style(self, text_renderer):
        """Test _apply_style method."""
        style = {
            "font_name": "Arial",
            "font_size": 14,
            "color": "#000000"
        }
        
        text_renderer._apply_style(style)
        
        # Verify font and color were set
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.setFillColor.called
    
    def test_apply_style_with_bold(self, text_renderer):
        """Test _apply_style with bold."""
        style = {
            "bold": True,
            "font_name": "Arial"
        }
        
        text_renderer._apply_style(style)
        
        assert text_renderer.canvas.setFont.called
    
    def test_apply_style_with_italic(self, text_renderer):
        """Test _apply_style with italic."""
        style = {
            "italic": True,
            "font_name": "Arial"
        }
        
        text_renderer._apply_style(style)
        
        assert text_renderer.canvas.setFont.called
    
    def test_transform_text(self, text_renderer):
        """Test _transform_text method."""
        text = "Test Text"
        style = {}
        
        result = text_renderer._transform_text(text, style)
        
        assert isinstance(result, str)
        assert result == text
    
    def test_transform_text_with_uppercase(self, text_renderer):
        """Test _transform_text with uppercase."""
        text = "test text"
        style = {"text_transform": "uppercase"}
        
        result = text_renderer._transform_text(text, style)
        
        # Should transform to uppercase if supported
        assert isinstance(result, str)
    
    def test_resolve_hyperlink_target(self, text_renderer):
        """Test _resolve_hyperlink_target method."""
        style = {}
        text = "Link text"
        
        result = text_renderer._resolve_hyperlink_target(style, text)
        
        assert result is None  # No hyperlink in style
    
    def test_resolve_hyperlink_target_with_link(self, text_renderer):
        """Test _resolve_hyperlink_target with hyperlink."""
        style = {
            "hyperlink": {"target": "https://example.com"}
        }
        text = "Link text"
        
        result = text_renderer._resolve_hyperlink_target(style, text)
        
        assert result == "https://example.com"
    
    def test_draw_with_empty_content(self, text_renderer, sample_block):
        """Test drawing block with empty content."""
        sample_block.content = {}
        
        text_renderer.draw(sample_block)
        
        # Should handle gracefully - may not draw anything but shouldn't crash
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_none_content(self, text_renderer, sample_block):
        """Test drawing block with None content."""
        sample_block.content = None
        
        text_renderer.draw(sample_block)
        
        # Should handle gracefully - may not draw anything but shouldn't crash
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_usable_width(self, text_renderer, sample_block):
        """Test drawing block with usable_width hint."""
        sample_block.content = {
            "text": "Text with usable width",
            "usable_width": 300.0
        }
        
        text_renderer.draw(sample_block)
        
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called
    
    def test_draw_with_invalid_usable_width(self, text_renderer, sample_block):
        """Test drawing block with invalid usable_width."""
        sample_block.content = {
            "text": "Text with invalid usable width",
            "usable_width": "invalid"
        }
        
        text_renderer.draw(sample_block)
        
        # Should handle gracefully and use frame width
        assert text_renderer.canvas.setFont.called or text_renderer.canvas.drawString.called

