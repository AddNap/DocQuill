"""
Numbering models for DOCX documents.

Handles numbering functionality, group support, level support, format support, and inheritance.
"""

from typing import List, Dict, Any, Optional
from .base import Models
import logging

logger = logging.getLogger(__name__)

class NumberingGroup(Models):
    """
    Represents a numbering group (abstract numbering).
    
    Handles numbering group functionality, level management, format support, and inheritance.
    """
    
    def __init__(self, group_id: str = "", levels: List[Dict[str, Any]] = None, 
                 format_type: str = "decimal", properties: Dict[str, Any] = None):
        """
        Initialize numbering group.
        
        Args:
            group_id: Numbering group identifier
            levels: List of numbering levels
            format_type: Default format type
            properties: Group properties
        """
        super().__init__()
        self.group_id = group_id
        self.levels = levels or []
        self.format_type = format_type
        self.properties = properties or {}
        self.validation_errors = []
        
        logger.debug(f"NumberingGroup initialized: {group_id}")
    
    def add_level(self, level: Dict[str, Any]) -> None:
        """
        Add numbering level.
        
        Args:
            level: Numbering level dictionary
        """
        if not isinstance(level, dict):
            raise ValueError("Level must be a dictionary")
        
        self.levels.append(level)
        logger.debug(f"Level added to numbering group: {level.get('level', 'unknown')}")
    
    def set_format(self, format_type: str) -> None:
        """
        Set numbering format.
        
        Args:
            format_type: Format type for numbering
        """
        if not format_type or not isinstance(format_type, str):
            raise ValueError("Format type must be a non-empty string")
        
        self.format_type = format_type
        logger.debug(f"Numbering format set to: {format_type}")
    
    def get_levels(self) -> List[Dict[str, Any]]:
        """
        Get all numbering levels.
        
        Returns:
            List of numbering levels
        """
        return self.levels.copy()
    
    def get_group_id(self) -> str:
        """
        Get group ID.
        
        Returns:
            Group identifier
        """
        return self.group_id
    
    def set_group_id(self, group_id: str) -> None:
        """
        Set group ID.
        
        Args:
            group_id: Group identifier
        """
        if not group_id or not isinstance(group_id, str):
            raise ValueError("Group ID must be a non-empty string")
        
        self.group_id = group_id
        logger.debug(f"Group ID set to: {group_id}")
    
    def get_format_type(self) -> str:
        """
        Get format type.
        
        Returns:
            Format type
        """
        return self.format_type
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set group property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Group property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get group property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate numbering group.
        
        Returns:
            True if group is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate group ID
        if not self.group_id:
            self.validation_errors.append("Group ID is required")
        
        # Validate levels
        if not isinstance(self.levels, list):
            self.validation_errors.append("Levels must be a list")
        
        # Validate format type
        if not self.format_type:
            self.validation_errors.append("Format type is required")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Properties must be a dictionary")
        
        # Validate level structure
        for i, level in enumerate(self.levels):
            if not isinstance(level, dict):
                self.validation_errors.append(f"Level {i} must be a dictionary")
            elif 'level' not in level:
                self.validation_errors.append(f"Level {i} must have a level number")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"NumberingGroup validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert numbering group to dictionary.
        
        Returns:
            Dictionary representation of numbering group
        """
        return {
            'type': 'numbering_group',
            'group_id': self.group_id,
            'levels': self.levels.copy(),
            'format_type': self.format_type,
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load numbering group from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.group_id = data.get('group_id', '')
        self.levels = data.get('levels', [])
        self.format_type = data.get('format_type', 'decimal')
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"NumberingGroup loaded from dictionary: {self.group_id}")
    
    def get_group_info(self) -> Dict[str, Any]:
        """
        Get numbering group information.
        
        Returns:
            Dictionary with numbering group information
        """
        return {
            'group_id': self.group_id,
            'levels_count': len(self.levels),
            'format_type': self.format_type,
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_levels(self) -> None:
        """Clear all numbering levels."""
        self.levels.clear()
        logger.debug("Numbering levels cleared")
    
    def clear_properties(self) -> None:
        """Clear all group properties."""
        self.properties.clear()
        logger.debug("Group properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if group has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove group property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Group property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if group is empty.
        
        Returns:
            True if group has no levels, False otherwise
        """
        return len(self.levels) == 0
    
    def get_levels_count(self) -> int:
        """
        Get number of levels.
        
        Returns:
            Number of levels
        """
        return len(self.levels)
    
    def remove_level(self, index: int) -> bool:
        """
        Remove level from group.
        
        Args:
            index: Index of level to remove
            
        Returns:
            True if level was removed, False if index out of range
        """
        if 0 <= index < len(self.levels):
            removed_level = self.levels.pop(index)
            logger.debug(f"Level removed from group: {removed_level.get('level', 'unknown')}")
            return True
        return False


class NumberingLevel(Models):
    """
    Represents a numbering level.
    
    Handles numbering level functionality, properties, format support, and inheritance.
    """
    
    def __init__(self, level: int = 0, format_type: str = "decimal", 
                 start_value: int = 1, properties: Dict[str, Any] = None):
        """
        Initialize numbering level.
        
        Args:
            level: Level number
            format_type: Format type for this level
            start_value: Starting value for numbering
            properties: Level properties
        """
        super().__init__()
        self.level = level
        self.format_type = format_type
        self.start_value = start_value
        self.properties = properties or {}
        self.validation_errors = []
        
        logger.debug(f"NumberingLevel initialized: level {level}")
    
    def set_level(self, level: int) -> None:
        """
        Set level number.
        
        Args:
            level: Level number
        """
        if not isinstance(level, int) or level < 0:
            raise ValueError("Level must be a non-negative integer")
        
        self.level = level
        logger.debug(f"Level set to: {level}")
    
    def set_format(self, format_type: str) -> None:
        """
        Set level format.
        
        Args:
            format_type: Format type for this level
        """
        if not format_type or not isinstance(format_type, str):
            raise ValueError("Format type must be a non-empty string")
        
        self.format_type = format_type
        logger.debug(f"Level format set to: {format_type}")
    
    def set_start(self, start_value: int) -> None:
        """
        Set start value.
        
        Args:
            start_value: Starting value for numbering
        """
        if not isinstance(start_value, int) or start_value < 1:
            raise ValueError("Start value must be a positive integer")
        
        self.start_value = start_value
        logger.debug(f"Start value set to: {start_value}")
    
    def get_level(self) -> int:
        """
        Get level number.
        
        Returns:
            Level number
        """
        return self.level
    
    def get_format_type(self) -> str:
        """
        Get format type.
        
        Returns:
            Format type
        """
        return self.format_type
    
    def get_start_value(self) -> int:
        """
        Get start value.
        
        Returns:
            Start value
        """
        return self.start_value
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set level property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Level property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get level property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate numbering level.
        
        Returns:
            True if level is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate level
        if not isinstance(self.level, int) or self.level < 0:
            self.validation_errors.append("Level must be a non-negative integer")
        
        # Validate format type
        if not self.format_type:
            self.validation_errors.append("Format type is required")
        
        # Validate start value
        if not isinstance(self.start_value, int) or self.start_value < 1:
            self.validation_errors.append("Start value must be a positive integer")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Properties must be a dictionary")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"NumberingLevel validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert numbering level to dictionary.
        
        Returns:
            Dictionary representation of numbering level
        """
        return {
            'type': 'numbering_level',
            'level': self.level,
            'format_type': self.format_type,
            'start_value': self.start_value,
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load numbering level from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.level = data.get('level', 0)
        self.format_type = data.get('format_type', 'decimal')
        self.start_value = data.get('start_value', 1)
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"NumberingLevel loaded from dictionary: level {self.level}")
    
    def get_level_info(self) -> Dict[str, Any]:
        """
        Get numbering level information.
        
        Returns:
            Dictionary with numbering level information
        """
        return {
            'level': self.level,
            'format_type': self.format_type,
            'start_value': self.start_value,
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_properties(self) -> None:
        """Clear all level properties."""
        self.properties.clear()
        logger.debug("Level properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if level has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove level property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Level property removed: {key}")
            return True
        return False
    
    def get_properties_count(self) -> int:
        """
        Get number of properties.
        
        Returns:
            Number of properties
        """
        return len(self.properties)
    
    def update_level(self, new_level: int) -> None:
        """
        Update level number.
        
        Args:
            new_level: New level number
        """
        if not isinstance(new_level, int) or new_level < 0:
            raise ValueError("Level must be a non-negative integer")
        
        self.level = new_level
        logger.debug(f"Level updated to: {new_level}")
    
    def update_format(self, new_format: str) -> None:
        """
        Update format type.
        
        Args:
            new_format: New format type
        """
        if not new_format or not isinstance(new_format, str):
            raise ValueError("Format type must be a non-empty string")
        
        self.format_type = new_format
        logger.debug(f"Format updated to: {new_format}")
    
    def update_start_value(self, new_start: int) -> None:
        """
        Update start value.
        
        Args:
            new_start: New start value
        """
        if not isinstance(new_start, int) or new_start < 1:
            raise ValueError("Start value must be a positive integer")
        
        self.start_value = new_start
        logger.debug(f"Start value updated to: {new_start}")
