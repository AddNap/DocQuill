"""PDF file writer - generates xref, trailer, and final PDF structure."""

from __future__ import annotations

import logging
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .objects import PdfDocument, PdfPage, PdfStream
from .resources import PdfImageRegistry

logger = logging.getLogger(__name__)


class PdfWriter:
    """Writes PDF document to file."""
    
    def __init__(self, output_path: str | Path):
        """Initialize PDF writer.
        
        Args:
            output_path: Path to output PDF file
        """
        self.output_path = Path(output_path)
        self.objects: List[Tuple[int, Dict | str]] = []  # (obj_num, content)
        self.xref_table: List[Tuple[int, int]] = []  # (offset, generation)
        self.current_offset = 0
    
    def write(self, document: PdfDocument, image_registry: PdfImageRegistry) -> None:
        """Write PDF document to file.
        
        Args:
            document: PdfDocument to write
            image_registry: Image registry for writing image objects
            
        Raises:
            ValueError: If document is None
            IOError: If file cannot be written
        """
        if document is None:
            raise ValueError("document cannot be None")
        if image_registry is None:
            raise ValueError("image_registry cannot be None")
        
        try:
            with open(self.output_path, "wb") as f:
                # Write PDF header
                f.write(b"%PDF-1.7\n")
                self.current_offset = f.tell()
                
                # Write catalog
                catalog_dict = document.get_catalog_dict(document.pages_obj_num)
                catalog_obj_num = document.catalog_obj_num
                self._write_object(f, catalog_obj_num, catalog_dict)
                
                # Write pages tree
                page_obj_nums = []
                next_obj_num = document.page_start_obj_num
                for i, page in enumerate(document.pages):
                    page_obj_num = next_obj_num
                    next_obj_num += 2  # Each page needs 2 objects (page dict + stream)
                    page_obj_nums.append(page_obj_num)
                    
                    # Calculate stream length and compression BEFORE writing page dict
                    # This ensures we have complete stream_dict with Length/Filter for proper PDF structure
                    stream_obj_num = page_obj_num + 1
                    stream_content = page.stream.get_content()
                    stream_bytes = (stream_content + "\n").encode("utf-8")
                    stream_dict = {}
                    
                    # Calculate compression and length
                    try:
                        compressed = zlib.compress(stream_bytes)
                        if len(compressed) < len(stream_bytes):
                            stream_dict["Filter"] = "/FlateDecode"
                            stream_dict["Length"] = len(compressed)
                        else:
                            stream_dict["Length"] = len(stream_bytes)
                    except Exception:
                        stream_dict["Length"] = len(stream_bytes)
                    
                    # Write page dictionary (with complete stream_dict info)
                    page_dict = page.get_page_dict(stream_obj_num, stream_dict)
                    # Add /Parent to every /Page (required by PDF spec)
                    page_dict["Parent"] = [document.pages_obj_num, 0]
                    self._write_object(f, page_obj_num, page_dict)
                    
                    # Write page content stream (with pre-calculated Length/Filter)
                    self._write_stream(f, stream_obj_num, stream_dict, stream_content)
                
                # Write pages tree
                pages_tree_dict = document.get_pages_tree_dict(page_obj_nums)
                self._write_object(f, document.pages_obj_num, pages_tree_dict)
                
                # Write image objects (XObject)
                # Note: object_num should already be assigned by compiler before building resources
                for image in image_registry.get_all_images().values():
                    if image.image_data:
                        if image.object_num is None:
                            # Fallback: assign object number if not already assigned
                            image.object_num = next_obj_num
                            next_obj_num += 1
                        else:
                            # Object number already assigned - just use it
                            # Update next_obj_num to be after the highest assigned number
                            if image.object_num >= next_obj_num:
                                next_obj_num = image.object_num + 1
                        self._write_image_object(f, image)
                
                # Write Info object (metadata) if available
                info_obj_num = None
                if hasattr(document, "info_dict") and document.info_dict:
                    # Ensure /Producer and /CreationDate are set (required for PDF/A compliance)
                    info_dict = document.info_dict.copy()
                    info_dict.setdefault("Producer", "DocQuill PDF Compiler 1.0")
                    # Add CreationDate if missing
                    if "CreationDate" not in info_dict:
                        from datetime import datetime
                        creation_date = datetime.now().strftime("(D:%Y%m%d%H%M%S)")
                        info_dict["CreationDate"] = creation_date
                    
                    info_obj_num = next_obj_num
                    next_obj_num += 1
                    self._write_object(f, info_obj_num, info_dict)
                
                # Sort xref_table entries by object number (for determinism and compatibility)
                # Note: xref_table entries are added in order, but sorting ensures consistency
                # The xref_table is a list of (offset, generation) tuples
                # We need to track which object number each entry corresponds to
                # Since we write objects sequentially, the order should match, but we sort for safety
                # Actually, we can't sort here because we don't have object numbers in xref_table
                # Instead, we'll ensure objects are written in order and xref_table matches
                # For now, we'll just write xref as-is (order matches object writing order)
                
                # Write xref table
                xref_offset = f.tell()
                self._write_xref(f)
                
                # Sanity-check offsets in XREF
                for i, (offset, generation) in enumerate(self.xref_table):
                    if offset <= 0:
                        logger.warning(f"Invalid xref offset for object {i + 1}: {offset}")
                
                # Write trailer
                self._write_trailer(f, xref_offset, catalog_obj_num, info_obj_num)
        except IOError as e:
            logger.error(f"IO error while writing PDF file: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while writing PDF file: {e}")
            raise
    
    def _write_object(self, f, obj_num: int, content: Dict) -> None:
        """Write PDF object.
        
        Args:
            f: File handle
            obj_num: Object number
            content: Object content (dictionary)
        """
        offset = f.tell()
        self.xref_table.append((offset, 0))  # Generation 0
        
        f.write(f"{obj_num} 0 obj\n".encode("utf-8"))
        f.write(self._dict_to_pdf(content).encode("utf-8"))
        f.write(b"\nendobj\n")
    
    def _write_stream(self, f, obj_num: int, stream_dict: Dict, content: str) -> None:
        """Write PDF stream object with optional compression.
        
        Args:
            f: File handle
            obj_num: Object number
            stream_dict: Stream dictionary
            content: Stream content
        """
        offset = f.tell()
        self.xref_table.append((offset, 0))
        
        f.write(f"{obj_num} 0 obj\n".encode("utf-8"))
        # Calculate actual stream length (content + newline before endstream)
        stream_bytes = (content + "\n").encode("utf-8")
        
        # Compress stream with /FlateDecode (zlib)
        try:
            compressed = zlib.compress(stream_bytes)
            # Only use compression if it actually reduces size
            if len(compressed) < len(stream_bytes):
                stream_dict["Filter"] = "/FlateDecode"
                stream_dict["Length"] = len(compressed)
                stream_bytes_to_write = compressed
            else:
                # Compression didn't help, use uncompressed
                stream_dict["Length"] = len(stream_bytes)
                stream_bytes_to_write = stream_bytes
        except Exception:
            # zlib compression failed, use uncompressed
            stream_dict["Length"] = len(stream_bytes)
            stream_bytes_to_write = stream_bytes
        
        f.write(self._dict_to_pdf(stream_dict).encode("utf-8"))
        f.write(b"\nstream\n")
        f.write(stream_bytes_to_write)
        f.write(b"\nendstream\n")
        f.write(b"endobj\n")
    
    def _write_image_object(self, f, image) -> None:
        """Write PDF image object (XObject).
        
        Args:
            f: File handle
            image: PdfImage object with image_data
        """
        from .resources import PdfImage
        
        if not image.image_data:
            return
        
        offset = f.tell()
        self.xref_table.append((offset, 0))
        
        # Image object dictionary (Length will be updated after processing)
        image_dict = {
            "Type": "/XObject",
            "Subtype": "/Image",
            "Width": int(image.width),
            "Height": int(image.height),
        }
        
        # Set color space and filter based on image type
        image_data_to_write = image.image_data
        
        if image.image_type == "JPEG":
            # JPEG can be embedded directly with DCTDecode filter
            # JPEG data is already in the correct format for PDF
            image_dict["ColorSpace"] = "/DeviceRGB"
            image_dict["BitsPerComponent"] = 8
            image_dict["Filter"] = "/DCTDecode"  # Filter name with / prefix
        elif image.image_type == "PNG":
            # PNG needs to be decoded to raw RGB data before writing to PDF
            # PDF cannot use PNG format directly - must be raw RGB/grayscale bytes
            try:
                from PIL import Image
                from io import BytesIO
                
                # Decode PNG to raw RGB
                png_image = Image.open(BytesIO(image.image_data))
                
                # Handle different color modes
                if png_image.mode in ("L", "1"):  # Grayscale or 1-bit
                    # Grayscale mode
                    image_dict["ColorSpace"] = "/DeviceGray"
                    image_dict["BitsPerComponent"] = 8 if png_image.mode == "L" else 1
                    # Convert to grayscale bytes
                    if png_image.mode == "1":
                        # 1-bit: convert to 8-bit grayscale
                        png_image = png_image.convert("L")
                        image_dict["BitsPerComponent"] = 8
                    raw_data = png_image.tobytes()
                    image_data_to_write = raw_data
                elif png_image.mode == "LA":  # Grayscale with alpha
                    # Convert to grayscale (drop alpha)
                    png_image = png_image.convert("L")
                    image_dict["ColorSpace"] = "/DeviceGray"
                    image_dict["BitsPerComponent"] = 8
                    raw_data = png_image.tobytes()
                    image_data_to_write = raw_data
                elif png_image.mode == "RGBA":
                    # Create white background and composite
                    rgb_image = Image.new("RGB", png_image.size, (255, 255, 255))
                    rgb_image.paste(png_image, mask=png_image.split()[3])  # Use alpha channel as mask
                    png_image = rgb_image
                    image_dict["ColorSpace"] = "/DeviceRGB"
                    image_dict["BitsPerComponent"] = 8
                    raw_data = png_image.tobytes()
                    image_data_to_write = raw_data
                elif png_image.mode == "RGB":
                    image_dict["ColorSpace"] = "/DeviceRGB"
                    image_dict["BitsPerComponent"] = 8
                    raw_data = png_image.tobytes()
                    image_data_to_write = raw_data
                else:
                    # Convert other modes to RGB
                    png_image = png_image.convert("RGB")
                    image_dict["ColorSpace"] = "/DeviceRGB"
                    image_dict["BitsPerComponent"] = 8
                    raw_data = png_image.tobytes()
                    image_data_to_write = raw_data
                
                # Update width/height from actual image (in case of conversion)
                image_dict["Width"] = png_image.width
                image_dict["Height"] = png_image.height
                # No filter needed for raw data
                
            except ImportError:
                # PIL not available - fallback: try to use PNG as-is (will likely fail)
                logger.warning("PIL not available - cannot decode PNG, image may be corrupted")
                image_dict["ColorSpace"] = "/DeviceRGB"
                image_dict["BitsPerComponent"] = 8
            except Exception as e:
                # Error decoding PNG - fallback to placeholder
                logger.error(f"Failed to decode PNG image: {e}")
                # Create a simple placeholder RGB image
                width = int(image.width)
                height = int(image.height)
                # Create gray placeholder (RGB: 238, 238, 238)
                placeholder_rgb = bytes([238, 238, 238]) * (width * height)
                image_data_to_write = placeholder_rgb
                image_dict["ColorSpace"] = "/DeviceRGB"
                image_dict["BitsPerComponent"] = 8
        else:
            # Default to RGB for unknown types
            image_dict["ColorSpace"] = "/DeviceRGB"
            image_dict["BitsPerComponent"] = 8
        
        # Update length with actual data size
        image_dict["Length"] = len(image_data_to_write)
        
        f.write(f"{image.object_num} 0 obj\n".encode("utf-8"))
        f.write(self._dict_to_pdf(image_dict).encode("utf-8"))
        f.write(b"\nstream\n")
        f.write(image_data_to_write)  # Write processed image data
        f.write(b"\nendstream\n")
        f.write(b"endobj\n")
    
    def _write_xref(self, f) -> None:
        """Write xref table.
        
        Args:
            f: File handle
        """
        f.write(b"xref\n")
        f.write(f"0 {len(self.xref_table) + 1}\n".encode("utf-8"))
        f.write(b"0000000000 65535 f \n")  # Free object
        
        for offset, generation in self.xref_table:
            f.write(f"{offset:010d} {generation:05d} n \n".encode("utf-8"))
    
    def _write_trailer(self, f, xref_offset: int, root_obj_num: int, info_obj_num: Optional[int] = None) -> None:
        """Write trailer.
        
        Args:
            f: File handle
            xref_offset: Offset to xref table
            root_obj_num: Root object number (catalog)
            info_obj_num: Optional Info object number for metadata
        """
        f.write(b"trailer\n")
        trailer_dict = {
            "Size": len(self.xref_table) + 1,
            "Root": [root_obj_num, 0],
        }
        if info_obj_num is not None:
            trailer_dict["Info"] = [info_obj_num, 0]
        f.write(self._dict_to_pdf(trailer_dict).encode("utf-8"))
        f.write(b"\nstartxref\n")
        f.write(f"{xref_offset}\n".encode("utf-8"))
        f.write(b"%%EOF\n")
    
    def _dict_to_pdf(self, d: Dict) -> str:
        """Convert dictionary to PDF format.
        
        Args:
            d: Dictionary to convert
            
        Returns:
            PDF-formatted string
        """
        parts = ["<<"]
        
        for key, value in d.items():
            # Remove leading slash if present (keys should not have slash in dict)
            clean_key = key.lstrip("/")
            
            if isinstance(value, dict):
                parts.append(f"/{clean_key} {self._dict_to_pdf(value)}")
            elif isinstance(value, list):
                # Check if it's an object reference [obj_num, gen] - both must be int
                if len(value) == 2 and all(isinstance(v, int) for v in value):
                    # Object reference [obj_num, gen]
                    parts.append(f"/{clean_key} {value[0]} {value[1]} R")
                else:
                    # Array
                    arr_parts = []
                    for item in value:
                        if isinstance(item, (int, float)):
                            arr_parts.append(str(item))
                        elif isinstance(item, list) and len(item) == 2:
                            # Nested object reference
                            arr_parts.append(f"{item[0]} {item[1]} R")
                    arr_str = " ".join(arr_parts)
                    parts.append(f"/{clean_key} [{arr_str}]")
            elif isinstance(value, str):
                # String values - check if it's already a PDF Name (starts with /)
                if value.startswith("/"):
                    # Already a PDF Name - use as-is
                    parts.append(f"/{clean_key} {value}")
                else:
                    # It's a literal string - wrap in parentheses and escape
                    # Note: For PDF Names (like BaseFont, Filter), caller should use / prefix
                    # For literal strings (like Title, Author), use as-is
                    from .utils import escape_pdf_string
                    escaped = escape_pdf_string(value)
                    parts.append(f"/{clean_key} ({escaped})")
            elif isinstance(value, (int, float)):
                parts.append(f"/{clean_key} {value}")
            elif isinstance(value, bool):
                parts.append(f"/{clean_key} {'true' if value else 'false'}")
        
        parts.append(">>")
        return " ".join(parts)

