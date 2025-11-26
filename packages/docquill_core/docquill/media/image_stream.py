"""
Image stream model for DOCX documents.

Handles image stream functionality, properties, management, validation, and access.
"""

from typing import Dict, Any, Optional, BinaryIO, List
import hashlib
import logging

logger = logging.getLogger(__name__)

class ImageStream:
    """
    Represents an image stream (ID, bytes, format).
    
    Handles image stream functionality, properties, management, and validation.
    """
    
    def __init__(self, image_id: str = "", image_data: bytes = b"", 
                 image_format: str = "", metadata: Dict[str, Any] = None):
        """
        Initialize image stream.
        
        Args:
            image_id: Image identifier
            image_data: Image binary data
            image_format: Image format
            metadata: Image metadata
        """
        self.image_id = image_id
        self.image_data = image_data
        self.image_format = image_format
        self.metadata = metadata or {}
        self.validation_errors = []
        
        # Calculate data hash for integrity
        if image_data:
            self.data_hash = hashlib.md5(image_data).hexdigest()
        else:
            self.data_hash = ""
        
        logger.debug(f"ImageStream initialized: {image_id}")
    
    def set_image_id(self, image_id: str) -> None:
        """
        Set image ID.
        
        Args:
            image_id: Image identifier
        """
        if not image_id or not isinstance(image_id, str):
            raise ValueError("Image ID must be a non-empty string")
        
        self.image_id = image_id
        logger.debug(f"Image ID set to: {image_id}")
    
    def set_image_data(self, image_data: bytes) -> None:
        """
        Set image data.
        
        Args:
            image_data: Image binary data
        """
        if not isinstance(image_data, bytes):
            raise ValueError("Image data must be bytes")
        
        self.image_data = image_data
        self.data_hash = hashlib.md5(image_data).hexdigest()
        logger.debug(f"Image data set: {len(image_data)} bytes")
    
    def set_image_format(self, image_format: str) -> None:
        """
        Set image format.
        
        Args:
            image_format: Image format
        """
        if not image_format or not isinstance(image_format, str):
            raise ValueError("Image format must be a non-empty string")
        
        self.image_format = image_format
        logger.debug(f"Image format set to: {image_format}")
    
    def get_image_id(self) -> str:
        """
        Get image ID.
        
        Returns:
            Image identifier
        """
        return self.image_id
    
    def get_image_data(self) -> bytes:
        """
        Get image data.
        
        Returns:
            Image binary data
        """
        return self.image_data
    
    def get_image_format(self) -> str:
        """
        Get image format.
        
        Returns:
            Image format
        """
        return self.image_format
    
    def get_data_size(self) -> int:
        """
        Get image data size.
        
        Returns:
            Image data size in bytes
        """
        return len(self.image_data)
    
    def get_data_hash(self) -> str:
        """
        Get image data hash.
        
        Returns:
            Image data hash
        """
        return self.data_hash
    
    def set_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Set image metadata.
        
        Args:
            metadata: Image metadata
        """
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")
        
        self.metadata = metadata.copy()
        logger.debug(f"Image metadata set: {metadata}")
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get image metadata.
        
        Returns:
            Image metadata
        """
        return self.metadata.copy()
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set image property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.metadata[key] = value
        logger.debug(f"Image property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get image property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.metadata.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate image stream.
        
        Returns:
            True if image stream is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate image ID
        if not self.image_id:
            self.validation_errors.append("Image ID is required")
        
        # Validate image data
        if not self.image_data:
            self.validation_errors.append("Image data is required")
        
        # Validate image format
        if not self.image_format:
            self.validation_errors.append("Image format is required")
        
        # Validate metadata
        if not isinstance(self.metadata, dict):
            self.validation_errors.append("Metadata must be a dictionary")
        
        # Validate data integrity
        if self.image_data and self.data_hash:
            current_hash = hashlib.md5(self.image_data).hexdigest()
            if current_hash != self.data_hash:
                self.validation_errors.append("Image data integrity check failed")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"ImageStream validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert image stream to dictionary.
        
        Returns:
            Dictionary representation of image stream
        """
        return {
            'type': 'image_stream',
            'image_id': self.image_id,
            'image_data': self.image_data,
            'image_format': self.image_format,
            'data_size': len(self.image_data),
            'data_hash': self.data_hash,
            'metadata': self.metadata.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load image stream from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.image_id = data.get('image_id', '')
        self.image_data = data.get('image_data', b'')
        self.image_format = data.get('image_format', '')
        self.data_hash = data.get('data_hash', '')
        self.metadata = data.get('metadata', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"ImageStream loaded from dictionary: {self.image_id}")
    
    def get_image_info(self) -> Dict[str, Any]:
        """
        Get image stream information.
        
        Returns:
            Dictionary with image stream information
        """
        return {
            'image_id': self.image_id,
            'image_format': self.image_format,
            'data_size': len(self.image_data),
            'data_hash': self.data_hash,
            'metadata_count': len(self.metadata),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_data(self) -> None:
        """Clear image data."""
        self.image_data = b""
        self.data_hash = ""
        logger.debug("Image data cleared")
    
    def clear_metadata(self) -> None:
        """Clear image metadata."""
        self.metadata.clear()
        logger.debug("Image metadata cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if image has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.metadata
    
    def remove_property(self, key: str) -> bool:
        """
        Remove image property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.metadata:
            del self.metadata[key]
            logger.debug(f"Image property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if image stream is empty.
        
        Returns:
            True if image stream has no data, False otherwise
        """
        return len(self.image_data) == 0
    
    def get_properties_count(self) -> int:
        """
        Get number of properties.
        
        Returns:
            Number of properties
        """
        return len(self.metadata)
    
    def update_data(self, new_data: bytes) -> None:
        """
        Update image data.
        
        Args:
            new_data: New image data
        """
        if not isinstance(new_data, bytes):
            raise ValueError("Image data must be bytes")
        
        self.image_data = new_data
        self.data_hash = hashlib.md5(new_data).hexdigest()
        logger.debug(f"Image data updated: {len(new_data)} bytes")
    
    def update_format(self, new_format: str) -> None:
        """
        Update image format.
        
        Args:
            new_format: New image format
        """
        if not new_format or not isinstance(new_format, str):
            raise ValueError("Image format must be a non-empty string")
        
        self.image_format = new_format
        logger.debug(f"Image format updated: {new_format}")
    
    def verify_integrity(self) -> bool:
        """
        Verify image data integrity.
        
        Returns:
            True if data integrity is valid, False otherwise
        """
        if not self.image_data or not self.data_hash:
            return False
        
        current_hash = hashlib.md5(self.image_data).hexdigest()
        return current_hash == self.data_hash
    
    def get_stream_info(self) -> Dict[str, Any]:
        """
        Get stream information.
        
        Returns:
            Dictionary with stream information
        """
        return {
            'image_id': self.image_id,
            'image_format': self.image_format,
            'data_size': len(self.image_data),
            'data_hash': self.data_hash,
            'metadata_count': len(self.metadata),
            'is_valid': self.validate(),
            'is_empty': self.is_empty(),
            'integrity_ok': self.verify_integrity()
        }
