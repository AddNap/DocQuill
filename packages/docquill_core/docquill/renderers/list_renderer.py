"""Renderer for numbered and bulleted lists."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..engine.unified_layout import LayoutBlock
from ..engine.numbering_formatter import NumberingFormatter


class ListRenderer:
    """Renderer for list markers (bullets and numbering)."""

    def __init__(self, canvas, numbering_formatter: Optional[NumberingFormatter] = None) -> None:
        """Initialize list renderer.
        
        Args:
            canvas: Canvas object for drawing
            numbering_formatter: Optional NumberingFormatter for formatting markers
        """
        self.canvas = canvas
        self.numbering_formatter = numbering_formatter

    def draw(self, block: LayoutBlock) -> None:
        """Render list marker (bullet or numbering).
        
        Args:
            block: LayoutBlock with list marker information
        """
        if not block or not block.content:
            return
        
        # Extract marker information from block content
        marker_info = None
        if isinstance(block.content, dict):
            marker_info = block.content.get("marker_info") or block.content.get("numbering_info")
        
        if not marker_info:
            return
        
        # Get marker text
        marker_text = marker_info.get("text") or marker_info.get("marker_text")
        if not marker_text:
            return
        
        # Get marker position and style
        marker_x = block.frame.x if hasattr(block, "frame") else 0.0
        marker_y = block.frame.y if hasattr(block, "frame") else 0.0
        
        # Get font style from marker_info or block style
        style = block.style or {}
        marker_style = marker_info.get("style", {})
        
        font_name = marker_style.get("font_name") or style.get("font_name") or "Arial"
        font_size = float(marker_style.get("font_size") or style.get("font_size") or 12.0)
        font_color = marker_style.get("color") or style.get("color") or "#000000"
        
        # Render marker text
        try:
            # Use canvas.drawString or similar method
            if hasattr(self.canvas, "drawString"):
                self.canvas.drawString(marker_x, marker_y, marker_text)
            elif hasattr(self.canvas, "text"):
                # Alternative: use text method if available
                self.canvas.text(marker_x, marker_y, marker_text)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Failed to render list marker: {e}")

