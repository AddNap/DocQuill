"""PDF objects and data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .utils import format_pdf_number, escape_pdf_string


@dataclass
class PdfStream:
    """Represents a PDF content stream (instructions for drawing)."""
    
    commands: List[str] = field(default_factory=list)
    
    def write(self, command: str) -> None:
        """Append a raw PDF command to the stream."""
        if command is None:
            return
        self.commands.append(str(command))
    
    def add_text(self, font_alias: str, font_size: float, x: float, y: float, text: str, 
                 color: Optional[tuple] = None) -> None:
        """Add text drawing command.
        
        Args:
            font_alias: Font alias (e.g., "/F1")
            font_size: Font size in points
            x: X position
            y: Y position
            text: Text content
            color: Optional RGB tuple (0-1 scale) for text color
        """
        # Set text color if provided (must be before BT)
        if color:
            self.commands.append(f"{format_pdf_number(color[0])} {format_pdf_number(color[1])} {format_pdf_number(color[2])} rg")
        
        # BT ... ET block for text
        self.commands.append(f"BT")
        self.commands.append(f"{font_alias} {format_pdf_number(font_size)} Tf")
        self.commands.append(f"{format_pdf_number(x)} {format_pdf_number(y)} Td")
        
        # Handle text encoding: UTF-16BE for non-ASCII characters
        try:
            # Check if text contains non-ASCII characters
            text_bytes = text.encode("ascii")
            # All ASCII - use simple encoding
            escaped_text = escape_pdf_string(text)
            self.commands.append(f"({escaped_text}) Tj")
        except UnicodeEncodeError:
            # Contains non-ASCII - use UTF-16BE encoding
            # UTF-16BE with BOM: <FEFF...>
            text_utf16be = text.encode("utf-16be").hex().upper()
            self.commands.append(f"<FEFF{text_utf16be}> Tj")
        
        self.commands.append(f"ET")
        
        # Reset text color to black after text (if color was set)
        if color:
            self.commands.append("0 0 0 rg")
    
    def add_rect(self, x: float, y: float, width: float, height: float, fill_color: Optional[tuple] = None) -> None:
        """Add rectangle drawing command.
        
        Args:
            x: X position
            y: Y position
            width: Rectangle width
            height: Rectangle height
            fill_color: Optional RGB tuple (0-1 scale)
        """
        # Save previous color if fill_color is set
        previous_color_set = False
        if fill_color:
            self.commands.append(f"{format_pdf_number(fill_color[0])} {format_pdf_number(fill_color[1])} {format_pdf_number(fill_color[2])} rg")
            previous_color_set = True
        
        self.commands.append(f"{format_pdf_number(x)} {format_pdf_number(y)} {format_pdf_number(width)} {format_pdf_number(height)} re")
        
        if fill_color:
            self.commands.append("f")
        else:
            self.commands.append("S")
        
        # Reset color to black after rectangle (to avoid affecting subsequent text)
        if previous_color_set:
            self.commands.append("0 0 0 rg")
    
    def add_line(self, x1: float, y1: float, x2: float, y2: float, width: float = 1.0) -> None:
        """Add line drawing command.
        
        Args:
            x1: Start X
            y1: Start Y
            x2: End X
            y2: End Y
            width: Line width
        """
        self.commands.append(f"{format_pdf_number(width)} w")  # Line width
        self.commands.append(f"{format_pdf_number(x1)} {format_pdf_number(y1)} m")  # Move to start
        self.commands.append(f"{format_pdf_number(x2)} {format_pdf_number(y2)} l")  # Line to end
        self.commands.append("S")  # Stroke
    
    def add_image(self, image_alias: str, x: float, y: float, width: float, height: float, 
                  clip_x: Optional[float] = None, clip_y: Optional[float] = None, 
                  clip_width: Optional[float] = None, clip_height: Optional[float] = None) -> None:
        """Add image drawing command using XObject.
        
        Args:
            image_alias: Image alias (e.g., "/Im1")
            x: X position (left edge) - can be negative (image extends beyond left margin)
            y: Y position (bottom edge) - can be negative (image extends beyond bottom margin)
            width: Image width
            height: Image height
            clip_x: Optional clipping X position (if image extends beyond page)
            clip_y: Optional clipping Y position (if image extends beyond page)
            clip_width: Optional clipping width (if image extends beyond page)
            clip_height: Optional clipping height (if image extends beyond page)
        """
        # PDF image drawing: q (save state) -> cm (transform matrix) -> Do (draw object) -> Q (restore state)
        # Negative positions are allowed - PDF viewer will clip images outside page bounds
        self.commands.append("q")  # Save graphics state
        
        # If clipping is needed (image extends beyond page), set up clipping path
        if clip_x is not None and clip_y is not None and clip_width is not None and clip_height is not None:
            # Set up clipping rectangle
            self.commands.append(f"{format_pdf_number(clip_x)} {format_pdf_number(clip_y)} {format_pdf_number(clip_width)} {format_pdf_number(clip_height)} re")  # Rectangle path
            self.commands.append("W")  # Clip (non-zero winding rule)
            self.commands.append("n")  # New path (no stroke/fill, just clipping)
        
        # Transformation matrix: [width 0 0 height x y] scales and translates
        # Note: Negative x/y values are allowed - they position the image outside the page
        # The clipping path (if set) will clip the image to the page bounds
        self.commands.append(f"{format_pdf_number(width)} 0 0 {format_pdf_number(height)} {format_pdf_number(x)} {format_pdf_number(y)} cm")  # Transformation matrix
        self.commands.append(f"{image_alias} Do")  # Draw image object
        self.commands.append("Q")  # Restore graphics state
    
    def add_comment(self, text: str) -> None:
        """Add PDF comment.
        
        Args:
            text: Comment text
        """
        self.commands.append(f"% {text}")
    
    def get_content(self) -> str:
        """Get stream content as string."""
        return "\n".join(self.commands)
    
    def get_length(self) -> int:
        """Get stream length in bytes (including newline before endstream)."""
        # PDF stream length must include the newline before endstream
        content = self.get_content()
        return len((content + "\n").encode("utf-8"))


@dataclass
class PdfPage:
    """Represents a single PDF page."""
    
    page_number: int
    width: float
    height: float
    stream: PdfStream = field(default_factory=PdfStream)
    resources: Dict[str, Dict] = field(default_factory=dict)
    
    def get_page_dict(self, stream_obj_num: int, stream_dict: Optional[Dict] = None) -> Dict:
        """Generate page dictionary for PDF.
        
        Args:
            stream_obj_num: Object number for content stream
            stream_dict: Optional stream dictionary with Length and Filter (for proper PDF structure)
            
        Returns:
            Page dictionary
        """
        # If stream_dict is provided, use it for Contents reference (more complete)
        # Otherwise, use simple indirect reference
        if stream_dict:
            # Use stream dictionary directly (already has Length and Filter)
            page_dict = {
                "Type": "/Page",
                "MediaBox": [0, 0, self.width, self.height],
                "Contents": [stream_obj_num, 0],  # Reference to stream object
            }
        else:
            # Simple indirect reference (will be updated later with Length/Filter)
            page_dict = {
                "Type": "/Page",
                "MediaBox": [0, 0, self.width, self.height],
                "Contents": [stream_obj_num, 0],  # Reference to stream object
            }
        
        if self.resources:
            # Add ProcSet to Resources (required by PDF spec)
            resources = self.resources.copy()
            if "ProcSet" not in resources:
                resources["ProcSet"] = ["/PDF", "/Text", "/ImageB", "/ImageC", "/ImageI"]
            page_dict["Resources"] = resources
        
        return page_dict


@dataclass
class PdfDocument:
    """Represents a complete PDF document."""
    
    pages: List[PdfPage] = field(default_factory=list)
    catalog_obj_num: int = 1
    pages_obj_num: int = 2
    page_start_obj_num: int = 3
    info_dict: Optional[Dict[str, str]] = None  # PDF metadata (Title, Author, Producer, etc.)
    
    def get_page_count(self) -> int:
        """Get total number of pages."""
        return len(self.pages)
    
    def get_catalog_dict(self, pages_obj_num: int) -> Dict:
        """Generate catalog dictionary for PDF.
        
        Args:
            pages_obj_num: Object number for pages tree
            
        Returns:
            Catalog dictionary
        """
        return {
            "Type": "/Catalog",
            "Pages": [pages_obj_num, 0],
        }
    
    def get_pages_tree_dict(self, page_obj_nums: List[int]) -> Dict:
        """Generate pages tree dictionary for PDF.
        
        Args:
            page_obj_nums: List of object numbers for pages
            
        Returns:
            Pages tree dictionary
        """
        kids = [[num, 0] for num in page_obj_nums]
        return {
            "Type": "/Pages",
            "Kids": kids,
            "Count": len(kids),
        }

