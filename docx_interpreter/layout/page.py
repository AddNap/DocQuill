"""
Page model for DOCX documents.

Handles page properties, content management, and layout.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class Orientation(Enum):
    """Page orientation options."""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"

class PageSize(Enum):
    """Standard page sizes."""
    A4 = (210.0, 297.0)  # mm
    A3 = (297.0, 420.0)
    A5 = (148.0, 210.0)
    LETTER = (215.9, 279.4)
    LEGAL = (215.9, 355.6)

class Page:
    """
    Represents a page in the document.
    
    Handles page properties, content management, and layout.
    """
    
    def __init__(self, page_number: int = 1, width: float = 210.0, height: float = 297.0, 
                 width_mm: float = None, height_mm: float = None, orientation: Orientation = None,
                 margin_top_mm: float = None, margin_bottom_mm: float = None, 
                 margin_left_mm: float = None, margin_right_mm: float = None):
        """
        Initialize page.
        
        Args:
            page_number: Page number
            width: Page width in mm
            height: Page height in mm
            width_mm: Page width in mm (alias for width)
            height_mm: Page height in mm (alias for height)
            orientation: Page orientation
            margin_top_mm: Top margin in mm
            margin_bottom_mm: Bottom margin in mm
            margin_left_mm: Left margin in mm
            margin_right_mm: Right margin in mm
        """
        self.page_number = page_number
        
        # Handle width/height with aliases
        self.width = width_mm if width_mm is not None else width
        self.height = height_mm if height_mm is not None else height
        
        # Handle orientation
        self.orientation = orientation if orientation is not None else Orientation.PORTRAIT
        
        # Handle margins with aliases
        self.margin_top = margin_top_mm if margin_top_mm is not None else 25.4
        self.margin_right = margin_right_mm if margin_right_mm is not None else 25.4
        self.margin_bottom = margin_bottom_mm if margin_bottom_mm is not None else 25.4
        self.margin_left = margin_left_mm if margin_left_mm is not None else 25.4
        
        # Content area
        self.content_width = self.width - self.margin_left - self.margin_right
        self.content_height = self.height - self.margin_top - self.margin_bottom
        
        # Content management
        self.content = []
        self.headers = []
        self.footers = []
        
        logger.debug(f"Page {page_number} initialized: {width}x{height}mm")
    
    # Properties for compatibility with tests
    @property
    def width_mm(self) -> float:
        """Page width in mm."""
        return self.width
    
    @property
    def height_mm(self) -> float:
        """Page height in mm."""
        return self.height
    
    @property
    def margin_top_mm(self) -> float:
        """Top margin in mm."""
        return self.margin_top
    
    @property
    def margin_bottom_mm(self) -> float:
        """Bottom margin in mm."""
        return self.margin_bottom
    
    @property
    def margin_left_mm(self) -> float:
        """Left margin in mm."""
        return self.margin_left
    
    @property
    def margin_right_mm(self) -> float:
        """Right margin in mm."""
        return self.margin_right
    
    def set_page_size(self, width, height=None) -> None:
        """
        Set page size.
        
        Args:
            width: Page width in mm or PageSize enum
            height: Page height in mm (if width is not PageSize enum)
        """
        if isinstance(width, PageSize):
            # Handle PageSize enum
            self.width, self.height = width.value
        else:
            # Handle numeric values
            if height is None:
                raise ValueError("Height must be provided when width is numeric")
            self.width = width
            self.height = height
        
        self.content_width = self.width - self.margin_left - self.margin_right
        self.content_height = self.height - self.margin_top - self.margin_bottom
        
        logger.debug(f"Page size set to {self.width}x{self.height}mm")
    
    def set_margins(self, margins) -> None:
        """
        Set page margins.
        
        Args:
            margins: Dictionary with 'top', 'right', 'bottom', 'left' keys or tuple (top, right, bottom, left)
        """
        if isinstance(margins, dict):
            self.margin_top = margins.get('top', self.margin_top)
            self.margin_right = margins.get('right', self.margin_right)
            self.margin_bottom = margins.get('bottom', self.margin_bottom)
            self.margin_left = margins.get('left', self.margin_left)
        elif isinstance(margins, (tuple, list)) and len(margins) == 4:
            self.margin_top, self.margin_right, self.margin_bottom, self.margin_left = margins
        else:
            raise ValueError("Margins must be a dictionary or tuple of 4 values")
        
        # Recalculate content area
        self.content_width = self.width - self.margin_left - self.margin_right
        self.content_height = self.height - self.margin_top - self.margin_bottom
        
        logger.debug(f"Margins set to T:{self.margin_top} R:{self.margin_right} B:{self.margin_bottom} L:{self.margin_left}mm")
    
    def set_orientation(self, orientation: Orientation) -> None:
        """
        Set page orientation.
        
        Args:
            orientation: Page orientation
        """
        if orientation == Orientation.LANDSCAPE and self.orientation == Orientation.PORTRAIT:
            # Swap width and height
            self.width, self.height = self.height, self.width
            self.content_width = self.width - self.margin_left - self.margin_right
            self.content_height = self.height - self.margin_top - self.margin_bottom
        elif orientation == Orientation.PORTRAIT and self.orientation == Orientation.LANDSCAPE:
            # Swap width and height back
            self.width, self.height = self.height, self.width
            self.content_width = self.width - self.margin_left - self.margin_right
            self.content_height = self.height - self.margin_top - self.margin_bottom
        
        self.orientation = orientation
        logger.debug(f"Orientation set to {orientation.value}")
    
    def add_content(self, content) -> None:
        """
        Add content to page.
        
        Args:
            content: Content element to add (dict or object)
        """
        if isinstance(content, dict):
            content['page'] = self.page_number
            self.content.append(content)
        else:
            # Handle object content - add directly
            self.content.append(content)
        
        logger.debug(f"Content added to page {self.page_number}: {content.get('type', 'unknown') if isinstance(content, dict) else 'object'}")
    
    def get_content(self, content_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get page content.
        
        Args:
            content_type: Optional content type filter
            
        Returns:
            List of content elements
        """
        if content_type:
            return [item for item in self.content if item.get('type') == content_type]
        return self.content.copy()
    
    def add_header(self, header) -> None:
        """Add header to page."""
        if isinstance(header, dict):
            header['page'] = self.page_number
            header['type'] = 'header'
            self.headers.append(header)
        else:
            # Handle object header - add directly
            self.headers.append(header)
        logger.debug(f"Header added to page {self.page_number}")
    
    def add_footer(self, footer) -> None:
        """Add footer to page."""
        if isinstance(footer, dict):
            footer['page'] = self.page_number
            footer['type'] = 'footer'
            self.footers.append(footer)
        else:
            # Handle object footer - add directly
            self.footers.append(footer)
        logger.debug(f"Footer added to page {self.page_number}")
    
    def get_headers(self) -> List[Dict[str, Any]]:
        """Get page headers."""
        return self.headers.copy()
    
    def get_footers(self) -> List[Dict[str, Any]]:
        """Get page footers."""
        return self.footers.copy()
    
    def get_content_area(self) -> Dict[str, float]:
        """Get content area dimensions."""
        return {
            'width': self.content_width,
            'height': self.content_height,
            'x': self.margin_left,
            'y': self.margin_top
        }
    
    def get_page_info(self) -> Dict[str, Any]:
        """Get complete page information."""
        return {
            'page_number': self.page_number,
            'width': self.width,
            'height': self.height,
            'width_mm': self.width_mm,
            'height_mm': self.height_mm,
            'orientation': self.orientation.value,
            'margins': {
                'top': self.margin_top,
                'right': self.margin_right,
                'bottom': self.margin_bottom,
                'left': self.margin_left
            },
            'content_area': self.get_content_area(),
            'content_count': len(self.content),
            'header_count': len(self.headers),
            'footer_count': len(self.footers)
        }
    
    def clear_content(self) -> None:
        """Clear all content from page."""
        self.content.clear()
        self.headers.clear()
        self.footers.clear()
        logger.debug(f"Page {self.page_number} content cleared")
    
    def is_empty(self) -> bool:
        """Check if page is empty."""
        return len(self.content) == 0 and len(self.headers) == 0 and len(self.footers) == 0
    
    def get_content_height(self) -> float:
        """Calculate total content height."""
        total_height = 0.0
        for item in self.content:
            if isinstance(item, dict):
                total_height += float(item.get('height', 0))
            else:
                # For object content, assume 0 height
                total_height += 0.0
        return total_height
    
    def has_overflow(self) -> bool:
        """Check if content overflows page."""
        return self.get_content_height() > self.content_height
