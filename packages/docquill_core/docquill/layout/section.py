"""
Section model for DOCX documents.

Handles section properties, page layout, headers/footers, and columns.
"""

from typing import Dict, Any, Optional, List
import logging
from enum import Enum
from .page import Page, Orientation, PageSize

logger = logging.getLogger(__name__)

class ColumnLayout(Enum):
    """Column layout options."""
    SINGLE = "single"
    TWO_COLUMNS = "two_columns"
    THREE_COLUMNS = "three_columns"
    CUSTOM = "custom"

class Section:
    """
    Represents a section in the document.
    
    Handles section properties, page layout, headers/footers, and columns.
    """
    
    def __init__(self, section_number: int = 1):
        """
        Initialize section.
        
        Args:
            section_number: Section number
        """
        self.section_number = section_number
        
        # Page properties
        self.page_width = 210.0  # A4 width in mm
        self.page_height = 297.0  # A4 height in mm
        self.orientation = Orientation.PORTRAIT
        
        # Margins
        self.margin_top = 25.4
        self.margin_right = 25.4
        self.margin_bottom = 25.4
        self.margin_left = 25.4
        
        # Column layout
        self.column_layout = ColumnLayout.SINGLE
        self.column_count = 1
        self.column_spacing = 0.0  # mm between columns
        
        # Headers and footers
        self.headers = {}
        self.footers = {}
        
        # Section content
        self.pages = []
        self.content = []
        
        logger.debug(f"Section {section_number} initialized")
    
    # Properties for compatibility with tests
    @property
    def page_width_mm(self) -> float:
        """Page width in mm."""
        return self.page_width
    
    @property
    def page_height_mm(self) -> float:
        """Page height in mm."""
        return self.page_height
    
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
    
    @property
    def column_spacing_mm(self) -> float:
        """Column spacing in mm."""
        return self.column_spacing
    
    def set_page_size(self, width, height=None) -> None:
        """
        Set page size for section.
        
        Args:
            width: Page width in mm or PageSize enum
            height: Page height in mm (if width is not PageSize enum)
        """
        if isinstance(width, PageSize):
            # Handle PageSize enum
            self.page_width, self.page_height = width.value
        else:
            # Handle numeric values
            if height is None:
                raise ValueError("Height must be provided when width is numeric")
            self.page_width = width
            self.page_height = height
        
        logger.debug(f"Page size set to {self.page_width}x{self.page_height}mm")
    
    def set_page_margins(self, margins) -> None:
        """
        Set page margins for section.
        
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
        
        logger.debug(f"Margins set to T:{self.margin_top} R:{self.margin_right} B:{self.margin_bottom} L:{self.margin_left}mm")
    
    def set_orientation(self, orientation: Orientation) -> None:
        """
        Set page orientation for section.
        
        Args:
            orientation: Page orientation
        """
        if orientation == Orientation.LANDSCAPE and self.orientation == Orientation.PORTRAIT:
            # Swap width and height
            self.page_width, self.page_height = self.page_height, self.page_width
        elif orientation == Orientation.PORTRAIT and self.orientation == Orientation.LANDSCAPE:
            # Swap width and height back
            self.page_width, self.page_height = self.page_height, self.page_width
        
        self.orientation = orientation
        logger.debug(f"Orientation set to {orientation.value}")
    
    def set_columns(self, layout, column_count: int = None, spacing: float = 6.35) -> None:
        """
        Set column layout for section.
        
        Args:
            layout: ColumnLayout enum or column count
            column_count: Number of columns (if layout is not ColumnLayout enum)
            spacing: Spacing between columns in mm
        """
        if isinstance(layout, ColumnLayout):
            # Handle ColumnLayout enum
            self.column_layout = layout
            if column_count is None:
                if layout == ColumnLayout.SINGLE:
                    self.column_count = 1
                elif layout == ColumnLayout.TWO_COLUMNS:
                    self.column_count = 2
                elif layout == ColumnLayout.THREE_COLUMNS:
                    self.column_count = 3
                else:
                    self.column_count = 1
            else:
                self.column_count = max(1, column_count)
        else:
            # Handle numeric column count
            self.column_count = max(1, layout)
            if self.column_count == 1:
                self.column_layout = ColumnLayout.SINGLE
            elif self.column_count == 2:
                self.column_layout = ColumnLayout.TWO_COLUMNS
            elif self.column_count == 3:
                self.column_layout = ColumnLayout.THREE_COLUMNS
            else:
                self.column_layout = ColumnLayout.CUSTOM
        
        self.column_spacing = spacing
        
        logger.debug(f"Column layout set to {self.column_count} columns with {spacing}mm spacing")
    
    def add_header(self, header_type: str, header) -> None:
        """
        Add header to section.
        
        Args:
            header_type: Type of header ('first', 'odd', 'even')
            header: Header content
        """
        if isinstance(header, dict):
            header['section'] = self.section_number
            header['type'] = 'header'
            header['header_type'] = header_type
            self.headers[header_type] = header
        else:
            # Handle object header
            self.headers[header_type] = header
        
        logger.debug(f"Header added: {header_type}")
    
    def add_footer(self, footer_type: str, footer) -> None:
        """
        Add footer to section.
        
        Args:
            footer_type: Type of footer ('first', 'odd', 'even')
            footer: Footer content
        """
        if isinstance(footer, dict):
            footer['section'] = self.section_number
            footer['type'] = 'footer'
            footer['footer_type'] = footer_type
            self.footers[footer_type] = footer
        else:
            # Handle object footer
            self.footers[footer_type] = footer
        
        logger.debug(f"Footer added: {footer_type}")
    
    def create_page(self, page_number: int = None) -> Page:
        """
        Create a new page for this section.
        
        Args:
            page_number: Page number (defaults to next available)
            
        Returns:
            New Page instance
        """
        if page_number is None:
            page_number = len(self.pages) + 1
        
        page = Page(
            page_number=page_number,
            width=self.page_width,
            height=self.page_height
        )
        
        # Set page properties
        page.set_orientation(self.orientation)
        page.set_margins({
            'top': self.margin_top,
            'right': self.margin_right,
            'bottom': self.margin_bottom,
            'left': self.margin_left
        })
        
        # Add headers and footers
        if page_number == 1 and self.headers.get('first'):
            page.add_header('first', self.headers['first'])
        elif page_number % 2 == 1 and self.headers.get('odd'):
            page.add_header('odd', self.headers['odd'])
        elif page_number % 2 == 0 and self.headers.get('even'):
            page.add_header('even', self.headers['even'])
        
        if page_number == 1 and self.footers.get('first'):
            page.add_footer('first', self.footers['first'])
        elif page_number % 2 == 1 and self.footers.get('odd'):
            page.add_footer('odd', self.footers['odd'])
        elif page_number % 2 == 0 and self.footers.get('even'):
            page.add_footer('even', self.footers['even'])
        
        self.pages.append(page)
        logger.debug(f"Page {page_number} created for section {self.section_number}")
        return page
    
    def get_column_width(self) -> float:
        """Calculate column width based on current settings."""
        if self.column_count == 1:
            return self.page_width - self.margin_left - self.margin_right
        
        total_spacing = (self.column_count - 1) * self.column_spacing
        available_width = self.page_width - self.margin_left - self.margin_right - total_spacing
        return available_width / self.column_count
    
    def get_column_positions(self) -> List[float]:
        """Get x positions for each column."""
        positions = []
        column_width = self.get_column_width()
        
        for i in range(self.column_count):
            x = self.margin_left + i * (column_width + self.column_spacing)
            positions.append(x)
        
        return positions
    
    def get_section_info(self) -> Dict[str, Any]:
        """Get complete section information."""
        return {
            'section_number': self.section_number,
            'page_size': {
                'width': self.page_width,
                'height': self.page_height
            },
            'page_width_mm': self.page_width_mm,
            'page_height_mm': self.page_height_mm,
            'orientation': self.orientation.value,
            'margins': {
                'top': self.margin_top,
                'right': self.margin_right,
                'bottom': self.margin_bottom,
                'left': self.margin_left
            },
            'column_layout': self.column_layout.value,
            'columns': {
                'count': self.column_count,
                'spacing': self.column_spacing,
                'width': self.get_column_width(),
                'positions': self.get_column_positions()
            },
            'headers': {k: v is not None for k, v in self.headers.items()},
            'footers': {k: v is not None for k, v in self.footers.items()},
            'page_count': len(self.pages)
        }
    
    def get_headers(self, header_type: Optional[str] = None) -> Dict[str, Any]:
        """Get section headers."""
        if header_type:
            return {header_type: self.headers.get(header_type)}
        return {k: v for k, v in self.headers.items() if v is not None}
    
    def get_footers(self, footer_type: Optional[str] = None) -> Dict[str, Any]:
        """Get section footers."""
        if footer_type:
            return {footer_type: self.footers.get(footer_type)}
        return {k: v for k, v in self.footers.items() if v is not None}
    
    def clear_content(self) -> None:
        """Clear all content from section."""
        self.pages.clear()
        self.content.clear()
        self.headers.clear()
        self.footers.clear()
        logger.debug(f"Section {self.section_number} content cleared")
