"""
PDF Footnote renderer for DOCX documents.

Handles rendering of footnotes at the bottom of PDF pages.
"""

from typing import Dict, Any, Optional, List, Tuple
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib import colors
import logging

logger = logging.getLogger(__name__)


class FootnotePDFRenderer:
    """
    Renderer for footnotes in PDF.
    
    Renders footnotes at the bottom of pages with proper formatting.
    """
    
    def __init__(self, footnote_renderer, canvas: Canvas, margins, page_height: float):
        """
        Initialize PDF footnote renderer.
        
        Args:
            footnote_renderer: FootnoteRenderer instance
            canvas: ReportLab Canvas
            margins: Margins object
            page_height: Page height in points
        """
        self.footnote_renderer = footnote_renderer
        self.canvas = canvas
        self.margins = margins
        self.page_height = page_height
        self.footnotes_per_page = {}  # Track footnotes per page
    
    def register_footnote_for_page(self, page_number: int, footnote_id: str):
        """
        Register a footnote for a specific page.
        
        Args:
            page_number: Page number (1-based)
            footnote_id: Footnote identifier
        """
        if page_number not in self.footnotes_per_page:
            self.footnotes_per_page[page_number] = []
        if footnote_id not in self.footnotes_per_page[page_number]:
            self.footnotes_per_page[page_number].append(footnote_id)
    
    def render_footnotes_for_page(self, page_number: int, footnote_area_height: float = 50.0) -> float:
        """
        Render footnotes for a specific page at the bottom.
        
        Args:
            page_number: Page number (1-based)
            footnote_area_height: Maximum height for footnotes area
            
        Returns:
            Actual height used for footnotes
        """
        if page_number not in self.footnotes_per_page:
            return 0.0
        
        footnote_ids = self.footnotes_per_page[page_number]
        if not footnote_ids:
            return 0.0
        
        # Calculate starting position (above footer margin)
        # Footnotes are rendered from bottom up
        start_y = self.margins.bottom + footnote_area_height
        current_y = start_y
        
        # Draw separator line
        line_y = self.margins.bottom + footnote_area_height - 5
        self.canvas.setStrokeColor(colors.grey)
        self.canvas.setLineWidth(0.5)
        content_width = self.page_width - self.margins.left - self.margins.right
        self.canvas.line(
            self.margins.left,
            line_y,
            self.margins.left + content_width,
            line_y
        )
        
        # Render each footnote
        font_size = 8.0
        line_height = font_size * 1.2
        self.canvas.setFont("Helvetica", font_size)
        self.canvas.setFillColor(colors.black)
        
        for footnote_id in sorted(footnote_ids, key=lambda x: self.footnote_renderer.get_footnote_number(x) or 0):
            footnote_data = self.footnote_renderer.footnotes.get(footnote_id)
            number = self.footnote_renderer.get_footnote_number(footnote_id) or "?"
            
            # Extract content
            content = ""
            if isinstance(footnote_data, dict):
                content = footnote_data.get('content', '')
                if isinstance(content, list):
                    content_parts = []
                    for para in content:
                        if isinstance(para, dict):
                            para_text = para.get('text', '') or para.get('runs', [{}])[0].get('text', '') if para.get('runs') else ''
                            content_parts.append(para_text)
                        else:
                            content_parts.append(str(para))
                    content = ' '.join(content_parts)
                elif not isinstance(content, str):
                    content = str(content)
            elif hasattr(footnote_data, 'content'):
                content = str(footnote_data.content)
            elif hasattr(footnote_data, 'get_content'):
                content = str(footnote_data.get_content())
            else:
                content = str(footnote_data) if footnote_data else "[Footnote not found]"
            
            # Render footnote marker and content
            marker_x = self.margins.left
            content_x = self.margins.left + 15  # Indent for content
            
            # Draw marker (superscript style)
            self.canvas.setFont("Helvetica-Bold", font_size)
            self.canvas.drawString(marker_x, current_y, str(number))
            
            # Draw content
            self.canvas.setFont("Helvetica", font_size)
            # Simple text wrapping (basic implementation)
            words = content.split()
            line = ""
            x = content_x
            y = current_y
            max_width = self.page_height - self.margins.left - self.margins.right - content_x
            
            for word in words:
                test_line = line + (" " if line else "") + word
                test_width = self.canvas.stringWidth(test_line, "Helvetica", font_size)
            
                if test_width > max_width and line:
                    # Draw current line
                    self.canvas.drawString(x, y, line)
                    y -= line_height
                    line = word
                else:
                    line = test_line
            
            # Draw last line
            if line:
                self.canvas.drawString(x, y, line)
                y -= line_height
            
            current_y = y - line_height * 0.5  # Space between footnotes
        
        # Return height used
        height_used = start_y - current_y + line_height
        return min(height_used, footnote_area_height)
    
    def clear_page_footnotes(self, page_number: int):
        """Clear footnotes for a page."""
        if page_number in self.footnotes_per_page:
            del self.footnotes_per_page[page_number]
    
    def get_footnotes_for_page(self, page_number: int) -> List[str]:
        """Get footnote IDs for a page."""
        return self.footnotes_per_page.get(page_number, []).copy()

