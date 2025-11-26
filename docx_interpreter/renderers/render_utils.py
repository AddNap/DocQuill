"""Utility helpers shared across renderer components."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple, Union

from reportlab.lib import colors
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ..engine.geometry import Margins, Size

PAGE_SIZES = {
    "A4": A4,
    "LETTER": LETTER,
}


def ensure_page_size(page_size: Union[str, Size, Iterable[float]]) -> Tuple[float, float]:
    if isinstance(page_size, Size):
        return float(page_size.width), float(page_size.height)

    if isinstance(page_size, str):
        preset = PAGE_SIZES.get(page_size.upper())
        if preset:
            return float(preset[0]), float(preset[1])
        raise ValueError(f"Unsupported page size preset: {page_size}")

    if isinstance(page_size, Iterable):
        values = list(page_size)
        if len(values) != 2:
            raise ValueError("Page size iterable must contain exactly two values")
        return float(values[0]), float(values[1])

    return float(A4[0]), float(A4[1])


def ensure_margins(margins: Union[Margins, Iterable[float]]) -> Margins:
    if isinstance(margins, Margins):
        return margins

    values = list(margins) if isinstance(margins, Iterable) else []
    if len(values) not in (0, 4):
        raise ValueError("Margins must be provided as four numeric values (top, right, bottom, left)")

    if not values:
        return Margins(top=50, right=50, bottom=50, left=50)

    top, right, bottom, left = [float(v) for v in values]
    return Margins(top=top, bottom=bottom, left=left, right=right)


WORD_COLOR_MAP = {
    "auto": None,
    "black": "#000000",
    "blue": "#0000FF",
    "cyan": "#00FFFF",
    "darkblue": "#00008B",
    "darkcyan": "#008B8B",
    "darkgray": "#A9A9A9",
    "darkgrey": "#A9A9A9",
    "darkgreen": "#006400",
    "darkmagenta": "#8B008B",
    "darkred": "#8B0000",
    "darkyellow": "#B59A00",
    "gold": "#FFD700",
    "gray": "#808080",
    "grey": "#808080",
    "green": "#008000",
    "lightblue": "#ADD8E6",
    "lightcyan": "#E0FFFF",
    "lightgray": "#D3D3D3",
    "lightgrey": "#D3D3D3",
    "lightgreen": "#90EE90",
    "lightmagenta": "#FF77FF",
    "lightred": "#FF8080",
    "lightyellow": "#FFFFE0",
    "magenta": "#FF00FF",
    "red": "#FF0000",
    "white": "#FFFFFF",
    "yellow": "#FFFF00",
}


def _normalize_color(value: object, fallback: str) -> str:
    if isinstance(value, (tuple, list)) and len(value) == 3:
        try:
            return colors.Color(*[float(v) for v in value])  # type: ignore[return-value]
        except Exception:
            return fallback

    token = str(value or "").strip()
    if not token:
        return fallback

    lowered = token.lower()
    if lowered in WORD_COLOR_MAP:
        mapped = WORD_COLOR_MAP[lowered]
        if mapped is None:
            return fallback
        return mapped

    if token.startswith("#"):
        candidate = token
    elif len(token) in {3, 6} and all(ch in "0123456789abcdefABCDEF" for ch in token):
        candidate = f"#{token}"
    else:
        candidate = token

    try:
        HexColor(candidate)
        return candidate
    except Exception:
        return fallback


def to_color(value: object, fallback: str = "#000000") -> Color:
    normalized = _normalize_color(value, fallback)
    if isinstance(normalized, Color):
        return normalized
    try:
        return HexColor(normalized)
    except Exception:
        return HexColor(fallback)


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        try:
            return float(stripped)
        except (TypeError, ValueError):
            return default
    return default


def font_name_from_style(style: dict, default: str = "Helvetica") -> str:
    if not style:
        return default

    if "font_name" in style and style["font_name"]:
        return str(style["font_name"])

    font = style.get("font") if isinstance(style.get("font"), dict) else None
    if font:
        for key in ("name", "family", "ascii"):
            if font.get(key):
                return str(font[key])

    return default


def font_size_from_style(style: dict, default: float = 12.0) -> float:
    if not style:
        return default

    size = normalize_font_size(style.get("font_size"))
    if size:
        return size

    font = style.get("font") if isinstance(style.get("font"), dict) else None
    if font:
        for key in ("size", "size_pt"):
            value = normalize_font_size(font.get(key))
            if value:
                return value
        value = normalize_font_size(font.get("size_hps"))
        if value:
            return value

    return default


def normalize_font_size(value: object) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        has_pt_suffix = False
        if stripped.lower().endswith("pt"):
            stripped = stripped[:-2]
            has_pt_suffix = True
        try:
            numeric = float(stripped)
        except (TypeError, ValueError):
            return None
        if has_pt_suffix:
            return numeric
        if numeric > 15.0 and float(numeric).is_integer():
            return numeric / 2.0
        return numeric

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 15.0 and float(numeric).is_integer():
            return numeric / 2.0
        return numeric

    return None


def resolve_padding(style: Optional[Dict[str, Any]]) -> Tuple[float, float, float, float]:
    if not style:
        return 0.0, 0.0, 0.0, 0.0

    padding = style.get("padding")
    if isinstance(padding, dict):
        base = 0.0
        top = _to_float(padding.get("top"), base)
        right = _to_float(padding.get("right"), base)
        bottom = _to_float(padding.get("bottom"), base)
        left = _to_float(padding.get("left"), base)
    else:
        base = _to_float(padding)
        top = right = bottom = left = base

    top = _to_float(style.get("padding_top"), top)
    right = _to_float(style.get("padding_right"), right)
    bottom = _to_float(style.get("padding_bottom"), bottom)
    left = _to_float(style.get("padding_left"), left)

    return top, right, bottom, left


def draw_shadow(canvas, frame, style: Optional[Dict[str, Any]]) -> None:
    if not style:
        return

    shadow = style.get("shadow")
    if not shadow:
        return

    if isinstance(shadow, bool) and not shadow:
        return

    if isinstance(shadow, dict):
        color = to_color(shadow.get("color", "#888888"))
        dx = _to_float(shadow.get("offset_x"), 2.0)
        dy = _to_float(shadow.get("offset_y"), -2.0)
    else:
        color = to_color("#888888")
        dx = 2.0
        dy = -2.0

    canvas.saveState()
    canvas.setFillColor(color)
    canvas.rect(frame.x + dx, frame.y + dy, frame.width, frame.height, fill=1, stroke=0)
    canvas.restoreState()


def draw_background(canvas, frame, style: Optional[Dict[str, Any]]) -> None:
    if not style:
        return

    background = style.get("background") or style.get("background_color")
    if not background:
        shading = style.get("shading") or {}
        background = shading.get("fill") or shading.get("color") or shading.get(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill"
        )
    if not background:
        return

    canvas.saveState()
    canvas.setFillColor(to_color(background))
    canvas.rect(frame.x, frame.y, frame.width, frame.height, fill=1, stroke=0)
    canvas.restoreState()


def draw_border(canvas, frame, style: Optional[Dict[str, Any]]) -> None:
    if not style:
        return

    border = style.get("border")
    borders = style.get("borders")

    if border or not borders:
        spec = _normalize_border_spec(border)
        if not spec:
            return

        canvas.saveState()
        _apply_border_style(canvas, spec)

        radius = spec.get("radius", 0.0)
        if radius > 0:
            canvas.roundRect(frame.x, frame.y, frame.width, frame.height, radius, stroke=1, fill=0)
        else:
            canvas.rect(frame.x, frame.y, frame.width, frame.height, stroke=1, fill=0)

        canvas.restoreState()
        return

    if not isinstance(borders, dict):
        return

    sides = {
        "top": ((frame.x, frame.y + frame.height), (frame.x + frame.width, frame.y + frame.height)),
        "bottom": ((frame.x, frame.y), (frame.x + frame.width, frame.y)),
        "left": ((frame.x, frame.y), (frame.x, frame.y + frame.height)),
        "right": ((frame.x + frame.width, frame.y), (frame.x + frame.width, frame.y + frame.height)),
    }

    for side, (start, end) in sides.items():
        spec = _normalize_border_spec(borders.get(side))
        if not spec:
            continue

        canvas.saveState()
        _apply_border_style(canvas, spec)

        width = spec.get("width", 1.0)
        if side in {"top", "bottom"}:
            offset = width / 2.0
            y = start[1] - offset if side == "top" else start[1] + offset
            canvas.line(start[0], y, end[0], y)
        else:
            offset = width / 2.0
            x = start[0] + offset if side == "left" else start[0] - offset
            canvas.line(x, start[1], x, end[1])

        canvas.restoreState()


def _normalize_border_spec(raw: Any) -> Optional[Dict[str, Any]]:
    if not raw:
        return None

    if isinstance(raw, bool):
        return None if not raw else {"width": 1.0, "color": "#000000", "style": "solid", "radius": 0.0}

    if isinstance(raw, (int, float)):
        width = max(float(raw), 0.0)
        if width <= 0:
            return None
        return {"width": width, "color": "#000000", "style": "solid", "radius": 0.0}

    if not isinstance(raw, dict):
        return None

    if raw.get("val") in {"none", "nil"} or raw.get("style") == "none":
        return None

    width = _to_float(raw.get("width"))
    if not width and raw.get("sz"):
        try:
            width = float(raw.get("sz")) / 8.0
        except (TypeError, ValueError):
            width = None
    if width is None or width <= 0:
        width = 1.0

    color_value = raw.get("color") or raw.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color")
    if not color_value or color_value == "auto":
        color_value = "#000000"

    radius = _to_float(raw.get("radius"), 0.0)
    style_name = raw.get("style") or raw.get("val") or raw.get("type") or "solid"

    return {
        "width": width,
        "color": color_value,
        "style": style_name,
        "radius": radius,
    }


def _apply_border_style(canvas, border_spec: Dict[str, Any]) -> None:
    width = max(border_spec.get("width", 1.0), 0.01)
    color = to_color(border_spec.get("color") or "#000000")
    style_name = (border_spec.get("style") or "solid").lower()

    canvas.setLineWidth(width)
    canvas.setStrokeColor(color)

    if style_name == "dashed":
        canvas.setDash(6, 3)
    elif style_name == "dotted":
        canvas.setDash(1, 2)


_PDF_FONTS_REGISTERED: Dict[str, str] = {}


def ensure_pdf_font(font_name: str, font_path: Optional[str]) -> None:
    if not font_name or not font_path:
        return
    if font_name in _PDF_FONTS_REGISTERED:
        return
    if font_name in pdfmetrics.getRegisteredFontNames():
        _PDF_FONTS_REGISTERED[font_name] = font_path
        return
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        _PDF_FONTS_REGISTERED[font_name] = font_path
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Font registration helpers
# ---------------------------------------------------------------------------

_FONTS_REGISTERED = False


def register_default_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    candidates = {
        "DejaVuSans": [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/local/share/fonts/DejaVuSans.ttf"),
        ],
        "DejaVuSans-Bold": [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/local/share/fonts/DejaVuSans-Bold.ttf"),
        ],
        "DejaVuSans-Oblique": [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
            Path("/usr/local/share/fonts/DejaVuSans-Oblique.ttf"),
        ],
        "DejaVuSans-BoldOblique": [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
            Path("/usr/local/share/fonts/DejaVuSans-BoldOblique.ttf"),
        ],
    }

    for font_name, paths in candidates.items():
        if font_name in pdfmetrics.getRegisteredFontNames():
            continue
        path = next((p for p in paths if p.exists()), None)
        if path:
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
            except Exception:
                continue

    _FONTS_REGISTERED = True


def resolve_font_variant(base_name: str, *, bold: bool = False, italic: bool = False) -> str:
    variant = base_name
    if bold and italic:
        candidate = f"{base_name}-BoldOblique"
        if candidate in pdfmetrics.getRegisteredFontNames():
            return candidate
    if bold:
        candidate = f"{base_name}-Bold"
        if candidate in pdfmetrics.getRegisteredFontNames():
            return candidate
    if italic:
        candidate = f"{base_name}-Oblique"
        if candidate in pdfmetrics.getRegisteredFontNames():
            return candidate
    return variant


def spacing_from_style(style: dict, key: str, default: float = 0.0) -> float:
    if not style:
        return default

    if key in style and style[key] is not None:
        try:
            return float(style[key])
        except (TypeError, ValueError):
            pass

    spacing = style.get("spacing") if isinstance(style.get("spacing"), dict) else {}
    candidate = spacing.get(key)
    if candidate is None:
        return default

    try:
        numeric = float(candidate)
        if numeric > 144:
            return numeric / 20.0
        return numeric
    except (TypeError, ValueError):
        return default

