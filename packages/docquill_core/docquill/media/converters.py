"""
Media converters for DOCX documents.

Handles media conversion functionality, EMF to PNG conversion, image format conversion, media optimization, and format validation.
"""

from typing import BinaryIO, Optional, Dict, Any, List, Tuple
from pathlib import Path
import io
import struct
import logging
import subprocess
import tempfile
import os
import shutil
import xml.etree.ElementTree as ET
import hashlib

logger = logging.getLogger(__name__)

# Import Java daemon for optimized conversion
try:
    from .java_daemon import get_java_daemon, shutdown_java_daemon
    _HAS_JAVA_DAEMON = True
except ImportError:
    _HAS_JAVA_DAEMON = False
    get_java_daemon = None  # type: ignore
    shutdown_java_daemon = None  # type: ignore

try:
    import cairosvg
    _HAS_CAIROSVG = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_CAIROSVG = False
    cairosvg = None  # type: ignore

try:
    import emf2svg  # type: ignore
    _HAS_EMF2SVG = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_EMF2SVG = False
    emf2svg = None  # type: ignore

# Import Rust converter for EMF/WMF conversion
# First try the unified PyPI package, then fallback to standalone module
_HAS_RUST_CONVERTER = False
emf_converter = None

try:
    # PyPI package: pip install docquill-rust
    import docquill_rust as emf_converter  # type: ignore
    _HAS_RUST_CONVERTER = True
except ImportError:
    try:
        # Standalone/legacy module
        import emf_converter  # type: ignore
        _HAS_RUST_CONVERTER = True
    except ImportError:  # pragma: no cover - optional dependency
        pass

class MediaConverter:
    """
    Converts media files between different formats.
    
    Handles media conversion functionality, format conversion, media optimization, and format validation.
    """
    
    def __init__(self, enable_cache: bool = True, enable_java_daemon: bool = False):
        """
        Initialize media converter.
        
        Sets up conversion tools, format support, and validation.
        
        Args:
            enable_cache: Enable caching of converted images (default: True)
            enable_java_daemon: Enable Java daemon for faster conversion (default: False)
                NOTE: Currently disabled by default because the daemon implementation
                still uses subprocess.run for each conversion, adding overhead without
                benefits. A true daemon would require modifying the Java converter to
                accept stdin/stdout communication.
        """
        self.supported_formats = {
            'emf': ['png', 'jpg', 'bmp'],
            'wmf': ['png', 'jpg', 'bmp'],
            'png': ['jpg', 'bmp', 'gif'],
            'jpg': ['png', 'bmp', 'gif'],
            'jpeg': ['png', 'bmp', 'gif'],
            'bmp': ['png', 'jpg', 'gif'],
            'gif': ['png', 'jpg', 'bmp']
        }
        
        self.format_signatures = {
            'png': [b'\x89PNG\r\n\x1a\n'],
            'jpg': [b'\xff\xd8\xff'],
            'jpeg': [b'\xff\xd8\xff'],
            'bmp': [b'BM'],
            'gif': [b'GIF87a', b'GIF89a'],
            'emf': [b'\x01\x00\x00\x00'],
            'wmf': [b'\xd7\xcd\xc6\x9a']
        }
        
        self.conversion_stats = {
            'conversions': 0,
            'optimizations': 0,
            'validations': 0,
            'errors': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Cache for converted images (key: hash of source data, value: converted PNG bytes)
        self.enable_cache = enable_cache
        self._conversion_cache: Dict[str, bytes] = {}
        
        # Java daemon for faster conversion
        self.enable_java_daemon = enable_java_daemon and _HAS_JAVA_DAEMON
        self._java_daemon = None
        
        logger.debug(f"MediaConverter initialized (cache={enable_cache}, java_daemon={self.enable_java_daemon})")
    
    def convert_emf_to_png(self, emf_data: bytes) -> Optional[bytes]:
        """
        Convert EMF to PNG format.
        
        Args:
            emf_data: EMF binary data
            
        Returns:
            PNG binary data or None if conversion fails
        """
        if not isinstance(emf_data, bytes):
            raise ValueError("EMF data must be bytes")
        
        try:
            # Validate EMF format
            if not self.validate_format(emf_data, 'emf'):
                logger.warning("Invalid EMF format")
                return None
            
            # For now, return a placeholder PNG
            # In a real implementation, this would use a library like Pillow
            # or a specialized EMF parser
            png_data = self._create_placeholder_png()
            
            self.conversion_stats['conversions'] += 1
            logger.debug("EMF to PNG conversion completed")
            return png_data
            
        except Exception as e:
            self.conversion_stats['errors'] += 1
            logger.error(f"EMF to PNG conversion failed: {e}")
            return None
    
    def convert_image_format(self, image_data: bytes, source_format: str, target_format: str) -> Optional[bytes]:
        """
        Convert image between formats.
        
        Args:
            image_data: Source image data
            source_format: Source format
            target_format: Target format
            
        Returns:
            Converted image data or None if conversion fails
        """
        if not isinstance(image_data, bytes):
            raise ValueError("Image data must be bytes")
        
        if not source_format or not target_format:
            raise ValueError("Source and target formats must be specified")
        
        if source_format not in self.supported_formats:
            raise ValueError(f"Unsupported source format: {source_format}")
        
        if target_format not in self.supported_formats[source_format]:
            raise ValueError(f"Cannot convert from {source_format} to {target_format}")
        
        try:
            # Validate source format
            if not self.validate_format(image_data, source_format):
                logger.warning(f"Invalid {source_format} format")
                return None
            
            # For now, return the original data
            # In a real implementation, this would use a library like Pillow
            converted_data = self._convert_with_pillow(image_data, source_format, target_format)
            
            self.conversion_stats['conversions'] += 1
            logger.debug(f"Image conversion completed: {source_format} -> {target_format}")
            return converted_data
            
        except Exception as e:
            self.conversion_stats['errors'] += 1
            logger.error(f"Image conversion failed: {e}")
            return None
    
    def optimize_image(self, image_data: bytes, format_type: str, quality: int = 85) -> Optional[bytes]:
        """
        Optimize image for better performance.
        
        Args:
            image_data: Image data to optimize
            format_type: Image format
            quality: Optimization quality (1-100)
            
        Returns:
            Optimized image data or None if optimization fails
        """
        if not isinstance(image_data, bytes):
            raise ValueError("Image data must be bytes")
        
        if not 1 <= quality <= 100:
            raise ValueError("Quality must be between 1 and 100")
        
        try:
            # Validate format
            if not self.validate_format(image_data, format_type):
                logger.warning(f"Invalid {format_type} format")
                return None
            
            # For now, return the original data
            # In a real implementation, this would use optimization techniques
            optimized_data = self._optimize_with_pillow(image_data, format_type, quality)
            
            self.conversion_stats['optimizations'] += 1
            logger.debug(f"Image optimization completed: {format_type}")
            return optimized_data
            
        except Exception as e:
            self.conversion_stats['errors'] += 1
            logger.error(f"Image optimization failed: {e}")
            return None
    
    def validate_format(self, data: bytes, format_type: str) -> bool:
        """
        Validate media format.
        
        Args:
            data: Media data to validate
            format_type: Expected format type
            
        Returns:
            True if format is valid, False otherwise
        """
        if not isinstance(data, bytes):
            return False
        
        if not format_type or format_type not in self.format_signatures:
            return False
        
        try:
            signatures = self.format_signatures[format_type]
            
            for signature in signatures:
                if data.startswith(signature):
                    self.conversion_stats['validations'] += 1
                    logger.debug(f"Format validation passed: {format_type}")
                    return True
            
            logger.debug(f"Format validation failed: {format_type}")
            return False
            
        except Exception as e:
            self.conversion_stats['errors'] += 1
            logger.error(f"Format validation error: {e}")
            return False
    
    def detect_format(self, data: bytes) -> Optional[str]:
        """
        Detect media format from data.
        
        Args:
            data: Media data to analyze
            
        Returns:
            Detected format or None if unknown
        """
        if not isinstance(data, bytes):
            return None
        
        try:
            for format_type, signatures in self.format_signatures.items():
                for signature in signatures:
                    if data.startswith(signature):
                        logger.debug(f"Format detected: {format_type}")
                        return format_type
            
            logger.debug("Format detection failed: unknown format")
            return None
            
        except Exception as e:
            logger.error(f"Format detection error: {e}")
            return None
    
    def get_supported_formats(self) -> Dict[str, List[str]]:
        """
        Get supported format conversions.
        
        Returns:
            Dictionary of supported format conversions
        """
        return self.supported_formats.copy()
    
    def get_conversion_stats(self) -> Dict[str, int]:
        """
        Get conversion statistics.
        
        Returns:
            Dictionary with conversion statistics
        """
        return self.conversion_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset conversion statistics."""
        self.conversion_stats = {
            'conversions': 0,
            'optimizations': 0,
            'validations': 0,
            'errors': 0
        }
        logger.debug("Conversion statistics reset")
    
    def _create_placeholder_png(self, width: int = 1, height: int = 1) -> bytes:
        """
        Create a placeholder PNG image.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Placeholder PNG data
        """
        try:
            # Try to create a simple colored PNG using PIL if available
            from PIL import Image
            img = Image.new('RGB', (width, height), color=(240, 240, 240))
            output = io.BytesIO()
            img.save(output, format='PNG')
            return output.getvalue()
        except ImportError:
            # Fallback: minimal 1x1 transparent PNG
            png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
            return png_data
    
    def _convert_with_soffice(self, emf_data: bytes, is_wmf: bool, width: int, height: int) -> Optional[bytes]:
        soffice_executable = shutil.which('soffice')
        if not soffice_executable:
            logger.debug("LibreOffice 'soffice' command not available; skipping fallback conversion")
            return None

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                suffix = '.wmf' if is_wmf else '.emf'
                input_path = Path(tmpdir) / f"input{suffix}"
                input_path.write_bytes(emf_data)

                cmd = [
                    soffice_executable,
                    '--headless',
                    '--convert-to', 'png',
                    '--outdir', tmpdir,
                    str(input_path)
                ]

                logger.debug(f"Running LibreOffice converter: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, timeout=90, text=True)
                if result.stdout:
                    logger.debug(f"LibreOffice stdout: {result.stdout.strip()}")
                if result.stderr:
                    logger.debug(f"LibreOffice stderr: {result.stderr.strip()}")

                if result.returncode != 0:
                    logger.error(f"LibreOffice conversion failed with code {result.returncode}")
                    return None

                output_path = input_path.with_suffix('.png')
                if not output_path.exists():
                    # LibreOffice sometimes preserves original name but may change case; fallback to search
                    candidates = list(Path(tmpdir).glob('*.png'))
                    if not candidates:
                        logger.error("LibreOffice conversion did not produce an output file")
                        return None
                    output_path = candidates[0]

                png_data = output_path.read_bytes()
                png_data = self._crop_image_whitespace(png_data)

                if width > 0 and height > 0:
                    try:
                        from PIL import Image
                        buffer = io.BytesIO(png_data)
                        with Image.open(buffer) as img:
                            resized = img.resize((width, height), Image.LANCZOS)
                            out_buffer = io.BytesIO()
                            resized.save(out_buffer, format='PNG')
                            png_data = out_buffer.getvalue()
                    except Exception as exc:
                        logger.debug(f"Failed to resize LibreOffice output: {exc}")

                return png_data

        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timed out")
        except Exception as exc:
            logger.error(f"LibreOffice conversion error: {exc}")

        return None

    def _crop_image_whitespace(self, image_data: bytes) -> bytes:
        """
        Remove surrounding white/transparent margins from rasterized images.
        LibreOffice often exports EMF/WMF assets with generous padding which shrinks
        the visible content when rendered using the original layout extents.
        """
        try:
            from PIL import Image

            buffer = io.BytesIO(image_data)
            with Image.open(buffer) as img:
                bbox = None
                if img.mode in ("RGBA", "LA"):
                    alpha = img.split()[-1]
                    bbox = alpha.getbbox()
                    if bbox == (0, 0, img.width, img.height):
                        bbox = None  # fall back to luminance-based detection
                if bbox is None:
                    grey = img.convert("L")
                    # Create a mask where non-white pixels are 255 (foreground), background 0
                    mask = grey.point(lambda p: 255 if p < 250 else 0, mode="1")
                    bbox = mask.getbbox()

                if not bbox:
                    return image_data

                left, upper, right, lower = bbox
                if (left, upper, right, lower) == (0, 0, img.width, img.height):
                    return image_data

                cropped = img.crop(bbox)
                out_buffer = io.BytesIO()
                cropped.save(out_buffer, format="PNG")
                logger.debug(
                    "Whitespace cropped from image: original=%sx%s -> cropped=%sx%s",
                    img.width,
                    img.height,
                    cropped.width,
                    cropped.height,
                )
                return out_buffer.getvalue()
        except ImportError:
            logger.debug("Pillow not available for whitespace cropping; returning original image")
            return image_data
        except Exception as exc:
            logger.debug(f"Whitespace cropping failed: {exc}")
            return image_data

    def _convert_with_pillow(self, image_data: bytes, source_format: str, target_format: str) -> bytes:
        """
        Convert image using Pillow library.
        
        Args:
            image_data: Source image data
            source_format: Source format
            target_format: Target format
            
        Returns:
            Converted image data
        """
        try:
            from PIL import Image
            
            # Open image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to target format
            output = io.BytesIO()
            image.save(output, format=target_format.upper())
            
            return output.getvalue()
            
        except ImportError:
            logger.warning("Pillow not available, returning original data")
            return image_data
        except Exception as e:
            logger.error(f"Pillow conversion failed: {e}")
            return image_data
    
    def _optimize_with_pillow(self, image_data: bytes, format_type: str, quality: int) -> bytes:
        """
        Optimize image using Pillow library.
        
        Args:
            image_data: Image data to optimize
            format_type: Image format
            quality: Optimization quality
            
        Returns:
            Optimized image data
        """
        try:
            from PIL import Image
            
            # Open image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            # Optimize based on format
            if format_type.lower() in ['jpg', 'jpeg']:
                # Convert to RGB if necessary
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')
                
                # Save with quality optimization
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=quality, optimize=True)
                return output.getvalue()
            
            elif format_type.lower() == 'png':
                # Save with optimization
                output = io.BytesIO()
                image.save(output, format='PNG', optimize=True)
                return output.getvalue()
            
            else:
                # Return original data for unsupported formats
                return image_data
                
        except ImportError:
            logger.warning("Pillow not available, returning original data")
            return image_data
        except Exception as e:
            logger.error(f"Pillow optimization failed: {e}")
            return image_data
    
    def get_image_info(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Get image information.
        
        Args:
            image_data: Image data to analyze
            
        Returns:
            Image information dictionary or None if analysis fails
        """
        if not isinstance(image_data, bytes):
            return None
        
        try:
            from PIL import Image
            
            # Open image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            return {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'width': image.width,
                'height': image.height,
                'has_transparency': image.mode in ('RGBA', 'LA', 'P'),
                'file_size': len(image_data)
            }
            
        except ImportError:
            logger.warning("Pillow not available for image analysis")
            return None
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return None
    
    def resize_image(self, image_data: bytes, width: int, height: int, format_type: str) -> Optional[bytes]:
        """
        Resize image to specified dimensions.
        
        Args:
            image_data: Image data to resize
            format_type: Image format
            width: Target width
            height: Target height
            
        Returns:
            Resized image data or None if resize fails
        """
        if not isinstance(image_data, bytes):
            raise ValueError("Image data must be bytes")
        
        if not isinstance(width, int) or not isinstance(height, int):
            raise ValueError("Width and height must be integers")
        
        if width <= 0 or height <= 0:
            raise ValueError("Width and height must be positive")
        
        try:
            from PIL import Image
            
            # Open image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            # Resize image
            resized_image = image.resize((width, height), Image.Resampling.LANCZOS)
            
            # Save in original format
            output = io.BytesIO()
            resized_image.save(output, format=format_type.upper())
            
            logger.debug(f"Image resized to {width}x{height}")
            return output.getvalue()
            
        except ImportError:
            logger.warning("Pillow not available for image resizing")
            return None
        except Exception as e:
            logger.error(f"Image resize failed: {e}")
            return None
    
    def convert_emf_to_svg(self, emf_data: bytes) -> Optional[str]:
        """
        Convert EMF/WMF data to SVG.
        
        Conversion priority:
        1. Rust converter (~50x faster, supports EMF, EMF+, WMF, WMF+embedded EMF)
        2. Java converter (FreeHEP/Apache POI - better edge case handling)
        3. Python emf2svg fallback
        """
        # Try Rust converter first (~50x faster than Java)
        svg_content = self._convert_emf_to_svg_rust(emf_data)
        if svg_content:
            return svg_content
        
        # Fallback to Java converter (better edge case support)
        svg_content = self._convert_emf_to_svg_java(emf_data)
        if svg_content:
            return svg_content
        
        # Final fallback to Python converter
        return self._convert_emf_to_svg_python(emf_data)

    def _convert_emf_to_svg_rust(self, emf_data: bytes) -> Optional[str]:
        """
        Convert EMF/WMF data to SVG using the Rust converter (~50x faster than Java).
        
        Supports: EMF, EMF+, WMF, WMF with embedded EMF.
        
        Returns SVG string or None if conversion is not possible.
        """
        if not _HAS_RUST_CONVERTER:
            logger.debug("Rust EMF converter not available")
            return None
        
        try:
            svg_content = emf_converter.convert_emf_bytes_to_svg(emf_data)  # type: ignore
            if svg_content and not self._is_svg_empty(svg_content):
                logger.debug("EMF converted to SVG via Rust converter")
                return svg_content
            else:
                logger.debug("Rust converter produced empty SVG output, falling back to Java")
                return None
        except Exception as exc:
            logger.debug(f"Rust EMF conversion failure: {exc}, falling back to Java")
            return None

    def _convert_emf_to_svg_java(self, emf_data: bytes) -> Optional[str]:
        """
        Try converting via Java backend (FreeHEP/Apache POI).
        
        Fallback for edge cases that Rust converter doesn't handle well.
        Slower (~50x) but has better compatibility with complex metafiles.
        
        Attempts both WMF and EMF codepaths because some DOCX files 
        store EMF payloads with a .wmf extension.
        """
        for suffix in (".emf", ".wmf"):
            svg = self._convert_emf_to_svg_java_with_suffix(emf_data, suffix)
            if svg:
                return svg
        return None

    def _convert_emf_to_svg_java_with_suffix(self, emf_data: bytes, suffix: str) -> Optional[str]:
        """
        Convert EMF/WMF data to SVG using the bundled Java converter (FreeHEP).
        Uses Java daemon if enabled for faster conversion.
        """
        converter_jar = Path(__file__).parent / "converter" / "java" / "emf-converter" / "target" / "emf-converter.jar"
        if not converter_jar.exists():
            logger.debug(f"EMF converter JAR not found at: {converter_jar}")
            return None

        # Try using Java daemon if enabled
        if self.enable_java_daemon and get_java_daemon:
            try:
                daemon = get_java_daemon(converter_jar)
                if daemon:
                    svg_content = daemon.convert(emf_data, suffix)
                    if svg_content and not self._is_svg_empty(svg_content):
                        logger.debug("EMF converted to SVG via Java daemon")
                        return svg_content
            except Exception as exc:
                logger.debug(f"Java daemon conversion failed, falling back to subprocess: {exc}")

        # Fallback to standard subprocess approach
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as emf_file:
            emf_file.write(emf_data)
            emf_path = Path(emf_file.name)

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as svg_file:
            svg_path = Path(svg_file.name)

        try:
            command = ["java", "-jar", str(converter_jar), str(emf_path), str(svg_path)]
            logger.debug(f"Executing converter command: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=30,
                text=True,
            )

            if result.stdout:
                logger.debug(f"Converter stdout: {result.stdout.strip()}")
            if result.stderr:
                logger.debug(f"Converter stderr: {result.stderr.strip()}")

            if result.returncode == 0 and svg_path.exists():
                svg_content = svg_path.read_text(encoding="utf-8")
                if self._is_svg_empty(svg_content):
                    logger.debug("Java converter produced empty SVG output")
                    return None
                logger.debug("EMF converted to SVG via Java converter")
                return svg_content

            logger.debug(
                "Java converter could not process EMF/WMF: "
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

    def _convert_emf_to_svg_python(self, emf_data: bytes) -> Optional[str]:
        """
        Convert EMF/WMF to SVG using the Python emf2svg package.

        Returns SVG string or None if conversion is not possible.
        """
        if not _HAS_EMF2SVG:
            return None

        suffix = ".emf"
        if emf_data[:2] == b"\xd7\xcd":  # WMF
            suffix = ".wmf"

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as emf_file:
                emf_file.write(emf_data)
                emf_path = Path(emf_file.name)

            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as svg_file:
                svg_path = Path(svg_file.name)

            try:
                # The emf2svg package provides a CLI-style API: emf2svg.convert(input, output)
                if hasattr(emf2svg, "convert"):
                    emf2svg.convert(str(emf_path), str(svg_path))  # type: ignore[attr-defined]
                elif hasattr(emf2svg, "EMF2SVGConverter"):
                    converter = emf2svg.EMF2SVGConverter(str(emf_path), str(svg_path))  # type: ignore[attr-defined]
                    converter.convert()  # type: ignore[attr-defined]
                else:
                    logger.debug("emf2svg module does not expose a known API (convert/EMF2SVGConverter)")
                    return None

                svg_content = svg_path.read_text(encoding="utf-8")
                if self._is_svg_empty(svg_content):
                    logger.debug("emf2svg produced empty SVG output")
                    return None
                logger.debug("EMF converted to SVG via emf2svg")
                return svg_content
            finally:
                try:
                    emf_path.unlink()
                except OSError:
                    pass
                try:
                    svg_path.unlink()
                except OSError:
                    pass
        except Exception as exc:  # pragma: no cover - best-effort fallback
            logger.debug(f"emf2svg conversion failed: {exc}")
            return None
    
    def convert_emf_to_png(
        self,
        emf_data: bytes,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Optional[bytes]:
        """
        Convert EMF/WMF data to PNG using Java converter.
        Uses cache if enabled to avoid re-converting the same images.
        
        Args:
            emf_data: EMF/WMF data as bytes
            width: Target width in pixels
            height: Target height in pixels
            
        Returns:
            PNG data as bytes or None if conversion fails
        """
        width_px = self._sanitize_dimension(width)
        height_px = self._sanitize_dimension(height)

        # Check cache if enabled
        if self.enable_cache:
            cache_key = self._get_cache_key(emf_data, width_px, height_px)
            if cache_key in self._conversion_cache:
                self.conversion_stats['cache_hits'] += 1
                logger.debug(f"Cache hit for EMF/WMF conversion (key: {cache_key[:16]}...)")
                return self._conversion_cache[cache_key]
            self.conversion_stats['cache_misses'] += 1

        try:
            # Check if it's WMF (different format than EMF)
            is_wmf = emf_data[:2] == b'\xd7\xcd'
            is_emf = emf_data[:4] == b'\x01\x00\x00\x00'
            
            if not (is_wmf or is_emf):
                logger.warning(f"Invalid EMF/WMF format signature")
                return None
            
            logger.debug(f"convert_emf_to_png invoked for {'WMF' if is_wmf else 'EMF'} image")

            # WMF: try conversion to SVG (first Rust, then Java, then Python...)
            if is_wmf:
                # Use convert_emf_to_svg which tries Rust first, then Java, then Python
                svg_content = self.convert_emf_to_svg(emf_data)
                
                # Only use SVG->PNG if SVG is not empty
                if svg_content and not self._is_svg_empty(svg_content):
                    png_from_svg = self._svg_to_png(svg_content, width_px, height_px)
                    if png_from_svg and len(png_from_svg) >= 500:  # Ensure it's not a placeholder
                        # Cache result if enabled
                        if self.enable_cache:
                            cache_key = self._get_cache_key(emf_data, width_px, height_px)
                            self._conversion_cache[cache_key] = png_from_svg
                        return png_from_svg
                
                # Fallback to LibreOffice for WMF conversion
                png_from_soffice = self._convert_with_soffice(
                    emf_data,
                    is_wmf=True,
                    width=self._resolve_dimension(width_px),
                    height=self._resolve_dimension(height_px),
                )
                if png_from_soffice and len(png_from_soffice) >= 500:  # Ensure it's not a placeholder
                    # Cache result if enabled
                    if self.enable_cache:
                        cache_key = self._get_cache_key(emf_data, width_px, height_px)
                        self._conversion_cache[cache_key] = png_from_soffice
                    return png_from_soffice
                
                logger.warning("No WMF conversion backend available, returning placeholder")
                return self._create_placeholder_png(
                    width_px or 1,
                    height_px or 1,
                )

            # First convert to SVG (preferred path for EMF)
            svg_content = self.convert_emf_to_svg(emf_data)
            if not svg_content:
                png_from_soffice = self._convert_with_soffice(
                    emf_data,
                    is_wmf=False,
                    width=self._resolve_dimension(width_px),
                    height=self._resolve_dimension(height_px),
                )
                if png_from_soffice:
                    return png_from_soffice
                logger.warning("No EMF conversion backend available, returning placeholder")
                return self._create_placeholder_png(
                    width_px or 1,
                    height_px or 1,
                )
            
            png_data = self._svg_to_png(svg_content, width_px, height_px)
            if png_data:
                logger.debug(f"SVG converted to PNG {width}x{height}")
                # Cache result if enabled
                if self.enable_cache:
                    cache_key = self._get_cache_key(emf_data, width_px, height_px)
                    self._conversion_cache[cache_key] = png_data
                return png_data

            png_from_soffice = self._convert_with_soffice(
                emf_data,
                is_wmf=False,
                width=self._resolve_dimension(width_px),
                height=self._resolve_dimension(height_px),
            )
            if png_from_soffice:
                # Cache result if enabled
                if self.enable_cache:
                    cache_key = self._get_cache_key(emf_data, width_px, height_px)
                    self._conversion_cache[cache_key] = png_from_soffice
                return png_from_soffice

            logger.warning("Unable to convert EMF to PNG via available backends, returning placeholder")
            placeholder = self._create_placeholder_png(
                width_px or 1,
                height_px or 1,
            )
            return placeholder
            
        except Exception as e:
            logger.error(f"EMF to PNG conversion failed: {e}")
            return self._create_placeholder_png(
                width_px or 1,
                height_px or 1,
            )

    def _svg_to_png(
        self,
        svg_content: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Optional[bytes]:
        """
        Convert SVG text to PNG bytes using cairosvg when available.
        """
        if not svg_content:
            return None
        if not _HAS_CAIROSVG:
            logger.debug("cairosvg not available for SVG→PNG conversion")
            return None

        try:
            kwargs: Dict[str, Any] = {}
            if isinstance(width, int) and width > 0:
                kwargs["output_width"] = width
            if isinstance(height, int) and height > 0:
                kwargs["output_height"] = height
            png_data = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"), **kwargs)  # type: ignore[arg-type]
            
            # Check if PNG is valid and not a placeholder
            # Placeholders are typically < 500 bytes, real images are much larger
            if png_data and len(png_data) < 500:
                logger.debug(f"SVG→PNG conversion produced very small PNG ({len(png_data)} bytes), likely empty/invalid")
                return None
            
            return png_data
        except Exception as exc:
            logger.warning(f"SVG→PNG conversion failed: {exc}")
            return None

    @staticmethod
    def _sanitize_dimension(value: Optional[int], min_value: int = 1, max_value: int = 4096) -> Optional[int]:
        if value is None:
            return None
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            return None
        if int_value <= 0:
            return min_value
        return min(int_value, max_value)

    @staticmethod
    def _resolve_dimension(value: Optional[int]) -> int:
        if isinstance(value, int) and value > 0:
            return value
        return 1

    @staticmethod
    def _get_cache_key(emf_data: bytes, width: Optional[int], height: Optional[int]) -> str:
        """
        Generate cache key for EMF/WMF conversion.
        
        Args:
            emf_data: EMF/WMF binary data
            width: Target width (optional)
            height: Target height (optional)
            
        Returns:
            Cache key string
        """
        # Use hash of data + dimensions as cache key
        hash_obj = hashlib.sha256(emf_data)
        if width is not None:
            hash_obj.update(f"w{width}".encode())
        if height is not None:
            hash_obj.update(f"h{height}".encode())
        return hash_obj.hexdigest()
    
    def clear_conversion_cache(self):
        """Clear conversion cache."""
        self._conversion_cache.clear()
        logger.debug("Conversion cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.conversion_stats['cache_hits'] + self.conversion_stats['cache_misses']
        hit_rate = (self.conversion_stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            'cache_enabled': self.enable_cache,
            'cache_size': len(self._conversion_cache),
            'cache_hits': self.conversion_stats['cache_hits'],
            'cache_misses': self.conversion_stats['cache_misses'],
            'hit_rate_percent': hit_rate,
            'java_daemon_enabled': self.enable_java_daemon,
        }
    
    @staticmethod
    def _is_svg_empty(svg_content: str) -> bool:
        if not svg_content or not svg_content.strip():
            return True
        normalized = svg_content.lower()
        if 'viewbox="0 0 -1 -1"' in normalized or 'viewbox="0 0 0 0"' in normalized:
            return True
        try:
            root = ET.fromstring(svg_content)
        except ET.ParseError:
            return False

        def _has_visible(node: ET.Element) -> bool:
            tag = node.tag.split('}')[-1] if '}' in node.tag else node.tag
            if tag in {"path", "polygon", "polyline"}:
                data = node.attrib.get("d") or node.attrib.get("points")
                if data and data.strip():
                    return True
            elif tag == "rect":
                try:
                    width = float(node.attrib.get("width", "0"))
                    height = float(node.attrib.get("height", "0"))
                except ValueError:
                    width = height = 0.0
                if width > 0.0 and height > 0.0:
                    return True
            elif tag in {"circle", "ellipse"}:
                try:
                    radius = float(node.attrib.get("r", "0"))
                except ValueError:
                    radius = 0.0
                if radius <= 0.0:
                    try:
                        rx = float(node.attrib.get("rx", "0"))
                        ry = float(node.attrib.get("ry", "0"))
                    except ValueError:
                        rx = ry = 0.0
                    if rx > 0.0 and ry > 0.0:
                        return True
                else:
                    return True
            elif tag in {"line"}:
                try:
                    x1 = float(node.attrib.get("x1", "0"))
                    y1 = float(node.attrib.get("y1", "0"))
                    x2 = float(node.attrib.get("x2", "0"))
                    y2 = float(node.attrib.get("y2", "0"))
                except ValueError:
                    x1 = y1 = x2 = y2 = 0.0
                if x1 != x2 or y1 != y2:
                    return True
            elif tag == "image":
                return True
            elif tag == "text":
                if (node.text and node.text.strip()) or any(
                    (child.text and child.text.strip()) for child in node
                ):
                    return True

            for child in list(node):
                if _has_visible(child):
                    return True
            return False

        return not _has_visible(root)
