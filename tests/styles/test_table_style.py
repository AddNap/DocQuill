"""
Tests for TableStyle class.

This module contains unit tests for TableStyle functionality.
"""

import pytest

from docx_interpreter.styles.table_style import TableStyle


class TestTableStyle:
    """Test cases for TableStyle class."""
    
    @pytest.fixture
    def table_style(self):
        """Create TableStyle instance."""
        return TableStyle("TableGrid", "Normal")
    
    def test_init(self):
        """Test TableStyle initialization."""
        style = TableStyle("TableGrid", "Normal")
        
        assert style.style_name == "TableGrid"
        assert style.parent_style == "Normal"
        assert isinstance(style.properties, dict)
    
    def test_set_table_alignment(self, table_style):
        """Test setting table alignment."""
        table_style.set_table_alignment("center")
        
        assert table_style.get_table_alignment() == "center"
    
    def test_set_table_alignment_invalid(self, table_style):
        """Test setting invalid table alignment."""
        with pytest.raises(ValueError):
            table_style.set_table_alignment("invalid")
    
    def test_set_table_borders(self, table_style):
        """Test setting table borders."""
        borders = {
            "top": {"width": 1, "color": "#000000"},
            "bottom": {"width": 1, "color": "#000000"}
        }
        table_style.set_table_borders(borders)
        
        result = table_style.get_table_borders()
        assert result == borders
    
    def test_set_table_borders_invalid(self, table_style):
        """Test setting invalid table borders."""
        with pytest.raises(ValueError):
            table_style.set_table_borders("invalid")
    
    def test_set_table_shading(self, table_style):
        """Test setting table shading."""
        shading = {"fill": "#F0F0F0", "pattern": "solid"}
        table_style.set_table_shading(shading)
        
        result = table_style.get_table_shading()
        assert result == shading
    
    def test_set_table_shading_invalid(self, table_style):
        """Test setting invalid table shading."""
        with pytest.raises(ValueError):
            table_style.set_table_shading("invalid")
    
    def test_set_cell_spacing(self, table_style):
        """Test setting cell spacing."""
        table_style.set_cell_spacing(5.0)
        
        assert table_style.get_cell_spacing() == 5.0
    
    def test_set_cell_spacing_invalid(self, table_style):
        """Test setting invalid cell spacing."""
        with pytest.raises(ValueError):
            table_style.set_cell_spacing(-1)
    
    def test_set_cell_padding(self, table_style):
        """Test setting cell padding."""
        padding = {"top": 5, "right": 10, "bottom": 5, "left": 10}
        table_style.set_cell_padding(padding)
        
        result = table_style.get_cell_padding()
        assert result == padding
    
    def test_set_cell_padding_invalid(self, table_style):
        """Test setting invalid cell padding."""
        with pytest.raises(ValueError):
            table_style.set_cell_padding("invalid")
    
    def test_set_table_width(self, table_style):
        """Test setting table width."""
        table_style.set_table_width(500, "points")
        
        result = table_style.get_table_width()
        assert result["width"] == 500
        assert result["width_type"] == "points"
    
    def test_set_table_width_invalid(self, table_style):
        """Test setting invalid table width."""
        with pytest.raises(ValueError):
            table_style.set_table_width(-1, "points")
    
    def test_set_property(self, table_style):
        """Test setting custom property."""
        table_style.set_property("custom_prop", "value")
        
        assert table_style.get_property("custom_prop") == "value"
    
    def test_get_property_default(self, table_style):
        """Test getting property with default value."""
        result = table_style.get_property("non_existent", "default")
        
        assert result == "default"
    
    def test_has_property(self, table_style):
        """Test checking if property exists."""
        table_style.set_property("test_prop", "value")
        
        assert table_style.has_property("test_prop") is True
        assert table_style.has_property("non_existent") is False
    
    def test_remove_property(self, table_style):
        """Test removing property."""
        table_style.set_property("test_prop", "value")
        
        result = table_style.remove_property("test_prop")
        
        assert result is True
        assert table_style.has_property("test_prop") is False
    
    def test_remove_property_not_found(self, table_style):
        """Test removing non-existing property."""
        result = table_style.remove_property("non_existent")
        
        assert result is False
    
    def test_validate(self, table_style):
        """Test validating table style."""
        table_style.set_table_alignment("left")
        table_style.set_cell_spacing(0)
        table_style.set_table_width(100, "points")
        
        assert table_style.validate() is True
    
    def test_validate_invalid(self, table_style):
        """Test validating invalid table style."""
        # Set invalid alignment through properties directly
        table_style.properties['table_alignment'] = 'invalid'
        
        assert table_style.validate() is False
        assert len(table_style.get_validation_errors()) > 0
    
    def test_to_dict(self, table_style):
        """Test converting to dictionary."""
        table_style.set_table_alignment("center")
        
        result = table_style.to_dict()
        
        assert isinstance(result, dict)
        assert result['style_name'] == "TableGrid"
        assert result['parent_style'] == "Normal"
        assert 'properties' in result
    
    def test_from_dict(self, table_style):
        """Test loading from dictionary."""
        data = {
            'style_name': 'CustomTable',
            'parent_style': 'TableGrid',
            'properties': {'table_alignment': 'right'}
        }
        
        table_style.from_dict(data)
        
        assert table_style.style_name == 'CustomTable'
        assert table_style.parent_style == 'TableGrid'
        assert table_style.get_table_alignment() == 'right'
    
    def test_get_style_info(self, table_style):
        """Test getting style information."""
        table_style.set_table_alignment("center")
        
        info = table_style.get_style_info()
        
        assert isinstance(info, dict)
        assert 'style_name' in info
        assert 'properties_count' in info
        assert 'is_valid' in info
    
    def test_clear_properties(self, table_style):
        """Test clearing all properties."""
        table_style.set_table_alignment("center")
        table_style.set_cell_spacing(5)
        
        table_style.clear_properties()
        
        assert table_style.get_properties_count() == 0
    
    def test_get_properties_count(self, table_style):
        """Test getting properties count."""
        table_style.set_table_alignment("center")
        table_style.set_cell_spacing(5)
        
        count = table_style.get_properties_count()
        
        assert count >= 2
    
    def test_update_property(self, table_style):
        """Test updating property."""
        table_style.set_property("test_prop", "value1")
        table_style.update_property("test_prop", "value2")
        
        assert table_style.get_property("test_prop") == "value2"
    
    def test_get_property_names(self, table_style):
        """Test getting property names."""
        table_style.set_table_alignment("center")
        table_style.set_cell_spacing(5)
        
        names = table_style.get_property_names()
        
        assert isinstance(names, list)
        assert 'table_alignment' in names
        assert 'cell_spacing' in names
    
    def test_get_style_summary(self, table_style):
        """Test getting style summary."""
        table_style.set_table_alignment("center")
        table_style.set_table_borders({"top": {"width": 1}})
        
        summary = table_style.get_style_summary()
        
        assert isinstance(summary, dict)
        assert 'has_borders' in summary
        assert summary['has_borders'] is True

