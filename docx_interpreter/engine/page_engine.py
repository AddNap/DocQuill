"""Page engine for creating pages with pre-calculated headers, footers, and margins.

This engine handles:
- Pre-calculation of header/footer heights
- Different header/footer variants (first page, odd/even pages)
- Page creation with already calculated margins
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .unified_layout import LayoutPage
from .geometry import Margins, Size


@dataclass(slots=True)
class PageConfig:
    """Configuration for page creation."""
    page_size: Size
    base_margins: Margins
    header_height: float = 0.0
    footer_height: float = 0.0
    header_height_first: Optional[float] = None  # Different header for first page
    footer_height_first: Optional[float] = None  # Different footer for first page
    header_height_even: Optional[float] = None  # Different header for even pages
    footer_height_even: Optional[float] = None  # Different footer for even pages
    
    @property
    def content_height(self) -> float:
        """Calculate available content height (excluding header/footer)."""
        return self.page_size.height - self.base_margins.top - self.base_margins.bottom - self.header_height - self.footer_height
    
    @property
    def content_top(self) -> float:
        """Top of content area in PDF coordinates."""
        return self.page_size.height - self.base_margins.top - self.header_height
    
    @property
    def content_bottom(self) -> float:
        """Bottom of content area in PDF coordinates."""
        return self.base_margins.bottom + self.footer_height
    
    def get_header_height(self, page_number: int) -> float:
        """Get header height for specific page number.
        
        Args:
            page_number: Page number (1-based)
            
        Returns:
            Header height for this page
        """
        if page_number == 1 and self.header_height_first is not None:
            return self.header_height_first
        if page_number % 2 == 0 and self.header_height_even is not None:
            return self.header_height_even
        # Odd pages (except first) use default header_height
        return self.header_height
    
    def get_footer_height(self, page_number: int) -> float:
        """Get footer height for specific page number.
        
        Args:
            page_number: Page number (1-based)
            
        Returns:
            Footer height for this page
        """
        if page_number == 1 and self.footer_height_first is not None:
            return self.footer_height_first
        if page_number % 2 == 0 and self.footer_height_even is not None:
            return self.footer_height_even
        return self.footer_height
    
    def get_content_height(self, page_number: int) -> float:
        """Get content height for specific page number.
        
        Args:
            page_number: Page number (1-based)
            
        Returns:
            Available content height for this page
        """
        header_h = self.get_header_height(page_number)
        footer_h = self.get_footer_height(page_number)
        return self.page_size.height - self.base_margins.top - self.base_margins.bottom - header_h - footer_h
    
    def get_content_top(self, page_number: int) -> float:
        """Get content top position for specific page number.
        
        Args:
            page_number: Page number (1-based)
            
        Returns:
            Top of content area in PDF coordinates
        """
        header_h = self.get_header_height(page_number)
        return self.page_size.height - self.base_margins.top - header_h
    
    def get_content_bottom(self, page_number: int) -> float:
        """Get content bottom position for specific page number.
        
        Args:
            page_number: Page number (1-based)
            
        Returns:
            Bottom of content area in PDF coordinates
        """
        footer_h = self.get_footer_height(page_number)
        return self.base_margins.bottom + footer_h


class PageEngine:
    """Engine for creating pages with pre-calculated headers, footers, and margins."""
    
    def __init__(self, config: PageConfig):
        """Initialize page engine.
        
        Args:
            config: Page configuration with pre-calculated header/footer heights
        """
        self.config = config
        self.current_page_number = 1
    
    def create_page(self, page_number: Optional[int] = None) -> LayoutPage:
        """Create a new page with pre-calculated margins.
        
        Args:
            page_number: Page number (if None, uses current page number)
            
        Returns:
            LayoutPage with pre-calculated margins
        """
        if page_number is None:
            page_number = self.current_page_number
        else:
            self.current_page_number = page_number
        
        # Get header/footer heights for this page
        header_height = self.config.get_header_height(page_number)
        footer_height = self.config.get_footer_height(page_number)
        
        # Calculate effective margins (base margins + header/footer)
        effective_margins = Margins(
            left=self.config.base_margins.left,
            right=self.config.base_margins.right,
            top=self.config.base_margins.top + header_height,
            bottom=self.config.base_margins.bottom + footer_height,
        )
        
        # Create page with pre-calculated header/footer heights
        page = LayoutPage(
            number=page_number,
            size=self.config.page_size,
            margins=effective_margins,
        )
        page.header_height = header_height
        page.footer_height = footer_height
        
        return page
    
    def starting_cursor(self, page_number: Optional[int] = None) -> float:
        """Get starting cursor position for a page.
        
        Args:
            page_number: Page number (if None, uses current page number)
            
        Returns:
            Top Y position of content area in PDF coordinates
        """
        if page_number is None:
            page_number = self.current_page_number
        return self.config.get_content_top(page_number)
    
    def remaining_space(self, y_cursor: float, page_number: Optional[int] = None) -> float:
        """Compute remaining vertical space above the bottom margin.
        
        Args:
            y_cursor: Current Y position in PDF coordinates
            page_number: Page number (if None, uses current page number)
            
        Returns:
            Remaining space in points
        """
        if page_number is None:
            page_number = self.current_page_number
        content_bottom = self.config.get_content_bottom(page_number)
        return max(0.0, y_cursor - content_bottom)
    
    def fits_on_page(self, y_cursor: float, block_height: float, page_number: Optional[int] = None) -> bool:
        """Check whether the block can fit on the current page.
        
        Args:
            y_cursor: Top Y position of block in PDF coordinates
            block_height: Height of block in points
            page_number: Page number (if None, uses current page number)
            
        Returns:
            True if block fits, False otherwise
        """
        return self.remaining_space(y_cursor, page_number) >= block_height
    
    def next_page(self) -> int:
        """Increment page number and return new page number.
        
        Returns:
            New page number
        """
        self.current_page_number += 1
        return self.current_page_number
    
    def reset(self) -> None:
        """Reset page engine for new document."""
        self.current_page_number = 1

