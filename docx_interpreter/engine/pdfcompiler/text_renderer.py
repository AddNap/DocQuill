"""Text renderer for PDF - handles runs and decorators."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Union

from .objects import PdfStream
from .resources import PdfFont, PdfFontRegistry
from .utils import escape_pdf_string, hex_to_rgb, format_pdf_number


class PdfTextRenderer:
    """Renders text runs with decorators (bold, italic, underline, etc.)."""
    
    def __init__(self, font_registry: PdfFontRegistry):
        """Initialize text renderer.
        
        Args:
            font_registry: Font registry for font management
        """
        self.font_registry = font_registry
    
    def render_run(
        self,
        stream: PdfStream,
        text: str,
        x: float,
        y: float,
        style: Dict,
    ) -> float:
        """Render a text run with all decorators.
        
        Args:
            stream: PDF stream to add commands to
            text: Text content
            x: X position
            y: Y position
            style: Style dictionary with font, size, color, etc.
            
        Returns:
            Width of rendered text (for positioning next runs)
        """
        def _format_rgb(values: Tuple[float, float, float], operator: str) -> str:
            return (
                f"{format_pdf_number(values[0])} "
                f"{format_pdf_number(values[1])} "
                f"{format_pdf_number(values[2])} {operator}"
            )

        def _resolve_float(value: Union[str, float, int, None], default: float = 0.0) -> float:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value.strip())
                except (TypeError, ValueError):
                    return default
            return default

        def _resolve_color_tuple(
            value: Union[str, Tuple[float, float, float], Dict[str, Any], None],
            default: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        ) -> Tuple[float, float, float]:
            if value is None:
                return default
            if isinstance(value, tuple) and len(value) >= 3:
                r, g, b = value[:3]
                if max(r, g, b) > 1.0:
                    r = float(r) / 255.0
                    g = float(g) / 255.0
                    b = float(b) / 255.0
                return (float(r), float(g), float(b))
            if isinstance(value, dict):
                try:
                    r = float(value.get("r"))
                    g = float(value.get("g"))
                    b = float(value.get("b"))
                    if max(r, g, b) > 1.0:
                        r /= 255.0
                        g /= 255.0
                        b /= 255.0
                    return (r, g, b)
                except (TypeError, ValueError):
                    pass
            if isinstance(value, str):
                normalized = value.strip().lower()
                if not normalized:
                    return default
                highlight_map = {
                    "yellow": "#fff200",
                    "green": "#00ff00",
                    "cyan": "#00ffff",
                    "magenta": "#ff00ff",
                    "blue": "#0000ff",
                    "red": "#ff0000",
                    "darkblue": "#000080",
                    "darkcyan": "#008080",
                    "darkgreen": "#006400",
                    "darkmagenta": "#800080",
                    "darkred": "#800000",
                    "darkyellow": "#808000",
                    "gray": "#808080",
                    "darkgray": "#a9a9a9",
                    "lightgray": "#d3d3d3",
                    "black": "#000000",
                    "white": "#ffffff",
                    "auto": None,
                    "none": None,
                    "transparent": None,
                }
                mapped = highlight_map.get(normalized, value)
                if mapped is None:
                    return default
                if isinstance(mapped, str):
                    return hex_to_rgb(mapped, default=default)
            return hex_to_rgb(str(value), default=default)

        style = style or {}

        # Resolve font attributes
        font_name = (
            style.get("font_name")
            or style.get("font_pdf_name")
            or style.get("font_family")
            or "Helvetica"
        )
        bold = bool(style.get("bold") or style.get("font_weight") == "bold")
        italic = bool(style.get("italic") or style.get("font_style") == "italic")
        base_font_size = float(style.get("font_size") or style.get("size") or 11.0)
        font = self.font_registry.register_font(font_name, bold=bold, italic=italic)

        # Resolve color
        color_value = (
            style.get("color")
            or style.get("font_color")
            or style.get("foreground")
            or "#000000"
        )
        rgb = _resolve_color_tuple(color_value, default=(0.0, 0.0, 0.0))

        # Superscript / subscript adjustments
        superscript = bool(
            style.get("superscript")
            or style.get("vertical_align") == "superscript"
        )
        subscript = bool(
            style.get("subscript") or style.get("vertical_align") == "subscript"
        )

        baseline_shift = _resolve_float(
            style.get("baseline_shift") or style.get("baseline_adjust"), 0.0
        )
        effective_font_size = base_font_size

        if superscript:
            baseline_shift += base_font_size * 0.35
            effective_font_size = base_font_size * 0.65
        elif subscript:
            baseline_shift -= base_font_size * 0.25
            effective_font_size = base_font_size * 0.65

        text_baseline = y + baseline_shift

        # Resolve run width (prefer provided metrics)
        width_candidates = [
            style.get("run_width"),
            style.get("text_width"),
            style.get("width"),
        ]
        text_width = None
        for candidate in width_candidates:
            if isinstance(candidate, (int, float)) and candidate > 0:
                text_width = float(candidate)
                break
            if isinstance(candidate, str):
                try:
                    candidate_float = float(candidate.strip())
                    if candidate_float > 0:
                        text_width = candidate_float
                        break
                except (TypeError, ValueError):
                    continue
        if text_width is None:
            # Fallback heuristics
            approx_size = effective_font_size if superscript or subscript else base_font_size
            text_width = max(len(text), 1) * approx_size * 0.6

        # --- Render background / highlight ---
        background_value = style.get("background") or style.get("background_color")
        highlight_value = style.get("highlight") or style.get("highlight_color")
        rect_height = effective_font_size * 1.2
        rect_bottom = text_baseline - effective_font_size * 0.85

        for bg_candidate in (background_value, highlight_value):
            if not bg_candidate:
                continue
            bg_rgb = _resolve_color_tuple(bg_candidate, default=None)
            if not bg_rgb:
                continue
            stream.write(_format_rgb(bg_rgb, "rg"))
            stream.write(
                f"{format_pdf_number(x)} {format_pdf_number(rect_bottom)} "
                f"{format_pdf_number(text_width)} {format_pdf_number(rect_height)} re f"
            )
            # Reset fill color (black) before drawing text; actual text color will be set below
            stream.write("0 0 0 rg")
            break  # Prefer first available background source

        # --- Render shadow ---
        shadow_spec = style.get("shadow")
        if shadow_spec:
            if isinstance(shadow_spec, dict):
                shadow_color = shadow_spec.get("color") or shadow_spec.get("fill") or "#777777"
                offset_x = _resolve_float(
                    shadow_spec.get("offset_x")
                    or shadow_spec.get("x")
                    or shadow_spec.get("distance")
                    or 0.8,
                    0.8,
                )
                offset_y = _resolve_float(
                    shadow_spec.get("offset_y")
                    or shadow_spec.get("y")
                    or shadow_spec.get("distance_y")
                    or -0.8,
                    -0.8,
                )
            else:
                shadow_color = "#777777"
                offset_x = 0.8
                offset_y = -0.8

            shadow_rgb = _resolve_color_tuple(shadow_color, default=(0.5, 0.5, 0.5))
            stream.write(_format_rgb(shadow_rgb, "rg"))
            stream.write("BT")
            stream.write(f"{font.alias} {format_pdf_number(effective_font_size)} Tf")
            stream.write(
                f"{format_pdf_number(x + offset_x)} {format_pdf_number(text_baseline + offset_y)} Td"
            )
            stream.write(f"({escape_pdf_string(text)}) Tj")
            stream.write("ET")

        # --- Render main text ---
        if rgb != (0.0, 0.0, 0.0):
            stream.write(_format_rgb(rgb, "rg"))

        stream.write("BT")
        stream.write(f"{font.alias} {format_pdf_number(effective_font_size)} Tf")
        stream.write(f"{format_pdf_number(x)} {format_pdf_number(text_baseline)} Td")
        stream.write(f"({escape_pdf_string(text)}) Tj")
        stream.write("ET")

        if rgb != (0.0, 0.0, 0.0):
            stream.write("0 0 0 rg")

        # --- Render underline / strike / overline ---
        stroke_rgb = rgb
        stroke_color_cmd = _format_rgb(stroke_rgb, "RG") if stroke_rgb != (0.0, 0.0, 0.0) else None

        def _stroke_line(y_pos: float, line_width: float) -> None:
            if stroke_color_cmd:
                stream.write(stroke_color_cmd)
            stream.write(f"{format_pdf_number(line_width)} w")
            stream.write(f"{format_pdf_number(x)} {format_pdf_number(y_pos)} m")
            stream.write(f"{format_pdf_number(x + text_width)} {format_pdf_number(y_pos)} l")
            stream.write("S")
            if stroke_color_cmd:
                stream.write("0 0 0 RG")

        if style.get("underline"):
            underline_y = text_baseline - effective_font_size * 0.12
            _stroke_line(underline_y, max(effective_font_size * 0.055, 0.35))

        if style.get("overline"):
            overline_y = text_baseline + effective_font_size * 0.8
            _stroke_line(overline_y, max(effective_font_size * 0.055, 0.35))

        if style.get("strikethrough") or style.get("strike") or style.get("strike_through"):
            strike_y = text_baseline + effective_font_size * 0.28
            _stroke_line(strike_y, max(effective_font_size * 0.05, 0.35))

        if style.get("double_strikethrough"):
            strike_y1 = text_baseline + effective_font_size * 0.22
            strike_y2 = text_baseline + effective_font_size * 0.34
            _stroke_line(strike_y1, max(effective_font_size * 0.045, 0.3))
            _stroke_line(strike_y2, max(effective_font_size * 0.045, 0.3))

        return text_width

