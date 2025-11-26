"""
Custom properties for DOCX documents.

Handles custom properties functionality, custom properties parsing, custom properties validation, custom properties access, and custom properties serialization.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class CustomProperties:
    """
    Represents custom document properties.
    
    Handles custom properties functionality, custom properties parsing, custom properties validation, and custom properties access.
    """
    
    def __init__(self, properties: Optional[Dict[str, Any]] = None):
        """
        Initialize custom properties.
        
        Args:
            properties: Custom properties dictionary
        """
        self.properties = properties or {}
        self.validation_errors = []
        self.custom_properties_stats = {
            'total_properties': 0,
            'string_properties': 0,
            'numeric_properties': 0,
            'boolean_properties': 0,
            'date_properties': 0,
            'other_properties': 0
        }
        
        # Update stats
        self._update_stats()
        
        logger.debug("Custom properties initialized")
    
    def add_property(self, name: str, value: Any, property_type: str = "string") -> None:
        """
        Add custom property.
        
        Args:
            name: Property name
            value: Property value
            property_type: Property type (string, number, boolean, date, other)
        """
        if not name or not isinstance(name, str):
            raise ValueError("Property name must be a non-empty string")
        
        if not isinstance(property_type, str):
            raise ValueError("Property type must be a string")
        
        # Validate property type
        valid_types = ["string", "number", "boolean", "date", "other"]
        if property_type not in valid_types:
            raise ValueError(f"Property type must be one of: {valid_types}")
        
        self.properties[name] = {
            'value': value,
            'type': property_type
        }
        self._update_stats()
        
        logger.debug(f"Custom property added: {name} = {value} ({property_type})")
    
    def get_property(self, name: str) -> Optional[Any]:
        """
        Get custom property by name.
        
        Args:
            name: Property name
            
        Returns:
            Property value or None if not found
        """
        if name in self.properties:
            return self.properties[name]['value']
        return None
    
    def get_property_type(self, name: str) -> Optional[str]:
        """
        Get custom property type.
        
        Args:
            name: Property name
            
        Returns:
            Property type or None if not found
        """
        if name in self.properties:
            return self.properties[name]['type']
        return None
    
    def get_properties(self) -> Dict[str, Any]:
        """
        Get all custom properties.
        
        Returns:
            Dictionary with all custom properties
        """
        return self.properties.copy()
    
    def get_property_names(self) -> List[str]:
        """
        Get all property names.
        
        Returns:
            List of property names
        """
        return list(self.properties.keys())
    
    def get_property_count(self) -> int:
        """
        Get property count.
        
        Returns:
            Number of custom properties
        """
        return len(self.properties)
    
    def remove_property(self, name: str) -> bool:
        """
        Remove custom property.
        
        Args:
            name: Property name to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if name in self.properties:
            del self.properties[name]
            self._update_stats()
            logger.debug(f"Custom property removed: {name}")
            return True
        return False
    
    def set_property(self, name: str, value: Any, property_type: str = "string") -> None:
        """
        Set custom property.
        
        Args:
            name: Property name
            value: Property value
            property_type: Property type (string, number, boolean, date, other)
        """
        if not name or not isinstance(name, str):
            raise ValueError("Property name must be a non-empty string")
        
        if not isinstance(property_type, str):
            raise ValueError("Property type must be a string")
        
        # Validate property type
        valid_types = ["string", "number", "boolean", "date", "other"]
        if property_type not in valid_types:
            raise ValueError(f"Property type must be one of: {valid_types}")
        
        self.properties[name] = {
            'value': value,
            'type': property_type
        }
        self._update_stats()
        
        logger.debug(f"Custom property set: {name} = {value} ({property_type})")
    
    def has_property(self, name: str) -> bool:
        """
        Check if custom property exists.
        
        Args:
            name: Property name
            
        Returns:
            True if property exists, False otherwise
        """
        return name in self.properties
    
    def clear_properties(self) -> None:
        """Clear all custom properties."""
        self.properties.clear()
        self._update_stats()
        logger.debug("Custom properties cleared")
    
    def get_properties_by_type(self, property_type: str) -> Dict[str, Any]:
        """
        Get properties by type.
        
        Args:
            property_type: Property type to filter by
            
        Returns:
            Dictionary with properties of the specified type
        """
        filtered_properties = {}
        for name, prop in self.properties.items():
            if prop['type'] == property_type:
                filtered_properties[name] = prop['value']
        return filtered_properties
    
    def validate(self) -> bool:
        """
        Validate custom properties.
        
        Returns:
            True if custom properties are valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate property names and types
        for name, prop in self.properties.items():
            if not name or not isinstance(name, str):
                self.validation_errors.append(f"Invalid property name: {name}")
            
            if not isinstance(prop, dict) or 'value' not in prop or 'type' not in prop:
                self.validation_errors.append(f"Invalid property structure: {name}")
            
            if 'type' in prop and prop['type'] not in ["string", "number", "boolean", "date", "other"]:
                self.validation_errors.append(f"Invalid property type: {name} ({prop['type']})")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Custom properties validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def get_custom_properties_stats(self) -> Dict[str, int]:
        """
        Get custom properties statistics.
        
        Returns:
            Dictionary with custom properties statistics
        """
        return self.custom_properties_stats.copy()
    
    def get_custom_properties_info(self) -> Dict[str, Any]:
        """
        Get custom properties information.
        
        Returns:
            Dictionary with custom properties information
        """
        return {
            'total_properties': len(self.properties),
            'property_names': list(self.properties.keys()),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.custom_properties_stats.copy()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert custom properties to dictionary.
        
        Returns:
            Dictionary with all custom properties
        """
        return {
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy(),
            'custom_properties_stats': self.custom_properties_stats.copy()
        }
    
    def get_custom_properties_summary(self) -> Dict[str, Any]:
        """
        Get custom properties summary.
        
        Returns:
            Dictionary with custom properties summary
        """
        return {
            'total_properties': len(self.properties),
            'property_names': list(self.properties.keys()),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.custom_properties_stats.copy()
        }
    
    def _update_stats(self) -> None:
        """Update custom properties statistics."""
        self.custom_properties_stats['total_properties'] = len(self.properties)
        
        # Count property types
        string_count = 0
        numeric_count = 0
        boolean_count = 0
        date_count = 0
        other_count = 0
        
        for prop in self.properties.values():
            if isinstance(prop, dict) and 'type' in prop:
                prop_type = prop['type']
                if prop_type == "string":
                    string_count += 1
                elif prop_type == "number":
                    numeric_count += 1
                elif prop_type == "boolean":
                    boolean_count += 1
                elif prop_type == "date":
                    date_count += 1
                else:
                    other_count += 1
        
        self.custom_properties_stats['string_properties'] = string_count
        self.custom_properties_stats['numeric_properties'] = numeric_count
        self.custom_properties_stats['boolean_properties'] = boolean_count
        self.custom_properties_stats['date_properties'] = date_count
        self.custom_properties_stats['other_properties'] = other_count
