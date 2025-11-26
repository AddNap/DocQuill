"""
Table style for DOCX documents.

Handles table style functionality, table formatting, table borders, table shading, and table alignment.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class TableStyle:
    """
    Represents table style and formatting.
    
    Handles table style functionality, table formatting, table borders, and table shading.
    """
    
    def __init__(self, style_name: str = "", parent_style: str = ""):
        """
        Initialize table style.
        
        Args:
            style_name: Style name
            parent_style: Parent style name
        """
        self.style_name = style_name
        self.parent_style = parent_style
        self.properties = {}
        self.validation_errors = []
        
        # Initialize default properties
        self._initialize_default_properties()
        
        logger.debug(f"TableStyle initialized: {style_name}")
    
    def set_table_alignment(self, alignment: str) -> None:
        """
        Set table alignment.
        
        Args:
            alignment: Table alignment (left, center, right)
        """
        if not alignment or not isinstance(alignment, str):
            raise ValueError("Alignment must be a non-empty string")
        
        valid_alignments = ['left', 'center', 'right']
        if alignment not in valid_alignments:
            raise ValueError(f"Invalid table alignment: {alignment}. Must be one of: {valid_alignments}")
        
        self.properties['table_alignment'] = alignment
        logger.debug(f"Table alignment set to: {alignment}")
    
    def set_table_borders(self, borders: Dict[str, Any]) -> None:
        """
        Set table borders.
        
        Args:
            borders: Border configuration dictionary
        """
        if not isinstance(borders, dict):
            raise ValueError("Borders must be a dictionary")
        
        # Validate border properties
        valid_border_sides = ['top', 'bottom', 'left', 'right', 'inside_horizontal', 'inside_vertical']
        for side in borders.keys():
            if side not in valid_border_sides:
                raise ValueError(f"Invalid border side: {side}. Must be one of: {valid_border_sides}")
        
        self.properties['borders'] = borders.copy()
        logger.debug(f"Table borders set: {borders}")
    
    def set_table_shading(self, shading: Dict[str, Any]) -> None:
        """
        Set table shading.
        
        Args:
            shading: Shading configuration dictionary
        """
        if not isinstance(shading, dict):
            raise ValueError("Shading must be a dictionary")
        
        # Validate shading properties
        if 'color' in shading and not isinstance(shading['color'], str):
            raise ValueError("Shading color must be a string")
        
        if 'pattern' in shading and not isinstance(shading['pattern'], str):
            raise ValueError("Shading pattern must be a string")
        
        self.properties['shading'] = shading.copy()
        logger.debug(f"Table shading set: {shading}")
    
    def set_cell_spacing(self, spacing: float) -> None:
        """
        Set cell spacing.
        
        Args:
            spacing: Cell spacing in points
        """
        if not isinstance(spacing, (int, float)) or spacing < 0:
            raise ValueError("Cell spacing must be a non-negative number")
        
        self.properties['cell_spacing'] = spacing
        logger.debug(f"Cell spacing set to: {spacing}pt")
    
    def set_cell_padding(self, padding: Dict[str, float]) -> None:
        """
        Set cell padding.
        
        Args:
            padding: Padding configuration dictionary
        """
        if not isinstance(padding, dict):
            raise ValueError("Padding must be a dictionary")
        
        # Validate padding properties
        valid_padding_sides = ['top', 'bottom', 'left', 'right']
        for side in padding.keys():
            if side not in valid_padding_sides:
                raise ValueError(f"Invalid padding side: {side}. Must be one of: {valid_padding_sides}")
            
            if not isinstance(padding[side], (int, float)) or padding[side] < 0:
                raise ValueError(f"Padding {side} must be a non-negative number")
        
        self.properties['cell_padding'] = padding.copy()
        logger.debug(f"Cell padding set: {padding}")
    
    def set_table_width(self, width: float, width_type: str = "auto") -> None:
        """
        Set table width.
        
        Args:
            width: Table width
            width_type: Width type (auto, percentage, points)
        """
        if not isinstance(width, (int, float)) or width <= 0:
            raise ValueError("Table width must be a positive number")
        
        valid_width_types = ['auto', 'percentage', 'points']
        if width_type not in valid_width_types:
            raise ValueError(f"Invalid width type: {width_type}. Must be one of: {valid_width_types}")
        
        self.properties['table_width'] = width
        self.properties['table_width_type'] = width_type
        logger.debug(f"Table width set: {width} ({width_type})")
    
    def get_table_alignment(self) -> str:
        """
        Get table alignment.
        
        Returns:
            Table alignment
        """
        return self.properties.get('table_alignment', 'left')
    
    def get_table_borders(self) -> Dict[str, Any]:
        """
        Get table borders.
        
        Returns:
            Dictionary with border information
        """
        return self.properties.get('borders', {})
    
    def get_table_shading(self) -> Dict[str, Any]:
        """
        Get table shading.
        
        Returns:
            Dictionary with shading information
        """
        return self.properties.get('shading', {})
    
    def get_cell_spacing(self) -> float:
        """
        Get cell spacing.
        
        Returns:
            Cell spacing in points
        """
        return self.properties.get('cell_spacing', 0)
    
    def get_cell_padding(self) -> Dict[str, float]:
        """
        Get cell padding.
        
        Returns:
            Dictionary with padding information
        """
        return self.properties.get('cell_padding', {})
    
    def get_table_width(self) -> Dict[str, Any]:
        """
        Get table width.
        
        Returns:
            Dictionary with width information
        """
        return {
            'width': self.properties.get('table_width', 0),
            'width_type': self.properties.get('table_width_type', 'auto')
        }
    
    def set_property(self, property_name: str, property_value: Any) -> None:
        """
        Set style property.
        
        Args:
            property_name: Property name
            property_value: Property value
        """
        if not property_name or not isinstance(property_name, str):
            raise ValueError("Property name must be a non-empty string")
        
        self.properties[property_name] = property_value
        logger.debug(f"Style property set: {property_name} = {property_value}")
    
    def get_property(self, property_name: str, default: Any = None) -> Any:
        """
        Get style property.
        
        Args:
            property_name: Property name
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(property_name, default)
    
    def has_property(self, property_name: str) -> bool:
        """
        Check if style has property.
        
        Args:
            property_name: Property name
            
        Returns:
            True if property exists, False otherwise
        """
        return property_name in self.properties
    
    def remove_property(self, property_name: str) -> bool:
        """
        Remove style property.
        
        Args:
            property_name: Property name to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if property_name in self.properties:
            del self.properties[property_name]
            logger.debug(f"Style property removed: {property_name}")
            return True
        return False
    
    def validate(self) -> bool:
        """
        Validate table style.
        
        Returns:
            True if style is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate table alignment
        alignment = self.properties.get('table_alignment', 'left')
        valid_alignments = ['left', 'center', 'right']
        if alignment not in valid_alignments:
            self.validation_errors.append(f"Invalid table alignment: {alignment}")
        
        # Validate cell spacing
        cell_spacing = self.properties.get('cell_spacing', 0)
        if not isinstance(cell_spacing, (int, float)) or cell_spacing < 0:
            self.validation_errors.append("Invalid cell spacing value")
        
        # Validate table width
        table_width = self.properties.get('table_width', 0)
        if not isinstance(table_width, (int, float)) or table_width <= 0:
            self.validation_errors.append("Invalid table width value")
        
        # Validate width type
        width_type = self.properties.get('table_width_type', 'auto')
        valid_width_types = ['auto', 'percentage', 'points']
        if width_type not in valid_width_types:
            self.validation_errors.append(f"Invalid width type: {width_type}")
        
        # Validate cell padding
        cell_padding = self.properties.get('cell_padding', {})
        if not isinstance(cell_padding, dict):
            self.validation_errors.append("Invalid cell padding configuration")
        else:
            for side, padding in cell_padding.items():
                if not isinstance(padding, (int, float)) or padding < 0:
                    self.validation_errors.append(f"Invalid padding {side} value")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"TableStyle validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert table style to dictionary.
        
        Returns:
            Dictionary representation of table style
        """
        return {
            'type': 'table_style',
            'style_name': self.style_name,
            'parent_style': self.parent_style,
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load table style from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.style_name = data.get('style_name', '')
        self.parent_style = data.get('parent_style', '')
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"TableStyle loaded from dictionary: {self.style_name}")
    
    def get_style_info(self) -> Dict[str, Any]:
        """
        Get table style information.
        
        Returns:
            Dictionary with style information
        """
        return {
            'style_name': self.style_name,
            'parent_style': self.parent_style,
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_properties(self) -> None:
        """Clear all style properties."""
        self.properties.clear()
        logger.debug("All style properties cleared")
    
    def get_properties_count(self) -> int:
        """
        Get number of properties.
        
        Returns:
            Number of properties
        """
        return len(self.properties)
    
    def update_property(self, property_name: str, property_value: Any) -> None:
        """
        Update style property.
        
        Args:
            property_name: Property name
            property_value: Property value
        """
        if not property_name or not isinstance(property_name, str):
            raise ValueError("Property name must be a non-empty string")
        
        self.properties[property_name] = property_value
        logger.debug(f"Style property updated: {property_name} = {property_value}")
    
    def get_property_names(self) -> List[str]:
        """
        Get list of property names.
        
        Returns:
            List of property names
        """
        return list(self.properties.keys())
    
    def _initialize_default_properties(self) -> None:
        """Initialize default table properties."""
        self.properties = {
            'table_alignment': 'left',
            'cell_spacing': 0,
            'cell_padding': {},
            'table_width': 0,
            'table_width_type': 'auto',
            'borders': {},
            'shading': {}
        }
    
    def get_style_summary(self) -> Dict[str, Any]:
        """
        Get style summary.
        
        Returns:
            Dictionary with style summary
        """
        return {
            'style_name': self.style_name,
            'parent_style': self.parent_style,
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'has_borders': bool(self.properties.get('borders')),
            'has_shading': bool(self.properties.get('shading')),
            'has_padding': bool(self.properties.get('cell_padding')),
            'table_width': self.get_table_width()
        }
