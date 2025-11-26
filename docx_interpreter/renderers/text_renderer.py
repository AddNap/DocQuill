"""Rendering routines for paragraph blocks."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from ..engine.unified_layout import LayoutBlock
from ..engine.geometry import Margins, Rect
from .render_utils import (
    draw_background,
    draw_border,
    draw_shadow,
    font_name_from_style,
    font_size_from_style,
    normalize_font_size,
    resolve_font_variant,
    resolve_padding,
    ensure_pdf_font,
    to_color,
)


class TextRenderer:
    """Render paragraph blocks onto a ReportLab canvas."""

    def __init__(self, canvas: Canvas, *, page_size=None, margins: Margins | None = None, footnote_renderer=None) -> None:
        self.canvas = canvas
        self.page_size = page_size
        self.margins = margins
        self.footnote_renderer = footnote_renderer

    def draw(self, block: LayoutBlock) -> None:
        style: Dict[str, Any] = block.style or {}
        alignment = (style.get("alignment") or style.get("text_align") or "left").lower()

        frame = self._translated_frame(block)

        draw_shadow(self.canvas, frame, style)
        draw_background(self.canvas, frame, style)
        draw_border(self.canvas, frame, style)
        self._apply_style(style)

        payload = block.content or {}

        pad_top, pad_right, pad_bottom, pad_left = resolve_padding(style)

        if isinstance(payload, dict) and payload.get("lines"):
            lines: List[Dict[str, Any]] = list(payload["lines"])
        elif isinstance(payload, dict) and payload.get("text"):
            # Handling format from LayoutEngine (dict with "text")
            text = payload.get("text", "")
            lines = [{"text": str(text), "offset_baseline": 0.0, "layout": None}]
        elif isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            # Convert all elements to dict if they are strings
            lines = []
            for item in payload:
                if isinstance(item, dict):
                    lines.append(item)
                elif isinstance(item, str):
                    lines.append({"text": item, "offset_baseline": 0.0, "layout": None})
                else:
                    lines.append({"text": str(item), "offset_baseline": 0.0, "layout": None})
        elif isinstance(payload, str):
            # If payload is string, use it directly
            lines = [{"text": payload, "offset_baseline": 0.0, "layout": None}]
        else:
            lines = [{"text": str(payload), "offset_baseline": 0.0, "layout": None}]

        marker = payload.get("marker") if isinstance(payload, dict) else None
        has_runs = isinstance(payload, dict) and bool(payload.get("runs"))

        text_area_hint = None
        if isinstance(payload, dict):
            text_area_hint = payload.get("usable_width")
        if text_area_hint is None:
            text_area_hint = style.get("usable_width")
        try:
            text_area_width = float(text_area_hint) if text_area_hint is not None else float(block.frame.width)
        except (TypeError, ValueError):
            text_area_width = float(block.frame.width)

        inner_frame_width = max(float(block.frame.width) - pad_left - pad_right, 0.0)
        content_width = max(inner_frame_width, 0.0)
        justify_width = max(text_area_width, content_width)

        if marker and not has_runs:
            self._draw_marker(marker, block, frame, pad_left, pad_top)
            self._apply_style(style)

        runs = []
        if isinstance(payload, dict) and payload.get("runs"):
            runs = payload["runs"]

        run_map = []
        if isinstance(payload, dict) and payload.get("run_map"):
            run_map = payload["run_map"]

        line_spacing = 1.0
        if isinstance(payload, dict) and payload.get("line_spacing"):
            try:
                line_spacing = max(float(payload["line_spacing"]), 0.1)
            except (TypeError, ValueError):
                line_spacing = 1.0

        if runs:
            self._draw_lines_with_runs(
                block,
                frame,
                lines,
                runs,
                run_map,
                style,
                marker if has_runs else None,
                pad_top,
                pad_right,
                pad_bottom,
                pad_left,
                content_width,
                justify_width,
                alignment,
            )
            return

        block_top = frame.y + frame.height - pad_top

        last_text_index = self._last_text_line_index(lines)

        for index, entry in enumerate(lines):
            text = str(entry.get("text", ""))
            layout = entry.get("layout")
            offset_baseline = float(entry.get("offset_baseline", 0.0))
            baseline_y = block_top - offset_baseline

            x_origin = frame.x + pad_left
            line_width = getattr(layout, "width", None)
            if line_width is None:
                line_width = self.canvas.stringWidth(text, self.canvas._fontname, self.canvas._fontsize)

            available = max(content_width - line_width, 0.0)
            if alignment == "center":
                x_origin += available / 2.0
            elif alignment in {"right", "end"}:
                x_origin += available

            layout_text_value = getattr(layout, "text", text) if layout else text
            extra_gap = self._justify_extra_space(
                index,
                last_text_index,
                alignment,
                line_width,
                justify_width,
                layout_text=layout_text_value,
                line_text=text,
            )

            if layout and getattr(layout, "glyphs", None):
                self._draw_glyphs(block, frame, x_origin, baseline_y, layout, None, extra_gap)
            else:
                if extra_gap > 0.0 and text:
                    words = text.split(" ")
                    base_space = self.canvas.stringWidth(" ", self.canvas._fontname, self.canvas._fontsize)
                    x_cursor = x_origin
                    for word_index, word in enumerate(words):
                        if word:
                            self.canvas.drawString(x_cursor, baseline_y, word)
                            x_cursor += self.canvas.stringWidth(
                                word, self.canvas._fontname, self.canvas._fontsize
                            )
                        if word_index < len(words) - 1:
                            x_cursor += base_space + extra_gap
                else:
                    self.canvas.drawString(x_origin, baseline_y, text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _translated_frame(self, block: LayoutBlock) -> Rect:
        left_margin = self.margins.left if self.margins else 0.0
        bottom_margin = self.margins.bottom if self.margins else 0.0
        return Rect(
            block.frame.x - left_margin,
            block.frame.y - bottom_margin,
            block.frame.width,
            block.frame.height,
        )

    def _draw_glyphs(
        self,
        block: LayoutBlock,
        frame: Rect,
        origin_x: float,
        baseline_y: float,
        layout,
        run_map=None,
        extra_space_per_gap: float = 0.0,
    ) -> None:
        text = getattr(layout, "text", "")
        glyphs = getattr(layout, "glyphs", [])

        run_map = run_map or []
        current_run_idx = 0
        current_run = run_map[0] if run_map else None
        accumulated_shift = 0.0

        for index, glyph in enumerate(glyphs):
            char = self._char_for_glyph(index, text)
            if not char:
                continue

            while current_run and index >= current_run.get("end", 0):
                current_run_idx += 1
                current_run = run_map[current_run_idx] if current_run_idx < len(run_map) else None

            if current_run:
                self._apply_style(current_run.get("style", {}))

            x = origin_x + getattr(glyph, "x", 0.0) + accumulated_shift
            y = baseline_y + getattr(glyph, "y", 0.0)
            self.canvas.drawString(x, y, char)

            if extra_space_per_gap > 0.0 and char == " ":
                accumulated_shift += extra_space_per_gap

    def _draw_marker(self, marker: Dict[str, Any], block: LayoutBlock, frame: Rect, pad_left: float, pad_top: float) -> None:
        marker_style = marker.get("style") or {}
        self._apply_style(marker_style)

        baseline_offset = float(marker.get("baseline_offset", 0.0))
        baseline_y = frame.y + frame.height - pad_top - baseline_offset
        x = float(marker.get("x", block.frame.x + pad_left))
        if "x" not in marker and marker.get("indent_hanging"):
            x = block.frame.x + pad_left - float(marker.get("indent_hanging", 0.0))
        x -= self.margins.left if self.margins else 0.0

        text = self._transform_text(str(marker.get("text", "")), marker_style)
        self.canvas.drawString(x, baseline_y, text)

        text_width = self.canvas.stringWidth(text, self.canvas._fontname, self.canvas._fontsize)
        if marker_style.get("underline"):
            self.canvas.line(x, baseline_y - 1, x + text_width, baseline_y - 1)
        if marker_style.get("strike") or marker_style.get("strikethrough"):
            strike_y = baseline_y + self.canvas._fontsize * 0.3
            self.canvas.line(x, strike_y, x + text_width, strike_y)

    @staticmethod
    def _char_for_glyph(index: int, text: str) -> Optional[str]:
        if index < len(text):
            return text[index]
        return None

    def _draw_lines_with_runs(
        self,
        block: LayoutBlock,
        frame: Rect,
        lines: Iterable[Dict[str, Any]],
        runs: Iterable[Dict[str, Any]],
        run_map: Iterable[Dict[str, Any]],
        paragraph_style: Dict[str, Any],
        marker: Optional[Dict[str, Any]],
        pad_top: float,
        pad_right: float,
        pad_bottom: float,
        pad_left: float,
        content_width: float,
        justify_width: float,
        alignment: str,
    ) -> None:
        lines_list = list(lines)
        if not lines_list:
            return

        block_top = frame.y + frame.height - pad_top

        alignment = alignment.lower()

        if marker:
            self._draw_marker(marker, block, frame, pad_left, pad_top)
            self._apply_style(paragraph_style)

        content_width = max(content_width, 0.0)
        justify_width = max(justify_width, content_width)

        run_queue: List[Dict[str, Any]] = []
        for run in runs:
            text = str(run.get("text", ""))
            if not text:
                continue
            run_queue.append({
                "text": text,
                "style": run.get("style", {}) or {},
                "pos": 0,
            })
        queue_index = 0

        last_text_index = self._last_text_line_index(lines_list)

        for idx, entry in enumerate(lines_list):
            line_text = entry.get("text", "")
            layout = entry.get("layout")
            if not line_text:
                continue

            baseline_y = block_top - float(entry.get("offset_baseline", 0.0))
            x_origin = frame.x + pad_left

            line_width = getattr(layout, "width", None)
            if line_width is None:
                line_width = self.canvas.stringWidth(line_text, self.canvas._fontname, self.canvas._fontsize)

            available = max(content_width - line_width, 0.0)
            if alignment == "center":
                x_origin += available / 2.0
            elif alignment in {"right", "end"}:
                x_origin += available

            layout_text_value = getattr(layout, "text", line_text) if layout else line_text
            extra_gap = self._justify_extra_space(
                idx,
                last_text_index,
                alignment,
                line_width,
                justify_width,
                layout_text=layout_text_value,
                line_text=line_text,
            )

            if layout and getattr(layout, "glyphs", None):
                line_start = entry.get("start", 0)
                line_end = entry.get("end", line_start + len(line_text))
                mapped_runs = []
                for rm in run_map:
                    start = rm.get("start", 0)
                    end = rm.get("end", 0)
                    if end <= line_start or start >= line_end:
                        continue
                    mapped_runs.append(
                        {
                            "start": max(start, line_start) - line_start,
                            "end": min(end, line_end) - line_start,
                            "style": rm.get("style", {}),
                        }
                    )
                self._draw_glyphs(block, frame, x_origin, baseline_y, layout, mapped_runs, extra_gap)
            else:
                x_cursor = x_origin
                remaining = line_text
                local_index = queue_index
                justify_extra = extra_gap
                while remaining:
                    if local_index >= len(run_queue):
                        segment = remaining
                        style = {}
                        advance = len(segment)
                    else:
                        current = run_queue[local_index]
                        text = current["text"]
                        pos = current["pos"]
                        run_remaining = text[pos:]
                        if not run_remaining:
                            local_index += 1
                            queue_index = max(queue_index, local_index)
                            continue

                        advance = min(len(run_remaining), len(remaining))
                        segment = run_remaining[:advance]

                        if not remaining.startswith(segment):
                            idx = advance
                            while idx > 0 and not remaining.startswith(run_remaining[:idx]):
                                idx -= 1
                            if idx == 0:
                                segment = remaining[0]
                                advance = 1
                            else:
                                segment = run_remaining[:idx]
                                advance = idx

                        if advance == len(run_remaining):
                            local_index += 1
                            queue_index = max(queue_index, local_index)

                        current["pos"] = pos + advance
                        style = dict(current.get("style", {}) or {})

                    hyperlink_target = self._resolve_hyperlink_target(style, segment)
                    if hyperlink_target:
                        style.setdefault("underline", True)
                        style.setdefault("color", "#1155cc")

                    transformed = self._transform_text(segment, style)
                    
                    # Handle superscript/subscript with baseline_shift
                    baseline_shift = style.get("baseline_shift", 0.0)
                    is_superscript = style.get("superscript") or style.get("vertical_align", "").lower() in ("superscript", "sup")
                    is_subscript = style.get("subscript") or style.get("vertical_align", "").lower() in ("subscript", "sub")
                    
                    # Calculate baseline shift if not explicitly set
                    if baseline_shift == 0.0:
                        if is_superscript:
                            font_size = self.canvas._fontsize
                            baseline_shift = font_size * 0.35  # Move up for superscript
                        elif is_subscript:
                            font_size = self.canvas._fontsize
                            baseline_shift = -font_size * 0.2  # Move down for subscript
                    
                    # Adjust font size for superscript/subscript if needed
                    original_font_size = self.canvas._fontsize
                    if is_superscript or is_subscript:
                        # Slightly reduce font size for superscript/subscript
                        adjusted_font_size = original_font_size * 0.75
                        self.canvas.setFont(self.canvas._fontname, adjusted_font_size)
                    
                    self._apply_style(style)

                    if style.get("highlight"):
                        highlight_color = to_color(style["highlight"])
                        self.canvas.saveState()
                        self.canvas.setFillColor(highlight_color)
                        text_width = self.canvas.stringWidth(transformed, self.canvas._fontname, self.canvas._fontsize)
                        height = self.canvas._fontsize * 1.2
                        # Adjust highlight rectangle position for baseline shift
                        highlight_y = baseline_y + baseline_shift - height * 0.9
                        self.canvas.rect(x_cursor, highlight_y, text_width, height, fill=1, stroke=0)
                        self.canvas.restoreState()

                    # Draw text with baseline shift
                    draw_y = baseline_y + baseline_shift
                    self.canvas.drawString(x_cursor, draw_y, transformed)
                    
                    # Calculate text width with current font size (may be adjusted for superscript/subscript)
                    text_width = self.canvas.stringWidth(transformed, self.canvas._fontname, self.canvas._fontsize)
                    
                    # Restore original font size if changed
                    if is_superscript or is_subscript:
                        self.canvas.setFont(self.canvas._fontname, original_font_size)
                    if style.get("underline"):
                        self.canvas.line(x_cursor, baseline_y - 1, x_cursor + text_width, baseline_y - 1)
                    if style.get("strike") or style.get("strikethrough"):
                        strike_y = baseline_y + self.canvas._fontsize * 0.3
                        self.canvas.line(x_cursor, strike_y, x_cursor + text_width, strike_y)

                    if hyperlink_target and text_width > 0:
                        font_size = self.canvas._fontsize
                        descent = font_size * 0.2
                        ascent = font_size * 0.8
                        rect = (x_cursor, baseline_y - descent, x_cursor + text_width, baseline_y + ascent)
                        try:
                            self.canvas.linkURL(hyperlink_target, rect, relative=0)
                        except Exception:
                            pass

                    # Render footnote references if in run
                    if self.footnote_renderer and style.get("footnote_refs"):
                        footnote_refs = style.get("footnote_refs", [])
                        if isinstance(footnote_refs, str):
                            footnote_refs = [footnote_refs]
                        elif not isinstance(footnote_refs, list):
                            footnote_refs = []
                        
                        for footnote_id in footnote_refs:
                            if footnote_id:
                                marker, number = self.footnote_renderer.render_footnote_reference_pdf(footnote_id)
                                # Renderuj jako superscript
                                self.canvas.saveState()
                                font_size = self.canvas._fontsize
                                superscript_size = font_size * 0.7
                                self.canvas.setFont(self.canvas._fontname, superscript_size)
                                superscript_x = x_cursor + text_width + 1
                                superscript_y = baseline_y + font_size * 0.3
                                self.canvas.drawString(superscript_x, superscript_y, marker)
                                self.canvas.restoreState()
                                # Zarejestruj footnote dla aktualnej strony
                                if hasattr(self.footnote_renderer, 'register_footnote_for_page'):
                                    page_number = getattr(self.canvas, '_pageNumber', 1)
                                    self.footnote_renderer.register_footnote_for_page(page_number, footnote_id)

                    x_cursor += text_width
                    remaining = remaining[advance:]

                    if advance == len(segment):
                        local_index += 1
                        queue_index = max(queue_index, local_index)

                    if justify_extra > 0.0:
                        spaces_in_segment = segment.count(" ")
                        if spaces_in_segment:
                            x_cursor += justify_extra * spaces_in_segment

    @staticmethod
    def _is_justify_alignment(alignment: str) -> bool:
        return alignment in {
            "justify",
            "justified",
            "both",
            "distributed",
            "justify_all",
        }

    @staticmethod
    def _last_text_line_index(lines: List[Dict[str, Any]]) -> int:
        for idx in range(len(lines) - 1, -1, -1):
            text = str(lines[idx].get("text", ""))
            if text.strip():
                return idx
        return -1

    def _justify_extra_space(
        self,
        line_index: int,
        last_text_index: int,
        alignment: str,
        line_width: float,
        target_width: float,
        *,
        layout_text: Optional[str],
        line_text: str,
    ) -> float:
        if not self._is_justify_alignment(alignment):
            return 0.0
        if last_text_index < 0 or line_index >= last_text_index:
            return 0.0
        if target_width <= 0.0 or line_width <= 0.0:
            return 0.0

        extra_space = target_width - line_width
        if extra_space <= 1e-6:
            return 0.0

        source_text = layout_text if layout_text is not None else line_text
        if not source_text:
            return 0.0

        gaps = source_text.count(" ")
        if gaps <= 0:
            return 0.0

        return extra_space / gaps

    def _apply_style(self, style: Dict[str, Any]) -> None:
        base_font = font_name_from_style(style, default="Times-Roman")
        font_size = normalize_font_size(style.get("font_size")) or font_size_from_style(style)
        bold = bool(style.get("bold") or style.get("is_bold") or style.get("font_weight") == "bold")
        italic = bool(style.get("italic") or style.get("is_italic") or style.get("font_style") == "italic")

        font_name = style.get("font_pdf_name") or resolve_font_variant(base_font, bold=bold, italic=italic)
        font_path = style.get("font_path")
        if font_path:
            ensure_pdf_font(font_name, font_path)
        elif font_name not in pdfmetrics.getRegisteredFontNames():
            fallback_font = resolve_font_variant(base_font, bold=bold, italic=italic)
            if fallback_font in pdfmetrics.getRegisteredFontNames():
                font_name = fallback_font
            else:
                font_name = base_font

        color_value = style.get("color") or style.get("font_color") or "#000000"
        color = to_color(str(color_value))

        small_caps = bool(style.get("small_caps") or style.get("is_small_caps"))
        if small_caps:
            font_size *= 0.8

        self.canvas.setFont(font_name, font_size)
        self.canvas.setFillColor(color)

    def _transform_text(self, text: str, style: Dict[str, Any]) -> str:
        if style.get("all_caps"):
            return text.upper()
        if style.get("small_caps"):
            return text.upper()
        return text

    def _resolve_hyperlink_target(self, style: Dict[str, Any], text: str) -> Optional[str]:
        if not style:
            return None

        hyperlink = style.get("hyperlink")
        if isinstance(hyperlink, dict):
            for key in ("url", "target", "href"):
                target = hyperlink.get(key)
                if target:
                    return str(target)
            rel_target = hyperlink.get("relationship_target")
            if rel_target:
                return str(rel_target)

        candidate = text.strip()
        if candidate.lower().startswith("http://") or candidate.lower().startswith("https://"):
            return candidate

        return None

