"""Kerning engine for adjusting character spacing.

This engine handles:
- Kerning pairs (automatic spacing adjustment between characters)
- Manual kerning adjustments
- Character spacing (tracking)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .text_metrics import TextLayout, TextMetricsEngine


class KerningEngine:
    """Engine for handling kerning and character spacing."""
    
    def __init__(self, metrics_engine: TextMetricsEngine):
        """Initialize kerning engine.
        
        Args:
            metrics_engine: Text metrics engine for measuring text
        """
        self.metrics_engine = metrics_engine
    
    def apply_kerning(
        self,
        text: str,
        style: Optional[Dict[str, Any]] = None,
    ) -> TextLayout:
        """Apply kerning to text using HarfBuzz features.
        
        Args:
            text: Text to apply kerning to
            style: Style dictionary (may contain kerning settings)
            
        Returns:
            TextLayout with kerning applied
        """
        # Kerning is handled by HarfBuzz through features
        # Enable kerning feature if not explicitly disabled
        if style:
            # Check if kerning is explicitly disabled
            kerning_disabled = style.get("kerning", True) is False
            if kerning_disabled:
                # Disable kerning by not including kern feature
                features = style.get("harfbuzz_features") or []
                if "kern=0" not in features:
                    features = list(features) if isinstance(features, (list, tuple)) else []
                    features.append("kern=0")
                    style = {**style, "harfbuzz_features": features}
            else:
                # Enable kerning (default)
                features = style.get("harfbuzz_features") or []
                if isinstance(features, (list, tuple)):
                    features = list(features)
                else:
                    features = []
                
                # Add kern=1 if not present
                has_kern = any("kern" in str(f) for f in features)
                if not has_kern:
                    features.append("kern=1")
                    style = {**style, "harfbuzz_features": features}
        
        # Use TextMetricsEngine which handles kerning through HarfBuzz
        return self.metrics_engine.layout_text(text, style)
    
    def apply_character_spacing(
        self,
        text: str,
        spacing: float,
        style: Optional[Dict[str, Any]] = None,
    ) -> TextLayout:
        """Apply character spacing (tracking) to text.
        
        Args:
            text: Text to apply spacing to
            spacing: Additional spacing between characters in points
            style: Style dictionary
            
        Returns:
            TextLayout with character spacing applied
        """
        # Get base layout
        layout = self.metrics_engine.layout_text(text, style)
        
        # Adjust character positions by adding spacing
        if spacing != 0.0 and layout.glyphs:
            adjusted_glyphs = []
            cumulative_spacing = 0.0
            
            for glyph in layout.glyphs:
                # Add cumulative spacing to x position
                adjusted_x = glyph.x + cumulative_spacing
                adjusted_glyphs.append(
                    type(glyph)(
                        glyph_id=glyph.glyph_id,
                        cluster=glyph.cluster,
                        x=adjusted_x,
                        y=glyph.y,
                        x_advance=glyph.x_advance + spacing,
                        y_advance=glyph.y_advance,
                    )
                )
                cumulative_spacing += spacing
            
            # Recalculate width
            if adjusted_glyphs:
                last_glyph = adjusted_glyphs[-1]
                adjusted_width = last_glyph.x + last_glyph.x_advance
            else:
                adjusted_width = layout.width
            
            return TextLayout(
                glyphs=adjusted_glyphs,
                width=adjusted_width,
                height=layout.height,
                font_size=layout.font_size,
                direction=layout.direction,
            )
        
        return layout

