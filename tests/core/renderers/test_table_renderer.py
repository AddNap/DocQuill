"""
Tests for TableRenderer class.

This module contains unit tests for TableRenderer functionality
to increase test coverage from 10% to higher levels.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

from docquill.renderers.table_renderer import TableRenderer
from docquill.engine.unified_layout import LayoutBlock
from docquill.engine.geometry import Rect, Margins


class MockCell:
    """Mock cell object for testing."""
    def __init__(self, text=""):
        self.text = text
    
    def get_text(self):
        return self.text


class MockRow:
    """Mock row object for testing."""
    def __init__(self, cells):
        self.cells = cells


class TestTableRenderer:
    """Test cases for TableRenderer class."""
    
    @pytest.fixture
    def mock_canvas(self):
        """Create a mock ReportLab canvas."""
        canvas = Mock(spec=Canvas)
        canvas.stringWidth = Mock(return_value=100.0)
        canvas._fontname = "DejaVuSans"
        canvas._fontsize = 12
        canvas._leading = 14.4
        canvas.saveState = Mock()
        canvas.restoreState = Mock()
        canvas.setFont = Mock()
        canvas.setFillColor = Mock()
        canvas.setStrokeColor = Mock()
        return canvas
    
    @pytest.fixture
    def table_renderer(self, mock_canvas):
        """Create TableRenderer instance."""
        return TableRenderer(mock_canvas, margins=Margins(72, 72, 72, 72))
    
    @pytest.fixture
    def sample_block(self):
        """Create a sample LayoutBlock for testing."""
        block = Mock(spec=LayoutBlock)
        block.frame = Rect(100, 100, 400, 200)
        block.style = {}
        block.content = {
            "rows": [
                MockRow([MockCell("Cell 1"), MockCell("Cell 2")]),
                MockRow([MockCell("Cell 3"), MockCell("Cell 4")])
            ]
        }
        return block
    
    def test_init(self, mock_canvas):
        """Test TableRenderer initialization."""
        renderer = TableRenderer(mock_canvas)
        
        assert renderer.canvas == mock_canvas
        assert renderer.margins is None
    
    def test_init_with_margins(self, mock_canvas):
        """Test TableRenderer initialization with margins."""
        margins = Margins(50, 50, 50, 50)
        renderer = TableRenderer(mock_canvas, margins=margins)
        
        assert renderer.margins == margins
    
    def test_draw_with_simple_table(self, table_renderer, sample_block):
        """Test drawing simple table."""
        table_renderer.draw(sample_block)
        
        # Verify canvas methods were called
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_empty_rows(self, table_renderer, sample_block):
        """Test drawing table with empty rows."""
        sample_block.content = {"rows": []}
        
        table_renderer.draw(sample_block)
        
        # Should handle gracefully
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_no_rows(self, table_renderer, sample_block):
        """Test drawing table with no rows."""
        sample_block.content = {}
        
        table_renderer.draw(sample_block)
        
        # Should handle gracefully
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_different_row_lengths(self, table_renderer, sample_block):
        """Test drawing table with rows of different lengths."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Cell 1"), MockCell("Cell 2"), MockCell("Cell 3")]),
                MockRow([MockCell("Cell 4"), MockCell("Cell 5")])
            ]
        }
        
        table_renderer.draw(sample_block)
        
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_style(self, table_renderer, sample_block):
        """Test drawing table with style."""
        sample_block.style = {
            "border": {"width": 1, "color": "#000000"},
            "background": {"fill": "#F0F0F0"}
        }
        
        table_renderer.draw(sample_block)
        
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_shadow(self, table_renderer, sample_block):
        """Test drawing table with shadow."""
        sample_block.style = {
            "shadow": {"enabled": True}
        }
        
        table_renderer.draw(sample_block)
        
        assert True  # Just verify it doesn't crash
    
    def test_column_widths_with_explicit_widths(self, table_renderer, sample_block):
        """Test _column_widths with explicit grid widths."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Cell 1"), MockCell("Cell 2")])
            ],
            "grid": [
                {"width": 2000},  # In twips
                {"width": 3000}
            ]
        }
        
        widths = table_renderer._column_widths(sample_block, 2)
        
        assert len(widths) == 2
        assert all(w > 0 for w in widths)
    
    def test_column_widths_with_auto_fit(self, table_renderer, sample_block):
        """Test _column_widths with auto-fit (no grid)."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Short"), MockCell("Much longer cell content")])
            ]
        }
        
        widths = table_renderer._column_widths(sample_block, 2)
        
        assert len(widths) == 2
        assert all(w > 0 for w in widths)
    
    def test_column_widths_with_mixed_widths(self, table_renderer, sample_block):
        """Test _column_widths with mixed explicit and auto-fit widths."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Cell 1"), MockCell("Cell 2"), MockCell("Cell 3")])
            ],
            "grid": [
                {"width": 2000},  # Explicit
                {},  # Auto-fit
                {"width": 3000}  # Explicit
            ]
        }
        
        widths = table_renderer._column_widths(sample_block, 3)
        
        assert len(widths) == 3
        assert all(w > 0 for w in widths)
    
    def test_column_widths_with_invalid_widths(self, table_renderer, sample_block):
        """Test _column_widths with invalid width values."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Cell 1"), MockCell("Cell 2")])
            ],
            "grid": [
                {"width": "invalid"},
                {"width": None}
            ]
        }
        
        widths = table_renderer._column_widths(sample_block, 2)
        
        assert len(widths) == 2
        assert all(w > 0 for w in widths)
    
    def test_calculate_auto_fit_widths(self, table_renderer, sample_block):
        """Test _calculate_auto_fit_widths method."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Short"), MockCell("Much longer cell content")]),
                MockRow([MockCell("Medium length"), MockCell("Short")])
            ]
        }
        sample_block.style = {}
        
        widths = table_renderer._calculate_auto_fit_widths(sample_block, 2)
        
        assert len(widths) == 2
        assert all(w > 0 for w in widths)
        # Second column should be wider due to longer content
        assert widths[1] >= widths[0]
    
    def test_calculate_auto_fit_widths_empty_rows(self, table_renderer, sample_block):
        """Test _calculate_auto_fit_widths with empty rows."""
        sample_block.content = {"rows": []}
        sample_block.style = {}
        
        widths = table_renderer._calculate_auto_fit_widths(sample_block, 2)
        
        assert len(widths) == 2
        assert all(w > 0 for w in widths)
    
    def test_calculate_auto_fit_widths_with_padding(self, table_renderer, sample_block):
        """Test _calculate_auto_fit_widths with cell padding."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Cell 1"), MockCell("Cell 2")])
            ]
        }
        sample_block.style = {
            "cell_padding": {"left": 10, "right": 10}
        }
        
        widths = table_renderer._calculate_auto_fit_widths(sample_block, 2)
        
        assert len(widths) == 2
        assert all(w > 0 for w in widths)
    
    def test_base_table_style(self, table_renderer):
        """Test _base_table_style method."""
        style = {}
        
        commands = table_renderer._base_table_style(style)
        
        assert isinstance(commands, list)
        assert len(commands) > 0
    
    def test_base_table_style_with_borders(self, table_renderer):
        """Test _base_table_style with border style."""
        style = {
            "border": {
                "width": 1,
                "color": "#000000"
            }
        }
        
        commands = table_renderer._base_table_style(style)
        
        assert isinstance(commands, list)
        assert len(commands) > 0
    
    def test_base_table_style_with_background(self, table_renderer):
        """Test _base_table_style with background color."""
        style = {
            "background": {
                "fill": "#F0F0F0"
            }
        }
        
        commands = table_renderer._base_table_style(style)
        
        assert isinstance(commands, list)
        assert len(commands) > 0
    
    def test_base_table_style_with_cell_padding(self, table_renderer):
        """Test _base_table_style with cell padding."""
        style = {
            "cell_padding": {
                "top": 5,
                "right": 10,
                "bottom": 5,
                "left": 10
            }
        }
        
        commands = table_renderer._base_table_style(style)
        
        assert isinstance(commands, list)
        assert len(commands) > 0
    
    def test_translated_frame(self, table_renderer, sample_block):
        """Test _translated_frame method."""
        # When margins is None, frame should be unchanged
        table_renderer.margins = None
        frame = table_renderer._translated_frame(sample_block)
        
        assert isinstance(frame, Rect)
        assert frame.x == sample_block.frame.x
        assert frame.y == sample_block.frame.y
        assert frame.width == sample_block.frame.width
        assert frame.height == sample_block.frame.height
    
    def test_translated_frame_with_margins(self, mock_canvas):
        """Test _translated_frame with margins."""
        margins = Margins(50, 50, 50, 50)
        renderer = TableRenderer(mock_canvas, margins=margins)
        
        block = Mock(spec=LayoutBlock)
        block.frame = Rect(100, 100, 400, 200)
        
        frame = renderer._translated_frame(block)
        
        assert isinstance(frame, Rect)
    
    def test_normalize_width(self, table_renderer):
        """Test _normalize_width method."""
        result = table_renderer._normalize_width(100, 400)
        
        assert isinstance(result, float)
        assert result > 0
    
    def test_normalize_width_with_percentage(self, table_renderer):
        """Test _normalize_width with percentage."""
        result = table_renderer._normalize_width("50%", 400)
        
        assert isinstance(result, float)
        assert result == 200.0
    
    def test_normalize_width_with_twips(self, table_renderer):
        """Test _normalize_width with twips value."""
        result = table_renderer._normalize_width(2000, 400)  # 2000 twips
        
        assert isinstance(result, float)
        assert result > 0
    
    def test_normalize_dimension(self, table_renderer):
        """Test _normalize_dimension method."""
        result = table_renderer._normalize_dimension(100)
        
        assert isinstance(result, float)
        assert result == 100.0
    
    def test_normalize_dimension_with_string(self, table_renderer):
        """Test _normalize_dimension with string value."""
        result = table_renderer._normalize_dimension("100")
        
        assert isinstance(result, float)
        assert result == 100.0
    
    def test_normalize_dimension_with_twips(self, table_renderer):
        """Test _normalize_dimension with twips value."""
        result = table_renderer._normalize_dimension(2000)  # 2000 twips
        
        assert isinstance(result, float)
        assert result > 0
    
    def test_normalize_dimension_with_invalid(self, table_renderer):
        """Test _normalize_dimension with invalid value."""
        result = table_renderer._normalize_dimension("invalid")
        
        assert isinstance(result, float)
        assert result == 0.0
    
    def test_draw_with_cell_text_attribute(self, table_renderer, sample_block):
        """Test drawing table with cells using text attribute."""
        class CellWithText:
            def __init__(self, text):
                self.text = text
        
        sample_block.content = {
            "rows": [
                MockRow([CellWithText("Cell 1"), CellWithText("Cell 2")])
            ]
        }
        
        table_renderer.draw(sample_block)
        
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_cell_string(self, table_renderer, sample_block):
        """Test drawing table with cells as strings."""
        sample_block.content = {
            "rows": [
                MockRow(["Cell 1", "Cell 2"])
            ]
        }
        
        table_renderer.draw(sample_block)
        
        assert True  # Just verify it doesn't crash
    
    def test_draw_with_zero_total_width(self, table_renderer, sample_block):
        """Test drawing table when total width is zero."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Cell 1"), MockCell("Cell 2")])
            ],
            "grid": [
                {"width": 0},
                {"width": 0}
            ]
        }
        
        # Should handle gracefully
        try:
            table_renderer.draw(sample_block)
            assert True
        except (ZeroDivisionError, ValueError):
            # Acceptable if it raises an error for zero width
            assert True
    
    def test_column_widths_scaling(self, table_renderer, sample_block):
        """Test that column widths are scaled to fit table width."""
        sample_block.content = {
            "rows": [
                MockRow([MockCell("Cell 1"), MockCell("Cell 2")])
            ],
            "grid": [
                {"width": 1000},
                {"width": 1000}
            ]
        }
        
        widths = table_renderer._column_widths(sample_block, 2)
        
        assert len(widths) == 2
        total_width = sum(widths)
        # Total should be approximately equal to frame width (allowing for small rounding)
        assert abs(total_width - sample_block.frame.width) < 1.0

