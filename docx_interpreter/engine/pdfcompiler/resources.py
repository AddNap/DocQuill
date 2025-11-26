"""Resource management for PDF (fonts, images, colors)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple, Any


@dataclass
class PdfFont:
    """Represents a PDF font resource."""
    
    name: str  # Display name (e.g., "Arial")
    alias: str  # PDF alias (e.g., "/F1")
    bold: bool = False
    italic: bool = False
    font_path: Optional[str] = None  # Path to TTF file if embedded
    
    def get_base_name(self) -> str:
        """Get base font name without variant suffix."""
        return self.name
    
    def get_variant_name(self) -> str:
        """Get font name with variant suffix."""
        parts = [self.name]
        if self.bold:
            parts.append("Bold")
        if self.italic:
            parts.append("Italic")
        return "-".join(parts) if len(parts) > 1 else self.name


class PdfFontRegistry:
    """Registry for managing PDF fonts."""
    
    def __init__(self):
        self._fonts: Dict[str, PdfFont] = {}
        self._next_alias_num = 1
    
    def register_font(
        self,
        name: str,
        bold: bool = False,
        italic: bool = False,
        font_path: Optional[str] = None,
    ) -> PdfFont:
        """Register a font variant and return PdfFont object.
        
        Args:
            name: Font name (e.g., "Arial")
            bold: Whether font is bold
            italic: Whether font is italic
            font_path: Optional path to TTF file
            
        Returns:
            PdfFont object
        """
        # Create unique key for variant
        key = f"{name}:{bold}:{italic}"
        
        if key not in self._fonts:
            alias = f"/F{self._next_alias_num}"
            self._next_alias_num += 1
            
            font = PdfFont(
                name=name,
                alias=alias,
                bold=bold,
                italic=italic,
                font_path=font_path,
            )
            self._fonts[key] = font
        
        return self._fonts[key]
    
    def get_font(self, name: str, bold: bool = False, italic: bool = False) -> Optional[PdfFont]:
        """Get registered font by name and variant.
        
        Args:
            name: Font name
            bold: Whether font is bold
            italic: Whether font is italic
            
        Returns:
            PdfFont or None if not found
        """
        key = f"{name}:{bold}:{italic}"
        return self._fonts.get(key)
    
    def get_resources_dict(self) -> Dict[str, Dict[str, str]]:
        """Generate /Resources /Font dictionary for PDF.
        
        Returns:
            Dictionary mapping aliases to font definitions
        """
        resources = {}
        for font in self._fonts.values():
            # Determine font subtype based on font_path
            if font.font_path:
                # TrueType font - use /Subtype /TrueType
                # BaseFont should be the font name (e.g., "Arial-Bold")
                font_dict = {
                    "Type": "/Font",
                    "Subtype": "/TrueType",
                    "BaseFont": f"/{font.get_variant_name()}",
                    "Encoding": "/WinAnsiEncoding",
                }
                
                # Add FontDescriptor for embedded TTF fonts (required by PDF spec)
                # Note: This is a minimal descriptor - for full support, would need actual font metrics
                font_descriptor_num = 10000 + len(resources)  # Temporary object number (will be reassigned)
                font_dict["FontDescriptor"] = [font_descriptor_num, 0]
                
                # For now, we'll use name-based font mapping (relies on system fonts)
                # Full implementation would require:
                # - Actual font metrics (Ascent, Descent, CapHeight, etc.)
                # - Font file embedding
                # - ToUnicode mapping for non-ASCII characters
                # Minimal descriptor for compatibility:
                # font_dict["FontDescriptor"] = {
                #     "Type": "/FontDescriptor",
                #     "FontName": f"/{font.get_variant_name()}",
                #     "Flags": 32,  # Symbolic flag
                #     "FontBBox": [0, 0, 1000, 1000],
                #     "ItalicAngle": 0,
                #     "Ascent": 1000,
                #     "Descent": -200,
                #     "CapHeight": 700,
                #     "StemV": 80
                # }
            else:
                # Type1 font (standard 14 fonts)
                font_dict = {
                    "Type": "/Font",
                    "Subtype": "/Type1",
                    "BaseFont": f"/{font.get_variant_name()}",
                    "Encoding": "/WinAnsiEncoding",
                }
            resources[font.alias[1:]] = font_dict
        
        return resources
    
    def get_all_fonts(self) -> Dict[str, PdfFont]:
        """Get all registered fonts."""
        return self._fonts.copy()


@dataclass
class PdfImage:
    """Represents a PDF image resource."""
    
    path: str  # Path to image file or identifier
    alias: str  # PDF alias (e.g., "/Im1")
    width: float
    height: float
    image_type: str = "JPEG"  # JPEG, PNG, etc.
    image_data: Optional[bytes] = None  # Raw image data (bytes)
    object_num: Optional[int] = None  # PDF object number for this image


class PdfImageRegistry:
    """Registry for managing PDF images."""
    
    def __init__(self):
        self._images: Dict[str, PdfImage] = {}
        self._next_alias_num = 1
    
    def register_image(
        self,
        path: Optional[str] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        image_data: Optional[bytes] = None,
        image_type: Optional[str] = None,
    ) -> PdfImage:
        """Register an image and return PdfImage object.
        
        Args:
            path: Path to image file or identifier (rel_id, etc.) - optional for in-memory images
            width: Image width in points (optional)
            height: Image height in points (optional)
            image_data: Raw image data (bytes) - if provided, will be embedded
            image_type: Image type (JPEG, PNG, etc.) - if not provided, will be determined from path or data
            
        Returns:
            PdfImage object
        """
        # Use path or generate key for in-memory images (no path)
        # If path is None or empty, generate a unique key based on image_data id
        key = path if path else f"mem_{id(image_data)}"
        
        if key not in self._images:
            alias = f"/Im{self._next_alias_num}"
            self._next_alias_num += 1
            
            # Determine image type
            if image_type:
                detected_type = image_type.upper()
            else:
                # Try to determine from extension
                if path:
                    ext = Path(path).suffix.lower()
                    if ext in (".jpg", ".jpeg"):
                        detected_type = "JPEG"
                    elif ext == ".png":
                        detected_type = "PNG"
                    else:
                        detected_type = None  # Will try to detect from data
                else:
                    detected_type = None  # Will try to detect from data
                
                # Try to detect from image data (magic bytes) if not determined from extension
                if detected_type is None and image_data:
                    if image_data[:2] == b'\xff\xd8':
                        detected_type = "JPEG"
                    elif image_data[:8] == b'\x89PNG\r\n\x1a\n':
                        detected_type = "PNG"
                    else:
                        detected_type = "JPEG"  # Default
                elif detected_type is None:
                    detected_type = "JPEG"  # Default
            
            image = PdfImage(
                path=path or key,  # Store key as path if path is None
                alias=alias,
                width=width or 100.0,
                height=height or 100.0,
                image_type=detected_type,
                image_data=image_data,
            )
            self._images[key] = image
        
        return self._images[key]
    
    def get_image(self, path: Optional[str] = None, image_data: Optional[bytes] = None) -> Optional[PdfImage]:
        """Get registered image by path or image_data.
        
        Args:
            path: Path to image file or identifier (rel_id, etc.)
            image_data: Raw image data (bytes) - used to generate key if path is None
            
        Returns:
            PdfImage or None if not found
        """
        # If path is provided, use it directly
        if path:
            return self._images.get(path)
        # If no path but image_data is provided, generate key and look up
        if image_data is not None:
            key = f"mem_{id(image_data)}"
            return self._images.get(key)
        return None
    
    def get_resources_dict(self) -> Dict[str, Dict]:
        """Generate /Resources /XObject dictionary for PDF.
        
        Returns:
            Dictionary mapping aliases to image object references
        """
        resources = {}
        for image in self._images.values():
            if image.object_num is not None:
                # Reference to actual image object
                resources[image.alias[1:]] = [image.object_num, 0]
            else:
                # Fallback: placeholder dictionary
                resources[image.alias[1:]] = {
                    "Type": "/XObject",
                    "Subtype": "/Image",
                    "Width": image.width,
                    "Height": image.height,
                }
        
        return resources
    
    def get_all_images(self) -> Dict[str, PdfImage]:
        """Get all registered images."""
        return self._images.copy()

