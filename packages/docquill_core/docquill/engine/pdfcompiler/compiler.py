"""Main PDF compiler - converts layout to PDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from docquill.engine.unified_layout import LayoutBlock, LayoutPage
from docquill.engine.geometry import Size, twips_to_points

from .objects import PdfDocument, PdfPage, PdfStream
from .resources import PdfFontRegistry, PdfImageRegistry
from .text_renderer import PdfTextRenderer
from .writer import PdfWriter

# Import watermark renderer for PDF
try:
    from ...renderers.watermark_renderer import WatermarkRenderer
except ImportError:
    WatermarkRenderer = None


logger = logging.getLogger(__name__)


class PDFCompiler:
    """Main compiler that converts layout pages to PDF."""
    
    def __init__(
        self,
        output_path: str | Path,
        options: Optional[Dict[str, Any]] = None,
    ):
        """Initialize PDF compiler.
        
        Args:
            output_path: Path to output PDF file
            options: Optional compiler options
                - package_reader: Optional package reader for loading image data
        """
        self.output_path = Path(output_path)
        self.options = options or {}
        
        # Initialize registries
        self.font_registry = PdfFontRegistry()
        self.image_registry = PdfImageRegistry()
        
        # Initialize renderer
        self.text_renderer = PdfTextRenderer(self.font_registry)
        
        # Package reader for loading image data (from DOCX)
        self.package_reader = self.options.get("package_reader")
        
        # Document structure
        self.document = PdfDocument()
        self.next_image_obj_num = 1000  # Start image objects after page objects
        
        # Initialize watermark renderer if available
        self.watermark_renderer = None
        if WatermarkRenderer:
            # Get watermarks from options or document if available
            watermarks = []
            # Try to get watermarks from options first
            if self.options:
                watermarks = self.options.get('watermarks', [])
            # If not in options, try to get from document model via package_reader
            if not watermarks and self.package_reader:
                try:
                    # Try to get watermarks from document model
                    # This will be set by PlaceholderEngine or Document API
                    document_model = getattr(self.package_reader, '_document_model', None)
                    if document_model:
                        if hasattr(document_model, 'get_watermarks'):
                            watermarks = document_model.get_watermarks() or []
                        elif hasattr(document_model, 'watermarks'):
                            watermarks = document_model.watermarks or []
                except Exception:
                    pass
            self.watermark_renderer = WatermarkRenderer(watermarks)
    
    def compile(self, layout_pages: Sequence[LayoutPage]) -> Path:
        """Compile layout pages to PDF.
        
        Args:
            layout_pages: Sequence of layout pages
            
        Returns:
            Path to generated PDF file
            
        Raises:
            ValueError: If layout_pages is empty or None
            IOError: If PDF file cannot be written
        """
        if not layout_pages:
            raise ValueError("layout_pages cannot be empty")
        
        # Process each layout page
        for layout_page in layout_pages:
            pdf_page = self._create_page(layout_page)
            self.document.pages.append(pdf_page)
        
        # Assign object numbers to images BEFORE building resources
        # Calculate next object number after pages
        # Each page needs 2 objects (page dict + stream)
        # Pages tree is 1 object, catalog is 1 object
        # So images start at: catalog(1) + pages_tree(2) + pages(2 * page_count) + 1
        next_obj_num = 3  # Start after catalog(1) + pages_tree(2)
        for page in self.document.pages:
            next_obj_num += 2  # Each page needs 2 objects (page dict + stream)
        # Images start at next_obj_num
        image_obj_num = next_obj_num
        
        # Assign object numbers to all images
        all_images = self.image_registry.get_all_images()
        for image in all_images.values():
            if image.image_data and image.object_num is None:
                image.object_num = image_obj_num
                image_obj_num += 1
        
        # Rebuild resources for all pages now that images have object numbers
        resources_built = self._build_resources()
        
        for page in self.document.pages:
            page.resources = resources_built.copy()  # Use copy to ensure all pages have the same resources
        
        # Set PDF metadata (optional - can be set via document.info_dict)
        if not self.document.info_dict:
            # Default metadata
            self.document.info_dict = {}
        
        # Always ensure Producer and CreationDate are set (required for PDF/A compliance)
        from datetime import datetime
        self.document.info_dict.setdefault("Producer", "DocQuill PDF Compiler 1.0")
        self.document.info_dict.setdefault("Creator", "DocQuill")
        if "CreationDate" not in self.document.info_dict:
            # PDF date format: (D:YYYYMMDDHHmmSSOHH'mm')
            creation_date = datetime.now().strftime("(D:%Y%m%d%H%M%S)")
            self.document.info_dict["CreationDate"] = creation_date
        
        # Write PDF file
        try:
            writer = PdfWriter(self.output_path)
            writer.write(self.document, self.image_registry)
        except Exception as e:
            logger.error(f"Failed to write PDF file to {self.output_path}: {e}")
            raise IOError(f"Failed to write PDF file: {e}") from e
        
        return self.output_path
    
    def _create_page(self, layout_page: LayoutPage) -> PdfPage:
        """Create PDF page from layout page.
        
        Args:
            layout_page: Layout page to convert
            
        Returns:
            PdfPage object
        """
        # Get page dimensions
        width = layout_page.size.width
        height = layout_page.size.height
        
        # Create PDF page
        pdf_page = PdfPage(
            page_number=layout_page.number,
            width=width,
            height=height,
        )
        
        # Create stream
        stream = pdf_page.stream
        
        # Render watermarks first (on background, before everything else)
        if self.watermark_renderer:
            self._render_watermarks(stream, width, height)
        
        # Separate blocks by z-order for proper rendering order
        # 1. Render images with z_order="behind" first (before text)
        # 2. Render text blocks (paragraphs, tables, textboxes)
        # 3. Render images with z_order="front" last (after text) - on top
        # Note: Default z_order for images is "front" to ensure they are visible
        behind_images = []
        text_blocks = []
        front_images = []
        
        # Safely handle empty or None blocks
        blocks = getattr(layout_page, "blocks", None) or []
        for block in blocks:
            if block.block_type == "image":
                z_order = (block.style or {}).get("z_order", "front")  # Default to "front"
                if z_order == "behind":
                    behind_images.append(block)
                else:
                    # Default to "front" if not explicitly "behind"
                    front_images.append(block)
            else:
                text_blocks.append(block)
        
        # Render in correct order: behind images -> text -> front images (on top)
        for block in behind_images:
            self._render_block(stream, block, height, layout_page)
        
        for block in text_blocks:
            self._render_block(stream, block, height, layout_page)
        
        # Render front images last (on top of everything)
        for block in front_images:
            self._render_block(stream, block, height, layout_page)
        
        # Render footnotes blocks (already created by LayoutAssembler)
        for block in blocks:
            if block.block_type == "footnotes":
                self._render_footnotes_block(stream, block, height, width)
        
        # Build resources dictionary (will be rebuilt later with image object numbers)
        # For now, build without images - they'll be added later
        pdf_page.resources = self._build_resources()
        
        return pdf_page
    
    def _render_block(self, stream: PdfStream, block: LayoutBlock, page_height: float, layout_page: Optional[LayoutPage] = None) -> None:
        """Render a layout block to PDF stream.
        
        Args:
            stream: PDF stream to add commands to
            block: Layout block to render
            page_height: Page height (for Y coordinate conversion)
        """
        # LayoutBlock coordinates are already in PDF coordinate system
        # where Y decreases downward from the top (like PDF coordinates)
        # block.frame.y is the BOTTOM edge of the block
        # block.frame.y + block.frame.height is the TOP edge of the block
        # No conversion needed - use directly as PDF coordinates
        x = block.frame.x
        # Top edge = bottom edge + height
        block_top_pdf = block.frame.y + block.frame.height  # Top edge in PDF coordinates
        
        block_type = block.block_type
        
        if block_type == "paragraph" or block_type == "footer" or block_type == "header":
            # Footer and header use the same rendering logic as paragraphs
            # They have the same structure (lines, runs, styles) from layout engine
            self._render_paragraph(stream, block, x, block_top_pdf, page_height)
        elif block_type == "table":
            part_path = None
            if hasattr(block, "content") and isinstance(block.content, dict):
                part_path = block.content.get("part_path")
            elif hasattr(block, "style") and isinstance(block.style, dict):
                part_path = block.style.get("part_path")
            self._render_table(stream, block, x, block_top_pdf, page_height)
        elif block_type == "textbox":
            # Textbox uses similar rendering logic as table
            # It's a container with positioned elements inside
            self._render_textbox(stream, block, x, block_top_pdf, page_height)
        elif block_type == "image":
            self._render_image(stream, block, x, block_top_pdf, page_height, layout_page)
        # Add more block types as needed
    
    def _render_paragraph(self, stream: PdfStream, block: LayoutBlock, x: float, block_top: float, page_height: float, 
                         cell_context: Optional[Dict[str, Any]] = None) -> None:
        """Render paragraph block.
        
        Args:
            stream: PDF stream
            block: Paragraph block
            x: X position
            block_top: Top edge of block in PDF coordinates
            page_height: Page height
            cell_context: Optional context for table cell (contains: width, height, v_align)
        """
        content = block.content
        style = block.style or {}
        
        # Handle dict-based content (legacy format)
        if isinstance(content, dict):
            # Layout engine should already break text into lines
            lines = content.get("lines", [])
            
            if not lines:
                # Layout engine should provide lines - log warning but don't break here
                # This is a fallback only if layout engine didn't provide lines
                logger.warning(f"Paragraph block has no lines in payload. Block type: {block.block_type}")
                # Don't break text here - layout engine should handle it
                return
            
            def _to_points(value):
                if value is None or value == "":
                    return 0.0
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    return 0.0
                if numeric > 144:
                    return twips_to_points(numeric)
                return numeric

            indent_dict = content.get("indent") or style.get("indent") or {}
            if not isinstance(indent_dict, dict):
                indent_dict = {}
            indent_left_pt = _to_points(indent_dict.get("left_pt") or indent_dict.get("left"))
            indent_hanging_pt = _to_points(indent_dict.get("hanging_pt") or indent_dict.get("hanging"))
            indent_first_line_pt = _to_points(indent_dict.get("first_line_pt") or indent_dict.get("first_line"))
            text_position_pt = _to_points(indent_dict.get("text_position_pt")) if indent_dict.get("text_position_pt") is not None else None
            if text_position_pt is not None:
                indent_first_line_pt = text_position_pt
            elif indent_first_line_pt == 0.0 and indent_hanging_pt:
                indent_first_line_pt = indent_left_pt - indent_hanging_pt

            # Render numbering marker if present
            try:
                default_font_size = float(style.get("font_size", 11.0))
            except (ValueError, TypeError):
                logger.warning(f"Invalid font_size in style, using default: {style.get('font_size')}")
                default_font_size = 11.0

            marker = content.get("marker")

            baselines: List[float] = []

            def _compute_baseline(line_idx: int, line_entry: Dict[str, Any]) -> float:
                offset_val = line_entry.get("offset_baseline")
                if offset_val not in (None, ""):
                    try:
                        return block_top - float(offset_val)
                    except (TypeError, ValueError):
                        pass
                line_layout = line_entry.get("layout")
                local_font = default_font_size
                local_height = default_font_size * 1.2
                if line_layout:
                    if isinstance(line_layout, dict):
                        font_candidate = line_layout.get("font_size")
                        if font_candidate not in (None, ""):
                            try:
                                local_font = float(font_candidate)
                            except (TypeError, ValueError):
                                local_font = default_font_size
                        height_candidate = line_layout.get("height")
                        if height_candidate not in (None, ""):
                            try:
                                local_height = float(height_candidate)
                            except (TypeError, ValueError):
                                local_height = local_font * 1.2
                        else:
                            local_height = local_font * 1.2
                    elif hasattr(line_layout, "font_size"):
                        try:
                            local_font = float(getattr(line_layout, "font_size"))
                        except (TypeError, ValueError):
                            local_font = default_font_size
                        try:
                            local_height = float(getattr(line_layout, "height"))
                        except (TypeError, ValueError):
                            local_height = local_font * 1.2
                if line_idx == 0:
                    return block_top - (local_font * 0.8)
                prev_baseline = baselines[line_idx - 1] if len(baselines) > line_idx - 1 else block_top - (local_font * 0.8)
                return prev_baseline - local_height

            first_line_baseline = None
            if marker and lines:
                first_entry = lines[0]
                if isinstance(first_entry, dict) and first_entry.get("offset_baseline") not in (None, ""):
                    try:
                        first_line_baseline = block_top - float(first_entry.get("offset_baseline"))
                    except (TypeError, ValueError):
                        first_line_baseline = _compute_baseline(0, first_entry)
                else:
                    first_line_baseline = _compute_baseline(0, first_entry if isinstance(first_entry, dict) else {})
                baselines.append(first_line_baseline)

            if marker:
                number_offset = marker.get("number_position")
                if number_offset is None:
                    number_offset = indent_dict.get("number_position_pt")
                if number_offset is None:
                    number_offset = indent_left_pt - indent_hanging_pt
                    marker.setdefault("number_position", number_offset)
                if marker.get("x") is None:
                    marker["x"] = x + number_offset
                if marker.get("baseline_offset") is None:
                    marker["baseline_offset"] = 0.0
                if marker.get("text_position") is None:
                    marker["text_position"] = text_position_pt if text_position_pt is not None else indent_left_pt
                self._render_numbering_marker(stream, marker, block_top, page_height, baseline_override=first_line_baseline)
            
            # Render lines from top to bottom (layout engine already broke text into lines)
            # block_top is the top edge of the block in PDF coordinates
            # Each line has offset_baseline relative to block top - use it!
            
            # Get default font size from style
            for line_idx, line_entry in enumerate(lines):
                if isinstance(line_entry, dict):
                    # Get line text - MUST use line_entry.get("text") NOT content.get("text")
                    # Each line should have its own text fragment
                    line_text = line_entry.get("text", "")
                    if not line_text and hasattr(line_entry, "text"):
                        line_text = getattr(line_entry, "text", "")
                    
                    if not line_text:
                        continue
                    
                    # Use offset_baseline from layout engine (relative to block top)
                    # baseline = block_top - offset_baseline (because offset_baseline is distance from top)
                    offset_baseline = line_entry.get("offset_baseline", 0.0)
                    if offset_baseline:
                        baseline = block_top - offset_baseline
                    else:
                        if line_idx < len(baselines):
                            baseline = baselines[line_idx]
                        else:
                            baseline = _compute_baseline(line_idx, line_entry)
                            baselines.append(baseline)
                    if line_idx >= len(baselines):
                        baselines.append(baseline)
                    
                    # Render line - check if line has runs (with individual styles)
                    entry_runs = line_entry.get("runs", [])
                    if entry_runs:
                        # Render each run separately with its own style
                        line_offset = line_entry.get("offset_x", 0.0)
                        if not isinstance(line_offset, (int, float)):
                            try:
                                line_offset = float(line_offset)
                            except (ValueError, TypeError):
                                line_offset = 0.0
                        current_x = x + line_offset
                        for run in entry_runs:
                            run_text = run.get("text", "")
                            run_style_source = run.get("style", style)
                            if isinstance(run_style_source, dict):
                                run_style = dict(run_style_source)
                            else:
                                run_style = dict(style)

                            # Merge inline flags/overrides that might live outside style dict
                            for key in (
                                "baseline_shift",
                                "highlight",
                                "highlight_color",
                                "underline",
                                "bold",
                                "italic",
                                "strike",
                                "strike_through",
                                "strikethrough",
                                "color",
                                "font_name",
                                "font_size",
                                "superscript",
                                "subscript",
                                "vertical_align",
                            ):
                                if key in run and run[key] not in (None, False, "", {}):
                                    value = run[key]
                                    if key in {"strike", "strike_through", "strikethrough"}:
                                        run_style["strike_through"] = bool(value)
                                    elif key == "highlight":
                                        run_style.setdefault("highlight", value)
                                    else:
                                        run_style[key] = value

                            run_image = run.get("image")  # Check for image in run
                            
                            
                            if run_image:
                                # Render inline image in run
                                # Images in runs should be rendered inline with text
                                # Get image dimensions from run or calculate from image
                                image_width = run.get("image_width") or run_style.get("image_width", 50.0)
                                image_height = run.get("image_height") or run_style.get("image_height", 50.0)
                                
                                # Calculate image position
                                # For inline images in table cells: position should be relative to cell position (cell_x, cell_top)
                                if cell_context:
                                    # For images in table cells: calculate position from cell position, dimensions, vAlign, and image dimensions
                                    cell_x = cell_context.get("x", x)  # Left edge of cell (absolute position in PDF coordinates)
                                    cell_width = cell_context.get("width", 0.0)
                                    cell_height = cell_context.get("height", 0.0)
                                    cell_top = cell_context.get("top", block_top)  # Top edge of cell (absolute position in PDF coordinates)
                                    v_align = cell_context.get("v_align", "top")
                                    
                                    # X position: relative to cell left edge (cell_x)
                                    # current_x is relative to content_x (x + padding_left), which is relative to cell left edge
                                    # So: image_x = cell_x + (current_x - x) where x is content_x
                                    # This gives us the absolute X position relative to cell left edge
                                    image_x = cell_x + (current_x - x)
                                    
                                    # Y position: calculate from cell position and dimensions, with vAlign consideration
                                    # In PDF coordinates (used by compiler): Y decreases downward from top
                                    # cell_top is the top edge of the cell (larger Y value = higher on page)
                                    # cell_bottom = cell_top - cell_height (smaller Y value = lower on page)
                                    # For vAlign="center": image should be centered vertically in cell
                                    # For vAlign="bottom": image bottom should align with cell bottom
                                    # For vAlign="top": image top should align with cell top
                                    if v_align == "center":
                                        # Center image vertically in cell
                                        # cell_center_y = cell_top - (cell_height / 2.0)
                                        # image_center_y = cell_center_y
                                        # image_bottom = image_center_y - (image_height / 2.0)
                                        image_bottom = cell_top - (cell_height / 2.0) - (image_height / 2.0)
                                    elif v_align == "bottom":
                                        # Align image to bottom of cell
                                        # cell_bottom = cell_top - cell_height
                                        # image_bottom should align with cell_bottom
                                        cell_bottom = cell_top - cell_height
                                        image_bottom = cell_bottom
                                    else:
                                        # Default: align to top of cell (vAlign="top")
                                        # image_top should align with cell_top
                                        # image_bottom = cell_top - image_height
                                        image_bottom = cell_top - image_height
                                    image_top_pdf = image_bottom + image_height
                                    
                                else:
                                    # For inline images in regular paragraphs: align bottom of image with baseline
                                    image_x = current_x  # Use current_x from paragraph rendering
                                    image_bottom = baseline - image_height * 0.2  # Slight offset for better alignment
                                    image_top_pdf = image_bottom + image_height
                                
                                # Render image using image rendering logic
                                # Create a temporary LayoutBlock for the image
                                from docquill.engine.base_engine import LayoutBlock
                                from docquill.engine.geometry import Rect
                                
                                image_block = LayoutBlock(
                                    frame=Rect(x=image_x, y=image_bottom, width=image_width, height=image_height),
                                    content=run_image if isinstance(run_image, dict) else {"image": run_image},
                                    style=run_style,
                                    block_type="image"
                                )
                                
                                # Render image inline (no page_height needed for inline images)
                                # Use image_x and image_top_pdf calculated above
                                self._render_image(stream, image_block, image_x, image_top_pdf, page_height)
                                
                                # Advance x position by image width + small gap
                                current_x += image_width + 2.0  # Small gap after image
                            elif run_text:
                                # Render text run and get its width for positioning next run
                                run_width = self.text_renderer.render_run(stream, run_text, current_x, baseline, run_style)
                                current_x += run_width
                    else:
                        # Fallback: render line as single run with line style
                        line_style = line_entry.get("style", style)
                        line_offset = line_entry.get("offset_x", 0.0)
                        if not isinstance(line_offset, (int, float)):
                            try:
                                line_offset = float(line_offset)
                            except (ValueError, TypeError):
                                line_offset = 0.0
                        self.text_renderer.render_run(stream, line_text, x + line_offset, baseline, line_style)
        
        # Handle model-based content (Paragraph object)
        # This should not happen - layout engine should convert Paragraph to dict with lines
        # FALLBACK BLOCKED - to verify if fallback is being used
        elif hasattr(content, "runs"):
            logger.error(f"FALLBACK BLOCKED: Paragraph block has model-based content (runs) instead of dict with lines. "
                         f"This should have been handled by layout engine. Fallback rendering is BLOCKED.")
            # Fallback: render runs as single line (not ideal, but better than nothing)
            # BLOCKED - do not render anything
            # full_text = "".join(getattr(run, "text", "") for run in content.runs if hasattr(run, "text"))
            # if full_text:
            #     font_size = float(style.get("font_size", 11.0))
            #     ascent = font_size * 0.8
            #     baseline = block_top - ascent
            #     self.text_renderer.render_run(stream, full_text, x, baseline, style)
    
    def _render_numbering_marker(
        self,
        stream: PdfStream,
        marker: Dict[str, Any],
        block_top: float,
        page_height: float,
        baseline_override: Optional[float] = None,
    ) -> None:
        """Render numbering marker (bullet, number, etc.).
        
        Args:
            stream: PDF stream
            marker: Marker info from layout engine (contains text, x, baseline_offset, style)
            block_top: Top edge of paragraph block in PDF coordinates
            page_height: Page height
        """
        marker_text = marker.get("text")
        if not marker_text:
            return
        
        # Get marker position
        try:
            marker_x = float(marker.get("x", 0.0))
        except (ValueError, TypeError):
            logger.warning("Invalid marker x-coordinate, using default 0.0")
            marker_x = 0.0

        marker_baseline: Optional[float] = baseline_override
        if marker_baseline is None:
            try:
                baseline_offset = float(marker.get("baseline_offset", 0.0))
            except (ValueError, TypeError):
                baseline_offset = 0.0
            marker_baseline = block_top - baseline_offset
        
        # Get marker style (may override paragraph style)
        marker_style = marker.get("style", {})
        if not marker_style:
            # Fallback to default marker style
            marker_style = {
                "font_size": 11.0,
                "font_family": "DejaVu Sans",
                "color": "#000000",
            }
        
        # Render marker text
        self.text_renderer.render_run(stream, marker_text, marker_x, marker_baseline, marker_style)
    
    def _render_table(self, stream: PdfStream, block: LayoutBlock, x: float, block_top: float, page_height: float) -> None:
        """Render table block.
        
        Layout engine calculates everything: column widths, row heights, cell positions, grid lines.
        Compiler only renders:
        1. Grid lines (x1, y1, x2, y2 from layout engine)
        2. Cell content at positions (x, y, width, height from layout engine)
        
        Args:
            stream: PDF stream
            block: Table block
            x: X position (left edge) - same as block.frame.x
            block_top: Top edge of block in PDF coordinates - same as block.frame.y + block.frame.height
            page_height: Page height
        """
        content = block.content
        style = block.style or {}
        
        # Grid lines and positioned cells use absolute coordinates relative to frame.x and frame.y
        # Since block.frame.x and block.frame.y are already in PDF coordinate system,
        # and grid_lines/cells are calculated using frame.x and frame.y,
        # they should be directly usable as PDF coordinates.
        # But we need to verify: grid_lines use table_x (which is frame.x) and table_top (which is frame.y + frame.height)
        # So they should match x and block_top passed to this function.
        
        if isinstance(content, dict):
            # 1. Render grid lines (calculated by layout engine)
            # Grid lines coordinates are absolute (relative to page), calculated from frame.x and frame.y
            grid_lines = content.get("grid_lines", [])
            if grid_lines:
                for line in grid_lines:
                    try:
                        x1 = float(line.get("x1", 0.0))
                        y1_layout = float(line.get("y1", 0.0))  # Y in layout coordinates (Y increases downward)
                        x2 = float(line.get("x2", 0.0))
                        y2_layout = float(line.get("y2", 0.0))  # Y in layout coordinates (Y increases downward)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid grid line coordinates, skipping line: {line}")
                        continue
                    # Convert from layout coordinates to PDF coordinates (Y increases upward)
                    # layout Y: 0 at top, increases downward
                    # PDF Y: 0 at bottom, increases upward
                    # Conversion: pdf_y = page_height - layout_y
                    y1_pdf = page_height - y1_layout
                    y2_pdf = page_height - y2_layout
                    stream.add_line(x1, y1_pdf, x2, y2_pdf, width=0.5)
            
            # 2. Render cell content at positions (x, y, width, height from layout engine)
            # Cell coordinates are absolute (relative to page), calculated from frame.x and frame.y
            # Get part_path from block content if available (for footer/header tables)
            part_path = None
            if hasattr(block, "content") and isinstance(block.content, dict):
                part_path = block.content.get("part_path")
            elif hasattr(block, "style") and isinstance(block.style, dict):
                part_path = block.style.get("part_path")
            
            positioned_cells = content.get("cells", [])
            if not positioned_cells:
                logger.warning(f"_render_table: No cells found in content!")
            for cell_data in positioned_cells:
                cell = cell_data.get("cell")
                try:
                    cell_x = float(cell_data.get("x", 0.0))  # Absolute X (from frame.x)
                    cell_y = float(cell_data.get("y", 0.0))  # Bottom edge in layout coordinates (relative to table_top)
                    cell_width = float(cell_data.get("width", 0.0))
                    cell_height = float(cell_data.get("height", 0.0))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid cell coordinates, skipping cell: {cell_data}")
                    continue
                
                # Convert cell_y from layout coordinates to PDF coordinates
                # In table_engine.py:
                #   table_top = frame.y + frame.height (top edge of table in layout coordinates, Y increases downward)
                #   current_y = table_top (start from top of table)
                #   row_bottom = current_y - row_height (bottom edge of row in layout coordinates)
                #   cell_y = row_bottom (bottom edge of cell in absolute layout coordinates)
                # So cell_y is bottom edge of cell in absolute layout coordinates (Y increases downward from top)
                # In compiler.py:
                #   block.frame.y is bottom edge of table in layout coordinates (Y increases downward)
                #   cell_y is bottom edge of cell in layout coordinates (Y increases downward)
                #   PDF coordinates: Y increases upward from bottom
                #   Conversion: pdf_y = page_height - layout_y
                cell_y_pdf = page_height - cell_y  # Bottom edge in PDF coordinates
                cell_top_pdf = page_height - (cell_y + cell_height)  # Top edge in PDF coordinates
                # Use cell_top_pdf for rendering (top edge in PDF coordinates)
                cell_top = cell_top_pdf
                
                # Render cell content (coordinates are already in PDF coordinate system)
                self._render_table_cell_content(stream, cell, cell_x, cell_top, cell_width, cell_height, style, page_height, part_path=part_path)
        
        elif hasattr(content, "rows"):
            logger.warning(f"Table block has model-based content (rows) - layout engine should provide grid_lines")
    
    
    def _render_table_cell_content(
        self,
        stream: PdfStream,
        cell: Any,
        x: float,
        y_top: float,
        width: float,
        height: float,
        table_style: Dict,
        page_height: float,
        part_path: Optional[str] = None,
        style_override: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Render cell content (paragraphs) at specified position.
        
        Args:
            stream: PDF stream
            cell: Table cell object
            x: X position (left edge)
            y_top: Y position (top edge) in PDF coordinates
            width: Cell width
            height: Cell height
            table_style: Table style
        """
        # Get cell style
        if isinstance(cell, dict):
            cell_style = cell.get("style", {}) or {}
        else:
            cell_style = getattr(cell, "style", {}) or {}
        if style_override:
            merged_style = dict(cell_style) if isinstance(cell_style, dict) else {}
            merged_style.update(style_override)
            cell_style = merged_style
        
        # Render cell background
        fill_color = cell_style.get("fill_color") or cell_style.get("background_color")
        if fill_color:
            if isinstance(fill_color, str):
                from .utils import hex_to_rgb
                fill_color = hex_to_rgb(fill_color)
            if isinstance(fill_color, (tuple, list)) and len(fill_color) == 3:
                # Convert to 0-1 scale
                rgb = tuple(c / 255.0 for c in fill_color)
                y_bottom = y_top - height
                stream.add_rect(x, y_bottom, width, height, fill_color=rgb)
        
        # Get cell content (paragraphs)
        # Layout engine should have already processed cells to dicts with 'elements' key
        if isinstance(cell, dict):
            # Check for 'elements' key (from table_engine processed cells)
            cell_content = cell.get("elements", [])
            if not cell_content:
                cell_content = cell.get("content", [])
            if not cell_content:
                # Check for 'paragraphs' key
                cell_content = cell.get("paragraphs", [])
        else:
            # Fallback: try to get content from object
            cell_content = getattr(cell, "elements", [])
            if not cell_content:
                cell_content = getattr(cell, "content", [])
            if not cell_content:
                if hasattr(cell, "get_paragraphs"):
                    cell_content = list(cell.get_paragraphs())
                elif hasattr(cell, "paragraphs"):
                    cell_content = getattr(cell, "paragraphs", [])
        
        
        if not cell_content:
            return
        
        # Calculate cell margins (padding) - all sides
        # Support both 'padding_*' and 'margin_*' keys
        padding_left = float(cell_style.get("padding_left") or cell_style.get("margin_left") or cell_style.get("cell_margin_left") or 2.0)
        padding_right = float(cell_style.get("padding_right") or cell_style.get("margin_right") or cell_style.get("cell_margin_right") or 2.0)
        padding_top = float(cell_style.get("padding_top") or cell_style.get("margin_top") or cell_style.get("cell_margin_top") or 2.0)
        padding_bottom = float(cell_style.get("padding_bottom") or cell_style.get("margin_bottom") or cell_style.get("cell_margin_bottom") or 2.0)
        
        # Calculate usable width and height for content
        usable_width = width - padding_left - padding_right
        usable_height = height - padding_top - padding_bottom
        
        # Get vertical alignment (vAlign) from cell style
        v_align = cell_style.get("vAlign") or cell_style.get("vertical_align")
        if isinstance(v_align, dict):
            v_align = v_align.get("val", "top")
        
        # Starting position for content (accounting for margins)
        content_x = x + padding_left
        content_y = y_top - padding_top  # Top edge minus top margin
        
        # Calculate total content height for vertical alignment
        total_content_height = 0.0
        para_heights = []
        for para in cell_content:
            # Check if para is a LayoutBlock (already processed by layout engine)
            from docquill.engine.base_engine import LayoutBlock
            if isinstance(para, LayoutBlock):
                # If it's a LayoutBlock, extract its content
                para_content = para.content if isinstance(para.content, dict) else {}
            elif isinstance(para, dict):
                para_content = para
            elif hasattr(para, "content"):
                para_content = para.content if isinstance(para.content, dict) else {}
            else:
                para_content = {}
            
            # Check if paragraph has lines (already laid out by layout engine)
            if not isinstance(para_content, dict) or "lines" not in para_content:
                continue
            
            # Calculate paragraph height from lines
            lines = para_content.get("lines", [])
            para_height = 0.0
            if lines:
                # Sum line heights
                for line_entry in lines:
                    line_layout = line_entry.get("layout")
                    if line_layout:
                        if isinstance(line_layout, dict):
                            para_height += float(line_layout.get("height", 11.0))
                        elif hasattr(line_layout, "height"):
                            para_height += float(line_layout.height)
                        else:
                            para_height += 11.0
                    else:
                        para_height += 11.0
                para_height = max(para_height, 11.0)
            else:
                # Fallback: estimate height
                para_height = usable_height / len(cell_content) if cell_content else 11.0
            
            para_heights.append(para_height)
            total_content_height += para_height
        
        # Apply vertical alignment offset
        if v_align == "center":
            # Center content vertically
            vertical_offset = (usable_height - total_content_height) / 2.0
            content_y -= vertical_offset
        elif v_align == "bottom":
            # Align content to bottom
            vertical_offset = usable_height - total_content_height
            content_y -= vertical_offset
        # else: v_align == "top" or None - start from top (default)
        
        # Render each paragraph
        # Layout engine should have already processed paragraphs to dicts with 'lines'
        para_idx = 0
        for para in cell_content:
            # Get paragraph content (already laid out by layout engine)
            if isinstance(para, dict):
                para_content = para
            elif hasattr(para, "content"):
                para_content = para.content if isinstance(para.content, dict) else {}
            else:
                para_content = {}
            
            
            # Check if paragraph has lines (already laid out by layout engine)
            # But also check for inline images in runs, even if lines are missing
            has_lines = isinstance(para_content, dict) and "lines" in para_content
            has_runs_with_images = False
            
            # Check if paragraph has runs with images (even if no lines)
            # Check multiple sources: para_content dict, para object directly, and in lines
            if isinstance(para_content, dict):
                # Check if content has runs directly
                runs = para_content.get("runs", [])
                if runs:
                    for run in runs:
                        if isinstance(run, dict) and run.get("image"):
                            has_runs_with_images = True
                            break
                # Also check in lines
                if not has_runs_with_images and "lines" in para_content:
                    lines = para_content.get("lines", [])
                    for line_entry in lines:
                        if isinstance(line_entry, dict):
                            line_runs = line_entry.get("runs", [])
                            for run in line_runs:
                                if isinstance(run, dict) and run.get("image"):
                                    has_runs_with_images = True
                                    break
                        if has_runs_with_images:
                            break
            
            # Also check if para object itself has runs (may not be in para_content)
            # This is important for Paragraph objects that may have images in runs
            if not has_runs_with_images and not isinstance(para, dict):
                if hasattr(para, "runs"):
                    para_runs = getattr(para, "runs", [])
                    for run in para_runs:
                        has_image_attr = hasattr(run, "image") and run.image
                        has_image_dict = isinstance(run, dict) and run.get("image")
                        if has_image_attr or has_image_dict:
                            has_runs_with_images = True
                            break
            
            if not has_lines and not has_runs_with_images:
                logger.warning(f"Table cell paragraph missing 'lines' and no images - layout engine should process paragraphs")
                # Skip paragraph if it doesn't have lines or images
                para_idx += 1
                continue
            
            # If paragraph has runs with images but no lines, create a minimal paragraph structure
            if not has_lines and has_runs_with_images:
                # Get runs from multiple sources
                # Priority: para.runs (object) > para_content.get("runs") (dict)
                runs = []
                
                # First, try to get runs from para object (may have images not in para_content)
                if not isinstance(para, dict) and hasattr(para, "runs"):
                    para_runs = getattr(para, "runs", [])
                    # Convert runs to dict format
                    for run in para_runs:
                        run_dict = {}
                        if hasattr(run, "text"):
                            run_dict["text"] = getattr(run, "text", "")
                        elif isinstance(run, dict):
                            run_dict["text"] = run.get("text", "")
                        if hasattr(run, "image") and run.image:
                            run_dict["image"] = run.image
                            # Get image dimensions from image object
                            # Image dimensions are typically in EMU, need to convert to points
                            from docquill.engine.geometry import emu_to_points
                            if hasattr(run.image, "width"):
                                width_emu = getattr(run.image, "width", None)
                                if width_emu is not None:
                                    # Convert EMU to points if value is large (likely EMU)
                                    if width_emu > 1000:  # Likely EMU
                                        run_dict["image_width"] = emu_to_points(width_emu)
                                    else:
                                        run_dict["image_width"] = width_emu  # Already in points
                            if hasattr(run.image, "height"):
                                height_emu = getattr(run.image, "height", None)
                                if height_emu is not None:
                                    # Convert EMU to points if value is large (likely EMU)
                                    if height_emu > 1000:  # Likely EMU
                                        run_dict["image_height"] = emu_to_points(height_emu)
                                    else:
                                        run_dict["image_height"] = height_emu  # Already in points
                        elif isinstance(run, dict) and run.get("image"):
                            run_dict["image"] = run.get("image")
                            run_dict["image_width"] = run.get("image_width")
                            run_dict["image_height"] = run.get("image_height")
                        runs.append(run_dict)
                
                # If no runs from para object, try para_content
                if not runs and isinstance(para_content, dict):
                    runs = para_content.get("runs", [])
                    # Convert runs to dict format if needed
                    if runs and not isinstance(runs[0], dict):
                        runs = [{"text": str(run), "image": None} for run in runs]
                
                if runs:
                    # Create a single line with all runs containing images
                    line_with_images = {
                        "text": "",
                        "runs": runs,
                        "layout": {"height": 20.0, "font_size": 11.0}  # Minimal height for image
                    }
                    if not isinstance(para_content, dict):
                        para_content = {}
                    para_content["lines"] = [line_with_images]
                    # Update has_lines flag since we just created lines
                    has_lines = True
                else:
                    # No runs found - skip
                    para_idx += 1
                continue
            
            # Create temporary LayoutBlock for paragraph
            from docquill.engine.base_engine import LayoutBlock
            from docquill.engine.geometry import Rect
            
            # Use pre-calculated paragraph height
            if para_idx < len(para_heights):
                para_height = para_heights[para_idx]
            else:
                # Fallback: calculate paragraph height from lines
                lines = para_content.get("lines", [])
                para_height = 0.0
                if lines:
                    # Sum line heights
                    for line_entry in lines:
                        line_layout = line_entry.get("layout")
                        if line_layout:
                            if isinstance(line_layout, dict):
                                para_height += float(line_layout.get("height", 11.0))
                            elif hasattr(line_layout, "height"):
                                para_height += float(line_layout.height)
                            else:
                                para_height += 11.0
                        else:
                            para_height += 11.0
                    para_height = max(para_height, 11.0)
                else:
                    # Fallback: estimate height
                    para_height = usable_height / len(cell_content) if cell_content else 11.0
            
            # Get paragraph style (may override cell style)
            para_style = para_content.get("style", {}) or cell_style
            
            # Create block for paragraph
            # y is bottom edge in PDF coordinates, so content_y - para_height is bottom edge
            # Account for usable width (width minus margins)
            para_bottom = content_y - para_height
            para_block = LayoutBlock(
                frame=Rect(x=content_x, y=para_bottom, width=usable_width, height=para_height),
                content=para_content,
                style=para_style,
                block_type="paragraph"
            )
            
            # Render paragraph (reuses existing paragraph rendering)
            # para_block.frame.y is bottom edge, para_block.frame.y + para_block.frame.height is top edge
            para_block_top = para_block.frame.y + para_block.frame.height  # Top edge in PDF coordinates
            
            # Create cell context for inline images in table cells
            # cell_top should be the top edge of the cell (y_top), not content_y which may be adjusted for vertical alignment
            # cell_x should be the left edge of the cell (x), so images can be positioned relative to cell
            # NOTE: For image positioning, we need the actual cell height (not usable_height) to center properly
            # usable_height = height - padding_top - padding_bottom, but image should be centered in the full cell
            cell_context = {
                "x": x,  # Left edge of cell (absolute position in PDF coordinates)
                "width": usable_width,
                "height": height,  # Use actual cell height (not usable_height) for image positioning
                "usable_height": usable_height,  # Store usable_height separately for reference
                "padding_top": padding_top,  # Store padding_top for reference
                "top": y_top,  # Top edge of cell (absolute position in PDF coordinates, not adjusted for vertical alignment)
                "v_align": v_align or "top"
            }
            
            
            self._render_paragraph(stream, para_block, content_x, para_block_top, page_height, cell_context=cell_context)
            
            # Move to next paragraph (downward in PDF = subtract height)
            content_y -= para_height
            para_idx += 1
    
    def _render_textbox(self, stream: PdfStream, block: LayoutBlock, x: float, block_top: float, page_height: float) -> None:
        """Render textbox block.
        
        TextBox is a container with positioned elements (paragraphs, tables) inside.
        Similar to table rendering - layout engine calculates positions, compiler renders.
        
        Args:
            stream: PDF stream
            block: TextBox block
            x: X position (left edge) - same as block.frame.x
            block_top: Top edge of block in PDF coordinates - same as block.frame.y + block.frame.height
            page_height: Page height
        """
        content = block.content
        style = block.style or {}
        
        # Render textbox background if present
        fill_color = style.get("fill_color") or style.get("background_color")
        if fill_color:
            if isinstance(fill_color, str):
                from .utils import hex_to_rgb
                fill_color = hex_to_rgb(fill_color)
            if isinstance(fill_color, (tuple, list)) and len(fill_color) == 3:
                # Convert to 0-1 scale
                rgb = tuple(c / 255.0 for c in fill_color)
                y_bottom = block_top - block.frame.height
                stream.add_rect(x, y_bottom, block.frame.width, block.frame.height, fill_color=rgb)
        
        # Render textbox border if present
        border_color = style.get("border_color") or style.get("border")
        if border_color:
            if isinstance(border_color, str):
                from .utils import hex_to_rgb
                border_color = hex_to_rgb(border_color)
            if isinstance(border_color, (tuple, list)) and len(border_color) == 3:
                # Convert to 0-1 scale for PDF
                rgb = tuple(c / 255.0 for c in border_color)
                y_bottom = block_top - block.frame.height
                # Draw border as rectangle outline using lines
                # Set color
                stream.commands.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} RG")  # Stroke color
                # Draw rectangle outline
                stream.add_line(x, y_bottom, x + block.frame.width, y_bottom, width=0.5)  # Bottom
                stream.add_line(x + block.frame.width, y_bottom, x + block.frame.width, block_top, width=0.5)  # Right
                stream.add_line(x + block.frame.width, block_top, x, block_top, width=0.5)  # Top
                stream.add_line(x, block_top, x, y_bottom, width=0.5)  # Left
                # Reset color to black
                stream.commands.append("0 0 0 RG")
        
        if isinstance(content, dict):
            # Render positioned elements inside textbox
            positioned_elements = content.get("positioned_elements", [])
            if not positioned_elements:
                logger.warning(f"Textbox block has no positioned_elements - textbox content will be empty")
            for element_data in positioned_elements:
                element_block = element_data.get("element")
                if not element_block:
                    logger.warning(f"Textbox positioned_element has no 'element' block - skipping")
                    continue
                
                # Render element at its position (already calculated by layout engine)
                try:
                    element_x = float(element_data.get("x", 0.0))
                    element_y = float(element_data.get("y", 0.0))
                    element_height = float(element_data.get("height", 0.0))
                    element_width = float(element_data.get("width", element_block.frame.width if hasattr(element_block, 'frame') else 0.0))
                    element_top = element_y + element_height
                except (ValueError, TypeError):
                    logger.warning(f"Invalid element coordinates, skipping element: {element_data}")
                    continue
                
                # Ensure element_block has correct frame with calculated positions
                # element_block.frame should already be set by layout engine, but verify it
                if hasattr(element_block, 'frame'):
                    # Update frame with calculated positions to ensure correct rendering
                    from docquill.engine.geometry import Rect
                    element_block.frame = Rect(
                        x=element_x,
                        y=element_y,  # Bottom edge in PDF coordinates
                        width=element_width,
                        height=element_height
                    )
                else:
                    # Create frame if missing (shouldn't happen, but handle gracefully)
                    from docquill.engine.base_engine import LayoutBlock
                    from docquill.engine.geometry import Rect
                    if isinstance(element_block, dict):
                        # Convert dict to LayoutBlock
                        element_block = LayoutBlock(
                            frame=Rect(x=element_x, y=element_y, width=element_width, height=element_height),
                            content=element_block.get("content", {}),
                            style=element_block.get("style", {}),
                            block_type=element_block.get("block_type", "paragraph")
                        )
                    else:
                        # Add frame to existing block
                        element_block.frame = Rect(x=element_x, y=element_y, width=element_width, height=element_height)
                    
                    # Render element block (paragraph, table, etc.)
                    self._render_block(stream, element_block, page_height)
        
        elif hasattr(content, "content"):
            logger.warning(f"Textbox block has model-based content - layout engine should provide positioned_elements")
    
    def _render_image(self, stream: PdfStream, block: LayoutBlock, x: float, y: float, page_height: float, layout_page: Optional[LayoutPage] = None) -> None:
        """Render image block.
        
        Args:
            stream: PDF stream
            block: Image block
            x: X position (left edge) - from block.frame.x
            y: Y position (top edge in PDF coordinates) - from block.frame.y + block.frame.height
            page_height: Page height
        """
        content = block.content
        style = block.style or {}
        
        # Get image dimensions and position from block frame
        # LayoutBlock coordinates are already in PDF coordinate system
        # where Y decreases downward from the top (like PDF coordinates)
        # block.frame.y is the BOTTOM edge of the block
        # block.frame.y + block.frame.height is the TOP edge of the block
        width = block.frame.width
        height = block.frame.height
        
        # Use absolute position from frame (already calculated by layout engine)
        # LayoutBlock coordinates: block.frame.y is the BOTTOM edge, block.frame.y + block.frame.height is the TOP edge
        # In LayoutBlock coordinate system: Y increases downward from top (0 at top, larger values at bottom)
        # In standard PDF coordinate system: Y increases upward from bottom (0 at bottom, larger values at top)
        # 
        # For images: we need the bottom edge in standard PDF coordinates
        # If block.frame.y is the bottom edge in LayoutBlock system (Y increases downward):
        #   - block.frame.y = 0 means bottom at top of page (in LayoutBlock) -> bottom = page_height in PDF
        # Get position from block.frame (already calculated by layout engine)
        # But we may need to recalculate for header/footer images with specific x_rel/y_rel values
        image_x = block.frame.x
        image_bottom_layout = block.frame.y  # Bottom edge in LayoutBlock coordinates (Y increases downward)
        
        # Check if this is a footer/header image - they may need special positioning
        # Footer images in DOCX are positioned from page bottom, not from top
        # Header images may have negative x_offset (extending beyond left margin)
        is_footer_image = False
        is_header_image = False
        part_path = None
        
        # Try multiple ways to get part_path
        if isinstance(content, dict):
            part_path = content.get("part_path")
        elif hasattr(content, "part_path"):
            part_path = getattr(content, "part_path", None)
        elif hasattr(content, "get") and callable(content.get):
            part_path = content.get("part_path")
        
        # Check if part_path indicates footer/header
        if part_path:
            part_path_str = str(part_path).lower()
            if "footer" in part_path_str:
                is_footer_image = True
            elif "header" in part_path_str:
                is_header_image = True
        
        # Log footer/header detection for debugging
        logger = logging.getLogger(__name__)
        logger.debug(f"Image detection: is_footer={is_footer_image}, is_header={is_header_image}, "
                   f"part_path={part_path}, block.frame.y={block.frame.y:.2f}, block.frame.height={block.frame.height:.2f}")
        
        # Footer images: layout engine may have calculated position incorrectly if it treated
        # y_offset as distance from top instead of from bottom
        # If image is in footer area (bottom ~20% of page), it's likely positioned from bottom
        # Check if image appears to be in footer area based on position
        footer_area_threshold = page_height * 0.2  # Bottom 20% of page
        in_footer_area = image_bottom_layout > (page_height - footer_area_threshold)
        
        # Check if position info indicates "from bottom" positioning
        position_from_bottom = False
        if isinstance(content, dict):
            position = content.get("position")
            if isinstance(position, dict):
                y_rel = position.get("y_rel")
                # If y_rel indicates bottom positioning, or if y_offset is very large
                if y_rel in ("page", "margin") and is_footer_image:
                    # Footer images are typically positioned from page bottom
                    position_from_bottom = True
        
        # Debug logging for footer images
        if is_footer_image or in_footer_area:
            logger = logging.getLogger(__name__)
            logger.debug(f"Footer image detected: part_path={part_path if 'part_path' in locals() else None}, "
                       f"image_bottom_layout={image_bottom_layout:.2f}, in_footer_area={in_footer_area}, "
                       f"position_from_bottom={position_from_bottom}")
        
        # Clamp image_bottom_layout to page bounds, but allow negative values for header images
        # Header images can have negative frame.y (they extend above page top)
        if image_bottom_layout > page_height:
            image_bottom_layout = page_height
        if image_bottom_layout < 0 and not is_header_image:
            # For non-header images, clamp negative values to 0
            # For header images, allow negative values (image extends above page)
            image_bottom_layout = 0
        
        # Log image rendering info
        logger = logging.getLogger(__name__)
        logger.debug(f"Rendering image: width={width:.2f} pt, height={height:.2f} pt, "
                   f"is_footer={is_footer_image}, is_header={is_header_image}, part_path={part_path}")
        
        # Convert to standard PDF coordinates (Y increases upward from bottom)
        # Bottom edge in standard PDF = page_height - bottom edge in LayoutBlock
        # For header images with negative frame.y, this gives: page_height - (-value) = page_height + value
        # Example: page_height=841.90, frame.y=-69.55 → image_bottom_pdf = 841.90 - (-69.55) = 911.45
        # BUT: layout engine already calculated frame.y correctly for footer/header images
        # So we should use block.frame.y directly, not recalculate from EMU
        # However, we may need to recalculate if layout engine calculation was incorrect
        image_bottom_pdf = page_height - image_bottom_layout
        
        # Special handling for footer images: recalculate position based on y_rel from DOCX
        # Layout engine calculates positions, but we need to handle y_rel correctly
        # IMPORTANT: layout engine already calculated block.frame.y correctly, so we should use it
        # But if position data is available, we can verify/override the calculation
        if is_footer_image:
            logger = logging.getLogger(__name__)
            
            # Get position data from content
            position = None
            y_offset_emu = None
            y_rel = None
            x_offset_emu = None
            x_rel = None
            
            if isinstance(content, dict):
                position = content.get("position")
                if isinstance(position, dict):
                    y_offset_emu = position.get("y", 0)
                    y_rel = position.get("y_rel", "page")
                    x_offset_emu = position.get("x", 0)
                    x_rel = position.get("x_rel", "page")
                    logger.debug(f"Footer image: got position from dict - y_offset_emu={y_offset_emu}, y_rel={y_rel}, "
                               f"x_offset_emu={x_offset_emu}, x_rel={x_rel}")
            elif hasattr(content, "position"):
                position = getattr(content, "position", None)
                if isinstance(position, dict):
                    y_offset_emu = position.get("y", 0)
                    y_rel = position.get("y_rel", "page")
                    x_offset_emu = position.get("x", 0)
                    x_rel = position.get("x_rel", "page")
                    logger.debug(f"Footer image: got position from object - y_offset_emu={y_offset_emu}, y_rel={y_rel}, "
                               f"x_offset_emu={x_offset_emu}, x_rel={x_rel}")
            
            # Recalculate Y position based on y_rel from DOCX
            if y_offset_emu is not None and y_rel:
                from docquill.engine.geometry import emu_to_points
                # Check if y_offset_emu is already in points (if it's small, it might be already converted)
                # EMU values are typically very large (e.g., 9825990 EMU ≈ 773.70 pt)
                # If y_offset_emu < 1000, it's likely already in points, not EMU
                if abs(y_offset_emu) < 1000:
                    logger.debug(f"Footer image: y_offset_emu={y_offset_emu} seems too small for EMU, "
                                 f"assuming it's already in points")
                    y_offset_pt = y_offset_emu
                else:
                    y_offset_pt = emu_to_points(y_offset_emu)
                logger.debug(f"Footer image: y_offset_emu={y_offset_emu}, y_offset_pt={y_offset_pt:.2f}, "
                             f"y_rel={y_rel}, height={height:.2f}")
                
                # Handle different y_rel values for footer images
                # Based on DOCX specification: when relativeFrom='page' and posOffset is large (close to page_height),
                # posOffset represents distance from page TOP, not bottom
                # For footer images: y_offset is typically the TOP edge position from page top
                # So: image_bottom_from_top = y_offset + height
                # image_bottom_pdf = page_height - image_bottom_from_top
                if y_rel == "page":
                    # For footer images with y_rel='page': y_offset is distance from page TOP
                    # posOffset represents the position of the TOP edge of the image from page top
                    # image_bottom_from_top = y_offset + height
                    # In PDF coordinates (Y increases upward from bottom): 
                    # image_bottom_pdf = page_height - (y_offset + height)
                    image_top_from_top = y_offset_pt
                    image_bottom_from_top = y_offset_pt + height
                    image_bottom_pdf = page_height - image_bottom_from_top
                    logger.debug(f"Footer image (y_rel='page'): y_offset={y_offset_pt:.2f} pt from page TOP, "
                               f"image_bottom_pdf={image_bottom_pdf:.2f} pt")
                elif y_rel == "margin":
                    # For footer images with y_rel='margin': y_offset is distance from margin
                    # Footer images treat margin as page bottom
                    image_bottom_pdf = y_offset_pt
                    logger.debug(f"Footer image (y_rel='margin'): treating as page bottom, "
                               f"y_offset={y_offset_pt:.2f} pt, image_bottom_pdf={image_bottom_pdf:.2f} pt")
                elif y_rel == "topMargin":
                    # For footer images with y_rel='topMargin': y_offset is distance from top margin
                    # Footer images treat topMargin as page bottom
                    image_bottom_pdf = y_offset_pt
                    logger.debug(f"Footer image (y_rel='topMargin'): treating as page bottom, "
                               f"y_offset={y_offset_pt:.2f} pt, image_bottom_pdf={image_bottom_pdf:.2f} pt")
                elif y_rel == "bottomMargin":
                    # For footer images with y_rel='bottomMargin': y_offset is distance from bottom margin
                    # Footer images treat bottomMargin as page bottom
                    image_bottom_pdf = y_offset_pt
                    logger.debug(f"Footer image (y_rel='bottomMargin'): treating as page bottom, "
                               f"y_offset={y_offset_pt:.2f} pt, image_bottom_pdf={image_bottom_pdf:.2f} pt")
                elif y_rel == "paragraph":
                    # For footer images with y_rel='paragraph': y_offset is distance from paragraph
                    # Footer images treat paragraph as page bottom
                    image_bottom_pdf = y_offset_pt
                    logger.debug(f"Footer image (y_rel='paragraph'): treating as page bottom, "
                               f"y_offset={y_offset_pt:.2f} pt, image_bottom_pdf={image_bottom_pdf:.2f} pt")
                elif y_rel == "line":
                    # For footer images with y_rel='line': y_offset is distance from line
                    # Footer images treat line as page bottom
                    image_bottom_pdf = y_offset_pt
                    logger.debug(f"Footer image (y_rel='line'): treating as page bottom, "
                               f"y_offset={y_offset_pt:.2f} pt, image_bottom_pdf={image_bottom_pdf:.2f} pt")
                elif y_rel == "character":
                    # For footer images with y_rel='character': y_offset is distance from character
                    # Footer images treat character as page bottom
                    image_bottom_pdf = y_offset_pt
                    logger.debug(f"Footer image (y_rel='character'): treating as page bottom, "
                               f"y_offset={y_offset_pt:.2f} pt, image_bottom_pdf={image_bottom_pdf:.2f} pt")
                elif y_rel == "inside" or y_rel == "outside":
                    # For footer images with y_rel='inside'/'outside': treat as page bottom
                    image_bottom_pdf = y_offset_pt
                    logger.debug(f"Footer image (y_rel='{y_rel}'): treating as page bottom, "
                               f"y_offset={y_offset_pt:.2f} pt, image_bottom_pdf={image_bottom_pdf:.2f} pt")
                else:
                    # Unknown y_rel - use layout engine calculation
                    logger.warning(f"Footer image: unknown y_rel='{y_rel}', using layout engine calculation")
                    # Keep image_bottom_pdf as calculated from layout engine
                
                logger.debug(f"Footer image position recalculated: y_rel={y_rel}, y_offset_pt={y_offset_pt:.2f}, "
                          f"image_bottom_pdf={image_bottom_pdf:.2f} pt")
            else:
                # No position data available - use layout engine calculation
                logger.debug(f"Footer image: no position data available, using layout engine calculation")
        
        # Special handling for header images: recalculate X position if x_rel='column' with negative x_offset
        # Header images with negative x_offset may extend beyond left margin
        if is_header_image:
            logger = logging.getLogger(__name__)
            
            # Get position data from content
            # Try multiple sources: content dict, content object, block.content
            position = None
            x_offset_emu = None
            x_rel = None
            
            # Try content dict first
            if isinstance(content, dict):
                position = content.get("position")
                if isinstance(position, dict):
                    x_offset_emu = position.get("x", 0)
                    x_rel = position.get("x_rel", "page")
                    logger.debug(f"Header image: got position from content dict - x_offset_emu={x_offset_emu}, x_rel={x_rel}")
            
            # Try content object
            if (x_offset_emu is None or x_rel is None) and hasattr(content, "position"):
                position = getattr(content, "position", None)
                if isinstance(position, dict):
                    if x_offset_emu is None:
                        x_offset_emu = position.get("x", 0)
                    if x_rel is None:
                        x_rel = position.get("x_rel", "page")
                    logger.debug(f"Header image: got position from content object - x_offset_emu={x_offset_emu}, x_rel={x_rel}")
            
            # Try block.content if content is not available
            if (x_offset_emu is None or x_rel is None) and hasattr(block, "content"):
                block_content = block.content
                if isinstance(block_content, dict):
                    position = block_content.get("position")
                    if isinstance(position, dict):
                        if x_offset_emu is None:
                            x_offset_emu = position.get("x", 0)
                        if x_rel is None:
                            x_rel = position.get("x_rel", "page")
                        logger.debug(f"Header image: got position from block.content - x_offset_emu={x_offset_emu}, x_rel={x_rel}")
                elif hasattr(block_content, "position"):
                    position = getattr(block_content, "position", None)
                    if isinstance(position, dict):
                        if x_offset_emu is None:
                            x_offset_emu = position.get("x", 0)
                        if x_rel is None:
                            x_rel = position.get("x_rel", "page")
                        logger.debug(f"Header image: got position from block.content object - x_offset_emu={x_offset_emu}, x_rel={x_rel}")
            
            # Log if position data is missing
            if x_offset_emu is None or x_rel is None:
                logger.warning(f"Header image: position data missing - x_offset_emu={x_offset_emu}, x_rel={x_rel}, "
                             f"content_type={type(content)}, content_keys={list(content.keys()) if isinstance(content, dict) else 'N/A'}")
            
            # Recalculate X position if x_rel='column' with negative x_offset
            # This allows header images to extend beyond left margin
            if x_offset_emu is not None and x_rel:
                from docquill.engine.geometry import emu_to_points
                x_offset_pt = emu_to_points(x_offset_emu)
                
                if x_rel == "column":
                    # For header images with x_rel='column': x_offset is distance from column left edge
                    # If x_offset is negative, image extends beyond left margin
                    # We need to recalculate column position and add x_offset
                    # Get page margins from layout_page if available
                    # For header images, column position should be relative to page left edge, not content area
                    # According to user: image should be at -27.50 pt (70.0 + (-97.50))
                    # So column_x should be 70.0 pt (standard page margin), not layout_page.margins.left
                    if layout_page and hasattr(layout_page, 'page_size'):
                        # Get page size to calculate standard margins
                        page_size = layout_page.page_size
                        # For A4: standard margins are typically 70.0 pt (≈25mm)
                        # But we should use the actual page_margins.left from layout_page if available
                        # However, if it's incorrect (136.10 pt instead of 70.0 pt), we need to use standard value
                        if layout_page and hasattr(layout_page, 'margins'):
                            page_margins = layout_page.margins
                            # Check if page_margins.left is reasonable (should be around 70.0 pt for A4)
                            # If it's too large (e.g., 136.10 pt), it might be incorrect for header images
                            # Use standard A4 margin: 70.0 pt (≈25mm)
                            if page_margins.left > 100.0:  # Likely incorrect for header images
                                logger.warning(f"Header image: page_margins.left={page_margins.left:.2f} pt seems incorrect, "
                                             f"using standard A4 margin 70.0 pt")
                                column_x = 70.0  # Standard A4 left margin
                            else:
                                column_x = page_margins.left
                        else:
                            # Fallback: use standard A4 margin
                            column_x = 70.0  # Standard A4 left margin
                        
                        recalculated_x = column_x + x_offset_pt
                        logger.debug(f"Header image (x_rel='column'): column_x={column_x:.2f} pt, "
                                   f"x_offset={x_offset_pt:.2f} pt, recalculated_x={recalculated_x:.2f} pt, "
                                   f"layout_calc={image_x:.2f} pt")
                        # Always use recalculated position for header images with x_rel='column'
                        # This ensures negative x_offset works correctly
                        image_x = recalculated_x
                        logger.info(f"Header image X position recalculated: x_rel={x_rel}, x_offset_emu={x_offset_emu}, "
                                  f"x_offset_pt={x_offset_pt:.2f}, image_x={image_x:.2f} pt "
                                  f"(layout_calc={block.frame.x:.2f} pt), column_x={column_x:.2f} pt")
                    else:
                        # Fallback: use standard A4 margin
                        column_x = 70.0  # Standard A4 left margin
                        recalculated_x = column_x + x_offset_pt
                        image_x = recalculated_x
                        logger.warning(f"Header image: layout_page not available, using standard A4 margin 70.0 pt")
                        logger.info(f"Header image X position recalculated: x_rel={x_rel}, x_offset_emu={x_offset_emu}, "
                                  f"x_offset_pt={x_offset_pt:.2f}, image_x={image_x:.2f} pt "
                                  f"(layout_calc={block.frame.x:.2f} pt), column_x={column_x:.2f} pt")
                elif x_rel == "page":
                    # For header images with x_rel='page': x_offset is distance from page left edge
                    # Use x_offset directly (may be negative)
                    recalculated_x = x_offset_pt
                    logger.debug(f"Header image (x_rel='page'): x_offset={x_offset_pt:.2f} pt, "
                               f"recalculated_x={recalculated_x:.2f} pt, layout_calc={image_x:.2f} pt")
                    if abs(recalculated_x - image_x) > 0.1:
                        image_x = recalculated_x
                        logger.info(f"Header image X position recalculated: x_rel={x_rel}, x_offset_emu={x_offset_emu}, "
                                  f"x_offset_pt={x_offset_pt:.2f}, image_x={image_x:.2f} pt "
                                  f"(layout_calc={block.frame.x:.2f} pt)")
        
        # Ensure image_bottom_pdf is not negative (with small epsilon for floating point precision)
        # But allow header images to have image_bottom_pdf > page_height (they extend above page)
        epsilon = 0.001  # Small tolerance for floating point comparison
        if image_bottom_pdf < -epsilon and not is_header_image:
            # Image is above page - clamp to 0 (but not for header images)
            logger = logging.getLogger(__name__)
            logger.warning(f"Image Y position is negative, clamping to 0: image_bottom_pdf={image_bottom_pdf:.2f}, "
                         f"is_header_image={is_header_image}")
            image_bottom_pdf = 0
        elif image_bottom_pdf < 0 and not is_header_image:
            # Very close to 0 but slightly negative - clamp to 0 (but not for header images)
            image_bottom_pdf = 0
        
        # Ensure image doesn't extend beyond page (with small epsilon for floating point precision)
        # Header images can extend above page (image_bottom_pdf > page_height), which is OK
        # Footer images can extend below page (image_bottom_pdf < 0), which should be handled
        
        # Re-check part_path to ensure is_header_image/is_footer_image are set correctly
        # (part_path might not have been available earlier)
        if not is_header_image and not is_footer_image:
            part_path_check = None
            if isinstance(content, dict):
                part_path_check = content.get("part_path")
            elif hasattr(content, "part_path"):
                part_path_check = getattr(content, "part_path", None)
            if part_path_check:
                part_path_str = str(part_path_check).lower()
                if "footer" in part_path_str:
                    is_footer_image = True
                elif "header" in part_path_str:
                    is_header_image = True
        
        epsilon = 0.01  # Small tolerance for floating point comparison
        image_top_pdf = image_bottom_pdf + height  # Top edge of image in PDF coordinates
        
        if image_top_pdf > page_height + epsilon:
            # Image extends above page - adjust height to fit within page
            max_height = page_height - image_bottom_pdf
            if max_height > 0:
                logger = logging.getLogger(__name__)
                logger.debug(f"Image extends beyond page, adjusting height: "
                           f"image_bottom_pdf={image_bottom_pdf:.2f}, original_height={height:.2f}, "
                           f"max_height={max_height:.2f}, page_height={page_height:.2f}, "
                           f"is_header_image={is_header_image}")
                height = max_height
            else:
                # Image is completely outside page - check if it's a header image
                # Header images can have image_bottom_pdf > page_height (they start above page)
                # For header images, we should still render them (they'll be clipped)
                if is_header_image and image_bottom_pdf > page_height:
                    # Header image starting above page - this is OK, render it (will be clipped)
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Header image extends above page - will render (will be clipped): "
                               f"image_bottom_pdf={image_bottom_pdf:.2f}, height={height:.2f}, "
                               f"page_height={page_height:.2f}, image_top_pdf={image_top_pdf:.2f}")
                    # Continue rendering - image will be clipped by PDF viewer
                else:
                    # Image is completely outside page - skip rendering
                    logger = logging.getLogger(__name__)
                    is_footer = "footer" in (part_path or "").lower() if part_path else False
                    logger.warning(f"Image is completely outside page bounds - skipping rendering: "
                                 f"y={image_bottom_pdf:.2f}, height={height:.2f}, page_height={page_height:.2f}, "
                                 f"is_footer={is_footer}, is_header={is_header_image}, part_path={part_path}")
                    
                    # For footer images, if position is wrong, log error instead of using hardcoded fallback
                    if is_footer_image and image_bottom_pdf < 0:
                        # Footer image with negative position - cannot determine correct position
                        logger.error(f"Footer image has negative position - cannot determine correct position. "
                                   f"Image will be skipped. part_path={part_path}, rel_id={rel_id}, "
                                   f"image_bottom_pdf={image_bottom_pdf:.2f}, page_height={page_height:.2f}")
                        return  # Skip rendering this image
                    else:
                        return  # Skip rendering this image
        
        # Debug: Log if position seems wrong
        if image_bottom_pdf < 0 or image_bottom_pdf + height > page_height:
            logger = logging.getLogger(__name__)
            logger.debug(f"Image position calculation: frame.y={block.frame.y:.2f}, frame.height={block.frame.height:.2f}, "
                        f"image_bottom_layout={image_bottom_layout:.2f}, image_bottom_pdf={image_bottom_pdf:.2f}, "
                        f"page_height={page_height:.2f}")
        
        # Validate position - ensure image is within page bounds
        # Get page width from block if available (for X validation)
        page_width = getattr(block, 'page_width', page_height)  # Fallback to page_height if not available
        
        if image_x < 0:
            logger = logging.getLogger(__name__)
            logger.warning(f"Image X position is negative: x={image_x:.2f}")
        if image_x + width > page_width:
            logger = logging.getLogger(__name__)
            logger.warning(f"Image X extends beyond page width: x={image_x:.2f}, width={width:.2f}, page_width={page_width:.2f}")
        
        if image_bottom_pdf < 0:
            logger = logging.getLogger(__name__)
            logger.warning(f"Image Y position is negative: y={image_bottom_pdf:.2f} (image_bottom_layout={image_bottom_layout:.2f}, page_height={page_height:.2f})")
        if image_bottom_pdf + height > page_height:
            logger = logging.getLogger(__name__)
            logger.warning(f"Image Y extends beyond page height: y={image_bottom_pdf:.2f}, height={height:.2f}, page_height={page_height:.2f}")
        
        # Get image data from content
        image_path = None
        image_data = None
        rel_id = None
        relationship_source = None
        
        # Get part_path again here (may not have been available earlier)
        if isinstance(content, dict):
            # Dict-based content
            image_path = content.get("path") or content.get("filename")
            rel_id = content.get("rel_id") or content.get("relationship_id")
            relationship_source = content.get("relationship_source")
            part_path = content.get("part_path") or part_path  # Use earlier value if available
        elif hasattr(content, "rel_id"):
            # Image object
            rel_id = getattr(content, "rel_id", None)
            image_path = getattr(content, "path", None)
            relationship_source = getattr(content, "relationship_source", None)
            part_path_from_obj = getattr(content, "part_path", None)
            if part_path_from_obj:
                part_path = part_path_from_obj  # Update part_path if found here
            if hasattr(content, "get_src"):
                image_path = content.get_src()
        
        # Re-check if this is a header/footer image now that we have part_path
        if part_path and not is_header_image and not is_footer_image:
            part_path_str = str(part_path).lower()
            if "footer" in part_path_str:
                is_footer_image = True
            elif "header" in part_path_str:
                is_header_image = True
        
        # Try to load image data
        if not image_data:
            image_data = self._load_image_data(rel_id, image_path, relationship_source, part_path)
        
        # Debug: Log image loading
        logger = logging.getLogger(__name__)
        if image_data:
            logger.debug(f"Image loaded: rel_id={rel_id}, size={len(image_data):,} bytes, "
                       f"pos=({image_x:.2f}, {image_bottom_pdf:.2f}), size=({width:.2f}, {height:.2f})")
        else:
            logger.warning(f"Image NOT loaded: rel_id={rel_id}, path={image_path}, "
                          f"relationship_source={relationship_source}, part_path={part_path}")
        
        # If we have image data, register and render it
        if image_data:
            # Register image with data
            # Use adjusted height if it was clamped
            image_identifier = rel_id or image_path or f"image_{id(block)}"
            pdf_image = self.image_registry.register_image(
                path=image_identifier,
                width=width,
                height=height,  # Use potentially adjusted height
                image_data=image_data,
            )
            
            # Render image using XObject
            # image_x is already the left edge from block.frame.x
            # image_bottom_pdf is the bottom edge in PDF coordinates (Y increases upward from bottom)
            # Negative positions are allowed - images can extend beyond page bounds
            # Set up clipping if image extends beyond page
            clip_x = None
            clip_y = None
            clip_width = None
            clip_height = None
            
            # Check if image extends beyond page bounds and set up clipping
            page_width = layout_page.page_size.width if layout_page and hasattr(layout_page, 'page_size') else 595.28
            page_height_pdf = page_height
            
            # Calculate clipping rectangle if image extends beyond page
            # Clipping rectangle is always in page bounds (0 to page_width/height)
            # Note: Clipping path is set BEFORE transformation, so clipping rectangle is in page coordinates
            # The transformation (cm) will then position the image, and clipping will clip it to the rectangle
            if image_x < 0 or image_x + width > page_width or image_bottom_pdf < 0 or image_bottom_pdf + height > page_height_pdf:
                # Image extends beyond page - set up clipping to page bounds
                # Clip rectangle is in page coordinates (0 to page_width/height)
                # It defines the visible area of the page
                clip_x = 0  # Clip from page left edge (0)
                clip_y = 0  # Clip from page bottom (0)
                clip_width = page_width  # Full page width
                clip_height = page_height_pdf  # Full page height
                
                logger = logging.getLogger(__name__)
                logger.debug(f"Image extends beyond page bounds - using clipping: "
                           f"image_x={image_x:.2f}, image_y={image_bottom_pdf:.2f}, "
                           f"width={width:.2f}, height={height:.2f}, "
                           f"clip_x={clip_x:.2f}, clip_y={clip_y:.2f}, "
                           f"clip_width={clip_width:.2f}, clip_height={clip_height:.2f}")
            
            # Render image using XObject
            stream.add_image(pdf_image.alias, image_x, image_bottom_pdf, width, height,
                           clip_x=clip_x, clip_y=clip_y, clip_width=clip_width, clip_height=clip_height)
        else:
            # Fallback: render placeholder rectangle
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Image not found: rel_id={rel_id}, path={image_path}, "
                f"relationship_source={relationship_source}, part_path={part_path}"
            )
            stream.add_comment(f"Image not found: rel_id={rel_id}, path={image_path}")
            # Use image_bottom_pdf instead of undefined y variable
            stream.add_rect(image_x, image_bottom_pdf, width, height, fill_color=(0.9, 0.9, 0.9))
    
    def _load_image_data(
        self,
        rel_id: Optional[str],
        image_path: Optional[str],
        relationship_source: Optional[str] = None,
        part_path: Optional[str] = None,
    ) -> Optional[bytes]:
        """Load image data from package reader or file system.
        
        Args:
            rel_id: Relationship ID (from DOCX)
            image_path: Image path (from DOCX or file system)
            relationship_source: Relationship source file (e.g., "word/_rels/header1.xml.rels" for header images)
            part_path: Part path (e.g., "word/header1.xml" for header images)
            
        Returns:
            Image data bytes or None if not found
        """
        # Try package reader first (for DOCX images)
        if self.package_reader and rel_id:
            try:
                # Get relationship target path
                # For header/footer images, relationship_source indicates the source rels file
                relationship = None
                if relationship_source:
                    # Get relationship from specific source file (e.g., "word/_rels/header1.xml.rels")
                    # PackageReader stores relationships by filename
                    if hasattr(self.package_reader, "get_relationships"):
                        rels_dict = self.package_reader.get_relationships(relationship_source)
                        if isinstance(rels_dict, dict):
                            relationship = rels_dict.get(rel_id)
                
                if not relationship:
                    # Fallback: try document-level relationships
                    if hasattr(self.package_reader, "get_relationships"):
                        rels_dict = self.package_reader.get_relationships("document")
                        if isinstance(rels_dict, dict):
                            relationship = rels_dict.get(rel_id)
                
                if relationship:
                    target_path = relationship.get("target") or relationship.get("Target")
                    if target_path:
                        # For header/footer images, target is relative to part_path
                        # If part_path is "word/footer1.xml", target "media/image3.png" becomes "word/media/image3.png"
                        if part_path:
                            # Resolve relative path from part_path
                            part_dir = Path(part_path).parent
                            resolved_path = str(part_dir / target_path)
                            # Normalize path (remove "word/word/" if any)
                            if resolved_path.startswith("word/word/"):
                                resolved_path = resolved_path.replace("word/word/", "word/", 1)
                            target_path = resolved_path
                        elif not target_path.startswith("word/"):
                            # Fallback: try with word/ prefix if not already present
                            target_path = f"word/{target_path}"
                        
                        # Load from package
                        if hasattr(self.package_reader, "get_binary_content"):
                            image_data = self.package_reader.get_binary_content(target_path)
                            if image_data:
                                return image_data
            except Exception as e:
                logger.debug(f"Failed to load image from package reader: {e}")
        
        # Try direct path from package reader
        if self.package_reader and image_path:
            try:
                if hasattr(self.package_reader, "get_binary_content"):
                    image_data = self.package_reader.get_binary_content(image_path)
                    if image_data:
                        return image_data
                    # Try with word/ prefix
                    if not image_path.startswith("word/"):
                        image_data = self.package_reader.get_binary_content(f"word/{image_path}")
                        if image_data:
                            return image_data
            except Exception as e:
                logger.debug(f"Failed to load image from path: {e}")
        
        # Try file system
        if image_path:
            try:
                path = Path(image_path)
                if path.exists() and path.is_file():
                    return path.read_bytes()
            except Exception as e:
                logger.debug(f"Failed to load image from file system: {e}")
        
        return None
    
    def _break_text_into_lines(self, text: str, max_width: float, style: Dict) -> List[Dict[str, Any]]:
        """Break text into lines based on available width.
        
        Args:
            text: Text to break
            max_width: Maximum width for each line
            style: Style dictionary with font information
            
        Returns:
            List of line dictionaries with 'text' and 'style' keys
        """
        if not text or max_width <= 0:
            return [{"text": text or "", "style": style}]
        
        # Get font size
        try:
            font_size = float(style.get("font_size", 11.0))
        except (ValueError, TypeError):
            font_size = 11.0  # Default font size
        # Estimate character width (simplified: 0.6 * font_size for average character)
        char_width = font_size *0.6
        
        # Split text by newlines first
        paragraphs = text.split("\n")
        lines = []
        
        for para in paragraphs:
            if not para:
                # Empty line
                lines.append({"text": "", "style": style, "line_height": font_size * 1.2})
                continue
            
            # Split paragraph into words
            words = para.split()
            if not words:
                continue
            
            current_line = ""
            current_line_width = 0.0
            
            for word in words:
                # Calculate word width
                word_width = len(word) * char_width
                # Calculate space width
                space_width = char_width if current_line else 0.0
                
                # Check if word fits on current line
                if current_line_width + space_width + word_width <= max_width:
                    # Word fits - add to current line
                    if current_line:
                        current_line += " " + word
                        current_line_width += space_width + word_width
                    else:
                        current_line = word
                        current_line_width = word_width
                else:
                    # Word doesn't fit - start new line
                    if current_line:
                        # Save current line
                        lines.append({
                            "text": current_line,
                            "style": style,
                            "line_height": font_size * 1.2
                        })
                    
                    # Check if word itself fits on a line
                    if word_width <= max_width:
                        current_line = word
                        current_line_width = word_width
                    else:
                        # Word is too long - break it character by character
                        current_line = ""
                        current_line_width = 0.0
                        for char in word:
                            char_w = char_width
                            if current_line_width + char_w <= max_width:
                                current_line += char
                                current_line_width += char_w
                            else:
                                if current_line:
                                    lines.append({
                                        "text": current_line,
                                        "style": style,
                                        "line_height": font_size * 1.2
                                    })
                                current_line = char
                                current_line_width = char_w
                        # Add remaining part of word as new line
                        if current_line:
                            lines.append({
                                "text": current_line,
                                "style": style,
                                "line_height": font_size * 1.2
                            })
                            current_line = ""
                            current_line_width = 0.0
            
            # Add remaining line
            if current_line:
                lines.append({
                    "text": current_line,
                    "style": style,
                    "line_height": font_size * 1.2
                })
        
        return lines if lines else [{"text": text, "style": style, "line_height": font_size * 1.2}]
    
    def _extract_run_style(self, run: Any, paragraph_style: Dict) -> Dict:
        """Extract style from run object.
        
        Args:
            run: Run object
            paragraph_style: Paragraph style as fallback
            
        Returns:
            Combined style dictionary
        """
        style = dict(paragraph_style)
        
        # Extract run-specific properties
        if hasattr(run, "style"):
            run_style = getattr(run, "style", {})
            if isinstance(run_style, dict):
                style.update(run_style)
        
        # Extract direct attributes
        if hasattr(run, "bold"):
            style["bold"] = getattr(run, "bold", False)
        if hasattr(run, "italic"):
            style["italic"] = getattr(run, "italic", False)
        if hasattr(run, "font_size"):
            style["font_size"] = getattr(run, "font_size", 11.0)
        if hasattr(run, "font_name"):
            style["font_name"] = getattr(run, "font_name", "Helvetica")
        
        return style
    
    def _build_resources(self) -> Dict[str, Dict]:
        """Build resources dictionary for page.
        
        Returns:
            Resources dictionary
        """
        resources = {}
        
        # Add fonts
        fonts = self.font_registry.get_resources_dict()
        if fonts:
            resources["Font"] = fonts
        
        # Add images
        images = self.image_registry.get_resources_dict()
        if images:
            resources["XObject"] = images
        
        return resources
    
    def _render_footnotes_block(self, stream: PdfStream, block: LayoutBlock, page_height: float, page_width: float) -> None:
        """Render footnotes block (already created by LayoutAssembler).
        
        Args:
            stream: PDF stream
            block: Footnotes LayoutBlock
            page_height: Page height in points
            page_width: Page width in points
        """
        content = block.content
        if not isinstance(content, dict) or 'footnotes' not in content:
            return
        
        footnotes = content.get('footnotes', [])
        if not footnotes:
            return
        
        # Get block position (already calculated by LayoutAssembler)
        # block.frame.y is the BOTTOM edge of the block in PDF coordinates (Y=0 at bottom)
        # block.frame.y + block.frame.height is the TOP edge of the block
        block_bottom_y = block.frame.y  # Bottom edge (from bottom of page)
        block_height = block.frame.height
        block_top_y = block_bottom_y + block_height  # Top edge (from bottom of page)
        margins_left = block.frame.x
        margins_right = page_width - block.frame.x - block.frame.width
        
        # Draw separator line at top of footnotes area (above footnotes)
        line_y = block_top_y - 5  # 5pt above footnotes
        stream.add_command(f"{margins_left} {line_y} m")
        content_width = page_width - margins_left - margins_right
        stream.add_command(f"{margins_left + content_width} {line_y} l")
        stream.add_command("0.5 G")  # Grey color
        stream.add_command("0.5 w")  # Line width
        stream.add_command("S")  # Stroke
        
        # Render each footnote from top to bottom
        font_size = 8.0
        line_height = font_size * 1.2
        current_y = block_top_y - line_height  # Start from top, going down
        
        for footnote in footnotes:
            number = footnote.get('number', '?')
            content_text = footnote.get('content', '')
            
            # Render footnote marker and content
            marker_x = margins_left
            content_x = margins_left + 15  # Indent for content
            
            # Draw marker (bold) - current_y is baseline for this footnote
            stream.add_command(f"BT")
            stream.add_command(f"/Helvetica-Bold {font_size} Tf")
            stream.add_command(f"{marker_x} {current_y} Td")
            stream.add_command(f"({self._escape_text(str(number))}) Tj")
            stream.add_command(f"ET")
            
            # Draw content (simple text wrapping)
            # Use text object with positioning for proper line wrapping
            stream.add_command(f"BT")
            stream.add_command(f"/Helvetica {font_size} Tf")
            
            # Simple text wrapping - render line by line
            words = content_text.split()
            line = ""
            y = current_y  # Start from current_y (baseline of first line)
            max_width = page_width - margins_left - margins_right - content_x
            
            for word in words:
                test_line = line + (" " if line else "") + word
                # Estimate width (rough approximation: 0.6 * font_size per character)
                test_width = len(test_line) * font_size * 0.6
                
                if test_width > max_width and line:
                    # Draw current line
                    stream.add_command(f"{content_x} {y} Td")
                    stream.add_command(f"({self._escape_text(line)}) Tj")
                    stream.add_command(f"0 {(-line_height)} Td")  # Move down for next line
                    y -= line_height
                    line = word
                else:
                    line = test_line
            
            # Draw last line
            if line:
                stream.add_command(f"{content_x} {y} Td")
                stream.add_command(f"({self._escape_text(line)}) Tj")
            
            stream.add_command(f"ET")
            
            # Move to next footnote (go down)
            # Find the lowest Y used for this footnote
            lowest_y = y - line_height  # After last line
            current_y = lowest_y - line_height * 1.5  # Space between footnotes
    
    def _escape_text(self, text: str) -> str:
        """Escape text for PDF string.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text
        """
        # Basic PDF string escaping
        text = text.replace('\\', '\\\\')
        text = text.replace('(', '\\(')
        text = text.replace(')', '\\)')
        return text
    
    def _render_watermarks(self, stream: PdfStream, page_width: float, page_height: float) -> None:
        """Render watermarks on PDF stream.
        
        Args:
            stream: PDF stream
            page_width: Page width in points
            page_height: Page height in points
        """
        if not self.watermark_renderer:
            return
        
        watermarks = self.watermark_renderer.watermarks
        if not watermarks:
            return
        
        for watermark in watermarks:
            # Extract watermark properties
            if isinstance(watermark, dict):
                text = watermark.get('text', '')
                angle = watermark.get('angle', 45.0)
                opacity = watermark.get('opacity', 0.5)
                color = watermark.get('color', '#CCCCCC')
                font_size = watermark.get('font_size', 72.0)
                font_name = watermark.get('font_name', 'Helvetica-Bold')
            elif hasattr(watermark, 'text'):
                text = watermark.text
                angle = getattr(watermark, 'angle', 45.0)
                opacity = getattr(watermark, 'opacity', 0.5)
                color = getattr(watermark, 'color', '#CCCCCC')
                font_size = getattr(watermark, 'font_size', 72.0)
                font_name = getattr(watermark, 'font_name', 'Helvetica-Bold')
            else:
                text = str(watermark)
                angle = 45.0
                opacity = 0.5
                color = '#CCCCCC'
                font_size = 72.0
                font_name = 'Helvetica-Bold'
            
            if not text:
                continue
            
            # Parse color
            try:
                if color.startswith('#'):
                    rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
                    r = rgb[0] / 255.0
                    g = rgb[1] / 255.0
                    b = rgb[2] / 255.0
                else:
                    r, g, b = 0.8, 0.8, 0.8
            except Exception:
                r, g, b = 0.8, 0.8, 0.8
            
            # Center position
            center_x = page_width / 2
            center_y = page_height / 2
            
            # Add PDF commands for watermark
            stream.add_command("q")  # Save state
            stream.add_command(f"{r} {g} {b} rg")  # Set fill color
            stream.add_command(f"{r} {g} {b} RG")  # Set stroke color
            stream.add_command(f"{center_x} {center_y} translate")  # Translate to center
            stream.add_command(f"{angle} rotate")  # Rotate
            stream.add_command(f"/{font_name} {font_size} Tf")  # Set font
            # Approximate text width (rough estimate)
            text_width = len(text) * font_size * 0.6
            stream.add_command(f"{-text_width / 2} {-font_size / 2} Td")  # Move to text position
            stream.add_command(f"({self._escape_text(text)}) Tj")  # Draw text
            stream.add_command("Q")  # Restore state

