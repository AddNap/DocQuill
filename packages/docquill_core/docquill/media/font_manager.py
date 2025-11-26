"""
Font manager for DOCX documents.

Handles font manager functionality, font management, embedded font handling, font validation, and font access.
"""

from typing import Dict, Any, Optional, List, Tuple
import hashlib
import struct
import logging

logger = logging.getLogger(__name__)

class FontManager:
    """
    Manages embedded fonts.
    
    Handles font manager functionality, font management, embedded font handling, and font validation.
    """
    
    def __init__(self):
        """
        Initialize font manager.
        
        Sets up font management, embedded font handling, and font validation.
        """
        self.embedded_fonts = {}
        self.font_metadata = {}
        self.font_stats = {
            'total_fonts': 0,
            'valid_fonts': 0,
            'invalid_fonts': 0,
            'total_size': 0
        }
        
        # Font format signatures
        self.font_signatures = {
            'ttf': [b'OTTO', b'\x00\x01\x00\x00'],
            'otf': [b'OTTO'],
            'woff': [b'wOFF'],
            'woff2': [b'wOF2'],
            'eot': [b'\x00\x00\x01\x00']
        }
        
        logger.debug("FontManager initialized")
    
    def add_embedded_font(self, font_id: str, font_data: bytes, metadata: Dict[str, Any] = None) -> bool:
        """
        Add embedded font.
        
        Args:
            font_id: Font identifier
            font_data: Font binary data
            metadata: Font metadata
            
        Returns:
            True if font was added successfully, False otherwise
        """
        if not font_id or not isinstance(font_id, str):
            raise ValueError("Font ID must be a non-empty string")
        
        if not isinstance(font_data, bytes):
            raise ValueError("Font data must be bytes")
        
        try:
            # Validate font data
            if not self.validate_font(font_data):
                self.font_stats['invalid_fonts'] += 1
                logger.warning(f"Invalid font data for: {font_id}")
                return False
            
            # Calculate font hash
            font_hash = hashlib.md5(font_data).hexdigest()
            
            # Store font data
            self.embedded_fonts[font_id] = {
                'data': font_data,
                'hash': font_hash,
                'size': len(font_data),
                'format': self._detect_font_format(font_data)
            }
            
            # Store metadata
            if metadata:
                self.font_metadata[font_id] = metadata.copy()
            else:
                self.font_metadata[font_id] = self._extract_font_metadata(font_data)
            
            # Update stats
            self.font_stats['total_fonts'] += 1
            self.font_stats['valid_fonts'] += 1
            self.font_stats['total_size'] += len(font_data)
            
            logger.debug(f"Embedded font added: {font_id}, size={len(font_data)} bytes")
            return True
            
        except Exception as e:
            self.font_stats['invalid_fonts'] += 1
            logger.error(f"Failed to add embedded font {font_id}: {e}")
            return False
    
    def get_embedded_font(self, font_id: str) -> Optional[bytes]:
        """
        Get embedded font by ID.
        
        Args:
            font_id: Font identifier
            
        Returns:
            Font binary data or None if not found
        """
        if not font_id or not isinstance(font_id, str):
            raise ValueError("Font ID must be a non-empty string")
        
        if font_id not in self.embedded_fonts:
            logger.debug(f"Font not found: {font_id}")
            return None
        
        logger.debug(f"Font retrieved: {font_id}")
        return self.embedded_fonts[font_id]['data']
    
    def get_all_embedded_fonts(self) -> List[str]:
        """
        Get all embedded fonts.
        
        Returns:
            List of font IDs
        """
        return list(self.embedded_fonts.keys())
    
    def validate_font(self, font_data: bytes) -> bool:
        """
        Validate font data.
        
        Args:
            font_data: Font binary data to validate
            
        Returns:
            True if font is valid, False otherwise
        """
        if not isinstance(font_data, bytes):
            return False
        
        if len(font_data) < 4:
            return False
        
        try:
            # Check for common font signatures
            for format_type, signatures in self.font_signatures.items():
                for signature in signatures:
                    if font_data.startswith(signature):
                        logger.debug(f"Font format detected: {format_type}")
                        return True
            
            # Check for TTF/OTF table structure
            if self._validate_ttf_structure(font_data):
                return True
            
            logger.debug("Font validation failed: unknown format")
            return False
            
        except Exception as e:
            logger.error(f"Font validation error: {e}")
            return False
    
    def get_font_metadata(self, font_id: str) -> Optional[Dict[str, Any]]:
        """
        Get font metadata.
        
        Args:
            font_id: Font identifier
            
        Returns:
            Font metadata or None if not found
        """
        if not font_id or not isinstance(font_id, str):
            raise ValueError("Font ID must be a non-empty string")
        
        if font_id not in self.font_metadata:
            logger.debug(f"Font metadata not found: {font_id}")
            return None
        
        return self.font_metadata[font_id].copy()
    
    def get_font_info(self, font_id: str) -> Optional[Dict[str, Any]]:
        """
        Get font information.
        
        Args:
            font_id: Font identifier
            
        Returns:
            Font information or None if not found
        """
        if font_id not in self.embedded_fonts:
            return None
        
        font_data = self.embedded_fonts[font_id]
        metadata = self.font_metadata.get(font_id, {})
        
        return {
            'font_id': font_id,
            'size': font_data['size'],
            'format': font_data['format'],
            'hash': font_data['hash'],
            'metadata': metadata.copy()
        }
    
    def remove_font(self, font_id: str) -> bool:
        """
        Remove embedded font.
        
        Args:
            font_id: Font identifier
            
        Returns:
            True if font was removed, False if not found
        """
        if font_id not in self.embedded_fonts:
            return False
        
        # Update stats
        font_size = self.embedded_fonts[font_id]['size']
        self.font_stats['total_fonts'] -= 1
        self.font_stats['valid_fonts'] -= 1
        self.font_stats['total_size'] -= font_size
        
        # Remove font data and metadata
        del self.embedded_fonts[font_id]
        if font_id in self.font_metadata:
            del self.font_metadata[font_id]
        
        logger.debug(f"Font removed: {font_id}")
        return True
    
    def get_font_stats(self) -> Dict[str, Any]:
        """
        Get font statistics.
        
        Returns:
            Dictionary with font statistics
        """
        return self.font_stats.copy()
    
    def clear_fonts(self) -> None:
        """Clear all embedded fonts."""
        self.embedded_fonts.clear()
        self.font_metadata.clear()
        self.font_stats = {
            'total_fonts': 0,
            'valid_fonts': 0,
            'invalid_fonts': 0,
            'total_size': 0
        }
        logger.debug("All fonts cleared")
    
    def get_fonts_by_format(self, format_type: str) -> List[str]:
        """
        Get fonts by format.
        
        Args:
            format_type: Font format type
            
        Returns:
            List of font IDs with specified format
        """
        if not format_type or not isinstance(format_type, str):
            raise ValueError("Format type must be a non-empty string")
        
        fonts = []
        for font_id, font_data in self.embedded_fonts.items():
            if font_data['format'] == format_type:
                fonts.append(font_id)
        
        return fonts
    
    def get_fonts_by_size(self, min_size: int = 0, max_size: int = None) -> List[str]:
        """
        Get fonts by size range.
        
        Args:
            min_size: Minimum font size
            max_size: Maximum font size (None for no limit)
            
        Returns:
            List of font IDs within size range
        """
        if not isinstance(min_size, int) or min_size < 0:
            raise ValueError("Min size must be a non-negative integer")
        
        if max_size is not None and (not isinstance(max_size, int) or max_size < min_size):
            raise ValueError("Max size must be an integer >= min_size")
        
        fonts = []
        for font_id, font_data in self.embedded_fonts.items():
            size = font_data['size']
            if size >= min_size and (max_size is None or size <= max_size):
                fonts.append(font_id)
        
        return fonts
    
    def _detect_font_format(self, font_data: bytes) -> str:
        """
        Detect font format from data.
        
        Args:
            font_data: Font binary data
            
        Returns:
            Detected format type
        """
        for format_type, signatures in self.font_signatures.items():
            for signature in signatures:
                if font_data.startswith(signature):
                    return format_type
        
        # Check for TTF/OTF table structure
        if self._validate_ttf_structure(font_data):
            return 'ttf'
        
        return 'unknown'
    
    def _validate_ttf_structure(self, font_data: bytes) -> bool:
        """
        Validate TTF/OTF table structure.
        
        Args:
            font_data: Font binary data
            
        Returns:
            True if TTF structure is valid, False otherwise
        """
        try:
            if len(font_data) < 12:
                return False
            
            # Check for TTF/OTF table count
            table_count = struct.unpack('>H', font_data[4:6])[0]
            if table_count < 1 or table_count > 100:
                return False
            
            # Check for reasonable table structure
            header_size = 12 + (table_count * 16)
            if len(font_data) < header_size:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _extract_font_metadata(self, font_data: bytes) -> Dict[str, Any]:
        """
        Extract font metadata from data.
        
        Args:
            font_data: Font binary data
            
        Returns:
            Font metadata dictionary
        """
        metadata = {
            'format': self._detect_font_format(font_data),
            'size': len(font_data),
            'hash': hashlib.md5(font_data).hexdigest()
        }
        
        try:
            # Try to extract TTF/OTF metadata
            if metadata['format'] in ['ttf', 'otf']:
                ttf_metadata = self._extract_ttf_metadata(font_data)
                metadata.update(ttf_metadata)
        except Exception as e:
            logger.warning(f"Failed to extract TTF metadata: {e}")
        
        return metadata
    
    def _extract_ttf_metadata(self, font_data: bytes) -> Dict[str, Any]:
        """
        Extract TTF/OTF metadata.
        
        Args:
            font_data: Font binary data
            
        Returns:
            TTF metadata dictionary
        """
        metadata = {}
        
        try:
            # This is a simplified TTF metadata extraction
            # In a real implementation, this would parse the TTF tables
            metadata['is_ttf'] = True
            metadata['table_count'] = struct.unpack('>H', font_data[4:6])[0] if len(font_data) > 6 else 0
            
        except Exception as e:
            logger.warning(f"TTF metadata extraction failed: {e}")
        
        return metadata
    
    def get_font_hash(self, font_id: str) -> Optional[str]:
        """
        Get font data hash.
        
        Args:
            font_id: Font identifier
            
        Returns:
            Font hash or None if not found
        """
        if font_id in self.embedded_fonts:
            return self.embedded_fonts[font_id]['hash']
        return None
    
    def verify_font_integrity(self, font_id: str) -> bool:
        """
        Verify font data integrity.
        
        Args:
            font_id: Font identifier
            
        Returns:
            True if font integrity is valid, False otherwise
        """
        if font_id not in self.embedded_fonts:
            return False
        
        font_data = self.embedded_fonts[font_id]['data']
        current_hash = hashlib.md5(font_data).hexdigest()
        stored_hash = self.embedded_fonts[font_id]['hash']
        
        return current_hash == stored_hash
    
    def get_fonts_info(self) -> Dict[str, Any]:
        """
        Get information about all fonts.
        
        Returns:
            Dictionary with fonts information
        """
        return {
            'total_fonts': len(self.embedded_fonts),
            'total_size': self.font_stats['total_size'],
            'formats': self._get_format_distribution(),
            'stats': self.font_stats.copy()
        }
    
    def _get_format_distribution(self) -> Dict[str, int]:
        """
        Get format distribution.
        
        Returns:
            Dictionary with format counts
        """
        distribution = {}
        for font_data in self.embedded_fonts.values():
            format_type = font_data['format']
            distribution[format_type] = distribution.get(format_type, 0) + 1
        
        return distribution
