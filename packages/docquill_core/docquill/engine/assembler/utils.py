from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..geometry import Rect, emu_to_points, twips_to_points
from ..layout_primitives import OverlayBox
from ..page_engine import PageConfig


def describe_element(element: Any) -> str:
    if isinstance(element, dict):
        return str(element.get("type") or element.get("kind") or "unknown")
    return element.__class__.__name__


def extract_anchor_info(source: Any) -> Tuple[str, Dict[str, Any]]:
    anchor_type = ""
    position: Dict[str, Any] = {}

    if isinstance(source, dict):
        anchor_type = str(source.get("anchor_type", "") or "")
        position = source.get("position") or {}
    elif hasattr(source, "textbox_anchor_info"):
        info = getattr(source, "textbox_anchor_info", {}) or {}
        anchor_type = str(info.get("anchor_type", "") or getattr(source, "anchor_type", "") or "")
        position = info.get("position") or {}
    elif hasattr(source, "anchor_type"):
        anchor_type = str(getattr(source, "anchor_type", "") or "")
        position = getattr(source, "position", {}) or {}

    if not isinstance(position, dict):
        position = {}

    return anchor_type.lower(), position


def extract_dimension(obj: Any, key: str, default: float) -> float:
    value = None
    if isinstance(obj, dict):
        value = obj.get(key)
    elif hasattr(obj, key):
        value = getattr(obj, key)

    raw_value = value

    if value in (None, 0, 0.0, ""):
        anchor_info = None
        if isinstance(obj, dict):
            anchor_info = obj.get("textbox_anchor_info") or obj.get("anchor_info")
        elif hasattr(obj, "textbox_anchor_info"):
            anchor_info = getattr(obj, "textbox_anchor_info", None)
        if isinstance(anchor_info, dict):
            raw_value = value = anchor_info.get(key)
            if value not in (None, ""):
                try:
                    float_value = float(value)
                    if abs(float_value) > 1000:
                        return emu_to_points(float_value)
                    return float_value
                except (TypeError, ValueError):
                    try:
                        return emu_to_points(float(value))
                    except (TypeError, ValueError):
                        pass
        return default

    try:
        float_value = float(value)
        if abs(float_value) > 1000:
            return emu_to_points(float_value)
        return float_value
    except (TypeError, ValueError):
        pass

    try:
        return emu_to_points(float(raw_value))
    except (TypeError, ValueError):
        return default


def resolve_overlay_frame(
    position: Dict[str, Any],
    width_pt: float,
    height_pt: float,
    block_rect: Optional[Rect],
    page_config: Optional[PageConfig],
) -> Rect:
    if not position or block_rect is None or page_config is None:
        if block_rect is not None:
            x = block_rect.x
            y = block_rect.y + block_rect.height - height_pt
        else:
            x = 0.0
            y = 0.0
        return Rect(x=x, y=y, width=width_pt, height=height_pt)

    x_rel = str(position.get("x_rel") or position.get("relative_from_x") or "column").lower()
    y_rel = str(position.get("y_rel") or position.get("relative_from_y") or "page").lower()

    x_offset_pt = emu_to_points(float(position.get("x", 0) or 0))
    y_offset_pt = emu_to_points(float(position.get("y", 0) or 0))

    margins = page_config.base_margins
    page_height = page_config.page_size.height

    if x_rel == "page":
        base_x = 0.0
    elif x_rel == "margin":
        base_x = margins.left
    elif x_rel == "column":
        base_x = block_rect.x
    else:
        base_x = block_rect.x

    left = base_x + x_offset_pt

    if y_rel == "page":
        top = page_height - y_offset_pt
    elif y_rel == "margin":
        top = page_height - margins.top - y_offset_pt
    elif y_rel in {"paragraph", "line", "text"}:
        top = block_rect.y + block_rect.height - y_offset_pt
    else:
        top = page_height - y_offset_pt

    bottom = top - height_pt

    return Rect(x=left, y=bottom, width=width_pt, height=height_pt)


def create_overlay_box(
    kind: str,
    source: Any,
    block_rect: Optional[Rect],
    default_width: float,
    default_height: float,
    page_config: Optional[PageConfig],
) -> OverlayBox:
    width_pt = extract_dimension(source, "width", default_width)
    height_pt = extract_dimension(source, "height", default_height)
    anchor_type, position = extract_anchor_info(source)
    frame = resolve_overlay_frame(position, width_pt, height_pt, block_rect, page_config)
    payload: Dict[str, Any] = {
        "anchor_type": anchor_type,
        "position": position,
        "source": source,
    }
    if kind == "image":
        payload["image"] = source
    elif kind == "textbox":
        payload["textbox"] = source
        if isinstance(source, dict):
            payload["style"] = source.get("style") or {}
            payload["text"] = source.get("text")
        else:
            payload["style"] = getattr(source, "style", {}) if hasattr(source, "style") else {}
            payload["text"] = getattr(source, "get_text", lambda: "")()
    return OverlayBox(kind=kind, frame=frame, payload=payload)


def extract_padding(style: Dict[str, Any]) -> Tuple[float, float, float, float]:
    general_padding = float(style.get("padding", 0.0) or 0.0)
    padding_top = float(style.get("padding_top", general_padding) or 0.0)
    padding_bottom = float(style.get("padding_bottom", general_padding) or 0.0)
    padding_left = float(style.get("padding_left", general_padding) or 0.0)
    padding_right = float(style.get("padding_right", general_padding) or 0.0)
    return padding_top, padding_right, padding_bottom, padding_left


def inline_metrics(font_size: float, line_spacing: float) -> Tuple[float, float]:
    ascent = font_size * 0.8
    descent = max(line_spacing - ascent, font_size * 0.2)
    return ascent, descent


def format_field_placeholder(field: Dict[str, Any]) -> str:
    field_type = str(field.get("field_type") or field.get("type") or "FIELD").upper()
    if field_type in {"PAGE", "NUMPAGES"}:
        return f"[{field_type}]"
    instruction = field.get("instr", "") or field.get("instruction", "")
    if instruction:
        return f"[{instruction.strip().split()[0].upper()}]"
    return "[FIELD]"


def parse_cell_margins(
    cell: Any,
    default_margin: float = 2.0,
    table_defaults: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    margins = {
        "top": default_margin,
        "bottom": default_margin,
        "left": default_margin,
        "right": default_margin,
    }

    cell_margins = None

    if isinstance(table_defaults, dict):
        for key in ("top", "bottom", "left", "right"):
            value = table_defaults.get(key)
            if value is not None:
                margins[key] = float(value)

    if hasattr(cell, "cell_margins"):
        cell_margins = cell.cell_margins
    elif hasattr(cell, "margins"):
        cell_margins = cell.margins
    elif isinstance(cell, dict):
        cell_margins = cell.get("margins") or cell.get("cell_margins")

    if not cell_margins:
        cell_style = {}
        if hasattr(cell, "style"):
            cell_style = cell.style if isinstance(cell.style, dict) else {}
        elif isinstance(cell, dict):
            cell_style = cell.get("style", {})

        cell_margins = cell_style.get("margins") or cell_style.get("cell_margins")

    if cell_margins and isinstance(cell_margins, dict):
        margin_map = {
            "top": "top",
            "bottom": "bottom",
            "left": "left",
            "right": "right",
            "start": "left",
            "end": "right",
        }

        for margin_key, margin_data in cell_margins.items():
            if isinstance(margin_data, dict):
                width_twips = margin_data.get("w") or margin_data.get("width")
                if width_twips is not None:
                    try:
                        width_points = twips_to_points(float(width_twips))
                        standard_key = margin_map.get(margin_key.lower(), margin_key.lower())
                        if standard_key in margins:
                            margins[standard_key] = width_points
                    except (ValueError, TypeError):
                        pass

    return margins


def _extract_spacing_value(value: Any) -> Optional[float]:
    if value in (None, "", {}, False):
        return None
    type_hint = ""
    raw = value
    if isinstance(value, dict):
        type_hint = str(value.get("type") or value.get("unit") or "").lower()
        raw = (
            value.get("w")
            or value.get("value")
            or value.get("val")
            or value.get("width")
            or value.get("amount")
        )
        if raw in (None, "", {}):
            return None
    if isinstance(raw, str):
        token = raw.strip()
        if not token or token.lower() == "auto":
            return None
        try:
            numeric = float(token)
        except (TypeError, ValueError):
            return None
    elif isinstance(raw, (int, float)):
        numeric = float(raw)
    else:
        return None
    if not type_hint:
        if numeric > 50:
            type_hint = "dxa"
    if type_hint in {"dxa", "twip", "twips"}:
        return twips_to_points(numeric)
    return numeric


def parse_table_spacing(table: Any) -> Tuple[float, float]:
    before = 0.0
    after = 0.0
    candidates: list[Any] = []
    if isinstance(table, dict):
        candidates.append(table.get("spacing"))
        style = table.get("style")
        if isinstance(style, dict):
            candidates.extend(
                [
                    style.get("spacing"),
                    style.get("table_spacing"),
                    style.get("tbl_spacing"),
                ]
            )
            direct_before = _extract_spacing_value(style.get("spacing_before") or style.get("space_before"))
            direct_after = _extract_spacing_value(style.get("spacing_after") or style.get("space_after"))
            if direct_before is not None:
                before = direct_before
            if direct_after is not None:
                after = direct_after
    else:
        if hasattr(table, "spacing"):
            candidates.append(getattr(table, "spacing"))
        if hasattr(table, "style") and isinstance(table.style, dict):
            candidates.append(table.style.get("spacing"))
    for spacing in candidates:
        if not isinstance(spacing, dict):
            continue
        val_before = (
            _extract_spacing_value(spacing.get("before_pt"))
            or _extract_spacing_value(spacing.get("before"))
        )
        val_after = (
            _extract_spacing_value(spacing.get("after_pt"))
            or _extract_spacing_value(spacing.get("after"))
        )
        if val_before is not None:
            before = val_before
        if val_after is not None:
            after = val_after
    return before, after


def parse_cell_spacing(cell: Any) -> Tuple[float, float]:
    before = 0.0
    after = 0.0
    candidates: list[Any] = []
    if isinstance(cell, dict):
        candidates.append(cell.get("spacing"))
        style = cell.get("style")
        if isinstance(style, dict):
            candidates.append(style.get("spacing"))
            direct_before = _extract_spacing_value(style.get("spacing_before") or style.get("space_before"))
            direct_after = _extract_spacing_value(style.get("spacing_after") or style.get("space_after"))
            if direct_before is not None:
                before = direct_before
            if direct_after is not None:
                after = direct_after
    else:
        if hasattr(cell, "properties") and getattr(cell, "properties"):
            spacing = getattr(cell.properties, "spacing", None)
            candidates.append(spacing)
        if hasattr(cell, "style") and isinstance(cell.style, dict):
            candidates.append(cell.style.get("spacing"))
    for spacing in candidates:
        if not isinstance(spacing, dict):
            continue
        val_before = (
            _extract_spacing_value(spacing.get("before_pt"))
            or _extract_spacing_value(spacing.get("before"))
        )
        val_after = (
            _extract_spacing_value(spacing.get("after_pt"))
            or _extract_spacing_value(spacing.get("after"))
        )
        if val_before is not None:
            before = val_before
        if val_after is not None:
            after = val_after
    return before, after



def normalize_font_size(value: Any) -> Optional[float]:
    """

    Converts font size values (including those stored in half-points) to points.

    """
    if value is None or value == "":
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


def estimate_text_height(text: str, available_width: float, style: Dict[str, Any]) -> float:
    if not text:
        return 0.0

    font_size = normalize_font_size(style.get("font_size")) or 11.0
    line_spacing = float(style.get("line_spacing", font_size * 1.2))
    char_width = max(font_size * 0.6, 1.0)
    available_width = max(available_width, char_width)

    words = text.replace("\r", "\n").split()
    if not words:
        lines = max(1, text.count("\n") + 1)
        return lines * line_spacing

    max_chars_per_line = max(1, int(available_width / char_width))
    current_line_len = 0
    lines = 1
    for word in words:
        word_len = len(word) + 1
        if current_line_len + word_len > max_chars_per_line and current_line_len > 0:
            lines += 1
            current_line_len = len(word)
        else:
            current_line_len += word_len
    return lines * line_spacing


def coerce_element_dict(element: Any, fallback_kind: Optional[str] = None) -> Dict[str, Any]:
    if isinstance(element, dict):
        return element
    if element is None:
        return {"type": fallback_kind or "unknown"}

    result: Dict[str, Any] = {}
    if hasattr(element, "__dict__"):
        for key, value in vars(element).items():
            if key.startswith("_"):
                continue
            result[key] = value

    for attr in (
        "type",
        "kind",
        "style",
        "text",
        "content",
        "children",
        "runs",
        "images",
        "fields",
        "textboxes",
        "id",
        "width",
        "height",
        "spacing_before",
        "spacing_after",
    ):
        if attr not in result and hasattr(element, attr):
            value = getattr(element, attr)
            if value is not None:
                result[attr] = value

    result.setdefault(
        "type",
        fallback_kind
        or getattr(element, "type", None)
        or element.__class__.__name__.lower(),
    )

    style = result.get("style")
    if style is None:
        pass
    elif not isinstance(style, dict):
        if hasattr(style, "to_dict"):
            try:
                style = style.to_dict()
            except Exception:
                style = dict(getattr(style, "__dict__", {}))
        elif hasattr(style, "__dict__"):
            style = {k: v for k, v in vars(style).items() if not k.startswith("_")}
        else:
            try:
                style = dict(style)
            except Exception:
                style = {}
        result["style"] = style

    return result


