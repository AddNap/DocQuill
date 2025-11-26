"""
HTMLCompiler — prototypowy renderer layoutu do HTML
---------------------------------------------------

Celowo lekka implementacja, która skupia się na:
- zachowaniu proporcji oryginalnej strony (punktów) względem viewportu
- dostarczeniu prostych haków na renderowanie poszczególnych bloków

Docelowo moduł ma zastąpić/uzupełnić PDFCompiler, dlatego API jest zbliżone:
- wywołanie: ``HTMLCompiler(config).compile(unified_layout)``
- wejście: ``UnifiedLayout`` z ``LayoutPage`` i ``LayoutBlock``
- wyjście: plik HTML z inline'owym layoutem oraz wstępnym CSS

Na razie generuje strukturalny szkielet; szczegóły renderowania bloków
powinny zostać rozbudowane podczas właściwej implementacji.
"""

from __future__ import annotations

import hashlib
import json
import re
import textwrap
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union

from ..geometry import Rect, Margins
from ..layout_primitives import (
    BlockContent,
    ParagraphLayout,
    GenericLayout,
    TableLayout,
    TableCellLayout,
    ImageLayout,
    TextboxLayout,
    OverlayBox,
    InlineBox,
    ParagraphLine,
    BoxStyle,
    ColorSpec,
    BlockPayload,
)
from ..unified_layout import LayoutBlock, LayoutPage, UnifiedLayout
from ...media import MediaConverter


@dataclass(frozen=True)
class HTMLCompilerConfig:
    """
    Konfiguracja domyślnego kompilatora HTML.

    Attributes:
        output_path: Domyślna ścieżka pliku wynikowego.
        title: Tytuł dokumentu osadzony w ``<head>``.
        embed_default_styles: Czy generować minimalny boilerplate CSS.
        scaling_mode: Strategia skalowania strony (na razie tylko ``"relative"``).
        html_lang: Wartość atrybutu ``lang`` w tagu ``<html>``.
    """

    output_path: Path = Path("output.html")
    title: str = "Document"
    embed_default_styles: bool = True
    scaling_mode: str = "relative"
    html_lang: str = "pl"
    asset_output_dirname: str = "html_media"
    embed_images_as_data_uri: bool = False
    page_max_width: float = 960.0
    page_viewport_padding: float = 32.0


@dataclass
class _FlowCursor:
    """
    Śledzi bieżący punkt odniesienia (w punktach PDF) podczas renderowania liniowego.
    """

    current_bottom: float = 0.0
    pending_spacing_after: float = 0.0


@dataclass
class _BlockRenderContext:
    block: LayoutBlock
    page_index: int
    flow_offset: float
    absolute_offset: float
    page_height: float
    page_width: float
    margin_top: float
    margin_right: float
    margin_bottom: float
    margin_left: float
    serial: int
    section_role: str = "body"
    section_origin: float = 0.0
    top_in_page: float = 0.0
    section_shift: float = 0.0


class HTMLCompiler:
    """
    Minimalna implementacja kompilatora HTML.

    Zakłada jeden główny kontener ``<div class="page">`` na każdą stronę layoutu
    oraz absolutnie pozycjonowane bloki wewnątrz. Treść bloków jest na razie
    reprezentowana tekstowo, co ułatwia dalszą rozbudowę.
    """

    def __init__(
        self,
        config: Optional[HTMLCompilerConfig] = None,
        *,
        output_path: Optional[Union[str, Path]] = None,
        package_reader: Optional[Any] = None,
        media_converter: Optional[MediaConverter] = None,
    ) -> None:
        self.config = config or HTMLCompilerConfig()
        self.output_path = Path(output_path) if output_path else self.config.output_path
        self.package_reader = package_reader
        self.media_converter = media_converter or MediaConverter()
        self._asset_cache: Dict[str, str] = {}
        self._assets_root: Optional[Path] = None
        
        # Parse footnotes and endnotes if package_reader is available
        self.footnotes: Dict[str, Any] = {}
        self.endnotes: Dict[str, Any] = {}
        if self.package_reader:
            try:
                from ...parser.notes_parser import NotesParser
                notes_parser = NotesParser(self.package_reader)
                self.footnotes = notes_parser.get_footnotes()
                self.endnotes = notes_parser.get_endnotes()
            except Exception:
                pass  # Silently fail if notes parsing fails

    # ------------------------------------------------------------------
    # API publiczne
    # ------------------------------------------------------------------
    def compile(
        self,
        unified_layout: UnifiedLayout,
        *,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Wygeneruj plik HTML dla podanego ``UnifiedLayout``.
        """
        if not unified_layout.pages:
            raise ValueError("UnifiedLayout nie zawiera żadnych stron do renderowania.")

        target_path = Path(output_path) if output_path else self.output_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        self._assets_root = target_path.parent / self.config.asset_output_dirname
        if not self.config.embed_images_as_data_uri:
            self._assets_root.mkdir(parents=True, exist_ok=True)
        self._asset_cache.clear()

        html = self._render_document(unified_layout)
        target_path.write_text(html, encoding="utf-8")
        return target_path

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _render_document(self, unified_layout: UnifiedLayout) -> str:
        head = self._render_head()
        body = self._render_body(unified_layout)
        footnotes_section = self._render_footnotes_section()
        endnotes_section = self._render_endnotes_section()
        script = self._default_document_script()
        lang = self.config.html_lang or "pl"

        return "\n".join(
            [
                "<!DOCTYPE html>",
                f'<html lang="{lang}">',
                "<head>",
                head,
                "</head>",
                "<body>",
                body,
                footnotes_section,
                endnotes_section,
                f"<script>{script}</script>" if script else "",
                "</body>",
                "</html>",
            ]
        )

    def _render_head(self) -> str:
        title = self.config.title or "Document"
        parts = [f"<meta charset=\"utf-8\" />", f"<title>{title}</title>"]

        if self.config.embed_default_styles:
            parts.append("<style>")
            parts.append(self._default_stylesheet())
            parts.append(self._footnotes_css())
            parts.append("</style>")
        return "\n".join(parts)
    
    def _render_footnotes_section(self) -> str:
        """Render footnotes section."""
        if not self.footnotes:
            return ""
        
        from ...renderers.footnote_renderer import FootnoteRenderer
        footnote_renderer = FootnoteRenderer(self.footnotes, {})
        return footnote_renderer.render_footnotes_section()
    
    def _render_endnotes_section(self) -> str:
        """Render endnotes section."""
        if not self.endnotes:
            return ""
        
        from ...renderers.footnote_renderer import FootnoteRenderer
        footnote_renderer = FootnoteRenderer({}, self.endnotes)
        return footnote_renderer.render_endnotes_section()
    
    def _footnotes_css(self) -> str:
        """Get CSS for footnotes."""
        if not self.footnotes and not self.endnotes:
            return ""
        
        from ...renderers.footnote_renderer import FootnoteRenderer
        footnote_renderer = FootnoteRenderer(self.footnotes, self.endnotes)
        return footnote_renderer.get_footnote_css()

    def _render_body(self, layout: UnifiedLayout) -> str:
        pages_list = list(layout.pages)
        return self._render_document_flat(layout, pages_list)

    def _detect_section_role(self, block: LayoutBlock) -> str:
        block_type = (block.block_type or "").strip().lower()
        if block_type in {"header", "footer"}:
            return block_type

        raw_context: Optional[Dict[str, Any]] = None
        content = block.content
        if isinstance(content, BlockContent):
            raw_context = content.raw
        elif isinstance(content, dict):
            raw_context = content
        elif hasattr(content, "raw"):
            candidate = getattr(content, "raw", None)
            if isinstance(candidate, dict):
                raw_context = candidate

        def _extract_role(container: Optional[Dict[str, Any]]) -> Optional[str]:
            if not isinstance(container, dict):
                return None
            value = container.get("header_footer_context") or container.get("headerFooterContext")
            if isinstance(value, str):
                token = value.strip().lower()
                if token in {"header", "footer"}:
                    return token
            return None

        role = _extract_role(raw_context)
        if role:
            return role

        style_dict = block.style if isinstance(block.style, dict) else {}
        role = _extract_role(style_dict)
        if role:
            return role

        payload = None
        if isinstance(content, BlockContent):
            payload = content.payload
        elif hasattr(content, "payload"):
            payload = getattr(content, "payload", None)
        if isinstance(payload, GenericLayout):
            role = _extract_role(payload.data if isinstance(payload.data, dict) else None)
            if role:
                return role

        return "body"

    def _render_document_flat(self, unified_layout: UnifiedLayout, pages: list[LayoutPage]) -> str:
        if not pages:
            return '<div class="document-root"></div>'

        first_page = pages[0]
        first_page_width = float(getattr(first_page.size, "width", 0.0) or 0.0)
        width_px = self._points_to_css_float(first_page_width)
        margins = getattr(first_page, "margins", None)
        padding_top = self._points_to_css_float(getattr(margins, "top", 0.0) if margins else 0.0)
        padding_right = self._points_to_css_float(getattr(margins, "right", 0.0) if margins else 0.0)
        padding_bottom = self._points_to_css_float(getattr(margins, "bottom", 0.0) if margins else 0.0)
        padding_left = self._points_to_css_float(getattr(margins, "left", 0.0) if margins else 0.0)

        root_style_parts = [
            "position: relative",
            "margin: 0 auto",
            "box-sizing: border-box",
            "background: #ffffff",
            "padding: 0",
            "overflow: hidden",
            "--doc-page-margin-top: 0px",
            "--doc-page-margin-right: 0px",
            "--doc-page-margin-bottom: 0px",
            "--doc-page-margin-left: 0px",
            "--doc-page-gap: 32px",
        ]
        if width_px:
            root_style_parts.append(f"width: {width_px:.2f}px")
            root_style_parts.append(f"max-width: {width_px:.2f}px")
        if padding_top is not None:
            root_style_parts.append(f"--doc-page-margin-top: {(padding_top or 0):.2f}px")
        if padding_right is not None:
            root_style_parts.append(f"--doc-page-margin-right: {(padding_right or 0):.2f}px")
        if padding_bottom is not None:
            root_style_parts.append(f"--doc-page-margin-bottom: {(padding_bottom or 0):.2f}px")
        if padding_left is not None:
            root_style_parts.append(f"--doc-page-margin-left: {(padding_left or 0):.2f}px")

        first_page_height = float(getattr(first_page.size, "height", 0.0) or 0.0)
        first_page_height_px = self._points_to_css_float(first_page_height)
        if first_page_height_px:
            root_style_parts.append(f"min-height: {first_page_height_px:.2f}px")
        # Intentionally avoid enforcing min-height so the page ends with the footer container.
        header_contexts_by_page: dict[int, list[_BlockRenderContext]] = {}
        footer_contexts_by_page: dict[int, list[_BlockRenderContext]] = {}
        footer_min_top_by_page: dict[int, float] = {}
        footer_section_origin_by_page: dict[int, float] = {}
        body_contexts: list[_BlockRenderContext] = []
        serial_counter = 0
        body_flow_offset = 0.0
        absolute_offset = 0.0
        for index, page in enumerate(pages):
            page_height = float(getattr(page.size, "height", 0.0) or 0.0)
            page_width = float(getattr(page.size, "width", 0.0) or 0.0)
            page_margins = getattr(page, "margins", None)
            margin_top = float(getattr(page_margins, "top", 0.0) or 0.0) if page_margins else 0.0
            margin_right = float(getattr(page_margins, "right", 0.0) or 0.0) if page_margins else 0.0
            margin_bottom = float(getattr(page_margins, "bottom", 0.0) or 0.0) if page_margins else 0.0
            margin_left = float(getattr(page_margins, "left", 0.0) or 0.0) if page_margins else 0.0
            content_height = max(page_height - margin_top - margin_bottom, 0.0)
            section_origin_body = margin_top
            section_origin_header = 0.0
            section_origin_footer = page_height - margin_bottom

            for block in page.blocks:
                section_role = self._detect_section_role(block)
                if section_role == "header":
                    flow_offset = 0.0
                    section_origin = section_origin_header
                elif section_role == "footer":
                    flow_offset = 0.0
                    section_origin = section_origin_footer
                else:
                    flow_offset = body_flow_offset
                    section_origin = section_origin_body

                frame = getattr(block, "frame", None)
                top_in_page = 0.0
                if frame is not None:
                    top_in_page = max(
                        page_height - float(getattr(frame, "y", 0.0)) - float(getattr(frame, "height", 0.0)),
                        0.0,
                    )

                context = _BlockRenderContext(
                    block=block,
                    page_index=index,
                    flow_offset=flow_offset,
                    absolute_offset=absolute_offset,
                    page_height=page_height,
                    page_width=page_width,
                    margin_top=margin_top,
                    margin_right=margin_right,
                    margin_bottom=margin_bottom,
                    margin_left=margin_left,
                    serial=serial_counter,
                    section_role=section_role,
                    section_origin=section_origin,
                    top_in_page=top_in_page,
                )
                serial_counter += 1
                if section_role == "header":
                    header_contexts_by_page.setdefault(index, []).append(context)
                elif section_role == "footer":
                    footer_contexts_by_page.setdefault(index, []).append(context)
                    footer_section_origin_by_page.setdefault(index, section_origin_footer)
                    current_min = footer_min_top_by_page.get(index, section_origin_footer)
                    footer_min_top_by_page[index] = min(current_min, top_in_page)
                    payload_for_overlays = self._extract_block_payload(block)
                    if payload_for_overlays is not None:
                        for overlay in self._iter_overlays(payload_for_overlays):
                            overlay_top = self._overlay_top_in_page(overlay, context)
                            current_min = footer_min_top_by_page.get(index, section_origin_footer)
                            footer_min_top_by_page[index] = min(current_min, overlay_top)
                else:
                    body_contexts.append(context)

            body_flow_offset += content_height
            absolute_offset += page_height

        def _sort_contexts(items: list[_BlockRenderContext]) -> list[_BlockRenderContext]:
            if any(ctx.block.sequence is not None for ctx in items):
                return sorted(
                    items,
                    key=lambda ctx: (
                        ctx.block.sequence if ctx.block.sequence is not None else ctx.serial
                    ),
                )
            return sorted(items, key=lambda ctx: ctx.serial)

        footer_shift_by_page: dict[int, float] = {}
        for page_idx, contexts in footer_contexts_by_page.items():
            section_origin_footer = footer_section_origin_by_page.get(page_idx, 0.0)
            min_top = footer_min_top_by_page.get(page_idx, section_origin_footer)
            shift = max(0.0, section_origin_footer - min_top)
            footer_shift_by_page[page_idx] = shift
            for ctx in contexts:
                ctx.section_shift = shift

        footer_content_height_by_page: dict[int, float] = {}
        footer_first_top_by_page: dict[int, float] = {}
        for page_idx, contexts in footer_contexts_by_page.items():
            shift = footer_shift_by_page.get(page_idx, 0.0)
            if not contexts:
                continue
            first_context = contexts[0]
            first_top = first_context.section_origin - shift
            footer_first_top_by_page[page_idx] = first_top
            max_extent = 0.0
            for ctx in contexts:
                frame = getattr(ctx.block, "frame", None)
                if frame is None:
                    continue
                block_height = max(float(getattr(frame, "height", 0.0) or 0.0), 0.0)
                effective_origin = ctx.section_origin - shift
                top_rel = ctx.top_in_page - effective_origin
                top_rel = max(top_rel, 0.0)
                max_extent = max(max_extent, top_rel + block_height)
            footer_content_height_by_page[page_idx] = max_extent

        header_contexts: list[_BlockRenderContext] = []
        if header_contexts_by_page:
            first_header_page = min(header_contexts_by_page.keys())
            header_contexts = _sort_contexts(header_contexts_by_page[first_header_page])

        footer_contexts: list[_BlockRenderContext] = []
        selected_footer_page: Optional[int] = None
        if footer_contexts_by_page:
            last_footer_page = max(footer_contexts_by_page.keys())
            selected_footer_page = last_footer_page
            footer_contexts = _sort_contexts(footer_contexts_by_page[last_footer_page])

        body_contexts = _sort_contexts(body_contexts)

        def _render_section(section_contexts: list[_BlockRenderContext]) -> str:
            if not section_contexts:
                return ""
            flow_cursor = _FlowCursor()
            flow_html: list[str] = []
            overlay_html: list[str] = []
            for context in section_contexts:
                block_html = self._render_block(context, flow_cursor)
                if block_html:
                    flow_html.append(block_html)
                overlay_html.extend(self._collect_overlays(context))
            return "\n".join(filter(None, [*flow_html, *overlay_html]))

        header_html = _render_section(header_contexts)
        body_html = _render_section(body_contexts)
        footer_html = _render_section(footer_contexts)

        footer_margin_px = 0.0
        footer_content_height_px = 0.0
        if footer_html and selected_footer_page is not None:
            shift_pt = footer_shift_by_page.get(selected_footer_page, 0.0)
            shift_px = self._points_to_css_float(shift_pt)
            if shift_px:
                footer_margin_px = shift_px
            content_height_pt = footer_content_height_by_page.get(selected_footer_page, 0.0)
            content_height_px = self._points_to_css_float(content_height_pt)
            if content_height_px:
                footer_content_height_px = content_height_px
        margin_bottom_pt = 0.0
        if selected_footer_page is not None and footer_contexts_by_page.get(selected_footer_page):
            margin_bottom_pt = footer_contexts_by_page[selected_footer_page][0].margin_bottom
        elif first_page:
            margin_bottom_pt = float(getattr(first_page.margins, "bottom", 0.0) or 0.0)
        margin_bottom_px = self._points_to_css_float(margin_bottom_pt) or 0.0

        footer_total_height_px = max(
            margin_bottom_px,
            footer_margin_px + footer_content_height_px,
        )

        sections_html: list[str] = []
        if header_html:
            header_style_parts = [
                self._format_section_padding(
                    0.0,
                    padding_right or 0.0,
                    0.0,
                    padding_left or 0.0,
                )
            ]
            if (padding_top or 0.0) > 0.0:
                header_style_parts.append(f"min-height: {(padding_top or 0.0):.2f}px")
            sections_html.append(
                "<div "
                'class="document-header" '
                f'data-margin-top-px="{(padding_top or 0.0):.2f}" '
                f'style="{"; ".join(header_style_parts)}">{header_html}</div>'
            )
        if body_html:
            body_padding = self._format_section_padding(
                0.0,
                padding_right or 0.0,
                0.0,
                padding_left or 0.0,
            )
            if footer_total_height_px > 0.0:
                body_padding = f"{body_padding}; padding-bottom: {footer_total_height_px:.2f}px"
            sections_html.append(
                f'<div class="document-body" style="{body_padding}">{body_html}</div>'
            )
        if footer_html:
            footer_style_parts = [
                self._format_section_padding(
                    0.0,
                    padding_right or 0.0,
                    0.0,
                    padding_left or 0.0,
                ),
                "position: absolute",
                "left: 0",
                "right: 0",
                "bottom: 0",
            ]
            if footer_total_height_px > 0.0:
                footer_style_parts.append(f"min-height: {footer_total_height_px:.2f}px")
            sections_html.append(
                "<div "
                'class="document-footer" '
                f'data-margin-bottom-px="{(padding_bottom or 0.0):.2f}" '
                f'data-footer-margin-px="{footer_margin_px:.2f}" '
                f'style="{"; ".join(footer_style_parts)}">{footer_html}</div>'
            )

        blocks_html = "\n".join(filter(None, sections_html))

        root_style = "; ".join(root_style_parts)
        root_attrs: list[str] = [
            'class="document-root"',
            f'style="{root_style}"',
        ]
        root_attrs.append('data-layout-mode="flow"')
        if first_page_width > 0.0:
            root_attrs.append(f'data-page-width-pt="{first_page_width:.2f}"')
        if width_px:
            root_attrs.append(f'data-page-width-px="{width_px:.2f}"')
        if first_page_height > 0.0:
            root_attrs.append(f'data-page-height-pt="{first_page_height:.2f}"')
        if first_page_height_px:
            root_attrs.append(f'data-page-height-px="{first_page_height_px:.2f}"')
        if padding_top is not None:
            root_attrs.append(f'data-margin-top-px="{padding_top or 0:.2f}"')
        if padding_bottom is not None:
            root_attrs.append(f'data-margin-bottom-px="{padding_bottom or 0:.2f}"')
        if padding_left is not None:
            root_attrs.append(f'data-margin-left-px="{padding_left or 0:.2f}"')
        if padding_right is not None:
            root_attrs.append(f'data-margin-right-px="{padding_right or 0:.2f}"')
        root_attr_str = " ".join(root_attrs)
        return "\n".join(
            [
                f"<div {root_attr_str}>",
                blocks_html,
                "</div>",
            ]
        )

    @staticmethod
    def _format_section_padding(
        padding_top: float,
        padding_right: float,
        padding_bottom: float,
        padding_left: float,
    ) -> str:
        def _fmt(value: float) -> str:
            return f"{value:.2f}px"

        segments = [
            "position: relative",
            "box-sizing: border-box",
            f"padding: {_fmt(padding_top)} {_fmt(padding_right)} {_fmt(padding_bottom)} {_fmt(padding_left)}",
            "width: 100%",
        ]
        return "; ".join(segments)

    @staticmethod
    def _safe_float_optional(value: Any) -> Optional[float]:
        if value in (None, "", False):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _emu_to_points(value: Any) -> Optional[float]:
        numeric = HTMLCompiler._safe_float_optional(value)
        if numeric is None:
            return None
        # 1 EMU = 1/914400 inch; 1 inch = 72 points
        return numeric * 72.0 / 914400.0

    def _extract_overlay_anchor(
        self,
        overlay: OverlayBox,
    ) -> tuple[Optional[float], Optional[str], Optional[float], Optional[str]]:
        payload = getattr(overlay, "payload", None)
        if not isinstance(payload, dict):
            return (None, None, None, None)

        stack: list[dict[str, Any]] = [payload]
        visited: set[int] = set()
        anchor_x: Optional[float] = None
        anchor_y: Optional[float] = None
        anchor_x_rel: Optional[str] = None
        anchor_y_rel: Optional[str] = None

        while stack:
            current = stack.pop()
            identifier = id(current)
            if identifier in visited:
                continue
            visited.add(identifier)

            if not isinstance(current, dict):
                continue

            position = current.get("position")
            if isinstance(position, dict):
                if anchor_x is None:
                    anchor_x = self._emu_to_points(position.get("x"))
                    anchor_x_rel = position.get("x_rel") or position.get("xRel")
                if anchor_y is None:
                    anchor_y = self._emu_to_points(position.get("y"))
                    anchor_y_rel = position.get("y_rel") or position.get("yRel")
                if anchor_x is not None and anchor_y is not None:
                    break

            for key in ("source", "image", "textbox", "content", "payload", "data"):
                nested = current.get(key)
                if isinstance(nested, dict):
                    stack.append(nested)

        return anchor_x, anchor_x_rel, anchor_y, anchor_y_rel

    def _resolve_overlay_vertical_position(
        self,
        points: float,
        relation: Optional[str],
        context: _BlockRenderContext,
        frame_height: float,
    ) -> float:
        rel = (relation or "").strip().lower()
        if rel in {"margin", "top-margin"}:
            return context.margin_top + points
        if rel in {"bottom", "page-bottom"}:
            return max(context.page_height - points - frame_height, 0.0)
        if rel in {"bottom-margin"}:
            return max(
                context.page_height - context.margin_bottom - points - frame_height,
                0.0,
            )
        return max(points, 0.0)

    def _resolve_overlay_horizontal_position(
        self,
        points: float,
        relation: Optional[str],
        context: _BlockRenderContext,
        frame_width: float,
    ) -> float:
        rel = (relation or "").strip().lower()
        if rel in {"margin", "left-margin", "column"}:
            return context.margin_left + points
        if rel in {"right-margin"}:
            effective_width = max(context.page_width - context.margin_right, 0.0)
            return max(effective_width - frame_width - points, 0.0)
        return points

    def _render_block(
        self,
        context: _BlockRenderContext,
        flow_cursor: _FlowCursor,
    ) -> str:
        block = context.block
        payload = self._extract_block_payload(block)
        if self._requires_absolute_position(block, payload):
            flow_cursor.pending_spacing_after = 0.0
            return self._render_block_absolute(context, payload)
        return self._render_block_flow(context, flow_cursor, payload)

    def _extract_block_payload(self, block: LayoutBlock) -> Optional[BlockPayload]:
        content = block.content
        if isinstance(content, BlockContent):
            return content.payload
        if isinstance(content, dict):
            payload = content.get("payload")
            if payload:
                return payload  # type: ignore[return-value]
            nested = content.get("layout_payload") or content.get("_layout_payload")
            if nested:
                return nested  # type: ignore[return-value]
        if isinstance(content, (ParagraphLayout, TableLayout, ImageLayout, TextboxLayout, GenericLayout)):
            return content  # type: ignore[return-value]
        return None

    def _requires_absolute_position(
        self,
        block: LayoutBlock,
        payload: Optional[BlockPayload],
    ) -> bool:
        block_type = (block.block_type or "").lower()
        if block_type in {"decorator", "background"}:
            return True
        if isinstance(payload, TextboxLayout) and getattr(payload, "anchor_mode", "inline") == "anchor":
            return True
        if isinstance(payload, GenericLayout):
            marker_type = (payload.data or {}).get("type")
            if isinstance(marker_type, str) and marker_type.lower() in {"header_marker", "footer_marker"}:
                return True
        style = block.style or {}
        if isinstance(style, dict):
            position_value = str(style.get("position") or "").lower()
            if position_value == "absolute":
                return True
        return False

    def _flow_requires_min_height(self, payload: Optional[BlockPayload], block_type: str) -> bool:
        if isinstance(payload, TableLayout):
            return True
        if isinstance(payload, ImageLayout):
            return True
        if block_type.lower() in {"table", "image", "picture", "chart"}:
            return True
        return False

    def _render_block_absolute(
        self,
        context: _BlockRenderContext,
        payload: Optional[BlockPayload],
    ) -> str:
        block = context.block
        frame = block.frame

        raw_top_in_page = (
            context.page_height
            - float(getattr(frame, "y", 0.0))
            - float(getattr(frame, "height", 0.0))
        )
        top_in_page = (
            raw_top_in_page
            if context.section_role == "footer"
            else max(raw_top_in_page, 0.0)
        )
        origin_top = context.absolute_offset + top_in_page
        section_shift = context.section_shift if context.section_role == "footer" else 0.0
        effective_origin = context.section_origin - section_shift
        relative_top = top_in_page - effective_origin
        if context.section_role != "footer" and relative_top < 0.0:
            relative_top = 0.0
        left_points = max(float(getattr(frame, "x", 0.0)) - context.margin_left, 0.0)

        top_points = context.flow_offset + relative_top

        left_px = self._points_to_css_float(left_points)
        top_px = self._points_to_css_float(top_points)
        width_px = self._points_to_css_float(float(getattr(frame, "width", 0.0)))
        height_px = self._points_to_css_float(float(getattr(frame, "height", 0.0)))

        style_parts = ["position: absolute"]
        if top_px is not None:
            style_parts.append(f"top: {top_px:.2f}px")
        if left_px is not None:
            style_parts.append(f"left: {left_px:.2f}px")
        if width_px is not None and width_px > 0:
            style_parts.append(f"width: {width_px:.2f}px")
        if height_px is not None and height_px > 0:
            style_parts.append(f"height: {height_px:.2f}px")

        style_override = self._style_dict_to_css(self._extract_block_style(block))
        if style_override:
            style_parts.append(style_override)

        style = "; ".join(style_parts)

        content_html = self._render_block_content(block)
        between_lines_html = self._render_between_lines(block)
        if between_lines_html:
            content_html = "\n".join([content_html, *between_lines_html])
        origin_left = float(getattr(frame, "x", 0.0) or 0.0)
        origin_page = context.page_index + 1
        attr_parts = [
            f'class="document-block block block-{escape(block.block_type)}"',
            f'data-type="{escape(block.block_type)}"',
            'data-page="1"',
            f'data-origin-page="{origin_page}"',
            f'data-block-uid="{context.serial}"',
            f'data-origin-top="{origin_top:.2f}"',
            f'data-origin-left="{origin_left:.2f}"',
        ]
        if context.section_role:
            attr_parts.append(f'data-section-role="{escape(context.section_role)}"')
        if context.section_role:
            attr_parts.append(f'data-section-role="{escape(context.section_role)}"')
        if block.sequence is not None:
            attr_parts.append(f'data-block-seq="{block.sequence}"')
        source_uid = getattr(block, "source_uid", None)
        if source_uid:
            normalized_uid = self._normalize_dom_id(str(source_uid))
            escaped_uid = escape(normalized_uid, quote=True)
            attr_parts.append(f'data-source-uid="{escaped_uid}"')
            attr_parts.append(f'id="block-{escaped_uid}"')
        decoration_payload = self._extract_block_decorations(block)
        if decoration_payload:
            attr_parts.append(f'data-decor="{self._encode_data_attribute(decoration_payload)}"')
        attr_parts.append(f'style="{style}"')
        block_html = (
            f"<div {' '.join(attr_parts)}>"
            f"{content_html}"
            "</div>"
        )
        return block_html

    def _render_block_flow(
        self,
        context: _BlockRenderContext,
        flow_cursor: _FlowCursor,
        payload: Optional[BlockPayload],
    ) -> str:
        block = context.block
        frame = block.frame
        page_height = context.page_height

        raw_top_in_page = (
            page_height
            - float(getattr(frame, "y", 0.0))
            - float(getattr(frame, "height", 0.0))
        )
        top_in_page = (
            raw_top_in_page
            if context.section_role == "footer"
            else max(raw_top_in_page, 0.0)
        )
        bottom_in_page = max(
            page_height - float(getattr(frame, "y", 0.0)),
            0.0,
        )
        origin_top = context.flow_offset + top_in_page

        block_height_points = max(float(getattr(frame, "height", 0.0)), 0.0)
        section_shift = context.section_shift if context.section_role == "footer" else 0.0
        effective_origin = context.section_origin - section_shift
        relative_top = top_in_page - effective_origin
        if context.section_role != "footer" and relative_top < 0.0:
            relative_top = 0.0
        top_points = context.flow_offset + relative_top
        bottom_points = top_points + block_height_points

        margin_top_points = max(top_points - flow_cursor.current_bottom, 0.0)
        margin_top_px = self._points_to_css_float(margin_top_points)
        flow_cursor.current_bottom = max(flow_cursor.current_bottom, bottom_points)

        margin_left_points = max(float(getattr(frame, "x", 0.0)) - context.margin_left, 0.0)
        margin_left_px = self._points_to_css_float(margin_left_points)
        width_px = self._points_to_css_float(max(float(getattr(frame, "width", 0.0)), 0.0))
        style_parts: list[str] = ["position: relative"]

        spacing_before_pt, spacing_after_pt = self._extract_block_spacing(block)
        spacing_gap_pt = max(flow_cursor.pending_spacing_after, spacing_before_pt)
        if spacing_gap_pt > 0.0:
            spacing_gap_px = self._points_to_css_float(spacing_gap_pt)
            if spacing_gap_px is not None:
                if margin_top_px is None or spacing_gap_px > margin_top_px:
                    margin_top_px = spacing_gap_px

        if margin_top_px is not None and margin_top_px > 0:
            style_parts.append(f"margin-top: {margin_top_px:.2f}px")
        else:
            style_parts.append("margin-top: 0")

        if (
            isinstance(block.content, BlockContent)
            and isinstance(block.content.raw, dict)
        ):
            if margin_left_px is not None:
                block.content.raw["_html_block_margin_left_px"] = float(margin_left_px)
            else:
                block.content.raw.pop("_html_block_margin_left_px", None)

        if margin_left_px is not None and margin_left_px > 0:
            style_parts.append(f"margin-left: {margin_left_px:.2f}px")
        else:
            style_parts.append("margin-left: 0")

        if width_px is not None and width_px > 0:
            style_parts.append(f"width: {width_px:.2f}px")
            style_parts.append(f"max-width: {width_px:.2f}px")
        else:
            style_parts.append("width: 100%")

        if self._flow_requires_min_height(payload, block.block_type):
            min_height_px = self._points_to_css_float(max(float(getattr(frame, "height", 0.0)), 0.0))
            if min_height_px is not None and min_height_px > 0:
                style_parts.append(f"min-height: {min_height_px:.2f}px")

        style_override = self._style_dict_to_css(self._extract_block_style(block))
        if style_override:
            filtered_parts: list[str] = []
            for part in style_override.split(";"):
                normalized = part.strip()
                if not normalized:
                    continue
                prop_name = normalized.split(":", 1)[0].strip().lower()
                if prop_name in {
                    "position",
                    "top",
                    "left",
                    "right",
                    "bottom",
                    "height",
                    "max-height",
                    "min-height",
                } or prop_name.startswith("border") or prop_name.startswith("background"):
                    continue
                filtered_parts.append(normalized)
            if filtered_parts:
                style_parts.append("; ".join(filtered_parts))

        style = "; ".join(style_parts)

        content_html = self._render_block_content(block)
        between_lines_html = self._render_between_lines(block)
        if between_lines_html:
            content_html = "\n".join([content_html, *between_lines_html])

        overlay_html = self._collect_overlays(context)
        origin_left = float(getattr(frame, "x", 0.0) or 0.0)
        origin_page = context.page_index + 1
        attr_parts = [
            f'class="document-block block block-{escape(block.block_type)}"',
            f'data-type="{escape(block.block_type)}"',
            'data-page="1"',
            f'data-origin-page="{origin_page}"',
            f'data-block-uid="{context.serial}"',
            f'data-origin-top="{origin_top:.2f}"',
            f'data-origin-left="{origin_left:.2f}"',
        ]
        if block.sequence is not None:
            attr_parts.append(f'data-block-seq="{block.sequence}"')
        source_uid = getattr(block, "source_uid", None)
        if source_uid:
            normalized_uid = self._normalize_dom_id(str(source_uid))
            escaped_uid = escape(normalized_uid, quote=True)
            attr_parts.append(f'data-source-uid="{escaped_uid}"')
            attr_parts.append(f'id="block-{escaped_uid}"')
        decoration_payload = self._extract_block_decorations(block)
        if decoration_payload:
            attr_parts.append(f'data-decor="{self._encode_data_attribute(decoration_payload)}"')
        attr_parts.append(f'style="{style}"')
        block_html = (
            f"<div {' '.join(attr_parts)}>"
            f"{content_html}"
            "</div>"
        )
        flow_cursor.pending_spacing_after = spacing_after_pt
        if not overlay_html:
            return block_html
        return "\n".join([block_html, *overlay_html])

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _extract_block_spacing(self, block: LayoutBlock) -> tuple[float, float]:
        style = block.style if isinstance(block.style, dict) else {}
        if not isinstance(style, dict):
            style = {}
        before = style.get("_html_spacing_before")
        after = style.get("_html_spacing_after")
        if before in (None, ""):
            before = style.get("spacing_before")
        if after in (None, ""):
            after = style.get("spacing_after")
        before_value = self._safe_float(before)
        after_value = self._safe_float(after)
        if before_value < 0.0:
            before_value = 0.0
        if after_value < 0.0:
            after_value = 0.0
        return before_value, after_value

    def _default_stylesheet(self) -> str:
        return "\n".join(
            [
                "html, body {",
                "  margin: 0;",
                "  padding: 0;",
                "  background: #f5f5f5;",
                "  font-family: 'Arial', 'Helvetica', sans-serif;",
                "}",
                ".page-wrapper {",
                "  display: flex;",
                "  justify-content: center;",
                "  padding: 16px;",
                "  --page-width: 794px;",
                "  --page-height: 1123px;",
                "  --page-max-width: 960px;",
                "  --page-scale-max: min(1, calc(var(--page-max-width) / var(--page-width)));",
                "  --page-scale-vw: min(1, calc((100vw - var(--page-viewport-padding)) / var(--page-width)));",
                "  --page-scale: max(0.1, min(var(--page-scale-max), var(--page-scale-vw)));",
                "}",
                ".page-viewport {",
                "  position: relative;",
                "  width: calc(var(--page-width) * var(--page-scale));",
                "  height: calc(var(--page-height) * var(--page-scale));",
                "}",
                ".page {",
                "  position: relative;",
                "  width: var(--page-width);",
                "  height: var(--page-height);",
                "  transform-origin: top left;",
                "  transform: scale(var(--page-scale));",
                "}",
                ".document-root {",
                "  position: relative;",
                "  margin: 0 auto;",
                "  box-sizing: border-box;",
                "  background: #ffffff;",
                "  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);",
                "  --doc-font-scale: 1;",
                "  --doc-page-margin-top: 0px;",
                "  --doc-page-margin-right: 0px;",
                "  --doc-page-margin-bottom: 0px;",
                "  --doc-page-margin-left: 0px;",
                "  --doc-page-gap: 32px;",
                "}",
                ".document-header, .document-footer, .document-body {",
                "  width: 100%;",
                "  box-sizing: border-box;",
                "}",
                ".doc-pages {",
                "  position: relative;",
                "  display: flex;",
                "  flex-direction: column;",
                "  gap: var(--doc-page-gap);",
                "}",
                ".doc-page {",
                "  position: relative;",
                "  margin: 0 auto;",
                "  background: #ffffff;",
                "  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.08);",
                "}",
                ".doc-page-body {",
                "  position: relative;",
                "  box-sizing: border-box;",
                "  padding: var(--doc-page-margin-top) var(--doc-page-margin-right) var(--doc-page-margin-bottom) var(--doc-page-margin-left);",
                "}",
                ".document-block {",
                "  position: relative;",
                "  box-sizing: border-box;",
                "}",
                ".doc-block-decor {",
                "  position: absolute;",
                "  inset: 0;",
                "  pointer-events: none;",
                "  box-sizing: border-box;",
                "}",
                ".doc-layout-guides {",
                "  position: absolute;",
                "  inset: 0;",
                "  pointer-events: none;",
                "  z-index: 1;",
                "}",
                ".doc-page-guide {",
                "  position: absolute;",
                "  left: 0;",
                "  right: 0;",
                "  border-top: 1px dashed rgba(0, 0, 0, 0.15);",
                "}",
                ".page-canvas {",
                "  position: absolute;",
                "  inset: 0;",
                "  background: white;",
                "  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);",
                "  overflow: hidden;",
                "}",
                ".block {",
                "  box-sizing: border-box;",
                "}",
                ".block:hover {",
                "  outline: 1px dashed rgba(0, 0, 0, 0.2);",
                "}",
                ".block .paragraph {",
                "  line-height: 1.35;",
                "  color: #222;",
                "  position: relative;",
                "}",
                ".block .paragraph-line {",
                "  white-space: pre-wrap;",
                "}",
                ".block .text-run {",
                "  display: inline;",
                "}",
                ".block .field {",
                "  display: inline;",
                "  color: #666;",
                "  font-style: italic;",
                "}",
                ".block .inline-textbox {",
                "  display: inline-block;",
                "  vertical-align: baseline;",
                "  background: transparent;",
                "  padding: 0;",
                "  border-radius: 0;",
                "}",
                ".block .text-run {",
                "  display: inline;",
                "}",
                ".block .run-bold {",
                "  font-weight: 600;",
                "}",
                ".block .run-italic {",
                "  font-style: italic;",
                "}",
                ".block .run-underline {",
                "  text-decoration: underline;",
                "}",
                ".block .run-strike {",
                "  text-decoration: line-through;",
                "}",
                ".block .run-sup {",
                "  vertical-align: super;",
                "  font-size: 85%;",
                "}",
                ".block .run-sub {",
                "  vertical-align: sub;",
                "  font-size: 85%;",
                "}",
                ".block .run-smallcaps {",
                "  font-variant: small-caps;",
                "}",
                ".block .run-allcaps {",
                "  text-transform: uppercase;",
                "}",
                ".block .inline-image {",
                "  display: inline-block;",
                "  color: #999;",
                "  font-size: 0.85em;",
                "  padding: 0 0.2em;",
                "}",
                ".block .block-placeholder {",
                "  display: flex;",
                "  align-items: center;",
                "  justify-content: center;",
                "  width: 100%;",
                "  height: 100%;",
                "  font-size: clamp(0.6rem, 1.2vw, 0.9rem);",
                "  color: #777;",
                "  text-align: center;",
                "  border: 1px dashed rgba(0, 0, 0, 0.1);",
                "  background: rgba(0, 0, 0, 0.02);",
                "}",
                ".overlay {",
                "  position: absolute;",
                "  pointer-events: none;",
                "}",
                ".overlay img {",
                "  width: 100%;",
                "  height: 100%;",
                "  object-fit: contain;",
                "}",
                ".image-block img {",
                "  max-width: 100%;",
                "  height: auto;",
                "  display: block;",
                "}",
                ".cell-image {",
                "  display: block;",
                "  text-align: center;",
                "}",
                ".cell-image img {",
                "  max-width: 100%;",
                "  height: auto;",
                "  display: inline-block;",
                "}",
                ".paragraph.list-paragraph {",
                "  position: relative;",
                "  padding-left: 0;",
                "  display: block;",
                "  overflow: visible;",
                "}",
                ".paragraph.list-paragraph .list-marker {",
                "  position: absolute;",
                "  top: 0;",
                "  left: 0;",
                "  display: inline-block;",
                "  text-align: right;",
                "  white-space: pre;",
                "  pointer-events: none;",
                "}",
                ".paragraph.list-paragraph .list-marker-empty {",
                "  visibility: hidden;",
                "}",
                ".paragraph.list-paragraph .list-content {",
                "  margin: 0;",
                "}",
                ".paragraph-between-line {",
                "  position: absolute;",
                "  left: 0;",
                "  right: 0;",
                "  border-top: 1px solid rgba(0, 0, 0, 0.2);",
                "  pointer-events: none;",
                "}",
                ".block a.text-run {",
                "  color: inherit;",
                "  text-decoration: none;",
                "}",
                ".block a.text-run:hover {",
                "  text-decoration: underline;",
                "}",
                ".block .generic-block {",
                "  display: flex;",
                "  flex-direction: column;",
                "  gap: 0.35em;",
                "  width: 100%;",
                "  height: 100%;",
                "}",
                ".block .table-container {",
                "  width: 100%;",
                "  height: 100%;",
                "  overflow: hidden;",
                "  position: relative;",
                "}",
                ".block .table-block {",
                "  width: 100%;",
                "  border-collapse: collapse;",
                "  table-layout: fixed;",
                "  font-size: clamp(0.6rem, 1.1vw, 0.95rem);",
                "  color: #222;",
                "}",
                ".block .table-block td,",
                ".block .table-block th {",
                "  border: 1px solid rgba(0, 0, 0, 0.15);",
                "  padding: 0.25em 0.4em;",
                "  vertical-align: top;",
                "  background: rgba(255, 255, 255, 0.95);",
                "}",
                ".block .table-block td:empty::after {",
                "  content: '\\00a0';",
                "}",
                ".block .table-block img {",
                "  max-width: 100%;",
                "  height: auto;",
                "  display: block;",
                "}",
                ".block .cell-image {",
                "  max-width: 100%;",
                "}",
                ".block .inline-image img {",
                "  max-width: 100%;",
                "  height: auto;",
                "  display: inline-block;",
                "}",
                ".block .table-border {",
                "  position: absolute;",
                "  left: 0;",
                "  right: 0;",
                "  pointer-events: none;",
                "}",
            ]
        )

    def _default_document_script(self) -> str:
        script = textwrap.dedent(
            """
            (function () {
              const EVENT_READY = "doclayout:ready";
              const EVENT_REFRESH = "doclayout:refresh";
              const CSS_DPI = 96;
              const DEFAULT_PAGE_GAP = 32;
              const state = {
                root: null,
                metrics: [],
                pages: [],
                totalPages: 0,
                totalHeight: 0,
                pageHeightPx: 0,
                marginTop: 0,
                marginBottom: 0,
                isApplying: false,
                lastPlanSignature: "",
              };
              let mutationObserver = null;
              let resizeObserver = null;

              function parseNumber(value) {
                if (value === undefined || value === null || value === "") {
                  return 0;
                }
                const numeric = Number.parseFloat(String(value));
                return Number.isFinite(numeric) ? numeric : 0;
              }

              function resolveMargins(root) {
                return {
                  top: parseNumber(root.dataset.marginTopPx),
                  right: parseNumber(root.dataset.marginRightPx),
                  bottom: parseNumber(root.dataset.marginBottomPx),
                  left: parseNumber(root.dataset.marginLeftPx),
                };
              }

              function ensureRootVariables(root, margins, pageHeightPx) {
                root.style.setProperty("--doc-page-margin-top", `${margins.top.toFixed(2)}px`);
                root.style.setProperty("--doc-page-margin-right", `${margins.right.toFixed(2)}px`);
                root.style.setProperty("--doc-page-margin-bottom", `${margins.bottom.toFixed(2)}px`);
                root.style.setProperty("--doc-page-margin-left", `${margins.left.toFixed(2)}px`);
                if (!root.style.getPropertyValue("--doc-page-gap")) {
                  root.style.setProperty("--doc-page-gap", `${DEFAULT_PAGE_GAP}px`);
                }
                if (pageHeightPx > 0) {
                  root.style.setProperty("--doc-page-height", `${pageHeightPx.toFixed(2)}px`);
                } else {
                  root.style.removeProperty("--doc-page-height");
                }
              }

              function resolvePageHeightPx(root) {
                const pageHeightPx = parseNumber(root.dataset.pageHeightPx);
                if (pageHeightPx > 0) {
                  return pageHeightPx;
                }
                const pageHeightPt = parseNumber(root.dataset.pageHeightPt);
                if (pageHeightPt > 0) {
                  return (pageHeightPt * CSS_DPI) / 72;
                }
                return 0;
              }

              function resolvePageWidthPx(root) {
                const pageWidthPx = parseNumber(root.dataset.pageWidthPx);
                if (pageWidthPx > 0) {
                  return pageWidthPx;
                }
                const pageWidthPt = parseNumber(root.dataset.pageWidthPt);
                if (pageWidthPt > 0) {
                  return (pageWidthPt * CSS_DPI) / 72;
                }
                return 0;
              }

              function ensureObservers(root) {
                if (!mutationObserver) {
                  mutationObserver = new MutationObserver(() => scheduleCompute());
                }
                mutationObserver.disconnect();
                mutationObserver.observe(root, {
                  childList: true,
                  characterData: true,
                  subtree: true,
                });
                if (!resizeObserver && typeof ResizeObserver === "function") {
                  resizeObserver = new ResizeObserver(() => scheduleCompute());
                }
                if (resizeObserver) {
                  resizeObserver.disconnect();
                  resizeObserver.observe(root);
                }
              }

              function applyDecorations(root) {
                const sectionSelectors = [".document-body", ".document-header", ".document-footer"];
                const sides = ["top", "right", "bottom", "left"];
                const containerCache = new Map();
                const pad = 2;

                function ensureDecorLayer(block) {
                  let layer = block.querySelector(":scope > .doc-block-decor");
                  if (!layer) {
                    layer = document.createElement("div");
                    layer.className = "doc-block-decor";
                    layer.setAttribute("aria-hidden", "true");
                    block.insertBefore(layer, block.firstChild);
                  }
                  return layer;
                }

                function resolveContainer(block) {
                  for (const selector of sectionSelectors) {
                    const container = block.closest(selector);
                    if (container) {
                      return container;
                    }
                  }
                  return root;
                }

                const blocks = Array.from(root.querySelectorAll(".document-block"));

                blocks.forEach((block) => {
                  const payload = block.dataset.decor;
                  let data = null;
                  if (payload) {
                    try {
                      data = JSON.parse(payload);
                    } catch (error) {
                      data = null;
                    }
                  }

                  if (!data) {
                    const existing = block.querySelector(":scope > .doc-block-decor");
                    if (existing) {
                      existing.remove();
                    }
                    block.style.removeProperty("background-color");
                    block.style.removeProperty("box-shadow");
                    sides.forEach((side) => block.style.removeProperty(`border-${side}`));
                    return;
                  }

                  block.style.position = block.style.position || "relative";
                  if (!block.style.zIndex) {
                    block.style.zIndex = "0";
                  }
                  block.style.removeProperty("background-color");
                  block.style.removeProperty("box-shadow");
                  sides.forEach((side) => block.style.removeProperty(`border-${side}`));

                  const container = resolveContainer(block);
                  if (!container) {
                    return;
                  }
                  let cached = containerCache.get(container);
                  if (!cached) {
                    const rect = container.getBoundingClientRect();
                    const computed = window.getComputedStyle(container);
                    const paddingLeft = Number.parseFloat(computed.paddingLeft) || 0;
                    const paddingRight = Number.parseFloat(computed.paddingRight) || 0;
                    cached = {
                      rect,
                      contentLeft: rect.left + paddingLeft,
                      contentRight: rect.right - paddingRight,
                    };
                    containerCache.set(container, cached);
                  }
                  const blockRect = block.getBoundingClientRect();
                  const offsetLeft = blockRect.left - cached.contentLeft;
                  const offsetRight = cached.contentRight - blockRect.right;

                  const layer = ensureDecorLayer(block);
                  layer.style.position = "absolute";
                  layer.style.left = `${-(offsetLeft + pad)}px`;
                  layer.style.right = `${-(offsetRight + pad)}px`;
                  layer.style.removeProperty("width");
                  layer.style.top = `${-pad}px`;
                  layer.style.bottom = `${-pad}px`;
                  layer.style.pointerEvents = "none";
                  layer.style.backgroundColor = data.backgroundColor || "transparent";
                  layer.style.zIndex = "-1";

                  if (data.shadow && data.shadow.color) {
                    const offsetX = Number.isFinite(data.shadow.offsetX) ? data.shadow.offsetX : 0;
                    const offsetY = Number.isFinite(data.shadow.offsetY) ? data.shadow.offsetY : 0;
                    const blur = Number.isFinite(data.shadow.blur) ? Math.max(data.shadow.blur, 0) : 0;
                    layer.style.boxShadow = `${offsetX.toFixed(2)}px ${offsetY.toFixed(2)}px ${blur.toFixed(2)}px ${data.shadow.color}`;
                  } else {
                    layer.style.removeProperty("box-shadow");
                  }

                  if (data.borders && typeof data.borders === "object") {
                    sides.forEach((side) => {
                      const spec = data.borders[side];
                      const cssProperty = `border-${side}`;
                      if (spec && Number.isFinite(spec.width) && spec.width > 0) {
                        const width = Math.max(spec.width, 0);
                        const style = typeof spec.style === "string" && spec.style ? spec.style : "solid";
                        const color = typeof spec.color === "string" && spec.color ? spec.color : "#000000";
                        layer.style.setProperty(cssProperty, `${width.toFixed(2)}px ${style} ${color}`);
                      } else {
                        layer.style.removeProperty(cssProperty);
                      }
                    });
                  } else {
                    sides.forEach((side) => layer.style.removeProperty(`border-${side}`));
                  }
                });
              }

              function ensureGuides(root) {
                let guides = root.querySelector(".doc-layout-guides");
                if (!guides) {
                  guides = document.createElement("div");
                  guides.className = "doc-layout-guides";
                  root.appendChild(guides);
                }
                return guides;
              }

              function ensurePagesContainer(root) {
                let container = root.querySelector(".doc-pages");
                if (!container) {
                  container = document.createElement("div");
                  container.className = "doc-pages";
                  root.insertBefore(container, root.firstChild);
                }
                return container;
              }

              function collectBlockGroups(metrics) {
                const groups = new Map();
                metrics.forEach((entry) => {
                  const element = entry.element;
                  if (groups.has(element)) {
                    return;
                  }
                  const nodes = [element];
                  let sibling = element.nextElementSibling;
                  while (sibling && !sibling.classList.contains("document-block")) {
                    nodes.push(sibling);
                    sibling = sibling.nextElementSibling;
                  }
                  groups.set(element, nodes);
                });
                return groups;
              }

              function collectMetrics(root, layoutTopOffset) {
                const rootRect = root.getBoundingClientRect();
                return Array.from(root.querySelectorAll(".document-block")).map((block, index) => {
                  const rect = block.getBoundingClientRect();
                  const layoutTop = Math.max(0, rect.top - rootRect.top - layoutTopOffset);
                  if (!block.dataset.blockUid) {
                    block.dataset.blockUid = String(index);
                  }
                  return {
                    element: block,
                    layoutTop,
                    height: rect.height,
                    width: rect.width,
                    offsetLeft: rect.left - rootRect.left,
                  };
                });
              }

              function buildPages(metrics, pageHeightPx) {
                const pagesMap = new Map();
                let totalHeight = 0;
                metrics.forEach((entry) => {
                  totalHeight = Math.max(totalHeight, entry.layoutTop + entry.height);
                  let pageIndex = parseNumber(entry.element.dataset.page);
                  if (pageHeightPx > 0) {
                    pageIndex = Math.max(1, Math.floor(entry.layoutTop / pageHeightPx) + 1);
                  } else {
                    pageIndex = pageIndex > 0 ? pageIndex : 1;
                  }
                  entry.targetPage = pageIndex;
                  if (!pagesMap.has(pageIndex)) {
                    pagesMap.set(pageIndex, []);
                  }
                  pagesMap.get(pageIndex).push(entry);
                });
                const pages = Array.from(pagesMap.entries()).sort((a, b) => a[0] - b[0]);
                const totalPages = pages.length || 1;
                return { pages, totalPages, totalHeight };
              }

              function planSignature(pages) {
                return pages
                  .map(([pageIndex, entries]) => `${pageIndex}:${entries.map((entry) => entry.element.dataset.blockUid || "").join(",")}`)
                  .join("|");
              }

              function applyPagination(root, plan) {
                const pagesContainer = ensurePagesContainer(root);
                const guides = ensureGuides(root);
                const fragment = document.createDocumentFragment();
                const blockGroups = collectBlockGroups(plan.metrics);

                plan.pages.forEach(([pageIndex, entries]) => {
                  const pageEl = document.createElement("section");
                  pageEl.className = "doc-page";
                  pageEl.dataset.page = String(pageIndex);
                  if (plan.pageHeightPx > 0) {
                    pageEl.style.minHeight = `${plan.pageHeightPx.toFixed(2)}px`;
                  } else {
                    pageEl.style.removeProperty("min-height");
                  }
                  const bodyEl = document.createElement("div");
                  bodyEl.className = "doc-page-body";
                  pageEl.appendChild(bodyEl);

                  entries
                    .slice()
                    .sort((a, b) => a.layoutTop - b.layoutTop)
                    .forEach((entry) => {
                      const group = blockGroups.get(entry.element) || [entry.element];
                      group.forEach((node) => {
                        bodyEl.appendChild(node);
                      });
                      entry.element.dataset.page = String(pageIndex);
                    });

                  fragment.appendChild(pageEl);
                });

                pagesContainer.textContent = "";
                pagesContainer.appendChild(fragment);
                if (guides) {
                  root.appendChild(guides);
                }
              }

              function renderPageGuides(root, layout) {
                const guides = ensureGuides(root);
                guides.textContent = "";
                if (layout.pageHeightPx <= 0) {
                  return;
                }
                for (let pageIndex = 1; pageIndex < layout.totalPages; pageIndex += 1) {
                  const guide = document.createElement("div");
                  guide.className = "doc-page-guide";
                  const top = layout.marginTop + layout.pageHeightPx * pageIndex;
                  guide.style.top = `${top.toFixed(2)}px`;
                  guide.dataset.page = String(pageIndex + 1);
                  guides.appendChild(guide);
                }
              }

              function updateFieldPlaceholders(root, layout) {
                const totalPages = layout.totalPages || 1;
                root.dataset.totalPages = String(totalPages);
                root.querySelectorAll('[data-field-kind="NUMPAGES"]').forEach((node) => {
                  node.textContent = String(totalPages);
                });
                root.querySelectorAll('[data-field-kind="PAGE"]').forEach((node) => {
                  const block = node.closest(".document-block");
                  if (!block || !block.dataset.page) {
                    return;
                  }
                  node.textContent = block.dataset.page;
                });
              }

              function computeLayout() {
                if (state.isApplying) {
                  return;
                }
                const root = document.querySelector(".document-root");
                if (!root) {
                  return;
                }

                state.isApplying = true;
                try {
                  ensureObservers(root);
                  const layoutMode = root.dataset.layoutMode || "paginate";
                  const shouldPaginate = layoutMode === "paginate";
                  const margins = resolveMargins(root);
                  const pageHeightPxRaw = resolvePageHeightPx(root);
                  const pageHeightPx = shouldPaginate ? pageHeightPxRaw : 0;
                  ensureRootVariables(root, margins, pageHeightPxRaw);
                  const pageWidthPxRaw = resolvePageWidthPx(root);
                  const rootRect = root.getBoundingClientRect();
                  const pageWidthScale =
                    pageWidthPxRaw > 0 && rootRect.width > 0
                      ? rootRect.width / pageWidthPxRaw
                      : 1;
                  root.style.setProperty("--doc-font-scale", pageWidthScale.toFixed(6));

                  if (!shouldPaginate) {
                    const pagesContainer = root.querySelector(".doc-pages");
                    if (pagesContainer) {
                      const fragment = document.createDocumentFragment();
                      while (pagesContainer.firstChild) {
                        fragment.appendChild(pagesContainer.firstChild);
                      }
                      pagesContainer.replaceWith(fragment);
                    }
                    root.querySelectorAll(".document-block").forEach((block) => {
                      block.dataset.page = "1";
                    });

                    const metrics = collectMetrics(root, margins.top);
                    const pages = buildPages(metrics, 0);
                    const signature = planSignature(pages.pages);

                    state.root = root;
                    state.metrics = metrics;
                    state.pages = pages.pages;
                    state.totalPages = pages.totalPages;
                    state.totalHeight = pages.totalHeight;
                    state.pageHeightPx = 0;
                    state.marginTop = margins.top;
                    state.marginBottom = margins.bottom;
                    state.lastPlanSignature = signature;

                    root.dataset.layoutHeight = pages.totalHeight.toFixed(2);
                    root.dataset.pageCount = String(pages.totalPages);

                    applyDecorations(root);

                    const guides = root.querySelector(".doc-layout-guides");
                    if (guides) {
                      guides.textContent = "";
                      if (guides.parentElement !== root) {
                        root.appendChild(guides);
                      }
                    }

                    updateFieldPlaceholders(root, {
                      totalPages: pages.totalPages,
                    });

                    document.dispatchEvent(
                      new CustomEvent(EVENT_READY, {
                        detail: {
                          root,
                          metrics,
                          pages: pages.pages,
                          totalPages: pages.totalPages,
                          totalHeight: pages.totalHeight,
                          pageHeightPx: 0,
                          margins,
                        },
                      })
                    );
                    return;
                  }

                  const metricsBefore = collectMetrics(root, margins.top);
                  const pagesBefore = buildPages(metricsBefore, pageHeightPx);
                  const signatureBefore = planSignature(pagesBefore.pages);

                  if (signatureBefore !== state.lastPlanSignature) {
                    applyPagination(root, {
                      metrics: metricsBefore,
                      pages: pagesBefore.pages,
                      pageHeightPx,
                    });
                  }

                  const metricsAfter = collectMetrics(root, margins.top);
                  const pagesAfter = buildPages(metricsAfter, pageHeightPx);
                  const signatureAfter = planSignature(pagesAfter.pages);

                  state.root = root;
                  state.metrics = metricsAfter;
                  state.pages = pagesAfter.pages;
                  state.totalPages = pagesAfter.totalPages;
                  state.totalHeight = pagesAfter.totalHeight;
                  state.pageHeightPx = pageHeightPx;
                  state.marginTop = margins.top;
                  state.marginBottom = margins.bottom;
                  state.lastPlanSignature = signatureAfter;

                  root.dataset.layoutHeight = pagesAfter.totalHeight.toFixed(2);
                  root.dataset.pageCount = String(pagesAfter.totalPages);

                  applyDecorations(root);

                  renderPageGuides(root, {
                    pageHeightPx,
                    totalPages: pagesAfter.totalPages,
                    marginTop: margins.top,
                  });
                  updateFieldPlaceholders(root, {
                    totalPages: pagesAfter.totalPages,
                  });

                  document.dispatchEvent(
                    new CustomEvent(EVENT_READY, {
                      detail: {
                        root,
                        metrics: metricsAfter,
                        pages: pagesAfter.pages,
                        totalPages: pagesAfter.totalPages,
                        totalHeight: pagesAfter.totalHeight,
                        pageHeightPx,
                        margins,
                      },
                    })
                  );
                } finally {
                  state.isApplying = false;
                }
              }

              function scheduleCompute() {
                if (state.isApplying) {
                  return;
                }
                if (scheduleCompute._raf) {
                  return;
                }
                scheduleCompute._raf = requestAnimationFrame(() => {
                  scheduleCompute._raf = null;
                  computeLayout();
                });
              }

              if (!window.DocLayout) {
                window.DocLayout = {
                  refresh: () => scheduleCompute(),
                  getState: () => ({ ...state }),
                  getMetrics: () => state.metrics.slice(),
                };
              } else {
                window.DocLayout.refresh = () => scheduleCompute();
                window.DocLayout.getState = () => ({ ...state });
                window.DocLayout.getMetrics = () => state.metrics.slice();
              }

              if (document.readyState === "loading") {
                document.addEventListener(
                  "DOMContentLoaded",
                  () => {
                    scheduleCompute();
                  },
                  { once: true }
                );
              } else {
                scheduleCompute();
              }

              window.addEventListener("resize", scheduleCompute);
              document.addEventListener(EVENT_REFRESH, scheduleCompute);
            })();
            """
        ).strip()
        return script

    def _render_block_content(self, block: LayoutBlock) -> str:
        """
        Renderuje treść bloku zależnie od typu payloadu.
        """
        raw: Optional[Dict[str, object]] = None
        if isinstance(block.content, BlockContent):
            raw = block.content.raw
            html = self._render_payload(
                block.content.payload,
                raw=raw,
                default_label=block.block_type,
            )
            if html:
                return html
            if block.block_type in {"header", "footer"}:
                return ""
        elif isinstance(block.content, dict):
            raw = block.content  # pragma: no cover - legacy fallback

        if block.block_type == "decorator":
            # Dekoratory używają stylów (background/border), więc nie wymagają treści
            return ""

        label = self._extract_label(raw, block.block_type)
        return self._render_placeholder(label, kind="unknown")

    def _collect_overlays(
        self,
        context: _BlockRenderContext,
    ) -> list[str]:
        overlays_html: list[str] = []

        block = context.block
        payload = None
        if isinstance(block.content, BlockContent):
            payload = block.content.payload
        elif hasattr(block.content, "payload"):
            payload = getattr(block.content, "payload", None)

        if payload is None:
            return overlays_html

        seen: set[int] = set()
        seen_signatures: set[tuple[Any, ...]] = set()

        for overlay in self._iter_overlays(payload):
            try:
                overlay_id = id(overlay)
            except Exception:
                overlay_id = None
            if overlay_id is not None and overlay_id in seen:
                continue
            if overlay_id is not None:
                seen.add(overlay_id)
            signature = self._overlay_signature(overlay)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            rendered = self._render_overlay(overlay, context)
            if rendered:
                overlays_html.append(rendered)
        return overlays_html

    def _overlay_top_in_page(
        self,
        overlay: OverlayBox,
        context: _BlockRenderContext,
    ) -> float:
        frame = overlay.frame
        raw_top_in_page = (
            context.page_height
            - float(getattr(frame, "y", 0.0))
            - float(getattr(frame, "height", 0.0))
        )
        top_in_page = (
            raw_top_in_page
            if context.section_role == "footer"
            else max(raw_top_in_page, 0.0)
        )
        _, _, anchor_y, anchor_y_rel = self._extract_overlay_anchor(overlay)
        if anchor_y is not None:
            frame_height = float(getattr(frame, "height", 0.0))
            resolved_top = self._resolve_overlay_vertical_position(anchor_y, anchor_y_rel, context, frame_height)
            top_in_page = max(min(resolved_top, context.page_height), 0.0)
        return top_in_page

    def _render_between_lines(self, block: LayoutBlock) -> list[str]:
        raw: Optional[Dict[str, Any]] = None
        if isinstance(block.content, BlockContent):
            raw = block.content.raw
        elif isinstance(block.content, dict):
            raw = block.content

        if not isinstance(raw, dict):
            return []

        entries = raw.get("between_lines")
        if not isinstance(entries, list) or not entries:
            return []

        block_height = float(block.frame.height or 0.0)
        if block_height <= 0.0:
            return []

        block_bottom = float(block.frame.y or 0.0)
        results: list[str] = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            spec = entry.get("spec")
            if not isinstance(spec, dict):
                continue
            y_value = self._safe_float(entry.get("y"))
            if y_value <= 0.0:
                continue
            border_width_px = self._points_to_css_float(spec.get("width")) or 0.5
            border_style = self._normalize_border_style(spec.get("style"))
            border_color = spec.get("color") or "#000000"

            offset_from_bottom = y_value - block_bottom
            offset_from_bottom = max(0.0, min(offset_from_bottom, block_height))
            offset_from_top_pt = block_height - offset_from_bottom
            offset_from_top_px = self._points_to_css_float(offset_from_top_pt)
            if offset_from_top_px is None:
                continue

            style_parts = [
                "position: absolute",
                "left: 0",
                "right: 0",
                f"top: {offset_from_top_px:.2f}px",
                f"border-top-width: {border_width_px:.2f}px",
                f"border-top-style: {border_style}",
                f"border-top-color: {border_color}",
            ]
            results.append(
                f'<div class="paragraph-between-line" style="{"; ".join(style_parts)}"></div>'
            )

        return results

    def _extract_block_style(self, block: LayoutBlock) -> Optional[Dict[str, Any]]:
        if isinstance(block.content, BlockContent):
            raw = block.content.raw
            if isinstance(raw, dict):
                style = raw.get("style")
            else:
                style = None
        elif isinstance(block.content, dict):
            style = block.content.get("style")
        else:
            style = None
        return style if isinstance(style, dict) else None

    def _extract_block_decorations(self, block: LayoutBlock) -> Optional[Dict[str, Any]]:
        style = self._extract_block_style(block)
        return self._style_to_decoration(style)

    def _style_dict_to_css(self, style: Optional[Any]) -> str:
        if isinstance(style, BoxStyle):
            style = self._box_style_to_style_dict(style)

        if not style:
            return ""

        if not isinstance(style, dict):
            return ""

        style_map = dict(style)
        css_parts: list[str] = []

        background = (
            style_map.get("background")
            or style_map.get("background_color")
            or style_map.get("fill")
            or style_map.get("fill_color")
            or (style_map.get("shading") or {}).get("fill")
        )
        if background:
            css_color = self._color_to_css(background)
            if css_color:
                css_parts.append(f"background-color: {css_color}")

        borders = style_map.get("borders") or {}
        for side in ("top", "right", "bottom", "left"):
            spec = borders.get(side)
            if isinstance(spec, dict):
                try:
                    width = float(spec.get("width", 0.5))
                except (TypeError, ValueError):
                    width = 0.5
                color_value = spec.get("color", "#000000")
                color = self._color_to_css(color_value) or "#000000"
                border_style = self._normalize_border_style(spec.get("style"))
                css_parts.append(f"border-{side}: {max(width, 0.1):.2f}px {border_style} {color}")

        shadow = style_map.get("shadow")
        if isinstance(shadow, dict):
            dx = float(shadow.get("offset_x", 2))
            dy = float(shadow.get("offset_y", -2))
            blur = float(shadow.get("blur", 4))
            color = self._color_to_css(shadow.get("color")) or "rgba(0,0,0,0.25)"
            css_parts.append(f"box-shadow: {dx}px {dy}px {blur}px {color}")

        padding = style_map.get("padding")
        if isinstance(padding, (list, tuple)) and len(padding) == 4:
            top, right, bottom, left = (float(v) for v in padding)
            css_parts.append(
                "padding: "
                f"{max(top, 0):.2f}px {max(right, 0):.2f}px "
                f"{max(bottom, 0):.2f}px {max(left, 0):.2f}px"
            )

        font_dict = style_map.get("font")
        if isinstance(font_dict, dict):
            style_map.setdefault("font_name", font_dict.get("name") or font_dict.get("family"))
            style_map.setdefault("font_family", font_dict.get("family"))
            style_map.setdefault("font_size", font_dict.get("size"))
            style_map.setdefault("color", font_dict.get("color"))

        font_family = style_map.get("font_family") or style_map.get("font_name")
        if isinstance(font_family, str) and font_family.strip():
            css_parts.append(self._format_font_family(font_family.strip()))

        font_size = style_map.get("font_size")
        font_size_value = self._coerce_font_size(font_size)
        if font_size_value:
            css_parts.append(self._format_font_size_rule(font_size_value))

        font_color = self._color_to_css(style_map.get("color") or style_map.get("font_color"))
        if font_color:
            css_parts.append(f"color: {font_color}")

        text_align = style_map.get("text_align") or style_map.get("alignment") or style_map.get("horizontal_align")
        if isinstance(text_align, str) and text_align:
            css_parts.append(f"text-align: {text_align}")

        opacity = style_map.get("opacity")
        if opacity not in (None, "", False):
            try:
                opacity_val = float(opacity)
                css_parts.append(f"opacity: {max(0.0, min(opacity_val, 1.0)):.3f}")
            except (TypeError, ValueError):
                pass

        return "; ".join(css_parts)

    def _style_to_decoration(self, style: Optional[Any]) -> Optional[Dict[str, Any]]:
        if isinstance(style, BoxStyle):
            style = self._box_style_to_style_dict(style)

        if not isinstance(style, dict):
            return None

        decoration: Dict[str, Any] = {}

        def _normalize_width(value: Any) -> Optional[float]:
            px = self._points_to_css_float(value)
            if px is None:
                try:
                    px = float(value)
                except (TypeError, ValueError):
                    return None
            return max(px, 0.0)

        background = (
            style.get("background")
            or style.get("background_color")
            or style.get("fill")
            or style.get("fill_color")
        )
        shading = style.get("shading")
        if not background and isinstance(shading, dict):
            background = shading.get("fill") or shading.get("color")
        if background:
            css_background = self._color_to_css(background)
            if css_background:
                decoration["backgroundColor"] = css_background

        borders = style.get("borders")
        if isinstance(borders, dict):
            border_spec: Dict[str, Dict[str, Any]] = {}
            for side in ("top", "right", "bottom", "left"):
                side_spec = borders.get(side)
                if not isinstance(side_spec, dict):
                    continue
                width = _normalize_width(side_spec.get("width", 0.0))
                if width is None or width <= 0.0:
                    continue
                color_value = (
                    side_spec.get("color")
                    or side_spec.get("color_value")
                    or side_spec.get("border_color")
                )
                color = self._color_to_css(color_value) or "#000000"
                border_style = self._normalize_border_style(side_spec.get("style"))
                border_spec[side] = {
                    "width": width,
                    "style": border_style,
                    "color": color,
                }
            if border_spec:
                decoration["borders"] = border_spec

        shadow = style.get("shadow")
        if isinstance(shadow, dict):
            dx = self._points_to_css_float(shadow.get("offset_x"))
            if dx is None:
                dx = self._safe_float(shadow.get("offset_x"))
            dy = self._points_to_css_float(shadow.get("offset_y"))
            if dy is None:
                dy = self._safe_float(shadow.get("offset_y"))
            blur = self._points_to_css_float(shadow.get("blur"))
            if blur is None:
                blur = self._safe_float(shadow.get("blur"))
            color = self._color_to_css(shadow.get("color"))
            if color:
                decoration["shadow"] = {
                    "offsetX": dx or 0.0,
                    "offsetY": dy or 0.0,
                    "blur": max(blur or 0.0, 0.0),
                    "color": color,
                }

        if not decoration:
            return None
        return decoration

    def _box_style_to_style_dict(self, box_style: BoxStyle) -> Dict[str, Any]:
        style_dict: Dict[str, Any] = {}

        if box_style.background:
            bg_color = self._color_to_css(box_style.background)
            if bg_color:
                style_dict["background"] = bg_color

        if box_style.borders:
            borders: Dict[str, Dict[str, Any]] = {}
            for border in box_style.borders:
                color = self._color_to_css(border.color) or "#000000"
                borders[border.side] = {
                    "width": border.width,
                    "style": border.style,
                    "color": color,
                }
            style_dict["borders"] = borders

        if box_style.padding:
            style_dict["padding"] = box_style.padding

        return style_dict

    def _color_to_css(self, value: Any) -> Optional[str]:
        if value in (None, "", False):
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, ColorSpec):
            r = max(0, min(255, int(round(value.r * 255))))
            g = max(0, min(255, int(round(value.g * 255))))
            b = max(0, min(255, int(round(value.b * 255))))
            alpha = max(0.0, min(1.0, float(value.a)))
            if alpha < 1.0 - 1e-6:
                return f"rgba({r}, {g}, {b}, {alpha:.3f})"
            return f"#{r:02X}{g:02X}{b:02X}"
        if isinstance(value, dict):
            try:
                r = value.get("r")
                g = value.get("g")
                b = value.get("b")
                a = value.get("a", value.get("alpha", 1.0))
                if None not in (r, g, b):
                    color_spec = ColorSpec(float(r), float(g), float(b), float(a) if a is not None else 1.0)
                    return self._color_to_css(color_spec)
            except Exception:
                return None
        if isinstance(value, (list, tuple)) and len(value) in (3, 4):
            try:
                r, g, b, *rest = value
                a = rest[0] if rest else 1.0
                color_spec = ColorSpec(float(r), float(g), float(b), float(a))
                return self._color_to_css(color_spec)
            except Exception:
                return None
        return None

    def _merge_style_segments(self, segments: Iterable[Optional[str]]) -> str:
        order: list[str] = []
        values: Dict[str, tuple[str, str]] = {}
        for segment in segments:
            if not segment:
                continue
            for part in segment.split(";"):
                if ":" not in part:
                    continue
                name, value = part.split(":", 1)
                prop_name = name.strip()
                prop_value = value.strip()
                if not prop_name:
                    continue
                key = prop_name.lower()
                values[key] = (prop_name, prop_value)
                if key not in order:
                    order.append(key)
        return "; ".join(f"{values[key][0]}: {values[key][1]}" for key in order)

    @staticmethod
    def _normalize_border_style(value: Optional[str]) -> str:
        mapping = {
            "single": "solid",
            "solid": "solid",
            "dashed": "dashed",
            "dash": "dashed",
            "dot": "dotted",
            "dotted": "dotted",
            "double": "double",
        }
        return mapping.get(str(value).lower(), "solid")

    def _overlay_signature(self, overlay: OverlayBox) -> tuple[Any, ...]:
        payload = overlay.payload if isinstance(overlay.payload, dict) else {}
        image_info = {}
        if isinstance(payload, dict):
            if isinstance(payload.get("image"), dict):
                image_info = payload["image"]
            elif isinstance(payload.get("source"), dict):
                image_info = payload["source"]

        path = ""
        rel_id = None
        if isinstance(image_info, dict):
            path = image_info.get("path") or image_info.get("image_path") or image_info.get("src") or ""
            rel_id = image_info.get("relationship_id") or image_info.get("rel_id")

        return (
            overlay.kind,
            round(overlay.frame.x, 4),
            round(overlay.frame.y, 4),
            round(overlay.frame.width, 4),
            round(overlay.frame.height, 4),
            path,
            rel_id,
        )

    def _render_payload(
        self,
        payload: Any,
        *,
        raw: Optional[Dict[str, object]] = None,
        default_label: str = "block",
    ) -> str:
        if payload is None:
            return ""

        if isinstance(payload, ParagraphLayout):
            marker = raw.get("marker") if isinstance(raw, dict) else None
            return self._render_paragraph_layout(payload, marker=marker, raw=raw)
        if isinstance(payload, TableLayout):
            return self._render_table_layout(payload, raw=raw, default_label=default_label)
        if isinstance(payload, ImageLayout):
            return self._render_image_layout(payload, raw=raw)
        if isinstance(payload, GenericLayout):
            return self._render_generic_layout(payload, raw=raw, default_label=default_label)
        if isinstance(payload, list):
            parts = [
                self._render_payload(item, raw=raw, default_label=default_label)
                for item in payload
            ]
            parts = [item for item in parts if item]
            if parts:
                return '<div class="generic-block">' + "\n".join(parts) + "</div>"
            return ""

        return ""

    def _iter_overlays(self, payload: Any) -> Iterable[OverlayBox]:
        if payload is None:
            return []

        stack = [payload]
        collected: list[OverlayBox] = []

        while stack:
            current = stack.pop()
            if isinstance(current, OverlayBox):
                collected.append(current)
                continue

            if isinstance(current, ParagraphLayout):
                if current.overlays:
                    collected.extend(current.overlays)
            elif isinstance(current, GenericLayout):
                if current.overlays:
                    collected.extend(current.overlays)
                nested = current.data.get("layout_payload") or current.data.get("_layout_payload")
                if nested:
                    stack.append(nested)
                rows = current.data.get("rows")
                if rows:
                    stack.extend(rows)
            elif isinstance(current, TableLayout):
                stack.extend(current.rows)
            elif hasattr(current, "cells"):
                try:
                    stack.extend(getattr(current, "cells") or [])
                except Exception:
                    pass
            elif isinstance(current, TableCellLayout):
                stack.extend(current.blocks)
            elif isinstance(current, list):
                stack.extend(current)
            elif isinstance(current, dict):
                if "layout_payload" in current:
                    stack.append(current["layout_payload"])
                if "_layout_payload" in current:
                    stack.append(current["_layout_payload"])
        return collected

    def _render_paragraph_layout(
        self,
        layout: ParagraphLayout,
        *,
        marker: Optional[Dict[str, Any]] = None,
        raw: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not layout.lines:
            return '<div class="paragraph"><div class="paragraph-line">&nbsp;</div></div>'

        list_meta = self._extract_list_meta(raw)
        indent_info = self._extract_indent_info(layout, raw, marker)
        paragraph_alignment = self._extract_paragraph_alignment(layout, raw)

        paragraph_font_name, paragraph_font_size = self._resolve_paragraph_typography(layout, raw)
        run_font_sizes: set[float] = set()
        for line in layout.lines:
            for item in getattr(line, "items", []):
                if getattr(item, "kind", None) != "text_run":
                    continue
                data = item.data or {}
                style_info = data.get("style") or {}
                font_size_value = self._coerce_font_size(style_info.get("font_size") or data.get("font_size"))
                if font_size_value:
                    run_font_sizes.add(round(font_size_value, 4))

        if run_font_sizes:
            if len(run_font_sizes) == 1:
                paragraph_font_size = next(iter(run_font_sizes))
            else:
                paragraph_font_size = None

        paragraph_classes = ["paragraph"]
        paragraph_styles: list[str] = []
        paragraph_attrs: list[str] = ['data-role="paragraph"']

        paragraph_id: Optional[str] = None
        if isinstance(layout.metadata, dict):
            paragraph_id = layout.metadata.get("source_id") or layout.metadata.get("id")
        if not paragraph_id and isinstance(raw, dict):
            paragraph_id = raw.get("id") or raw.get("paragraph_id")
        if paragraph_id:
            paragraph_attrs.append(f'data-paragraph-id="{escape(str(paragraph_id), quote=True)}"')

        paragraph_attrs.append('contenteditable="true"')

        if paragraph_alignment:
            paragraph_styles.append(f"text-align: {paragraph_alignment}")

        block_margin_left_px: Optional[float] = None
        if isinstance(raw, dict):
            try:
                candidate = raw.get("_html_block_margin_left_px")
                if candidate not in (None, ""):
                    block_margin_left_px = float(candidate)
            except (TypeError, ValueError):
                block_margin_left_px = None

        left_margin = indent_info.get("left_px")
        if (
            left_margin is not None
            and block_margin_left_px is not None
        ):
            diff = left_margin - block_margin_left_px
            if abs(diff) <= 0.5:
                left_margin = 0.0
            else:
                left_margin = diff
        if left_margin is not None and abs(left_margin) > 0.5 and not list_meta:
            paragraph_styles.append(f"margin-left: {left_margin:.2f}px")

        right_margin = indent_info.get("right_px")
        if right_margin is not None and abs(right_margin) > 0.5 and not list_meta:
            paragraph_styles.append(f"margin-right: {right_margin:.2f}px")

        if paragraph_font_name:
            paragraph_styles.append(self._format_font_family(paragraph_font_name))
        if paragraph_font_size:
            paragraph_styles.append(self._format_font_size_rule(paragraph_font_size))

        if not list_meta:
            text_indent = indent_info.get("first_line_px")
            if text_indent is not None and abs(text_indent) > 0.5:
                paragraph_styles.append(f"text-indent: {text_indent:.2f}px")
            else:
                hanging_indent = indent_info.get("hanging_px")
                if hanging_indent is not None and abs(hanging_indent) > 0.5:
                    paragraph_styles.append(f"text-indent: {-hanging_indent:.2f}px")

        inline_fragments: list[str] = []
        last_terminal_char: Optional[str] = None
        last_fragment_ended_with_space = False
        hyphen_like_chars = {"-", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014"}

        def _last_non_whitespace_char(text: str) -> Optional[str]:
            for ch in reversed(text):
                if not ch.isspace():
                    return ch
            return None

        for line_index, line in enumerate(layout.lines):
            line_join_applied = line_index == 0
            for item in line.items:
                data = item.data or {}
                text_source = ""
                fragment_html = ""

                if item.kind == "text_run":
                    text_source = str(data.get("raw_text") or data.get("text") or "")
                    fragment_html = self._wrap_text_run(data.get("text", ""), data)
                elif item.kind == "field":
                    display_text = str(data.get("display") or "")
                    if display_text:
                        text_source = display_text
                    fragment_html = self._render_field_span(data) or ""
                elif item.kind == "inline_textbox":
                    fragment_html = self._render_inline_textbox_inline(data)
                elif item.kind == "inline_image":
                    fragment_html = self._render_inline_image_inline(data)
                else:
                    continue

                if not fragment_html:
                    continue

                if text_source:
                    normalized_source = self._normalize_inline_spacing(text_source)
                    text_source = normalized_source

                has_text = bool(text_source) and any(not ch.isspace() for ch in text_source)
                starts_with_space = bool(text_source[:1]) and text_source[0].isspace()

                if line_index > 0 and not line_join_applied and has_text:
                    if (
                        inline_fragments
                        and not last_fragment_ended_with_space
                        and not starts_with_space
                        and last_terminal_char not in hyphen_like_chars
                    ):
                        inline_fragments.append(" ")
                        last_terminal_char = " "
                        last_fragment_ended_with_space = True
                    line_join_applied = True

                inline_fragments.append(fragment_html)

                if has_text:
                    trailing_char = _last_non_whitespace_char(text_source)
                    if trailing_char is not None:
                        last_terminal_char = trailing_char
                    last_fragment_ended_with_space = bool(text_source) and text_source[-1].isspace()
                elif text_source:
                    last_fragment_ended_with_space = text_source[-1].isspace()

        if not inline_fragments:
            inline_fragments.append("&nbsp;")

        content_html = f'<div class="paragraph-line">{"".join(inline_fragments)}</div>'
        style_attr = f' style="{"; ".join(paragraph_styles)}"' if paragraph_styles else ""
        attr_str = " " + " ".join(paragraph_attrs) if paragraph_attrs else ""

        if not list_meta:
            class_attr = ' class="' + " ".join(paragraph_classes) + '"'
            return f"<div{class_attr}{attr_str}{style_attr}>\n{content_html}\n</div>"

        paragraph_classes.append("list-paragraph")

        list_type = "ordered"
        marker_format = ""
        if isinstance(marker, dict):
            marker_format = str(marker.get("format") or "").lower()
        if marker_format in {"bullet", "none", "nothing"}:
            list_type = "bullet"

        list_attrs = [
            f'data-list-type="{list_type}"',
        ]
        if "num_id" in list_meta:
            list_attrs.append(f'data-list-num="{escape(str(list_meta["num_id"]), quote=True)}"')
        if "level" in list_meta and list_meta["level"] is not None:
            list_attrs.append(f'data-list-level="{escape(str(list_meta["level"]), quote=True)}"')
        if "mode" in list_meta and list_meta["mode"]:
            list_attrs.append(f'data-list-mode="{escape(str(list_meta["mode"]), quote=True)}"')

        marker_left_offset_px = self._compute_marker_left_offset(marker, indent_info)
        marker_baseline_offset_px = self._compute_marker_baseline_offset(marker)

        marker_html = self._render_list_marker(
            marker,
            indent_info,
            list_meta,
            paragraph_font_name,
            paragraph_font_size,
            marker_left_offset_px,
            marker_baseline_offset_px,
        )
        if not marker_html:
            marker_html = self._render_list_marker_placeholder(indent_info, marker_left_offset_px)

        list_content_style_attr = ""

        class_attr = ' class="' + " ".join(paragraph_classes) + '"'
        data_attr_str = (" " + " ".join(list_attrs)) if list_attrs else ""

        return (
            f"<div{class_attr}{attr_str}{data_attr_str}{style_attr}>\n"
            f"  {marker_html}\n"
            f'  <div class="list-content"{list_content_style_attr}>\n{content_html}\n  </div>\n'
            "</div>"
        )

    def _wrap_text_run(
        self,
        text: str,
        data: Dict[str, Any],
        *,
        extra_space_per_space: float = 0.0,
    ) -> str:
        raw_text = str(data.get("raw_text", text or ""))
        text = str(text or "")
        space_count = int(data.get("space_count") or 0)

        base_text = raw_text or text
        normalized_text = self._normalize_inline_spacing(base_text)

        if not normalized_text and not space_count:
            return ""

        style_classes: list[str] = []
        css_styles: list[str] = []

        style_info = data.get("style") or {}

        if data.get("bold"):
            style_classes.append("run-bold")
        if data.get("italic"):
            style_classes.append("run-italic")
        if data.get("underline"):
            style_classes.append("run-underline")
        if data.get("strike_through"):
            style_classes.append("run-strike")
        if data.get("superscript"):
            style_classes.append("run-sup")
        if data.get("subscript"):
            style_classes.append("run-sub")
        baseline_shift = data.get("baseline_shift")
        if isinstance(baseline_shift, (int, float)):
            if baseline_shift > 0 and "run-sup" not in style_classes:
                style_classes.append("run-sup")
            elif baseline_shift < 0 and "run-sub" not in style_classes:
                style_classes.append("run-sub")
        if data.get("small_caps") or style_info.get("small_caps"):
            style_classes.append("run-smallcaps")
        if data.get("all_caps") or style_info.get("all_caps"):
            style_classes.append("run-allcaps")

        font_name = (
            style_info.get("font_ascii")
            or style_info.get("font_hAnsi")
            or style_info.get("font_name")
        )
        if font_name:
            css_styles.append(self._format_font_family(font_name))

        font_size = self._coerce_font_size(style_info.get("font_size") or data.get("font_size"))
        if font_size:
            css_styles.append(self._format_font_size_rule(font_size))

        color = data.get("color") or style_info.get("color")
        if color:
            css_styles.append(f"color: {color}")

        highlight = data.get("highlight") or style_info.get("highlight")
        if highlight:
            hex_color = self._highlight_to_hex(str(highlight))
            if hex_color:
                css_styles.append(f"background-color: {hex_color}")

        if extra_space_per_space > 0.0 and space_count > 0:
            extra_margin_px = self._points_to_css_float(extra_space_per_space * space_count)
            if extra_margin_px:
                css_styles.append(f"margin-right: {extra_margin_px:.4f}px")

        style_attr = f' style="{"; ".join(css_styles)}"' if css_styles else ""

        base_classes = ["text-run", *style_classes] if style_classes else ["text-run"]
        class_attr = f' class="{" ".join(base_classes)}"'

        hyperlink_info = data.get("hyperlink") or style_info.get("hyperlink")
        url = self._resolve_hyperlink_url(hyperlink_info, raw_text or text)
        tag_name = "span"
        attr_parts: list[str] = []
        if url:
            tag_name = "a"
            attr_parts.append(f'href="{escape(url, quote=True)}"')
            if isinstance(hyperlink_info, dict):
                tooltip = hyperlink_info.get("tooltip") or hyperlink_info.get("title")
                if tooltip:
                    attr_parts.append(f'title="{escape(str(tooltip), quote=True)}"')
                target = hyperlink_info.get("target_frame")
                if target:
                    attr_parts.append(f'target="{escape(str(target), quote=True)}"')
            attr_parts.append('rel="noopener noreferrer"')

        escaped_text = self._escape_text_with_spaces(normalized_text)
        if space_count > 0:
            escaped_text += "&nbsp;" * space_count

        run_id = data.get("run_id")
        if run_id:
            attr_parts.append(f'data-run-id="{escape(str(run_id), quote=True)}"')

        extra_attrs = f" {' '.join(attr_parts)}" if attr_parts else ""

        return f"<{tag_name}{class_attr}{style_attr}{extra_attrs}>{escaped_text}</{tag_name}>"

    def _render_field_span(self, data: Dict[str, Any]) -> Optional[str]:
        display_text = str(data.get("display") or "").strip()
        if not display_text:
            return None

        attrs: list[str] = ['class="field"']
        field_info = data.get("field")
        field_kind: Optional[str] = None
        if isinstance(field_info, dict):
            field_kind = (
                field_info.get("field_type")
                or field_info.get("type")
                or field_info.get("name")
                or field_info.get("instr")
                or field_info.get("instruction")
            )
            field_kind = str(field_kind).strip().upper() if field_kind else None
            field_instr = field_info.get("instr") or field_info.get("instruction")
            if field_instr:
                attrs.append(f'data-field-instr="{escape(str(field_instr).strip(), quote=True)}"')
        else:
            field_kind = None

        if field_kind:
            attrs.append(f'data-field-kind="{escape(field_kind, quote=True)}"')

        attrs_str = " ".join(attrs)
        return f"<span {attrs_str}>{escape(display_text)}</span>"

    def _render_inline_textbox_inline(self, data: Dict[str, Any]) -> str:
        if not isinstance(data, dict):
            return ""

        style_candidates: list[tuple[int, Any]] = []
        paragraph_payload: Optional[ParagraphLayout] = None

        raw_candidate = data.get("textbox") or data.get("layout_payload") or data.get("_layout_payload")

        def resolve_paragraph(candidate: Any) -> Optional[ParagraphLayout]:
            if isinstance(candidate, ParagraphLayout):
                return candidate
            if isinstance(candidate, TextboxLayout):
                style_candidates.append((10, candidate.style))
                return candidate.content
            if isinstance(candidate, dict):
                nested = candidate.get("layout_payload") or candidate.get("_layout_payload")
                if isinstance(nested, ParagraphLayout):
                    inner_style = candidate.get("style")
                    if inner_style:
                        style_candidates.append((20, inner_style))
                    return nested
            return None

        paragraph_payload = resolve_paragraph(raw_candidate)

        if not paragraph_payload and isinstance(data.get("textbox"), dict):
            paragraph_payload = resolve_paragraph(data["textbox"])

        if not paragraph_payload:
            text_value = data.get("text") or data.get("content") or data.get("value") or "[textbox]"
            text = escape(str(text_value))
            css_string = self._merge_style_segments(
                [self._style_dict_to_css(data.get("style"))]
            )
            style_attr = f' style="{css_string}"' if css_string else ""
            return f'<span class="inline-textbox"{style_attr}>{text}</span>'

        # Collect additional style hints
        if "style" in data:
            style_candidates.append((100, data.get("style")))
        textbox_style = data.get("textbox_style")
        if textbox_style:
            style_candidates.append((50, textbox_style))

        meta = getattr(paragraph_payload, "metadata", None)
        if isinstance(meta, dict):
            raw_style = meta.get("raw_style")
            if raw_style:
                style_candidates.append((60, raw_style))

        ordered_segments: list[str] = []
        for _, candidate_style in sorted(style_candidates, key=lambda item: item[0]):
            css = self._style_dict_to_css(candidate_style)
            if css:
                ordered_segments.append(css)

        container_css = self._merge_style_segments(ordered_segments)
        style_attr = f' style="{container_css}"' if container_css else ""

        lines: list[str] = []
        for line in paragraph_payload.lines:
            inline_fragments: list[str] = []
            for inline_item in line.items:
                inline_data = inline_item.data or {}
                if inline_item.kind == "text_run":
                    inline_fragments.append(
                        self._wrap_text_run(
                            inline_data.get("text", ""),
                            inline_data,
                            extra_space_per_space=0.0,
                        )
                    )
                elif inline_item.kind == "field":
                    field_html = self._render_field_span(inline_data)
                    if field_html:
                        inline_fragments.append(field_html)
                elif inline_item.kind == "inline_image":
                    inline_fragments.append(self._render_inline_image_inline(inline_data))
            if not inline_fragments:
                inline_fragments.append("&nbsp;")
            lines.append("".join(inline_fragments))

        inner_html = "<br />".join(lines)
        return f'<span class="inline-textbox"{style_attr}>{inner_html}</span>'

    def _extract_list_meta(self, raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        meta = raw.get("meta")
        if not isinstance(meta, dict):
            return {}
        num_id = meta.get("num_id")
        if num_id in (None, "", False):
            return {}
        result: Dict[str, Any] = {"num_id": num_id}
        level = meta.get("level")
        try:
            if level not in (None, ""):
                result["level"] = int(level)
        except (TypeError, ValueError):
            result["level"] = level
        mode = meta.get("list_indent_mode") or meta.get("mode")
        if mode:
            result["mode"] = mode
        counter_override = meta.get("marker_override_counter")
        if counter_override not in (None, "", False):
            result["counter"] = counter_override
        restart = meta.get("marker_restart")
        if restart not in (None, ""):
            result["restart"] = restart
        override_text = meta.get("marker_override_text")
        if override_text:
            result["override_text"] = override_text
        return result

    def _extract_indent_info(
        self,
        layout: ParagraphLayout,
        raw: Optional[Dict[str, Any]],
        marker: Optional[Dict[str, Any]],
    ) -> Dict[str, Optional[float]]:
        indent_source: Dict[str, Any] = {}
        if isinstance(raw, dict):
            style = raw.get("style")
            if isinstance(style, dict):
                indent_candidate = style.get("indent")
                if isinstance(indent_candidate, dict):
                    indent_source.update(indent_candidate)

        metadata_indent = layout.metadata.get("indent_metrics") if isinstance(layout.metadata, dict) else None
        if isinstance(metadata_indent, dict):
            indent_source = {**indent_source, **metadata_indent}

        marker_info = marker if isinstance(marker, dict) else {}

        def _value(*keys: str) -> Optional[Any]:
            for key in keys:
                if key in indent_source and indent_source[key] not in (None, ""):
                    return indent_source[key]
                if key in marker_info and marker_info[key] not in (None, ""):
                    return marker_info[key]
            return None

        left_px = self._points_to_css_float(_value("left_pt", "left"))
        right_px = self._points_to_css_float(_value("right_pt", "right"))
        first_line_px = self._points_to_css_float(_value("first_line_pt", "first_line"))
        hanging_px = self._points_to_css_float(_value("hanging_pt", "hanging"))
        text_position_px = self._points_to_css_float(_value("text_position_pt", "text_position"))
        number_position_px = self._points_to_css_float(_value("number_position_pt", "number_position"))

        marker_width_px: Optional[float] = None
        if text_position_px is not None and number_position_px is not None:
            marker_width_px = max(text_position_px - number_position_px, 0.0)

        return {
            "left_px": left_px,
            "right_px": right_px,
            "first_line_px": first_line_px,
            "hanging_px": hanging_px,
            "text_position_px": text_position_px,
            "number_position_px": number_position_px,
            "marker_width_px": marker_width_px,
        }

    def _compute_marker_left_offset(
        self,
        marker: Optional[Dict[str, Any]],
        indent_info: Dict[str, Optional[float]],
    ) -> Optional[float]:
        offset_px: Optional[float] = None

        if isinstance(marker, dict):
            relative = marker.get("relative_to_text")
            if relative not in (None, "", False):
                try:
                    offset_px = self._points_to_css_float(abs(float(relative)))
                except (TypeError, ValueError):
                    offset_px = None

            if offset_px is None:
                render_text_x = marker.get("render_text_x")
                marker_x = marker.get("x")
                if render_text_x not in (None, "", False) and marker_x not in (None, "", False):
                    try:
                        diff = float(render_text_x) - float(marker_x)
                        offset_px = self._points_to_css_float(diff)
                    except (TypeError, ValueError):
                        offset_px = None

        if offset_px is None:
            offset_px = indent_info.get("text_position_px") or indent_info.get("marker_width_px")

        return offset_px

    def _compute_marker_baseline_offset(self, marker: Optional[Dict[str, Any]]) -> Optional[float]:
        if not isinstance(marker, dict):
            return None
        baseline = marker.get("baseline_offset") or marker.get("baseline_shift")
        if baseline in (None, "", False):
            return None
        return self._points_to_css_float(baseline)

    def _extract_paragraph_alignment(
        self,
        layout: ParagraphLayout,
        raw: Optional[Dict[str, Any]],
    ) -> str:
        candidates: list[str] = []

        if isinstance(raw, dict):
            style = raw.get("style")
            if isinstance(style, dict):
                for key in ("text_align", "alignment", "justify"):
                    value = style.get(key)
                    if value:
                        candidates.append(str(value))

        metadata_style = layout.metadata.get("raw_style") if isinstance(layout.metadata, dict) else None
        if isinstance(metadata_style, dict):
            for key in ("justification", "alignment"):
                value = metadata_style.get(key)
                if value:
                    candidates.append(str(value))

        for candidate in candidates:
            token = candidate.strip().lower()
            if token in {"left", "right", "center"}:
                return token
            if token in {"justify", "both"}:
                return "justify"

        return ""

    def _resolve_paragraph_typography(
        self,
        layout: ParagraphLayout,
        raw: Optional[Dict[str, Any]],
    ) -> tuple[Optional[str], Optional[float]]:
        font_name: Optional[str] = None
        font_size: Optional[float] = None

        def consider(style: Optional[Dict[str, Any]]) -> None:
            nonlocal font_name, font_size
            if not isinstance(style, dict):
                return
            if font_name is None:
                candidate = (
                    style.get("font_ascii")
                    or style.get("font_hAnsi")
                    or style.get("font_name")
                )
                if candidate:
                    font_name = str(candidate)
            if font_size is None:
                candidate_size = style.get("font_size") or style.get("size")
                size_value = self._coerce_font_size(candidate_size)
                if size_value is not None:
                    font_size = size_value

        for line in layout.lines:
            for item in line.items:
                if not isinstance(item.data, dict):
                    continue
                consider(item.data.get("style"))
                if font_name and font_size:
                    break
            if font_name and font_size:
                break

        metadata_style = layout.metadata.get("raw_style") if isinstance(layout.metadata, dict) else None
        consider(metadata_style)

        if isinstance(raw, dict):
            consider(raw.get("style"))

        return font_name, font_size

    def _render_list_marker(
        self,
        marker: Optional[Dict[str, Any]],
        indent_info: Dict[str, Optional[float]],
        list_meta: Dict[str, Any],
        default_font_name: Optional[str],
        default_font_size: Optional[float],
        marker_left_offset_px: Optional[float],
        baseline_offset_px: Optional[float],
    ) -> str:
        text = list_meta.get("override_text")
        if not text and isinstance(marker, dict):
            text = self._normalize_marker_text(marker)
        if not text:
            return ""

        marker_style_parts: list[str] = []
        marker_width = indent_info.get("marker_width_px")
        if marker_width is not None and marker_width > 0.0:
            marker_style_parts.append(f"min-width: {marker_width:.2f}px")
            marker_style_parts.append(f"width: {marker_width:.2f}px")

        alignment = "right"
        if isinstance(marker, dict):
            alignment_candidate = marker.get("alignment")
            if alignment_candidate:
                alignment = str(alignment_candidate).strip().lower()
        if alignment not in {"left", "right", "center"}:
            alignment = "right"
        marker_style_parts.append(f"text-align: {alignment}")

        if marker_left_offset_px:
            marker_style_parts.append(f"left: {-marker_left_offset_px:.2f}px")

        style_info = {}
        if isinstance(marker, dict) and isinstance(marker.get("style"), dict):
            style_info = marker["style"]

        marker_dict = marker or {}

        font_name = (
            style_info.get("font_ascii")
            or style_info.get("font_hAnsi")
            or style_info.get("font_name")
            or marker_dict.get("font_name")
        )
        if not font_name:
            font_name = default_font_name
        if font_name:
            marker_style_parts.append(self._format_font_family(font_name))

        font_size = self._coerce_font_size(
            style_info.get("font_size")
            or marker_dict.get("font_size")
            or marker_dict.get("size")
        )
        if font_size is None:
            font_size = default_font_size
        if font_size:
            marker_style_parts.append(self._format_font_size_rule(font_size))
        font_size_px = self._points_to_css_float(font_size) if font_size else None

        color = (
            style_info.get("color")
            or style_info.get("font_color")
            or marker_dict.get("color")
        )
        if color:
            marker_style_parts.append(f"color: {color}")

        if baseline_offset_px:
            top_px = baseline_offset_px
            if font_size_px:
                top_px = max(baseline_offset_px - font_size_px, 0.0)
            marker_style_parts.append(f"top: {top_px:.2f}px")

        style_attr = f' style="{"; ".join(marker_style_parts)}"' if marker_style_parts else ""
        return f'<span class="list-marker"{style_attr}>{escape(str(text))}</span>'

    def _render_list_marker_placeholder(
        self,
        indent_info: Dict[str, Optional[float]],
        marker_left_offset_px: Optional[float],
    ) -> str:
        marker_width = indent_info.get("marker_width_px")
        style_parts = []
        if marker_width is not None and marker_width > 0.0:
            style_parts.append(f"min-width: {marker_width:.2f}px")
            style_parts.append(f"width: {marker_width:.2f}px")
        if marker_left_offset_px:
            style_parts.append(f"left: {-marker_left_offset_px:.2f}px")
        style_attr = f' style="{"; ".join(style_parts)}"' if style_parts else ""
        return f'<span class="list-marker list-marker-empty" aria-hidden="true"{style_attr}>&nbsp;</span>'

    def _normalize_marker_text(self, marker: Optional[Dict[str, Any]]) -> str:
        if not isinstance(marker, dict):
            return ""
        marker_text = (
            marker.get("text")
            or marker.get("label")
            or marker.get("display")
            or marker.get("bullet")
            or ""
        )
        marker_text = str(marker_text)

        suffix_raw = marker.get("suffix", "")
        suffix_text = ""
        if isinstance(suffix_raw, str):
            normalized = suffix_raw.strip().lower()
            if normalized in {"tab", "tabulation", "none", "-"}:
                suffix_text = ""
            elif normalized == "space":
                suffix_text = " "
            else:
                suffix_text = suffix_raw
        elif suffix_raw not in (None, ""):
            suffix_text = str(suffix_raw)

        if suffix_text and suffix_text not in marker_text:
            marker_text += suffix_text
        return marker_text.strip()

    def _resolve_hyperlink_url(
        self,
        hyperlink: Optional[Any],
        fallback_text: str,
    ) -> Optional[str]:
        def _normalize(candidate: Any, mode: str) -> Optional[str]:
            if candidate in (None, "", {}):
                return None
            url = str(candidate).strip()
            if not url:
                return None
            if url.startswith("#"):
                return url
            lowered = url.lower()
            if lowered.startswith(
                ("http://", "https://", "mailto:", "ftp://", "ftps://", "news:", "tel:", "sms:", "file://")
            ):
                return url
            if mode.lower() == "external":
                return url
            return url

        if isinstance(hyperlink, str):
            normalized = _normalize(hyperlink, "")
            if normalized:
                return normalized

        if isinstance(hyperlink, dict):
            target_mode = str(hyperlink.get("target_mode") or "").lower()
            for key in ("url", "href", "target", "relationship_target"):
                candidate = hyperlink.get(key)
                normalized = _normalize(candidate, target_mode)
                if normalized:
                    return normalized
            anchor_value = hyperlink.get("anchor")
            if anchor_value and str(anchor_value).strip():
                return f'#{str(anchor_value).strip()}'

        fallback = (fallback_text or "").strip()
        return _normalize(fallback, "")

    @staticmethod
    def _escape_text_with_spaces(value: str) -> str:
        if not value:
            return ""
        result: list[str] = []
        space_run = 0
        seen_content_in_line = False

        def _flush_spaces(count: int) -> None:
            if count <= 0 or not seen_content_in_line:
                return
            if count == 1:
                result.append(" ")
            else:
                result.append("&nbsp;" * (count - 1) + " ")

        for ch in value:
            if ch == " ":
                space_run += 1
                continue
            if ch == "\t":
                space_run += 4
                continue
            if ch == "\n":
                # trailing spaces at line end are discarded
                space_run = 0
                result.append("<br />")
                seen_content_in_line = False
                continue

            if space_run:
                _flush_spaces(space_run)
                space_run = 0

            result.append(escape(ch))
            seen_content_in_line = True

        if space_run:
            _flush_spaces(space_run)

        return "".join(result)

    @staticmethod
    def _normalize_inline_spacing(value: str) -> str:
        if not value:
            return ""
        # Normalize non-breaking spaces to regular spaces before collapsing.
        working = value.replace("\u00A0", " ")
        # Collapse consecutive space-like characters to a single space.
        working = re.sub(r"[ \t]{2,}", " ", working)
        return working

    @staticmethod
    def _highlight_to_hex(value: str) -> Optional[str]:
        token = value.strip().lower()
        if not token or token == "none":
            return None
        if token.startswith("#"):
            return value
        mapping = {
            "yellow": "#ffff00",
            "green": "#00ff00",
            "cyan": "#00ffff",
            "turquoise": "#00ffff",
            "blue": "#0000ff",
            "pink": "#ff00ff",
            "red": "#ff0000",
            "darkblue": "#000080",
            "darkcyan": "#008080",
            "darkgreen": "#008000",
            "darkmagenta": "#800080",
            "darkred": "#800000",
            "darkyellow": "#808000",
            "gray50": "#808080",
            "gray25": "#c0c0c0",
            "black": "#000000",
            "lightgray": "#d9d9d9",
            "lightyellow": "#ffffcc",
        }
        return mapping.get(token, None)

    def _render_generic_layout(
        self,
        layout: GenericLayout,
        *,
        raw: Optional[Dict[str, object]],
        default_label: str,
    ) -> str:
        data = layout.data if isinstance(layout.data, dict) else {}

        model_rows = data.get("rows")
        if isinstance(model_rows, list) and model_rows:
            layout_info = None
            if isinstance(raw, dict):
                layout_info = raw.get("layout_info")
            rendered_table = self._render_table_from_model_rows(
                model_rows,
                layout_info=layout_info if isinstance(layout_info, dict) else None,
                table_style=raw.get("style") if isinstance(raw, dict) else None,
                raw_source=raw if isinstance(raw, dict) else None,
            )
            if rendered_table:
                return rendered_table

        nested_payload = data.get("layout_payload") or data.get("_layout_payload")
        if nested_payload:
            html = self._render_payload(
                nested_payload,
                raw=raw,
                default_label=default_label,
            )
            if html:
                return html

        text_blob = data.get("text") or (raw.get("text") if isinstance(raw, dict) else None)
        if not text_blob:
            runs = data.get("runs_payload")
            if isinstance(runs, list):
                text_blob = "".join(str(run.get("text", "")) for run in runs if isinstance(run, dict))

        if text_blob and text_blob.strip():
            return self._render_text_blob(str(text_blob))

        marker_type = data.get("type")
        if isinstance(marker_type, str) and marker_type.lower() in {"header_marker", "footer_marker"}:
            return ""

        label = self._extract_label(raw, default_label)
        return self._render_placeholder(label, kind="generic")

    def _resolve_table_row_heights_points(
        self,
        layout: TableLayout,
        raw: Optional[Dict[str, Any]],
    ) -> list[float]:
        layout_info = {}
        if isinstance(raw, dict):
            layout_info = raw.get("layout_info") or {}

        info_heights: list[float] = []
        if isinstance(layout_info, dict):
            stored_heights = layout_info.get("row_heights")
            if isinstance(stored_heights, (list, tuple)):
                info_heights = [
                    float(value) if isinstance(value, (int, float)) else 0.0
                    for value in stored_heights
                ]

        estimated: list[float] = []
        for row in layout.rows:
            estimated.append(self._estimate_table_row_content_height(row))

        max_len = max(len(info_heights), len(estimated))
        if max_len == 0:
            return []

        result: list[float] = []
        for index in range(max_len):
            info_value = info_heights[index] if index < len(info_heights) else 0.0
            content_value = estimated[index] if index < len(estimated) else 0.0
            result.append(max(info_value, content_value))
        return result

    def _estimate_table_row_content_height(
        self,
        row: Iterable[TableCellLayout],
    ) -> float:
        max_height = 0.0
        for cell in row:
            cell_height = self._estimate_table_cell_height(cell)
            max_height = max(max_height, cell_height)
        return max_height

    def _estimate_table_cell_height(self, cell: TableCellLayout) -> float:
        content_height = 0.0
        for payload in cell.blocks or []:
            content_height += self._estimate_block_payload_height(payload)

        padding_top = padding_bottom = 0.0
        if isinstance(cell.style, BoxStyle):
            padding_top, _, padding_bottom, _ = cell.style.padding
        elif isinstance(cell.style, dict):
            padding = cell.style.get("padding")
            if isinstance(padding, (list, tuple)) and len(padding) == 4:
                padding_top = float(padding[0])
                padding_bottom = float(padding[2])

        frame_height = getattr(getattr(cell, "frame", None), "height", 0.0)
        return max(content_height + padding_top + padding_bottom, float(frame_height or 0.0))

    def _estimate_block_payload_height(self, payload: Any) -> float:
        if isinstance(payload, ParagraphLayout):
            return self._paragraph_layout_height(payload)
        if isinstance(payload, TableLayout):
            heights = self._resolve_table_row_heights_points(payload, getattr(payload, "metadata", None))
            return sum(heights)
        if isinstance(payload, ImageLayout):
            return getattr(getattr(payload, "frame", None), "height", 0.0)
        if isinstance(payload, TextboxLayout):
            content_height = self._paragraph_layout_height(payload.content)
            padding_top, _, padding_bottom, _ = payload.style.padding if isinstance(payload.style, BoxStyle) else (0.0, 0.0, 0.0, 0.0)
            frame_height = getattr(getattr(payload, "rect", None), "height", 0.0)
            return max(content_height + padding_top + padding_bottom, float(frame_height or 0.0))
        if isinstance(payload, GenericLayout):
            return getattr(getattr(payload, "frame", None), "height", 0.0)
        return float(getattr(getattr(payload, "frame", None), "height", 0.0) or 0.0)

    def _paragraph_layout_height(self, layout: ParagraphLayout) -> float:
        if not layout.lines:
            return 0.0
        last_line = layout.lines[-1]
        base_height = float(last_line.baseline_y + last_line.height)

        spacing_before = spacing_after = 0.0
        meta = getattr(layout, "metadata", None)
        if isinstance(meta, dict):
            spacing = meta.get("spacing") or {}
            spacing_before = float(spacing.get("before", 0.0) or 0.0)
            spacing_after = float(spacing.get("after", 0.0) or 0.0)

        style = getattr(layout, "style", None)
        if isinstance(style, dict):
            spacing = style.get("spacing") or {}
            spacing_before = max(spacing_before, float(spacing.get("before", 0.0) or 0.0))
            spacing_after = max(spacing_after, float(spacing.get("after", 0.0) or 0.0))

        return base_height + spacing_before + spacing_after

    def _render_table_horizontal_border(
        self,
        style_source: Optional[Any],
        raw: Optional[Dict[str, Any]],
        *,
        position: str,
    ) -> str:
        style_dict: Dict[str, Any] = {}
        if isinstance(style_source, BoxStyle):
            style_dict = self._box_style_to_style_dict(style_source)
        elif isinstance(style_source, dict):
            style_dict = style_source
        elif isinstance(raw, dict):
            style_dict = raw.get("style") or {}

        borders = {}
        if isinstance(style_dict, dict):
            candidate = style_dict.get("borders") or style_dict.get("border")
            if isinstance(candidate, dict):
                borders = candidate

        border_spec = None
        if isinstance(borders, dict):
            border_spec = borders.get(position)

        if not isinstance(border_spec, dict):
            return ""

        width = float(border_spec.get("width", 0.5) or 0.0)
        color = self._color_to_css(border_spec.get("color") or "#000000") or "#000000"
        border_style = self._normalize_border_style(border_spec.get("style"))
        if width <= 0.0:
            return ""

        offset_css = "top: 0;"
        if position == "bottom":
            offset_css = "bottom: 0;"

        return (
            f'<div class="table-border table-border-{position}" '
            f'style="{offset_css} height: 0; border-{position}: {width:.2f}px {border_style} {color};"></div>'
        )

    def _resolve_table_height_override(self, block: LayoutBlock) -> Optional[float]:
        payload = getattr(block.content, "payload", None)
        raw = getattr(block.content, "raw", None)

        if isinstance(payload, TableLayout):
            row_heights = self._resolve_table_row_heights_points(payload, raw)
            total = sum(value for value in row_heights if value > 0.0)
            frame_height = getattr(block.frame, "height", 0.0)
            return max(total, float(frame_height or 0.0)) if total > 0.0 else float(frame_height or 0.0)

        if isinstance(payload, GenericLayout) and isinstance(raw, dict):
            layout_info = raw.get("layout_info") or {}
            if isinstance(layout_info, dict):
                row_heights = layout_info.get("row_heights")
                if isinstance(row_heights, (list, tuple)):
                    total = sum(float(val) for val in row_heights if isinstance(val, (int, float)))
                    if total > 0.0:
                        frame_height = getattr(block.frame, "height", 0.0)
                        return max(total, float(frame_height or 0.0))
        return getattr(block.frame, "height", None)

    def _render_table_layout(
        self,
        layout: TableLayout,
        *,
        raw: Optional[Dict[str, object]],
        default_label: str,
    ) -> str:
        if not layout.rows:
            label = self._extract_label(raw, default_label or "Tabela")
            return self._render_placeholder(label, kind="table", extra="(empty)")

        span_info = self._extract_table_span_info(raw, layout)
        row_heights_points = self._resolve_table_row_heights_points(layout, raw)
        total_row_height = sum(row_heights_points)

        colgroup_html = ""
        row_height_styles: Dict[int, str] = {}
        if isinstance(raw, dict):
            layout_info = raw.get("layout_info") or {}
            if isinstance(layout_info, dict):
                col_widths = layout_info.get("col_widths")
                table_width = layout_info.get("table_width")
                if (
                    isinstance(col_widths, (list, tuple))
                    and col_widths
                    and all(isinstance(w, (int, float)) for w in col_widths)
                ):
                    total_width = sum(float(w) for w in col_widths if isinstance(w, (int, float)))
                    if total_width <= 0 and isinstance(table_width, (int, float)) and table_width > 0:
                        total_width = float(table_width)
                    if total_width > 0:
                        col_html = []
                        for width in col_widths:
                            if not isinstance(width, (int, float)):
                                continue
                            percentage = max(float(width) / total_width * 100.0, 0.0)
                            col_html.append(f'<col style="width: {percentage:.4f}%;" />')
                        if col_html:
                            colgroup_html = "<colgroup>" + "".join(col_html) + "</colgroup>"

                if row_heights_points:
                    total_height = sum(value for value in row_heights_points if value > 0.0)
                    if total_height <= 0.0 and layout.frame.height:
                        total_height = layout.frame.height
                    if total_height > 0.0:
                        for idx, value in enumerate(row_heights_points):
                            if value <= 0.0:
                                continue
                            percent = max(float(value) / total_height * 100.0, 0.0)
                            row_height_styles[idx] = f' style="height: {percent:.4f}%;"'
        elif row_heights_points:
            total_height = sum(value for value in row_heights_points if value > 0.0)
            if total_height > 0.0:
                for idx, value in enumerate(row_heights_points):
                    if value <= 0.0:
                        continue
                    percent = max(float(value) / total_height * 100.0, 0.0)
                    row_height_styles[idx] = f' style="height: {percent:.4f}%;"'

        rows_html: list[str] = []
        for row_idx, row in enumerate(layout.rows):
            cells_html: list[str] = []
            for col_idx, cell in enumerate(row):
                attributes: list[str] = []
                span_key = (row_idx, col_idx)
                cell_span = span_info.get(span_key)
                if cell_span and not cell_span.get("skip"):
                    colspan = cell_span.get("colspan")
                    rowspan = cell_span.get("rowspan")
                    if colspan and colspan > 1:
                        attributes.append(f'colspan="{colspan}"')
                    if rowspan and rowspan > 1:
                        attributes.append(f'rowspan="{rowspan}"')
                elif cell_span and cell_span.get("skip"):
                    continue
                cell_html = self._render_table_cell(cell)
                attr_str = " " + " ".join(attributes) if attributes else ""
                cells_html.append(f"<td{attr_str}>{cell_html}</td>")
            row_style = row_height_styles.get(row_idx, "")
            rows_html.append(f"<tr{row_style}>" + "".join(cells_html) + "</tr>")

        table_html = "<table class=\"table-block\">\n"
        if colgroup_html:
            table_html += colgroup_html + "\n"
        table_html += "\n".join(rows_html) + "\n</table>"
        bottom_border_html = self._render_table_horizontal_border(layout.style, raw, position="bottom")
        if bottom_border_html:
            table_html += "\n" + bottom_border_html
        return '<div class="table-container">' + table_html + "</div>"

    def _render_table_cell(self, cell: TableCellLayout) -> str:
        parts: list[str] = []
        for block in cell.blocks or []:
            html = self._render_payload(block, default_label="paragraph")
            if html:
                parts.append(html)
        if not parts:
            return "&nbsp;"
        return "".join(parts)

    def _extract_table_span_info(
        self,
        raw: Optional[Dict[str, Any]],
        layout: Any,
    ) -> Dict[Tuple[int, int], Dict[str, int]]:
        rows_source: Optional[Iterable[Any]] = None

        if isinstance(layout, GenericLayout):
            rows_source = layout.data.get("rows")
        elif isinstance(layout, TableLayout):
            # TableLayout does not currently expose merge metadata; rely on raw fallback.
            rows_source = layout.metadata.get("rows") if isinstance(layout.metadata, dict) else None

        if rows_source is None and isinstance(raw, dict):
            rows_source = raw.get("rows")

        _, span_map = self._analyze_model_table_rows(rows_source)
        return span_map

    def _analyze_model_table_rows(
        self,
        rows: Optional[Iterable[Any]],
    ) -> tuple[list[list[Dict[str, Any]]], Dict[Tuple[int, int], Dict[str, int]]]:
        if not rows:
            return [], {}

        rows_list = list(rows)
        if not rows_list:
            return [], {}

        normalized_rows: list[list[Any]] = []
        for row in rows_list:
            cells = getattr(row, "cells", None)
            if cells is None and isinstance(row, dict):
                cells = row.get("cells") or []
            normalized_rows.append(list(cells or []))

        row_positions: list[list[Dict[str, Any]]] = []
        for cells in normalized_rows:
            col_idx = 0
            positions: list[Dict[str, Any]] = []
            for cell in cells:
                grid_span = self._safe_int(
                    getattr(cell, "grid_span", None)
                    or (cell.get("grid_span") if isinstance(cell, dict) else None)
                    or (cell.get("gridSpan") if isinstance(cell, dict) else None)
                    or 1
                )
                grid_span = max(grid_span or 1, 1)
                vm_type = self._get_cell_vertical_merge_type(cell)
                positions.append(
                    {
                        "start_col": col_idx,
                        "grid_span": grid_span,
                        "cell": cell,
                        "vm_type": vm_type,
                    }
                )
                col_idx += grid_span
            row_positions.append(positions)

        def find_entry_covering(row_entries: list[Dict[str, Any]], target_col: int) -> Optional[Dict[str, Any]]:
            for entry in row_entries:
                start = entry["start_col"]
                span = entry["grid_span"]
                if start <= target_col < start + span:
                    return entry
            return None

        span_map: Dict[Tuple[int, int], Dict[str, int]] = {}
        total_rows = len(row_positions)

        for row_idx, entries in enumerate(row_positions):
            for entry in entries:
                start_col = entry["start_col"]
                grid_span = entry["grid_span"]
                vm_type = entry["vm_type"]

                if vm_type == "continue":
                    span_map[(row_idx, start_col)] = {"skip": True}
                    continue

                rowspan = 1
                if vm_type == "restart":
                    next_row_idx = row_idx + 1
                    while next_row_idx < total_rows:
                        next_entry = find_entry_covering(row_positions[next_row_idx], start_col)
                        if not next_entry:
                            break
                        next_vm = next_entry["vm_type"]
                        if next_vm == "continue":
                            rowspan += 1
                            next_row_idx += 1
                        else:
                            break

                has_colspan = grid_span > 1
                has_rowspan = rowspan > 1
                if has_colspan or has_rowspan:
                    span_map[(row_idx, start_col)] = {}
                    if has_colspan:
                        span_map[(row_idx, start_col)]["colspan"] = grid_span
                    if has_rowspan:
                        span_map[(row_idx, start_col)]["rowspan"] = rowspan

                if rowspan > 1:
                    for offset in range(grid_span):
                        for delta in range(1, rowspan):
                            span_map[(row_idx + delta, start_col + offset)] = {"skip": True}

        return row_positions, span_map

    @staticmethod
    def _get_cell_vertical_merge_type(cell: Any) -> Optional[str]:
        vm_type = getattr(cell, "vertical_merge_type", None)
        if vm_type is None:
            vm = getattr(cell, "vertical_merge", None)
            vm_type = getattr(vm, "type", None) if vm else None
        if vm_type is None and isinstance(cell, dict):
            candidate = cell.get("vertical_merge_type") or cell.get("vMerge") or cell.get("vertical_merge")
            if isinstance(candidate, dict):
                vm_type = candidate.get("val") or candidate.get("value")
            else:
                vm_type = candidate
        if isinstance(vm_type, str):
            vm_type = vm_type.lower()
        return vm_type or None

    def _render_image_layout(
        self,
        layout: ImageLayout,
        *,
        raw: Optional[Dict[str, object]],
    ) -> str:
        if isinstance(raw, dict):
            label = raw.get("alt_text") or raw.get("title") or raw.get("name")
        else:
            label = None
        if not label and isinstance(layout.metadata, dict):
            label = layout.metadata.get("description") or layout.metadata.get("title")
        label = label or "Obraz"

        payload: Dict[str, Any] = {}
        if isinstance(layout.metadata, dict):
            payload.update(layout.metadata)
        if layout.path:
            payload.setdefault("path", layout.path)
            payload.setdefault("image_path", layout.path)

        src = self._resolve_image_source(
            payload,
            layout.frame,
            width_px=self._points_to_pixels(layout.frame.width),
            height_px=self._points_to_pixels(layout.frame.height),
        )
        if not src:
            return self._render_placeholder(str(label), kind="image")

        return (
            '<div class="image-block">'
            f'<img src="{escape(src, quote=True)}" alt="{escape(str(label), quote=True)}" />'
            "</div>"
        )

    def _render_table_from_model_rows(
        self,
        rows: Iterable[Any],
        *,
        layout_info: Optional[Dict[str, Any]] = None,
        table_style: Optional[Any] = None,
        raw_source: Optional[Dict[str, Any]] = None,
    ) -> str:
        rows_list = list(rows or [])
        row_positions, span_info = self._analyze_model_table_rows(rows_list)

        colgroup_html = ""
        row_height_styles: Dict[int, str] = {}
        if isinstance(layout_info, dict):
            col_widths = layout_info.get("col_widths")
            table_width = layout_info.get("table_width")
            if (
                isinstance(col_widths, (list, tuple))
                and col_widths
                and all(isinstance(w, (int, float)) for w in col_widths)
            ):
                total_width = sum(float(w) for w in col_widths if isinstance(w, (int, float)))
                if total_width <= 0 and isinstance(table_width, (int, float)) and table_width > 0:
                    total_width = float(table_width)
                if total_width > 0:
                    col_tags: list[str] = []
                    for width in col_widths:
                        if not isinstance(width, (int, float)):
                            continue
                        percentage = max(float(width) / total_width * 100.0, 0.0)
                        col_tags.append(f'<col style="width: {percentage:.4f}%;" />')
                    if col_tags:
                        colgroup_html = "<colgroup>" + "".join(col_tags) + "</colgroup>"
            row_heights = layout_info.get("row_heights")
            if isinstance(row_heights, (list, tuple)) and row_heights:
                numeric_rows = [
                    float(value)
                    for value in row_heights
                    if isinstance(value, (int, float))
                ]
                total_height = sum(value for value in numeric_rows if value > 0.0)
                if total_height <= 0.0 and isinstance(layout_info.get("table_height"), (int, float)):
                    total_height = float(layout_info.get("table_height"))
                if total_height <= 0.0:
                    total_height = sum(numeric_rows)
                if total_height > 0.0:
                    for idx, value in enumerate(row_heights):
                        if not isinstance(value, (int, float)) or value <= 0.0:
                            continue
                        percent = max(float(value) / total_height * 100.0, 0.0)
                        row_height_styles[idx] = f' style="height: {percent:.4f}%;"'

        html_rows: list[str] = []
        if row_positions:
            for row_idx, entries in enumerate(row_positions):
                cells_html: list[str] = []
                for entry in entries:
                    start_col = entry["start_col"]
                    cell = entry["cell"]
                    attr_data = span_info.get((row_idx, start_col))
                    if attr_data and attr_data.get("skip"):
                        continue

                    attributes: list[str] = []
                    if attr_data:
                        colspan = attr_data.get("colspan")
                        rowspan = attr_data.get("rowspan")
                        if colspan and colspan > 1:
                            attributes.append(f'colspan="{colspan}"')
                        if rowspan and rowspan > 1:
                            attributes.append(f'rowspan="{rowspan}"')

                    cell_html = self._render_table_model_cell(cell)
                    attr_str = " " + " ".join(attributes) if attributes else ""
                    cells_html.append(f"<td{attr_str}>{cell_html}</td>")
                row_style = row_height_styles.get(row_idx, "")
                html_rows.append(f"<tr{row_style}>" + "".join(cells_html) + "</tr>")

        if not html_rows:
            return ""
        table_html = "<table class=\"table-block\">\n"
        if colgroup_html:
            table_html += colgroup_html + "\n"
        table_html += "\n".join(html_rows) + "\n</table>"
        bottom_border = self._render_table_horizontal_border(table_style, raw_source, position="bottom")
        if bottom_border:
            table_html += "\n" + bottom_border
        return '<div class="table-container">' + table_html + "</div>"

    def _render_table_model_cell(self, cell: Any) -> str:
        parts: list[str] = []
        for child in getattr(cell, "children", None) or []:
            normalized = self._render_cell_child(child)
            if normalized:
                parts.append(normalized)

        images = self._collect_cell_images(cell)
        if images:
            for img_payload in images:
                width_pt = float(img_payload.get("width", 0.0)) or 0.0
                height_pt = float(img_payload.get("height", 0.0)) or 0.0
                rect = Rect(0.0, 0.0, width_pt, height_pt)
                src = self._resolve_image_source(
                    img_payload,
                    rect,
                    width_px=self._points_to_pixels(width_pt) if width_pt else None,
                    height_px=self._points_to_pixels(height_pt) if height_pt else None,
                )
                if not src:
                    continue
                label = (
                    img_payload.get("alt")
                    or img_payload.get("description")
                    or img_payload.get("title")
                    or "image"
                )
                parts.append(
                    '<div class="cell-image">'
                    f'<img src="{escape(src, quote=True)}" alt="{escape(str(label), quote=True)}" style="max-width: 100%; height: auto; display: block;" />'
                    "</div>"
                )

        if not parts:
            return "&nbsp;"
        return "".join(parts)

    def _render_cell_child(self, child: Any) -> str:
        if child is None:
            return ""

        if isinstance(child, dict):
            payload = child.get("layout_payload") or child.get("_layout_payload")
            if payload:
                return self._render_payload(payload, raw=child, default_label="paragraph")
            if "text" in child:
                return self._render_text_blob(str(child.get("text") or ""))
            if "runs" in child and isinstance(child["runs"], list):
                return self._render_paragraph_layout(
                    ParagraphLayout(
                        lines=[
                            ParagraphLine(
                                baseline_y=0.0,
                                height=12.0,
                                items=self._inline_boxes_from_runs(child["runs"]),
                            )
                        ]
                    )
                )
            return ""

        layout_payload = getattr(child, "layout_payload", None)
        if layout_payload:
            return self._render_payload(layout_payload, default_label="paragraph")

        text = getattr(child, "text", None)
        if text:
            return self._render_text_blob(str(text))

        runs = getattr(child, "runs", None)
        if runs:
            return self._render_paragraph_layout(
                ParagraphLayout(
                    lines=[
                        ParagraphLine(
                            baseline_y=0.0,
                            height=12.0,
                            items=self._inline_boxes_from_runs(runs),
                        )
                    ]
                )
            )

        children = getattr(child, "children", None)
        if children:
            fragments: list[str] = []
            for grandchild in children:
                normalized = self._render_cell_child(grandchild)
                if normalized:
                    fragments.append(normalized)
            return "".join(fragments)

        return ""

    def _inline_boxes_from_runs(self, runs: Iterable[Any]) -> list[InlineBox]:
        boxes: list[InlineBox] = []
        for run in runs:
            data: Dict[str, Any] = {}
            if isinstance(run, dict):
                data = dict(run)
                text = run.get("text", "")
                style = run.get("style", {})
            else:
                text = getattr(run, "text", "")
                style = getattr(run, "style", {})
                data = {
                    "text": text,
                    "raw_text": getattr(run, "raw_text", text),
                    "style": style if isinstance(style, dict) else {},
                    "bold": getattr(run, "bold", False),
                    "italic": getattr(run, "italic", False),
                    "underline": getattr(run, "underline", False),
                    "strike_through": getattr(run, "strike_through", False),
                    "superscript": getattr(run, "superscript", False),
                    "subscript": getattr(run, "subscript", False),
                    "color": getattr(run, "color", None),
                }
            boxes.append(
                InlineBox(
                    kind="text_run",
                    x=0.0,
                    width=0.0,
                    ascent=0.0,
                    descent=0.0,
                    data=data,
                )
            )
        return boxes

    def _render_inline_image_inline(self, data: Dict[str, Any]) -> str:
        payload: Dict[str, Any] = {}
        original: Dict[str, Any] = {}
        if isinstance(data, dict):
            original = data
            if isinstance(data.get("image"), dict):
                payload = dict(data["image"])
            else:
                payload = dict(data)
        else:
            payload = self._normalize_image_payload(data) or {}
            original = {}

        if original:
            payload.setdefault("path", payload.get("path") or original.get("path"))
            payload.setdefault("image_path", payload.get("image_path") or original.get("image_path"))

        width_pt = float(payload.get("width", 0.0)) or 0.0
        height_pt = float(payload.get("height", 0.0)) or 0.0
        rect = Rect(0.0, 0.0, width_pt, height_pt)

        src = self._resolve_image_source(
            payload,
            rect,
            width_px=self._points_to_pixels(width_pt) if width_pt else None,
            height_px=self._points_to_pixels(height_pt) if height_pt else None,
        )
        label = payload.get("description") or payload.get("title") or "inline image"
        if not src:
            return f'<span class="inline-image">{escape(str(label))}</span>'

        style_attr = ' style="max-width: 100%; height: auto; display: inline-block;"'
        return (
            '<span class="inline-image">'
            f'<img src="{escape(src, quote=True)}" alt="{escape(str(label), quote=True)}"{style_attr} />'
            "</span>"
        )

    def _collect_cell_images(self, cell: Any) -> list[Dict[str, Any]]:
        images: list[Dict[str, Any]] = []
        seen_signatures: set[tuple[Any, ...]] = set()
        visited: set[int] = set()

        def add_image(candidate: Any) -> None:
            payload = self._normalize_image_payload(candidate)
            if not payload:
                return
            signature = self._image_signature(payload)
            if signature in seen_signatures:
                return
            seen_signatures.add(signature)
            images.append(payload)

        def visit(obj: Any) -> None:
            if obj is None:
                return
            try:
                obj_id = id(obj)
                if obj_id in visited:
                    return
                visited.add(obj_id)
            except Exception:
                pass

            if isinstance(obj, dict):
                if obj.get("type") == "image":
                    add_image(obj)
                if obj.get("type") == "drawing":
                    visit(obj.get("content"))
                if "images" in obj:
                    seq = obj["images"]
                    if isinstance(seq, list):
                        for element in seq:
                            add_image(element)
                    else:
                        add_image(seq)
                for key in ("content", "children", "elements", "items", "paragraphs", "runs"):
                    value = obj.get(key)
                    if isinstance(value, list):
                        for element in value:
                            visit(element)
                    elif value is not None:
                        visit(value)
                return

            if isinstance(obj, (list, tuple, set)):
                for element in obj:
                    visit(element)
                return

            if hasattr(obj, "get_images"):
                try:
                    seq = obj.get_images()
                except Exception:
                    seq = None
                if seq:
                    for element in seq:
                        add_image(element)

            for attr in ("images", "image", "drawing", "drawings"):
                if hasattr(obj, attr):
                    value = getattr(obj, attr)
                    if attr == "image" and value is not None and not isinstance(value, (list, tuple)):
                        add_image(value)
                    else:
                        visit(value)

            for attr in ("content", "children", "elements", "paragraphs", "runs"):
                if hasattr(obj, attr):
                    visit(getattr(obj, attr))

        visit(cell)
        return images

    def _normalize_image_payload(self, image: Any) -> Optional[Dict[str, Any]]:
        if image is None:
            return None

        if isinstance(image, dict):
            payload = dict(image)
        else:
            payload: Dict[str, Any] = {}
            for attr in (
                "path",
                "image_path",
                "src",
                "relationship_id",
                "rel_id",
                "part_path",
                "width",
                "height",
            ):
                if hasattr(image, attr):
                    value = getattr(image, attr)
                    if value not in (None, "", 0):
                        payload[attr] = value
            inner_image = getattr(image, "image", None)
            if inner_image:
                normalized_inner = self._normalize_image_payload(inner_image)
                if normalized_inner:
                    payload.setdefault("image", normalized_inner)
            payload = {k: v for k, v in payload.items() if v not in (None, "", [])}

        if not payload:
            return None
        return payload

    def _image_signature(self, payload: Dict[str, Any]) -> tuple[Any, ...]:
        signature = (
            payload.get("relationship_id") or payload.get("rel_id"),
            payload.get("path") or payload.get("image_path") or payload.get("src"),
        )
        if all(value is None for value in signature):
            digest_source = repr(sorted(payload.items())).encode("utf-8", errors="ignore")
            digest = hashlib.sha1(digest_source).hexdigest()
            return (digest,)
        return signature

    def _render_overlay(
        self,
        overlay: OverlayBox,
        context: _BlockRenderContext,
    ) -> Optional[str]:
        frame = overlay.frame
        raw_top_in_page = (
            context.page_height
            - float(getattr(frame, "y", 0.0))
            - float(getattr(frame, "height", 0.0))
        )
        top_in_page = (
            raw_top_in_page
            if context.section_role == "footer"
            else max(raw_top_in_page, 0.0)
        )
        left_points = float(getattr(frame, "x", 0.0)) - context.margin_left
        frame_height = float(getattr(frame, "height", 0.0))
        frame_width = float(getattr(frame, "width", 0.0))

        anchor_x, anchor_x_rel, anchor_y, anchor_y_rel = self._extract_overlay_anchor(overlay)
        if anchor_y is not None:
            resolved_top = self._resolve_overlay_vertical_position(anchor_y, anchor_y_rel, context, frame_height)
            top_in_page = max(min(resolved_top, context.page_height), 0.0)
        if anchor_x is not None:
            left_points = self._resolve_overlay_horizontal_position(anchor_x, anchor_x_rel, context, frame_width)
        else:
            left_points = max(left_points, 0.0)

        section_shift = context.section_shift if context.section_role == "footer" else 0.0
        effective_origin = context.section_origin - section_shift
        adjusted_top = top_in_page - effective_origin
        if context.section_role != "footer" and adjusted_top < 0.0:
            adjusted_top = 0.0

        bottom_points: Optional[float] = None
        top_points: Optional[float] = None
        if context.section_role == "footer":
            bottom_points = context.page_height - (top_in_page + frame_height)
        else:
            top_points = context.flow_offset + adjusted_top

        left_px = self._points_to_css_float(left_points)
        top_px = self._points_to_css_float(top_points) if top_points is not None else None
        bottom_px = (
            self._points_to_css_float(bottom_points) if bottom_points is not None else None
        )
        width_px = self._points_to_css_float(float(getattr(frame, "width", 0.0)))
        height_px = self._points_to_css_float(float(getattr(frame, "height", 0.0)))

        style_parts = ["position: absolute"]
        if top_px is not None:
            style_parts.append(f"top: {top_px:.2f}px")
        if bottom_px is not None:
            style_parts.append(f"bottom: {bottom_px:.2f}px")
        if left_px is not None:
            style_parts.append(f"left: {left_px:.2f}px")
        if width_px is not None and width_px > 0:
            style_parts.append(f"width: {width_px:.2f}px")
        if height_px is not None and height_px > 0:
            style_parts.append(f"height: {height_px:.2f}px")

        base_style = "; ".join(style_parts)

        payload_dict: Dict[str, Any] = {}
        if isinstance(overlay.payload, dict):
            payload_dict = overlay.payload

        if overlay.kind == "image":
            src = self._resolve_image_source(
                payload_dict,
                overlay.frame,
                width_px=self._points_to_pixels(overlay.frame.width),
                height_px=self._points_to_pixels(overlay.frame.height),
            )
            if src:
                alt = self._extract_label(payload_dict, "image")
                return (
                    f'<div class="overlay overlay-image" style="{base_style}">'
                    f'<img src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}" />'
                    "</div>"
                )

        if overlay.kind == "textbox":
            style_candidates: list[tuple[int, Any]] = []
            paragraph_payload: Optional[ParagraphLayout] = None
            raw_context: Optional[Dict[str, Any]] = payload_dict if payload_dict else None

            if isinstance(overlay.payload, TextboxLayout):
                paragraph_payload = overlay.payload.content
                style_candidates.append((10, overlay.payload.style))
                if isinstance(overlay.payload.metadata, dict):
                    raw_context = overlay.payload.metadata

            def resolve_paragraph(candidate: Any) -> Optional[ParagraphLayout]:
                if isinstance(candidate, ParagraphLayout):
                    return candidate
                if isinstance(candidate, TextboxLayout):
                    style_candidates.append((20, candidate.style))
                    return candidate.content
                if isinstance(candidate, dict):
                    inner_style = candidate.get("style")
                    if inner_style:
                        style_candidates.append((30, inner_style))
                    nested = candidate.get("layout_payload") or candidate.get("_layout_payload")
                    if isinstance(nested, ParagraphLayout):
                        return nested
                return None

            if paragraph_payload is None and payload_dict:
                paragraph_payload = resolve_paragraph(payload_dict.get("layout_payload"))
                if paragraph_payload is None:
                    textbox_candidate = (
                        payload_dict.get("textbox")
                        or payload_dict.get("content")
                        or payload_dict.get("layout")
                    )
                    paragraph_payload = resolve_paragraph(textbox_candidate)

            if payload_dict:
                style_candidates.append((40, payload_dict.get("style")))
                textbox_meta = payload_dict.get("textbox")
                if isinstance(textbox_meta, dict):
                    style_candidates.append((50, textbox_meta.get("style")))

            if paragraph_payload and raw_context is None and isinstance(getattr(paragraph_payload, "metadata", None), dict):
                raw_context = paragraph_payload.metadata  # type: ignore[attr-defined]

            if paragraph_payload and isinstance(raw_context, dict):
                raw_style = raw_context.get("raw_style")
                if raw_style:
                    style_candidates.append((60, raw_style))

            content_html: str
            if paragraph_payload:
                content_html = self._render_paragraph_layout(
                    paragraph_payload,
                    raw=raw_context,
                )
            else:
                text_value = (
                    payload_dict.get("text")
                    or payload_dict.get("content")
                    or payload_dict.get("value")
                    or (overlay.payload.text if hasattr(overlay.payload, "text") else None)
                )
                if text_value:
                    content_html = self._render_text_blob(str(text_value))
                else:
                    label = self._extract_label(payload_dict, "textbox")
                    content_html = self._render_placeholder(label, kind="textbox")

            style_segments: list[tuple[int, Optional[str]]] = [(0, base_style)]
            for priority, candidate_style in sorted(style_candidates, key=lambda item: item[0]):
                css = self._style_dict_to_css(candidate_style)
                if css:
                    style_segments.append((priority, css))
            final_style = self._merge_style_segments(segment for _, segment in style_segments)

            return (
                f'<div class="overlay overlay-textbox" style="{final_style}">'
                f"{content_html}"
                "</div>"
            )

        label = self._extract_label(payload_dict, overlay.kind)
        final_style = self._merge_style_segments(
            [base_style, self._style_dict_to_css(payload_dict.get("style"))]
        )
        return (
            f'<div class="overlay overlay-{overlay.kind}" style="{final_style}">'
            f"{escape(label)}"
            "</div>"
        )

    def _resolve_image_source(
        self,
        payload: Dict[str, Any],
        frame: Rect,
        *,
        width_px: Optional[int] = None,
        height_px: Optional[int] = None,
    ) -> Optional[str]:
        if payload is None:
            return None

        image_info = payload
        if isinstance(payload.get("image"), dict):
            image_info = payload["image"]
        elif isinstance(payload.get("source"), dict):
            image_info = payload["source"]

        path = ""
        if isinstance(image_info, dict):
            path = image_info.get("path") or image_info.get("image_path") or image_info.get("src") or ""
        elif isinstance(image_info, str):
            path = image_info

        binary: Optional[bytes] = None
        suffix: Optional[str] = None

        if path:
            path_obj = Path(path)
            if path_obj.exists():
                try:
                    binary = path_obj.read_bytes()
                    suffix = path_obj.suffix.lower()
                except OSError:
                    binary = None

        if binary is None and isinstance(image_info, dict):
            rel_id = image_info.get("relationship_id") or image_info.get("rel_id")
            rel_source = image_info.get("relationship_source") or image_info.get("part_path")
            candidates = [path]
            if image_info.get("image_path"):
                candidates.append(image_info["image_path"])
            if rel_source:
                candidates.append(rel_source)
            for candidate in filter(None, candidates):
                candidate_name = str(candidate).lstrip("/")
                if self.package_reader:
                    try:
                        data = self.package_reader.get_binary_content(candidate_name)
                    except KeyError:
                        data = None
                    if data:
                        binary = data
                        suffix = Path(candidate_name).suffix.lower()
                        break

        if binary is None:
            return None

        suffix = (suffix or (Path(path).suffix if path else "") or "").lower()
        if suffix in {".wmf", ".emf"}:
            png_bytes = self.media_converter.convert_emf_to_png(
                binary,
                width=width_px,
                height=height_px,
            )
            if png_bytes:
                return self._store_image_bytes(png_bytes, ".png")
            return None

        allowed = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
        if suffix not in allowed:
            source_format = suffix.lstrip(".")
            if source_format and source_format in getattr(self.media_converter, "supported_formats", {}):
                try:
                    converted = self.media_converter.convert_image_format(binary, source_format, "png")
                except Exception:
                    converted = None
                if converted:
                    return self._store_image_bytes(converted, ".png")
            return None

        return self._store_image_bytes(binary, suffix or ".png")

    def _store_image_bytes(self, data: bytes, extension: str) -> str:
        if self.config.embed_images_as_data_uri:
            import base64

            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
            }.get(extension.lower(), "application/octet-stream")
            encoded = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{encoded}"

        if not self._assets_root:
            raise RuntimeError("Assets directory not initialised")

        ext = extension if extension.startswith(".") else f".{extension}"
        digest = hashlib.sha1(data).hexdigest()
        filename = f"{digest}{ext.lower()}"

        cached = self._asset_cache.get(filename)
        if cached:
            return cached

        target_path = self._assets_root / filename
        if not target_path.exists():
            target_path.write_bytes(data)

        relative = str(Path(self.config.asset_output_dirname) / filename)
        self._asset_cache[filename] = relative
        return relative

    def _render_placeholder(self, label: str, *, kind: str, extra: Optional[str] = None) -> str:
        text = label.strip() if label else kind
        if extra:
            text = f"{text} {extra}"
        return (
            f'<div class="block-placeholder" data-kind="{escape(kind)}">'
            f"{escape(text)}"
            "</div>"
        )

    def _render_text_blob(self, text: str) -> str:
        lines = text.splitlines() or [text]
        line_html = []
        for line in lines:
            if line:
                line_html.append(f'<div class="paragraph-line">{escape(line)}</div>')
            else:
                line_html.append('<div class="paragraph-line">&nbsp;</div>')
        return '<div class="paragraph" data-role="paragraph">\n' + "\n".join(line_html) + "\n</div>"

    @staticmethod
    def _format_font_family(font_name: str) -> str:
        sanitized = str(font_name).replace("'", "\\'")
        return f"font-family: '{sanitized}', sans-serif"

    @staticmethod
    def _format_font_size_rule(points: float) -> str:
        safe_points = max(float(points or 0.0), 0.0)
        return f"font-size: calc(var(--doc-font-scale, 1) * {safe_points:.2f}pt)"

    def _coerce_font_size(self, value: Any) -> Optional[float]:
        if value in (None, "", False):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            try:
                numeric = float(str(value).strip())
            except (TypeError, ValueError):
                return None
        if numeric <= 0.0:
            return None
        return numeric

    @staticmethod
    def _points_to_css_float(value: Any, dpi: float = 96.0) -> Optional[float]:
        if value in (None, "", False):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric * dpi / 72.0

    @staticmethod
    def _normalize_dom_id(value: str) -> str:
        token = re.sub(r"[^0-9A-Za-z_-]+", "-", value.strip())
        token = token.strip("-")
        if not token:
            token = "block"
        if token[0].isdigit():
            token = f"b-{token}"
        return token

    @staticmethod
    def _encode_data_attribute(value: Any) -> str:
        try:
            serialized = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        except TypeError:
            serialized = json.dumps({})
        return escape(serialized, quote=True)

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value in (None, "", False):
            return None
        if isinstance(value, int):
            return value
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _points_to_pixels(value: float, dpi: float = 96.0) -> int:
        pixels = int(round(value * dpi / 72.0))
        return max(pixels, 1)

    @staticmethod
    def _safe_float(value: Any) -> float:
        if value in (None, "", False):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return 0.0

    def _extract_label(
        self,
        raw: Optional[Dict[str, object]],
        default: str,
    ) -> str:
        if isinstance(raw, dict):
            for key in ("title", "caption", "text", "label", "name"):
                value = raw.get(key)
                if value:
                    return str(value)
        return default

