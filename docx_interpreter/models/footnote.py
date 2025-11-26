"""
Footnote model for DOCX documents.

Handles footnote functionality, properties, content, validation, and numbering.
"""

from typing import Dict, Any, Optional, List, List
from .base import Models
import logging

logger = logging.getLogger(__name__)

class Footnote(Models):
    """
    Represents a footnote in the document.
    
    Handles footnote functionality, properties, content, and validation.
    """
    
    def __init__(self, footnote_id: str = "", footnote_type: str = "normal", 
                 content: str = "", properties: Dict[str, Any] = None):
        """
        Initialize footnote.
        
        Args:
            footnote_id: Footnote identifier
            footnote_type: Type of footnote (normal, separator, continuation)
            content: Footnote content
            properties: Footnote properties
        """
        super().__init__()
        self.footnote_id = footnote_id
        self.footnote_type = footnote_type
        self.content = content
        self.properties = properties or {}
        self.validation_errors = []
        
        logger.debug(f"Footnote initialized: {footnote_id}")
    
    def set_footnote_id(self, footnote_id: str) -> None:
        """
        Set footnote ID.
        
        Args:
            footnote_id: Footnote identifier
        """
        if not footnote_id or not isinstance(footnote_id, str):
            raise ValueError("Footnote ID must be a non-empty string")
        
        self.footnote_id = footnote_id
        logger.debug(f"Footnote ID set to: {footnote_id}")
    
    def set_footnote_type(self, footnote_type: str) -> None:
        """
        Set footnote type.
        
        Args:
            footnote_type: Type of footnote
        """
        if not footnote_type or not isinstance(footnote_type, str):
            raise ValueError("Footnote type must be a non-empty string")
        
        self.footnote_type = footnote_type
        logger.debug(f"Footnote type set to: {footnote_type}")
    
    def set_content(self, content: str) -> None:
        """
        Set footnote content.
        
        Args:
            content: Footnote content
        """
        if not isinstance(content, str):
            raise ValueError("Footnote content must be a string")
        
        self.content = content
        logger.debug(f"Footnote content set: {len(content)} characters")
    
    def get_footnote_id(self) -> str:
        """
        Get footnote ID.
        
        Returns:
            Footnote identifier
        """
        return self.footnote_id
    
    def get_content(self) -> str:
        """
        Get footnote content.
        
        Returns:
            Footnote content
        """
        return self.content
    
    def get_footnote_type(self) -> str:
        """
        Get footnote type.
        
        Returns:
            Footnote type
        """
        return self.footnote_type
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set footnote property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Footnote property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get footnote property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate footnote.
        
        Returns:
            True if footnote is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate footnote ID
        if not self.footnote_id:
            self.validation_errors.append("Footnote ID is required")
        
        # Validate footnote type
        if not self.footnote_type:
            self.validation_errors.append("Footnote type is required")
        
        # Validate content
        if not self.content:
            self.validation_errors.append("Footnote content is required")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Footnote properties must be a dictionary")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Footnote validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert footnote to dictionary.
        
        Returns:
            Dictionary representation of footnote
        """
        return {
            'type': 'footnote',
            'footnote_id': self.footnote_id,
            'footnote_type': self.footnote_type,
            'content': self.content,
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load footnote from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.footnote_id = data.get('footnote_id', '')
        self.footnote_type = data.get('footnote_type', 'normal')
        self.content = data.get('content', '')
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"Footnote loaded from dictionary: {self.footnote_id}")
    
    def get_footnote_info(self) -> Dict[str, Any]:
        """
        Get footnote information.
        
        Returns:
            Dictionary with footnote information
        """
        return {
            'footnote_id': self.footnote_id,
            'footnote_type': self.footnote_type,
            'content_length': len(self.content),
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_content(self) -> None:
        """Clear footnote content."""
        self.content = ""
        logger.debug("Footnote content cleared")
    
    def clear_properties(self) -> None:
        """Clear all footnote properties."""
        self.properties.clear()
        logger.debug("Footnote properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if footnote has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove footnote property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Footnote property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if footnote is empty.
        
        Returns:
            True if footnote has no content, False otherwise
        """
        return not self.content.strip()
    
    def get_length(self) -> int:
        """
        Get footnote content length.
        
        Returns:
            Length of footnote content
        """
        return len(self.content)


class Endnote(Models):
    """
    Represents an endnote in the document.
    
    Handles endnote functionality, properties, content, and validation.
    """
    
    def __init__(self, endnote_id: str = "", content: str = "", 
                 properties: Dict[str, Any] = None):
        """
        Initialize endnote.
        
        Args:
            endnote_id: Endnote identifier
            content: Endnote content
            properties: Endnote properties
        """
        super().__init__()
        self.endnote_id = endnote_id
        self.content = content
        self.properties = properties or {}
        self.validation_errors = []
        
        logger.debug(f"Endnote initialized: {endnote_id}")
    
    def set_endnote_id(self, endnote_id: str) -> None:
        """
        Set endnote ID.
        
        Args:
            endnote_id: Endnote identifier
        """
        if not endnote_id or not isinstance(endnote_id, str):
            raise ValueError("Endnote ID must be a non-empty string")
        
        self.endnote_id = endnote_id
        logger.debug(f"Endnote ID set to: {endnote_id}")
    
    def set_content(self, content: str) -> None:
        """
        Set endnote content.
        
        Args:
            content: Endnote content
        """
        if not isinstance(content, str):
            raise ValueError("Endnote content must be a string")
        
        self.content = content
        logger.debug(f"Endnote content set: {len(content)} characters")
    
    def get_endnote_id(self) -> str:
        """
        Get endnote ID.
        
        Returns:
            Endnote identifier
        """
        return self.endnote_id
    
    def get_content(self) -> str:
        """
        Get endnote content.
        
        Returns:
            Endnote content
        """
        return self.content
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set endnote property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Endnote property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get endnote property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate endnote.
        
        Returns:
            True if endnote is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate endnote ID
        if not self.endnote_id:
            self.validation_errors.append("Endnote ID is required")
        
        # Validate content
        if not self.content:
            self.validation_errors.append("Endnote content is required")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Endnote properties must be a dictionary")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Endnote validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert endnote to dictionary.
        
        Returns:
            Dictionary representation of endnote
        """
        return {
            'type': 'endnote',
            'endnote_id': self.endnote_id,
            'content': self.content,
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load endnote from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.endnote_id = data.get('endnote_id', '')
        self.content = data.get('content', '')
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"Endnote loaded from dictionary: {self.endnote_id}")
    
    def get_endnote_info(self) -> Dict[str, Any]:
        """
        Get endnote information.
        
        Returns:
            Dictionary with endnote information
        """
        return {
            'endnote_id': self.endnote_id,
            'content_length': len(self.content),
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_content(self) -> None:
        """Clear endnote content."""
        self.content = ""
        logger.debug("Endnote content cleared")
    
    def clear_properties(self) -> None:
        """Clear all endnote properties."""
        self.properties.clear()
        logger.debug("Endnote properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if endnote has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove endnote property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Endnote property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if endnote is empty.
        
        Returns:
            True if endnote has no content, False otherwise
        """
        return not self.content.strip()
    
    def get_length(self) -> int:
        """
        Get endnote content length.
        
        Returns:
            Length of endnote content
        """
        return len(self.content)
