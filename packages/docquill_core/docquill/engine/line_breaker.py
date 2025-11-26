"""Paragraph line breaking utilities with optional hyphenation support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

try:  # pragma: no cover - optional dependency
    import pyphen
except ImportError:  # pragma: no cover - optional dependency
    pyphen = None  # type: ignore

from .text_metrics import TextLayout, TextMetricsEngine


@dataclass(slots=True)
class LineBreakResult:
    text: str
    layout: TextLayout
    hyphenated: bool = False


class LineBreaker:
    """Simple greedy line breaker with optional hyphenation."""

    def __init__(
        self,
        metrics_engine: TextMetricsEngine,
        *,
        hyphen_lang: Optional[str] = None,
        justify: bool = False,
    ) -> None:
        self.metrics_engine = metrics_engine
        self.hyphen_lang = hyphen_lang
        self.justify = justify
        self._hyphenator = self._create_hyphenator(hyphen_lang)

    def break_text(self, text: str, max_width: float, style: Optional[dict] = None) -> List[LineBreakResult]:
        if not text:
            layout = self.metrics_engine.layout_text("", style)
            return [LineBreakResult(text="", layout=layout)]

        # Debug: log if max_width seems too large
        if max_width > 1000 and len(text) > 100:
            import logging
            logger = logging.getLogger("docx_interpreter.engine.line_breaker")
            logger.warning(f"⚠️ break_text called with very large max_width={max_width:.2f} for text length={len(text)}. This may prevent line breaking.")

        words = text.split()
        lines: List[LineBreakResult] = []
        current_line = ""
        current_layout = self.metrics_engine.layout_text("", style)

        for word in words:
            # Calculate candidate line with this word added
            candidate = f"{current_line} {word}".strip() if current_line else word
            layout = self.metrics_engine.layout_text(candidate, style)

            # Check if candidate fits in max_width
            if layout.width <= max_width:
                # Candidate fits - use it
                current_line = candidate
                current_layout = layout
                continue
            
            # Debug: log when line breaking occurs
            if len(candidate) > 50 and len(current_line) > 0:
                import logging
                logger = logging.getLogger("docx_interpreter.engine.line_breaker")
                logger.debug(f"Line break: candidate width={layout.width:.2f} > max_width={max_width:.2f}, breaking at '{current_line[:30]}...'")
            
            # Candidate doesn't fit - need to break line
            if current_line:
                # Add current line to results and start new line with this word
                lines.append(LineBreakResult(text=current_line, layout=current_layout))
                current_line = word
                current_layout = self.metrics_engine.layout_text(current_line, style)
                
                # If word itself doesn't fit, add it anyway (better than losing it)
                if current_layout.width > max_width:
                    # Word is too long - still add it but log a warning
                    lines.append(LineBreakResult(text=current_line, layout=current_layout))
                    current_line = ""
                    current_layout = self.metrics_engine.layout_text("", style)
            else:
                # First word doesn't fit - add it anyway (better than losing it)
                lines.append(LineBreakResult(text=word, layout=layout))
                current_line = ""
                current_layout = self.metrics_engine.layout_text("", style)

        if current_line:
            lines.append(LineBreakResult(text=current_line, layout=current_layout))

        return lines

    def _create_hyphenator(self, language: Optional[str]):  # pragma: no cover - optional dependency
        if not language or pyphen is None:
            return None
        try:
            return pyphen.Pyphen(lang=language)
        except KeyError:
            return None

