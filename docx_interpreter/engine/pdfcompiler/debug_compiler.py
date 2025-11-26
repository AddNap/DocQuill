"""
Debugowy PDF Compiler — wizualizacja układu stron i bloków (ramki, typy).
Renderuje obrazy, tekst, nagłówki, stopki, textboxy itp. z informacjami debugowymi.
"""

from pathlib import Path
from typing import Optional, Any, Dict, List
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color, black, red, blue, green, yellow, magenta, cyan
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import logging
from ..layout_primitives import BlockContent, ParagraphLayout, GenericLayout
from ..unified_layout import LayoutBlock
from ..geometry import Rect, emu_to_points
from ..assembler.utils import parse_cell_margins

logger = logging.getLogger(__name__)


class DebugPDFCompiler:
    def __init__(self, output_path: str = "layout_debug.pdf", package_reader: Optional[Any] = None):
        """
        Inicjalizacja DebugPDFCompiler.
        
        Args:
            output_path: Ścieżka do pliku wyjściowego PDF
            package_reader: PackageReader do rozwiązywania ścieżek obrazów (opcjonalne)
        """
        self.output_path = output_path
        self.package_reader = package_reader

    def compile(self, unified_layout):
        """
        Tworzy PDF pokazujący układ bloków i stron z UnifiedLayout.
        """
        c = canvas.Canvas(self.output_path, pagesize=A4)

        for page in unified_layout.pages:
            self._render_page(c, page)
            c.showPage()

        c.save()
        print(f"✅ Layout debug PDF zapisany jako: {self.output_path}")

    # ------------------------------------------------------------------
    def _render_page(self, c, page):
        """Rysuje pojedynczą stronę z blokami."""
        width = page.size.width
        height = page.size.height

        # Ramka strony (zewnętrzna)
        c.setStrokeColor(black)
        c.setLineWidth(1)
        c.rect(0, 0, width, height)

        # Marginesy
        m = page.margins
        c.setStrokeColor(Color(0.7, 0.7, 0.7))
        c.setLineWidth(0.5)
        c.setDash([2, 2])
        c.rect(m.left, m.bottom, width - m.left - m.right, height - m.top - m.bottom)
        c.setDash()

        # Nagłówek strony
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(black)
        c.drawString(40, height - 20, f"Page {page.number}")

        # Sortuj bloki: najpierw nagłówki, potem body, potem stopki
        header_blocks = []
        footer_blocks = []
        body_blocks = []
        
        logger.info(f"Page {page.number}: Total blocks: {len(page.blocks)}")
        
        for i, block in enumerate(page.blocks):
            # Sprawdź czy blok należy do nagłówka/stopki na podstawie block_type lub header_footer_context
            content_obj = block.content
            if isinstance(content_obj, BlockContent):
                content = content_obj.raw or {}
            else:
                content = content_obj or {}
            header_footer_context = content.get("header_footer_context", "")
            
            # Loguj wszystkie bloki z nagłówkami/stopkami
            if header_footer_context or block.block_type in ("header", "footer"):
                logger.info(f"  Block {i}: type={block.block_type}, header_footer_context={header_footer_context}, "
                           f"x={block.frame.x:.2f}, y={block.frame.y:.2f}, w={block.frame.width:.2f}, h={block.frame.height:.2f}")
            
            if block.block_type == "header" or header_footer_context == "header":
                header_blocks.append(block)
                logger.info(f"  Added to header_blocks: type={block.block_type}, "
                          f"header_footer_context={header_footer_context}, "
                          f"x={block.frame.x:.2f}, y={block.frame.y:.2f}")
            elif block.block_type == "footer" or header_footer_context == "footer":
                footer_blocks.append(block)
                logger.info(f"  Added to footer_blocks: type={block.block_type}, "
                          f"header_footer_context={header_footer_context}, "
                          f"x={block.frame.x:.2f}, y={block.frame.y:.2f}")
            else:
                body_blocks.append(block)
                if header_footer_context:
                    logger.warning(f"  Block with header_footer_context={header_footer_context} added to body_blocks: "
                                 f"type={block.block_type}, x={block.frame.x:.2f}, y={block.frame.y:.2f}")
        
        logger.info(f"  Sorted: {len(header_blocks)} header blocks, {len(body_blocks)} body blocks, {len(footer_blocks)} footer blocks")
        
        # Renderuj w kolejności: headers, body, footers
        for block in header_blocks:
            self._draw_block(c, block)
        for block in body_blocks:
            self._draw_block(c, block)
        for block in footer_blocks:
            self._draw_block(c, block)

    # ------------------------------------------------------------------
    @staticmethod
    def _paragraph_layout_height(payload: Optional[ParagraphLayout]) -> float:
        """Zwraca wysokość paragrafu bazując na ParagraphLayout."""
        if not isinstance(payload, ParagraphLayout):
            return 0.0
        padding_top = padding_bottom = 0.0
        if getattr(payload, "style", None) and getattr(payload.style, "padding", None):
            padding_top, _, padding_bottom, _ = payload.style.padding
        if not payload.lines:
            return padding_top + padding_bottom
        last_line = payload.lines[-1]
        text_height = last_line.baseline_y + last_line.height
        return padding_top + text_height + padding_bottom

    @staticmethod
    def _extract_paragraph_payload(content_item: Any) -> Optional[ParagraphLayout]:
        """Pobiera ParagraphLayout z elementu zawartości, jeśli istnieje."""
        payload = None
        if isinstance(content_item, dict):
            payload = content_item.get("layout_payload") or content_item.get("_layout_payload")
        elif hasattr(content_item, "layout_payload"):
            payload = getattr(content_item, "layout_payload")
        elif hasattr(content_item, "_layout_payload"):
            payload = getattr(content_item, "_layout_payload")
        return payload if isinstance(payload, ParagraphLayout) else None

    @staticmethod
    def _image_unique_key(image: Any) -> str:
        if isinstance(image, dict):
            path = image.get("path") or image.get("image_path")
            rel_id = image.get("relationship_id") or image.get("rel_id")
        else:
            path = getattr(image, "path", None) or getattr(image, "image_path", None)
            rel_id = getattr(image, "relationship_id", None) or getattr(image, "rel_id", None)
        if path:
            return f"path::{path}"
        if rel_id:
            return f"rel::{rel_id}"
        return f"obj::{id(image)}"

    # ------------------------------------------------------------------
    def _draw_block(self, c, block):
        """Rysuje ramkę, etykietę i zawartość dla bloku."""
        rect = block.frame
        x, y, w, h = rect.x, rect.y, rect.width, rect.height

        # Logowanie dla każdego bloku
        content_obj = block.content
        if isinstance(content_obj, BlockContent):
            payload = content_obj.payload
            content = content_obj.raw or {}
        else:
            payload = None
            content = content_obj or {}
        header_footer_context = content.get("header_footer_context", "")
        logger.info(f"Rendering block: type={block.block_type}, page={block.page_number}, "
                   f"x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}, "
                   f"header_footer_context={header_footer_context}")

        # Kolor w zależności od typu
        color_map = {
            "paragraph": blue,
            "image": green,
            "table": red,
            "textbox": Color(0.8, 0.5, 0.0),  # Pomarańczowy
            "header": magenta,
            "footer": cyan,
        }
        color = color_map.get(block.block_type, black)

        # Renderuj zawartość w zależności od typu
        if block.block_type == "image":
            self._draw_image_block(c, block, color)
        elif block.block_type == "paragraph":
            self._draw_paragraph_block(c, block, color)
        elif block.block_type == "table":
            self._draw_table_block(c, block, color)
        elif block.block_type == "textbox":
            self._draw_textbox_block(c, block, color)
        elif block.block_type in ("header", "footer"):
            self._draw_header_footer_block(c, block, color)
        else:
            # Domyślny renderer dla nieznanych typów
            self._draw_generic_block(c, block, color)

    def _draw_image_block(self, c, block, color):
        """Renderuje blok obrazu - tylko ramka i etykieta."""
        rect = block.frame
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        
        content_obj = block.content
        if isinstance(content_obj, BlockContent):
            content = content_obj.raw or {}
        else:
            content = content_obj or {}
        header_footer_context = content.get("header_footer_context", "")
        
        logger.info(f"  Drawing IMAGE block: x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}, header_footer_context={header_footer_context}")
        
        
        # Spróbuj pobrać ścieżkę obrazu (tylko do sprawdzenia czy istnieje)
        path = content.get("path") or content.get("src") or content.get("image_path")
        
        # Jeśli nie ma ścieżki, spróbuj pobrać z relationship_id
        if not path and self.package_reader:
            rel_id = content.get("relationship_id") or content.get("rel_id")
            relationship_source = content.get("relationship_source") or content.get("part_path")
            
            if rel_id and relationship_source:
                try:
                    # Pobierz relationship target
                    if not relationship_source.endswith('.rels'):
                        if relationship_source.startswith("word/"):
                            part_name = relationship_source.replace("word/", "")
                            relationship_source = f"word/_rels/{part_name}.rels"
                        else:
                            relationship_source = f"word/_rels/{relationship_source}.rels"
                    
                    relationships = self.package_reader.get_relationships(relationship_source)
                    if relationships and rel_id in relationships:
                        rel_data = relationships[rel_id]
                        rel_target = rel_data.get("target", "")
                        if rel_target:
                            extract_to = self.package_reader.extract_to
                            if rel_target.startswith("word/"):
                                image_path = Path(extract_to) / rel_target
                            else:
                                image_path = Path(extract_to) / "word" / rel_target
                            if image_path.exists():
                                path = str(image_path)
                except Exception:
                    pass
        
        # Ramka obrazu
        c.setStrokeColor(color)
        c.setLineWidth(1.5)
        c.rect(x, y, w, h)
        
        # Etykieta
        c.setFont("Helvetica", 7)
        c.setFillColor(color)
        label = f"IMAGE (p.{block.page_number})"
        if header_footer_context:
            label += f" [{header_footer_context.upper()}]"
        if path:
            label += f" ✓"
        else:
            rel_id = content.get("relationship_id") or content.get("rel_id") or "?"
            label += f" ✗ [{rel_id}]"
        c.drawString(x + 3, y + h - 12, label)

    def _draw_paragraph_block(self, c, block, color):
        """Renderuje blok paragrafu - tylko ramka i etykieta."""
        rect = block.frame
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        
        content_obj = block.content
        if isinstance(content_obj, BlockContent):
            payload = content_obj.payload
            content = content_obj.raw or {}
        else:
            payload = None
            content = content_obj or {}

        text = content.get("text", "")
        images = list(content.get("images", []) or [])
        textboxes = list(content.get("textboxes", []) or [])
        fields = content.get("fields", [])
        style_dict = content.get("style", {}) or {}
        indent_dict = content.get("indent") or style_dict.get("indent") or {}
        if not isinstance(indent_dict, dict):
            indent_dict = {}

        def _pt(value: Any) -> float:
            if value is None or value == "":
                return 0.0
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        def _maybe_float(value: Any) -> Optional[float]:
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        indent_left = _pt(indent_dict.get("left_pt") or indent_dict.get("left"))
        indent_right = _pt(indent_dict.get("right_pt") or indent_dict.get("right"))
        indent_hanging = _pt(indent_dict.get("hanging_pt") or indent_dict.get("hanging"))
        indent_first_line = _pt(indent_dict.get("first_line_pt") or indent_dict.get("first_line"))
        text_position = _pt(indent_dict.get("text_position_pt")) or indent_first_line or indent_left

        layout_metrics = content.get("layout_metrics") or {}
        indent_metrics_meta = layout_metrics.get("indent_metrics")
        if isinstance(payload, ParagraphLayout) and not indent_metrics_meta:
            indent_metrics_meta = payload.metadata.get("indent_metrics")

        if indent_metrics_meta:
            meta_left = _maybe_float(indent_metrics_meta.get("left"))
            if meta_left is not None:
                indent_left = meta_left
            meta_right = _maybe_float(indent_metrics_meta.get("right"))
            if meta_right is not None:
                indent_right = meta_right
            meta_hanging = _maybe_float(indent_metrics_meta.get("hanging"))
            if meta_hanging is not None:
                indent_hanging = meta_hanging
            meta_first = _maybe_float(indent_metrics_meta.get("first_line"))
            if meta_first is not None:
                indent_first_line = meta_first
            meta_text_pos = _maybe_float(indent_metrics_meta.get("text_position"))
            if meta_text_pos is not None:
                text_position = meta_text_pos

        marker = content.get("marker")
        lines_data = content.get("lines") or []
        block_top = y + h

        baselines: List[float] = []

        def _compute_line_baseline(idx: int, entry: Dict[str, Any]) -> float:
            offset_val = entry.get("offset_baseline")
            if offset_val not in (None, ""):
                try:
                    return block_top - float(offset_val)
                except (TypeError, ValueError):
                    pass

            entry_layout = entry.get("layout")
            font_local = _maybe_float(style_dict.get("font_size")) or 11.0
            line_height_local = font_local * 1.2
            if entry_layout:
                if isinstance(entry_layout, dict):
                    font_candidate = _maybe_float(entry_layout.get("font_size"))
                    if font_candidate is not None:
                        font_local = font_candidate
                    height_candidate = _maybe_float(entry_layout.get("height"))
                    if height_candidate is not None:
                        line_height_local = height_candidate
                elif hasattr(entry_layout, "font_size"):
                    font_candidate = _maybe_float(getattr(entry_layout, "font_size", None))
                    if font_candidate is not None:
                        font_local = font_candidate
                    height_candidate = _maybe_float(getattr(entry_layout, "height", None))
                    if height_candidate is not None:
                        line_height_local = height_candidate
            ascent = font_local * 0.8
            if idx == 0:
                return block_top - ascent
            prev_baseline = baselines[idx - 1] if len(baselines) > idx - 1 else block_top - ascent
            return prev_baseline - line_height_local

        first_line_baseline = None
        if lines_data:
            first_line_baseline = _compute_line_baseline(0, lines_data[0])
            baselines.append(first_line_baseline)

        header_footer_context = content.get("header_footer_context", "")
        if isinstance(payload, ParagraphLayout) and payload.overlays:
            overlay_images = [ov.payload for ov in payload.overlays if ov.kind == "image"]
            overlay_textboxes = [ov.payload for ov in payload.overlays if ov.kind == "textbox"]
            images.extend(overlay_images)

            # Anchored textboxes są już renderowane jako overlay, usuń je z listy tekstboxów
            def _is_anchored(tb: Any) -> bool:
                if isinstance(tb, dict):
                    anchor_type = str(tb.get("anchor_type") or "").lower()
                    position = tb.get("position") or {}
                    return anchor_type == "anchor" and bool(position)
                if hasattr(tb, "textbox_anchor_info"):
                    info = getattr(tb, "textbox_anchor_info", {}) or {}
                    anchor_type = str(info.get("anchor_type") or "").lower()
                    position = info.get("position") or {}
                    return anchor_type == "anchor" and bool(position)
                return False

            textboxes = [tb for tb in textboxes if not _is_anchored(tb)]
        
        text_frame = layout_metrics.get("text_frame")
        if isinstance(payload, ParagraphLayout) and not text_frame:
            text_frame = payload.metadata.get("text_frame")

        area_x = _maybe_float(text_frame.get("abs_area_x")) if text_frame else None
        area_width = _maybe_float(text_frame.get("abs_width")) if text_frame else None
        first_line_offset = _maybe_float(text_frame.get("x")) if text_frame else None
        first_line_x = _maybe_float(text_frame.get("abs_first_line_x")) if text_frame else None

        if area_x is None:
            area_x = x
        if area_width is None or area_width <= 0.0:
            area_width = w
        if first_line_offset is None:
            first_line_offset = text_position - indent_left
        if first_line_x is None:
            first_line_x = area_x + first_line_offset

        base_x = area_x - indent_left

        marker_number_pos = None
        marker_text_pos = None
        marker_relative = None
        marker_abs_x = None
        if marker:
            marker_number_pos = _maybe_float(marker.get("number_position"))
            marker_text_pos = _maybe_float(marker.get("text_position"))
            marker_relative = _maybe_float(marker.get("relative_to_text"))
            marker_abs_x = _maybe_float(marker.get("x"))

        if marker_number_pos is None and indent_metrics_meta:
            meta_number = _maybe_float(indent_metrics_meta.get("number_position"))
            if meta_number is not None:
                marker_number_pos = meta_number
        if marker_text_pos is None and indent_metrics_meta:
            meta_text = _maybe_float(indent_metrics_meta.get("text_position"))
            if meta_text is not None:
                marker_text_pos = meta_text

        if marker_number_pos is None:
            marker_number_pos = indent_left - indent_hanging
        if marker_text_pos is None:
            marker_text_pos = text_position

        if marker_abs_x is None:
            if marker_relative is not None:
                marker_abs_x = first_line_x + marker_relative
            else:
                marker_abs_x = area_x - indent_hanging

        inline_indent_meta = layout_metrics.get("inline_indent") if isinstance(layout_metrics, dict) else {}
        if inline_indent_meta is None:
            inline_indent_meta = {}
        inline_indent_source = {}
        if isinstance(content, dict):
            inline_indent_source = content.get("inline_indent") or {}
        inline_left = _maybe_float(inline_indent_meta.get("left_pt"))
        if inline_left is None:
            inline_left = _maybe_float(inline_indent_source.get("left_pt"))
        inline_first = _maybe_float(inline_indent_meta.get("first_line_pt"))
        if inline_first is None:
            inline_first = _maybe_float(inline_indent_source.get("first_line_pt"))
        inline_indicator_x = None
        if inline_left is not None and inline_left > 0.0 and not marker:
            inline_indicator_x = base_x + inline_left

        text_x = first_line_x
        number_x = marker_abs_x if marker_abs_x is not None else area_x - indent_hanging
        text_width = max(0.0, area_width)

        # Visual guides: margin, marker, text, area, inline indents
        c.saveState()
        c.setLineWidth(0.6)
        c.setDash(1, 0)
        c.setStrokeColor(Color(0, 0, 0))
        c.line(base_x, y, base_x, y + h)

        # Fill left indent area (blue)
        left_indent_width = max(0.0, area_x - base_x)
        if left_indent_width > 0.0:
            c.setFillColor(Color(0.25, 0.45, 0.95))
            try:
                c.setFillAlpha(0.18)
            except AttributeError:
                pass
            c.rect(base_x, y, left_indent_width, h, fill=1, stroke=0)
            try:
                c.setFillAlpha(1.0)
            except AttributeError:
                pass

        # Fill first-line indent (if different) with lighter blue
        first_line_span = max(0.0, first_line_x - area_x)
        if first_line_span > 0.0:
            c.setFillColor(Color(0.35, 0.55, 1.0))
            try:
                c.setFillAlpha(0.18)
            except AttributeError:
                pass
            c.rect(area_x, y, first_line_span, h, fill=1, stroke=0)
            try:
                c.setFillAlpha(1.0)
            except AttributeError:
                pass

        if marker or indent_hanging:
            c.setStrokeColor(Color(0.95, 0.1, 0.1))
            c.setDash(2, 2)
            c.line(number_x, y, number_x, y + h)

        c.setStrokeColor(Color(0.1, 0.8, 0.1))
        c.setDash(1, 2)
        c.line(text_x, y, text_x, y + h)

        c.setStrokeColor(Color(0.15, 0.45, 0.95))
        c.setDash(3, 2)
        c.line(area_x, y, area_x, y + h)

        if inline_indicator_x is not None:
            c.setStrokeColor(Color(0.5, 0.35, 0.9))
            c.setDash(1, 3)
            c.line(inline_indicator_x, y, inline_indicator_x, y + h)
        c.restoreState()

        if text_width > 0.0:
            c.saveState()
            c.setStrokeColor(Color(0.1, 0.6, 0.1))
            c.setLineWidth(0.9)
            c.setDash(1, 0)
            c.rect(area_x, y, text_width, h)
            c.restoreState()

        if marker:
            list_box_left = min(number_x, area_x)
            list_box_right = max(area_x + text_width, number_x)
            c.saveState()
            c.setStrokeColor(Color(0.95, 0.75, 0.15))
            c.setLineWidth(0.7)
            c.setDash(4, 2)
            c.rect(list_box_left, y, list_box_right - list_box_left, h)
            c.restoreState()

        marker_label = "MARKER"
        block_label = "BLOCK"
        if marker:
            marker_text = marker.get("text", "") or "·"
            suffix = marker.get("suffix", "")
            alignment = marker.get("alignment", "")
            baseline_offset = float(marker.get("baseline_offset", 0.0))
            marker_baseline_y = first_line_baseline if first_line_baseline is not None else y + h - baseline_offset
            c.setFillColor(Color(0.2, 0.2, 0.8))
            c.setFont("Helvetica-Bold", 9)
            c.drawString(number_x, marker_baseline_y, marker_text)
            marker_label = (
                f"MARKER text='{marker_text.strip() or marker_text}' num={marker_number_pos:.1f} "
                f"text={marker_text_pos:.1f} suffix={suffix or '-'} align={alignment or '-'}"
            )
        else:
            marker_label = f"MARKER num={marker_number_pos:.1f} text={marker_text_pos:.1f} (computed)"

        inline_label = ""
        if inline_left is not None and inline_left > 0.0 and not marker:
            inline_label = f" inline_left={inline_left:.1f}"
            if inline_first is not None:
                inline_label += f" inline_first={inline_first:.1f}"

        block_label = (
            f"BLOCK left={indent_left:.1f} first={indent_first_line:.1f} hang={indent_hanging:.1f} "
            f"text={marker_text_pos:.1f} right={indent_right:.1f} w={text_width:.1f}{inline_label}"
        )

        # Draw labels inside block (top-left corner)
        c.setFillColor(color)
        c.setFont("Helvetica", 6)
        label_y = y + h - 8
        c.drawString(x + 3, label_y, marker_label)
        c.drawString(x + 3, label_y - 9, block_label)

        logger.info(f"  Drawing PARAGRAPH block: x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}, "
                   f"images={len(images)}, textboxes={len(textboxes)}, header_footer_context={header_footer_context}")
        
        if isinstance(payload, ParagraphLayout) and payload.overlays:
            logger.info(f"    Paragraph payload has {len(payload.overlays)} overlays")
            for overlay in payload.overlays:
                if overlay.kind == "image":
                    overlay_block = LayoutBlock(
                        frame=overlay.frame,
                        block_type="image",
                        content=overlay.payload,
                        style={},
                        page_number=block.page_number,
                    )
                    self._draw_image_block(c, overlay_block, green)
                elif overlay.kind == "textbox":
                    overlay_block = LayoutBlock(
                        frame=overlay.frame,
                        block_type="textbox",
                        content=overlay.payload,
                        style={},
                        page_number=block.page_number,
                    )
                    textbox_color = Color(0.8, 0.5, 0.0)
                    self._draw_textbox_block(c, overlay_block, textbox_color)

        # Sprawdź czy paragraf ma textboxy z pozycjonowaniem absolutnym
        # Jeśli tak, renderuj je jako osobne bloki textboxów
        for i, textbox in enumerate(textboxes):
            logger.info(f"    Textbox {i+1} in paragraph: {type(textbox).__name__}")
            if isinstance(textbox, dict):
                anchor_type = textbox.get("anchor_type", "")
                position = textbox.get("position", {})
                logger.info(f"      anchor_type={anchor_type}, position={position}, position type={type(position)}, position bool={bool(position)}")
                condition_check = anchor_type == "anchor" and position
                logger.info(f"      Condition check: anchor_type == 'anchor' = {anchor_type == 'anchor'}, position = {bool(position)}, combined = {condition_check}")
                if anchor_type == "anchor" and position:
                    logger.info(f"      Processing absolute positioned textbox: anchor_type={anchor_type}, position={position}")
                    try:
                        # To jest textbox z pozycjonowaniem absolutnym - renderuj jako osobny blok textboxu
                        logger.info(f"      Imports successful")
                        
                        # Oblicz współrzędne textboxu
                        x_offset_emu = position.get("x", 0)
                        y_offset_emu = position.get("y", 0)
                        x_rel = position.get("x_rel", "")
                        y_rel = position.get("y_rel", "")
                        
                        logger.info(f"      Offsets: x_offset_emu={x_offset_emu}, y_offset_emu={y_offset_emu}, x_rel={x_rel}, y_rel={y_rel}")
                        
                        x_offset_pt = emu_to_points(x_offset_emu)
                        y_offset_pt = emu_to_points(y_offset_emu)
                        
                        # Oblicz współrzędne w zależności od relativeFrom
                        # Użyj współrzędnych z bloku paragrafu, które już są obliczone
                        # w _create_footer_blocks dla textboxów z pozycjonowaniem absolutnym
                        textbox_x = x  # Użyj x z bloku paragrafu (już obliczone dla textboxu z pozycjonowaniem absolutnym)
                        textbox_y = y  # Użyj y z bloku paragrafu (już obliczone dla textboxu z pozycjonowaniem absolutnym)
                        
                        width_emu = textbox.get("width", 0)
                        height_emu = textbox.get("height", 0)
                        textbox_w = emu_to_points(width_emu) if width_emu else w
                        textbox_h = emu_to_points(height_emu) if height_emu else h
                        
                        logger.info(f"      Textbox dimensions: width_emu={width_emu}, height_emu={height_emu}, textbox_w={textbox_w:.2f}, textbox_h={textbox_h:.2f}")
                        
                        # Utwórz tymczasowy blok textboxu do renderowania
                        textbox_rect = Rect(x=textbox_x, y=textbox_y, width=textbox_w, height=textbox_h)
                        logger.info(f"      Creating textbox block from paragraph textbox: "
                                   f"x={textbox_x:.2f}, y={textbox_y:.2f}, w={textbox_w:.2f}, h={textbox_h:.2f}")
                        # Dodaj header_footer_context do textboxu, jeśli paragraf ma ten kontekst
                        textbox_content = textbox.copy() if isinstance(textbox, dict) else textbox
                        if isinstance(textbox_content, dict):
                            textbox_content["header_footer_context"] = header_footer_context
                        
                        textbox_block = LayoutBlock(
                            frame=textbox_rect,
                            block_type="textbox",
                            content=textbox_content,
                            style={},
                            page_number=block.page_number
                        )
                        # Renderuj jako blok textboxu
                        logger.info(f"      Calling _draw_textbox_block for textbox block")
                        textbox_color = Color(0.8, 0.5, 0.0)  # Pomarańczowy
                        self._draw_textbox_block(c, textbox_block, textbox_color)
                        logger.info(f"      Textbox block rendered successfully")
                    except Exception as e:
                        logger.error(f"      Error processing absolute positioned textbox: {e}", exc_info=True)
                else:
                    logger.info(f"      Skipping textbox: anchor_type={anchor_type}, position={position}, condition={anchor_type == 'anchor' and bool(position)}")
            else:
                # Textbox może być obiektem Run z textbox_anchor_info
                if hasattr(textbox, 'textbox_anchor_info') and textbox.textbox_anchor_info:
                    logger.info(f"      Textbox is Run object with textbox_anchor_info, converting to dict")
                    anchor_info = textbox.textbox_anchor_info
                    textbox_dict = {
                        "type": "textbox",
                        "anchor_type": anchor_info.get('anchor_type', 'inline'),
                        "position": anchor_info.get('position', {}),
                        "width": anchor_info.get('width', 0),
                        "height": anchor_info.get('height', 0),
                        "content": textbox
                    }
                    # Przetwórz jako dict
                    anchor_type = textbox_dict.get("anchor_type", "")
                    position = textbox_dict.get("position", {})
                    if anchor_type == "anchor" and position:
                        logger.info(f"      Processing absolute positioned textbox from Run object: anchor_type={anchor_type}, position={position}")
                        try:
                            x_offset_emu = position.get("x", 0)
                            y_offset_emu = position.get("y", 0)
                            x_offset_pt = emu_to_points(x_offset_emu)
                            y_offset_pt = emu_to_points(y_offset_emu)
                            
                            textbox_x = x
                            textbox_y = y
                            
                            width_emu = textbox_dict.get("width", 0)
                            height_emu = textbox_dict.get("height", 0)
                            textbox_w = emu_to_points(width_emu) if width_emu else w
                            textbox_h = emu_to_points(height_emu) if height_emu else h
                            
                            textbox_rect = Rect(x=textbox_x, y=textbox_y, width=textbox_w, height=textbox_h)
                            textbox_dict["header_footer_context"] = header_footer_context
                            
                            textbox_block = LayoutBlock(
                                frame=textbox_rect,
                                block_type="textbox",
                                content=textbox_dict,
                                style={},
                                page_number=block.page_number
                            )
                            textbox_color = Color(0.8, 0.5, 0.0)
                            self._draw_textbox_block(c, textbox_block, textbox_color)
                            logger.info(f"      Textbox block rendered successfully from Run object")
                        except Exception as e:
                            logger.error(f"      Error processing absolute positioned textbox from Run: {e}", exc_info=True)
                else:
                    logger.info(f"      Textbox is not a dict and has no textbox_anchor_info, skipping absolute positioning check")

        # Inline textbox visualization based on paragraph layout
        if isinstance(payload, ParagraphLayout) and payload.lines:
            padding_top, padding_right, padding_bottom, padding_left = payload.style.padding
            text_height = payload.lines[-1].baseline_y + payload.lines[-1].height if payload.lines else 0.0
            for line in payload.lines:
                line_bottom = y + padding_bottom + line.baseline_y
                for item in line.items:
                    if item.kind == "inline_textbox":
                        inline_x = x + padding_left + item.x
                        available_width = max(0.0, w - (inline_x - x))
                        inline_width = max(4.0, min(item.width, available_width))
                        inline_height = line.height
                        inline_rect = Rect(inline_x, line_bottom, inline_width, inline_height)
                        textbox_content = {
                            "type": "textbox",
                            "text": item.data.get("text", ""),
                            "anchor_type": "inline",
                            "header_footer_context": header_footer_context,
                        }
                        textbox_block = LayoutBlock(
                            frame=inline_rect,
                            block_type="textbox",
                            content=textbox_content,
                            style={},
                            page_number=block.page_number,
                        )
                        textbox_color = Color(0.8, 0.5, 0.0)
                        self._draw_textbox_block(c, textbox_block, textbox_color)
        
        # Renderuj pola (PAGE, NUMPAGES, etc.)
        if fields:
            logger.info(f"    Rendering {len(fields)} fields in paragraph")
            for i, field in enumerate(fields):
                field_type = field.get("field_type", "unknown")
                field_instr = field.get("instr", "")
                logger.info(f"      Field {i+1}: type={field_type}, instr={field_instr}")
                # Renderuj pole jako tekst w paragrafie
                # Dla PAGE/NUMPAGES wyświetl placeholder
                if field_type == "PAGE":
                    field_text = f"[PAGE]"
                elif field_type == "NUMPAGES":
                    field_text = f"[NUMPAGES]"
                else:
                    field_text = f"[{field_type}]"
                
                # Dodaj do etykiety paragrafu
                if i == 0:
                    text += f" {field_text}"
        
        # Ramka paragrafu
        c.setStrokeColor(color)
        c.setLineWidth(0.8)
        c.rect(x, y, w, h)
        
        # Etykieta
        c.setFont("Helvetica", 7)
        c.setFillColor(color)
        label = f"PARAGRAPH (p.{block.page_number})"
        if header_footer_context:
            label += f" [{header_footer_context.upper()}]"
        if text:
            label += f" [{len(text)} chars]"
        if payload and isinstance(payload, ParagraphLayout):
            total_overlays = len(payload.overlays)
        else:
            total_overlays = 0
        if images:
            label += f" +{len(images)}IMG"
        if textboxes:
            label += f" +{len(textboxes)}TBX"
        if fields:
            label += f" +{len(fields)}FLD"
        if total_overlays:
            label += f" +{total_overlays}OVR"
        c.drawString(x + 3, y + h - 12, label)

    def _draw_table_block(self, c, block, color):
        """Renderuje blok tabeli - ramka, etykieta i układ (wiersze/kolumny)."""
        rect = block.frame
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        
        content_obj = block.content
        if isinstance(content_obj, BlockContent):
            content = content_obj.raw or {}
        else:
            content = content_obj or {}
        rows = content.get("rows", [])
        header_footer_context = content.get("header_footer_context", "")
        grid = content.get("grid", [])
        style = content.get("style", {})
        
        logger.info(f"  Drawing TABLE block: x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}, "
                   f"rows={len(rows)}, header_footer_context={header_footer_context}, grid={len(grid)} columns")
        
        # Ramka tabeli
        c.setStrokeColor(color)
        c.setLineWidth(1.0)
        c.rect(x, y, w, h)
        
        # Oblicz liczbę kolumn i przygotuj informacje o grid
        num_cols = 0
        grid_info = ""
        if rows:
            num_rows = len(rows)
            # Oblicz liczbę kolumn
            for row in rows:
                if isinstance(row, (list, tuple)):
                    num_cols = max(num_cols, len(row))
                elif hasattr(row, "cells"):
                    num_cols = max(num_cols, len(row.cells))
                elif hasattr(row, "__len__"):
                    num_cols = max(num_cols, len(row))
            
            # Dodaj informacje o grid do etykiety
            if grid and len(grid) > 0:
                grid_info = f" grid:{len(grid)}"
            
            # Rysuj układ tabeli (wiersze i kolumny)
            if num_cols > 0 and num_rows > 0:
                # Oblicz szerokości kolumn
                col_widths = []
                if grid and len(grid) > 0:
                    # Użyj grid jeśli jest dostępny
                    from ...engine.geometry import twips_to_points
                    for col in grid:
                        if isinstance(col, dict):
                            width_twips = col.get("w", 0)
                            if width_twips:
                                col_widths.append(twips_to_points(width_twips))
                        elif isinstance(col, (int, float)):
                            col_widths.append(twips_to_points(col))
                    # Jeśli grid nie ma wszystkich kolumn, uzupełnij równomiernie
                    while len(col_widths) < num_cols:
                        remaining_width = w - sum(col_widths) if col_widths else w
                        col_widths.append(remaining_width / (num_cols - len(col_widths)))
                else:
                    # Równomierny podział
                    col_widths = [w / num_cols] * num_cols
                
                # Rysuj linie pionowe (kolumny)
                c.setStrokeColor(color)
                c.setLineWidth(0.5)
                c.setDash([2, 2])  # Linia przerywana dla kolumn
                current_x = x
                for i, col_w in enumerate(col_widths):
                    current_x += col_w
                    if i < len(col_widths) - 1:  # Nie rysuj ostatniej linii (to jest prawa krawędź)
                        c.line(current_x, y, current_x, y + h)
                
                # Pobierz rzeczywiste wysokości wierszy z layout_info (jeśli są dostępne)
                layout_info = content.get("layout_info", {})
                row_heights_actual = layout_info.get("row_heights", [])
                
                # Oblicz wysokości wierszy
                if row_heights_actual and len(row_heights_actual) == num_rows:
                    # Użyj rzeczywistych wysokości wierszy
                    row_heights = row_heights_actual
                    total_height = sum(row_heights)
                    # Skaluj jeśli wysokość tabeli się różni
                    if total_height > 0 and abs(total_height - h) > 0.1:
                        scale_factor = h / total_height
                        row_heights = [rh * scale_factor for rh in row_heights]
                else:
                    # Równomierny podział
                    row_height = h / num_rows if num_rows > 0 else h
                    row_heights = [row_height] * num_rows
                
                # Rysuj linie poziome (wiersze) używając rzeczywistych wysokości
                c.setDash([1, 1])  # Krótsze kreski dla wierszy
                current_y = y + h  # Zaczynamy od góry tabeli (y + h to góra w ReportLab)
                for i in range(num_rows):
                    if i < len(row_heights):
                        current_y -= row_heights[i]
                        if i < num_rows - 1:  # Nie rysuj ostatniej linii (to jest dolna krawędź)
                            c.line(x, current_y, x + w, current_y)
                
                c.setDash()  # Reset dash
                
                # Rysuj bloki zawartości w komórkach
                self._draw_table_cell_content(c, rows, x, y, w, h, col_widths, row_heights, color)
        
        # Etykieta
        c.setFont("Helvetica", 7)
        c.setFillColor(color)
        label = f"TABLE (p.{block.page_number})"
        if header_footer_context:
            label += f" [{header_footer_context.upper()}]"
        if rows:
            if num_cols == 0:
                num_cols = max(len(row) if isinstance(row, (list, tuple)) else (len(getattr(row, "cells", [])) if hasattr(row, "cells") else 1) for row in rows) if rows else 1
            label += f" [{len(rows)}x{num_cols}]"
            if grid_info:
                label += grid_info
        c.drawString(x + 3, y + h - 12, label)
    
    def _draw_table_cell_content(self, c, rows, table_x, table_y, table_w, table_h, col_widths, row_heights, table_color):
        """Rysuje bloki zawartości w komórkach tabeli."""
        logger.info(f"  _draw_table_cell_content: rows={len(rows) if rows else 0}, col_widths={len(col_widths) if col_widths else 0}, row_heights={len(row_heights) if row_heights else 0}")
        if not rows or not col_widths or not row_heights:
            logger.info(f"  Skipping _draw_table_cell_content: rows={bool(rows)}, col_widths={bool(col_widths)}, row_heights={bool(row_heights)}")
            return
        
        # Kolor dla bloków zawartości w komórkach (jaśniejszy od koloru tabeli)
        content_color = Color(
            min(1.0, table_color.red * 0.7),
            min(1.0, table_color.green * 0.7),
            min(1.0, table_color.blue * 0.7)
        )
        
        current_y = table_y + table_h  # Zaczynamy od góry tabeli (y + h to góra w ReportLab)
        
        for row_idx, row in enumerate(rows):
            if row_idx >= len(row_heights):
                break
            
            row_height = row_heights[row_idx]
            current_x = table_x
            
            # Pobierz komórki z wiersza
            cells = []
            if isinstance(row, list):
                cells = row
            elif isinstance(row, dict) and "cells" in row:
                cells = row["cells"]
            elif hasattr(row, "cells"):
                cells = row.cells
            else:
                cells = []
            
            col_idx = 0
            for cell_idx, cell in enumerate(cells):
                if col_idx >= len(col_widths):
                    break
                
                # Pobierz szerokość komórki (uwzględnij grid_span)
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
                
                # Oblicz szerokość komórki
                if col_idx + grid_span <= len(col_widths):
                    cell_width = sum(col_widths[col_idx:col_idx + grid_span])
                else:
                    cell_width = col_widths[col_idx] if col_idx < len(col_widths) else col_widths[0] if col_widths else 100.0
                
                # Pobierz zawartość komórki
                cell_content = []
                if isinstance(cell, dict):
                    cell_content = cell.get("content", []) or cell.get("children", [])
                elif hasattr(cell, "content"):
                    cell_content = cell.content if isinstance(cell.content, list) else [cell.content] if cell.content else []
                elif hasattr(cell, "children"):
                    cell_content = cell.children if isinstance(cell.children, list) else [cell.children] if cell.children else []
                
                logger.info(f"      Cell [{row_idx},{col_idx}]: {len(cell_content)} content items, cell type={type(cell).__name__}")
                
                # Sprawdź czy komórka ma bezpośrednio obrazy
                if hasattr(cell, "images"):
                    cell_images = cell.images if isinstance(cell.images, list) else [cell.images] if cell.images else []
                    if cell_images:
                        logger.info(f"        Cell has {len(cell_images)} direct images")
                elif isinstance(cell, dict) and "images" in cell:
                    cell_images = cell["images"] if isinstance(cell["images"], list) else [cell["images"]] if cell["images"] else []
                    if cell_images:
                        logger.info(f"        Cell dict has {len(cell_images)} direct images")
                
                # Rysuj bloki zawartości w komórce
                cell_y = current_y - row_height
                for content_idx, content_item in enumerate(cell_content):
                    logger.info(f"        Content item {content_idx+1}: {type(content_item).__name__}")
                    if content_item:
                        # Określ typ zawartości
                        content_type = None
                        if isinstance(content_item, dict):
                            content_type = content_item.get("type", "")
                        elif hasattr(content_item, "type"):
                            content_type = getattr(content_item, "type", None)
                        else:
                            class_name = type(content_item).__name__.lower()
                            if "paragraph" in class_name:
                                content_type = "paragraph"
                            elif "table" in class_name:
                                content_type = "table"
                            elif "image" in class_name:
                                content_type = "image"
                            elif "textbox" in class_name:
                                content_type = "textbox"
                        
                        # Rysuj blok zawartości w komórce
                        if content_type == "paragraph":
                            # Pobierz tekst paragrafu
                            text = ""
                            images_in_para: List[Any] = []
                            seen_para_images: Dict[str, bool] = {}

                            def _add_para_image(img: Any) -> None:
                                if not img:
                                    return
                                key = self._image_unique_key(img)
                                if key in seen_para_images:
                                    return
                                seen_para_images[key] = True
                                images_in_para.append(img)
                            if isinstance(content_item, dict):
                                text = content_item.get("text", "")
                                raw_images = content_item.get("images", [])
                                if isinstance(raw_images, list):
                                    for img in raw_images:
                                        _add_para_image(img)
                                elif raw_images:
                                    _add_para_image(raw_images)
                            elif hasattr(content_item, "get_text"):
                                text = content_item.get_text() or ""
                                if hasattr(content_item, "images"):
                                    images_list = content_item.images if isinstance(content_item.images, list) else [content_item.images] if content_item.images else []
                                    for img in images_list:
                                        _add_para_image(img)
                            elif hasattr(content_item, "text"):
                                text = str(content_item.text) if content_item.text else ""
                                if hasattr(content_item, "images"):
                                    images_list = content_item.images if isinstance(content_item.images, list) else [content_item.images] if content_item.images else []
                                    for img in images_list:
                                        _add_para_image(img)
                            
                            # Sprawdź też obrazy w runach paragrafu
                            if hasattr(content_item, "children") or hasattr(content_item, "runs"):
                                runs = getattr(content_item, "children", []) or getattr(content_item, "runs", [])
                                logger.info(f"          Paragraph has {len(runs)} runs")
                                for run_idx, run in enumerate(runs):
                                    logger.info(f"            Run {run_idx+1}: type={type(run).__name__}, hasattr(images)={hasattr(run, 'images')}, hasattr(image)={hasattr(run, 'image')}, has_drawing={getattr(run, 'has_drawing', False)}")
                                    # Sprawdź obrazy w runie (może być jako lista images lub pojedynczy image)
                                    # UWAGA: xml_parser dodaje obrazy do run.images (lista), nie run.image (pojedynczy)
                                    run_images = []
                                    if hasattr(run, "images"):
                                        run_images = run.images if isinstance(run.images, list) else [run.images] if run.images else []
                                    if run_images:
                                            logger.info(f"            Run {run_idx+1} has {len(run_images)} images (from images attr)")
                                    elif hasattr(run, "image"):
                                        if run.image:
                                            run_images = [run.image] if run.image else []
                                            logger.info(f"            Run {run_idx+1} has {len(run_images)} images (from image attr), image type={type(run.image).__name__}")
                                        else:
                                            logger.info(f"            Run {run_idx+1} has image attr but image is None/False")
                                    elif isinstance(run, dict):
                                        if "images" in run:
                                            run_images = run["images"] if isinstance(run["images"], list) else [run["images"]] if run["images"] else []
                                            if run_images:
                                                logger.info(f"            Run {run_idx+1} dict has {len(run_images)} images (from images key)")
                                        elif "image" in run and run["image"]:
                                            run_images = [run["image"]] if run["image"] else []
                                            logger.info(f"            Run {run_idx+1} dict has {len(run_images)} images (from image key)")
                                    
                                    if run_images:
                                        logger.info(f"              Run {run_idx+1} image types: {[type(img).__name__ for img in run_images]}")
                                        # Sprawdź czy obrazy są dict czy obiekty
                                        for img_idx, img in enumerate(run_images):
                                            if isinstance(img, dict):
                                                logger.info(f"                Image {img_idx+1}: dict with keys={list(img.keys())}")
                                            else:
                                                logger.info(f"                Image {img_idx+1}: object {type(img).__name__}, hasattr(path)={hasattr(img, 'path')}, hasattr(image_path)={hasattr(img, 'image_path')}")
                                    for img in run_images:
                                        _add_para_image(img)
                            
                            logger.info(f"          Paragraph: text={len(text) if text else 0} chars, images={len(images_in_para)}")

                            payload = self._extract_paragraph_payload(content_item)
                            cell_margins = parse_cell_margins(cell, default_margin=0.0) if cell is not None else {
                                "top": 0.0,
                                "bottom": 0.0,
                                "left": 0.0,
                                "right": 0.0,
                            }
                            margin_top = float(cell_margins.get("top") or 0.0)
                            margin_bottom = float(cell_margins.get("bottom") or 0.0)
                            margin_left = float(cell_margins.get("left") or 0.0)
                            margin_right = float(cell_margins.get("right") or 0.0)

                            available_height = max(row_height - margin_top - margin_bottom, 0.0)
                            para_height = self._paragraph_layout_height(payload)
                            if para_height <= 0.0:
                                para_height = available_height
                            elif available_height > 0.0:
                                para_height = min(para_height, available_height)
                            para_height = max(para_height, 0.0)

                            para_width = max(cell_width - margin_left - margin_right, 0.0)
                            para_x = current_x + margin_left
                            para_y = cell_y + margin_bottom

                            if text or images_in_para:
                                if para_width > 0.0 and para_height > 0.0:
                                    # Rysuj ramkę paragrafu z rzeczywistymi wymiarami
                                    c.setStrokeColor(content_color)
                                    c.setLineWidth(0.3)
                                    c.setDash([1, 1])
                                    c.rect(para_x, para_y, para_width, para_height)
                                    c.setDash()

                                    # Etykieta
                                    c.setFont("Helvetica", 5)
                                    c.setFillColor(content_color)
                                    label_parts = ["P"]
                                    if text:
                                        label_parts.append(str(len(text)))
                                    if para_height:
                                        label_parts.append(f"h={para_height:.1f}")
                                    if images_in_para:
                                        label_parts.append(f"+{len(images_in_para)}IMG")
                                    label = " ".join(label_parts)
                                    if para_width > 0.0 and len(label) * 3 > para_width:
                                        label = "P"
                                        if para_height:
                                            label += f" {para_height:.0f}"
                                        if images_in_para:
                                            label += f"+{len(images_in_para)}"
                                    c.drawString(para_x + 1, para_y + para_height - 6, label)

                                # Rysuj obrazy w paragrafie jako osobne bloki
                                for img_idx, img in enumerate(images_in_para):
                                    logger.info(f"          Drawing image {img_idx+1} in paragraph: {type(img).__name__}")
                                    if not (para_width > 0.0 and (para_height > 0.0 or available_height > 0.0)):
                                        continue
                                    if isinstance(img, dict):
                                        # Rysuj blok obrazu w komórce używając oryginalnych wymiarów obrazu
                                        c.setStrokeColor(green)
                                        c.setLineWidth(0.3)
                                        img_margin = 2

                                        # Pobierz oryginalne wymiary obrazu (w EMU)
                                        width_emu = img.get("width", 0)
                                        height_emu = img.get("height", 0)
                                        img_w_original = None
                                        img_h_original = None

                                        if width_emu and height_emu:
                                            # Konwertuj z EMU na punkty
                                            from ...engine.geometry import emu_to_points
                                            img_w_original = emu_to_points(width_emu)
                                            img_h_original = emu_to_points(height_emu)

                                            # Sprawdź czy obraz mieści się w komórce
                                            # Pobierz marginesy komórki (domyślnie 0)
                                            cell_margin_left = 0
                                            cell_margin_right = 0
                                            if isinstance(cell, dict) and "style" in cell:
                                                cell_style = cell["style"]
                                                if isinstance(cell_style, dict) and "margins" in cell_style:
                                                    margins = cell_style["margins"]
                                                    if isinstance(margins, dict):
                                                        cell_margin_left = margins.get("left", 0)
                                                        cell_margin_right = margins.get("right", 0)
                                            elif hasattr(cell, "style") and hasattr(cell.style, "margins"):
                                                margins = cell.style.margins
                                                if isinstance(margins, dict):
                                                    cell_margin_left = margins.get("left", 0)
                                                    cell_margin_right = margins.get("right", 0)

                                            available_cell_width = cell_width - cell_margin_left - cell_margin_right - 2 * img_margin
                                            if img_w_original > available_cell_width and available_cell_width > 0:
                                                # Jeśli obraz jest szerszy, przeskaluj go do szerokości komórki, zachowując proporcje
                                                scale = available_cell_width / img_w_original
                                                img_w = available_cell_width
                                                img_h = img_h_original * scale
                                            else:
                                                # Jeśli obraz mieści się w komórce, użyj jego oryginalnych wymiarów
                                                img_w = img_w_original if img_w_original is not None else 0.0
                                                img_h = img_h_original if img_h_original is not None else 0.0
                                        else:
                                            # Fallback: użyj wymiarów wynikających z dostępnej powierzchni
                                            content_height = para_height if para_height > 0.0 else available_height
                                            content_height = max(content_height - img_margin * 2, 10.0)
                                            available_width = max(para_width - img_margin * 2, 10.0)
                                            img_w = min(available_width, 25.0)
                                            img_h = min(content_height, 25.0)

                                        if img_w <= 0.0 or img_h <= 0.0:
                                            continue

                                        # Pozycjonuj obraz w komórce (z lewej strony, z małym marginesem)
                                        img_x = para_x + img_margin
                                        img_y = para_y + img_margin

                                        logger.info(
                                            "            Image block in cell: x=%.2f, y=%.2f, w=%.2f, h=%.2f (original: %s, %s)",
                                            img_x,
                                            img_y,
                                            img_w,
                                            img_h,
                                            f"{img_w_original:.2f}" if img_w_original is not None else "N/A",
                                            f"{img_h_original:.2f}" if img_h_original is not None else "N/A",
                                        )
                                        c.rect(img_x, img_y, img_w, img_h)

                                        c.setFont("Helvetica", 4)
                                        c.setFillColor(green)
                                        c.drawString(img_x + 1, img_y + img_h - 5, "IMG")
                        
                        elif content_type == "table":
                            # Zagnieżdżona tabela - rysuj mniejszy blok
                            c.setStrokeColor(content_color)
                            c.setLineWidth(0.3)
                            c.setDash([1, 1])
                            margin = 2
                            nested_x = current_x + margin
                            nested_y = cell_y + margin
                            nested_w = cell_width - 2 * margin
                            nested_h = max(8, min(row_height - 2 * margin, 20))
                            c.rect(nested_x, nested_y, nested_w, nested_h)
                            c.setDash()
                            
                            c.setFont("Helvetica", 5)
                            c.setFillColor(content_color)
                            c.drawString(nested_x + 1, nested_y + nested_h - 6, "TBL")
                        
                        elif content_type == "image":
                            # Obraz w komórce (bezpośrednio w komórce, nie w paragrafie)
                            logger.info(f"          Drawing direct image in cell: {type(content_item).__name__}")
                            c.setStrokeColor(green)
                            c.setLineWidth(0.3)
                            margin = 2
                            img_x = current_x + margin
                            img_y = cell_y + margin
                            img_w = max(10, min(cell_width - 2 * margin, 30))
                            img_h = max(10, min(row_height - 2 * margin, 30))
                            logger.info(f"            Image block in cell: x={img_x:.2f}, y={img_y:.2f}, w={img_w:.2f}, h={img_h:.2f}")
                            c.rect(img_x, img_y, img_w, img_h)
                            
                            c.setFont("Helvetica", 5)
                            c.setFillColor(green)
                            c.drawString(img_x + 1, img_y + img_h - 6, "IMG")
                
                current_x += cell_width
                col_idx += grid_span
            
            current_y -= row_height

    def _draw_textbox_block(self, c, block, color):
        """Renderuje blok textbox - tylko ramka i etykieta."""
        rect = block.frame
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        
        content_obj = block.content
        if isinstance(content_obj, BlockContent):
            content = content_obj.raw or {}
        else:
            content = content_obj or {}
        header_footer_context = content.get("header_footer_context", "")
        
        logger.info(f"  Drawing TEXTBOX block: x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}, header_footer_context={header_footer_context}")
        
        # Ramka textbox
        c.setStrokeColor(color)
        c.setLineWidth(1.0)
        c.rect(x, y, w, h)
        
        # Etykieta
        c.setFont("Helvetica", 7)
        c.setFillColor(color)
        label = f"TEXTBOX (p.{block.page_number})"
        if header_footer_context:
            label += f" [{header_footer_context.upper()}]"
        c.drawString(x + 3, y + h - 12, label)

    def _draw_header_footer_block(self, c, block, color):
        """Renderuje blok nagłówka/stopki - tylko linia przerywana do oznaczenia obszaru."""
        rect = block.frame
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        
        content_obj = block.content
        if isinstance(content_obj, BlockContent):
            content = content_obj.raw or {}
            payload = content_obj.payload
        else:
            content = content_obj or {}
            payload = None
 
        # Sprawdź czy to marker (tylko linia przerywana) czy element zawartości
        is_marker = content.get("type") in ["header_marker", "footer_marker"]
 
        logger.info(f"  Drawing HEADER/FOOTER block: type={block.block_type}, "
                   f"x={x:.2f}, y={y:.2f}, w={w:.2f}, h={h:.2f}, is_marker={is_marker}")
        
        if is_marker:
            # Tylko linia przerywana do oznaczenia obszaru nagłówka/stopki
            # Użyj ciemniejszego koloru, żeby linia była lepiej widoczna
            c.setStrokeColor(color)
            c.setLineWidth(2.5)  # Grubsza linia, żeby była lepiej widoczna
            c.setDash([8, 4])  # Linia przerywana - dłuższe kreski
            
            # Rysuj linię na granicy obszaru nagłówka/stopki
            if block.block_type == "header":
                # Linia na dole obszaru nagłówka (od dołu strony)
                # y to dolna krawędź obszaru nagłówka
                c.line(x, y, x + w, y)
            else:  # footer
                # Linia na górze obszaru stopki (od dołu strony)
                # y + h to górna krawędź obszaru stopki
                c.line(x, y + h, x + w, y + h)
            
            c.setDash()  # Reset dash
        else:
            if isinstance(payload, GenericLayout) and payload.overlays:
                logger.info(f"    Header/footer payload has {len(payload.overlays)} overlays")
                for overlay in payload.overlays:
                    overlay_block = LayoutBlock(
                        frame=overlay.frame,
                        block_type="image" if overlay.kind == "image" else "textbox",
                        content=overlay.payload,
                        style={},
                        page_number=block.page_number,
                    )
                    if overlay.kind == "image":
                        self._draw_image_block(c, overlay_block, green)
                    elif overlay.kind == "textbox":
                        textbox_color = Color(0.8, 0.5, 0.0)
                        self._draw_textbox_block(c, overlay_block, textbox_color)

    def _draw_generic_block(self, c, block, color):
        """Renderuje blok nieznanego typu."""
        rect = block.frame
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        
        payload = None
        if isinstance(block.content, BlockContent):
            payload = block.content.payload

        # Ramka
        c.setStrokeColor(color)
        c.setLineWidth(0.8)
        c.rect(x, y, w, h)
 
        # Etykieta
        c.setFont("Helvetica", 7)
        c.setFillColor(color)
        label = f"{block.block_type.upper()} (p.{block.page_number})"
        c.drawString(x + 3, y + h - 12, label)

        if isinstance(payload, GenericLayout) and payload.overlays:
            for overlay in payload.overlays:
                overlay_block = LayoutBlock(
                    frame=overlay.frame,
                    block_type="image" if overlay.kind == "image" else "textbox",
                    content=overlay.payload,
                    style={},
                    page_number=block.page_number,
                )
                if overlay.kind == "image":
                    self._draw_image_block(c, overlay_block, green)
                elif overlay.kind == "textbox":
                    textbox_color = Color(0.8, 0.5, 0.0)
                    self._draw_textbox_block(c, overlay_block, textbox_color)
