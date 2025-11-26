"""
Watermark renderer for HTML and PDF output.
"""

from typing import Dict, Any, Optional
from html import escape
import logging

logger = logging.getLogger(__name__)


class WatermarkRenderer:
    """Renderer for watermarks in HTML and PDF."""
    
    def __init__(self, watermarks: Optional[list] = None):
        """
        Initialize watermark renderer.
        
        Args:
            watermarks: List of watermark objects or dictionaries
        """
        self.watermarks = watermarks or []
    
    def add_watermark(self, watermark: Any) -> None:
        """
        Add watermark to renderer.
        
        Args:
            watermark: Watermark object or dictionary
        """
        self.watermarks.append(watermark)
    
    def render_html(self, page_width: float = 210.0, page_height: float = 297.0) -> str:
        """
        Render watermarks as HTML.
        
        Args:
            page_width: Page width in mm
            page_height: Page height in mm
            
        Returns:
            HTML string with watermark elements
        """
        if not self.watermarks:
            return ""
        
        watermark_html = []
        for watermark in self.watermarks:
            # Extract watermark properties
            if isinstance(watermark, dict):
                text = watermark.get('text', '')
                angle = watermark.get('angle', 45.0)
                opacity = watermark.get('opacity', 0.5)
                color = watermark.get('color', '#CCCCCC')
                font_size = watermark.get('font_size', 72.0)
                font_name = watermark.get('font_name', 'Arial')
            elif hasattr(watermark, 'text'):
                text = watermark.text
                angle = getattr(watermark, 'angle', 45.0)
                opacity = getattr(watermark, 'opacity', 0.5)
                color = getattr(watermark, 'color', '#CCCCCC')
                font_size = getattr(watermark, 'font_size', 72.0)
                font_name = getattr(watermark, 'font_name', 'Arial')
            else:
                text = str(watermark)
                angle = 45.0
                opacity = 0.5
                color = '#CCCCCC'
                font_size = 72.0
                font_name = 'Arial'
            
            if not text:
                continue
            
            # Convert mm to pixels (approximate: 1mm ≈ 3.78px at 96dpi)
            width_px = page_width * 3.78
            height_px = page_height * 3.78
            
            # Center position
            center_x = width_px / 2
            center_y = height_px / 2
            
            # Create watermark HTML with absolute positioning and rotation
            watermark_html.append(
                f'<div class="watermark" '
                f'style="position: absolute; '
                f'top: 0; left: 0; width: {width_px}px; height: {height_px}px; '
                f'pointer-events: none; z-index: -1; overflow: hidden;">'
                f'<div style="position: absolute; '
                f'top: 50%; left: 50%; '
                f'transform: translate(-50%, -50%) rotate({angle}deg); '
                f'color: {color}; '
                f'opacity: {opacity}; '
                f'font-size: {font_size}pt; '
                f'font-family: {escape(font_name)}; '
                f'font-weight: bold; '
                f'white-space: nowrap; '
                f'user-select: none;">'
                f'{escape(text)}'
                f'</div></div>'
            )
        
        return '\n'.join(watermark_html)
    
    def get_watermark_css(self) -> str:
        """
        Get CSS for watermarks.
        
        Returns:
            CSS string
        """
        return """
        <style>
        .watermark {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: -1;
            overflow: hidden;
        }
        </style>
        """
    
    def render_pdf(self, canvas, page_width: float, page_height: float) -> None:
        """
        Render watermarks on PDF canvas.
        
        Args:
            canvas: ReportLab Canvas object
            page_width: Page width in points
            page_height: Page height in points
        """
        if not self.watermarks:
            return
        
        for watermark in self.watermarks:
            # Extract watermark properties
            if isinstance(watermark, dict):
                text = watermark.get('text', '')
                angle = watermark.get('angle', 45.0)
                opacity = watermark.get('opacity', 0.5)
                color = watermark.get('color', '#CCCCCC')
                font_size = watermark.get('font_size', 72.0)
                font_name = watermark.get('font_name', 'Helvetica-Bold')
            elif hasattr(watermark, 'text'):
                text = watermark.text
                angle = getattr(watermark, 'angle', 45.0)
                opacity = getattr(watermark, 'opacity', 0.5)
                color = getattr(watermark, 'color', '#CCCCCC')
                font_size = getattr(watermark, 'font_size', 72.0)
                font_name = getattr(watermark, 'font_name', 'Helvetica-Bold')
            else:
                text = str(watermark)
                angle = 45.0
                opacity = 0.5
                color = '#CCCCCC'
                font_size = 72.0
                font_name = 'Helvetica-Bold'
            
            if not text:
                continue
            
            # Save canvas state
            canvas.saveState()
            
            # Set opacity
            from reportlab.lib import colors
            try:
                # Parse color
                if color.startswith('#'):
                    rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
                    watermark_color = colors.Color(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0, alpha=opacity)
                else:
                    watermark_color = colors.Color(0.8, 0.8, 0.8, alpha=opacity)
            except Exception:
                watermark_color = colors.Color(0.8, 0.8, 0.8, alpha=opacity)
            
            canvas.setFillColor(watermark_color)
            canvas.setStrokeColor(watermark_color)
            
            # Center position
            center_x = page_width / 2
            center_y = page_height / 2
            
            # Translate to center and rotate
            canvas.translate(center_x, center_y)
            canvas.rotate(angle)
            
            # Set font
            try:
                canvas.setFont(font_name, font_size)
            except Exception:
                canvas.setFont('Helvetica-Bold', font_size)
            
            # Calculate text width for centering
            text_width = canvas.stringWidth(text, font_name, font_size)
            
            # Draw text centered
            canvas.drawString(-text_width / 2, -font_size / 2, text)
            
            # Restore canvas state
            canvas.restoreState()

