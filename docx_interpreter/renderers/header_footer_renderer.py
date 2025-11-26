"""Rendering utilities for headers and footers."""

from __future__ import annotations

from reportlab.pdfgen.canvas import Canvas
from typing import Optional, Dict, Any

from ..engine.unified_layout import LayoutBlock
from ..engine.geometry import Rect
from .render_utils import (
    draw_background,
    draw_border,
    draw_shadow,
    font_name_from_style,
    font_size_from_style,
    resolve_font_variant,
    resolve_padding,
    to_color,
)
from .field_renderer import FieldRenderer


class HeaderFooterRenderer:
    """Render header and footer blocks."""

    def __init__(self, canvas: Canvas, *, page_size, margins, context: Optional[Dict[str, Any]] = None) -> None:
        self.canvas = canvas
        self.page_width, self.page_height = page_size
        self.margins = margins
        self.field_renderer = FieldRenderer(context)

    def draw(self, block: LayoutBlock) -> None:
        text = ""
        if isinstance(block.content, dict):
            text = str(block.content.get("text", ""))
            # Sprawdź czy content ma field codes
            if 'fields' in block.content:
                # Renderuj field codes
                for field in block.content['fields']:
                    field_value = self.field_renderer.render_field(field)
                    text = text.replace(f"[{field.instr}]", field_value) if hasattr(field, 'instr') else text
        elif block.content is not None:
            text = str(block.content)
        
        # Zastąp field codes w tekście (fallback dla prostych przypadków)
        text = self.field_renderer.replace_fields_in_text(text)

        style = block.style or {}
        frame = self._translated_frame(block)

        draw_shadow(self.canvas, frame, style)
        draw_background(self.canvas, frame, style)
        draw_border(self.canvas, frame, style)

        base_font = font_name_from_style(style, default="DejaVuSans")
        font_size = font_size_from_style(style, default=10.0)
        bold = bool(style.get("bold") or style.get("font_weight") == "bold")
        italic = bool(style.get("italic") or style.get("font_style") == "italic")
        font_name = resolve_font_variant(base_font, bold=bold, italic=italic)
        color = to_color(style.get("color") or "#000000")

        self.canvas.setFont(font_name, font_size)
        self.canvas.setFillColor(color)

        pad_top, pad_right, pad_bottom, pad_left = resolve_padding(style)

        x = frame.x + pad_left
        alignment = (style.get("alignment") or style.get("text_align") or "left").lower()
        text_width = self.canvas.stringWidth(text, font_name, font_size)
        available_width = max(frame.width - pad_left - pad_right, 0.0)
        if alignment == "center":
            x = frame.x + pad_left + max((available_width - text_width) / 2.0, 0.0)
        elif alignment in {"right", "end"}:
            x = frame.x + pad_left + max(available_width - text_width, 0.0)

        if block.block_type == "header":
            y = self.page_height - self.margins.top + 10 - self.margins.bottom
        elif block.block_type == "footer":
            y = self.margins.bottom - block.frame.height - 10 - self.margins.bottom
        else:
            y = frame.y + pad_bottom

        self.canvas.drawString(x, y, text)

    def _translated_frame(self, block: LayoutBlock) -> Rect:
        left_margin = self.margins.left if self.margins else 0.0
        bottom_margin = self.margins.bottom if self.margins else 0.0
        return Rect(
            block.frame.x - left_margin,
            block.frame.y - bottom_margin,
            block.frame.width,
            block.frame.height,
        )

