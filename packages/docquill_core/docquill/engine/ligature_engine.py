"""Ligature engine for handling typographic ligatures.

This engine handles:
- Ligature substitution (fi, fl, ffi, etc.)
- Ligature application through HarfBuzz
- Ligature detection and rendering
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .text_metrics import TextLayout, TextMetricsEngine


class LigatureEngine:
    """Engine for handling ligatures and typographic features."""
    
    def __init__(self, metrics_engine: TextMetricsEngine):
        """Initialize ligature engine.
        
        Args:
            metrics_engine: Text metrics engine for measuring text
        """
        self.metrics_engine = metrics_engine
    
    def apply_ligatures(
        self,
        text: str,
        style: Optional[Dict[str, Any]] = None,
    ) -> TextLayout:
        """Apply ligatures to text using HarfBuzz features.
        
        Args:
            text: Text to apply ligatures to
            style: Style dictionary (may contain ligature settings)
            
        Returns:
            TextLayout with ligatures applied
        """
        # Ligatures are handled by HarfBuzz through features
        # Enable ligature feature if not explicitly disabled
        if style:
            # Check if ligatures are explicitly disabled
            ligatures_disabled = style.get("ligatures", True) is False
            if ligatures_disabled:
                # Disable ligatures by not including liga feature
                features = style.get("harfbuzz_features") or []
                if isinstance(features, (list, tuple)):
                    features = list(features)
                else:
                    features = []
                
                # Add liga=0 if not present
                has_liga = any("liga" in str(f) for f in features)
                if not has_liga:
                    features.append("liga=0")
                    style = {**style, "harfbuzz_features": features}
            else:
                # Enable ligatures (default)
                features = style.get("harfbuzz_features") or []
                if isinstance(features, (list, tuple)):
                    features = list(features)
                else:
                    features = []
                
                # Add liga=1 if not present
                has_liga = any("liga" in str(f) for f in features)
                if not has_liga:
                    features.append("liga=1")
                    style = {**style, "harfbuzz_features": features}
        
        # Use TextMetricsEngine which handles ligatures through HarfBuzz
        return self.metrics_engine.layout_text(text, style)
    
    def detect_ligatures(self, text: str) -> List[tuple[int, int, str]]:
        """Detect potential ligature opportunities in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of (start_index, end_index, ligature_type) tuples
        """
        ligatures = []
        
        # Common ligature patterns
        ligature_patterns = {
            "fi": ("f", "i"),
            "fl": ("f", "l"),
            "ff": ("f", "f"),
            "ffi": ("f", "f", "i"),
            "ffl": ("f", "f", "l"),
            "ft": ("f", "t"),
        }
        
        for ligature_type, pattern in ligature_patterns.items():
            pattern_text = "".join(pattern)
            start = 0
            while True:
                idx = text.find(pattern_text, start)
                if idx == -1:
                    break
                ligatures.append((idx, idx + len(pattern_text), ligature_type))
                start = idx + 1
        
        return ligatures

