"""
Media cache for DOCX documents.

Handles media cache functionality, caching, management, validation, and optimization.
"""

from typing import Dict, Any, Optional, BinaryIO, List
import hashlib
import time
import logging

logger = logging.getLogger(__name__)

class MediaCache:
    """
    Caches media and their metadata.
    
    Handles media cache functionality, caching, management, and validation.
    """
    
    def __init__(self, max_size: int = 100, max_age: int = 3600):
        """
        Initialize media cache.
        
        Args:
            max_size: Maximum number of cached items
            max_age: Maximum age of cached items in seconds
        """
        self.max_size = max_size
        self.max_age = max_age
        self.cache = {}
        self.metadata_cache = {}
        self.access_times = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_size': 0
        }
        
        logger.debug(f"MediaCache initialized: max_size={max_size}, max_age={max_age}")
    
    def cache_media(self, media_id: str, media_data: bytes, metadata: Dict[str, Any]) -> None:
        """
        Cache media with metadata.
        
        Args:
            media_id: Media identifier
            media_data: Media binary data
            metadata: Media metadata
        """
        if not media_id or not isinstance(media_id, str):
            raise ValueError("Media ID must be a non-empty string")
        
        if not isinstance(media_data, bytes):
            raise ValueError("Media data must be bytes")
        
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")
        
        # Check cache size and evict if necessary
        self._evict_if_needed()
        
        # Calculate data hash for integrity
        data_hash = hashlib.md5(media_data).hexdigest()
        
        # Store media data
        self.cache[media_id] = {
            'data': media_data,
            'hash': data_hash,
            'size': len(media_data),
            'timestamp': time.time()
        }
        
        # Store metadata
        self.metadata_cache[media_id] = {
            'metadata': metadata.copy(),
            'timestamp': time.time()
        }
        
        # Update access time
        self.access_times[media_id] = time.time()
        
        # Update stats
        self.cache_stats['total_size'] += len(media_data)
        
        logger.debug(f"Media cached: {media_id}, size={len(media_data)} bytes")
    
    def get_cached_media(self, media_id: str) -> Optional[bytes]:
        """
        Get cached media by ID.
        
        Args:
            media_id: Media identifier
            
        Returns:
            Cached media data or None if not found
        """
        if not media_id or not isinstance(media_id, str):
            raise ValueError("Media ID must be a non-empty string")
        
        if media_id not in self.cache:
            self.cache_stats['misses'] += 1
            logger.debug(f"Media cache miss: {media_id}")
            return None
        
        # Check if cache entry is expired
        if self._is_expired(media_id):
            self._remove_media(media_id)
            self.cache_stats['misses'] += 1
            logger.debug(f"Media cache expired: {media_id}")
            return None
        
        # Update access time
        self.access_times[media_id] = time.time()
        self.cache_stats['hits'] += 1
        
        logger.debug(f"Media cache hit: {media_id}")
        return self.cache[media_id]['data']
    
    def get_cached_metadata(self, media_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached metadata by ID.
        
        Args:
            media_id: Media identifier
            
        Returns:
            Cached metadata or None if not found
        """
        if not media_id or not isinstance(media_id, str):
            raise ValueError("Media ID must be a non-empty string")
        
        if media_id not in self.metadata_cache:
            logger.debug(f"Metadata cache miss: {media_id}")
            return None
        
        # Check if cache entry is expired
        if self._is_expired(media_id):
            self._remove_media(media_id)
            logger.debug(f"Metadata cache expired: {media_id}")
            return None
        
        # Update access time
        self.access_times[media_id] = time.time()
        
        logger.debug(f"Metadata cache hit: {media_id}")
        return self.metadata_cache[media_id]['metadata'].copy()
    
    def is_media_cached(self, media_id: str) -> bool:
        """
        Check if media is cached.
        
        Args:
            media_id: Media identifier
            
        Returns:
            True if media is cached and not expired, False otherwise
        """
        if not media_id or not isinstance(media_id, str):
            return False
        
        if media_id not in self.cache:
            return False
        
        # Check if cache entry is expired
        if self._is_expired(media_id):
            self._remove_media(media_id)
            return False
        
        return True
    
    def clear_cache(self) -> None:
        """
        Clear media cache.
        
        Clears all cached media and metadata.
        """
        self.cache.clear()
        self.metadata_cache.clear()
        self.access_times.clear()
        self.cache_stats['total_size'] = 0
        
        logger.debug("Media cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get cache information.
        
        Returns:
            Dictionary with cache information
        """
        return {
            'max_size': self.max_size,
            'max_age': self.max_age,
            'current_size': len(self.cache),
            'total_size_bytes': self.cache_stats['total_size'],
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'evictions': self.cache_stats['evictions'],
            'hit_rate': self._calculate_hit_rate()
        }
    
    def get_cached_media_ids(self) -> List[str]:
        """
        Get list of cached media IDs.
        
        Returns:
            List of cached media IDs
        """
        return list(self.cache.keys())
    
    def remove_media(self, media_id: str) -> bool:
        """
        Remove specific media from cache.
        
        Args:
            media_id: Media identifier
            
        Returns:
            True if media was removed, False if not found
        """
        if media_id in self.cache:
            self._remove_media(media_id)
            logger.debug(f"Media removed from cache: {media_id}")
            return True
        return False
    
    def get_media_size(self, media_id: str) -> Optional[int]:
        """
        Get size of cached media.
        
        Args:
            media_id: Media identifier
            
        Returns:
            Media size in bytes or None if not found
        """
        if media_id in self.cache:
            return self.cache[media_id]['size']
        return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return self.cache_stats.copy()
    
    def _evict_if_needed(self) -> None:
        """Evict old entries if cache is full."""
        if len(self.cache) >= self.max_size:
            # Find oldest entry
            oldest_id = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            self._remove_media(oldest_id)
            self.cache_stats['evictions'] += 1
            logger.debug(f"Media evicted from cache: {oldest_id}")
    
    def _is_expired(self, media_id: str) -> bool:
        """Check if cache entry is expired."""
        if media_id not in self.access_times:
            return True
        
        age = time.time() - self.access_times[media_id]
        return age > self.max_age
    
    def _remove_media(self, media_id: str) -> None:
        """Remove media from cache."""
        if media_id in self.cache:
            self.cache_stats['total_size'] -= self.cache[media_id]['size']
            del self.cache[media_id]
        
        if media_id in self.metadata_cache:
            del self.metadata_cache[media_id]
        
        if media_id in self.access_times:
            del self.access_times[media_id]
    
    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        if total_requests == 0:
            return 0.0
        return self.cache_stats['hits'] / total_requests
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired entries.
        
        Returns:
            Number of expired entries removed
        """
        expired_ids = [media_id for media_id in self.cache.keys() if self._is_expired(media_id)]
        
        for media_id in expired_ids:
            self._remove_media(media_id)
        
        logger.debug(f"Cleaned up {len(expired_ids)} expired entries")
        return len(expired_ids)
    
    def set_max_size(self, max_size: int) -> None:
        """
        Set maximum cache size.
        
        Args:
            max_size: Maximum number of cached items
        """
        if not isinstance(max_size, int) or max_size < 1:
            raise ValueError("Max size must be a positive integer")
        
        self.max_size = max_size
        logger.debug(f"Max cache size set to: {max_size}")
    
    def set_max_age(self, max_age: int) -> None:
        """
        Set maximum cache age.
        
        Args:
            max_age: Maximum age in seconds
        """
        if not isinstance(max_age, int) or max_age < 1:
            raise ValueError("Max age must be a positive integer")
        
        self.max_age = max_age
        logger.debug(f"Max cache age set to: {max_age} seconds")
    
    def get_media_hash(self, media_id: str) -> Optional[str]:
        """
        Get media data hash.
        
        Args:
            media_id: Media identifier
            
        Returns:
            Media data hash or None if not found
        """
        if media_id in self.cache:
            return self.cache[media_id]['hash']
        return None
    
    def verify_integrity(self, media_id: str) -> bool:
        """
        Verify media data integrity.
        
        Args:
            media_id: Media identifier
            
        Returns:
            True if data integrity is valid, False otherwise
        """
        if media_id not in self.cache:
            return False
        
        cached_data = self.cache[media_id]['data']
        current_hash = hashlib.md5(cached_data).hexdigest()
        stored_hash = self.cache[media_id]['hash']
        
        return current_hash == stored_hash
