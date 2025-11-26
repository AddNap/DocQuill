"""
Watermark model for DOCX documents.

Handles watermark functionality, properties, validation, and management.
"""

from typing import Dict, Any, Optional
from .base import Models
import logging

logger = logging.getLogger(__name__)


class Watermark(Models):
    """
    Represents a watermark in the document.
    
    Handles watermark functionality, properties, validation, and positioning.
    """
    
    def __init__(self, text: str = "", angle: float = 45.0, opacity: float = 0.5, 
                 color: str = "#CCCCCC", font_size: float = 72.0, font_name: str = "Arial"):
        """
        Initialize watermark.
        
        Args:
            text: Watermark text
            angle: Rotation angle in degrees (default: 45)
            opacity: Opacity value 0.0-1.0 (default: 0.5)
            color: Text color (default: light gray)
            font_size: Font size in points (default: 72)
            font_name: Font name (default: Arial)
        """
        super().__init__()
        self.text = text
        self.angle = float(angle)
        self.opacity = float(opacity)
        self.color = color
        self.font_size = float(font_size)
        self.font_name = font_name
        self.properties = {}
        self.validation_errors = []
        
        # Validate opacity
        if not 0.0 <= self.opacity <= 1.0:
            self.opacity = max(0.0, min(1.0, self.opacity))
            logger.warning(f"Opacity clamped to {self.opacity}")
        
        logger.debug(f"Watermark initialized: text='{text}', angle={angle}, opacity={opacity}")
    
    def set_text(self, text: str) -> None:
        """
        Set watermark text.
        
        Args:
            text: Watermark text
        """
        if not isinstance(text, str):
            raise ValueError("Watermark text must be a string")
        
        self.text = text
        logger.debug(f"Watermark text set to: {text}")
    
    def set_angle(self, angle: float) -> None:
        """
        Set rotation angle.
        
        Args:
            angle: Rotation angle in degrees
        """
        if not isinstance(angle, (int, float)):
            raise ValueError("Angle must be a number")
        
        self.angle = float(angle)
        logger.debug(f"Watermark angle set to: {angle}")
    
    def set_opacity(self, opacity: float) -> None:
        """
        Set opacity.
        
        Args:
            opacity: Opacity value 0.0-1.0
        """
        if not isinstance(opacity, (int, float)):
            raise ValueError("Opacity must be a number")
        
        self.opacity = max(0.0, min(1.0, float(opacity)))
        logger.debug(f"Watermark opacity set to: {self.opacity}")
    
    def set_color(self, color: str) -> None:
        """
        Set text color.
        
        Args:
            color: Color value (hex, rgb, etc.)
        """
        if not isinstance(color, str):
            raise ValueError("Color must be a string")
        
        self.color = color
        logger.debug(f"Watermark color set to: {color}")
    
    def set_font_size(self, font_size: float) -> None:
        """
        Set font size.
        
        Args:
            font_size: Font size in points
        """
        if not isinstance(font_size, (int, float)):
            raise ValueError("Font size must be a number")
        
        self.font_size = float(font_size)
        logger.debug(f"Watermark font size set to: {font_size}")
    
    def set_font_name(self, font_name: str) -> None:
        """
        Set font name.
        
        Args:
            font_name: Font name
        """
        if not isinstance(font_name, str):
            raise ValueError("Font name must be a string")
        
        self.font_name = font_name
        logger.debug(f"Watermark font name set to: {font_name}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert watermark to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'text': self.text,
            'angle': self.angle,
            'opacity': self.opacity,
            'color': self.color,
            'font_size': self.font_size,
            'font_name': self.font_name,
            'properties': self.properties.copy()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Watermark':
        """
        Create watermark from dictionary.
        
        Args:
            data: Dictionary with watermark data
            
        Returns:
            Watermark instance
        """
        return cls(
            text=data.get('text', ''),
            angle=data.get('angle', 45.0),
            opacity=data.get('opacity', 0.5),
            color=data.get('color', '#CCCCCC'),
            font_size=data.get('font_size', 72.0),
            font_name=data.get('font_name', 'Arial')
        )

