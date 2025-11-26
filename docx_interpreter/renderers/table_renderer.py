"""Rendering routines for table blocks."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.pdfgen.canvas import Canvas

from ..engine.unified_layout import LayoutBlock
from ..engine.geometry import Margins, Rect, twips_to_points
from .render_utils import (
    draw_background,
    draw_border,
    draw_shadow,
    font_name_from_style,
    font_size_from_style,
    resolve_padding,
    to_color,
    spacing_from_style,
)


class TableRenderer:
    """Render table blocks with basic styling."""

    def __init__(self, canvas: Canvas, margins: Margins | None = None) -> None:
        self.canvas = canvas
        self.margins = margins

    def draw(self, block: LayoutBlock) -> None:
        style = block.style or {}

        frame = self._translated_frame(block)

        draw_shadow(self.canvas, frame, style)
        draw_background(self.canvas, frame, style)
        draw_border(self.canvas, frame, style)

        rows = block.content.get("rows") or []
        if not rows:
            return

        data = []
        max_cols = 0
        for row in rows:
            cells = getattr(row, "cells", [])
            max_cols = max(max_cols, len(cells))
            row_data = []
            for cell in cells:
                if hasattr(cell, "get_text"):
                    row_data.append(cell.get_text() or "")
                elif hasattr(cell, "text"):
                    row_data.append(str(getattr(cell, "text")))
                else:
                    row_data.append(str(cell))
            data.append(row_data)

        if not data or max_cols == 0:
            return

        col_widths = self._column_widths(block, max_cols)
        table = Table(data, colWidths=col_widths)

        table_style_commands = self._base_table_style(style)
        table.setStyle(TableStyle(table_style_commands))

        table.wrapOn(self.canvas, frame.width, frame.height)
        table.drawOn(self.canvas, frame.x, frame.y)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _column_widths(self, block: LayoutBlock, max_cols: int) -> list[float]:
        """
        Calculate column widths for table.
        
        If grid widths are specified, use them. Otherwise, use auto-fit
        algorithm based on cell content.
        """
        grid = block.content.get("grid") if isinstance(block.content, dict) else None
        
        # If grid widths are explicitly specified, use them
        if isinstance(grid, list) and grid:
            widths = []
            has_explicit_widths = False
            for entry in grid[:max_cols]:
                width = entry.get("width") if isinstance(entry, dict) else None
                if width is None:
                    widths.append(None)  # Mark as auto-fit needed
                else:
                    has_explicit_widths = True
                    try:
                        numeric = float(width)
                    except (TypeError, ValueError):
                        widths.append(None)  # Mark as auto-fit needed
                    else:
                        widths.append(twips_to_points(numeric) if numeric > 1000 else numeric)
            
            # If all widths are explicit, scale and return
            if has_explicit_widths and all(w is not None for w in widths):
                if len(widths) == max_cols:
                    total = sum(widths)
                    if total > 0:
                        scale = block.frame.width / total
                        widths = [w * scale for w in widths]
                    return widths
            
            # Some columns need auto-fit - calculate based on content
            auto_fit_widths = self._calculate_auto_fit_widths(block, max_cols)
            
            # Merge explicit widths with auto-fit widths
            result = []
            for i in range(max_cols):
                if i < len(widths) and widths[i] is not None:
                    result.append(widths[i])
                elif i < len(auto_fit_widths):
                    result.append(auto_fit_widths[i])
                else:
                    result.append(block.frame.width / max_cols)
            
            # Scale to fit table width
            total = sum(result)
            if total > 0:
                scale = block.frame.width / total
                result = [w * scale for w in result]
            
            return result

        # No grid specified - use auto-fit
        widths = self._calculate_auto_fit_widths(block, max_cols)
        
        # Scale to fit table width
        total = sum(widths)
        if total > 0:
            scale = block.frame.width / total
            widths = [w * scale for w in widths]
        
        return widths
    
    def _calculate_auto_fit_widths(self, block: LayoutBlock, max_cols: int) -> list[float]:
        """
        Calculate column widths based on cell content (auto-fit).
        
        Algorithm:
        1. For each column, find the maximum content width
        2. Use ReportLab's stringWidth for accurate text measurement
        3. Add padding to account for cell padding
        4. Return proportional widths
        """
        from reportlab.pdfbase.pdfmetrics import stringWidth
        
        rows = block.content.get("rows") or []
        if not rows:
            # Fallback: equal widths
            return [block.frame.width / max_cols for _ in range(max_cols)]
        
        # Get font metrics for text width calculation
        style = block.style or {}
        font_name = font_name_from_style(style, default="DejaVuSans")
        font_size = font_size_from_style(style, default=9)
        
        # Calculate padding
        pad_top, pad_right, pad_bottom, pad_left = resolve_padding(style)
        padding = pad_left + pad_right
        
        # Track maximum content width per column
        col_max_widths = [0.0] * max_cols
        
        for row in rows:
            cells = getattr(row, "cells", [])
            for col_idx, cell in enumerate(cells):
                if col_idx >= max_cols:
                    break
                
                # Get cell text
                cell_text = ""
                if hasattr(cell, "get_text"):
                    cell_text = cell.get_text() or ""
                elif hasattr(cell, "text"):
                    cell_text = str(getattr(cell, "text", ""))
                elif isinstance(cell, dict):
                    cell_text = str(cell.get("text", ""))
                else:
                    cell_text = str(cell)
                
                # Calculate text width using ReportLab's stringWidth
                # This gives accurate measurement based on font metrics
                try:
                    text_width = stringWidth(cell_text, font_name, font_size)
                except Exception:
                    # Fallback: estimate based on character count
                    # Average character width is roughly 0.6 * font_size for most fonts
                    char_width = font_size * 0.6
                    text_width = len(cell_text) * char_width
                
                # Add padding
                cell_width = text_width + padding
                
                # Update maximum for this column
                col_max_widths[col_idx] = max(col_max_widths[col_idx], cell_width)
        
        # Ensure minimum width for each column
        min_width = 20.0  # Minimum 20 points
        col_max_widths = [max(w, min_width) for w in col_max_widths]
        
        # If all columns are empty, use equal widths
        if sum(col_max_widths) == 0:
            return [block.frame.width / max_cols for _ in range(max_cols)]
        
        return col_max_widths

    def _base_table_style(self, style: dict) -> list[tuple]:
        commands: list[tuple] = []

        font_name = font_name_from_style(style, default="DejaVuSans")
        font_size = font_size_from_style(style, default=9)
        commands.append(("FONT", (0, 0), (-1, -1), font_name, font_size))

        pad_top, pad_right, pad_bottom, pad_left = resolve_padding(style)
        commands.extend(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), pad_left),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad_right),
                ("TOPPADDING", (0, 0), (-1, -1), pad_top),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad_bottom),
            ]
        )

        border_color = colors.grey
        border_width = 0.3
        borders = style.get("borders") or style.get("border")
        if isinstance(borders, dict):
            general = borders.get("all") or borders.get("default") or {}
            if isinstance(general, dict):
                color_val = general.get("color") or general.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color")
                width_val = general.get("width") or general.get("sz")
                if color_val:
                    border_color = to_color(color_val, fallback="#6c6c6c")
                if width_val:
                    try:
                        border_width = float(width_val)
                        if border_width > 10:
                            border_width = border_width / 20.0
                    except (TypeError, ValueError):
                        border_width = 0.3

        commands.append(("GRID", (0, 0), (-1, -1), border_width, border_color))
        commands.append(("BOX", (0, 0), (-1, -1), border_width, border_color))

        shading = style.get("shading") or {}
        fill_color = shading.get("fill") or shading.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill")
        if fill_color:
            commands.append(("BACKGROUND", (0, 0), (-1, -1), to_color(fill_color, fallback="#FFFFFF")))

        row_spacing = spacing_from_style(style, "after")
        if row_spacing:
            commands.append(("BOTTOMPADDING", (0, 0), (-1, -1), pad_bottom + row_spacing))

        return commands

    def _translated_frame(self, block: LayoutBlock) -> Rect:
        left_margin = self.margins.left if self.margins else 0.0
        bottom_margin = self.margins.bottom if self.margins else 0.0
        return Rect(
            block.frame.x - left_margin,
            block.frame.y - bottom_margin,
            block.frame.width,
            block.frame.height,
        )

    def _normalize_width(self, value: Any, content_width: float) -> float:
        # Percentage specified as string (e.g. "50%")
        if isinstance(value, str):
            token = value.strip()
            if token.endswith("%"):
                try:
                    percentage = float(token[:-1]) / 100.0
                    return max(content_width * percentage, 0.0)
                except ValueError:
                    return content_width

        # Percentage represented as dictionary from DOCX
        if isinstance(value, dict):
            unit = (value.get("type") or value.get("unit") or "").lower()
            numeric = value.get("value") or value.get("w")
            if unit in {"pct", "percentage"} and numeric is not None:
                try:
                    percentage = float(numeric)
                except (TypeError, ValueError):
                    percentage = 0.0
                if percentage > 1:
                    percentage = percentage / 10000.0 if percentage > 100 else percentage / 100.0
                return max(content_width * max(percentage, 0.0), 0.0)
            value = numeric

        width = self._normalize_dimension(value)
        if 0 < width <= 1.0:
            # Treat values between 0 and 1 as ratio of available width
            return max(content_width * width, 0.0)
        if width <= 0:
            return content_width
        return min(width, content_width)

    def _normalize_dimension(self, value: Any) -> float:
        if value is None:
            return 0.0

        if isinstance(value, str):
            unit = value.strip().lower()
            if unit.endswith("%"):
                try:
                    return float(unit[:-1]) / 100.0
                except ValueError:
                    return 0.0
            if unit.endswith("pt"):
                try:
                    return float(unit[:-2])
                except ValueError:
                    return 0.0
            try:
                numeric = float(unit)
            except ValueError:
                return 0.0
            return self._normalize_dimension(numeric)

        if isinstance(value, (int, float)):
            numeric = float(value)
            if numeric > 1000:  # likely twips
                return twips_to_points(numeric)
            return numeric

        return 0.0

