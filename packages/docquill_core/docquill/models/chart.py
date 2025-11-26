"""
Chart model for DOCX documents.

Handles chart functionality, properties, data, styling, and validation.
"""

from typing import Dict, Any, Optional, List
from .base import Models
import logging

logger = logging.getLogger(__name__)

class Chart(Models):
    """
    Represents a chart in the document.
    
    Handles chart functionality, properties, data, and styling.
    """
    
    def __init__(self, chart_type: str = "column", data: List[Dict[str, Any]] = None, 
                 style: Dict[str, Any] = None, position: Dict[str, Any] = None):
        """
        Initialize chart.
        
        Args:
            chart_type: Type of chart (column, line, pie, etc.)
            data: Chart data
            style: Chart styling information
            position: Chart position information
        """
        super().__init__()
        self.chart_type = chart_type
        self.data = data or []
        self.style = style or {}
        self.position = position or {}
        self.properties = {}
        self.validation_errors = []
        
        logger.debug(f"Chart initialized: {chart_type}")
    
    def set_chart_type(self, chart_type: str) -> None:
        """
        Set chart type.
        
        Args:
            chart_type: Type of chart
        """
        if not chart_type or not isinstance(chart_type, str):
            raise ValueError("Chart type must be a non-empty string")
        
        self.chart_type = chart_type
        logger.debug(f"Chart type set to: {chart_type}")
    
    def set_chart_data(self, data: List[Dict[str, Any]]) -> None:
        """
        Set chart data.
        
        Args:
            data: Chart data as list of dictionaries
        """
        if not isinstance(data, list):
            raise ValueError("Chart data must be a list")
        
        self.data = data.copy()
        logger.debug(f"Chart data set: {len(data)} data points")
    
    def set_chart_style(self, style: Dict[str, Any]) -> None:
        """
        Set chart style.
        
        Args:
            style: Chart styling information
        """
        if not isinstance(style, dict):
            raise ValueError("Chart style must be a dictionary")
        
        self.style = style.copy()
        logger.debug(f"Chart style set: {style}")
    
    def set_position(self, position: Dict[str, Any]) -> None:
        """
        Set chart position.
        
        Args:
            position: Position information dictionary
        """
        if not isinstance(position, dict):
            raise ValueError("Position must be a dictionary")
        
        self.position = position.copy()
        logger.debug(f"Chart position set: {position}")
    
    def get_chart_type(self) -> str:
        """
        Get chart type.
        
        Returns:
            Chart type
        """
        return self.chart_type
    
    def get_chart_data(self) -> List[Dict[str, Any]]:
        """
        Get chart data.
        
        Returns:
            Chart data
        """
        return self.data.copy()
    
    def get_chart_style(self) -> Dict[str, Any]:
        """
        Get chart style.
        
        Returns:
            Chart style
        """
        return self.style.copy()
    
    def get_position(self) -> Dict[str, Any]:
        """
        Get chart position.
        
        Returns:
            Position information
        """
        return self.position.copy()
    
    def add_data_point(self, data_point: Dict[str, Any]) -> None:
        """
        Add data point to chart.
        
        Args:
            data_point: Data point dictionary
        """
        if not isinstance(data_point, dict):
            raise ValueError("Data point must be a dictionary")
        
        self.data.append(data_point)
        logger.debug(f"Data point added: {data_point}")
    
    def remove_data_point(self, index: int) -> bool:
        """
        Remove data point from chart.
        
        Args:
            index: Index of data point to remove
            
        Returns:
            True if data point was removed, False if index out of range
        """
        if 0 <= index < len(self.data):
            removed_point = self.data.pop(index)
            logger.debug(f"Data point removed: {removed_point}")
            return True
        return False
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set chart property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Chart property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get chart property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate chart.
        
        Returns:
            True if chart is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate chart type
        if not self.chart_type:
            self.validation_errors.append("Chart type is required")
        
        # Validate data
        if not self.data:
            self.validation_errors.append("Chart data is required")
        
        # Validate data structure
        for i, data_point in enumerate(self.data):
            if not isinstance(data_point, dict):
                self.validation_errors.append(f"Data point {i} must be a dictionary")
        
        # Validate style
        if not isinstance(self.style, dict):
            self.validation_errors.append("Chart style must be a dictionary")
        
        # Validate position
        if not isinstance(self.position, dict):
            self.validation_errors.append("Chart position must be a dictionary")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Chart validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert chart to dictionary.
        
        Returns:
            Dictionary representation of chart
        """
        return {
            'type': 'chart',
            'chart_type': self.chart_type,
            'data': self.data.copy(),
            'style': self.style.copy(),
            'position': self.position.copy(),
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load chart from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.chart_type = data.get('chart_type', 'column')
        self.data = data.get('data', [])
        self.style = data.get('style', {})
        self.position = data.get('position', {})
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"Chart loaded from dictionary: {self.chart_type}")
    
    def get_chart_info(self) -> Dict[str, Any]:
        """
        Get chart information.
        
        Returns:
            Dictionary with chart information
        """
        return {
            'chart_type': self.chart_type,
            'data_points_count': len(self.data),
            'style_properties_count': len(self.style),
            'position_properties_count': len(self.position),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_data(self) -> None:
        """Clear all chart data."""
        self.data.clear()
        logger.debug("Chart data cleared")
    
    def clear_style(self) -> None:
        """Clear all chart styling."""
        self.style.clear()
        logger.debug("Chart style cleared")
    
    def has_data(self) -> bool:
        """
        Check if chart has data.
        
        Returns:
            True if chart has data, False otherwise
        """
        return len(self.data) > 0
    
    def get_data_count(self) -> int:
        """
        Get number of data points.
        
        Returns:
            Number of data points
        """
        return len(self.data)
