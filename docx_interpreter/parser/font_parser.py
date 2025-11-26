"""
Font parser for DOCX documents.

Handles embedded font parsing, font metadata parsing, and validation.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FontParser:
    """
    Parser for embedded fonts.
    
    Handles font parsing, font metadata parsing, and validation.
    """
    
    def __init__(self, package_reader):
        """
        Initialize font parser.
        
        Args:
            package_reader: PackageReader instance for accessing font files
        """
        self.package_reader = package_reader
        self.fonts = {}
        self.font_info = {}
        
        # Parse fonts
        self._parse_fonts()
        
        logger.debug("Font parser initialized")
    
    def parse_embedded_fonts(self) -> Dict[str, Any]:
        """
        Parse embedded fonts.
        
        Returns:
            Dictionary of parsed fonts
        """
        return {
            'fonts': self.fonts.copy(),
            'info': self.font_info.copy()
        }
    
    def parse_font_file(self, font_path: str) -> Dict[str, Any]:
        """
        Parse individual font file.
        
        Args:
            font_path: Path to font file
            
        Returns:
            Dictionary of parsed font content
        """
        try:
            font_data = self.package_reader.get_binary_content(font_path)
            if font_data:
                return self._parse_font_data(font_data, font_path)
            else:
                logger.warning(f"No font data found for: {font_path}")
                return {'type': 'font', 'path': font_path, 'error': 'No data found'}
        except Exception as e:
            logger.error(f"Failed to parse font file {font_path}: {e}")
            return {'type': 'font', 'path': font_path, 'error': str(e)}
    
    def get_font_metadata(self, font_data: bytes) -> Dict[str, Any]:
        """
        Get font metadata.
        
        Args:
            font_data: Font binary data
            
        Returns:
            Dictionary of font metadata
        """
        metadata = {
            'type': 'font_metadata',
            'size': len(font_data),
            'format': 'unknown',
            'properties': {}
        }
        
        # Basic font format detection
        if font_data.startswith(b'OTTO'):
            metadata['format'] = 'otf'
        elif font_data.startswith(b'\x00\x01\x00\x00'):
            metadata['format'] = 'ttf'
        elif font_data.startswith(b'wOFF'):
            metadata['format'] = 'woff'
        elif font_data.startswith(b'wOF2'):
            metadata['format'] = 'woff2'
        else:
            metadata['format'] = 'unknown'
        
        # Basic validation
        metadata['is_valid'] = self.validate_font(font_data)
        
        return metadata
    
    def validate_font(self, font_data: bytes) -> bool:
        """
        Validate font data.
        
        Args:
            font_data: Font binary data
            
        Returns:
            True if font is valid, False otherwise
        """
        if not font_data:
            return False
        
        # Check minimum size
        if len(font_data) < 100:
            return False
        
        # Check for common font signatures
        valid_signatures = [
            b'OTTO',  # OTF
            b'\x00\x01\x00\x00',  # TTF
            b'wOFF',  # WOFF
            b'wOF2',  # WOFF2
            b'ttcf',  # TTC
            b'fvar',  # Variable font
        ]
        
        for signature in valid_signatures:
            if font_data.startswith(signature):
                return True
        
        return False
    
    def get_fonts(self) -> Dict[str, Any]:
        """
        Get all fonts.
        
        Returns:
            Dictionary of fonts
        """
        return self.fonts.copy()
    
    def get_font(self, font_name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific font.
        
        Args:
            font_name: Font name
            
        Returns:
            Font content or None if not found
        """
        return self.fonts.get(font_name)
    
    def get_font_info(self) -> Dict[str, Any]:
        """
        Get font information.
        
        Returns:
            Dictionary with font metadata
        """
        return self.font_info.copy()
    
    def get_fonts_by_format(self, format_type: str) -> List[Dict[str, Any]]:
        """
        Get fonts by format.
        
        Args:
            format_type: Font format to filter by
            
        Returns:
            List of fonts with matching format
        """
        matching_fonts = []
        for font_name, font_content in self.fonts.items():
            if font_content.get('format') == format_type:
                matching_fonts.append(font_content)
        return matching_fonts
    
    def get_fonts_by_size(self, min_size: int = 0, max_size: int = None) -> List[Dict[str, Any]]:
        """
        Get fonts by size range.
        
        Args:
            min_size: Minimum font size
            max_size: Maximum font size (None for no limit)
            
        Returns:
            List of fonts within size range
        """
        matching_fonts = []
        for font_name, font_content in self.fonts.items():
            font_size = font_content.get('size', 0)
            if font_size >= min_size and (max_size is None or font_size <= max_size):
                matching_fonts.append(font_content)
        return matching_fonts
    
    def _parse_fonts(self) -> None:
        """Parse fonts from the document."""
        try:
            # Find font files in the package
            font_files = self._discover_font_files()
            
            for font_path in font_files:
                try:
                    font_content = self.parse_font_file(font_path)
                    font_name = Path(font_path).stem
                    self.fonts[font_name] = font_content
                except Exception as e:
                    logger.warning(f"Failed to parse font {font_path}: {e}")
            
            # Update info
            self.font_info = {
                'total_fonts': len(self.fonts),
                'font_names': list(self.fonts.keys()),
                'font_formats': list(set(font.get('format', 'unknown') for font in self.fonts.values())),
                'total_size': sum(font.get('size', 0) for font in self.fonts.values())
            }
            
            logger.info(f"Parsed {len(self.fonts)} fonts")
            
        except Exception as e:
            logger.error(f"Failed to parse fonts: {e}")
    
    def _discover_font_files(self) -> List[str]:
        """Discover font files in the package."""
        font_files = []
        
        # Common font file patterns
        font_patterns = [
            'word/fonts/',
            'word/media/fonts/',
            'word/embeddings/',
            'word/objects/'
        ]
        
        for pattern in font_patterns:
            try:
                # This would need to be implemented based on the actual package structure
                # For now, we'll try to find font files in common locations
                pass
            except Exception:
                continue
        
        return font_files
    
    def _parse_font_data(self, font_data: bytes, font_path: str) -> Dict[str, Any]:
        """Parse font data."""
        font = {
            'type': 'font',
            'path': font_path,
            'size': len(font_data),
            'format': 'unknown',
            'metadata': {},
            'properties': {}
        }
        
        # Get font metadata
        font['metadata'] = self.get_font_metadata(font_data)
        font['format'] = font['metadata'].get('format', 'unknown')
        font['is_valid'] = font['metadata'].get('is_valid', False)
        
        return font
    
    def clear_fonts(self) -> None:
        """Clear all fonts."""
        self.fonts.clear()
        self.font_info.clear()
        logger.debug("Fonts cleared")
