"""
Image conversion cache for pre-converting WMF/EMF images during parsing.

This module provides a cache for converted images, allowing asynchronous
conversion during parsing and synchronous retrieval during rendering.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Set
from concurrent.futures import ThreadPoolExecutor, Future
import threading

logger = logging.getLogger(__name__)


class ImageConversionCache:
    """
    Cache for converted images (WMF/EMF -> PNG).
    
    Allows asynchronous conversion during parsing and synchronous retrieval during rendering.
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize image conversion cache.
        
        Args:
            max_workers: Maximum number of concurrent conversion threads
        """
        self._cache: Dict[str, Optional[Path]] = {}  # relationship_id -> PNG path
        self._pending: Dict[str, Future] = {}  # relationship_id -> Future
        self._lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers = max_workers
        
    def start(self) -> None:
        """Start the thread pool executor for asynchronous conversions."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
            logger.debug(f"ImageConversionCache: Started thread pool with {self._max_workers} workers")
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread pool executor."""
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None
            logger.debug("ImageConversionCache: Shutdown thread pool")
    
    def convert_async(
        self,
        relationship_id: str,
        image_data: bytes,
        image_path: Optional[str],
        converter_fn,
        width_px: Optional[int] = None,
        height_px: Optional[int] = None,
    ) -> None:
        """
        Schedule asynchronous image conversion.
        
        Args:
            relationship_id: Relationship ID of the image
            image_data: Image binary data (WMF/EMF)
            image_path: Optional path to the image file
            converter_fn: Function to call for conversion (MediaConverter.convert_emf_to_png)
            width_px: Optional width in pixels
            height_px: Optional height in pixels
        """
        if not relationship_id:
            return
        
        with self._lock:
            # Skip if already cached or pending
            if relationship_id in self._cache or relationship_id in self._pending:
                return
            
            # Ensure executor is started
            if self._executor is None:
                self.start()
            
            # Schedule conversion
            future = self._executor.submit(
                self._convert_image,
                relationship_id,
                image_data,
                image_path,
                converter_fn,
                width_px,
                height_px,
            )
            self._pending[relationship_id] = future
            logger.debug(f"ImageConversionCache: Scheduled async conversion for {relationship_id}")
    
    def _convert_image(
        self,
        relationship_id: str,
        image_data: bytes,
        image_path: Optional[str],
        converter_fn,
        width_px: Optional[int],
        height_px: Optional[int],
    ) -> Optional[Path]:
        """Internal method to convert image (runs in thread)."""
        try:
            # Call converter function (MediaConverter.convert_emf_to_png accepts width/height)
            png_bytes = converter_fn(image_data, width=width_px, height=height_px)
            
            if not png_bytes:
                logger.warning(f"ImageConversionCache: Conversion failed for {relationship_id}")
                with self._lock:
                    self._cache[relationship_id] = None
                    self._pending.pop(relationship_id, None)
                return None
            
            # Save to temporary file
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / "docx_interpreter_images"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Use relationship_id as filename (sanitize)
            safe_id = relationship_id.replace("/", "_").replace("\\", "_")
            temp_file = temp_dir / f"{safe_id}.png"
            temp_file.write_bytes(png_bytes)
            
            logger.debug(f"ImageConversionCache: Converted {relationship_id} -> {temp_file}")
            
            with self._lock:
                self._cache[relationship_id] = temp_file
                self._pending.pop(relationship_id, None)
            
            return temp_file
            
        except Exception as e:
            logger.error(f"ImageConversionCache: Error converting {relationship_id}: {e}", exc_info=True)
            with self._lock:
                self._cache[relationship_id] = None
                self._pending.pop(relationship_id, None)
            return None
    
    def get(self, relationship_id: str, wait: bool = True) -> Optional[Path]:
        """
        Get converted image path.
        
        Args:
            relationship_id: Relationship ID of the image
            wait: If True, wait for pending conversion to complete
            
        Returns:
            Path to converted PNG file or None if not available/converted
        """
        if not relationship_id:
            return None
        
        with self._lock:
            # Check cache
            if relationship_id in self._cache:
                return self._cache[relationship_id]
            
            # Check pending
            if relationship_id in self._pending:
                if wait:
                    # Wait for conversion to complete
                    future = self._pending[relationship_id]
                    with self._lock:
                        # Release lock before waiting
                        pass
                    try:
                        result = future.result(timeout=30.0)  # 30 second timeout
                        with self._lock:
                            return self._cache.get(relationship_id)
                    except Exception as e:
                        logger.warning(f"ImageConversionCache: Timeout/error waiting for {relationship_id}: {e}")
                        with self._lock:
                            self._pending.pop(relationship_id, None)
                            self._cache[relationship_id] = None
                        return None
                else:
                    # Not ready yet
                    return None
        
        # Not found
        return None
    
    def wait_for_all(self, timeout: Optional[float] = None) -> None:
        """
        Wait for all pending conversions to complete.
        
        Args:
            timeout: Maximum time to wait in seconds (None = wait indefinitely)
        """
        with self._lock:
            pending = list(self._pending.items())
        
        if not pending:
            return
        
        logger.debug(f"ImageConversionCache: Waiting for {len(pending)} pending conversions")
        
        for relationship_id, future in pending:
            try:
                future.result(timeout=timeout)
            except Exception as e:
                logger.warning(f"ImageConversionCache: Error waiting for {relationship_id}: {e}")
        
        logger.debug("ImageConversionCache: All conversions completed")
    
    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._pending.clear()
        logger.debug("ImageConversionCache: Cache cleared")

