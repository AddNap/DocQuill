"""
Java daemon manager for EMF/WMF conversion.

Maintains a persistent Java process to avoid startup overhead.
Communicates via stdin/stdout for efficient batch processing.
"""

import subprocess
import threading
import queue
import logging
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile
import time

logger = logging.getLogger(__name__)


class JavaConverterDaemon:
    """
    Manages a persistent Java process for EMF/WMF conversion.
    
    NOTE: Current implementation is NOT a true daemon - it still uses subprocess.run
    for each conversion, which means it starts a new Java process each time.
    
    To create a true daemon, the Java converter would need to be modified to:
    1. Accept input via stdin (or socket) instead of file paths
    2. Return output via stdout (or socket) instead of file paths
    3. Run in "server mode" (loop waiting for requests)
    
    With a true daemon:
    - First conversion: ~0.8-1.0s (JVM startup ~0.3-0.5s + conversion ~0.5s)
    - Subsequent conversions: ~0.5s (only conversion, no JVM startup)
    
    Current implementation adds overhead (lock, tempfile operations) without benefits.
    """
    
    def __init__(self, converter_jar: Path, max_idle_time: float = 60.0):
        """
        Initialize Java daemon.
        
        Args:
            converter_jar: Path to emf-converter.jar
            max_idle_time: Maximum idle time before shutdown (seconds)
        """
        self.converter_jar = converter_jar
        self.max_idle_time = max_idle_time
        self.process: Optional[subprocess.Popen] = None
        self.last_used: float = 0.0
        self.lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        
    def _start_process(self) -> bool:
        """Start Java converter process."""
        if self.process is not None:
            return True
            
        # Note: The Java converter uses file-based I/O and requires input/output paths.
        # We can't keep a persistent process running since each conversion needs file paths.
        # Instead, we'll just verify the JAR exists and is executable.
        # The actual conversion will use subprocess.run for each conversion.
        if not self.converter_jar.exists():
            logger.debug(f"Java converter JAR not found: {self.converter_jar}")
            return False
        
        # Verify Java is available
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                timeout=5,
                text=True,
            )
            if result.returncode != 0:
                logger.debug("Java not available or not working")
                return False
        except Exception:
            logger.debug("Failed to verify Java availability")
            return False
        
        # Mark as "started" (we'll use subprocess.run for each conversion)
        self.last_used = time.time()
        logger.debug("Java converter daemon initialized (using subprocess.run per conversion)")
        return True
    
    def convert(self, emf_data: bytes, suffix: str = ".wmf") -> Optional[str]:
        """
        Convert EMF/WMF data to SVG using daemon process.
        
        NOTE: Current implementation is NOT a true daemon - it still uses subprocess.run
        for each conversion. This adds overhead without benefits. Consider disabling
        java_daemon in MediaConverter until a proper daemon implementation is available.
        
        Args:
            emf_data: EMF/WMF binary data
            suffix: File suffix (.emf or .wmf)
            
        Returns:
            SVG content or None if conversion fails
        """
        # WARNING: This is NOT a true daemon - it still uses subprocess.run each time
        # which means it starts a new Java process for each conversion.
        # This adds overhead (lock, tempfile operations) without benefits.
        # For now, this method just delegates to the standard subprocess approach.
        # A true daemon would require modifying the Java converter to accept stdin/stdout.
        
        with self.lock:
            # Ensure JAR exists (but don't start a persistent process)
            if not self.converter_jar.exists():
                return None
            self.last_used = time.time()
        
        # Use standard file-based conversion (same as non-daemon path)
        # This is actually faster than the "daemon" wrapper because it has less overhead
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as emf_file:
            emf_file.write(emf_data)
            emf_path = Path(emf_file.name)

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as svg_file:
            svg_path = Path(svg_file.name)

        try:
            command = ["java", "-jar", str(self.converter_jar), str(emf_path), str(svg_path)]
            
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=30,
                text=True,
            )

            if result.returncode == 0 and svg_path.exists():
                svg_content = svg_path.read_text(encoding="utf-8")
                if svg_content.strip():
                    logger.debug("EMF converted to SVG via Java converter")
                    return svg_content

            logger.debug(
                f"Java converter failed: "
                f"{result.stderr.strip() if result.stderr else result.stdout.strip() if result.stdout else 'no details'}"
            )
            return None
            
        except subprocess.TimeoutExpired:
            logger.debug("EMF conversion via Java timed out")
            return None
        except Exception as exc:
            logger.debug(f"Java EMF conversion failure: {exc}")
            return None
        finally:
            try:
                emf_path.unlink()
            except OSError:
                pass
            try:
                svg_path.unlink()
            except OSError:
                pass
    
    def shutdown(self):
        """Shutdown Java daemon process."""
        with self.lock:
            if self.process is not None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                except Exception as exc:
                    logger.debug(f"Error shutting down Java daemon: {exc}")
                finally:
                    self.process = None
            
            self._shutdown_event.set()
    
    def is_running(self) -> bool:
        """Check if daemon is running."""
        with self.lock:
            if self.process is None:
                return False
            return self.process.poll() is None


# Global daemon instance
_global_daemon: Optional[JavaConverterDaemon] = None
_daemon_lock = threading.Lock()


def get_java_daemon(converter_jar: Path) -> Optional[JavaConverterDaemon]:
    """
    Get or create global Java daemon instance.
    
    Args:
        converter_jar: Path to emf-converter.jar
        
    Returns:
        JavaConverterDaemon instance or None if JAR not found
    """
    global _global_daemon
    
    if not converter_jar.exists():
        logger.debug(f"EMF converter JAR not found at: {converter_jar}")
        return None
    
    with _daemon_lock:
        if _global_daemon is None:
            _global_daemon = JavaConverterDaemon(converter_jar)
        return _global_daemon


def shutdown_java_daemon():
    """Shutdown global Java daemon."""
    global _global_daemon
    with _daemon_lock:
        if _global_daemon is not None:
            _global_daemon.shutdown()
            _global_daemon = None

