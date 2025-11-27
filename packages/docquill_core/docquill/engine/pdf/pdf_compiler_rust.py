"""
Rust-based PDF compiler using pdf-writer.

This module provides a high-performance PDF renderer using Rust (pdf-writer)
as an alternative to ReportLab. It can be used as a drop-in replacement
or as a fallback option.
"""

import logging
import mimetypes
import threading
import tempfile
import hashlib
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Tuple
from dataclasses import asdict, fields, is_dataclass

logger = logging.getLogger(__name__)
_IMAGE_TARGET_DPI = 192.0  # Match ReportLab implementation for rasterizing EMF/WMF

# Try to import Rust renderer
pdf_renderer_rust = None
HAS_RUST_RENDERER = False

# Try docquill_rust first (new unified package from PyPI)
try:
    import docquill_rust
    if hasattr(docquill_rust, 'PdfRenderer'):
        pdf_renderer_rust = docquill_rust
        HAS_RUST_RENDERER = True
        logger.debug("Loaded Rust renderer from docquill_rust (PdfRenderer)")
except ImportError:
    pass

# Legacy: try pdf_renderer_rust
if not HAS_RUST_RENDERER:
    try:
        import pdf_renderer_rust as _pdf_renderer_rust
        if hasattr(_pdf_renderer_rust, 'PdfRenderer'):
            pdf_renderer_rust = _pdf_renderer_rust
            HAS_RUST_RENDERER = True
            logger.debug("Loaded Rust renderer from pdf_renderer_rust")
    except ImportError:
        pass

if not HAS_RUST_RENDERER:
    logger.debug(
        "pdf_renderer_rust not available. Install docquill-rust: pip install docquill-rust"
    )

try:
    from ..unified_layout import UnifiedLayout, LayoutPage, LayoutBlock
    from ..geometry import Rect, Size, Margins, emu_to_points
    from ..layout_primitives import (
        BlockContent,
        ParagraphLayout,
        ParagraphLine,
        InlineBox,
        OverlayBox,
    )
except ImportError:
    # Allow running as a script for testing (add parent to path)
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))
    from docquill.engine.unified_layout import UnifiedLayout, LayoutPage, LayoutBlock
    from docquill.engine.geometry import Rect, Size, Margins, emu_to_points
    from docquill.engine.layout_primitives import (
        BlockContent,
        ParagraphLayout,
        ParagraphLine,
        InlineBox,
        OverlayBox,
    )
from ...media import MediaConverter


class PDFCompilerRust:
    """
    Rust-based PDF compiler using pdf-writer.
    
    Provides high-performance PDF rendering as an alternative to ReportLab.
    """
    
    def __init__(
        self,
        output_path: str,
        page_size: tuple = (595.0, 842.0),  # A4 in points
        package_reader: Optional[Any] = None,
        footnote_renderer: Optional[Any] = None,
        image_cache: Optional[Any] = None,
        media_converter: Optional[Any] = None,
        watermark_opacity: Optional[float] = None,
    ):
        """
        Initialize Rust PDF compiler.
        
        Args:
            output_path: Path to output PDF file
            page_size: Page size tuple (width, height) in points
            package_reader: PackageReader instance (for image paths)
            footnote_renderer: FootnoteRenderer instance (optional)
            image_cache: LayoutPipeline image cache (for pre-converted WMF/EMF images)
            media_converter: MediaConverter instance (optional)
            watermark_opacity: Optional opacity override for watermark blocks (0.0-1.0)
        """
        if not HAS_RUST_RENDERER:
            raise ImportError(
                "Rust PDF renderer not available. "
                "Install with: pip install docquill-rust"
            )
        
        self.output_path = str(output_path)
        self.page_size = page_size
        self.package_reader = package_reader
        self.footnote_renderer = footnote_renderer
        self.image_cache = image_cache
        self.media_converter = media_converter or MediaConverter()
        self._temp_files: List[Path] = []
        self._converted_images: Dict[str, Path] = {}
        self._current_timings: Optional[Dict[str, List[float]]] = None
        self._registered_stream_keys: Set[str] = set()
        self.image_streams: Dict[str, bytes] = {}  # Store image bytes for streaming
        self.watermark_opacity_override = self._normalize_opacity_value(watermark_opacity)
        
        # Initialize Rust renderer
        self.renderer = pdf_renderer_rust.PdfRenderer(
            self.output_path,
            page_size[0],
            page_size[1],
        )
        
        # Performance limits (can be adjusted)
        self._max_pages: Optional[int] = None  # None = no limit
        self._max_blocks_per_page: Optional[int] = None  # None = no limit
        self._max_lines_per_paragraph: Optional[int] = None  # None = no limit
        
        # Enable compact layout by default
        self._use_compact_layout = True

        # Dispatcher: block_type -> handler
        self._dispatch = self._build_dispatcher()
        
        logger.info(f"PDFCompilerRust initialized: output={self.output_path}, page_size={self.page_size}")
    
    def __del__(self):
        for tmp in getattr(self, "_temp_files", []) or []:
            try:
                Path(tmp).unlink(missing_ok=True)
            except Exception:
                pass

    # ======================================================================
    # Dispatcher
    # ======================================================================

    def _build_dispatcher(self) -> Dict[str, Any]:
        """
        Build dispatcher mapping block_type -> handler function.
        Each handler has signature:
            handler(x, y, width, height, content, block)
        """
        return {
            "paragraph": self._handle_paragraph_block,
            "table": self._handle_table_block,
            "image": self._handle_image_block,
            "header": self._handle_header_block,
            "footer": self._handle_footer_block,
            "footnotes": self._handle_footnotes_block,
            "endnotes": self._handle_endnotes_block,
            # Shapes / textboxes / decorations
            "textbox": self._handle_rect_block,
            "decorator": self._handle_rect_block,
            "rectangle": self._handle_rect_block,
            "rect": self._handle_rect_block,
            "vml_shape": self._handle_rect_block,
        }

    def _render_element(self, block: LayoutBlock) -> None:
        """
        Central dispatch for a single block using dict lookup instead of
        match/case spaghetti.
        """
        block_type = getattr(block, "block_type", None)
        handler = self._dispatch.get(block_type)

        if handler is None:
            logger.warning(f"Unknown block type: {block_type}, skipping")
            return

        frame = block.frame
        x, y, width, height = frame.x, frame.y, frame.width, frame.height
        
        content = self._prepare_content_for_renderer(block.content)
        
        # For paragraphs, check if layout_payload is in block or content
        if block_type == "paragraph":
            # First check if block has layout_payload directly
            if hasattr(block, "layout_payload") and block.layout_payload:
                layout_dict = self._safe_to_dict(block.layout_payload, visited=None)
                if "lines" in layout_dict:
                    content["layout_payload"] = layout_dict
                    logger.info(f"✅ Extracted layout_payload from block.layout_payload for paragraph at ({x:.1f}, {y:.1f}), lines: {len(layout_dict.get('lines', []))}")
            elif hasattr(block, "_layout_payload") and block._layout_payload:
                layout_dict = self._safe_to_dict(block._layout_payload, visited=None)
                if "lines" in layout_dict:
                    content["layout_payload"] = layout_dict
                    logger.info(f"✅ Extracted layout_payload from block._layout_payload for paragraph at ({x:.1f}, {y:.1f}), lines: {len(layout_dict.get('lines', []))}")
            
            # Then check if content has layout_payload
            if "layout_payload" not in content and "_layout_payload" not in content:
                # Check if content has payload with layout_payload
                if "payload" in content:
                    payload = content["payload"]
                    logger.warning(f"🔍 Paragraph at ({x:.1f}, {y:.1f}): payload type: {type(payload).__name__}")
                    # payload might be dict or ParagraphLayout object
                    if isinstance(payload, dict):
                        logger.warning(f"  payload keys: {list(payload.keys())[:10]}")
                        # Check if payload has lines directly or layout_payload
                        if "lines" in payload:
                            # payload is ParagraphLayout with lines
                            content["layout_payload"] = payload
                            logger.info(f"✅ Extracted layout_payload from payload (dict) for paragraph at ({x:.1f}, {y:.1f}), lines: {len(payload.get('lines', []))}")
                        elif "data" in payload:
                            # Check if payload.data has lines
                            data = payload["data"]
                            logger.warning(f"  payload.data type: {type(data).__name__}")
                            if isinstance(data, dict):
                                logger.warning(f"  payload.data keys: {list(data.keys())[:10]}")
                                if "lines" in data:
                                    content["layout_payload"] = data
                                    logger.info(f"✅ Extracted layout_payload from payload.data for paragraph at ({x:.1f}, {y:.1f}), lines: {len(data.get('lines', []))}")
                            elif hasattr(data, "lines"):
                                # data is ParagraphLayout object
                                data_dict = self._safe_to_dict(data, visited=None)
                                if "lines" in data_dict:
                                    content["layout_payload"] = data_dict
                                    logger.info(f"✅ Extracted layout_payload from payload.data (object) for paragraph at ({x:.1f}, {y:.1f}), lines: {len(data_dict.get('lines', []))}")
                        elif "layout_payload" in payload:
                            content["layout_payload"] = payload["layout_payload"]
                            logger.info(f"✅ Extracted layout_payload from payload.layout_payload for paragraph at ({x:.1f}, {y:.1f})")
                    elif hasattr(payload, "lines"):
                        # payload is ParagraphLayout object - convert to dict
                        logger.warning(f"  payload is object with lines attribute, converting...")
                        payload_dict = self._safe_to_dict(payload, visited=None)
                        logger.warning(f"  converted payload keys: {list(payload_dict.keys())[:10]}")
                        if "lines" in payload_dict:
                            content["layout_payload"] = payload_dict
                            logger.info(f"✅ Extracted layout_payload from payload (object) for paragraph at ({x:.1f}, {y:.1f}), lines: {len(payload_dict.get('lines', []))}")
                        else:
                            logger.warning(f"⚠️ payload object has no lines after conversion, keys: {list(payload_dict.keys())}")
                    else:
                        logger.warning(f"⚠️ payload is neither dict nor has lines attribute, type: {type(payload).__name__}")
                else:
                    logger.warning(f"⚠️ Paragraph at ({x:.1f}, {y:.1f}): no 'payload' in content")
            
            # Final check
            has_layout = bool(content.get("layout_payload") or content.get("_layout_payload"))
            if has_layout:
                layout = content.get("layout_payload") or content.get("_layout_payload")
                has_lines = bool(layout and isinstance(layout, dict) and layout.get("lines"))
                if not has_lines:
                    logger.warning(f"⚠️ Paragraph at ({x:.1f}, {y:.1f}) has layout_payload but no lines! layout keys: {list(layout.keys()) if isinstance(layout, dict) else 'not dict'}")
            else:
                logger.warning(f"⚠️ Paragraph at ({x:.1f}, {y:.1f}) has no layout_payload, content keys: {list(content.keys())[:10]}")

        is_watermark = bool(content.get("is_watermark"))

        if is_watermark:
            opacity = self._get_watermark_opacity(block, content)
            self.renderer.canvas_save_state()
            try:
                if opacity < 0.999:
                    self.renderer.canvas_set_opacity(opacity)
                handler(x, y, width, height, content, block)
            finally:
                self.renderer.canvas_restore_state()
        else:
            handler(x, y, width, height, content, block)

    def _get_watermark_opacity(self, block: LayoutBlock, content: Dict[str, Any]) -> float:
        """
        Determine the opacity for a watermark block.
        """
        if self.watermark_opacity_override is not None:
            return self.watermark_opacity_override

        explicit = self._extract_opacity_value(content, include_generic=True)
        if explicit is None and hasattr(block, "style") and isinstance(block.style, dict):
            explicit = self._extract_opacity_value(block.style, include_generic=False)
        if explicit is not None:
            return max(0.0, min(1.0, explicit))

        block_type = getattr(block, "block_type", "") or ""
        content_type = content.get("type") or content.get("content", {}).get("type", "")
        normalized_type = str(content_type).lower()
        if block_type == "image" or normalized_type == "image":
            return 0.5
        if normalized_type == "vml_shape":
            return 0.3
        return 0.35

    def _extract_opacity_value(self, value: Any, include_generic: bool = True) -> Optional[float]:
        """
        Recursively search for an opacity hint inside a nested content dict/list.
        """
        try_keys = ("watermark_opacity", "opacity") if include_generic else ("watermark_opacity",)
        if isinstance(value, dict):
            for key in try_keys:
                if key in value:
                    try:
                        normalized = float(value[key])
                        return max(0.0, min(1.0, normalized))
                    except (TypeError, ValueError):
                        continue
            for child in value.values():
                result = self._extract_opacity_value(child)
                if result is not None:
                    return result
        elif isinstance(value, (list, tuple)):
            for item in value:
                result = self._extract_opacity_value(item)
                if result is not None:
                    return result
        return None

    @staticmethod
    def _normalize_opacity_value(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            logger.warning(f"Ignoring invalid watermark opacity value: {value}")
            return None
        return max(0.0, min(1.0, normalized))

    # ======================================================================
    # Public entry
    # ======================================================================
    
    def compile(self, unified_layout: UnifiedLayout) -> str:
        """
        Compile UnifiedLayout to PDF using dispatcher-based iteration.
        Iterates over all elements and calls Rust methods with x, y, width, height.
        
        Args:
            unified_layout: UnifiedLayout instance to render
            
        Returns:
            Path to generated PDF file
        """
        import time as time_module
        start_time = time_module.perf_counter()
        timings = {
            "content_prep": 0.0,
            "rust_calls": 0.0,
            "save": 0.0,
            "total": 0.0,
        }
        
        try:
            self._registered_stream_keys.clear()
            # Set total pages for field codes
            total_pages = max(len(unified_layout.pages), 1)
            self.renderer.set_total_pages(total_pages)
            
            logger.info(f"🔄 Rendering {len(unified_layout.pages)} pages (dispatcher-based)...")
            
            # Iterate through pages and blocks, calling Rust methods via dispatcher
            for page in unified_layout.pages:
                # Set current page number
                self.renderer.set_current_page_number(page.number)
                
                # Create new page
                self.renderer.new_page(page.size.width, page.size.height)
                
                # Sort blocks: watermarks first, then headers, body, footnotes, footers
                watermark_blocks = []
                header_blocks = []
                body_blocks = []
                footnote_blocks = []
                footer_blocks = []
                
                t0 = time_module.perf_counter()
                for block in page.blocks:
                    # Get content as dict-ish
                    content = block.content
                    if not isinstance(content, dict):
                        if hasattr(content, "__dict__"):
                            content = {k: v for k, v in content.__dict__.items() if not k.startswith("__")}
                        elif hasattr(content, "to_dict"):
                            content = content.to_dict()
                        else:
                            content = {}
                    
                    header_footer_context = content.get("header_footer_context")
                    
                    # Classification
                    if content.get("is_watermark") or (block.block_type == "textbox" and header_footer_context == "header"):
                        watermark_blocks.append(block)
                    elif block.block_type == "header" or header_footer_context == "header":
                        header_blocks.append(block)
                    elif block.block_type == "footer" or header_footer_context == "footer":
                        footer_blocks.append(block)
                    elif block.block_type == "footnotes":
                        footnote_blocks.append(block)
                    else:
                        body_blocks.append(block)
                timings["content_prep"] += time_module.perf_counter() - t0
                
                # Render in order: watermarks, headers, body, footnotes, footers
                t0 = time_module.perf_counter()
                for block in watermark_blocks:
                    self._render_element(block)
                
                for block in header_blocks:
                    self._render_element(block)
                
                for block in body_blocks:
                    self._render_element(block)
                
                for block in footnote_blocks:
                    self._render_element(block)
                
                for block in footer_blocks:
                    self._render_element(block)
                timings["rust_calls"] += time_module.perf_counter() - t0
            
            elapsed = time_module.perf_counter() - start_time
            logger.info(f"✅ Layout rendered in {elapsed:.2f}s")
            
            # Save PDF
            logger.info(f"💾 Saving PDF to: {self.output_path}")
            output_path = Path(self.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            t0 = time_module.perf_counter()
            self.renderer.save()
            timings["save"] = time_module.perf_counter() - t0
            logger.info("✅ PDF save() completed")
            
            timings["total"] = time_module.perf_counter() - start_time
            logger.info(f"⏱️  Rust compile timings: content_prep={timings['content_prep']:.3f}s, rust_calls={timings['rust_calls']:.3f}s, save={timings['save']:.3f}s, total={timings['total']:.3f}s")
            import sys
            sys.stdout.write(f"RUST_TIMINGS:content_prep={timings['content_prep']:.6f},rust_calls={timings['rust_calls']:.6f},save={timings['save']:.6f},total={timings['total']:.6f}\n")
            sys.stdout.flush()
            
            # Verify file was created
            if output_path.exists():
                file_size = output_path.stat().st_size
                if file_size > 0:
                    logger.info("Registered %d unique image streams", len(self._registered_stream_keys))
                    logger.info(
                        f"✅ PDF generated successfully: {output_path.absolute()} "
                        f"({file_size:,} bytes)"
                    )
                    return str(output_path.absolute())
                else:
                    error_msg = f"PDF file was created but is empty (0 bytes): {output_path.absolute()}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            else:
                error_msg = f"PDF file was not created: {output_path.absolute()}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
                
        except Exception as e:
            logger.error(f"❌ Rust PDF compilation failed: {e}", exc_info=True)
            raise
    
    # ======================================================================
    # Handlers used by dispatcher
    # ======================================================================

    def _handle_paragraph_block(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
        block: LayoutBlock,
    ) -> None:
        logger.debug(f"📄 Rendering paragraph at ({x:.1f}, {y:.1f}), size {width:.1f}x{height:.1f}")
        has_layout = bool(content.get("layout_payload") or content.get("_layout_payload"))
        logger.debug(f"  Has layout_payload: {has_layout}")
        self._render_paragraph_with_lines(x, y, width, height, content)

    def _handle_table_block(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
        block: LayoutBlock,
    ) -> None:
        rows = content.get("rows", [])
        logger.info(f"📊 Rendering table at ({x:.1f}, {y:.1f}), size {width:.1f}x{height:.1f}, rows: {len(rows)}")
        self._render_table_with_cells(x, y, width, height, content)

    def _handle_image_block(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
        block: LayoutBlock,
    ) -> None:
        self._render_image_direct(x, y, width, height, content)

    def _handle_header_block(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
        block: LayoutBlock,
    ) -> None:
        # Headers can be paragraph or more complex block
        if isinstance(content, dict):
            layout_payload = content.get("layout_payload") or content.get("_layout_payload")
            if layout_payload and isinstance(layout_payload, dict) and layout_payload.get("lines"):
                self._render_paragraph_with_lines(x, y, width, height, content)
                return
        self.renderer.render_header_block(x, y, width, height, content)

    def _handle_footer_block(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
        block: LayoutBlock,
    ) -> None:
        if isinstance(content, dict):
            layout_payload = content.get("layout_payload") or content.get("_layout_payload")
            if layout_payload and isinstance(layout_payload, dict) and layout_payload.get("lines"):
                self._render_paragraph_with_lines(x, y, width, height, content)
                return
        self.renderer.render_footer_block(x, y, width, height, content)

    def _handle_footnotes_block(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
        block: LayoutBlock,
    ) -> None:
        # Extract footnotes list from content - no JSON, just values
        footnotes_list = []
        if isinstance(content, dict):
            footnotes = content.get("footnotes", [])
            if isinstance(footnotes, list):
                for footnote in footnotes:
                    if isinstance(footnote, dict):
                        number = str(footnote.get("number", "?"))
                        footnote_content = str(footnote.get("content", ""))
                        footnotes_list.append((number, footnote_content))
        
        logger.info(f"📝 Rendering {len(footnotes_list)} footnotes at ({x:.1f}, {y:.1f}), size {width:.1f}x{height:.1f}")
        if footnotes_list:
            for i, (num, text) in enumerate(footnotes_list[:3]):  # Log first 3
                logger.info(f"  Footnote {i+1}: {num} = {text[:50]}...")
        
        # Call Rust with direct values, no JSON
        self.renderer.render_footnotes_block(x, y, width, height, footnotes_list)

    def _handle_endnotes_block(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
        block: LayoutBlock,
    ) -> None:
        self.renderer.render_endnotes_block(x, y, width, height, content)

    def _handle_rect_block(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
        block: LayoutBlock,
    ) -> None:
        """
        Generic rectangle/textbox/decorator/vml_shape handler.
        """
        style_dict = self._style_to_dict(getattr(block, "style", None))
        fill_color = (
            style_dict.get("fill_color")
            or style_dict.get("background_color")
        )
        stroke_color = (
            style_dict.get("stroke_color")
            or style_dict.get("border_color")
            or style_dict.get("color")
        )
        line_width = (
            style_dict.get("line_width")
            or style_dict.get("border_width")
            or 1.0
        )
        self.renderer.render_rectangle_block(
            x,
            y,
            width,
            height,
            str(fill_color) if fill_color else None,
            str(stroke_color) if stroke_color else None,
            line_width,
        )

    # ======================================================================
    # Paragraph rendering
    # ======================================================================

    def _render_paragraph_with_lines(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
    ) -> None:
        """
        Render paragraph by iterating over lines and items, calling Rust draw_string
        or image methods for each item (once exposed in Rust).
        """
        # Get layout_payload with lines
        layout_payload = content.get("layout_payload") or content.get("_layout_payload")
        if not layout_payload or not isinstance(layout_payload, dict):
            logger.warning(f"⚠️ Paragraph at ({x:.1f}, {y:.1f}) has no layout_payload with lines, skipping")
            logger.debug(f"  Content keys: {list(content.keys())[:10]}")
            return
        
        lines = layout_payload.get("lines", [])
        if not lines:
            logger.warning(f"⚠️ Paragraph at ({x:.1f}, {y:.1f}) has no lines in layout_payload, skipping")
            logger.debug(f"  layout_payload keys: {list(layout_payload.keys())}")
            return
        
        logger.info(f"📝 Rendering paragraph at ({x:.1f}, {y:.1f}) with {len(lines)} lines")
        
        # Call Rust render_paragraph_block which handles layout_payload
        # This method expects content with layout_payload.lines
        self.renderer.render_paragraph_block(x, y, width, height, content)
        return  # Skip the manual iteration below - Rust handles it
        
        # Get paragraph style (for future use if needed)
        style = content.get("style", {}) or {}
        padding = style.get("padding", {})
        if isinstance(padding, (list, tuple)) and len(padding) >= 4:
            padding_top, padding_right, padding_bottom, padding_left = (
                padding[0],
                padding[1],
                padding[2],
                padding[3],
            )
        else:
            padding_top = padding.get("top", 0.0) if isinstance(padding, dict) else 0.0
            padding_right = padding.get("right", 0.0) if isinstance(padding, dict) else 0.0
            padding_bottom = padding.get("bottom", 0.0) if isinstance(padding, dict) else 0.0
            padding_left = padding.get("left", 0.0) if isinstance(padding, dict) else 0.0
        
        text_left = x + padding_left
        text_top = y + height - padding_top  # PDF: Y increases upward
        
        # Iterate over lines and items
        for line in lines:
            if not isinstance(line, dict):
                    continue
            
            baseline_y = line.get("baseline_y", 0.0)
            offset_x = line.get("offset_x", 0.0)
            line_y = text_top - baseline_y  # PDF: Y increases upward
            
            items = line.get("items", [])
            for item in items:
                if not isinstance(item, dict):
                        continue
                
                item_kind = item.get("kind", "text_run")
                item_x = item.get("x", 0.0)
                item_data = item.get("data", {})
                
                match item_kind:
                    case "text_run" | "field":
                        # Extract text
                        text = item_data.get("text") if isinstance(item_data, dict) else None
                        if not text:
                            text = item.get("text")
                        if not text:
                            continue
                        
                        # Get item style
                        item_style = item_data.get("style") if isinstance(item_data, dict) else {}
                        font_name = item_style.get("font_name") or style.get("font_name", "DejaVu Sans")
                        font_size = item_style.get("font_size") or style.get("font_size", 11.0)
                        color = item_style.get("color") or style.get("color", "#000000")
                        
                        # Calculate position
                        text_x = text_left + offset_x + item_x
                        text_y = line_y
                        
                        # Use Rust render_paragraph_block which handles layout_payload
                        # For now, we'll call it once per paragraph with full layout_payload
                        # TODO: Add direct draw_string method to Rust for fine-grained control
                        pass  # Will be handled by render_paragraph_block call below
                    
                    case "inline_image" | "image":
                        # Extract image data
                        image_data = item_data.get("image") if isinstance(item_data, dict) else item_data
                        if not isinstance(image_data, dict):
                            continue
                        
                        stream_key = image_data.get("stream_key")
                        image_path = image_data.get("path") or image_data.get("image_path")
                        item_width = item.get("width", 0.0)
                        item_height = item.get("height", 0.0)
                        item_ascent = item.get("ascent", 0.0)
                        item_descent = item.get("descent", 0.0)
                        
                        # Calculate image position and size
                        image_x = text_left + offset_x + item_x
                        image_y = line_y - (item_ascent + item_descent)  # PDF: Y increases upward
                        image_width = item_width if item_width > 0 else 50.0
                        image_height = (
                            (item_ascent + item_descent)
                            if (item_ascent > 0 or item_descent > 0)
                            else item_height if item_height > 0 else 50.0
                        )
                        
                        # TODO: Replace with Rust draw_image method when available
                        logger.debug(
                            f"Would draw image at ({image_x:.2f}, {image_y:.2f}) "
                            f"size ({image_width:.2f}, {image_height:.2f})"
                        )
                    
                    case _:
                        logger.debug(f"Unknown item kind: {item_kind}, skipping")
        
        # Render overlays if any
        overlays = layout_payload.get("overlays", [])
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            self._render_overlay(overlay)

    # ======================================================================
    # Table rendering
    # ======================================================================

    def _render_table_with_cells(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
    ) -> None:
        """
        Render table by iterating over rows -> cells -> content, calling Rust
        methods for each element.
        """
        rows = content.get("rows", [])
        if not rows:
            logger.warning("Table has no rows, skipping")
            return
        
        # Iterate over rows and cells
        for row in rows:
            if not isinstance(row, dict):
                continue
            
            cells = row.get("cells", [])
            for cell in cells:
                if not isinstance(cell, dict):
                    continue
                
                cell_frame = cell.get("frame", {})
                if isinstance(cell_frame, dict):
                    cell_x = cell_frame.get("x", x)
                    cell_y = cell_frame.get("y", y)
                    cell_width = cell_frame.get("width", width)
                    cell_height = cell_frame.get("height", height)
                else:
                    cell_x, cell_y, cell_width, cell_height = x, y, width, height
                
                # Get cell content
                content_array = cell.get("content")
                if isinstance(content_array, list):
                    for item in content_array:
                        if not isinstance(item, dict):
                                continue
                        
                        layout_payload = item.get("layout_payload") or item.get("_layout_payload")
                        if layout_payload and isinstance(layout_payload, dict) and layout_payload.get("lines"):
                            # Render as paragraph
                            self._render_paragraph_with_lines(
                                cell_x,
                                cell_y,
                                cell_width,
                                cell_height,
                                item,
                            )
                        else:
                            # Try to render as simple element
                            item_type = item.get("type", "paragraph")
                            match item_type:
                                case "paragraph":
                                    text = item.get("text") or ""
                                    runs = item.get("runs", [])
                                    if runs and isinstance(runs, list):
                                        text_parts = []
                                        for run in runs:
                                            if isinstance(run, dict):
                                                run_text = run.get("text", "")
                                                if run_text:
                                                    text_parts.append(run_text)
                                        text = "".join(text_parts)
                                    
                                    if text:
                                        # TODO: direct Rust draw_string in cell
                                        logger.debug(
                                            f"Would draw text in cell at ({cell_x:.2f}, {cell_y:.2f}): "
                                            f"'{text[:50]}...'"
                                        )
                                
                                case "image":
                                    self._render_image_direct(
                                        cell_x,
                                        cell_y,
                                        cell_width,
                                        cell_height,
                                        item,
                                    )
                                
                                case _:
                                    logger.debug(f"Unknown item type in cell: {item_type}, skipping")
                
                # TODO: Render cell borders via renderer.draw_rect / rectangle if exposed

    # ======================================================================
    # Image rendering
    # ======================================================================

    def _render_image_direct(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        content: Dict[str, Any],
    ) -> None:
        """
        Render image by calling Rust render_image_block or render_image_block_stream
        with x, y, width, height.
        """
        # Extract image data
        image_data = content.get("data") if isinstance(content.get("data"), dict) else content
        image_path = content.get("path") or content.get("image_path") or ""
        if isinstance(image_data, dict) and not image_path:
            image_path = image_data.get("path") or image_data.get("image_path") or ""
        
        resolved_path = self._resolve_image_path(image_data or content)
        if resolved_path:
            image_path = resolved_path
        
        stream_key = None
        if isinstance(image_data, dict):
            stream_key = image_data.get("stream_key")
            registered = self._register_image_stream(image_data, resolved_path)
            if registered:
                stream_key = registered
        elif isinstance(content, dict):
            stream_key = content.get("stream_key")
            registered = self._register_image_stream(content, resolved_path)
            if registered:
                stream_key = registered
        
        width_emu = content.get("width_emu") or content.get("width")
        height_emu = content.get("height_emu") or content.get("height")
        numeric_width = width_emu if isinstance(width_emu, (int, float)) else None
        numeric_height = height_emu if isinstance(height_emu, (int, float)) else None
        
        if stream_key:
            self.renderer.render_image_block_stream(
                x,
                y,
                width,
                height,
                str(stream_key),
                numeric_width,
                numeric_height,
            )
        elif image_path:
            self.renderer.render_image_block(
                x,
                y,
                width,
                height,
                str(image_path),
                numeric_width,
                numeric_height,
            )
        else:
            logger.warning("Image block missing path and stream_key")

    # ======================================================================
    # Overlay rendering
    # ======================================================================

    def _render_overlay(self, overlay: Dict[str, Any]) -> None:
        """
        Render overlay (floating image/textbox) by calling Rust methods with
        x, y, width, height.
        """
        frame = overlay.get("frame", {})
        if not isinstance(frame, dict):
            return
        
        overlay_x = frame.get("x", 0.0)
        overlay_y = frame.get("y", 0.0)
        overlay_width = frame.get("width", 0.0)
        overlay_height = frame.get("height", 0.0)
        
        overlay_kind = overlay.get("kind", "image")
        payload = overlay.get("payload", {})
        
        match overlay_kind:
            case "image":
                image_data = payload.get("image") if isinstance(payload, dict) else payload
                if isinstance(image_data, dict):
                    stream_key = image_data.get("stream_key")
                    image_path = image_data.get("path") or image_data.get("image_path")
                    if stream_key or image_path:
                        # TODO: Replace with Rust overlay draw_image
                        logger.debug(
                            f"Would draw overlay image at ({overlay_x:.2f}, {overlay_y:.2f}) "
                            f"size ({overlay_width:.2f}, {overlay_height:.2f})"
                        )
            
            case "textbox":
                textbox_content = payload.get("content") if isinstance(payload, dict) else payload
                if isinstance(textbox_content, dict):
                    layout_payload = (
                        textbox_content.get("layout_payload")
                        or textbox_content.get("_layout_payload")
                    )
                    if layout_payload and isinstance(layout_payload, dict) and layout_payload.get("lines"):
                        self._render_paragraph_with_lines(
                            overlay_x,
                            overlay_y,
                            overlay_width,
                            overlay_height,
                            textbox_content,
                        )
            
            case _:
                logger.debug(f"Unknown overlay kind: {overlay_kind}, skipping")

    # ======================================================================
    # Helpers
    # ======================================================================

    def _prepare_content_for_renderer(self, content: Any) -> Dict[str, Any]:
        """
        Prepare content for renderer by converting to dict and ensuring
        layout_payload exists if needed.
        Safely handles circular references by using visited set.
        """
        if isinstance(content, dict):
            return content
        
        # Use safe conversion that handles circular references
        return self._safe_to_dict(content, visited=None)
    
    def _safe_to_dict(self, obj: Any, visited: Optional[Set[int]] = None, depth: int = 0) -> Dict[str, Any]:
        """
        Safely convert object to dict, handling circular references.
        """
        # Prevent infinite recursion
        if depth > 10:
            return {"_error": "max_depth_exceeded", "_type": type(obj).__name__}
        
        if visited is None:
            visited = set()
        
        obj_id = id(obj)
        if obj_id in visited:
            return {"_circular_ref": type(obj).__name__}
        
        visited.add(obj_id)
        
        try:
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    if isinstance(k, str) and not k.startswith("__"):
                        result[k] = self._safe_to_dict(v, visited, depth + 1)
                return result
            
            elif isinstance(obj, (list, tuple)):
                return [self._safe_to_dict(item, visited, depth + 1) for item in obj]
            
            elif is_dataclass(obj):
                result = {}
                for field in fields(obj):
                    field_name = field.name
                    if field_name.startswith("_"):
                            continue
                    try:
                        field_value = getattr(obj, field_name, None)
                        if field_value is not None:
                            result[field_name] = self._safe_to_dict(field_value, visited, depth + 1)
                    except Exception:
                        continue
                return result
            
            elif hasattr(obj, "to_dict"):
                try:
                    dict_result = obj.to_dict()
                    if isinstance(dict_result, dict):
                        return self._safe_to_dict(dict_result, visited, depth + 1)
                    return dict_result
                except Exception:
                    pass
            
            elif hasattr(obj, "__dict__"):
                result = {}
                for k, v in obj.__dict__.items():
                    if not k.startswith("__"):
                        try:
                            result[k] = self._safe_to_dict(v, visited, depth + 1)
                        except Exception:
                            continue
                return result
            
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            
            else:
                # Fallback: return string representation
                return {"_type": type(obj).__name__, "_repr": str(obj)[:100]}
        
        finally:
            visited.discard(obj_id)
    
    def _style_to_dict(self, style: Any) -> Dict[str, Any]:
        """Convert style to dict."""
        if isinstance(style, dict):
            return style
        elif is_dataclass(style):
            return asdict(style)
        elif hasattr(style, "__dict__"):
            return {k: v for k, v in style.__dict__.items() if not k.startswith("__")}
        else:
            return {}
    
    def _resolve_image_path(self, image: Any) -> Optional[str]:
        """Resolve image path from image object/dict."""
        if isinstance(image, dict):
            return image.get("path") or image.get("src") or image.get("image_path")
        elif hasattr(image, "path"):
            return getattr(image, "path", None) or getattr(image, "image_path", None)
        return None
    
    def _register_image_stream(
        self,
        image_data: Dict[str, Any],
        resolved_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Register image as stream and return stream_key.
        Returns None if image cannot be registered.
        """
        # Check if already registered
        stream_key = image_data.get("stream_key")
        if stream_key and stream_key in self.image_streams:
            return stream_key
        
        # Load image bytes
        image_bytes, mime_type = self._load_image_bytes_for_stream(image_data, resolved_path)
        if not image_bytes:
            return None
        
        # Generate stream_key
        if not stream_key:
            if resolved_path:
                stream_key = f"img_{hashlib.md5(resolved_path.encode()).hexdigest()[:8]}"
            else:
                stream_key = f"img_{hashlib.md5(image_bytes).hexdigest()[:8]}"
        
        # Store in image_streams
        self.image_streams[stream_key] = image_bytes
        
        # Register with Rust renderer
        try:
            self.renderer.register_image_stream(stream_key, image_bytes, mime_type)
            self._registered_stream_keys.add(stream_key)
            return stream_key
        except Exception as e:
            logger.warning(f"Failed to register image stream: {e}")
            return None
    
    def _load_image_bytes_for_stream(
        self,
        image_data: Dict[str, Any],
        resolved_path: Optional[str] = None,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Load image bytes for streaming to Rust.
        Returns (bytes, mime_type) or (None, None) if failed.
        For WMF/EMF, returns raw bytes with mime_type=None so Rust can handle conversion.
        """
        image_path = resolved_path or image_data.get("path") or image_data.get("image_path")
        
        # Try to load from package_reader
        if self.package_reader and image_path:
            try:
                raw_data = self.package_reader.get_binary_content(image_path)
                if raw_data:
                    # WMF/EMF detection (let Rust convert)
                    if len(raw_data) > 0:
                        if raw_data[:2] == b"\x01\x00" or raw_data[:4] == b"\x01\x00\x00\x00":
                            return raw_data, None
                        mime_type, _ = mimetypes.guess_type(image_path)
                        return raw_data, mime_type
            except Exception as e:
                logger.debug(f"Failed to load image from package_reader: {e}")
        
        # Try filesystem
        if image_path and Path(image_path).exists():
            try:
                raw_data = Path(image_path).read_bytes()
                mime_type, _ = mimetypes.guess_type(image_path)
                return raw_data, mime_type
            except Exception as e:
                logger.debug(f"Failed to load image from filesystem: {e}")

        return None, None
