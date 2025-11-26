"""

LayoutAssembler - the actual layout engine:
- calculates dimensions, spacing and element positions
- handles pagination and margins
- prepares LayoutBlock for PDFCompiler

"""

import copy
import re
import logging
from typing import Optional, Any, Dict, List, Tuple

logger = logging.getLogger(__name__)
from ..geometry import Rect, twips_to_points
from ..unified_layout import UnifiedLayout, LayoutBlock
from ..layout_primitives import (
    ParagraphLayout,
    ParagraphLine,
    InlineBox,
    OverlayBox,
    BoxStyle,
    ColorSpec,
    BorderSpec,
    BlockContent,
    GenericLayout,
)
from ..page_engine import PageConfig
from ..text_metrics import TextMetricsEngine
from ..layout_tree import BaseNode
from ..engines import create_default_dispatcher
from .utils import (
    describe_element,
    create_overlay_box,
    extract_anchor_info,
    extract_dimension,
    extract_padding,
    inline_metrics,
    format_field_placeholder,
    parse_cell_margins,
    parse_cell_spacing,
    parse_table_spacing,
    estimate_text_height,
    coerce_element_dict,
    normalize_font_size,
)


class LayoutAssembler:
    def __init__(self, page_config: PageConfig, *, target: str = "pdf"):
        """
        page_config: obiekt PageConfig z atrybutami:
            - page_size: Size(width, height)
            - base_margins: Margins(top, bottom, left, right)
        """
        self.page_config = page_config
        self.current_y = 0
        self.page_number = 0
        self.text_metrics = TextMetricsEngine()
        self.tree_dispatcher = create_default_dispatcher()
        self.target = str(target or "pdf").lower()
        self._is_html = self.target == "html"
        self._is_pdf = self.target == "pdf"
        self.page_variator = None
        self._page_bottom_limit = self.page_config.base_margins.bottom
        self._border_group_serial = 0
        self._pending_spacing_after = 0.0
        self._page_has_content = False
        self._block_counter = 0
        
        # Initialize footnote tracking
        try:
            from ...renderers.footnote_renderer import FootnoteRenderer
            from ...parser.notes_parser import NotesParser
            # Get footnotes and endnotes from package_reader if available
            footnotes = {}
            endnotes = {}
            package_reader = getattr(page_config, 'package_reader', None)
            if package_reader:
                try:
                    notes_parser = NotesParser(package_reader)
                    footnotes = notes_parser.get_footnotes() or {}
                    endnotes = notes_parser.get_endnotes() or {}
                except Exception:
                    pass
            self.footnote_renderer = FootnoteRenderer(footnotes, endnotes) if FootnoteRenderer else None
            self._footnotes_per_page = {}  # Track footnotes per page
            self._footnote_area_height = 50.0  # Default height for footnotes area
            self._endnotes_collected = []  # Collect all endnotes for rendering at the end
        except ImportError:
            self.footnote_renderer = None
            self._footnotes_per_page = {}
            self._footnote_area_height = 50.0
            self._endnotes_collected = []

    def set_page_variator(self, page_variator):
        self.page_variator = page_variator

    def _get_cached_tree(self, element: Any) -> Optional[BaseNode]:
        if isinstance(element, dict):
            return element.get("_layout_tree")
        return getattr(element, "_layout_tree", None)

    def _cache_tree(self, element: Any, tree: BaseNode) -> None:
        if isinstance(element, dict):
            element["_layout_tree"] = tree
        else:
            setattr(element, "_layout_tree", tree)

    @staticmethod
    def _strip_namespace(value: Any) -> Any:
        if isinstance(value, str) and "}" in value:
            return value.split("}", 1)[1]
        return value

    def _apply_inter_block_spacing(
        self,
        spacing_before: float,
        unified: UnifiedLayout,
        enforce_min: bool = True,
    ) -> None:
        desired = max(self._pending_spacing_after, spacing_before)
        enforce_min_gap = (
            enforce_min
            and self._page_has_content
            and self._pending_spacing_after <= 0.0
            and spacing_before <= 0.0
        )
        if enforce_min_gap and desired <= 0.0:
            desired = 1.0

        if desired <= 0.0:
            self._pending_spacing_after = 0.0
            return

        available = self.current_y - self._page_bottom_limit
        if desired > available + 1e-6:
            self._new_page(unified)
            desired = max(spacing_before, 0.0)
            enforce_min_gap = enforce_min and spacing_before <= 0.0
            if enforce_min_gap and desired <= 0.0:
                desired = 0.0
            if desired <= 0.0:
                self._pending_spacing_after = 0.0
                return
            available = self.current_y - self._page_bottom_limit
            if desired > available + 1e-6:
                desired = max(available, 0.0)

        if desired > 0.0:
            self.current_y -= desired
        self._pending_spacing_after = 0.0

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        if value in (None, "", False):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except (TypeError, ValueError):
                return default
        return default

    def _capture_html_spacing(self, style: Optional[Dict[str, Any]]) -> None:
        if not self._is_html or not isinstance(style, dict):
            return
        spacing_before = self._to_float(style.get("spacing_before"), 0.0)
        spacing_after = self._to_float(style.get("spacing_after"), 0.0)
        style["_html_spacing_before"] = spacing_before
        style["_html_spacing_after"] = spacing_after

    def _resolve_element_uid(self, element: Any) -> Optional[str]:
        if isinstance(element, dict):
            for key in (
                "_block_uid",
                "block_uid",
                "source_uid",
                "source_id",
                "id",
                "element_id",
                "uid",
                "unique_id",
                "paragraph_id",
                "shape_id",
                "table_id",
            ):
                value = element.get(key)
                if value not in (None, ""):
                    return str(value)
            meta = element.get("meta")
            if isinstance(meta, dict):
                for key in ("id", "uid", "source_id"):
                    value = meta.get(key)
                    if value not in (None, ""):
                        return str(value)
        return None

    def _allocate_block_identity(
        self,
        element: Any,
        *,
        suffix: Optional[str] = None,
    ) -> Tuple[int, str]:
        sequence = self._block_counter
        self._block_counter += 1

        base_uid = None
        if isinstance(element, dict):
            base_uid = element.get("_block_uid")

        if not base_uid:
            base_uid = self._resolve_element_uid(element)
            if not base_uid:
                base_uid = f"block-{sequence}"
            if isinstance(element, dict):
                element["_block_uid"] = base_uid

        source_uid = f"{base_uid}:{suffix}" if suffix else base_uid

        if isinstance(element, dict) and "_block_sequence" not in element:
            element["_block_sequence"] = sequence

        return sequence, str(source_uid)

    def _normalize_color_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            token = value.strip()
            if not token:
                return None
            lowered = token.lower()
            if lowered in {"auto", "none", "transparent"}:
                return None
            if token.startswith("#"):
                token = token.upper()
            elif len(token) in {3, 6} and all(ch in "0123456789abcdefABCDEF" for ch in token):
                token = f"#{token.upper()}"
            return token
        if isinstance(value, (tuple, list)) and len(value) == 3:
            try:
                return "#%02X%02X%02X" % tuple(int(float(v) * 255) for v in value)
            except Exception:
                return None
        return None

    @staticmethod
    def _normalize_table_alignment(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in ("val", "w", "value", "alignment", "jc"):
                if value.get(key) not in (None, "", {}):
                    value = value[key]
                    break
        if isinstance(value, str):
            token = value.strip().lower()
            if not token:
                return None
            mapping = {
                "start": "left",
                "left": "left",
                "center": "center",
                "centre": "center",
                "middle": "center",
                "right": "right",
                "end": "right",
                "both": "justify",
                "distribute": "justify",
                "justify": "justify",
            }
            normalized = mapping.get(token, token)
            if normalized in {"left", "center", "right", "justify"}:
                return normalized
        return None

    @staticmethod
    def _normalize_table_vertical_alignment(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in ("val", "value", "alignment"):
                if value.get(key) not in (None, "", {}):
                    value = value[key]
                    break
        if isinstance(value, str):
            token = value.strip().lower()
            if not token:
                return None
            mapping = {
                "top": "top",
                "center": "center",
                "middle": "center",
                "bottom": "bottom",
                "baseline": "top",
            }
            normalized = mapping.get(token)
            if normalized:
                return normalized
        return None

    def _hex_to_rgb_tuple(self, value: Any) -> Optional[Tuple[float, float, float]]:
        token = self._normalize_color_value(value)
        if not token or not isinstance(token, str) or not token.startswith("#") or len(token) != 7:
            return None
        try:
            r = int(token[1:3], 16) / 255.0
            g = int(token[3:5], 16) / 255.0
            b = int(token[5:7], 16) / 255.0
            return (r, g, b)
        except (TypeError, ValueError):
            return None

    def _normalize_shading(self, shading: Any) -> Optional[Dict[str, Any]]:
        if not shading or not isinstance(shading, dict):
            return None
        cleaned = {self._strip_namespace(k): v for k, v in shading.items()}
        fill = self._normalize_color_value(
            cleaned.get("fill")
            or cleaned.get("color")
            or cleaned.get("background")
        )
        if not fill:
            return None
        result: Dict[str, Any] = {"fill": fill}
        if cleaned.get("color"):
            border_color = self._normalize_color_value(cleaned.get("color"))
            if border_color:
                result["color"] = border_color
        if cleaned.get("pattern"):
            result["pattern"] = cleaned["pattern"]
        return result

    def _normalize_border_dict(self, border: Any) -> Optional[Dict[str, Any]]:
        if not border:
            return None
        if isinstance(border, (int, float)):
            width = max(float(border), 0.0)
            if width <= 0:
                return None
            return {"width": width, "color": "#000000", "style": "solid"}
        if isinstance(border, str):
            color = self._normalize_color_value(border)
            if not color:
                return None
            return {"width": 1.0, "color": color, "style": "solid"}
        if not isinstance(border, dict):
            return None
        cleaned = {self._strip_namespace(k): v for k, v in border.items()}
        style_name = cleaned.get("style") or cleaned.get("val") or cleaned.get("type") or "solid"
        if isinstance(style_name, str) and style_name.lower() in {"none", "nil"}:
            return None
        width = self._to_float(cleaned.get("width"))
        if not width and cleaned.get("sz"):
            try:
                width = float(cleaned["sz"]) / 8.0
            except (TypeError, ValueError):
                width = None
        if not width or width <= 0.0:
            width = 1.0
        color_value = (
            cleaned.get("color")
            or cleaned.get("color_val")
            or cleaned.get("color_value")
        )
        normalized_color = self._normalize_color_value(color_value) or "#000000"
        result = {
            "width": width,
            "color": normalized_color,
            "style": str(style_name or "solid"),
        }
        if cleaned.get("space") is not None:
            space_val = self._to_float(cleaned.get("space"))
            if space_val is not None:
                result["space"] = space_val
        radius = self._to_float(cleaned.get("radius"))
        if radius:
            result["radius"] = radius
        return result

    def _normalize_shadow(self, shadow: Any) -> Optional[Dict[str, Any]]:
        if not shadow:
            return None
        if isinstance(shadow, bool):
            return {"color": "#888888", "offset_x": 2.0, "offset_y": -2.0}
        if not isinstance(shadow, dict):
            return None
        cleaned = {self._strip_namespace(k): v for k, v in shadow.items()}
        color = self._normalize_color_value(cleaned.get("color") or cleaned.get("fill")) or "#888888"
        offset_x = self._to_float(
            cleaned.get("offset_x")
            or cleaned.get("x")
            or cleaned.get("distance")
            or cleaned.get("dist")
            or 2.0,
            2.0,
        )
        offset_y = self._to_float(
            cleaned.get("offset_y")
            or cleaned.get("y")
            or cleaned.get("distance_y")
            or cleaned.get("dy")
            or -2.0,
            -2.0,
        )
        return {"color": color, "offset_x": offset_x, "offset_y": offset_y}

    def _ensure_paragraph_style(self, element: Any) -> Dict[str, Any]:
        if not isinstance(element, dict):
            return {}

        style = element.get("style")
        if not isinstance(style, dict):
            style = {}
            element["style"] = style

        if element.get("_style_normalized_paragraph"):
            return style

        normalized = self._normalize_paragraph_style(style)
        style.clear()
        style.update(normalized)

        def _coerce_length(value: Any) -> Optional[float]:
            if value in (None, "", {}, False):
                return None
            if isinstance(value, (int, float)):
                numeric = float(value)
            else:
                try:
                    numeric = float(str(value).strip())
                except (TypeError, ValueError):
                    return None
            if abs(numeric) > 144.0:
                return twips_to_points(numeric)
            return numeric

        padding_value = style.get("padding")
        if isinstance(padding_value, dict):
            padding_normalized: Dict[str, float] = {}
            for key, raw_val in padding_value.items():
                coerced = _coerce_length(raw_val)
                if coerced is not None:
                    padding_normalized[self._strip_namespace(key)] = coerced
            if padding_normalized:
                style["padding"] = padding_normalized
            else:
                style.pop("padding", None)
        elif padding_value not in (None, "", {}, False):
            coerced = _coerce_length(padding_value)
            if coerced is not None:
                style["padding"] = coerced

        for side in ("top", "right", "bottom", "left"):
            key = f"padding_{side}"
            coerced = _coerce_length(style.get(key))
            if coerced is not None:
                style[key] = coerced

        spacing_before = _coerce_length(style.get("spacing_before"))
        if spacing_before is not None:
            style["spacing_before"] = spacing_before
        spacing_after = _coerce_length(style.get("spacing_after"))
        if spacing_after is not None:
            style["spacing_after"] = spacing_after

        spacing_map = style.get("spacing")
        if isinstance(spacing_map, dict):
            before_pt = _coerce_length(spacing_map.get("before_pt"))
            if before_pt is None:
                before_pt = _coerce_length(spacing_map.get("before"))
            if before_pt is not None:
                spacing_map["before_pt"] = before_pt

            after_pt = _coerce_length(spacing_map.get("after_pt"))
            if after_pt is None:
                after_pt = _coerce_length(spacing_map.get("after"))
            if after_pt is not None:
                spacing_map["after_pt"] = after_pt

            line_height = _coerce_length(spacing_map.get("line_height_pt"))
            if line_height is not None:
                spacing_map["line_height_pt"] = line_height

        shadow_value = style.get("shadow")
        if isinstance(shadow_value, dict):
            for key in ("offset_x", "offset_y"):
                coerced = _coerce_length(shadow_value.get(key))
                if coerced is not None:
                    shadow_value[key] = coerced

        style.pop("_borders_to_draw", None)
        style.pop("_border_group_index", None)
        style.pop("_border_group_size", None)
        style.pop("_border_group_id", None)
        style.pop("_border_group_draw", None)
        style.pop("_border_group_span_rect", None)
        style.pop("_border_extra_bottom", None)

        signature = self._compute_paragraph_border_signature(style)
        if signature:
            style["_border_signature"] = signature
        else:
            style.pop("_border_signature", None)

        element["_style_normalized_paragraph"] = True
        return style

    @staticmethod
    def _compute_paragraph_border_signature(style: Dict[str, Any]) -> Optional[Tuple[Any, ...]]:
        borders = style.get("borders")
        if not isinstance(borders, dict) or not borders:
            return None
        has_visible = any(
            isinstance(borders.get(side), dict)
            for side in ("top", "bottom", "left", "right", "between", "bar")
        )
        if not has_visible:
            return None
        signature: List[Any] = []
        background = (
            style.get("background")
            or style.get("background_color")
            or (
                style.get("shading", {}).get("fill")
                if isinstance(style.get("shading"), dict)
                else None
            )
        )
        padding = style.get("padding") or style.get("padding_top")
        signature.append(("background", background))
        signature.append(("padding", padding))
        signature_sides = ("right", "left", "between", "bar")
        for side in signature_sides:
            spec = borders.get(side)
            if isinstance(spec, dict):
                width = spec.get("width")
                try:
                    width = round(float(width), 3)
                except (TypeError, ValueError):
                    width = width
                signature.append(
                    (
                        side,
                        width,
                        spec.get("color"),
                        spec.get("style"),
                        spec.get("space"),
                    )
                )
            else:
                signature.append((side, None, None, None, None))
        top_spec = borders.get("top")
        if isinstance(top_spec, dict):
            width = top_spec.get("width")
            try:
                width = round(float(width), 3)
            except (TypeError, ValueError):
                width = width
            signature.append(
                (
                    "top",
                    width,
                    top_spec.get("color"),
                    top_spec.get("style"),
                )
            )
        else:
            signature.append(("top", None, None, None))

        return tuple(signature)

    def _apply_paragraph_border_grouping(self, elements: List[Dict[str, Any]]) -> None:
        current_group: List[Dict[str, Any]] = []
        current_signature: Optional[Tuple[Any, ...]] = None

        def flush_group() -> None:
            nonlocal current_group, current_signature
            if not current_group or not current_signature:
                current_group = []
                current_signature = None
                return
            total = len(current_group)
            if total <= 0:
                current_group = []
                current_signature = None
                return
            group_id = self._border_group_serial
            self._border_group_serial += 1
            for index, paragraph in enumerate(current_group):
                style = paragraph.get("style") or {}
                style.pop("_border_extra_bottom", None)
                borders = style.get("borders") if isinstance(style.get("borders"), dict) else {}
                if total > 1 and index < total - 1:
                    between_spec = borders.get("between")
                    if isinstance(between_spec, dict):
                        next_style = current_group[index + 1].get("style") or {}
                        next_style["_border_between_spec"] = dict(between_spec)  # OPTIMIZATION: shallow copy dict
                    else:
                        next_style = current_group[index + 1].get("style") or {}
                        if not next_style.get("_border_between_spec"):
                            fallback_specs: List[Dict[str, Any]] = []
                            bottom_spec = borders.get("bottom")
                            if isinstance(bottom_spec, dict):
                                fallback_specs.append(dict(bottom_spec))  # OPTIMIZATION: shallow copy dict
                            next_borders = next_style.get("borders")
                            if isinstance(next_borders, dict):
                                top_spec = next_borders.get("top")
                                if isinstance(top_spec, dict):
                                    fallback_specs.append(dict(top_spec))  # OPTIMIZATION: shallow copy dict
                            if fallback_specs:
                                if len(fallback_specs) == 1:
                                    next_style["_border_between_spec"] = fallback_specs[0]
                                else:
                                    next_style["_border_between_spec"] = fallback_specs
                style["_borders_to_draw"] = {}
                style["_border_group_index"] = index
                style["_border_group_size"] = total
                style["_border_group_id"] = group_id
                style["_border_group_draw"] = False
            current_group = []
            current_signature = None

        for element in elements:
            if not isinstance(element, dict):
                continue
            if element.get("type") != "paragraph":
                flush_group()
                continue
            style = self._ensure_paragraph_style(element)
            signature = style.get("_border_signature")
            if signature:
                if current_signature == signature:
                    current_group.append(element)
                else:
                    flush_group()
                    current_signature = signature
                    current_group = [element]
                continue
            flush_group()
        flush_group()

    def _resolve_paragraph_pagination_settings(
        self, element: Dict[str, Any]
    ) -> Dict[str, Any]:
        style = dict(element.get("style") or {})

        def _to_bool(value: Any, default: bool = False) -> bool:
            if isinstance(value, bool):
                return value
            if value in (None, "", {}):
                return default
            if isinstance(value, (int, float)):
                return value != 0
            token = str(value).strip().lower()
            if token in {"1", "true", "yes", "on"}:
                return True
            if token in {"0", "false", "no", "off"}:
                return False
            return default

        keep_together = _to_bool(
            element.get("keep_together")
            or style.get("keep_together")
            or style.get("keep_lines")
            or style.get("keepLines")
        )
        keep_with_next = _to_bool(
            element.get("keep_with_next")
            or style.get("keep_with_next")
            or style.get("keep_next")
            or style.get("keepNext")
        )
        widow_control = _to_bool(
            style.get("widow_control")
            or style.get("widowControl")
            or style.get("widows_control"),
            default=True,
        )
        widow_lines = style.get("widow_lines") or style.get("widowLines")
        orphan_lines = style.get("orphan_lines") or style.get("orphanLines")

        def _to_int(value: Any, default: int) -> int:
            if value in (None, "", {}):
                return default
            if isinstance(value, bool):
                return default
            try:
                return max(int(value), 0)
            except (ValueError, TypeError):
                return default

        widow_lines_int = _to_int(widow_lines, 2)
        orphan_lines_int = _to_int(orphan_lines, 2)
        if widow_lines_int <= 0:
            widow_lines_int = 2
        if orphan_lines_int <= 0:
            orphan_lines_int = 2

        return {
            "keep_together": keep_together,
            "keep_with_next": keep_with_next,
            "widow_control": widow_control,
            "widow_lines": widow_lines_int,
            "orphan_lines": orphan_lines_int,
        }

    @staticmethod
    def _compute_paragraph_segment_height(
        payload: ParagraphLayout,
        start: int,
        end: int,
        include_padding_top: bool = False,
        include_padding_bottom: bool = False,
    ) -> float:
        lines = payload.lines or []
        if start >= end or not lines:
            height = 0.0
        else:
            height = 0.0
            for idx in range(start, end):
                line = lines[idx]
                block_height = getattr(line, "block_height", None)
                if block_height is None or block_height <= 0:
                    block_height = line.height
                height += max(block_height, 0.0)

        padding_top = 0.0
        padding_bottom = 0.0
        if isinstance(payload.style, BoxStyle):
            padding_top, _, padding_bottom, _ = payload.style.padding

        if include_padding_top:
            height += padding_top
        if include_padding_bottom:
            height += padding_bottom
        return max(height, 0.0)

    def _determine_paragraph_break_index(
        self,
        payload: ParagraphLayout,
        start: int,
        available_height: float,
        settings: Dict[str, Any],
        force_split_allowed: bool,
    ) -> Optional[int]:
        lines = payload.lines or []
        total_lines = len(lines)
        if total_lines == 0 or start >= total_lines:
            return total_lines

        remaining = total_lines - start
        include_padding_top = start == 0
        total_height_remaining = self._compute_paragraph_segment_height(
            payload,
            start,
            total_lines,
            include_padding_top=include_padding_top,
            include_padding_bottom=True,
        )

        if (
            settings.get("keep_together")
            and start == 0
            and not force_split_allowed
        ):
            if total_height_remaining <= available_height + 1e-6:
                return total_lines
            return None

        natural_end = start
        for idx in range(start, total_lines):
            include_bottom = idx + 1 == total_lines
            segment_height = self._compute_paragraph_segment_height(
                payload,
                start,
                idx + 1,
                include_padding_top=include_padding_top,
                include_padding_bottom=include_bottom,
            )
            if segment_height <= available_height + 1e-6:
                natural_end = idx + 1
            else:
                break

        natural_break = natural_end - start
        if natural_break <= 0:
            return start
        if natural_end == total_lines:
            return total_lines

        lines_here = natural_break
        lines_next = remaining - lines_here
        if settings.get("widow_control", True):
            widow_lines = max(int(settings.get("widow_lines", 2)), 1)
            orphan_lines = max(int(settings.get("orphan_lines", 2)), 1)

            if 0 < lines_next < widow_lines:
                diff = widow_lines - lines_next
                lines_here -= diff
                if lines_here < 0:
                    lines_here = 0

            if 0 < lines_here < orphan_lines:
                lines_here = 0

        if lines_here <= 0:
            return start

        # Ensure the adjusted segment still fits within available height.
        adjusted_end = start + lines_here
        include_bottom = adjusted_end == total_lines
        adjusted_height = self._compute_paragraph_segment_height(
            payload,
            start,
            adjusted_end,
            include_padding_top=include_padding_top,
            include_padding_bottom=include_bottom,
        )
        while lines_here > 0 and adjusted_height > available_height + 1e-6:
            lines_here -= 1
            adjusted_end = start + lines_here
            include_bottom = adjusted_end == total_lines
            adjusted_height = self._compute_paragraph_segment_height(
                payload,
                start,
                adjusted_end,
                include_padding_top=include_padding_top,
                include_padding_bottom=include_bottom,
            )

        if lines_here <= 0:
            return start

        return start + lines_here

    def _slice_paragraph_layout(
        self,
        payload: ParagraphLayout,
        start: int,
        end: int,
    ) -> ParagraphLayout:
        lines = payload.lines or []
        start = max(0, min(start, len(lines)))
        end = max(start, min(end, len(lines)))

        new_lines: List[ParagraphLine] = []
        current_baseline = 0.0
        for line in lines[start:end]:
            # OPTIMIZATION: Instead of deepcopy, shallow copy list and copy dicts inside InlineBox
            # InlineBox is a dataclass with a dict field (data), so we need to copy the dict
            copied_items = []
            for item in line.items:
                # Shallow copy the InlineBox (dataclass), but deep copy the dict inside
                new_item = InlineBox(
                    kind=item.kind,
                    x=item.x,
                    width=item.width,
                    ascent=item.ascent,
                    descent=item.descent,
                    data=dict(item.data) if item.data else {},  # Shallow copy dict is enough
                )
                copied_items.append(new_item)
            
            block_height = getattr(line, "block_height", None)
            if block_height is None or block_height <= 0:
                block_height = line.height
            new_line = ParagraphLine(
                baseline_y=current_baseline,
                height=line.height,
                items=copied_items,
                offset_x=line.offset_x,
                available_width=line.available_width,
                block_height=block_height,
            )
            new_lines.append(new_line)
            current_baseline += block_height

        # OPTIMIZATION: Instead of deepcopy, shallow copy list and copy dicts inside OverlayBox
        new_overlays = []
        for overlay in payload.overlays:
            new_overlay = OverlayBox(
                kind=overlay.kind,
                frame=overlay.frame,  # Rect is immutable-like, can be shared
                payload=dict(overlay.payload) if overlay.payload else {},  # Shallow copy dict
            )
            new_overlays.append(new_overlay)
        
        # OPTIMIZATION: BoxStyle is a dataclass, copy.copy() is sufficient (shallow copy)
        # Dataclasses with immutable fields don't need deepcopy
        new_style = copy.copy(payload.style)
        new_metadata = dict(payload.metadata or {})
        new_layout = ParagraphLayout(
            lines=new_lines,
            overlays=new_overlays,
            style=new_style,
            metadata=new_metadata,
        )
        return new_layout

    @staticmethod
    def _mark_segment_payload_final(
        payload: Optional[ParagraphLayout],
        block_width: float,
    ) -> None:
        if not isinstance(payload, ParagraphLayout):
            return
        metadata = payload.metadata
        if not isinstance(metadata, dict):
            metadata = {}
            payload.metadata = metadata
        metadata["block_rect_is_final"] = True
        try:
            metadata["block_rect_width"] = float(block_width)
        except (TypeError, ValueError):
            metadata["block_rect_width"] = block_width
        metadata["_pagination_segment_payload"] = True

    def _clone_paragraph_segment_element(
        self,
        base_element: Dict[str, Any],
        segment_payload: ParagraphLayout,
        segment_index: int,
        segment_count: int,
        spacing_before: float,
        spacing_after: float,
    ) -> Dict[str, Any]:
        # OPTIMIZATION: Instead of deepcopy, use shallow copy and only deep copy mutable nested structures
        # Most fields in base_element are immutable (strings, numbers) or can be shared
        segment_element = dict(base_element)  # Shallow copy
        
        # Deep copy only the style dict since we'll modify it
        original_style = base_element.get("style")
        if isinstance(original_style, dict):
            style = dict(original_style)  # Shallow copy dict is enough (values are mostly immutable)
        else:
            style = {}
        
        style["spacing_before"] = spacing_before
        style["spacing_after"] = spacing_after
        segment_element["style"] = style
        segment_element["layout_payload"] = segment_payload
        segment_element["_layout_payload"] = segment_payload
        segment_element["_pagination_segment_index"] = segment_index
        segment_element["_pagination_segment_count"] = segment_count
        return segment_element

    def _update_border_geometry_for_paragraph(
        self,
        element: Dict[str, Any],
        rect: Rect,
        border_group_geometry: Dict[Tuple[int, int], Dict[str, Any]],
        unified: UnifiedLayout,
        paragraph_block: LayoutBlock,
    ) -> None:
        style = element.get("style") or {}
        group_id = style.get("_border_group_id")
        if group_id is None:
            return

        frame_info = element.get("_frame_original") if isinstance(element.get("_frame_original"), dict) else {}
        frame_x = rect.x
        frame_y = rect.y
        frame_width = rect.width
        frame_height = rect.height
        if frame_info:
            try:
                frame_x = float(frame_info.get("x", frame_x))
                frame_y = float(frame_info.get("y", frame_y))
                frame_width = float(frame_info.get("width", frame_width))
                frame_height = float(frame_info.get("height", frame_height))
            except (TypeError, ValueError):
                frame_x = rect.x
                frame_y = rect.y
                frame_width = rect.width
                frame_height = rect.height

        top = frame_y + frame_height
        bottom = frame_y
        left = frame_x
        right = frame_x + frame_width

        key = (group_id, self.page_number)
        info = border_group_geometry.setdefault(
            key,
            {
                "left": left,
                "right": right,
                "top": top,
                "bottom": bottom,
                "styles": [],
                "decorator_block": None,
                "style_source": dict(style) if isinstance(style, dict) else style,  # OPTIMIZATION: shallow copy dict
                "between_lines": [],
            },
        )

        styles_list = info.get("styles")
        if isinstance(styles_list, list):
            styles_list.append(style)

        info["left"] = min(info.get("left", left), left)
        info["right"] = max(info.get("right", right), right)
        info["top"] = max(info.get("top", top), top)
        info["bottom"] = min(info.get("bottom", bottom), bottom)

        style_source = info.get("style_source") or {}
        borders_source = style_source.setdefault("borders", {})
        borders_current = style.get("borders") or {}
        if isinstance(borders_current, dict):
            for side_name, side_spec in borders_current.items():
                if isinstance(side_spec, dict):
                    borders_source[side_name] = dict(side_spec)  # OPTIMIZATION: shallow copy dict
        info["style_source"] = style_source

        between_spec = style.pop("_border_between_spec", None)
        between_specs: List[Dict[str, Any]] = []
        if isinstance(between_spec, list):
            between_specs = [spec for spec in between_spec if isinstance(spec, dict)]
        elif isinstance(between_spec, dict):
            between_specs = [between_spec]
        if between_specs:
            between_lines = info.get("between_lines")
            if isinstance(between_lines, list):
                for spec in between_specs:
                    between_lines.append(
                        {
                            "y": rect.y + rect.height,
                            "spec": dict(spec),  # OPTIMIZATION: shallow copy dict
                        }
                    )
        decorator_block = info.get("decorator_block")
        page = unified.pages[-1] if unified.pages else None
        if decorator_block is None and page is not None:
            style_source_or_style = info.get("style_source") or style
            decor_style = dict(style_source_or_style) if isinstance(style_source_or_style, dict) else style_source_or_style  # OPTIMIZATION: shallow copy dict
            for key_to_remove in (
                "_borders_to_draw",
                "_border_group_index",
                "_border_group_size",
                "_border_group_id",
                "_border_group_draw",
                "_border_between_spec",
                "_border_signature",
            ):
                decor_style.pop(key_to_remove, None)

            sequence, source_uid = self._allocate_block_identity(element, suffix="decor")
            decorator_block = LayoutBlock(
                frame=Rect(left, bottom, max(right - left, 0.0), max(top - bottom, 0.0)),
                block_type="decorator",
                content={
                    "type": "decorator",
                    "style": decor_style,
                    "between_lines": info.get("between_lines", []),
                },
                style=decor_style,
                page_number=self.page_number,
                source_uid=source_uid,
                sequence=sequence,
            )

            if page.blocks and page.blocks[-1] is paragraph_block:
                insertion_index = max(len(page.blocks) - 1, 0)
                page.blocks.insert(insertion_index, decorator_block)
            else:
                page.blocks.append(decorator_block)

            info["decorator_block"] = decorator_block
        else:
            decorator_block = info.get("decorator_block")

        if decorator_block is not None:
            decorator_block.frame = Rect(
                info["left"],
                info["bottom"],
                max(info["right"] - info["left"], 0.0),
                max(info["top"] - info["bottom"], 0.0),
            )
            decorator_block.page_number = self.page_number
            decor_style = decorator_block.style or {}
            style_source = info.get("style_source") or {}
            borders_source = copy.deepcopy(style_source.get("borders") or {})
            if borders_source:
                decor_style["borders"] = borders_source
            else:
                decor_style.pop("borders", None)
            for key_name in ("background", "background_color", "shadow"):
                value = style_source.get(key_name)
                if value is not None:
                    decor_style[key_name] = value
            decorator_block.content = {
                "type": "decorator",
                "style": decor_style,
                "between_lines": info.get("between_lines", []),
            }

        group_index = style.get("_border_group_index")
        group_size = style.get("_border_group_size")
        if (
            isinstance(group_index, int)
            and isinstance(group_size, int)
            and group_index == group_size - 1
        ):
            border_group_geometry.pop(key, None)

    def _layout_paragraph_with_pagination(
        self,
        element: Dict[str, Any],
        unified: UnifiedLayout,
        border_group_geometry: Dict[Tuple[int, int], Dict[str, Any]],
        available_width: float,
    ) -> None:
        style = element.get("style") or {}
        spacing_before = self._to_float(style.get("spacing_before"), 0.0)
        spacing_after = self._to_float(style.get("spacing_after"), 0.0)

        self._apply_inter_block_spacing(spacing_before, unified)
        spacing_before = 0.0

        payload = self._ensure_paragraph_layout_payload(element, available_width)
        settings = self._resolve_paragraph_pagination_settings(element)

        total_lines = len(payload.lines or [])
        if total_lines == 0:
            # Traktuj pusty paragraf jako pojedynczy segment.
            segment_payload = self._slice_paragraph_layout(payload, 0, 0)
            segment_element = self._clone_paragraph_segment_element(
                element,
                segment_payload,
                segment_index=0,
                segment_count=1,
                spacing_before=spacing_before,
                spacing_after=spacing_after,
            )
            self._mark_segment_payload_final(segment_payload, available_width)
            segment_height = self._compute_paragraph_segment_height(
                payload, 0, 0, include_padding_top=True, include_padding_bottom=True
            )
            rect = Rect(
                x=self.page_config.base_margins.left,
                y=self.current_y - segment_height,
                width=available_width,
                height=segment_height,
            )
            sequence, source_uid = self._allocate_block_identity(segment_element, suffix="seg0")
            content = self._prepare_block_content(segment_element, rect)
            block = LayoutBlock(
                frame=rect,
                block_type=segment_element["type"],
                content=content,
                style=segment_element["style"],
                page_number=self.page_number,
                source_uid=source_uid,
                sequence=sequence,
            )
            unified.add_block(block)
            self._page_has_content = True
            self._update_border_geometry_for_paragraph(
                segment_element,
                rect,
                border_group_geometry,
                unified,
                block,
            )
            self.current_y = rect.y
            self._pending_spacing_after = spacing_after
            return

        start = 0
        segment_index = 0
        produced_segments: List[Dict[str, Any]] = []
        force_split_allowed = False

        while start < total_lines:
            # Calculate available height, accounting for footnotes for current page (PDF only)
            bottom_limit = self._page_bottom_limit
            if self._is_pdf and self.footnote_renderer:
                footnote_height = self._calculate_footnotes_height_for_page(self.page_number)
                if footnote_height > 0:
                    # Add footnotes height to bottom_limit (footnotes occupy space above bottom margin)
                    bottom_limit = bottom_limit + footnote_height
            
            available_height = self.current_y - bottom_limit
            if available_height <= 0.0:
                self._new_page(unified)
                force_split_allowed = False
                continue

            break_index = self._determine_paragraph_break_index(
                payload,
                start,
                available_height,
                settings,
                force_split_allowed=force_split_allowed,
            )

            if break_index is None or break_index == start:
                if not force_split_allowed:
                    self._new_page(unified)
                    force_split_allowed = True
                    continue
                # If still no progress, force at least one line.
                break_index = min(total_lines, start + 1)

            force_split_allowed = False

            is_last_segment = break_index >= total_lines
            segment_payload = self._slice_paragraph_layout(payload, start, break_index)
            segment_height = self._compute_paragraph_segment_height(
                payload,
                start,
                break_index,
                include_padding_top=start == 0,
                include_padding_bottom=is_last_segment,
            )
            rect = Rect(
                x=self.page_config.base_margins.left,
                y=self.current_y - segment_height,
                width=available_width,
                height=segment_height,
            )

            segment_element = self._clone_paragraph_segment_element(
                element,
                segment_payload,
                segment_index=segment_index,
                segment_count=0,  # updated later
                spacing_before=0.0,
                spacing_after=spacing_after if is_last_segment else 0.0,
            )

            self._mark_segment_payload_final(segment_payload, available_width)
            sequence, source_uid = self._allocate_block_identity(
                segment_element,
                suffix=f"seg{segment_index}",
            )
            content = self._prepare_block_content(segment_element, rect)
            block = LayoutBlock(
                frame=rect,
                block_type=segment_element["type"],
                content=content,
                style=segment_element["style"],
                page_number=self.page_number,
                source_uid=source_uid,
                sequence=sequence,
            )
            unified.add_block(block)
            self._page_has_content = True
            self._update_border_geometry_for_paragraph(
                segment_element,
                rect,
                border_group_geometry,
                unified,
                block,
            )

            produced_segments.append(segment_element)

            self.current_y = rect.y
            if is_last_segment:
                self._pending_spacing_after = spacing_after
                break

            start = break_index
            segment_index += 1

            if self.current_y - self._page_bottom_limit <= 0.0:
                self._new_page(unified)
                force_split_allowed = False

        segment_count = max(len(produced_segments), 1)
        for idx, segment_element in enumerate(produced_segments):
            segment_element["_pagination_segment_count"] = segment_count
            segment_element["_pagination_segment_index"] = idx

        if segment_count > 0:
            self._pending_spacing_after = spacing_after

    def _layout_paragraph_without_pagination(
        self,
        element: Dict[str, Any],
        unified: UnifiedLayout,
        border_group_geometry: Dict[Tuple[int, int], Dict[str, Any]],
        available_width: float,
    ) -> None:
        payload = self._ensure_paragraph_layout_payload(element, available_width)
        segment_payload = payload
        segment_height = max(
            self._measure_paragraph_height(element, available_width),
            0.0,
        )
        rect = Rect(
            x=self.page_config.base_margins.left,
            y=self.current_y - segment_height,
            width=available_width,
            height=segment_height,
        )
        segment_element = dict(element)
        segment_element["layout_payload"] = segment_payload
        segment_element["_layout_payload"] = segment_payload
        style = dict(segment_element.get("style") or {})
        self._capture_html_spacing(style)
        style["spacing_before"] = 0.0
        style["spacing_after"] = 0.0
        segment_element["style"] = style
        segment_element.pop("_pagination_segment_index", None)
        segment_element.pop("_pagination_segment_count", None)
        self._mark_segment_payload_final(segment_payload, available_width)
        sequence, source_uid = self._allocate_block_identity(segment_element)
        content = self._prepare_block_content(segment_element, rect)
        block = LayoutBlock(
            frame=rect,
            block_type=segment_element["type"],
            content=content,
            style=segment_element["style"],
            page_number=self.page_number,
            source_uid=source_uid,
            sequence=sequence,
        )
        unified.add_block(block)
        self._page_has_content = True
        if not self._is_html:
            self._update_border_geometry_for_paragraph(
                segment_element,
                rect,
                border_group_geometry,
                unified,
                block,
            )
        self.current_y = rect.y
        self._pending_spacing_after = 0.0

    def _normalize_paragraph_style(self, style: Dict[str, Any]) -> Dict[str, Any]:
        base = dict(style)
        color_norm = self._normalize_color_value(base.get("color"))
        if color_norm:
            base["color"] = color_norm
        elif "color" in base:
            base.pop("color", None)

        font_color_norm = self._normalize_color_value(
            base.get("font_color") or base.get("fontColour")
        )
        if font_color_norm:
            base["font_color"] = font_color_norm
        elif "font_color" in base:
            base.pop("font_color", None)

        shading = self._normalize_shading(base.get("shading") or base.get("background"))
        if shading:
            base["shading"] = shading
            fill_color = shading.get("fill")
            if fill_color:
                base["background"] = fill_color
                base["background_color"] = fill_color
        border_norm = self._normalize_border_dict(base.get("border"))
        if border_norm:
            base["border"] = border_norm
        borders_raw = base.get("borders")
        if isinstance(borders_raw, dict):
            normalized_borders: Dict[str, Dict[str, Any]] = {}
            for side, spec in borders_raw.items():
                normalized_spec = self._normalize_border_dict(spec)
                if normalized_spec:
                    normalized_borders[self._strip_namespace(side).lower()] = normalized_spec
            if normalized_borders:
                base["borders"] = normalized_borders
        shadow_norm = self._normalize_shadow(base.get("shadow"))
        if shadow_norm:
            base["shadow"] = shadow_norm
        return base

    @staticmethod
    def _cache_paragraph_payload(element: Any, payload: ParagraphLayout) -> None:
        """
        Attach ParagraphLayout to the original element so downstream renderers
        can access precomputed layout metrics (also used by debug compiler).
        """
        if element is None or payload is None:
            return
        if isinstance(element, dict):
            element["layout_payload"] = payload
            element["_layout_payload"] = payload
        else:
            try:
                setattr(element, "layout_payload", payload)
            except Exception:
                pass
            try:
                setattr(element, "_layout_payload", payload)
            except Exception:
                pass

    def _ensure_layout_tree(self, element: Any) -> BaseNode:
        cached = self._get_cached_tree(element)
        if cached is not None:
            return cached
        try:
            tree = self.tree_dispatcher.dispatch(element)
        except LookupError:
            tree = BaseNode(
                kind=describe_element(element),
                source=element,
                metadata={"error": "no_engine_registered"},
            )
        self._cache_tree(element, tree)
        return tree

    # ----------------------------------------------------------------------
    def assemble(self, layout_structure):
        """
        Assemble layout structure into UnifiedLayout.
        
        Args:
            layout_structure: LayoutStructure from LayoutEngine
            
        Returns:
            UnifiedLayout with positioned blocks
        """
        self._border_group_serial = 0
        if self._is_pdf:
            self._apply_paragraph_border_grouping(layout_structure.body)
        self._block_counter = 0
        unified = UnifiedLayout()
        self._new_page(unified)
        border_group_geometry: Dict[Tuple[int, int], Dict[str, Any]] = {}
        
        # Collect watermarks from headers (will be added to all pages after assembling)
        collected_watermarks: List[Dict[str, Any]] = []
        
        # Process headers to detect watermarks
        if hasattr(layout_structure, "headers") and layout_structure.headers:
            logger.info(f"Processing {len(layout_structure.headers)} header types")
            for header_type, header_elements in layout_structure.headers.items():
                if not isinstance(header_elements, list):
                    logger.debug(f"Header type '{header_type}' is not a list: {type(header_elements)}")
                    continue
                logger.info(f"Processing header type '{header_type}' with {len(header_elements)} elements")
                for i, header_element in enumerate(header_elements):
                    # Check if element has textboxes with absolute positioning
                    if isinstance(header_element, dict):
                        element_type = header_element.get("type", "")
                        logger.debug(f"Header element {i}: type={element_type}, keys={list(header_element.keys())}")
                        # Check if element is paragraph with textboxes or images (watermarks)
                        if element_type == "paragraph":
                            # Check textboxes - we only use is_watermark flag from XML
                            textboxes = header_element.get("textboxes", [])
                            for j, textbox in enumerate(textboxes):
                                if isinstance(textbox, dict):
                                    # We only use is_watermark flag from parsed XML data
                                    if textbox.get("is_watermark", False):
                                        # This is a watermark - save for later addition
                                        anchor_type, anchor_info = extract_anchor_info(textbox)
                                        textbox["anchor_info"] = anchor_info
                                        textbox["is_watermark"] = True
                                        textbox["header_footer_context"] = "header"
                                        collected_watermarks.append(textbox)
                            
                            # Check images - we only use is_watermark flag from XML
                            images = header_element.get("images", [])
                            for j, image in enumerate(images):
                                if isinstance(image, dict):
                                    # We only use is_watermark flag from parsed XML data
                                    # Nie sprawdzamy heurystyk jak behindDoc czy anchor_type
                                    if image.get("is_watermark", False):
                                        # This is a watermark - save for later addition
                                        anchor_type = image.get("anchor_type", "")
                                        if "position" in image:
                                            image["anchor_info"] = {
                                                "anchor_type": anchor_type,
                                                "position": image.get("position", {})
                                            }
                                        image["is_watermark"] = True
                                        image["header_footer_context"] = "header"
                                        collected_watermarks.append(image)
                            
                            # Check VML shapes (text watermarks)
                            vml_shapes = header_element.get("vml_shapes", [])
                            for j, vml_shape in enumerate(vml_shapes):
                                if isinstance(vml_shape, dict):
                                    is_watermark = vml_shape.get("is_watermark", False)
                                    position_absolute = vml_shape.get("position", {}).get("absolute", False)
                                    # VML shape is watermark if it has is_watermark=True or absolute positioning
                                    if is_watermark or position_absolute:
                                        # This is a watermark - save for later addition
                                        vml_shape["is_watermark"] = True
                                        vml_shape["header_footer_context"] = "header"
                                        collected_watermarks.append(vml_shape)
                        # Check if element is directly a textbox - we only use is_watermark flag from XML
                        elif element_type == "textbox":
                            # We only use is_watermark flag from parsed XML data
                            if header_element.get("is_watermark", False):
                                # This is a watermark - save for later addition
                                anchor_type, anchor_info = extract_anchor_info(header_element)
                                header_element["anchor_info"] = anchor_info
                                header_element["is_watermark"] = True
                                header_element["header_footer_context"] = "header"
                                collected_watermarks.append(header_element)
                    else:
                        logger.debug(f"Header element {i} is not a dict: {type(header_element)}")
        else:
            logger.info(f"No headers found in layout_structure (has headers: {hasattr(layout_structure, 'headers')})")

        page_body_elements = layout_structure.body

        for element in page_body_elements:
            # Extract footnote references from element before processing
            if self.footnote_renderer:
                self._extract_footnote_refs_from_element(element, self.page_number)
            
            # Check page-break-before
            if element.get("page_break_before", False):
                self._new_page(unified)

            available_width = (
                self.page_config.page_size.width
                - self.page_config.base_margins.left
                - self.page_config.base_margins.right
            )

            style = element.get("style")
            if not isinstance(style, dict):
                style = {}
                element["style"] = style
            spacing_before = self._to_float(style.get("spacing_before"), 0.0)
            spacing_after = self._to_float(style.get("spacing_after"), 0.0)
            if self._is_html:
                self._capture_html_spacing(style)
                spacing_before = 0.0
                spacing_after = 0.0

            if element.get("type") == "paragraph":
                # Extract watermarks from paragraphs in headers before layout
                header_footer_context = element.get("header_footer_context")
                if header_footer_context == "header" and not self._is_html:
                    # Check if paragraph has textboxes with absolute positioning
                    textboxes = element.get("textboxes", [])
                    logger.debug(f"Paragraph in header has {len(textboxes)} textboxes")
                    for textbox in textboxes:
                        if isinstance(textbox, dict):
                            anchor_type, anchor_info = extract_anchor_info(textbox)
                            logger.debug(f"Textbox anchor_type={anchor_type}, anchor_info={anchor_info}")
                            if anchor_type == "anchor":
                                # This is a watermark - save for later addition
                                textbox["anchor_info"] = anchor_info
                                textbox["is_watermark"] = True
                                textbox["header_footer_context"] = "header"
                                collected_watermarks.append(textbox)
                
                if self._is_html:
                    self._layout_paragraph_without_pagination(
                        element,
                        unified,
                        border_group_geometry,
                        available_width,
                    )
                    self._pending_spacing_after = 0.0
                    continue
                self._layout_paragraph_with_pagination(
                    element,
                    unified,
                    border_group_geometry,
                    available_width,
                )

                if element.get("page_break_after", False):
                    self._new_page(unified)
                continue

            self._apply_inter_block_spacing(spacing_before, unified)
            block_height = self._measure_block_height(element)
            if self._is_html and block_height <= 0:
                block_height = style.get("explicit_height") or 0.0

            if not self._fits(block_height):
                self._new_page(unified)
                self._apply_inter_block_spacing(spacing_before, unified, enforce_min=False)

            y = self.current_y - block_height

            rect = Rect(
                x=self.page_config.base_margins.left,
                y=y,
                width=available_width,
                height=block_height
            )

            if element["type"] == "table" and not self._is_html:
                layout_info = element.get("layout_info", {}) or {}
                table_width = layout_info.get("table_width") or 0.0
                table_indent = float(layout_info.get("table_indent") or 0.0)
                table_indent = max(table_indent, 0.0)
                table_alignment = (
                    layout_info.get("table_alignment")
                    or element.get("style", {}).get("table_alignment")
                )
                max_width = max(available_width - table_indent, 0.0)
                if max_width <= 0 and table_width > 0:
                    max_width = table_width
                if table_width <= 0:
                    table_width = max_width
                if table_width and table_width > 0:
                    adjusted_width = min(table_width, max_width) if max_width > 0 else table_width
                    usable_width = max_width if max_width > 0 else adjusted_width
                    offset = 0.0
                    if table_alignment:
                        align_token = str(table_alignment).lower()
                        if align_token in {"center", "centre", "middle"}:
                            offset = max((usable_width - adjusted_width) / 2.0, 0.0)
                        elif align_token in {"right", "end"}:
                            offset = max(usable_width - adjusted_width, 0.0)
                    table_x = self.page_config.base_margins.left + table_indent + offset
                    rect = Rect(
                        x=table_x,
                        y=y,
                        width=adjusted_width,
                        height=block_height,
                    )
                    layout_info["table_x"] = table_x

            sequence, source_uid = self._allocate_block_identity(element)
            content = self._prepare_block_content(element, rect)
            block = LayoutBlock(
                frame=rect,
                block_type=element["type"],
                content=content,
                style=element["style"],
                page_number=self.page_number,
                source_uid=source_uid,
                sequence=sequence,
            )

            unified.add_block(block)
            self._page_has_content = True

            # zaktualizuj kursor
            self.current_y = y
            self._pending_spacing_after = spacing_after if not self._is_html else 0.0
            
            # Check page-break-after
            if element.get("page_break_after", False):
                self._new_page(unified)
        
        # After assembling is complete, add footnote blocks to all pages
        if self.footnote_renderer:
            for page in unified.pages:
                self._create_footnote_blocks(unified, page.number)
        
        # Add watermarks to all pages (after assembling, when all pages are created)
        if collected_watermarks and not self._is_html:
            for watermark_data in collected_watermarks:
                anchor_info = watermark_data.get("anchor_info", {})
                sequence, source_uid = self._allocate_block_identity(watermark_data, suffix="watermark")
                # Determine watermark type (textbox, image or vml_shape)
                watermark_type = watermark_data.get("type", "textbox")
                if watermark_type == "Image" or watermark_data.get("path") or watermark_data.get("image_path"):
                    watermark_type = "image"
                elif watermark_type == "vml_shape":
                    watermark_type = "vml_shape"  # VML shape jako textbox (tekst)
                else:
                    watermark_type = "textbox"
                
                watermark_content = {
                    "type": watermark_type,
                    "content": watermark_data,
                    "anchor_info": anchor_info,
                    "header_footer_context": "header",
                    "is_watermark": True,
                }
                # Use full page size for watermark
                watermark_rect = Rect(
                    x=0.0,
                    y=0.0,
                    width=self.page_config.page_size.width,
                    height=self.page_config.page_size.height,
                )
                watermark_block = LayoutBlock(
                    frame=watermark_rect,
                    block_type=watermark_type,  # Use proper type (image or textbox)
                    content=watermark_content,
                    style=watermark_data.get("style", {}),
                    page_number=1,  # Watermark will be on all pages
                    source_uid=source_uid,
                    sequence=sequence,
                )
                # Dodaj watermark do wszystkich stron
                for page in unified.pages:
                    page.blocks.append(watermark_block)
        
        # At the end of document, add endnotes under the last body element (PDF only)
        if self._is_pdf and self._endnotes_collected:
            self._create_endnotes_after_body(unified)

        # Add header/footer blocks to each page
        if hasattr(layout_structure, "headers") and layout_structure.headers:
            for header_type, header_elements in layout_structure.headers.items():
                if not isinstance(header_elements, list):
                    continue
                for header_element in header_elements:
                    if isinstance(header_element, dict):
                        # Add header as block to each page
                        for page in unified.pages:
                            header_rect = Rect(
                                x=self.page_config.base_margins.left,
                                y=self.page_config.page_size.height - self.page_config.base_margins.top - 20.0,  # 20pt header height
                                width=self.page_config.page_size.width - self.page_config.base_margins.left - self.page_config.base_margins.right,
                                height=20.0,
                            )
                            sequence, source_uid = self._allocate_block_identity(header_element, suffix="header")
                            content = self._prepare_block_content(header_element, header_rect)
                            header_block = LayoutBlock(
                                frame=header_rect,
                                block_type="header",
                                content=content.raw if hasattr(content, 'raw') else content,
                                style=header_element.get("style", {}),
                                page_number=page.number,
                                source_uid=source_uid,
                                sequence=sequence,
                            )
                            page.blocks.insert(0, header_block)  # Add at beginning
        
        # Footers are added by PaginationManager.apply_headers_footers(),
        # so we don't add them here to avoid duplication
        # if hasattr(layout_structure, "footers") and layout_structure.footers:
        #     for footer_type, footer_elements in layout_structure.footers.items():
        #         if not isinstance(footer_elements, list):
        #             continue
        #         for footer_element in footer_elements:
        #             if isinstance(footer_element, dict):
        #                 # Dodaj footer jako blok do każdej strony
        #                 for page in unified.pages:
        #                     footer_rect = Rect(
        #                         x=self.page_config.base_margins.left,
        #                         y=self.page_config.base_margins.bottom + 20.0,  # 20pt wysokość footera
        #                         width=self.page_config.page_size.width - self.page_config.base_margins.left - self.page_config.base_margins.right,
        #                         height=20.0,
        #                     )
        #                     sequence, source_uid = self._allocate_block_identity(footer_element, suffix="footer")
        #                     content = self._prepare_block_content(footer_element, footer_rect)
        #                     footer_block = LayoutBlock(
        #                         frame=footer_rect,
        #                         block_type="footer",
        #                         content=content.raw if hasattr(content, 'raw') else content,
        #                         style=footer_element.get("style", {}),
        #                         page_number=page.number,
        #                         source_uid=source_uid,
        #                         sequence=sequence,
        #                     )
        #                     page.blocks.append(footer_block)  # Dodaj na końcu

        return unified

    # ----------------------------------------------------------------------
    def _calculate_footnotes_height_for_page(self, page_number: int) -> float:
        """
Calculates footnotes height for page.

        Args:
        page_number: Page number

        Returns:
        Footnotes height in points

        """
        if not self.footnote_renderer:
            return 0.0
        
        footnote_ids = self._footnotes_per_page.get(page_number, [])
        if not footnote_ids:
            return 0.0
        
        # Calculate height based on number of footnotes and their content
        font_size = 9.0  # We use the same size as in renderer
        font_name = "DejaVuSans"
        line_height = font_size * 1.2
        indent = 15.0  # Indent for footnote number
        separator_height = 8.0  # Separator line + spacing (4pt separator + 4pt spacing)
        spacing_between = line_height * 0.5
        
        total_height = separator_height  # Separator at top
        
        # Get available page width (approximate, will be corrected in _create_footnote_blocks)
        # We use default A4 width minus margins
        available_width = 595.0 - 136.1 - 51.0  # Approximate width (will be corrected)
        
        for footnote_id in footnote_ids:
            footnote_data = self.footnote_renderer.footnotes.get(footnote_id)
            if not footnote_data:
                continue
            
            # Extract content - improved full text extraction
            content = ""
            if isinstance(footnote_data, dict):
                content_list = footnote_data.get('content', [])
                if isinstance(content_list, list):
                    # Content is a list of paragraphs
                    content_parts = []
                    for para in content_list:
                        if isinstance(para, dict):
                            # First try to get full paragraph text
                            para_text = para.get('text', '')
                            # If no text, collect from runs
                            if not para_text and para.get('runs'):
                                para_text = ' '.join([
                                    run.get('text', '') 
                                    for run in para.get('runs', []) 
                                    if isinstance(run, dict) and run.get('text')
                                ])
                            if para_text:
                                content_parts.append(para_text)
                        elif isinstance(para, str):
                            content_parts.append(para)
                        else:
                            content_parts.append(str(para))
                    content = ' '.join(content_parts)
                elif isinstance(content_list, str):
                    content = content_list
                else:
                    content = str(content_list) if content_list else ""
            elif hasattr(footnote_data, 'content'):
                content = str(footnote_data.content)
            elif hasattr(footnote_data, 'get_content'):
                content = str(footnote_data.get_content())
            else:
                content = str(footnote_data) if footnote_data else ""
            
            # Estimate lines needed - use TextMetricsEngine for more accurate measurement
            try:
                from ..text_metrics import TextMetricsEngine
                metrics = TextMetricsEngine()
                wrapped_lines = metrics.wrap_text(
                    content,
                    available_width - indent,  # Account for indent for number
                    font_name=font_name,
                    font_size=font_size
                )
                lines = len(wrapped_lines) if wrapped_lines else 1
            except Exception:
                # Fallback: rough approximation
                # Assume ~60 characters per line at 9pt font
                chars_per_line = 60
                lines = max(1, len(content) // chars_per_line + (1 if len(content) % chars_per_line > 0 else 0))
            
            footnote_height = lines * line_height + spacing_between
            total_height += footnote_height
        
        return total_height
    
    def _extract_footnote_refs_from_element(self, element: Dict[str, Any], page_number: int) -> None:
        """
Extracts footnote references from element and registers them for page.

        Args:
        element: Layout element (paragraph, table cell, etc.) - can be dict or object
        page_number: Page number

        """
        if not self.footnote_renderer:
            return
        
        # Handle both dict and object elements
        runs = []
        if isinstance(element, dict):
            runs = element.get("runs_payload") or element.get("runs", [])
        elif hasattr(element, "runs_payload"):
            runs = element.runs_payload
        elif hasattr(element, "runs"):
            runs = element.runs
        
        for run in runs:
            footnote_refs = []
            endnote_refs = []
            
            # Check if run is dict or object
            if isinstance(run, dict):
                # Check for footnote_refs directly in run dict
                footnote_refs = run.get("footnote_refs", [])
                endnote_refs = run.get("endnote_refs", [])
                
                # Also check in style (for backward compatibility)
                if not footnote_refs:
                    run_style = run.get("style", {})
                    footnote_refs = run_style.get("footnote_refs", [])
                if not endnote_refs:
                    run_style = run.get("style", {})
                    endnote_refs = run_style.get("endnote_refs", [])
            elif hasattr(run, "footnote_refs") or hasattr(run, "endnote_refs"):
                # Run is an object (Run instance)
                footnote_refs = getattr(run, "footnote_refs", [])
                endnote_refs = getattr(run, "endnote_refs", [])
            
            # Process footnote references
            if footnote_refs:
                if isinstance(footnote_refs, str):
                    footnote_refs = [footnote_refs]
                for footnote_id in footnote_refs:
                    if footnote_id:
                        if page_number not in self._footnotes_per_page:
                            self._footnotes_per_page[page_number] = []
                        if footnote_id not in self._footnotes_per_page[page_number]:
                            self._footnotes_per_page[page_number].append(footnote_id)
                            # Also register in footnote_renderer
                            footnote_data = self.footnote_renderer.footnotes.get(footnote_id)
                            if footnote_data:
                                self.footnote_renderer.register_footnote(footnote_id, footnote_data)
            
            # Process endnote references (same logic)
            if endnote_refs:
                if isinstance(endnote_refs, str):
                    endnote_refs = [endnote_refs]
                for endnote_id in endnote_refs:
                    if endnote_id:
                        # Register endnote and collect it for rendering at the end
                        endnote_data = self.footnote_renderer.endnotes.get(endnote_id)
                        if endnote_data:
                            self.footnote_renderer.register_endnote(endnote_id, endnote_data)
                            # Collect endnote for rendering at the end of document
                            if endnote_id not in [e.get('id') for e in self._endnotes_collected]:
                                self._endnotes_collected.append({
                                    'id': endnote_id,
                                    'data': endnote_data
                                })
        
        # Also check element itself (for cases where refs are at element level)
        element_footnote_refs = []
        element_endnote_refs = []
        
        if isinstance(element, dict):
            element_footnote_refs = element.get("footnote_refs", [])
            element_endnote_refs = element.get("endnote_refs", [])
        else:
            element_footnote_refs = getattr(element, "footnote_refs", [])
            element_endnote_refs = getattr(element, "endnote_refs", [])
        
        if element_footnote_refs:
            if isinstance(element_footnote_refs, str):
                element_footnote_refs = [element_footnote_refs]
            for footnote_id in element_footnote_refs:
                if footnote_id:
                    if page_number not in self._footnotes_per_page:
                        self._footnotes_per_page[page_number] = []
                    if footnote_id not in self._footnotes_per_page[page_number]:
                        self._footnotes_per_page[page_number].append(footnote_id)
                        footnote_data = self.footnote_renderer.footnotes.get(footnote_id)
                        if footnote_data:
                            self.footnote_renderer.register_footnote(footnote_id, footnote_data)
        
        if element_endnote_refs:
            if isinstance(element_endnote_refs, str):
                element_endnote_refs = [element_endnote_refs]
            for endnote_id in element_endnote_refs:
                if endnote_id:
                    endnote_data = self.footnote_renderer.endnotes.get(endnote_id)
                    if endnote_data:
                        self.footnote_renderer.register_endnote(endnote_id, endnote_data)
                        # Collect endnote for rendering at the end of document
                        if endnote_id not in [e.get('id') for e in self._endnotes_collected]:
                            self._endnotes_collected.append({
                                'id': endnote_id,
                                'data': endnote_data
                            })
    
    def _create_footnote_blocks(self, unified: UnifiedLayout, page_number: int) -> None:
        """Tworzy bloki footnotes dla strony i dodaje je do unified layout.
        
        Args:
            unified: UnifiedLayout
            page_number: Numer strony
        """
        if not self.footnote_renderer or not unified.pages:
            return
        
        footnote_ids = self._footnotes_per_page.get(page_number, [])
        if not footnote_ids:
            return
        
        # Find the page
        page = None
        for p in unified.pages:
            if p.number == page_number:
                page = p
                break
        
        if not page:
            return
        
        # Calculate footnote area position (above footer margin or footer, whichever is larger)
        margins = page.margins
        footnote_area_height = self._calculate_footnotes_height_for_page(page_number)
        if footnote_area_height <= 0:
            return
        
        # Calculate footer height if footer exists on this page
        footer_height = 0.0
        footer_bottom_y = 0.0  # Footer bottom Y coordinate (from bottom of page in PDF coordinates)
        # Check if page has footer blocks
        for block in page.blocks:
            if block.block_type == "footer":
                # block.frame.y is the BOTTOM edge of the block in PDF coordinates (Y=0 at bottom)
                footer_bottom_y = max(footer_bottom_y, block.frame.y)
                footer_height = max(footer_height, block.frame.height)
        
        # Footnotes should be above footer OR above bottom margin, whichever is larger
        # In PDF coordinates: Y=0 is at bottom, Y increases upward
        # block.frame.y is the BOTTOM edge of the block
        # So footnotes bottom should be at: max(footer_bottom_y + footer_height, margins.bottom) + footnote_area_height
        # But we want footnotes ABOVE footer, so:
        # footnote_y (bottom edge) = max(footer_bottom_y + footer_height, margins.bottom)
        bottom_space = max(footer_bottom_y + footer_height, margins.bottom)
        footnote_y = bottom_space  # Bottom edge of footnotes block (from bottom of page)
        footnote_height = footnote_area_height
        
        # Prepare footnote content
        footnote_content = {
            'type': 'footnotes',
            'footnotes': []
        }
        
        for footnote_id in sorted(footnote_ids, key=lambda x: self.footnote_renderer.get_footnote_number(x) or 0):
            footnote_data = self.footnote_renderer.footnotes.get(footnote_id)
            number = self.footnote_renderer.get_footnote_number(footnote_id) or "?"
            
            # Extract content - improved full text extraction
            content = ""
            if isinstance(footnote_data, dict):
                content_list = footnote_data.get('content', [])
                if isinstance(content_list, list):
                    # Content is a list of paragraphs
                    content_parts = []
                    for para in content_list:
                        if isinstance(para, dict):
                            # First try to get full paragraph text
                            para_text = para.get('text', '')
                            # If no text, collect from runs
                            if not para_text and para.get('runs'):
                                para_text = ' '.join([
                                    run.get('text', '') 
                                    for run in para.get('runs', []) 
                                    if isinstance(run, dict) and run.get('text')
                                ])
                            if para_text:
                                content_parts.append(para_text)
                        elif isinstance(para, str):
                            content_parts.append(para)
                        else:
                            content_parts.append(str(para))
                    content = ' '.join(content_parts)
                elif isinstance(content_list, str):
                    content = content_list
                else:
                    content = str(content_list) if content_list else ""
            elif hasattr(footnote_data, 'content'):
                content = str(footnote_data.content)
            elif hasattr(footnote_data, 'get_content'):
                content = str(footnote_data.get_content())
            else:
                content = str(footnote_data) if footnote_data else "[Footnote not found]"
            
            footnote_content['footnotes'].append({
                'id': footnote_id,
                'number': number,
                'content': content
            })
        
        # Create LayoutBlock for footnotes
        footnote_rect = Rect(
            x=margins.left,
            y=footnote_y,
            width=page.size.width - margins.left - margins.right,
            height=footnote_height
        )
        
        footnote_block = LayoutBlock(
            frame=footnote_rect,
            block_type="footnotes",
            content=footnote_content,
            style={},
            page_number=page_number,
            source_uid=None,
            sequence=None,
        )
        
        page.add_block(footnote_block)
    
    def _create_endnotes_after_body(self, unified: UnifiedLayout) -> None:
        """
Creates endnotes under the last body element.
        Endnotes are rendered as block type "endnotes" (same as footnotes).

        Args:
        unified: UnifiedLayout

        """
        if not self.footnote_renderer or not self._endnotes_collected:
            return
        
        # Check if we have current page
        if not unified.pages:
            return
        
        # Use current page and margins (don't create new page)
        current_page = unified.pages[-1]
        margins = current_page.margins
        
        # Calculate endnotes height (similar to footnotes)
        endnote_area_height = self._calculate_endnotes_height()
        if endnote_area_height <= 0:
            return
        
        # Check if endnotes will fit on current page
        # If not, create new page
        available_height = self.current_y - margins.bottom
        if endnote_area_height > available_height:
            # Endnotes won't fit - create new page
            self._new_page(unified)
            current_page = unified.pages[-1]
            margins = current_page.margins
            self.current_y = self.page_config.page_size.height - margins.top
        
        # Calculate endnotes position (under last body element)
        endnote_y = self.current_y - endnote_area_height
        endnote_height = endnote_area_height
        
        # Sort endnotes by numbers
        sorted_endnotes = sorted(
            self._endnotes_collected,
            key=lambda e: self.footnote_renderer.get_endnote_number(e['id']) or 0
        )
        
        # Prepare endnote content (podobnie jak footnotes)
        endnote_content = {
            'type': 'endnotes',
            'endnotes': []
        }
        
        for endnote_item in sorted_endnotes:
            endnote_id = endnote_item['id']
            endnote_data = endnote_item['data']
            endnote_number = self.footnote_renderer.get_endnote_number(endnote_id) or "?"
            
            # Extract content - podobnie jak w footnotes
            content = ""
            if isinstance(endnote_data, dict):
                content_list = endnote_data.get('content', [])
                if isinstance(content_list, list):
                    # Content is a list of paragraphs
                    content_parts = []
                    for para in content_list:
                        if isinstance(para, dict):
                            # First try to get full paragraph text
                            para_text = para.get('text', '')
                            # If no text, collect from runs
                            if not para_text and para.get('runs'):
                                para_text = ' '.join([
                                    run.get('text', '') 
                                    for run in para.get('runs', []) 
                                    if isinstance(run, dict) and run.get('text')
                                ])
                            if para_text:
                                content_parts.append(para_text)
                        elif isinstance(para, str):
                            content_parts.append(para)
                        else:
                            content_parts.append(str(para))
                    content = ' '.join(content_parts)
                elif isinstance(content_list, str):
                    content = content_list
                else:
                    content = str(content_list) if content_list else ""
            elif hasattr(endnote_data, 'content'):
                content = str(endnote_data.content)
            elif hasattr(endnote_data, 'get_content'):
                content = str(endnote_data.get_content())
            else:
                content = str(endnote_data) if endnote_data else "[Endnote not found]"
            
            endnote_content['endnotes'].append({
                'id': endnote_id,
                'number': endnote_number,
                'content': content
            })
        
        # Create LayoutBlock for endnotes (podobnie jak footnotes)
        endnote_rect = Rect(
            x=margins.left,
            y=endnote_y,
            width=current_page.size.width - margins.left - margins.right,
            height=endnote_height
        )
        
        endnote_block = LayoutBlock(
            frame=endnote_rect,
            block_type="endnotes",
            content=endnote_content,
            style={},
            page_number=current_page.number,
            source_uid=None,
            sequence=None,
        )
        
        current_page.add_block(endnote_block)
        
        # Update cursor position (endnotes take up space)
        self.current_y = endnote_y
    
    def _calculate_endnotes_height(self) -> float:
        """
Calculates endnotes height (similar to footnotes).

        Returns:
        Endnotes height in points

        """
        if not self.footnote_renderer or not self._endnotes_collected:
            return 0.0
        
        # Use similar logic as in _calculate_footnotes_height_for_page
        font_size = 9.0  # Mniejszy font dla endnotes (jak footnotes)
        font_name = "DejaVuSans"
        line_height = font_size * 1.2
        separator_height = 8.0  # Separator line + spacing (4pt separator + 4pt spacing)
        spacing_between = line_height * 0.5
        
        total_height = separator_height  # Separator at top
        
        # Get available width (approximate)
        available_width = 595.0 - 136.1 - 51.0  # Approximate width (will be corrected)
        
        for endnote_item in self._endnotes_collected:
            endnote_data = endnote_item.get('data')
            if not endnote_data:
                continue
            
            # Extract content - podobnie jak w footnotes
            content = ""
            if isinstance(endnote_data, dict):
                content_list = endnote_data.get('content', [])
                if isinstance(content_list, list):
                    content_parts = []
                    for para in content_list:
                        if isinstance(para, dict):
                            para_text = para.get('text', '')
                            if not para_text and para.get('runs'):
                                para_text = ' '.join([
                                    run.get('text', '') 
                                    for run in para.get('runs', []) 
                                    if isinstance(run, dict) and run.get('text')
                                ])
                            if para_text:
                                content_parts.append(para_text)
                        elif isinstance(para, str):
                            content_parts.append(para)
                        else:
                            content_parts.append(str(para))
                    content = ' '.join(content_parts)
                elif isinstance(content_list, str):
                    content = content_list
                else:
                    content = str(content_list) if content_list else ""
            elif hasattr(endnote_data, 'content'):
                content = str(endnote_data.content)
            elif hasattr(endnote_data, 'get_content'):
                content = str(endnote_data.get_content())
            else:
                content = str(endnote_data) if endnote_data else ""
            
            # Estimate lines needed - use TextMetricsEngine for more accurate measurement
            try:
                from ..text_metrics import TextMetricsEngine
                metrics = TextMetricsEngine()
                wrapped_lines = metrics.wrap_text(
                    content,
                    available_width - 15.0,  # Account for indent for number (similar to footnotes)
                    font_name=font_name,
                    font_size=font_size
                )
                lines = len(wrapped_lines) if wrapped_lines else 1
            except Exception:
                # Fallback: rough approximation
                chars_per_line = 60
                lines = max(1, len(content) // chars_per_line + (1 if len(content) % chars_per_line > 0 else 0))
            
            endnote_height = lines * line_height + spacing_between
            total_height += endnote_height
        
        return total_height
    
    def _new_page(self, unified):
        """Creates new page in unified layout and resets cursor position."""
        self.page_number += 1
        margins = self.page_config.base_margins
        # Use self.page_number instead of unified.current_page to ensure synchronization
        # unified.new_page() uses unified.current_page, but we want to use self.page_number
        # So first set unified.current_page to proper value BEFORE calling new_page()
        # unified.new_page() will use unified.current_page to set page.number, then increment unified.current_page
        unified.current_page = self.page_number
        page = unified.new_page(
            self.page_config.page_size,
            margins
        )
        # Check if page.number is correctly set (should equal self.page_number)
        # If not, set it manually
        if page.number != self.page_number:
            # Fix: set page.number manually
            page.number = self.page_number

        if self.page_variator:
            variant = self.page_variator.get_variant(self.page_number)
            self.current_y = self.page_config.page_size.height - variant.body_top_offset
            base_bottom = variant.body_bottom_offset
        else:
            self.current_y = self.page_config.page_size.height - self.page_config.base_margins.top
            base_bottom = self.page_config.base_margins.bottom
        
        # Account for footnotes height for new page
        footnote_height = 0.0
        if self.footnote_renderer:
            footnote_height = self._calculate_footnotes_height_for_page(self.page_number)
        
        self._page_bottom_limit = base_bottom + footnote_height
        self._pending_spacing_after = 0.0
        self._page_has_content = False
        return page

    # ----------------------------------------------------------------------
    def _fits(self, block_height: float) -> bool:
        """
Checks if block will fit on page.
        Accounts for footnotes height for current page (PDF only).
        Footnotes are rendered above bottom margin, so they reduce available space.

        """
        bottom_limit = self._page_bottom_limit
        
        # For PDF, account for footnotes height for current page
        if self._is_pdf and self.footnote_renderer:
            footnote_height = self._calculate_footnotes_height_for_page(self.page_number)
            if footnote_height > 0:
                # Add footnotes height to bottom_limit (footnotes occupy space above bottom margin)
                # In PDF coordinates: Y=0 at bottom, Y increases upward
                # bottom_limit is minimum Y position (from page bottom)
                # If we have footnotes, they must be above bottom margin, so we increase bottom_limit
                bottom_limit = bottom_limit + footnote_height
        
        return (self.current_y - block_height) > bottom_limit

    # ----------------------------------------------------------------------
    def _measure_block_height(self, element) -> float:
        """

        Calculates actual element height.
        Uses line_breaker for paragraphs, estimates for other types.

        Args:
        element: Element from LayoutStructure

        Returns:
        Height in points

        """
        t = element["type"]
        style = element.get("style", {})
        
        # Calculate available width
        available_width = (
            self.page_config.page_size.width
            - self.page_config.base_margins.left
            - self.page_config.base_margins.right
        )

        if t == "paragraph":
            return self._measure_paragraph_height(element, available_width)
        elif t == "table":
            return self._measure_table_height(element)
        elif t == "image":
            return self._measure_image_height(element, available_width)
        elif t == "textbox":
            return self._measure_textbox_height(element, available_width)
        else:
            return 20.0
    
    def _ensure_paragraph_layout_payload(
        self, element: dict, available_width: float
    ) -> ParagraphLayout:
        payload = element.get("_layout_payload")
        if not isinstance(payload, ParagraphLayout):
            payload = self._build_paragraph_layout(element, available_width)
            element["_layout_payload"] = payload
            element["layout_payload"] = payload
            if isinstance(payload, ParagraphLayout):
                self._cache_paragraph_payload(element, payload)
        return payload

    def _measure_paragraph_height(self, element: dict, available_width: float) -> float:
        """

        Calculates paragraph height using line_breaker.

        Args:
        element: Paragraph element
        available_width: Available width in points

        Returns:
        Height in points

        """
        if self._is_html:
            payload = self._ensure_paragraph_layout_payload(element, available_width)
        else:
            payload = self._ensure_paragraph_layout_payload(element, available_width)

        if not payload.lines:
            fallback = element.get("style", {}).get("line_spacing", 12.0)
            return float(fallback)

        last_line = payload.lines[-1]
        text_height = last_line.baseline_y + last_line.height
        padding_top, _, padding_bottom, _ = payload.style.padding

        return padding_top + text_height + padding_bottom

    def _prepare_block_content(self, element: dict, rect: Rect) -> BlockContent:
        """

        Builds standard BlockContent with payload depending on block type.

        """
        block_type = element.get("type")

        if block_type == "paragraph":
            payload = element.get("layout_payload")
            block_rect_width = rect.width if rect is not None else None
            original_frame = None
            if rect is not None:
                original_frame = {
                    "x": float(rect.x),
                    "y": float(rect.y),
                    "width": float(rect.width),
                    "height": float(rect.height),
                }
                element["_frame_original"] = original_frame
            needs_rebuild = (
                not isinstance(payload, ParagraphLayout)
                or payload.metadata.get("block_rect_is_final") is not True
                or payload.metadata.get("block_rect_width") != block_rect_width
            )
            if needs_rebuild and not self._is_html:
                payload = self._build_paragraph_layout(element, rect.width, rect)
                element["layout_payload"] = payload

            layout_metrics = element.get("layout_metrics") or {}
            text_frame = layout_metrics.get("text_frame") or {}
            indent_data = element.get("indent") or element.get("style", {}).get("indent", {}) or {}

            def _to_float(value: Any) -> float:
                if value is None or value == "":
                    return 0.0
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return 0.0

            indent_left = _to_float(indent_data.get("left_pt") or indent_data.get("left"))
            indent_right = _to_float(indent_data.get("right_pt") or indent_data.get("right"))
            indent_hanging = _to_float(indent_data.get("hanging_pt") or indent_data.get("hanging"))
            base_rect_x = rect.x
            text_offset_first = float(text_frame.get("x", 0.0)) if text_frame else 0.0
            text_area_width = float(text_frame.get("width") or 0.0) if text_frame else rect.width - indent_left - indent_right
            if text_area_width <= 0.0:
                text_area_width = rect.width - indent_left - indent_right
            rect.x = base_rect_x + indent_left
            rect.width = max(0.0, text_area_width)
            text_frame["abs_area_x"] = rect.x
            text_frame["abs_first_line_x"] = rect.x + text_offset_first
            text_frame["abs_width"] = rect.width
            layout_metrics["text_frame"] = text_frame
            element["layout_metrics"] = layout_metrics

        marker = element.get("marker")
        if marker and isinstance(payload, ParagraphLayout) and rect is not None:
            padding_top, _, _, _ = payload.style.padding
            first_line = payload.lines[0] if payload.lines else None
            line_height = first_line.height if first_line else 0.0
            baseline_offset = padding_top + (first_line.baseline_y if first_line else 0.0) + (line_height * 0.8 if line_height else 0.0)
            number_offset = marker.get("number_position")
            if number_offset is None:
                number_offset = indent_data.get("number_position_pt")
            if number_offset is None:
                fallback_left = _to_float(marker.get("indent_left")) or indent_left
                fallback_hanging = _to_float(marker.get("indent_hanging")) or indent_hanging
                number_offset = fallback_left - fallback_hanging
                marker.setdefault("number_position", number_offset)
            hanging_for_marker = _to_float(marker.get("indent_hanging")) if marker.get("indent_hanging") is not None else indent_hanging
            marker_x = rect.x - hanging_for_marker
            marker["baseline_offset"] = baseline_offset
            marker["x"] = marker_x
            text_position = marker.get("text_position")
            if text_position is None:
                text_position = indent_data.get("text_position_pt", indent_data.get("left_pt", 0.0))
                marker["text_position"] = text_position
            marker.setdefault("render_text_x", rect.x + text_offset_first if rect else text_position)
            marker["relative_to_text"] = marker_x - (rect.x + text_offset_first)
            element["marker"] = marker

            if isinstance(payload, ParagraphLayout):
                payload.metadata["block_rect_is_final"] = True
                payload.metadata["block_rect_width"] = rect.width
                payload.metadata["text_frame_abs"] = {
                    "area_x": rect.x,
                    "first_line_x": rect.x + text_offset_first,
                    "width": rect.width,
                }
            return BlockContent(payload=payload, raw=element)

        # Other types - use GenericLayout with optional overlays
        overlays: List[OverlayBox] = []
        if not self._is_html:
            for image in element.get("images", []) if isinstance(element, dict) else []:
                anchor_type, _ = extract_anchor_info(image)
                if anchor_type == "anchor":
                    overlays.append(
                        create_overlay_box(
                            kind="image",
                            source=image,
                            block_rect=rect,
                            default_width=rect.width * 0.3 if rect.width else 50.0,
                            default_height=rect.height if rect.height else 40.0,
                            page_config=self.page_config,
                        )
                    )
            for textbox in element.get("textboxes", []) if isinstance(element, dict) else []:
                anchor_type, anchor_info = extract_anchor_info(textbox)
                if anchor_type == "anchor":
                    # Check if this is watermark (textbox in header with absolute positioning)
                    header_footer_context = element.get("header_footer_context")
                    is_watermark = header_footer_context == "header" and anchor_type == "anchor"
                    
                    if is_watermark:
                        # Watermark - ekstraktuj jako osobny blok watermark
                        # Save watermark info in content so PDF compiler can detect it
                        if isinstance(textbox, dict):
                            textbox["anchor_info"] = anchor_info
                            textbox["is_watermark"] = True
                            # Add textbox to content as watermark (will be extracted later)
                            if "watermarks" not in element:
                                element["watermarks"] = []
                            element["watermarks"].append(textbox)
                    else:
                        # Normalny textbox - dodaj jako overlay
                        parent_width = rect.width if rect and rect.width else self.page_config.page_size.width
                        prepared = self._prepare_textbox_overlay(textbox, parent_width)
                        overlay_box = create_overlay_box(
                            kind="textbox",
                            source=textbox,
                            block_rect=rect,
                            default_width=prepared[0] if prepared else (rect.width * 0.25 if rect and rect.width else parent_width * 0.25),
                            default_height=prepared[1] if prepared else (rect.height if rect and rect.height else 40.0),
                            page_config=self.page_config,
                        )
                        if prepared:
                            width_pt, height_pt, payload, overlay_style = prepared
                            overlay_box.payload["layout_payload"] = payload
                            overlay_box.payload.setdefault("style", overlay_style)
                            overlay_box.frame = Rect(
                                overlay_box.frame.x,
                                overlay_box.frame.y,
                                width_pt,
                                height_pt,
                            )
                        overlays.append(overlay_box)
        generic_payload = GenericLayout(frame=rect, data=element, overlays=overlays)
        return BlockContent(payload=generic_payload, raw=element)

    def _prepare_textbox_overlay(
        self,
        textbox: Dict[str, Any],
        parent_available_width: float,
    ) -> Optional[Tuple[float, float, ParagraphLayout, Dict[str, Any]]]:
        if not isinstance(textbox, dict):
            return None

        fallback_width = max(parent_available_width, 1.0)
        width_pt = extract_dimension(textbox, "width", fallback_width)
        width_pt = max(width_pt, 1.0)

        raw_items = textbox.get("content")
        run_entries: List[Dict[str, Any]] = []

        if isinstance(raw_items, list):
            for item in raw_items:
                text_value: str = ""
                if hasattr(item, "get_text"):
                    text_value = item.get_text() or ""
                elif isinstance(item, dict):
                    text_value = str(item.get("text") or "")
                elif isinstance(item, str):
                    text_value = item
                elif item is not None:
                    text_value = str(item)
                text_value = text_value.replace("\r\n", "\n").replace("\r", "\n")
                if not text_value and not getattr(item, "has_break", False):
                    continue

                run_style: Dict[str, Any] = {}
                font_name = getattr(item, "font_name", None)
                if font_name:
                    run_style["font_name"] = font_name
                font_size_raw = getattr(item, "font_size", None)
                normalized_size = normalize_font_size(font_size_raw)
                if normalized_size:
                    run_style["font_size"] = normalized_size
                if getattr(item, "bold", False):
                    run_style["bold"] = True
                if getattr(item, "italic", False):
                    run_style["italic"] = True
                if getattr(item, "underline", False):
                    run_style["underline"] = True
                color_raw = getattr(item, "color", None)
                if color_raw:
                    normalized_color = self._normalize_color_value(color_raw)
                    if normalized_color:
                        run_style["color"] = normalized_color

                run_entries.append(
                    {
                        "text": text_value,
                        "style": run_style,
                    }
                )

        if not run_entries:
            fallback_text = str(textbox.get("text") or "")
            fallback_text = fallback_text.replace("\r\n", "\n").replace("\r", "\n")
            if fallback_text:
                run_entries.append({"text": fallback_text, "style": {}})

        if not run_entries:
            return None

        for entry in run_entries[:-1]:
            entry["has_break"] = True

        font_size_from_runs: Optional[float] = None
        font_name_from_runs: Optional[str] = None
        font_color_from_runs: Optional[str] = None
        spacing_from_runs: Optional[Dict[str, Any]] = None
        if isinstance(raw_items, list):
            for item in raw_items:
                if item is None:
                    continue
                if font_size_from_runs is None:
                    candidate_size = getattr(item, "paragraph_font_size", None)
                    if candidate_size not in (None, "", 0):
                        try:
                            font_size_from_runs = float(candidate_size)
                        except (TypeError, ValueError):
                            font_size_from_runs = None
                if font_name_from_runs is None:
                    candidate_name = getattr(item, "paragraph_font_name", None)
                    if candidate_name:
                        font_name_from_runs = str(candidate_name)
                if font_color_from_runs is None:
                    candidate_color = getattr(item, "paragraph_font_color", None)
                    if candidate_color:
                        font_color_from_runs = str(candidate_color)
                if spacing_from_runs is None:
                    candidate_spacing = getattr(item, "paragraph_spacing", None)
                    if isinstance(candidate_spacing, dict) and candidate_spacing:
                        spacing_from_runs = dict(candidate_spacing)

        paragraph_style = dict(textbox.get("style") or {})  # OPTIMIZATION: shallow copy dict
        if font_size_from_runs and "font_size" not in paragraph_style:
            paragraph_style["font_size"] = font_size_from_runs
        if font_name_from_runs and "font_name" not in paragraph_style:
            paragraph_style["font_name"] = font_name_from_runs
        if font_color_from_runs and "color" not in paragraph_style:
            paragraph_style["color"] = font_color_from_runs
        if spacing_from_runs:
            spacing_dict = paragraph_style.setdefault("spacing", {})
            before_raw = spacing_from_runs.get("before")
            after_raw = spacing_from_runs.get("after")
            line_raw = spacing_from_runs.get("line")
            line_rule = spacing_from_runs.get("line_rule")
            if before_raw not in (None, "", "0"):
                try:
                    spacing_dict["before"] = twips_to_points(float(before_raw))
                except (TypeError, ValueError):
                    pass
            if after_raw not in (None, "", "0"):
                try:
                    spacing_dict["after"] = twips_to_points(float(after_raw))
                except (TypeError, ValueError):
                    pass
            if line_raw not in (None, "", "0"):
                try:
                    spacing_dict["line"] = twips_to_points(float(line_raw))
                    paragraph_style.setdefault("line_spacing", spacing_dict["line"])
                except (TypeError, ValueError):
                    pass
            if line_rule:
                paragraph_style.setdefault("line_spacing_rule", line_rule)
        style_ref = textbox.get("style_ref") or textbox.get("style_id")
        if style_ref:
            paragraph_style.setdefault("style_id", style_ref)
            paragraph_style.setdefault("style_name", paragraph_style.get("style_name") or style_ref)
        paragraph_element = {
            "type": "paragraph",
            "style": paragraph_style,
            "runs_payload": run_entries,
        }
        if style_ref:
            paragraph_element["style_ref"] = style_ref
            paragraph_element.setdefault("style_name", style_ref)

        temp_rect = Rect(0.0, 0.0, width_pt, 0.0)
        payload = self._build_paragraph_layout(paragraph_element, width_pt, temp_rect)

        padding_top, padding_right, padding_bottom, padding_left = (
            payload.style.padding if payload.style else (0.0, 0.0, 0.0, 0.0)
        )
        if payload.lines:
            last_line = payload.lines[-1]
            content_height = last_line.baseline_y + last_line.height
        else:
            content_height = 0.0

        computed_height = content_height + padding_top + padding_bottom
        declared_height = extract_dimension(
            textbox,
            "height",
            computed_height if computed_height > 0.0 else 0.0,
        )
        final_height = computed_height
        if declared_height > 0.0:
            final_height = max(declared_height, computed_height)
        elif final_height <= 0.0:
            default_size = normalize_font_size(paragraph_element["style"].get("font_size"))
            if not default_size:
                default_size = next(
                    (
                        entry["style"].get("font_size")
                        for entry in run_entries
                        if entry["style"].get("font_size")
                    ),
                    None,
                )
            final_height = max(float(default_size or 11.0), 1.0) + padding_top + padding_bottom

        overlay_style = dict(paragraph_element.get("style") or {})  # OPTIMIZATION: shallow copy dict
        if "font_size" not in overlay_style:
            first_font_size = next(
                (
                    entry["style"].get("font_size")
                    for entry in run_entries
                    if entry["style"].get("font_size")
                ),
                None,
            )
            if first_font_size:
                overlay_style["font_size"] = first_font_size

        return width_pt, final_height, payload, overlay_style

    def _build_paragraph_layout(self, element: dict, available_width: float, block_rect: Optional[Rect] = None) -> ParagraphLayout:
        """

        Creates ParagraphLayout with simple text segmentation into lines, fields and inline elements.

        """
        style = self._ensure_paragraph_style(element)
        if block_rect is not None:
            available_width = block_rect.width
        text = (element.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
        fields = element.get("fields") or []
        textboxes = element.get("textboxes") or []
        images = element.get("images") or []

        def _resolve_line_spacing(style_dict: Dict[str, Any], element_dict: dict, base_font: float) -> Optional[float]:
            def _as_float(value: Any) -> Optional[float]:
                if value in (None, ""):
                    return None
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            spacing_rule = style_dict.get("line_spacing_rule") or element_dict.get("line_spacing_rule")
            spacing_value = style_dict.get("line_spacing")
            if spacing_value is None:
                spacing_value = element_dict.get("line_spacing")

            spacing_map = element_dict.get("spacing") or style_dict.get("spacing") or {}
            if not isinstance(spacing_map, dict):
                spacing_map = {}
            line_attr = spacing_map.get("line")

            rule = str(spacing_rule).lower() if spacing_rule else None

            if rule == "auto":
                factor = None
                line_val = _as_float(line_attr)
                if line_val is not None:
                    factor = line_val / 240.0
                if factor is None:
                    factor = _as_float(spacing_value)
                if factor is None:
                    return None
                return base_font * factor

            if rule == "exact":
                length = None
                line_val = _as_float(line_attr)
                if line_val is not None:
                    length = line_val / 20.0
                if length is None:
                    length = _as_float(spacing_value)
                return length

            if rule == "atleast":
                length = None
                line_val = _as_float(line_attr)
                if line_val is not None:
                    length = line_val / 20.0
                if length is None:
                    length = _as_float(spacing_value)
                if length is None:
                    return None
                return max(length, base_font)

            # Unknown rule – try to interpret as multiplier or absolute value
            factor = _as_float(spacing_value)
            if factor is not None and factor <= 10:
                return base_font * factor
            if factor is not None:
                return factor
            line_val = _as_float(line_attr)
            if line_val is not None:
                return line_val / 20.0
            return None

        base_font_size = style.get("font_size")
        font_size = normalize_font_size(base_font_size)

        run_font_sizes: List[float] = []
        for run in element.get("runs", []):
            run_dict = coerce_element_dict(run, getattr(run, "type", None)) if not isinstance(run, dict) else run
            run_style = run_dict.get("style") or {}
            run_font_size_raw = (
                run_dict.get("font_size")
                or run_style.get("font_size")
                or run_style.get("font_size_cs")
                or run_dict.get("font_size_cs")
            )
            run_font_size = normalize_font_size(run_font_size_raw)
            if run_font_size is not None and run_font_size > 0:
                run_font_sizes.append(run_font_size)

        if run_font_sizes:
            max_run_font = max(run_font_sizes)
            min_run_font = min(run_font_sizes)
            # If all runs have the same (or nearly the same) size, use it as base
            if font_size is None or abs(max_run_font - min_run_font) < 0.01:
                font_size = max_run_font
            else:
                # For mixed sizes, ensure base font is at least as large as the largest run
                if font_size is None or max_run_font > font_size:
                    font_size = max_run_font

        if font_size is None:
            font_size = 11.0
        style["font_size"] = font_size
        line_spacing = _resolve_line_spacing(style, element, font_size)
        if line_spacing is None:
            line_spacing = 0.0
        fallback_char_width = max(font_size * 0.6, 0.1)
        available_width = max(available_width, fallback_char_width)

        indent_dict = element.get("indent") or style.get("indent") or {}
        if not isinstance(indent_dict, dict):
            indent_dict = {}

        def _to_float(value: Any) -> Optional[float]:
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        indent_left = _to_float(indent_dict.get("left_pt") or indent_dict.get("left")) or 0.0
        indent_right = _to_float(indent_dict.get("right_pt") or indent_dict.get("right")) or 0.0
        indent_hanging = _to_float(indent_dict.get("hanging_pt") or indent_dict.get("hanging")) or 0.0
        # Always calculate first_line from left and hanging, ignoring first_line from parser
        # (parser may set first_line_indent = -hanging_indent, which is incorrect)
        if indent_hanging:
            indent_first_line = indent_left - indent_hanging
        else:
            # If no hanging, check if first_line is set in indent_dict
            indent_first_line = _to_float(indent_dict.get("first_line_pt") or indent_dict.get("first_line"))
            if indent_first_line is None:
                indent_first_line = indent_hanging
        text_position = _to_float(indent_dict.get("text_position_pt"))
        if text_position is None:
            # text_position is position where first line text starts
            # For hanging indent: first_line = 0.0, so text_position = 0.0
            # Dla first_line indent: text_position = first_line
            text_position = indent_first_line
        number_position = _to_float(indent_dict.get("number_position_pt"))
        if number_position is None:
            number_position = indent_left - indent_hanging

        indent_dict.update(
            {
                "left_pt": indent_left,
                "right_pt": indent_right,
                "hanging_pt": indent_hanging,
                "first_line_pt": indent_first_line,
                "text_position_pt": text_position,
                "number_position_pt": number_position,
            }
        )
        element["indent"] = indent_dict
        style["indent"] = indent_dict

        text_area_width = max(available_width - indent_left - indent_right, 0.0)
        # first_line_offset can be negative for hanging indent (first line extends left)
        first_line_offset = text_position - indent_left
        text_width_first = max(text_area_width - first_line_offset, 0.0)
        text_width_other = text_area_width

        measure_cache: dict[tuple[str, int], float] = {}

        def _measure_width(text_value: str, style_override: Optional[Dict[str, Any]] = None) -> float:
            if not text_value:
                return 0.0
            key = (text_value, id(style_override) if style_override is not None else 0)
            if key in measure_cache:
                return measure_cache[key]
            measure_style = dict(style)
            if style_override:
                measure_style.update(style_override)
            try:
                metrics = self.text_metrics.measure_text(text_value, measure_style)
                width = float(metrics.get("width", 0.0))
            except Exception:
                width = 0.0
            if width <= 0.0:
                width = max(len(text_value), 1) * fallback_char_width
            measure_cache[key] = width
            return width

        tab_replacement = " " * 4

        paragraph_font_name = (
            style.get("font_name")
            or style.get("font_ascii")
            or style.get("font_hAnsi")
            or style.get("font_family")
        )
        paragraph_color = style.get("color") or style.get("font_color")
        # Bold from paragraph style can be in style["bold"] or style["run"]["bold"]
        # (depending on how parser passes styles)
        paragraph_bold = bool(
            style.get("bold")
            or (isinstance(style.get("run"), dict) and style.get("run", {}).get("bold"))
        )
        paragraph_italic = bool(
            style.get("italic")
            or (isinstance(style.get("run"), dict) and style.get("run", {}).get("italic"))
        )
        paragraph_underline = bool(
            style.get("underline")
            or (isinstance(style.get("run"), dict) and style.get("run", {}).get("underline"))
        )

        def _compose_run_style(run: Any) -> Dict[str, Any]:
            run_style: Dict[str, Any] = {}
            if isinstance(run, dict):
                raw_style = run.get("style", {}) or {}
            else:
                raw_style = getattr(run, "style", {}) or {}
            if isinstance(raw_style, dict):
                run_style.update(raw_style)

            font_name_run = (
                _run_attr(run, "font_name")
                or raw_style.get("font_name")
                or paragraph_font_name
            )
            if font_name_run:
                run_style["font_name"] = font_name_run

            font_size_run = normalize_font_size(
                _run_attr(run, "font_size") or raw_style.get("font_size")
            )
            if font_size_run:
                run_style["font_size"] = font_size_run
            else:
                run_style["font_size"] = font_size

            color_run = _run_attr(run, "color") or raw_style.get("color") or paragraph_color
            if color_run:
                run_style["color"] = color_run

            highlight_run = _run_attr(run, "highlight") or raw_style.get("highlight")
            if highlight_run:
                run_style["highlight"] = highlight_run

            # Logika bold zgodna z Wordem:
            # - If paragraph style has bold, then everything is bold by default
            # - BUT if run has explicit bold=False (inline override), bold is disabled
            # - If run has explicit bold=True (inline override), bold is enabled
            run_bold_override = _run_attr(run, "bold", None)  # None if no override
            if run_bold_override is None:
                run_bold_override = raw_style.get("bold")  # Check in raw_style
            if run_bold_override is not None:
                # Run has explicit bold set (True or False) - use it
                run_style["bold"] = bool(run_bold_override)
            else:
                # Run has no override - use bold from paragraph style
                run_style["bold"] = bool(paragraph_bold)
            if paragraph_italic or _run_attr(run, "italic", False) or raw_style.get("italic"):
                run_style["italic"] = True
            if paragraph_underline or _run_attr(run, "underline", False) or raw_style.get("underline"):
                run_style["underline"] = True
            if _run_attr(run, "superscript", False) or raw_style.get("superscript"):
                run_style["superscript"] = True
            if _run_attr(run, "subscript", False) or raw_style.get("subscript"):
                run_style["subscript"] = True
            if (
                _run_attr(run, "strike_through", False)
                or raw_style.get("strike_through")
                or raw_style.get("strikethrough")
            ):
                run_style["strike_through"] = True

            hyperlink_payload = run_style.get("hyperlink")
            if isinstance(hyperlink_payload, dict):
                hyperlink_info = dict(hyperlink_payload)
                url_candidate = hyperlink_info.get("url") or hyperlink_info.get("href")
                if not url_candidate:
                    rel_target = hyperlink_info.get("relationship_target") or hyperlink_info.get("target")
                    if isinstance(rel_target, str) and rel_target:
                        rel_target_str = rel_target.strip()
                        rel_lower = rel_target_str.lower()
                        if rel_lower.startswith(
                            ("http://", "https://", "mailto:", "ftp://", "ftps://", "news:", "tel:", "sms:", "file://")
                        ) or str(hyperlink_info.get("target_mode", "")).lower() == "external":
                            url_candidate = rel_target_str
                if url_candidate:
                    hyperlink_info.setdefault("url", url_candidate)
                run_style["hyperlink"] = hyperlink_info
                run_style.setdefault("underline", True)
                if not run_style.get("color"):
                    run_style["color"] = "#1155cc"

            return run_style

        def _run_attr(run: Any, attr: str, default: Any = None) -> Any:
            if isinstance(run, dict):
                return run.get(attr, default)
            return getattr(run, attr, default)

        runs = element.get("runs_payload") or element.get("runs") or []
        segments: List[Dict[str, Any]] = []
        if runs:
            for run in runs:
                run_text = _run_attr(run, "text", "") or ""
                break_type = (_run_attr(run, "break_type", None) or "").lower()
                if _run_attr(run, "has_tab", False) and "\t" not in run_text:
                    run_text += "\t"
                if _run_attr(run, "has_break", False) and break_type in ("", "textwrapping", "line"):
                    if not run_text.endswith("\n"):
                        run_text += "\n"
                
                # Check if run has footnote/endnote references
                footnote_refs = _run_attr(run, "footnote_refs", [])
                endnote_refs = _run_attr(run, "endnote_refs", [])
                has_footnote_refs = bool(footnote_refs)
                has_endnote_refs = bool(endnote_refs)
                
                # Check if run has field codes
                run_fields = _run_attr(run, "fields", [])
                
                # Add run to segments even if no text, but has footnote/endnote references or field codes
                if not run_text and not _run_attr(run, "has_drawing", False) and not has_footnote_refs and not has_endnote_refs and not run_fields:
                    continue
                run_style = _compose_run_style(run)
                segments.append({"text": run_text, "style": run_style, "run": run, "footnote_refs": footnote_refs, "endnote_refs": endnote_refs, "fields": run_fields})
        else:
            if text:
                segments.append({"text": text, "style": {"font_size": font_size}, "run": None})
            else:
                segments.append({"text": "", "style": {"font_size": font_size}, "run": None})

        tokens: List[Dict[str, Any]] = []
        for segment in segments:
            segment_text = segment.get("text") or ""
            run_style = segment.get("style") or {}
            run_ref = segment.get("run")
            footnote_refs = segment.get("footnote_refs", [])
            endnote_refs = segment.get("endnote_refs", [])
            segment_fields = segment.get("fields", [])  # Pobierz field codes z segmentu
            
            # If segment has field codes, add them as tokens BEFORE text
            for field in segment_fields:
                placeholder = format_field_placeholder(field)
                field_style = field.get("style") or {}
                # Use style from field (which contains formatting from run), but combine with run_style for other properties
                combined_style = dict(run_style)
                combined_style.update(field_style)  # field_style ma priorytet (zawiera formatowanie z runu)
                tokens.append({
                    "text": "",
                    "display": placeholder,
                    "style": combined_style,  # Use combined style with formatting from field
                    "run": run_ref,
                    "run_id": getattr(run_ref, "id", None) if run_ref else None,
                    "field": field,  # Dodaj field do tokenu
                    "kind": "field",  # Oznacz jako field token
                })
            
            idx = 0
            length = len(segment_text)
            
            # If segment has no text but has footnote/endnote references, create empty token
            if length == 0:
                if footnote_refs or endnote_refs:
                    # Create empty token with footnote_refs/endnote_refs
                    tokens.append({
                        "text": "",
                        "display": "",
                        "style": dict(run_style),
                        "run": run_ref,
                        "run_id": getattr(run_ref, "id", None) if run_ref else None,
                        "footnote_refs": footnote_refs,
                        "endnote_refs": endnote_refs,
                    })
                continue
            while idx < length:
                char = segment_text[idx]
                if char == "\n":
                    tokens.append(
                        {
                            "text": "\n",
                            "display": "\n",
                            "style": dict(run_style),
                            "run": run_ref,
                            "run_id": getattr(run_ref, "id", None),
                        }
                    )
                    idx += 1
                    continue
                if char.isspace():
                    end = idx
                    while end < length and segment_text[end].isspace() and segment_text[end] != "\n":
                        end += 1
                    raw_token = segment_text[idx:end]
                    display_token = raw_token.replace("\t", tab_replacement)
                    tokens.append(
                        {
                            "text": raw_token,
                            "display": display_token,
                            "style": dict(run_style),
                            "run": run_ref,
                            "run_id": getattr(run_ref, "id", None),
                        }
                    )
                    idx = end
                    continue
                end = idx
                while end < length and not segment_text[end].isspace():
                    end += 1
                raw_token = segment_text[idx:end]
                tokens.append(
                    {
                        "text": raw_token,
                        "display": raw_token,
                        "style": dict(run_style),
                        "run": run_ref,
                        "run_id": getattr(run_ref, "id", None),
                    }
                )
                idx = end

        lines_data: List[Dict[str, Any]] = []
        current_tokens: List[Dict[str, Any]] = []
        current_width = 0.0
        current_limit = text_width_first if text_width_first > 0.0 else text_area_width

        def _finalize_line(token_list: List[Dict[str, Any]], width_value: float, available: float) -> Dict[str, Any]:
            trimmed = list(token_list)
            trimmed_width = width_value
            while trimmed and not trimmed[-1]["display"].strip():
                trimmed_width -= trimmed[-1]["width"]
                trimmed.pop()
            return {
                "tokens": trimmed,
                "available": available,
                "width": max(trimmed_width, 0.0),
            }

        for token in tokens:
            if token["text"] == "\n":
                lines_data.append(_finalize_line(current_tokens, current_width, current_limit))
                current_tokens = []
                current_width = 0.0
                current_limit = text_width_other
                continue

            # Check if token is field code
            if token.get("kind") == "field":
                # Field code - use minimal width (e.g. "1" for PAGE, "10" for NUMPAGES)
                # to avoid too large gaps. Actual width will be adjusted during rendering
                field = token.get("field", {})
                placeholder = token.get("display", "")
                field_style = field.get("style") or {}
                field_type = field.get("field_type", "").upper()
                
                # Use minimal width for field codes - actual value will be rendered in PDF
                # For PAGE use "1" (minimal width for one digit)
                # For NUMPAGES use "10" (typical value for most documents)
                if field_type == "PAGE":
                    # Use minimal width for one digit
                    estimated_value = "1"
                elif field_type == "NUMPAGES":
                    # Use typical value for most documents (2 digits)
                    estimated_value = "10"
                else:
                    # For other types use placeholder
                    estimated_value = placeholder
                
                width = _measure_width(estimated_value, field_style)
                token["width"] = width
                token["space_count"] = 0
                token["baseline_shift"] = 0.0
                # Ensure font_size is float
                field_font_size = normalize_font_size(field_style.get("font_size")) or font_size
                token["font_size"] = field_font_size
                current_tokens.append(token)
                current_width += width
                continue

            display_text = token["display"]
            if display_text is None:
                continue
            
            # Check if token has footnote/endnote references
            token_footnote_refs = token.get("footnote_refs", [])
            token_endnote_refs = token.get("endnote_refs", [])
            has_footnote_refs = bool(token_footnote_refs)
            has_endnote_refs = bool(token_endnote_refs)
            
            style_override = token.get("style") or {}
            font_size_token = normalize_font_size(style_override.get("font_size")) or font_size
            
            # For superscript/subscript use reduced font_size to calculate width
            # (as it will be rendered in PDF)
            is_superscript = style_override.get("superscript", False)
            is_subscript = style_override.get("subscript", False)
            
            if is_superscript or is_subscript:
                # Use reduced font_size to measure width (as in PDF)
                measurement_style = dict(style_override)
                measurement_style["font_size"] = font_size_token * 0.58  # Tak samo jak w PDF
                width = _measure_width(display_text, measurement_style)
            else:
                width = _measure_width(display_text, style_override)
            
            if width <= 0.0 and display_text:
                # Fallback: use reduced font_size for superscript/subscript
                if is_superscript or is_subscript:
                    fallback_char_width_scaled = fallback_char_width * 0.58
                else:
                    fallback_char_width_scaled = fallback_char_width
                width = max(len(display_text), 1) * fallback_char_width_scaled
            
            # If token has footnote_refs/endnote_refs, calculate index width
            if has_footnote_refs or has_endnote_refs:
                # Pobierz numery footnote/endnote
                ref_numbers = []
                if has_footnote_refs and self.footnote_renderer:
                    for ref_id in token_footnote_refs:
                        try:
                            num = self.footnote_renderer.get_footnote_number(str(ref_id))
                            if num is not None:
                                ref_numbers.append(str(num))
                        except Exception:
                            ref_numbers.append(str(ref_id))
                if has_endnote_refs and self.footnote_renderer:
                    for ref_id in token_endnote_refs:
                        try:
                            num = self.footnote_renderer.get_endnote_number(str(ref_id))
                            if num is not None:
                                ref_numbers.append(str(num))
                        except Exception:
                            ref_numbers.append(str(ref_id))
                
                if ref_numbers:
                    # Create index text (no spaces between numbers)
                    ref_text = "".join(ref_numbers)
                    # Indices are rendered as superscript (font_size * 0.58)
                    ref_font_size = font_size_token * 0.58
                    # Calculate index width
                    ref_style = dict(style_override)
                    ref_style["font_size"] = ref_font_size
                    ref_width = _measure_width(ref_text, ref_style)
                    if ref_width <= 0.0:
                        # Fallback: estimate width
                        ref_width = ref_font_size * len(ref_text) * 0.6
                    # Add spacing (1pt) between text and index
                    ref_spacing = 1.0
                    # If token has text, add index width to token width
                    # If token has no text, width is only index width + spacing
                    if width > 0.0:
                        width = width + ref_width + ref_spacing
                    else:
                        width = ref_width + ref_spacing
            
            token["width"] = width
            token["space_count"] = display_text.count(" ") if display_text else 0
            
            # Oblicz baseline_shift dla superscript/subscript
            if is_superscript:
                # Baseline shift tak samo jak w footnotes: 0.33 * font_size (gdzie font_size to oryginalny rozmiar)
                token["baseline_shift"] = font_size_token * 0.33
            elif is_subscript:
                # For subscript shift down
                token["baseline_shift"] = -font_size_token * 0.25
            else:
                token["baseline_shift"] = 0.0
            
            # Zachowaj oryginalny font_size (nie zmniejszaj go tutaj - PDF compiler to zrobi)
            token["font_size"] = font_size_token

            # Don't skip token if it has footnote/endnote references, even if no text
            if not current_tokens and not display_text.strip() and not has_footnote_refs and not has_endnote_refs:
                continue

            candidate_width = current_width + width
            if candidate_width > current_limit and current_tokens:
                lines_data.append(_finalize_line(current_tokens, current_width, current_limit))
                current_tokens = []
                current_width = 0.0
                current_limit = text_width_other
                if not display_text.strip():
                    continue

            current_tokens.append(token)
            current_width += width

        if current_tokens or not lines_data:
            lines_data.append(_finalize_line(current_tokens, current_width, current_limit))

        ascent, descent = inline_metrics(font_size, line_spacing)
        lines: list[ParagraphLine] = []
        overlays: list[OverlayBox] = []
        line_offsets: List[float] = []
        line_widths: List[float] = []

        marker_data = element.get("marker") if isinstance(element, dict) else None
        has_visible_marker = isinstance(marker_data, dict) and not marker_data.get("hidden_marker")

        # If paragraph does NOT have visible marker (i.e. is not a real list),
        # and Word set left == hanging (pseudo-list), text should return
        # to left margin. Numbered lists have marker and should preserve
        # text_position = indent_left, so we don't touch them.
        if (
            not has_visible_marker
            and indent_hanging
            and abs(text_position - indent_left) < 1e-4
        ):
            text_position = max(indent_left - indent_hanging, 0.0)
            indent_dict["text_position_pt"] = text_position
            style["indent"] = indent_dict
            element["indent"] = indent_dict

        for idx, line_info in enumerate(lines_data):
            if has_visible_marker:
                line_indent = text_position
            else:
                line_indent = text_position if idx == 0 else indent_left
            line_available = line_info.get("available", text_width_other if idx else text_width_first)
            line_offsets.append(line_indent)
            line_widths.append(line_available)
            items: list[InlineBox] = []
            cursor_x = 0.0
            max_ascent = 0.0
            max_descent = 0.0

            for token in line_info.get("tokens", []):
                # Check if token is field code
                if token.get("kind") == "field":
                    # This is field code - use special rendering
                    field = token.get("field", {})
                    placeholder = token.get("display", "")
                    field_style = field.get("style") or {}
                    style_override = dict(style)
                    style_override.update(field_style)
                    font_size_token = normalize_font_size(token.get("font_size")) or normalize_font_size(field_style.get("font_size")) or font_size
                    style_override["font_size"] = font_size_token
                    token_ascent = max(font_size_token * 0.8, 0.1)
                    token_descent = max(font_size_token * 0.2, 0.05)
                    
                    width = token.get("width", 0.0)
                    
                    inline = InlineBox(
                        kind="field",
                        x=cursor_x,
                        width=width,
                        ascent=token_ascent,
                        descent=token_descent,
                        data={
                            "field": field,
                            "display": placeholder,
                            "style": field_style,
                            "bold": field_style.get("bold"),
                            "italic": field_style.get("italic"),
                            "underline": field_style.get("underline"),
                        },
                    )
                    items.append(inline)
                    cursor_x += width
                    max_ascent = max(max_ascent, inline.ascent)
                    max_descent = max(max_descent, inline.descent)
                else:
                    # This is regular text token
                    style_override = dict(style)
                    style_override.update(token.get("style") or {})
                    font_size_token = normalize_font_size(token.get("font_size")) or font_size
                    style_override["font_size"] = font_size_token
                    baseline_shift = token.get("baseline_shift", 0.0)
                    token_ascent = max(font_size_token * 0.8, 0.1)
                    token_descent = max(font_size_token * 0.2, 0.05)
                    
                    # Pobierz footnote/endnote references z tokenu
                    token_footnote_refs = token.get("footnote_refs", [])
                    token_endnote_refs = token.get("endnote_refs", [])
                    
                    inline = InlineBox(
                        kind="text_run",
                        x=cursor_x,
                        width=token.get("width", 0.0),
                        ascent=token_ascent + max(0.0, baseline_shift),
                        descent=token_descent - min(0.0, baseline_shift),
                        data={
                            "text": token.get("display", ""),
                            "raw_text": token.get("text", ""),
                            "style": style_override,
                            "space_count": token.get("space_count", 0),
                            "baseline_shift": baseline_shift,
                            "strike_through": style_override.get("strike_through"),
                            "highlight": style_override.get("highlight"),
                            "underline": style_override.get("underline"),
                            "bold": style_override.get("bold"),
                            "italic": style_override.get("italic"),
                            "superscript": style_override.get("superscript"),
                            "subscript": style_override.get("subscript"),
                            "run_id": token.get("run_id"),
                            "footnote_refs": token_footnote_refs,
                            "endnote_refs": token_endnote_refs,
                        },
                    )
                    items.append(inline)
                    cursor_x += token.get("width", 0.0)
                    max_ascent = max(max_ascent, inline.ascent)
                    max_descent = max(max_descent, inline.descent)

            line_height = max(line_spacing, max_ascent + max_descent if items else line_spacing)
            lines.append(
                ParagraphLine(
                    baseline_y=0.0,
                    height=line_height,
                    items=items,
                    offset_x=line_indent - indent_left,
                    available_width=line_available,
                    block_height=line_height,
                )
            )

        if not lines:
            default_offset = text_position if text_position is not None else 0.0
            default_width = text_width_first if text_width_first > 0.0 else text_area_width
            lines.append(
                ParagraphLine(
                    baseline_y=0.0,
                    height=line_spacing,
                    items=[],
                    offset_x=default_offset - indent_left,
                    available_width=default_width,
                    block_height=line_spacing,
                )
            )
            line_offsets = [default_offset]
            line_widths = [default_width]

        def _append_inline(item: InlineBox) -> None:
            last_line = lines[-1]
            last_line.items.append(item)
            item_height = item.ascent + item.descent
            if item_height > last_line.height:
                last_line.height = item_height
                last_line.block_height = item_height

        # Field codes are already added as tokens in proper place, so no need to add them here
        # (they were already added during segment processing)

        # Obrazy inline lub absolutne
        for image in images:
            anchor_type, _ = extract_anchor_info(image)
            if anchor_type == "anchor":
                overlays.append(
                    create_overlay_box(
                        kind="image",
                        source=image,
                        block_rect=block_rect,
                        default_width=available_width * 0.3,
                        default_height=line_spacing * 1.5,
                        page_config=self.page_config,
                    )
                )
                continue

            width_pt = extract_dimension(image, "width", default=font_size)
            height_pt = extract_dimension(image, "height", default=line_spacing)
            inline = InlineBox(
                kind="inline_image",
                x=cursor_x,
                width=width_pt,
                ascent=max(height_pt * 0.8, ascent),
                descent=max(height_pt * 0.2, descent),
                data={"image": image, "width": width_pt, "height": height_pt},
            )
            _append_inline(inline)
            cursor_x += width_pt

        # Textboxy inline/anchor
        for textbox in textboxes:
            anchor_type, _ = extract_anchor_info(textbox)
            if anchor_type == "anchor":
                prepared = self._prepare_textbox_overlay(textbox, available_width)
                overlay_box = create_overlay_box(
                    kind="textbox",
                    source=textbox,
                    block_rect=block_rect,
                    default_width=prepared[0] if prepared else available_width * 0.25,
                    default_height=prepared[1] if prepared else line_spacing * 1.4,
                    page_config=self.page_config,
                )
                if prepared:
                    width_pt, height_pt, payload, overlay_style = prepared
                    overlay_box.payload["layout_payload"] = payload
                    overlay_box.payload.setdefault("style", overlay_style)
                    overlay_box.frame = Rect(
                        overlay_box.frame.x,
                        overlay_box.frame.y,
                        width_pt,
                        height_pt,
                    )
                overlays.append(overlay_box)
                continue

            inline_text = ""
            if isinstance(textbox, dict):
                inline_text = (textbox.get("text") or textbox.get("content") or "").strip()
            elif hasattr(textbox, "text"):
                inline_text = (getattr(textbox, "text", "") or "").strip()
            if not inline_text:
                inline_text = "[textbox]"

            width = _measure_width(inline_text) if inline_text else fallback_char_width * 4
            inline = InlineBox(
                kind="inline_textbox",
                x=cursor_x,
                width=width,
                ascent=ascent,
                descent=descent,
                data={"textbox": textbox, "text": inline_text},
            )
            _append_inline(inline)
            cursor_x += width

        # Recalculate baseline positions using final line heights
        current_baseline = 0.0
        for line in lines:
            line.height = max(line.height, line_spacing)
            line.baseline_y = current_baseline
            line.block_height = line.height
            current_baseline += line.height

        padding_top, padding_right, padding_bottom, padding_left = extract_padding(style)

        background_spec: Optional[ColorSpec] = None
        background_value = style.get("background") or style.get("background_color")
        rgb_tuple = self._hex_to_rgb_tuple(background_value)
        if rgb_tuple:
            background_spec = ColorSpec(*rgb_tuple)

        border_specs: List[BorderSpec] = []
        borders_dict = style.get("borders")
        if isinstance(borders_dict, dict):
            for side, spec in borders_dict.items():
                normalized_spec = self._normalize_border_dict(spec)
                if not normalized_spec:
                    continue
                rgb = self._hex_to_rgb_tuple(normalized_spec.get("color"))
                color_spec = ColorSpec(*(rgb if rgb else (0.0, 0.0, 0.0)))
                side_key = self._strip_namespace(side).lower()
                if side_key not in {"top", "bottom", "left", "right"}:
                    continue
                border_specs.append(
                    BorderSpec(
                        side=side_key,  # type: ignore[arg-type]
                        width=float(normalized_spec.get("width", 1.0) or 1.0),
                        color=color_spec,
                        style=str(normalized_spec.get("style", "solid")).lower(),
                    )
                )

        box_style = BoxStyle(
            background=background_spec,
            borders=border_specs,
            padding=(padding_top, padding_right, padding_bottom, padding_left),
        )

        def _element_attr(key: str, default: Any = None) -> Any:
            if isinstance(element, dict):
                return element.get(key, default)
            return getattr(element, key, default)

        metadata = {
            "source_id": _element_attr("id"),
            "source_type": _element_attr("type", "paragraph"),
            "raw_style": style,
        }
        frame_original = element.get("_frame_original")
        if isinstance(frame_original, dict):
            metadata["frame_original"] = frame_original
        line_offsets_relative = [
            offset - indent_left
            for offset in line_offsets
        ]
        indent_metrics = {
            "left": indent_left,
            "right": indent_right,
            "first_line": indent_first_line,
            "hanging": indent_hanging,
            "text_position": text_position,
            "number_position": number_position,
            "text_width_first": text_width_first,
            "text_width_other": text_width_other,
            "wrap_width": text_area_width,
            "line_offsets": line_offsets,
            "line_offsets_relative": line_offsets_relative,
            "line_widths": line_widths,
        }
        max_text_width = max(line_widths) if line_widths else text_width_first
        text_frame = {
            "x": first_line_offset,
            "width": max(0.0, text_area_width),
            "first_line_width": max(0.0, text_width_first),
            "right_indent": indent_right,
            "line_offsets_relative": line_offsets_relative,
        }
        layout_metrics = element.get("layout_metrics") or {}
        layout_metrics["text_frame"] = text_frame
        layout_metrics["indent_metrics"] = indent_metrics
        layout_metrics["block_rect_is_final"] = block_rect is not None
        inline_indent_src = style.get("inline_indent") or element.get("inline_indent")
        if isinstance(inline_indent_src, dict):
            inline_indent = {
                key: value for key, value in (
                    (name, _to_float(inline_indent_src.get(name))) for name in ("left_pt", "right_pt", "first_line_pt", "hanging_pt")
                ) if value is not None
            }
        else:
            inline_indent = {}
        layout_metrics["inline_indent"] = inline_indent
        element["layout_metrics"] = layout_metrics
        metadata["indent_metrics"] = indent_metrics
        metadata["text_frame"] = text_frame
        metadata["block_rect_is_final"] = block_rect is not None
        metadata["inline_indent"] = inline_indent
        metadata["layout_tree"] = self._ensure_layout_tree(element)
        block_width = block_rect.width if block_rect is not None else available_width
        metadata["block_rect_width"] = block_width

        return ParagraphLayout(
            lines=lines,
            overlays=overlays,
            style=box_style,
            metadata=metadata,
        )

    def _measure_table_height(self, element: dict) -> float:
        """

        Calculates table height using TableLayoutEngine.

        Args:
        element: Table element

        Returns:
        Height in points

        """
        return self._layout_table(element)
    
    def _layout_table(self, element: dict) -> float:
        """

        Precise table layout with multiple columns, padding and row heights.

        Args:
        element: Table element with rows

        Returns:
        Total table height in points

        Side effects:
        Saves calculated row_heights in element['layout_info']['row_heights']

        """
        self._ensure_layout_tree(element)

        if isinstance(element, dict):
            rows = element.get("rows", []) or []
        else:
            rows = getattr(element, "rows", []) or []
        if not rows:
            return 20.0
        
        style = element.get("style", {}) or {}
        if not isinstance(style, dict):
            style = {}

        table_alignment = self._normalize_table_alignment(
            style.get("table_alignment") or style.get("alignment") or style.get("jc")
        )
        if table_alignment:
            style["table_alignment"] = table_alignment
        table_vertical_alignment = self._normalize_table_vertical_alignment(
            style.get("table_vertical_alignment")
            or style.get("vertical_alignment")
            or style.get("valign")
        )
        if table_vertical_alignment:
            style["table_vertical_alignment"] = table_vertical_alignment

        element["style"] = style

        spacing_before_tbl, spacing_after_tbl = parse_table_spacing(element)
        existing_before = style.get("spacing_before")
        existing_after = style.get("spacing_after")
        spacing_before_tbl = self._to_float(existing_before, spacing_before_tbl or 0.0)
        spacing_after_tbl = self._to_float(existing_after, spacing_after_tbl or 0.0)
        style["spacing_before"] = spacing_before_tbl
        style["spacing_after"] = spacing_after_tbl

        margins = self.page_config.base_margins
        content_width = max(
            self.page_config.page_size.width - margins.left - margins.right,
            0.0,
        )

        table_indent = max(self._resolve_table_indent(style), 0.0)
        usable_width = max(content_width - table_indent, 0.0)

        min_row_height = float(style.get("row_height") or 0.0)
        spacing_between_rows = float(style.get("spacing_between_rows", 0.0))

        spacing_info = style.get("cell_spacing")
        if isinstance(spacing_info, dict):
            spacing_pts = self._convert_table_spacing(spacing_info)
            if spacing_pts is not None:
                spacing_between_rows = max(spacing_between_rows, spacing_pts)

        grid = element.get("grid") if isinstance(element, dict) else getattr(element, "grid", None)
        num_cols = self._infer_table_columns(rows)
        col_widths = self._extract_grid_column_widths(grid, num_cols)

        grid_total = sum(col_widths) if col_widths else 0.0
        requested_width = self._resolve_table_width(style, usable_width)

        if requested_width is None or requested_width <= 0.0:
            fallback_request = grid_total if grid_total > 0 else usable_width
            if not fallback_request or fallback_request <= 0.0:
                fallback_request = content_width
            requested_width = fallback_request

        final_table_width = min(requested_width, usable_width if usable_width > 0 else requested_width)
        if final_table_width <= 0.0:
            final_table_width = requested_width if requested_width > 0 else usable_width or content_width

        if not col_widths:
            target_cols = max(num_cols, 1)
            fallback_width = final_table_width / target_cols if final_table_width > 0 else (
                usable_width / target_cols if usable_width > 0 else content_width / target_cols
            )
            col_widths = [fallback_width] * target_cols
        else:
            total = sum(col_widths)
            target_cols = len(col_widths)
            if total > 0 and final_table_width > 0:
                scale = final_table_width / total
                col_widths = [w * scale for w in col_widths]
            else:
                fallback_width = final_table_width / target_cols if final_table_width > 0 else (
                    usable_width / target_cols if usable_width > 0 else content_width / target_cols
                )
                col_widths = [fallback_width] * target_cols

        table_default_margins = self._convert_table_cell_margins(
            style.get("cell_margins"), final_table_width
        )
        default_margin_values = [
            float(v)
            for v in table_default_margins.values()
            if isinstance(v, (int, float))
        ]
        if default_margin_values:
            cell_padding = sum(default_margin_values) / len(default_margin_values)
        else:
            raw_padding = style.get("cell_padding")
            if isinstance(raw_padding, dict):
                numeric_values = [
                    float(v)
                    for v in raw_padding.values()
                    if isinstance(v, (int, float)) and float(v) > 0.0
                ]
                cell_padding = min(numeric_values) if numeric_values else 0.0
            else:
                cell_padding = float(style.get("cell_padding", 0.0))
        
        # Calculate height of each row
        # row_height = max(min_row_height, max(cell.height for cell in row))
        # Row height is dynamic: max(min_row_height_from_DOCX, content_height)
        row_heights = []
        vmerge_state: Dict[int, Dict[str, Any]] = {}

        def _ensure_cell_style(cell_obj: Any) -> Dict[str, Any]:
            if isinstance(cell_obj, dict):
                style_dict = cell_obj.get("style")
                if not isinstance(style_dict, dict):
                    style_dict = {}
                    cell_obj["style"] = style_dict
                return style_dict
            style_attr = getattr(cell_obj, "style", None)
            if isinstance(style_attr, dict):
                return style_attr
            if hasattr(cell_obj, "style"):
                setattr(cell_obj, "style", {})
                return getattr(cell_obj, "style")
            return {}

        def _extract_vertical_align(value: Any) -> Optional[str]:
            if isinstance(value, dict):
                candidate = value.get("val") or value.get("value")
                if candidate:
                    value = candidate
            if value in (None, "", {}, False):
                return None
            token = str(value).strip().lower()
            if not token:
                return None
            mapping = {
                "middle": "center",
                "centre": "center",
                "baseline": "top",
                "start": "top",
                "end": "bottom",
            }
            normalized = mapping.get(token, token)
            if normalized in {"top", "center", "bottom", "justify"}:
                return normalized
            return None

        def _get_cell_vertical_align(cell_obj: Any) -> Optional[str]:
            if hasattr(cell_obj, "vertical_align"):
                aligned = _extract_vertical_align(getattr(cell_obj, "vertical_align"))
                if aligned:
                    return aligned
            if isinstance(cell_obj, dict):
                style_dict = cell_obj.get("style") if isinstance(cell_obj.get("style"), dict) else {}
                raw = (
                    cell_obj.get("vertical_align")
                    or cell_obj.get("vAlign")
                    or cell_obj.get("valign")
                    or style_dict.get("vertical_align")
                    or style_dict.get("vAlign")
                    or style_dict.get("valign")
                )
                aligned = _extract_vertical_align(raw)
                if aligned:
                    return aligned
            else:
                style_attr = getattr(cell_obj, "style", None)
                if isinstance(style_attr, dict):
                    raw = (
                        style_attr.get("vertical_align")
                        or style_attr.get("vAlign")
                        or style_attr.get("valign")
                    )
                    aligned = _extract_vertical_align(raw)
                    if aligned:
                        return aligned
            return None

        def _apply_vertical_align(cell_obj: Any, align_value: str) -> None:
            if not align_value:
                return
            style_dict = _ensure_cell_style(cell_obj)
            style_dict["vertical_align"] = align_value
            style_dict["vAlign"] = align_value
            if hasattr(cell_obj, "vertical_align"):
                setattr(cell_obj, "vertical_align", align_value)
        
        for row_idx, row in enumerate(rows):
            row_height_info = self._extract_row_height_info(row)
            row_rule = row_height_info.get("rule")
            row_height_points = row_height_info.get("value")
            if row_height_points is not None and row_height_points < 0:
                row_height_points = None

            # Get cells from row
            if isinstance(row, list):
                cells = row
            elif isinstance(row, dict) and "cells" in row:
                cells = row["cells"]
            elif hasattr(row, "cells"):
                cells = row.cells
            else:
                cells = []
            
            # Calculate height of each cell
            # Use column width for this cell (or default width)
            # Account for grid_span (colspan) - cell may span multiple columns
            cell_heights: List[float] = []
            col_idx = 0
            cell_idx = 0
            row_has_content_cell = False
            while cell_idx < len(cells):
                cell = cells[cell_idx]
                
                # Pobierz grid_span (colspan)
                grid_span = 1
                if hasattr(cell, 'grid_span'):
                    grid_span = cell.grid_span or 1
                elif isinstance(cell, dict):
                    grid_span = cell.get("grid_span") or cell.get("gridSpan") or 1
                    if isinstance(grid_span, str):
                        try:
                            grid_span = int(grid_span)
                        except (ValueError, TypeError):
                            grid_span = 1
                
                # Get cell margins
                cell_margins = parse_cell_margins(
                    cell,
                    default_margin=cell_padding,
                    table_defaults=table_default_margins,
                )
                
                # Calculate cell width (sum of column widths it spans)
                if col_idx + grid_span <= len(col_widths):
                    cell_col_width = sum(col_widths[col_idx:col_idx + grid_span])
                else:
                    # Fallback: use single column width
                    cell_col_width = col_widths[col_idx] if col_idx < len(col_widths) else col_widths[0] if col_widths else 100.0
                
                # Available width = cell width - left and right margins
                available_width = cell_col_width - cell_margins["left"] - cell_margins["right"]
                
                vmerge_val = None
                if hasattr(cell, "v_merge"):
                    vmerge_val = getattr(cell, "v_merge")
                elif isinstance(cell, dict):
                    raw_vmerge = (
                        cell.get("v_merge")
                        or cell.get("vMerge")
                        or cell.get("vmerge")
                    )
                    if isinstance(raw_vmerge, dict):
                        vmerge_val = raw_vmerge.get("val") or raw_vmerge.get("value")
                    else:
                        vmerge_val = raw_vmerge
                vmerge_val_norm = str(vmerge_val).lower() if isinstance(vmerge_val, str) else None

                cell_height = self._measure_cell_height(
                    cell,
                    style,
                    available_width,
                    table_default_margins=table_default_margins,
                )
                if vmerge_val_norm == "continue":
                    state = vmerge_state.get(col_idx)
                    if state is not None:
                        state["rows"].append(row_idx)
                        if cell_height is not None:
                            state["height"] = max(state["height"], cell_height)
                        align_value = _get_cell_vertical_align(cell)
                        if align_value and not state.get("vertical_align"):
                            state["vertical_align"] = align_value
                            _apply_vertical_align(state["cell"], align_value)
                    col_idx += grid_span
                    cell_idx += 1
                    continue
                else:
                    if vmerge_val_norm in ("restart", "start", "true"):
                        align_value = _get_cell_vertical_align(cell)
                        vmerge_state[col_idx] = {
                            "row": row_idx,
                            "rows": [row_idx],
                            "height": cell_height or 0.0,
                            "cell": cell,
                            "vertical_align": align_value,
                        }
                        if align_value:
                            _apply_vertical_align(cell, align_value)
                    elif vmerge_val is None:
                        state = vmerge_state.get(col_idx)
                        if state is not None and state.get("row") != row_idx:
                            vmerge_state.pop(col_idx, None)

                if cell_height is not None:
                    cell_heights.append(cell_height)
                    row_has_content_cell = True
                
                col_idx += grid_span
                cell_idx += 1

            while col_idx < num_cols:
                fallback_height = max(min_row_height, 10.0) if min_row_height > 0 else 10.0
                cell_heights.append(fallback_height)
                col_idx += 1
            
            content_height = max(cell_heights) if cell_heights else 0.0
            if not row_has_content_cell and content_height <= 0.0:
                content_height = max(min_row_height, 10.0) if min_row_height > 0 else 10.0

            if row_height_points is not None:
                if row_rule == "exact":
                    row_height = row_height_points
                elif row_rule == "atleast":
                    row_height = max(row_height_points, content_height)
                else:
                    row_height = max(content_height, row_height_points)
            else:
                row_height = content_height

            if min_row_height > 0:
                row_height = max(row_height, min_row_height)

            row_height = max(row_height, 0.0)

            row_heights.append(row_height)
        
        # Save row_heights and col_widths in element structure for later use in PDFCompiler
        layout_info = element.setdefault("layout_info", {})
        layout_info["row_heights"] = row_heights
        layout_info["col_widths"] = col_widths
        layout_info["table_width"] = final_table_width
        layout_info["table_indent"] = table_indent
        if table_alignment:
            layout_info["table_alignment"] = table_alignment
        if table_vertical_alignment:
            layout_info["table_vertical_alignment"] = table_vertical_alignment
 
        # Sum row heights + spacing
        total_height = sum(row_heights)
        if len(row_heights) > 1:
            total_height += spacing_between_rows * (len(row_heights) - 1)
            if spacing_between_rows <= 0.0:
                spacing_vertical_raw = style.get("cell_spacing_vertical")
                if spacing_vertical_raw not in (None, "", {}):
                    try:
                        spacing_vertical = float(spacing_vertical_raw)
                    except (TypeError, ValueError):
                        spacing_vertical = 0.0
                    if spacing_vertical > 0.0:
                        total_height += spacing_vertical * (len(row_heights) - 1)
        
        # Add table margins if present
        table_margin_top = float(style.get("margin_top", 0.0))
        table_margin_bottom = float(style.get("margin_bottom", 0.0))
        total_height += table_margin_top + table_margin_bottom

        layout_info["spacing_before"] = spacing_before_tbl
        layout_info["spacing_after"] = spacing_after_tbl
        
        if row_heights:
            return max(total_height, 0.0)
        return 20.0
    
    @staticmethod
    def _infer_table_columns(rows: List[Any]) -> int:
        max_cols = 0
        for row in rows:
            if isinstance(row, (list, tuple)):
                count = len(row)
            elif isinstance(row, dict):
                cells = row.get("cells")
                count = len(cells) if isinstance(cells, list) else len(row)
            elif hasattr(row, "cells"):
                count = len(getattr(row, "cells", []) or [])
            else:
                count = 0
            max_cols = max(max_cols, count)
        return max_cols if max_cols > 0 else 1

    def _extract_grid_column_widths(self, grid: Any, num_cols: int) -> List[float]:
        widths: List[float] = []
        if not isinstance(grid, list):
            return widths
        for entry in grid:
            width_raw = None
            if isinstance(entry, dict):
                width_raw = entry.get("width") or entry.get("w") or entry.get("val")
            if width_raw in (None, "", {}):
                continue
            try:
                numeric = float(width_raw)
            except (TypeError, ValueError):
                continue
            widths.append(max(twips_to_points(numeric), 0.0))
        if widths and num_cols > 0 and len(widths) < num_cols:
            avg_width = sum(widths) / len(widths) if widths else 0.0
            widths.extend([avg_width] * (num_cols - len(widths)))
        if num_cols > 0:
            return widths[:num_cols]
        return widths

    def _resolve_table_width(
        self,
        style: Dict[str, Any],
        usable_width: float,
    ) -> Optional[float]:
        width_raw = style.get("width")
        width_type = style.get("width_type")
        if isinstance(width_raw, dict):
            width_type = width_raw.get("type") or width_type
            raw_value = (
                width_raw.get("w")
                or width_raw.get("value")
                or width_raw.get("val")
                or width_raw.get("width")
            )
        else:
            raw_value = width_raw

        type_hint = str(width_type or "").lower()

        if raw_value in (None, "", {}):
            return None

        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            return None

        if type_hint == "pct":
            percentage = numeric / 5000.0 if numeric > 1 else numeric
            if percentage > 10:
                percentage = percentage / 100.0
            percentage = max(min(percentage, 1.0), 0.0)
            return max(usable_width * percentage, 0.0)

        if type_hint in ("", "dxa", "twip", "twips"):
            return max(twips_to_points(numeric), 0.0)

        if type_hint in ("auto", "nil"):
            return None

        # Treat remaining units as points
        return max(numeric, 0.0)

    @staticmethod
    def _resolve_table_indent(style: Dict[str, Any]) -> float:
        indent_data = None
        for key in ("indentation", "indent"):
            candidate = style.get(key)
            if isinstance(candidate, dict):
                indent_data = candidate
                break
        if not isinstance(indent_data, dict):
            return 0.0
        raw_value = None
        for attr in ("w", "value", "val", "left"):
            if indent_data.get(attr) not in (None, ""):
                raw_value = indent_data[attr]
                break
        if raw_value in (None, ""):
            return 0.0
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            return 0.0
        type_hint = str(indent_data.get("type") or indent_data.get("unit") or "").lower()
        if type_hint == "pct":
            return 0.0
        if type_hint in ("", "dxa", "twip", "twips"):
            return max(twips_to_points(numeric), 0.0)
        return max(numeric, 0.0)

    def _convert_table_cell_margins(
        self,
        margins_src: Any,
        reference_width: float,
    ) -> Dict[str, float]:
        if not isinstance(margins_src, dict):
            return {}

        mapping = {"start": "left", "end": "right"}
        result: Dict[str, float] = {}

        for key, margin_data in margins_src.items():
            if not isinstance(margin_data, dict):
                continue
            raw_value = (
                margin_data.get("w")
                or margin_data.get("width")
                or margin_data.get("value")
                or margin_data.get("val")
            )
            if raw_value in (None, ""):
                continue
            try:
                numeric = float(raw_value)
            except (TypeError, ValueError):
                continue
            type_hint = str(margin_data.get("type") or margin_data.get("unit") or "").lower()
            side = mapping.get(key.lower(), key.lower())
            if type_hint == "pct":
                if reference_width > 0:
                    result[side] = max(reference_width * (numeric / 5000.0), 0.0)
                continue
            if type_hint in ("", "dxa", "twip", "twips"):
                result[side] = max(twips_to_points(numeric), 0.0)
            else:
                result[side] = max(numeric, 0.0)
        return result

    @staticmethod
    def _convert_table_spacing(spacing_info: Dict[str, Any]) -> Optional[float]:
        raw_value = (
            spacing_info.get("w")
            or spacing_info.get("value")
            or spacing_info.get("val")
            or spacing_info.get("width")
        )
        if raw_value in (None, "", "0"):
            return 0.0
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            return None
        type_hint = str(spacing_info.get("type") or spacing_info.get("unit") or "").lower()
        if type_hint in ("", "dxa", "twip", "twips"):
            return max(twips_to_points(numeric), 0.0)
        if type_hint == "pct":
            return None
        return max(numeric, 0.0)

    @staticmethod
    def _extract_row_height_info(row: Any) -> Dict[str, Optional[float]]:
        height_dict: Optional[Dict[str, Any]] = None
        raw_value: Any = None
        rule: Optional[str] = None

        if isinstance(row, dict):
            style_dict = row.get("style")
            if isinstance(style_dict, dict):
                height_candidate = style_dict.get("height")
                if isinstance(height_candidate, dict):
                    height_dict = height_candidate
                elif height_candidate not in (None, "", {}):
                    raw_value = height_candidate
            if raw_value is None and row.get("height") not in (None, ""):
                raw_value = row.get("height")
        else:
            style_dict = getattr(row, "style", None)
            if isinstance(style_dict, dict):
                height_candidate = style_dict.get("height")
                if isinstance(height_candidate, dict):
                    height_dict = height_candidate
                elif height_candidate not in (None, "", {}):
                    raw_value = height_candidate
            if raw_value is None and getattr(row, "height", None) is not None:
                raw_value = getattr(row, "height")

        if height_dict:
            raw_value = (
                height_dict.get("val")
                or height_dict.get("w")
                or height_dict.get("value")
                or raw_value
            )
            rule = height_dict.get("hRule") or height_dict.get("rule")

        value_pt: Optional[float] = None
        if raw_value not in (None, "", {}):
            try:
                numeric = float(raw_value)
            except (TypeError, ValueError):
                numeric = None
            if numeric is not None:
                value_pt = twips_to_points(numeric)

        return {"value": value_pt, "rule": str(rule).lower() if rule else None}

    def _measure_cell_height(
        self,
        cell: Any,
        table_style: dict,
        available_width: float,
        table_default_margins: Optional[Dict[str, float]] = None,
    ) -> Optional[float]:
        if hasattr(cell, "height") and cell.height is not None:
            return float(cell.height)
        if isinstance(cell, dict) and cell.get("height") is not None:
            try:
                return float(cell["height"])
            except (TypeError, ValueError):
                pass

        cell_style: Dict[str, Any] = {}
        if hasattr(cell, "style") and isinstance(getattr(cell, "style"), dict):
            cell_style = getattr(cell, "style")
        elif isinstance(cell, dict):
            cell_style = cell.get("style", {}) or {}

        cell_margins = parse_cell_margins(
            cell,
            table_defaults=table_default_margins,
        )
        available_width = max(available_width, 1.0)

        def _extract_cell_text(cell_obj: Any) -> str:
            if hasattr(cell_obj, "get_text"):
                return cell_obj.get_text() or ""
            if isinstance(cell_obj, dict):
                text_val = cell_obj.get("text")
                if text_val:
                    return str(text_val)
                if cell_obj.get("content"):
                    return str(cell_obj["content"])
            if hasattr(cell_obj, "text"):
                return str(getattr(cell_obj, "text") or "")
            return ""

        cell_text = _extract_cell_text(cell)

        tree = None
        try:
            tree = self._ensure_layout_tree(cell)
        except Exception:
            tree = None

        stacked_height = 0.0
        overlay_height = 0.0

        def _to_float(value: Any) -> float:
            if value in (None, ""):
                return 0.0
            if isinstance(value, (int, float)):
                return float(value)
            try:
                return float(str(value))
            except (TypeError, ValueError):
                return 0.0

        def _extract_spacing(edict: Dict[str, Any], source: Any, attr: str) -> float:
            style = edict.get("style") if isinstance(edict.get("style"), dict) else {}
            if isinstance(style, dict):
                val = style.get(attr)
                if val not in (None, ""):
                    return _to_float(val)
            val = edict.get(attr)
            if val not in (None, ""):
                return _to_float(val)
            if source is not None and hasattr(source, attr):
                return _to_float(getattr(source, attr))
            return 0.0

        def _measure_node(node: BaseNode) -> float:
            element = node.source
            element_dict = coerce_element_dict(element, node.kind)
            element_type = (element_dict.get("type") or node.kind or "").lower()
            if element_type == "paragraph":
                height = self._measure_paragraph_height(element_dict, available_width)
                payload = element_dict.get("layout_payload")
                if isinstance(payload, ParagraphLayout):
                    self._cache_paragraph_payload(element, payload)
                return height
            if element_type == "table":
                return self._layout_table(element_dict)
            if element_type == "image":
                return self._measure_image_height(element_dict, available_width)
            if element_type == "textbox":
                return self._measure_textbox_height(element_dict, available_width)
            text_val = element_dict.get("text") or element_dict.get("content")
            if text_val:
                return estimate_text_height(str(text_val), available_width, element_dict.get("style", {}) or {})
            if node.children:
                subtotal = 0.0
                for child in node.children:
                    subtotal = max(subtotal, _measure_node(child))
                return subtotal
            return 0.0

        def _collect_overlay_height(node: BaseNode, element_dict: Dict[str, Any]) -> float:
            element_type = (element_dict.get("type") or node.kind or "").lower()
            max_height = 0.0
            if element_type == "paragraph":
                payload = element_dict.get("layout_payload")
                if isinstance(payload, ParagraphLayout) and payload.overlays:
                    max_height = max(
                        (ov.frame.height for ov in payload.overlays if ov.frame is not None),
                        default=0.0,
                    )
            elif element_type == "image":
                max_height = max(max_height, extract_dimension(element_dict, "height", 0.0))
            for child in node.children:
                child_dict = coerce_element_dict(child.source, child.kind)
                max_height = max(max_height, _collect_overlay_height(child, child_dict))
            return max_height

        if tree and getattr(tree, "children", None):
            children = list(tree.children)
            apply_spacing = len(children) <= 1
            for child in children:
                element = child.source
                element_dict = coerce_element_dict(element, child.kind)
                # DOCX renderers ignore spacing_before/after inside table cells,
                # so we skip them when calculating height.
                spacing_before = 0.0
                spacing_after = 0.0
                block_height = _measure_node(child)
                if apply_spacing or stacked_height == 0.0:
                    stacked_height += spacing_before
                stacked_height += block_height
                if apply_spacing:
                    stacked_height += spacing_after
                overlay_height = max(overlay_height, _collect_overlay_height(child, element_dict))
        elif cell_text.strip():
            paragraph_stub = {
                "type": "paragraph",
                "text": cell_text,
                "style": cell_style,
            }
            stacked_height = self._measure_paragraph_height(paragraph_stub, available_width)

        content_height = max(stacked_height, overlay_height)
        if content_height <= 0:
            margin_height = cell_margins["top"] + cell_margins["bottom"]
            return margin_height if margin_height > 0 else None

        cell_space_before, cell_space_after = parse_cell_spacing(cell)
        content_height += cell_margins["top"] + cell_margins["bottom"] + cell_space_before + cell_space_after
        return content_height
