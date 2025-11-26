"""
ControlBox model for DOCX documents.

Handles controlbox functionality, form control support, checkbox support, dropdown support, and text input support.
"""

from typing import Dict, Any, Optional, List
from .base import Models
import logging

logger = logging.getLogger(__name__)

class ControlBox(Models):
    """
    Represents a form control in the document.
    
    Handles controlbox functionality, control types, properties, and validation.
    """
    
    def __init__(self, control_type: str = "text", properties: Dict[str, Any] = None, 
                 value: Any = None, position: Dict[str, Any] = None):
        """
        Initialize controlbox.
        
        Args:
            control_type: Type of control (text, checkbox, dropdown, etc.)
            properties: Control properties
            value: Control value
            position: Control position
        """
        super().__init__()
        self.control_type = control_type
        self.properties = properties or {}
        self.value = value
        self.position = position or {}
        self.validation_errors = []
        
        logger.debug(f"ControlBox initialized: {control_type}")
    
    def set_control_type(self, control_type: str) -> None:
        """
        Set control type.
        
        Args:
            control_type: Type of control
        """
        if not control_type or not isinstance(control_type, str):
            raise ValueError("Control type must be a non-empty string")
        
        self.control_type = control_type
        logger.debug(f"Control type set to: {control_type}")
    
    def set_properties(self, properties: Dict[str, Any]) -> None:
        """
        Set control properties.
        
        Args:
            properties: Control properties dictionary
        """
        if not isinstance(properties, dict):
            raise ValueError("Control properties must be a dictionary")
        
        self.properties = properties.copy()
        logger.debug(f"Control properties set: {properties}")
    
    def get_control_type(self) -> str:
        """
        Get control type.
        
        Returns:
            Control type
        """
        return self.control_type
    
    def get_value(self) -> Any:
        """
        Get control value.
        
        Returns:
            Control value
        """
        return self.value
    
    def set_value(self, value: Any) -> None:
        """
        Set control value.
        
        Args:
            value: Control value
        """
        self.value = value
        logger.debug(f"Control value set to: {value}")
    
    def set_position(self, position: Dict[str, Any]) -> None:
        """
        Set control position.
        
        Args:
            position: Position information dictionary
        """
        if not isinstance(position, dict):
            raise ValueError("Position must be a dictionary")
        
        self.position = position.copy()
        logger.debug(f"Control position set: {position}")
    
    def get_position(self) -> Dict[str, Any]:
        """
        Get control position.
        
        Returns:
            Position information
        """
        return self.position.copy()
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set control property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Control property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get control property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate control.
        
        Returns:
            True if control is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate control type
        if not self.control_type:
            self.validation_errors.append("Control type is required")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Control properties must be a dictionary")
        
        # Validate position
        if not isinstance(self.position, dict):
            self.validation_errors.append("Control position must be a dictionary")
        
        # Type-specific validation
        if self.control_type == "checkbox":
            if not isinstance(self.value, bool):
                self.validation_errors.append("Checkbox value must be a boolean")
        elif self.control_type == "dropdown":
            if not isinstance(self.value, (str, int)):
                self.validation_errors.append("Dropdown value must be a string or integer")
        elif self.control_type == "text":
            if not isinstance(self.value, str):
                self.validation_errors.append("Text control value must be a string")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Control validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert control to dictionary.
        
        Returns:
            Dictionary representation of control
        """
        return {
            'type': 'controlbox',
            'control_type': self.control_type,
            'properties': self.properties.copy(),
            'value': self.value,
            'position': self.position.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load control from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.control_type = data.get('control_type', 'text')
        self.properties = data.get('properties', {})
        self.value = data.get('value')
        self.position = data.get('position', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"ControlBox loaded from dictionary: {self.control_type}")
    
    def get_control_info(self) -> Dict[str, Any]:
        """
        Get control information.
        
        Returns:
            Dictionary with control information
        """
        return {
            'control_type': self.control_type,
            'properties_count': len(self.properties),
            'position_properties_count': len(self.position),
            'has_value': self.value is not None,
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_properties(self) -> None:
        """Clear all control properties."""
        self.properties.clear()
        logger.debug("Control properties cleared")
    
    def clear_value(self) -> None:
        """Clear control value."""
        self.value = None
        logger.debug("Control value cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if control has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove control property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Control property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if control is empty.
        
        Returns:
            True if control has no value, False otherwise
        """
        return self.value is None or (isinstance(self.value, str) and not self.value.strip())
    
    def get_properties_count(self) -> int:
        """
        Get number of properties.
        
        Returns:
            Number of properties
        """
        return len(self.properties)
