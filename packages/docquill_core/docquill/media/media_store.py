"""
Media store for DOCX documents.

Handles media store functionality, media file management, media caching, media access methods, and media validation.
"""

from typing import Dict, List, Any, Optional, BinaryIO
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MediaStore:
    """
    Stores and manages media files from DOCX documents.
    
    Handles media store functionality, media file management, media caching, and media access.
    """
    
    def __init__(self, package_reader=None):
        """
        Initialize media store.
        
        Args:
            package_reader: Package reader instance
        """
        self.package_reader = package_reader
        self.media_files = {}
        self.media_metadata = {}
        self.media_cache = {}
        self.media_stats = {
            'total_media': 0,
            'images': 0,
            'fonts': 0,
            'other': 0,
            'total_size': 0
        }
        
        logger.debug("MediaStore initialized")
    
    def load_media(self) -> bool:
        """
        Load all media files from package.
        
        Returns:
            True if media loading was successful, False otherwise
        """
        if not self.package_reader:
            logger.warning("No package reader available")
            return False
        
        try:
            # Get media files from package
            media_files = self.package_reader.get_media_files()
            
            for media_file in media_files:
                try:
                    # Load media data
                    media_data = self.package_reader.get_binary_content(media_file)
                    if media_data:
                        # Detect media type
                        media_type = self._detect_media_type(media_data)
                        
                        # Store media file
                        self.media_files[media_file] = {
                            'data': media_data,
                            'type': media_type,
                            'size': len(media_data)
                        }
                        
                        # Update stats
                        self.media_stats['total_media'] += 1
                        self.media_stats['total_size'] += len(media_data)
                        
                        if media_type == 'image':
                            self.media_stats['images'] += 1
                        elif media_type == 'font':
                            self.media_stats['fonts'] += 1
                        else:
                            self.media_stats['other'] += 1
                        
                        logger.debug(f"Media loaded: {media_file}, type={media_type}, size={len(media_data)}")
                
                except Exception as e:
                    logger.error(f"Failed to load media file {media_file}: {e}")
                    continue
            
            logger.info(f"Media loading completed: {self.media_stats['total_media']} files")
            return True
            
        except Exception as e:
            logger.error(f"Media loading failed: {e}")
            return False
    
    def get_image(self, image_id: str) -> Optional[bytes]:
        """
        Get image by ID.
        
        Args:
            image_id: Image identifier
            
        Returns:
            Image binary data or None if not found
        """
        if not image_id or not isinstance(image_id, str):
            raise ValueError("Image ID must be a non-empty string")
        
        if image_id not in self.media_files:
            logger.debug(f"Image not found: {image_id}")
            return None
        
        media_file = self.media_files[image_id]
        if media_file['type'] != 'image':
            logger.warning(f"Media file {image_id} is not an image")
            return None
        
        logger.debug(f"Image retrieved: {image_id}")
        return media_file['data']
    
    def get_images(self) -> List[str]:
        """
        Get all images.
        
        Returns:
            List of image IDs
        """
        images = []
        for media_id, media_file in self.media_files.items():
            if media_file['type'] == 'image':
                images.append(media_id)
        
        logger.debug(f"Found {len(images)} images")
        return images
    
    def get_media_file(self, media_id: str) -> Optional[bytes]:
        """
        Get media file by ID.
        
        Args:
            media_id: Media identifier
            
        Returns:
            Media binary data or None if not found
        """
        if not media_id or not isinstance(media_id, str):
            raise ValueError("Media ID must be a non-empty string")
        
        if media_id not in self.media_files:
            logger.debug(f"Media file not found: {media_id}")
            return None
        
        logger.debug(f"Media file retrieved: {media_id}")
        return self.media_files[media_id]['data']
    
    def add_media(self, media_id: str, media_data: bytes, media_type: str = None) -> bool:
        """
        Add media to store.
        
        Args:
            media_id: Media identifier
            media_data: Media binary data
            media_type: Media type (auto-detected if None)
            
        Returns:
            True if media was added successfully, False otherwise
        """
        if not media_id or not isinstance(media_id, str):
            raise ValueError("Media ID must be a non-empty string")
        
        if not isinstance(media_data, bytes):
            raise ValueError("Media data must be bytes")
        
        try:
            # Detect media type if not provided
            if not media_type:
                media_type = self._detect_media_type(media_data)
            
            # Store media file
            self.media_files[media_id] = {
                'data': media_data,
                'type': media_type,
                'size': len(media_data)
            }
            
            # Update stats
            self.media_stats['total_media'] += 1
            self.media_stats['total_size'] += len(media_data)
            
            if media_type == 'image':
                self.media_stats['images'] += 1
            elif media_type == 'font':
                self.media_stats['fonts'] += 1
            else:
                self.media_stats['other'] += 1
            
            logger.debug(f"Media added: {media_id}, type={media_type}, size={len(media_data)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add media {media_id}: {e}")
            return False
    
    def get_media_info(self, media_id: str) -> Optional[Dict[str, Any]]:
        """
        Get media file information.
        
        Args:
            media_id: Media identifier
            
        Returns:
            Media information or None if not found
        """
        if media_id not in self.media_files:
            return None
        
        media_file = self.media_files[media_id]
        return {
            'media_id': media_id,
            'type': media_file['type'],
            'size': media_file['size'],
            'data': media_file['data']
        }
    
    def get_media_stats(self) -> Dict[str, Any]:
        """
        Get media statistics.
        
        Returns:
            Dictionary with media statistics
        """
        return self.media_stats.copy()
    
    def get_media_by_type(self, media_type: str) -> List[str]:
        """
        Get media files by type.
        
        Args:
            media_type: Media type to filter by
            
        Returns:
            List of media IDs with specified type
        """
        if not media_type or not isinstance(media_type, str):
            raise ValueError("Media type must be a non-empty string")
        
        media_files = []
        for media_id, media_file in self.media_files.items():
            if media_file['type'] == media_type:
                media_files.append(media_id)
        
        return media_files
    
    def remove_media(self, media_id: str) -> bool:
        """
        Remove media file.
        
        Args:
            media_id: Media identifier
            
        Returns:
            True if media was removed, False if not found
        """
        if media_id not in self.media_files:
            return False
        
        # Update stats
        media_file = self.media_files[media_id]
        media_type = media_file['type']
        media_size = media_file['size']
        
        self.media_stats['total_media'] -= 1
        self.media_stats['total_size'] -= media_size
        
        if media_type == 'image':
            self.media_stats['images'] -= 1
        elif media_type == 'font':
            self.media_stats['fonts'] -= 1
        else:
            self.media_stats['other'] -= 1
        
        # Remove media file
        del self.media_files[media_id]
        
        logger.debug(f"Media removed: {media_id}")
        return True
    
    def clear_media(self) -> None:
        """Clear all media files."""
        self.media_files.clear()
        self.media_metadata.clear()
        self.media_cache.clear()
        self.media_stats = {
            'total_media': 0,
            'images': 0,
            'fonts': 0,
            'other': 0,
            'total_size': 0
        }
        logger.debug("All media cleared")
    
    def get_media_list(self) -> List[str]:
        """
        Get list of all media IDs.
        
        Returns:
            List of media IDs
        """
        return list(self.media_files.keys())
    
    def has_media(self, media_id: str) -> bool:
        """
        Check if media exists.
        
        Args:
            media_id: Media identifier
            
        Returns:
            True if media exists, False otherwise
        """
        return media_id in self.media_files
    
    def get_media_size(self, media_id: str) -> Optional[int]:
        """
        Get media file size.
        
        Args:
            media_id: Media identifier
            
        Returns:
            Media size in bytes or None if not found
        """
        if media_id in self.media_files:
            return self.media_files[media_id]['size']
        return None
    
    def get_media_type(self, media_id: str) -> Optional[str]:
        """
        Get media file type.
        
        Args:
            media_id: Media identifier
            
        Returns:
            Media type or None if not found
        """
        if media_id in self.media_files:
            return self.media_files[media_id]['type']
        return None
    
    def _detect_media_type(self, media_data: bytes) -> str:
        """
        Detect media type from data.
        
        Args:
            media_data: Media binary data
            
        Returns:
            Detected media type
        """
        if not media_data:
            return 'unknown'
        
        # Check for image signatures
        if media_data.startswith(b'\x89PNG'):
            return 'image'
        elif media_data.startswith(b'\xff\xd8\xff'):
            return 'image'
        elif media_data.startswith(b'BM'):
            return 'image'
        elif media_data.startswith(b'GIF87a') or media_data.startswith(b'GIF89a'):
            return 'image'
        
        # Check for font signatures
        elif media_data.startswith(b'OTTO') or media_data.startswith(b'\x00\x01\x00\x00'):
            return 'font'
        elif media_data.startswith(b'wOFF'):
            return 'font'
        elif media_data.startswith(b'wOF2'):
            return 'font'
        
        # Check for other formats
        elif media_data.startswith(b'%PDF'):
            return 'pdf'
        elif media_data.startswith(b'PK'):
            return 'archive'
        
        return 'other'
    
    def get_media_summary(self) -> Dict[str, Any]:
        """
        Get media summary.
        
        Returns:
            Dictionary with media summary
        """
        return {
            'total_media': len(self.media_files),
            'total_size': self.media_stats['total_size'],
            'by_type': {
                'images': self.media_stats['images'],
                'fonts': self.media_stats['fonts'],
                'other': self.media_stats['other']
            },
            'media_files': list(self.media_files.keys())
        }
    
    def validate_media(self, media_id: str) -> bool:
        """
        Validate media file.
        
        Args:
            media_id: Media identifier
            
        Returns:
            True if media is valid, False otherwise
        """
        if media_id not in self.media_files:
            return False
        
        media_file = self.media_files[media_id]
        media_data = media_file['data']
        
        # Basic validation
        if not media_data or len(media_data) == 0:
            return False
        
        # Type-specific validation
        media_type = media_file['type']
        if media_type == 'image':
            return self._validate_image(media_data)
        elif media_type == 'font':
            return self._validate_font(media_data)
        
        return True
    
    def _validate_image(self, image_data: bytes) -> bool:
        """
        Validate image data.
        
        Args:
            image_data: Image binary data
            
        Returns:
            True if image is valid, False otherwise
        """
        try:
            # Check for valid image signatures
            if (image_data.startswith(b'\x89PNG') or 
                image_data.startswith(b'\xff\xd8\xff') or 
                image_data.startswith(b'BM') or 
                image_data.startswith(b'GIF87a') or 
                image_data.startswith(b'GIF89a')):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _validate_font(self, font_data: bytes) -> bool:
        """
        Validate font data.
        
        Args:
            font_data: Font binary data
            
        Returns:
            True if font is valid, False otherwise
        """
        try:
            # Check for valid font signatures
            if (font_data.startswith(b'OTTO') or 
                font_data.startswith(b'\x00\x01\x00\x00') or 
                font_data.startswith(b'wOFF') or 
                font_data.startswith(b'wOF2')):
                return True
            
            return False
            
        except Exception:
            return False
