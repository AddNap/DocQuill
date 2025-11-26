"""
Metadata for DOCX documents.

Handles metadata functionality, metadata aggregation, metadata serialization, metadata validation, and metadata access.
"""

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class Metadata:
    """
    Represents document metadata and properties.
    
    Handles metadata functionality, metadata aggregation, metadata serialization, and metadata validation.
    """
    
    def __init__(self, core_properties: Optional[Dict[str, Any]] = None, 
                 app_properties: Optional[Dict[str, Any]] = None, 
                 custom_properties: Optional[Dict[str, Any]] = None):
        """
        Initialize metadata.
        
        Args:
            core_properties: Core properties dictionary
            app_properties: App properties dictionary
            custom_properties: Custom properties dictionary
        """
        self.core_properties = core_properties or {}
        self.app_properties = app_properties or {}
        self.custom_properties = custom_properties or {}
        self.validation_errors = []
        self.metadata_stats = {
            'core_properties': 0,
            'app_properties': 0,
            'custom_properties': 0,
            'total_properties': 0
        }
        
        # Initialize with default metadata if not provided
        if not core_properties:
            self._initialize_default_core_properties()
        if not app_properties:
            self._initialize_default_app_properties()
        if not custom_properties:
            self._initialize_default_custom_properties()
        
        # Update stats
        self._update_stats()
        
        logger.debug("Metadata initialized")
    
    def set_core_properties(self, core_properties: Dict[str, Any]) -> None:
        """
        Set core properties.
        
        Args:
            core_properties: Core properties dictionary
        """
        if not isinstance(core_properties, dict):
            raise ValueError("Core properties must be a dictionary")
        
        # Validate core properties
        if not self._validate_core_properties(core_properties):
            raise ValueError("Invalid core properties")
        
        self.core_properties = core_properties.copy()
        self._update_stats()
        
        logger.debug(f"Core properties set: {len(core_properties)} properties")
    
    def set_app_properties(self, app_properties: Dict[str, Any]) -> None:
        """
        Set application properties.
        
        Args:
            app_properties: App properties dictionary
        """
        if not isinstance(app_properties, dict):
            raise ValueError("App properties must be a dictionary")
        
        # Validate app properties
        if not self._validate_app_properties(app_properties):
            raise ValueError("Invalid app properties")
        
        self.app_properties = app_properties.copy()
        self._update_stats()
        
        logger.debug(f"App properties set: {len(app_properties)} properties")
    
    def set_custom_properties(self, custom_properties: Dict[str, Any]) -> None:
        """
        Set custom properties.
        
        Args:
            custom_properties: Custom properties dictionary
        """
        if not isinstance(custom_properties, dict):
            raise ValueError("Custom properties must be a dictionary")
        
        # Validate custom properties
        if not self._validate_custom_properties(custom_properties):
            raise ValueError("Invalid custom properties")
        
        self.custom_properties = custom_properties.copy()
        self._update_stats()
        
        logger.debug(f"Custom properties set: {len(custom_properties)} properties")
    
    def get_title(self) -> Optional[str]:
        """
        Get document title.
        
        Returns:
            Document title or None if not found
        """
        return self.core_properties.get('title')
    
    def get_author(self) -> Optional[str]:
        """
        Get document author.
        
        Returns:
            Document author or None if not found
        """
        return self.core_properties.get('creator')
    
    def get_created_date(self) -> Optional[datetime]:
        """
        Get creation date.
        
        Returns:
            Creation date or None if not found
        """
        return self.core_properties.get('created')
    
    def get_modified_date(self) -> Optional[datetime]:
        """
        Get modified date.
        
        Returns:
            Modified date or None if not found
        """
        return self.core_properties.get('modified')
    
    def get_subject(self) -> Optional[str]:
        """
        Get document subject.
        
        Returns:
            Document subject or None if not found
        """
        return self.core_properties.get('subject')
    
    def get_description(self) -> Optional[str]:
        """
        Get document description.
        
        Returns:
            Document description or None if not found
        """
        return self.core_properties.get('description')
    
    def get_keywords(self) -> Optional[str]:
        """
        Get document keywords.
        
        Returns:
            Document keywords or None if not found
        """
        return self.core_properties.get('keywords')
    
    def get_category(self) -> Optional[str]:
        """
        Get document category.
        
        Returns:
            Document category or None if not found
        """
        return self.core_properties.get('category')
    
    def get_version(self) -> Optional[str]:
        """
        Get document version.
        
        Returns:
            Document version or None if not found
        """
        return self.core_properties.get('version')
    
    def get_language(self) -> Optional[str]:
        """
        Get document language.
        
        Returns:
            Document language or None if not found
        """
        return self.core_properties.get('language')
    
    def get_application(self) -> Optional[str]:
        """
        Get application name.
        
        Returns:
            Application name or None if not found
        """
        return self.app_properties.get('application')
    
    def get_app_version(self) -> Optional[str]:
        """
        Get application version.
        
        Returns:
            Application version or None if not found
        """
        return self.app_properties.get('app_version')
    
    def get_company(self) -> Optional[str]:
        """
        Get company name.
        
        Returns:
            Company name or None if not found
        """
        return self.app_properties.get('company')
    
    def get_manager(self) -> Optional[str]:
        """
        Get manager name.
        
        Returns:
            Manager name or None if not found
        """
        return self.app_properties.get('manager')
    
    def get_security(self) -> Optional[str]:
        """
        Get security level.
        
        Returns:
            Security level or None if not found
        """
        return self.app_properties.get('security')
    
    def get_template(self) -> Optional[str]:
        """
        Get template name.
        
        Returns:
            Template name or None if not found
        """
        return self.app_properties.get('template')
    
    def get_total_time(self) -> Optional[str]:
        """
        Get total editing time.
        
        Returns:
            Total editing time or None if not found
        """
        return self.app_properties.get('total_time')
    
    def get_pages(self) -> Optional[str]:
        """
        Get page count.
        
        Returns:
            Page count or None if not found
        """
        return self.app_properties.get('pages')
    
    def get_words(self) -> Optional[str]:
        """
        Get word count.
        
        Returns:
            Word count or None if not found
        """
        return self.app_properties.get('words')
    
    def get_characters(self) -> Optional[str]:
        """
        Get character count.
        
        Returns:
            Character count or None if not found
        """
        return self.app_properties.get('characters')
    
    def get_characters_with_spaces(self) -> Optional[str]:
        """
        Get character count with spaces.
        
        Returns:
            Character count with spaces or None if not found
        """
        return self.app_properties.get('characters_with_spaces')
    
    def get_lines(self) -> Optional[str]:
        """
        Get line count.
        
        Returns:
            Line count or None if not found
        """
        return self.app_properties.get('lines')
    
    def get_paragraphs(self) -> Optional[str]:
        """
        Get paragraph count.
        
        Returns:
            Paragraph count or None if not found
        """
        return self.app_properties.get('paragraphs')
    
    def get_custom_property(self, property_name: str) -> Optional[Any]:
        """
        Get custom property by name.
        
        Args:
            property_name: Custom property name
            
        Returns:
            Custom property value or None if not found
        """
        return self.custom_properties.get(property_name)
    
    def set_custom_property(self, property_name: str, property_value: Any) -> None:
        """
        Set custom property.
        
        Args:
            property_name: Custom property name
            property_value: Custom property value
        """
        if not property_name or not isinstance(property_name, str):
            raise ValueError("Property name must be a non-empty string")
        
        self.custom_properties[property_name] = property_value
        self._update_stats()
        
        logger.debug(f"Custom property set: {property_name} = {property_value}")
    
    def remove_custom_property(self, property_name: str) -> bool:
        """
        Remove custom property.
        
        Args:
            property_name: Custom property name to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if property_name in self.custom_properties:
            del self.custom_properties[property_name]
            self._update_stats()
            logger.debug(f"Custom property removed: {property_name}")
            return True
        return False
    
    def has_custom_property(self, property_name: str) -> bool:
        """
        Check if custom property exists.
        
        Args:
            property_name: Custom property name
            
        Returns:
            True if property exists, False otherwise
        """
        return property_name in self.custom_properties
    
    def get_all_custom_properties(self) -> Dict[str, Any]:
        """
        Get all custom properties.
        
        Returns:
            Dictionary with all custom properties
        """
        return self.custom_properties.copy()
    
    def validate(self) -> bool:
        """
        Validate metadata.
        
        Returns:
            True if metadata is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate core properties
        if not self._validate_core_properties(self.core_properties):
            self.validation_errors.append("Invalid core properties")
        
        # Validate app properties
        if not self._validate_app_properties(self.app_properties):
            self.validation_errors.append("Invalid app properties")
        
        # Validate custom properties
        if not self._validate_custom_properties(self.custom_properties):
            self.validation_errors.append("Invalid custom properties")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Metadata validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def get_metadata_stats(self) -> Dict[str, int]:
        """
        Get metadata statistics.
        
        Returns:
            Dictionary with metadata statistics
        """
        return self.metadata_stats.copy()
    
    def get_metadata_info(self) -> Dict[str, Any]:
        """
        Get metadata information.
        
        Returns:
            Dictionary with metadata information
        """
        return {
            'core_properties_count': len(self.core_properties),
            'app_properties_count': len(self.app_properties),
            'custom_properties_count': len(self.custom_properties),
            'total_properties': self.metadata_stats['total_properties'],
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.metadata_stats.copy()
        }
    
    def clear_metadata(self) -> None:
        """Clear all metadata."""
        self.core_properties.clear()
        self.app_properties.clear()
        self.custom_properties.clear()
        self.validation_errors.clear()
        self.metadata_stats = {
            'core_properties': 0,
            'app_properties': 0,
            'custom_properties': 0,
            'total_properties': 0
        }
        logger.debug("Metadata cleared")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metadata to dictionary.
        
        Returns:
            Dictionary with all metadata
        """
        return {
            'core_properties': self.core_properties.copy(),
            'app_properties': self.app_properties.copy(),
            'custom_properties': self.custom_properties.copy(),
            'validation_errors': self.validation_errors.copy(),
            'metadata_stats': self.metadata_stats.copy()
        }
    
    def _initialize_default_core_properties(self) -> None:
        """Initialize default core properties."""
        self.core_properties = {
            'title': 'Untitled Document',
            'creator': 'Unknown',
            'created': datetime.now(),
            'modified': datetime.now(),
            'subject': '',
            'description': '',
            'keywords': '',
            'category': '',
            'version': '1.0',
            'language': 'en-US'
        }
    
    def _initialize_default_app_properties(self) -> None:
        """Initialize default app properties."""
        self.app_properties = {
            'application': 'Microsoft Word',
            'app_version': '16.0',
            'company': '',
            'manager': '',
            'security': '0',
            'template': 'Normal.dotm',
            'total_time': '0',
            'pages': '1',
            'words': '0',
            'characters': '0',
            'characters_with_spaces': '0',
            'lines': '0',
            'paragraphs': '0'
        }
    
    def _initialize_default_custom_properties(self) -> None:
        """Initialize default custom properties."""
        self.custom_properties = {}
    
    def _update_stats(self) -> None:
        """Update metadata statistics."""
        self.metadata_stats['core_properties'] = len(self.core_properties)
        self.metadata_stats['app_properties'] = len(self.app_properties)
        self.metadata_stats['custom_properties'] = len(self.custom_properties)
        self.metadata_stats['total_properties'] = len(self.core_properties) + len(self.app_properties) + len(self.custom_properties)
    
    def _validate_core_properties(self, core_props: Dict[str, Any]) -> bool:
        """
        Validate core properties.
        
        Args:
            core_props: Core properties to validate
            
        Returns:
            True if core properties are valid, False otherwise
        """
        if not isinstance(core_props, dict):
            return False
        
        # Check for required fields
        required_fields = ['title', 'creator', 'created', 'modified']
        for field in required_fields:
            if field not in core_props:
                return False
        
        return True
    
    def _validate_app_properties(self, app_props: Dict[str, Any]) -> bool:
        """
        Validate app properties.
        
        Args:
            app_props: App properties to validate
            
        Returns:
            True if app properties are valid, False otherwise
        """
        if not isinstance(app_props, dict):
            return False
        
        # Check for required fields
        required_fields = ['application', 'app_version']
        for field in required_fields:
            if field not in app_props:
                return False
        
        return True
    
    def _validate_custom_properties(self, custom_props: Dict[str, Any]) -> bool:
        """
        Validate custom properties.
        
        Args:
            custom_props: Custom properties to validate
            
        Returns:
            True if custom properties are valid, False otherwise
        """
        if not isinstance(custom_props, dict):
            return False
        
        # Custom properties can be empty or contain any key-value pairs
        return True
    
    def get_metadata_summary(self) -> Dict[str, Any]:
        """
        Get metadata summary.
        
        Returns:
            Dictionary with metadata summary
        """
        return {
            'total_properties': self.metadata_stats['total_properties'],
            'core_properties': list(self.core_properties.keys()),
            'app_properties': list(self.app_properties.keys()),
            'custom_properties': list(self.custom_properties.keys()),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.metadata_stats.copy()
        }
