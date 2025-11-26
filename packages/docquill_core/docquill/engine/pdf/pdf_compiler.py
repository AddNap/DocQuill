"""

PDFCompiler - production layout renderer to PDF
-------------------------------------------------
Transforms UnifiedLayout into ready PDF file
preserving margins, header/footer, fonts and styles.

Can use Rust renderer (pdf-writer) as alternative to ReportLab.

"""

from __future__ import annotations

import logging
from pathlib import Path
import os
import tempfile
import hashlib
import multiprocessing
from typing import Any, Dict, List, Optional, Tuple, Union

# Try to import Rust renderer
try:
    from .pdf_compiler_rust import PDFCompilerRust, HAS_RUST_RENDERER
except ImportError:
    HAS_RUST_RENDERER = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import black, Color
    from reportlab.pdfbase import pdfmetrics
    from reportlab.lib.utils import ImageReader
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    canvas = None  # type: ignore
    A4 = None  # type: ignore
    black = None  # type: ignore
    Color = None  # type: ignore
    pdfmetrics = None  # type: ignore
    ImageReader = None  # type: ignore

from ..text_metrics import TextMetricsEngine, TextLayout
from ..text_alignment import TextAlignmentEngine
from ..kerning_engine import KerningEngine
from ..ligature_engine import LigatureEngine
from ..geometry import Rect, Size, twips_to_points
from ..unified_layout import UnifiedLayout, LayoutBlock
from ..layout_primitives import BlockContent, ParagraphLayout, OverlayBox
from ..utils.font_utils import resolve_font_variant
from ..utils.font_registry import register_default_fonts
from ...media import MediaConverter
from ...models.field import Field

try:
    from PyPDF2 import PdfMerger
    PYPDF2_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYPDF2_AVAILABLE = False
    PdfMerger = None  # type: ignore

_PARALLEL_LAYOUT: Optional[UnifiedLayout] = None
_PARALLEL_PAGE_SIZE: Optional[Tuple[float, float]] = None
_PARALLEL_PACKAGE_READER: Optional[Any] = None
_PARALLEL_TOTAL_PAGES: int = 0

# Import funkcji do renderowania borders i background
try:
    from ...renderers.render_utils import draw_background, draw_border, draw_shadow, to_color
except ImportError:  # pragma: no cover - fallback path for minimal installs
    from reportlab.lib.colors import Color, HexColor

    def _fallback_to_color(value: object, fallback: str = "#000000") -> Color:
        if isinstance(value, Color):
            return value
        if isinstance(value, (tuple, list)) and len(value) == 3:
            try:
                r, g, b = (float(v) for v in value)
                return Color(r, g, b)
            except Exception:
                return HexColor(fallback)

        token = str(value or "").strip()
        if not token or token.lower() == "auto":
            return HexColor(fallback)
        if token.startswith("#"):
            candidate = token
        elif len(token) in {3, 6} and all(ch in "0123456789abcdefABCDEF" for ch in token):
            candidate = f"#{token}"
        else:
            candidate = token

        try:
            return HexColor(candidate)
        except Exception:
            return HexColor(fallback)

    def _fallback_to_float(value: object, default: float = 0.0) -> float:
        if value in (None, "", False):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except Exception:
            return default

    def _fallback_normalize_border_spec(raw) -> Optional[Dict[str, Any]]:
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
        if str(raw.get("val") or raw.get("style") or "").lower() in {"none", "nil"}:
            return None
        width = _fallback_to_float(raw.get("width"))
        if not width and raw.get("sz"):
            try:
                width = float(raw["sz"]) / 8.0
            except Exception:
                width = None
        if not width or width <= 0:
            width = 1.0
        color_value = raw.get("color") or raw.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color") or "#000000"
        radius = _fallback_to_float(raw.get("radius"), 0.0)
        style_name = raw.get("style") or raw.get("val") or raw.get("type") or "solid"
        return {
            "width": width,
            "color": color_value,
            "style": style_name,
            "radius": radius,
        }

    def _fallback_apply_border_style(canvas, border_spec: Dict[str, Any]) -> None:
        width = max(border_spec.get("width", 1.0), 0.01)
        color = _fallback_to_color(border_spec.get("color") or "#000000")
        style_name = str(border_spec.get("style") or "solid").lower()
        canvas.setLineWidth(width)
        canvas.setStrokeColor(color)
        if style_name == "dashed":
            canvas.setDash(6, 3)
        elif style_name == "dotted":
            canvas.setDash(1, 2)

    def to_color(color, fallback="#000000"):
        return _fallback_to_color(color, fallback)

    def draw_background(canvas, frame, style):
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
        canvas.setFillColor(_fallback_to_color(background))
        canvas.rect(frame.x, frame.y, frame.width, frame.height, fill=1, stroke=0)
        canvas.restoreState()

    def draw_border(canvas, frame, style):
        if not style:
            return
        border = style.get("border")
        borders = style.get("borders")
        if border or not borders:
            spec = _fallback_normalize_border_spec(border)
            if not spec:
                return
            canvas.saveState()
            _fallback_apply_border_style(canvas, spec)
            radius = spec.get("radius", 0.0)
            if radius and radius > 0:
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
            spec = _fallback_normalize_border_spec(borders.get(side))
            if not spec:
                continue
            canvas.saveState()
            _fallback_apply_border_style(canvas, spec)
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

    def draw_shadow(canvas, frame, style):
        if not style:
            return
        shadow = style.get("shadow")
        if not shadow or (isinstance(shadow, bool) and not shadow):
            return
        if isinstance(shadow, dict):
            color = _fallback_to_color(shadow.get("color", "#888888"))
            dx = _fallback_to_float(shadow.get("offset_x"), 2.0)
            dy = _fallback_to_float(shadow.get("offset_y"), -2.0)
        else:
            color = _fallback_to_color("#888888")
            dx = 2.0
            dy = -2.0
        canvas.saveState()
        canvas.setFillColor(color)
        canvas.rect(frame.x + dx, frame.y + dy, frame.width, frame.height, fill=1, stroke=0)
        canvas.restoreState()

logger = logging.getLogger(__name__)


class PDFCompiler:
    """

    Production PDF compiler from UnifiedLayout.

    Renders all block types (paragraph, table, image, textbox)
    using TextMetricsEngine, TextAlignmentEngine, KerningEngine and LigatureEngine.

    """

    _IMAGE_TARGET_DPI = 192.0  # Prefer higher-than-screen DPI to avoid EMF raster degradation
    
    def __init__(
        self,
        output_path: Union[str, Path] = "output.pdf",
        page_size: Optional[Tuple[float, float]] = None,
        package_reader: Optional[Any] = None,
        footnote_renderer: Optional[Any] = None,
        image_cache: Optional[Any] = None,
        *,
        parallelism: int = 1,
        merge_tmp_dir: Optional[Union[str, Path]] = None,
        use_rust: bool = False,
        watermark_opacity: Optional[float] = None,
    ):
        """

        PDFCompiler initialization.

        Args:
        output_path: Path to output PDF file
        page_size: Page size (width, height) in points. If None, uses A4.
        package_reader: PackageReader for resolving image paths from relationship_id (optional)
        footnote_renderer: FootnoteRenderer for rendering footnote/endnote references (optional)
        parallelism: Number of processes used for page rendering (>=1).
        merge_tmp_dir: Optional directory for temporary PDF fragments (for parallel mode).
        use_rust: If True, uses Rust renderer instead of ReportLab (supports multithreading).

        """
        self.use_rust = use_rust
        
        # Check if Rust renderer is available when requested
        if use_rust:
            try:
                from .rust_canvas import HAS_RUST_RENDERER
                if not HAS_RUST_RENDERER:
                    logger.warning("Rust renderer requested but not available, falling back to ReportLab")
                    self.use_rust = False
            except ImportError:
                logger.warning("Rust renderer requested but not available, falling back to ReportLab")
                self.use_rust = False
        
        # Check ReportLab availability (only if not using Rust)
        if not self.use_rust and not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab jest wymagany do generowania PDF. Zainstaluj: pip install reportlab")
        
        self.output_path = Path(output_path)
        self.page_size = page_size if page_size else A4
        self.package_reader = package_reader
        self.footnote_renderer = footnote_renderer
        self.image_cache = image_cache  # Image conversion cache for pre-converted images
        self.parallelism = max(int(parallelism), 1)
        self.merge_tmp_dir = Path(merge_tmp_dir) if merge_tmp_dir else None
        self.watermark_opacity_override = self._normalize_opacity_value(watermark_opacity)
        
        # Initialize Rust renderer if using Rust
        if self.use_rust:
            try:
                # Import from rust_pdf_canvas.rust_pdf_canvas (maturin creates it this way)
                # The Rust module is compiled as rust_pdf_canvas.abi3.so in the package
                try:
                    from rust_pdf_canvas import PdfCanvasRenderer
                except (ImportError, AttributeError):
                    # Fallback: manually load the Rust module from .so file
                    import importlib.util
                    import sys
                    import os
                    
                    # Find the .so file in site-packages (check both venv and system paths)
                    rust_module_path = None
                    for site_path in sys.path:
                        if 'site-packages' in site_path:
                            candidate = os.path.join(site_path, 'rust_pdf_canvas', 'rust_pdf_canvas.abi3.so')
                            if os.path.exists(candidate):
                                rust_module_path = candidate
                                break
                    
                    # Also check .venv if it exists
                    if not rust_module_path:
                        venv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.venv', 'lib', 'python3.10', 'site-packages', 'rust_pdf_canvas', 'rust_pdf_canvas.abi3.so')
                        if os.path.exists(venv_path):
                            rust_module_path = venv_path
                    
                    if rust_module_path:
                        # Load the module manually
                        spec = importlib.util.spec_from_file_location('rust_pdf_canvas', rust_module_path)
                        rust_mod = importlib.util.module_from_spec(spec)
                        # Register it in sys.modules so it can be imported later
                        sys.modules['rust_pdf_canvas.rust_pdf_canvas'] = rust_mod
                        spec.loader.exec_module(rust_mod)
                        PdfCanvasRenderer = rust_mod.PdfCanvasRenderer
                    else:
                        raise ImportError("Could not find rust_pdf_canvas.abi3.so")
                
                self.rust_renderer = PdfCanvasRenderer(
                    str(self.output_path),
                    self.page_size[0],
                    self.page_size[1]
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Rust renderer: {e}, falling back to ReportLab")
                self.use_rust = False
                self.rust_renderer = None
        else:
            self.rust_renderer = None
        
        # Engines
        self.metrics = TextMetricsEngine()
        self.aligner = TextAlignmentEngine()
        self.kerning = KerningEngine(self.metrics)
        self.ligatures = LigatureEngine(self.metrics)
        self.media_converter = MediaConverter()
        self._temp_files: list[Path] = []
        self._converted_images: dict[str, Path] = {}
        self._total_pages: int = 1
        self._current_page_number: int = 1
        self._current_timings: Optional[Dict[str, List[float]]] = None
        
        # Enable font parsing cache for performance (saves ~0.7s on font parsing)
        # Only for ReportLab (Rust has its own font handling)
        if not self.use_rust:
            from ..utils.font_registry import enable_font_parsing_cache
            enable_font_parsing_cache()
        register_default_fonts()
        
        logger.info(f"PDFCompiler zainicjalizowany: output={self.output_path}, page_size={self.page_size}, backend={'Rust' if self.use_rust else 'ReportLab'}, parallelism={self.parallelism}, package_reader={'yes' if package_reader else 'no'}, footnote_renderer={'yes' if footnote_renderer else 'no'}")
    
    # ----------------------------------------------------------------------
    # Main compilation method
    # ----------------------------------------------------------------------

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
    
    def compile(self, unified_layout: UnifiedLayout, timings: Optional[Dict[str, List[float]]] = None) -> Path:
        """

        Main method - renders all pages to PDF.

        Args:
        unified_layout: UnifiedLayout with ready document layout
        timings: Optional dictionary for collecting operation times

        Returns:
        Path to generated PDF file

        """
        import time
        
        if not unified_layout.pages:
            raise ValueError("UnifiedLayout nie zawiera żadnych stron")
        
        # Create output directory if needed
        t0 = time.time()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if timings is not None:
            if 'compile_setup' not in timings:
                timings['compile_setup'] = []
            timings['compile_setup'].append(time.time() - t0)

        self._total_pages = max(len(unified_layout.pages), 1)
        self._current_page_number = 1

        try:
            t0 = time.time()
            # Rust renderer supports true parallelism (multithreading)
            # ReportLab parallelism uses multiprocessing (slower)
            if self.use_rust:
                if self.parallelism > 1 and len(unified_layout.pages) > 1:
                    self._render_parallel_rust(unified_layout, timings=timings)
                else:
                    self._render_sequential_rust(unified_layout, timings=timings)
            else:
                # ReportLab rendering
                if self.parallelism > 1 and len(unified_layout.pages) > 1:
                    try:
                        self._render_parallel(unified_layout, timings=timings)
                    except Exception:
                        logger.exception(
                            "Parallel PDF rendering failed – falling back to sequential mode"
                        )
                        self._render_sequential(unified_layout, timings=timings)
                else:
                    self._render_sequential(unified_layout, timings=timings)
            if timings is not None:
                if 'compile_render_all' not in timings:
                    timings['compile_render_all'] = []
                timings['compile_render_all'].append(time.time() - t0)
        finally:
            t0 = time.time()
            self._cleanup_temp_artifacts()
            if timings is not None:
                if 'compile_cleanup' not in timings:
                    timings['compile_cleanup'] = []
                timings['compile_cleanup'].append(time.time() - t0)
        
        logger.info(f"✅ PDF zapisany jako {self.output_path}")
        return self.output_path

    def _render_sequential_rust(self, unified_layout: UnifiedLayout, start_page_number: Optional[int] = None, timings: Optional[Dict[str, List[float]]] = None) -> None:
        """

        Render all pages sequentially using Rust renderer.

        Args:
        unified_layout: UnifiedLayout with pages to render
        start_page_number: Optional offset for page numbers
        timings: Optional dictionary for collecting operation times

        """
        import time
        import sys
        from .rust_canvas import RustCanvas
        
        rust_timings = {
            "content_prep": 0.0,
            "rust_calls": 0.0,
            "save": 0.0,
        }
        total_rust_call_count = 0  # Track total number of Rust calls across all pages
        
        t0 = time.time()
        if timings is not None:
            if 'render_create_canvas' not in timings:
                timings['render_create_canvas'] = []
            timings['render_create_canvas'].append(time.time() - t0)
        
        for page_index, page in enumerate(unified_layout.pages, start=1):
            # Set page number
            if hasattr(page, 'number') and page.number:
                self._current_page_number = int(page.number)
            else:
                self._current_page_number = page_index
            
            # Get page size
            page_width = self.page_size[0]
            page_height = self.page_size[1]
            if hasattr(page, 'size'):
                page_width = page.size.width
                page_height = page.size.height
            
            # Create new page in Rust renderer
            t0 = time.time()
            self.rust_renderer.new_page(page_width, page_height)
            if timings is not None:
                if 'render_create_page' not in timings:
                    timings['render_create_page'] = []
                timings['render_create_page'].append(time.time() - t0)
            
            # Wrap Rust renderer in RustCanvas
            # RustCanvas will delegate canvas operations to the renderer
            # Pass metrics engine for text width measurement
            rust_canvas = RustCanvas(self.rust_renderer, page_width, page_height, self.metrics)
            
            # Render page using same logic as ReportLab (all _draw_* methods work with RustCanvas)
            t0 = time.time()
            self._render_page(rust_canvas, page, timings=timings)
            # Flush any pending batched commands before moving to next page
            rust_canvas.flush()
            page_render_time = time.time() - t0
            rust_timings["rust_calls"] += page_render_time
            
            # Collect Rust call statistics (if available)
            if hasattr(rust_canvas, 'get_profiling_stats'):
                stats = rust_canvas.get_profiling_stats()
                total_rust_call_count += stats.get('call_count', 0)
            if timings is not None:
                if 'render_page_total' not in timings:
                    timings['render_page_total'] = []
                timings['render_page_total'].append(time.time() - t0)
        
        # Finalize and save PDF
        t0 = time.time()
        self.rust_renderer.save()
        rust_timings["save"] = time.time() - t0
        if timings is not None:
            if 'render_save_canvas' not in timings:
                timings['render_save_canvas'] = []
            timings['render_save_canvas'].append(time.time() - t0)
        
        # Print Rust-specific timings
        rust_timings["total"] = rust_timings["content_prep"] + rust_timings["rust_calls"] + rust_timings["save"]
        # Include call count in output for analysis
        call_count_str = f",call_count={total_rust_call_count}" if total_rust_call_count > 0 else ""
        # Use print() to stdout for benchmark parsing (not logger, as benchmark script parses stdout)
        print(f"RUST_TIMINGS:content_prep={rust_timings['content_prep']:.6f},rust_calls={rust_timings['rust_calls']:.6f},save={rust_timings['save']:.6f},total={rust_timings['total']:.6f}{call_count_str}", flush=True)
        
        # Print detailed render timings if available
        if timings is not None:
            detail_parts = []
            for key in ['render_sort_blocks', 'render_resolve_content', 'render_watermarks', 
                       'render_headers', 'render_headers_table', 'render_headers_paragraph', 
                       'render_headers_image', 'render_headers_textbox', 'render_headers_decorator', 
                       'render_headers_other', 'render_body_total', 'render_paragraphs', 'render_tables', 
                       'render_images', 'render_textboxes', 'render_decorators', 'render_footnotes', 
                       'render_footers', 'draw_paragraph_from_layout', 'draw_paragraph_setup', 
                       'draw_paragraph_lines', 'draw_paragraph_inline_items', 'draw_paragraph_rust_calls',
                       'draw_paragraph_line_count', 'draw_paragraph_inline_count']:
                if key in timings and timings[key]:
                    total_time = sum(timings[key])
                    count = len(timings[key])
                    avg_time = total_time / count if count > 0 else 0.0
                    detail_parts.append(f"{key}={total_time:.6f}(avg={avg_time:.6f},count={count})")
            if detail_parts:
                print(f"RENDER_DETAILS:{','.join(detail_parts)}", flush=True)

    def _render_parallel_rust(self, unified_layout: UnifiedLayout, timings: Optional[Dict[str, List[float]]] = None) -> None:
        """

        Render pages in parallel using Rust renderer (multithreading).

        Args:
        unified_layout: UnifiedLayout with pages to render
        timings: Optional dictionary for collecting operation times

        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from .rust_canvas import RustCanvas
        
        page_count = len(unified_layout.pages)
        if page_count == 0:
            raise ValueError("Brak stron do renderowania.")
        
        # Render pages in parallel using threads
        # Each page gets its own renderer instance (thread-safe)
        def render_page(page_data):
            """Render single page in thread."""
            page, page_index = page_data
            
            # Set page number
            if hasattr(page, 'number') and page.number:
                page_number = int(page.number)
            else:
                page_number = page_index
            
            # Get page size
            page_width = self.page_size[0]
            page_height = self.page_size[1]
            if hasattr(page, 'size'):
                page_width = page.size.width
                page_height = page.size.height
            
            # Create temporary renderer for this page
            # Note: We'll need to merge pages later
            import tempfile
            import pdf_renderer_rust
            temp_path = tempfile.mktemp(suffix='.pdf')
            page_renderer = pdf_renderer_rust.PdfRenderer(temp_path, page_width, page_height)
            page_renderer.new_page(page_width, page_height)
            
            # Wrap Rust renderer in RustCanvas
            # Pass metrics engine for text width measurement
            rust_canvas = RustCanvas(page_renderer, page_width, page_height, self.metrics)
            
            # Render page (all business logic stays the same)
            # Temporarily set page number for field codes
            old_page_number = self._current_page_number
            self._current_page_number = page_number
            try:
                self._render_page(rust_canvas, page, timings=None)  # Don't collect timings in parallel
                # Flush any pending batched commands before saving page
                rust_canvas.flush()
            finally:
                self._current_page_number = old_page_number
            
            # Finalize page
            page_renderer.save()
            
            return (page_index, temp_path, page_width, page_height)
        
        # Render all pages in parallel
        t0 = time.time()
        page_data_list = [(page, idx) for idx, page in enumerate(unified_layout.pages, start=1)]
        
        rendered_pages = []
        with ThreadPoolExecutor(max_workers=self.parallelism) as executor:
            futures = {executor.submit(render_page, data): data for data in page_data_list}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    rendered_pages.append(result)
                except Exception as e:
                    logger.error(f"Error rendering page: {e}", exc_info=True)
        
        # Sort by page index
        rendered_pages.sort(key=lambda x: x[0])
        
        if timings is not None:
            if 'render_parallel_total' not in timings:
                timings['render_parallel_total'] = []
            timings['render_parallel_total'].append(time.time() - t0)
        
        # Merge pages into final PDF
        # For now, use simple approach: render sequentially but pages were prepared in parallel
        # TODO: Implement proper PDF merging in Rust
        t0 = time.time()
        for page_index, temp_path, page_width, page_height in rendered_pages:
            # For now, we'll need to copy content from temp PDFs
            # This is a simplified version - full implementation would merge PDFs properly
            pass
        
        # For now, fallback to sequential rendering with prepared pages
        # Full implementation would merge the temporary PDFs
        logger.warning("Parallel Rust rendering: full PDF merging not yet implemented, using sequential fallback")
        self._render_sequential_rust(unified_layout, timings=timings)

    def _render_sequential(self, unified_layout: UnifiedLayout, start_page_number: Optional[int] = None, timings: Optional[Dict[str, List[float]]] = None) -> None:
        """

        Render all pages sequentially (single process).

        Args:
        unified_layout: UnifiedLayout with pages to render
        start_page_number: Optional offset for page numbers (for parallel mode).
        If None, uses page numbers from page.number directly.
        timings: Optional dictionary for collecting operation times

        """
        import time
        
        t0 = time.time()
        # Use page size from first page if available, otherwise use self.page_size
        first_page_size = self.page_size
        if unified_layout.pages and hasattr(unified_layout.pages[0], 'size'):
            first_page_size = (unified_layout.pages[0].size.width, unified_layout.pages[0].size.height)
        c = canvas.Canvas(str(self.output_path), pagesize=first_page_size)
        if timings is not None:
            if 'render_create_canvas' not in timings:
                timings['render_create_canvas'] = []
            timings['render_create_canvas'].append(time.time() - t0)
        
        for page_index, page in enumerate(unified_layout.pages, start=1):
            # ALWAYS use page number from page.number (set in pipeline)
            # page.number contains proper page number from original layout
            # Set _current_page_number BEFORE calling _render_page(), so field codes in header/footer
            # can use proper page number
            if hasattr(page, 'number') and page.number:
                self._current_page_number = int(page.number)
            else:
                # Fallback: if page.number is not set, use page position in list
                self._current_page_number = page_index
            
            # Set page size for each page (may differ between pages)
            if hasattr(page, 'size'):
                c.setPageSize((page.size.width, page.size.height))
            
            t0 = time.time()
            self._render_page(c, page, timings=timings)
            if timings is not None:
                if 'render_page_total' not in timings:
                    timings['render_page_total'] = []
                timings['render_page_total'].append(time.time() - t0)
            
            t0 = time.time()
            c.showPage()
            if timings is not None:
                if 'render_show_page' not in timings:
                    timings['render_show_page'] = []
                timings['render_show_page'].append(time.time() - t0)
        
        t0 = time.time()
        c.save()
        if timings is not None:
            if 'render_save_canvas' not in timings:
                timings['render_save_canvas'] = []
            timings['render_save_canvas'].append(time.time() - t0)

    def _render_parallel(self, unified_layout: UnifiedLayout, timings: Optional[Dict[str, List[float]]] = None) -> None:
        """

        Render pages in multiple processes, then merge resulting PDFs.

        Args:
        unified_layout: UnifiedLayout with pages to render
        timings: Optional dictionary for collecting operation times

        """
        if not PYPDF2_AVAILABLE:
            raise RuntimeError("PyPDF2 jest wymagany do trybu równoległego renderowania.")

        try:
            ctx = multiprocessing.get_context("fork")
        except ValueError as exc:  # pragma: no cover - platform lacking fork
            raise RuntimeError("Tryb równoległy wymaga wsparcia kontekstu 'fork'.") from exc

        page_count = len(unified_layout.pages)
        if page_count == 0:
            raise ValueError("Brak stron do renderowania.")

        chunks = self._split_page_indices(page_count, self.parallelism)
        if len(chunks) <= 1:
            self._render_sequential(unified_layout, timings=timings)
            return

        temp_dir_ctx = None
        if self.merge_tmp_dir:
            tmp_dir = self.merge_tmp_dir
            tmp_dir.mkdir(parents=True, exist_ok=True)
            cleanup_tmp = False
        else:
            temp_dir_ctx = tempfile.TemporaryDirectory()
            tmp_dir = Path(temp_dir_ctx.name)
            cleanup_tmp = True

        try:
            tasks = []
            for idx, indices in enumerate(chunks):
                chunk_path = tmp_dir / f"chunk_{idx}.pdf"
                tasks.append((indices, str(chunk_path)))

            # Prepare shared state for child processes (fork).
            global _PARALLEL_LAYOUT, _PARALLEL_PAGE_SIZE, _PARALLEL_PACKAGE_READER, _PARALLEL_TOTAL_PAGES
            _PARALLEL_LAYOUT = unified_layout
            _PARALLEL_PAGE_SIZE = self.page_size
            _PARALLEL_PACKAGE_READER = self.package_reader
            _PARALLEL_TOTAL_PAGES = len(unified_layout.pages)

            with ctx.Pool(processes=min(self.parallelism, len(tasks))) as pool:
                pool.map(_parallel_render_chunk, tasks)

            # Scal fragmenty w finalny PDF
            merger = PdfMerger()
            chunk_files: List[Path] = []
            for _, chunk_path in tasks:
                chunk_file = Path(chunk_path)
                if not chunk_file.exists():
                    raise RuntimeError(f"Oczekiwany fragment PDF nie istnieje: {chunk_file}")
                merger.append(str(chunk_file))
                chunk_files.append(chunk_file)

            with self.output_path.open("wb") as final_fp:
                merger.write(final_fp)
            merger.close()

        finally:
            # Cleanup fragments
            if 'chunk_files' in locals():
                for chunk_file in chunk_files:
                    try:
                        chunk_file.unlink(missing_ok=True)
                    except Exception:
                        logger.debug(f"Nie udało się usunąć pliku fragmentu PDF: {chunk_file}")
            if cleanup_tmp and temp_dir_ctx is not None:
                temp_dir_ctx.cleanup()
            _PARALLEL_LAYOUT = None
            _PARALLEL_PAGE_SIZE = None
            _PARALLEL_PACKAGE_READER = None
            _PARALLEL_TOTAL_PAGES = 0

    @staticmethod
    def _split_page_indices(total_pages: int, workers: int) -> List[List[int]]:
        workers = max(1, min(workers, total_pages))
        base = total_pages // workers
        remainder = total_pages % workers
        result: List[List[int]] = []
        start = 0
        for worker in range(workers):
            extra = 1 if worker < remainder else 0
            stop = start + base + extra
            result.append(list(range(start, stop)))
            start = stop
        return [chunk for chunk in result if chunk]

    def _cleanup_temp_artifacts(self) -> None:
        for tmp_path in self._temp_files:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                logger.debug(f"Nie udało się usunąć pliku tymczasowego: {tmp_path}")
        self._temp_files.clear()
        self._converted_images.clear()
    
    # ----------------------------------------------------------------------
    # Renderowanie stron
    # ----------------------------------------------------------------------

    @staticmethod
    def _resolve_content(content: Any) -> tuple[Any, Optional[Any]]:
        """

        Unpacks BlockContent to raw dictionary or payload.
        Returns tuple (raw_content, payload).

        """
        if isinstance(content, BlockContent):
            raw = content.raw
            payload = content.payload
            if raw is not None:
                return raw, payload
            return payload, payload
        return content, None

    @staticmethod
    def _make_image_unique_key(image: Any) -> str:
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

    def _register_temp_file(self, data: bytes, suffix: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(data)
        tmp.flush()
        tmp.close()
        path = Path(tmp.name)
        self._temp_files.append(path)
        return path

    def _get_image_cache_key(self, path: Optional[str], rel_id: Optional[str], data: Optional[bytes]) -> Optional[str]:
        if path:
            return f"path::{path}"
        if rel_id:
            return f"rel::{rel_id}"
        if data:
            digest = hashlib.md5(data).hexdigest()
            return f"data::{digest}"
        return None

    def _extract_image_dimensions(self, image: Any) -> Tuple[Optional[float], Optional[float]]:
        def _to_float(value: Any) -> Optional[float]:
            if value in (None, "", False):
                return None
            if isinstance(value, (int, float)):
                return float(value)
            try:
                return float(str(value))
            except (TypeError, ValueError):
                return None

        width = height = None
        if isinstance(image, dict):
            width = (
                _to_float(image.get("width"))
                or _to_float(image.get("cx"))
                or _to_float(image.get("width_pt"))
            )
            height = (
                _to_float(image.get("height"))
                or _to_float(image.get("cy"))
                or _to_float(image.get("height_pt"))
            )
        else:
            width = _to_float(getattr(image, "width", None))
            height = _to_float(getattr(image, "height", None))

        if width and width > 0:
            if width > 10000:
                from ..geometry import emu_to_points
                width = emu_to_points(width)
        else:
            width = None

        if height and height > 0:
            if height > 10000:
                from ..geometry import emu_to_points
                height = emu_to_points(height)
        else:
            height = None

        return width, height

    @classmethod
    def _points_to_pixels(cls, value: Optional[float], max_px: int = 4096) -> Optional[int]:
        if value is None:
            return None
        try:
            pixels = int(round((float(value) / 72.0) * cls._IMAGE_TARGET_DPI))
        except (TypeError, ValueError):
            return None
        if pixels <= 0:
            pixels = 1
        return min(pixels, max_px)

    def _ensure_bitmap_path(
        self,
        image: Any,
        initial_path: Optional[str],
    ) -> Optional[str]:
        """

        Ensures image has path to raster file (PNG/JPG). 
        If image is in EMF/WMF format, converts to PNG.

        """
        rel_id = None
        relationship_source = None
        part_path = None

        if isinstance(image, dict):
            rel_id = image.get("relationship_id") or image.get("rel_id")
            relationship_source = image.get("relationship_source") or image.get("part_path")
            part_path = image.get("part_path")
        else:
            rel_id = getattr(image, "relationship_id", None) or getattr(image, "rel_id", None)
            relationship_source = getattr(image, "relationship_source", None) or getattr(image, "part_path", None)
            part_path = getattr(image, "part_path", None)

        candidate_path = initial_path
        image_bytes: Optional[bytes] = None

        def load_image_bytes() -> Optional[bytes]:
            return self._load_image_binary(rel_id, candidate_path, relationship_source, part_path)

        if candidate_path and Path(candidate_path).exists():
            suffix = Path(candidate_path).suffix.lower()
            if suffix in {".wmf", ".emf"}:
                try:
                    image_bytes = Path(candidate_path).read_bytes()
                except OSError:
                    image_bytes = load_image_bytes()
        else:
            image_bytes = load_image_bytes()
            if image_bytes:
                _, ext = os.path.splitext(candidate_path or "")
                ext = ext or ".img"
                temp_path = self._register_temp_file(image_bytes, ext)
                cache_key = self._get_image_cache_key(candidate_path, rel_id, image_bytes)
                if cache_key:
                    self._converted_images[cache_key] = temp_path
                candidate_path = str(temp_path)

        if candidate_path:
            suffix = Path(candidate_path).suffix.lower()
        else:
            suffix = None

        if suffix in {".wmf", ".emf"}:
            # First check preconverted images cache (from pipeline)
            if self.image_cache and rel_id:
                cached_path = self.image_cache.get(rel_id, wait=True)
                if cached_path and cached_path.exists():
                    logger.debug(f"Using pre-converted image from cache: {rel_id} -> {cached_path}")
                    return str(cached_path)
                elif cached_path is None:
                    # Cache miss - image was not preconverted or conversion failed
                    logger.debug(f"Cache miss for {rel_id}, will convert synchronously")
            
            # Fallback: convert now (if not in cache)
            if image_bytes is None:
                image_bytes = load_image_bytes()
            if image_bytes:
                cache_key = self._get_image_cache_key(candidate_path, rel_id, image_bytes)
                if cache_key and cache_key in self._converted_images:
                    cached = self._converted_images[cache_key]
                    logger.debug(f"Using in-memory cached image: {cache_key}")
                    return str(cached)

                width_pt, height_pt = self._extract_image_dimensions(image)
                width_px = self._points_to_pixels(width_pt)
                height_px = self._points_to_pixels(height_pt)

                # Pomiar czasu konwersji WMF/EMF
                import time
                t0 = time.time()
                logger.debug(f"Converting WMF/EMF synchronously: {rel_id or candidate_path}, size={len(image_bytes)} bytes")
                png_bytes = self.media_converter.convert_emf_to_png(
                    image_bytes,
                    width=width_px,
                    height=height_px,
                )
                conversion_time = time.time() - t0
                logger.debug(f"WMF/EMF conversion completed in {conversion_time:.3f}s for {rel_id or candidate_path}")
                # Save conversion time if timings are available (via instance attribute)
                if hasattr(self, '_current_timings') and self._current_timings is not None:
                    if 'image_conversion_wmf_emf' not in self._current_timings:
                        self._current_timings['image_conversion_wmf_emf'] = []
                    self._current_timings['image_conversion_wmf_emf'].append(conversion_time)
                
                if png_bytes:
                    temp_png = self._register_temp_file(png_bytes, ".png")
                    if cache_key:
                        self._converted_images[cache_key] = temp_png
                    return str(temp_png)

        return candidate_path

    @staticmethod
    def _paragraph_layout_height(payload: Optional[ParagraphLayout]) -> float:
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
        payload = None
        if isinstance(content_item, dict):
            payload = content_item.get("layout_payload") or content_item.get("_layout_payload")
        elif hasattr(content_item, "layout_payload"):
            payload = getattr(content_item, "layout_payload")
        elif hasattr(content_item, "_layout_payload"):
            payload = getattr(content_item, "_layout_payload")
        return payload if isinstance(payload, ParagraphLayout) else None

    def _extract_cell_content(self, cell: Any) -> List[Any]:
        items: List[Any] = []
        seen: set[int] = set()

        def _track(value: Any) -> None:
            if value is None:
                return
            try:
                key = id(value)
            except Exception:
                key = None
            if key is not None and key in seen:
                return
            if key is not None:
                seen.add(key)
            items.append(value)

        def _extend(value: Any) -> None:
            if isinstance(value, list):
                for element in value:
                    _track(element)
            else:
                _track(value)

        if isinstance(cell, dict):
            _extend(cell.get("content"))
            _extend(cell.get("paragraphs"))
            _extend(cell.get("elements"))
            _extend(cell.get("children"))
        if hasattr(cell, "content"):
            _extend(getattr(cell, "content"))
        if hasattr(cell, "paragraphs"):
            _extend(getattr(cell, "paragraphs"))
        if hasattr(cell, "elements"):
            _extend(getattr(cell, "elements"))
        if hasattr(cell, "children"):
            _extend(getattr(cell, "children"))

        return [item for item in items if item]

    def _extract_style(self, item: Any) -> Dict[str, Any]:
        style: Dict[str, Any] = {}
        if isinstance(item, dict):
            raw_style = item.get("style") or {}
            style = raw_style if isinstance(raw_style, dict) else {}
        elif hasattr(item, "style"):
            raw_style = getattr(item, "style")
            style = raw_style if isinstance(raw_style, dict) else {}
        return style

    def _render_cell_paragraphs(
        self,
        c: canvas.Canvas,
        paragraphs: List[Any],
        cell_rect: Rect,
        cell_margins: Dict[str, float],
        header_footer_context: Optional[str] = None,
        style_override: Optional[Dict[str, Any]] = None,
        vertical_align: Optional[str] = None,
    ) -> bool:
        payload_entries: List[tuple[Any, ParagraphLayout, bool]] = []
        any_textual_content = False
        for item in paragraphs:
            payload = self._extract_paragraph_payload(item)
            if payload:
                has_textual = False
                for line in getattr(payload, "lines", []) or []:
                    for inline in getattr(line, "items", []) or []:
                        kind = getattr(inline, "kind", None)
                        if kind == "inline_image":
                            continue
                        if kind == "inline_textbox":
                            has_textual = True
                            break
                        data = inline.data if hasattr(inline, "data") else None
                        text_candidate = ""
                        if isinstance(data, dict):
                            text_candidate = (
                                data.get("text")
                                or data.get("display")
                                or data.get("value")
                                or ""
                            )
                        elif hasattr(data, "text"):
                            text_candidate = getattr(data, "text", "") or ""
                        if (text_candidate or kind not in ("inline_image", None)):
                            has_textual = True
                            break
                    if has_textual:
                        break
                payload_entries.append((item, payload, has_textual))
                if has_textual:
                    any_textual_content = True

        if not payload_entries:
            return False

        if not any_textual_content:
            return False

        margin_top = float(cell_margins.get("top") or 0.0)
        margin_bottom = float(cell_margins.get("bottom") or 0.0)
        margin_left = float(cell_margins.get("left") or 0.0)
        margin_right = float(cell_margins.get("right") or 0.0)

        inner_width = max(cell_rect.width - margin_left - margin_right, 0.0)
        inner_height = max(cell_rect.height - margin_top - margin_bottom, 0.0)
        if inner_width <= 0.0 or inner_height <= 0.0:
            return False
        bottom_limit = cell_rect.y + margin_bottom

        plan: List[tuple[Any, ParagraphLayout, float]] = []
        remaining_height = inner_height
        for item, payload, _has_text in payload_entries:
            if remaining_height <= 0.0:
                break
            para_height = self._paragraph_layout_height(payload)
            if para_height <= 0.0:
                para_height = remaining_height
            para_height = min(para_height, remaining_height)
            if para_height <= 0.0:
                continue
            plan.append((item, payload, para_height))
            remaining_height -= para_height

        if not plan:
            return False

        used_height = sum(height for _, _, height in plan)
        vertical_token = (vertical_align or "").strip().lower()
        offset = 0.0
        if vertical_token in {"center", "middle"}:
            offset = max((inner_height - used_height) / 2.0, 0.0)
        elif vertical_token in {"bottom", "end"}:
            offset = max(inner_height - used_height, 0.0)

        current_top = cell_rect.y + cell_rect.height - margin_top - offset
        any_rendered = False

        for item, payload, para_height in plan:
            available_height = max(current_top - bottom_limit, 0.0)
            if available_height <= 0.0:
                break

            para_height = min(para_height, available_height)
            if para_height <= 0.0:
                continue

            para_rect = Rect(
                cell_rect.x + margin_left,
                current_top - para_height,
                inner_width,
                para_height,
            )
            style = self._extract_style(item)
            if style_override:
                style = dict(style) if isinstance(style, dict) else {}
                style.update(style_override)
            marker = item.get("marker") if isinstance(item, dict) else None
            # For paragraphs in tables check pagination_segment_index
            pagination_segment_index = item.get("_pagination_segment_index") if isinstance(item, dict) else None

            self._draw_paragraph_from_layout(
                c,
                para_rect,
                payload,
                style,
                marker,
                header_footer_context,
                pagination_segment_index=pagination_segment_index,
            )
            current_top = para_rect.y
            any_rendered = True

        return any_rendered

    def _resolve_image_path(self, image: Any) -> Optional[str]:
        """

        Extracts image path from object/dict and ensures WMF/EMF to PNG conversion.

        """
        if isinstance(image, dict):
            initial_path = image.get("path") or image.get("src") or image.get("image_path")
        else:
            initial_path = getattr(image, "path", None) or getattr(image, "image_path", None)

        resolved = self._ensure_bitmap_path(image, initial_path)
        if resolved and not Path(resolved).exists():
            # If path doesn't exist, try to create temp file from data
            rel_id = None
            relationship_source = None
            part_path = None
            if isinstance(image, dict):
                rel_id = image.get("relationship_id") or image.get("rel_id")
                relationship_source = image.get("relationship_source") or image.get("part_path")
                part_path = image.get("part_path")
            else:
                rel_id = getattr(image, "relationship_id", None) or getattr(image, "rel_id", None)
                relationship_source = getattr(image, "relationship_source", None) or getattr(image, "part_path", None)
                part_path = getattr(image, "part_path", None)
            data = self._load_image_binary(rel_id, resolved, relationship_source, part_path)
            if data:
                suffix = Path(resolved).suffix if resolved else ".img"
                temp_path = self._register_temp_file(data, suffix or ".img")
                resolved = str(temp_path)
        return resolved

    def _load_image_binary(
        self,
        rel_id: Optional[str],
        image_path: Optional[str],
        relationship_source: Optional[str] = None,
        part_path: Optional[str] = None,
    ) -> Optional[bytes]:
        """

        Loads image data from PackageReader or filesystem.

        """
        # Try to read through DOCX relations
        if self.package_reader and rel_id:
            try:
                relationship = None
                if relationship_source:
                    rels_dict = self.package_reader.get_relationships(relationship_source)
                    if isinstance(rels_dict, dict):
                        relationship = rels_dict.get(rel_id)
                if not relationship and part_path:
                    rels_candidate = f"word/_rels/{Path(part_path).name}.rels"
                    rels_dict = self.package_reader.get_relationships(rels_candidate)
                    if isinstance(rels_dict, dict):
                        relationship = rels_dict.get(rel_id)
                if not relationship:
                    rels_dict = self.package_reader.get_relationships("document")
                    if isinstance(rels_dict, dict):
                        relationship = rels_dict.get(rel_id)
                if relationship:
                    target_path = relationship.get("target") or relationship.get("Target")
                    if target_path:
                        if part_path:
                            part_dir = Path(part_path).parent
                            resolved = str(part_dir / target_path)
                            if resolved.startswith("word/word/"):
                                resolved = resolved.replace("word/word/", "word/", 1)
                            target_path = resolved
                        elif not target_path.startswith("word/"):
                            target_path = f"word/{target_path}"
                        binary = self.package_reader.get_binary_content(target_path)
                        if binary:
                            return binary
            except Exception as exc:
                logger.debug(f"Nie udało się załadować obrazu z rel_id {rel_id}: {exc}")

        # Try direct path from package
        if self.package_reader and image_path:
            try:
                binary = self.package_reader.get_binary_content(image_path)
                if binary:
                    return binary
                if not image_path.startswith("word/"):
                    binary = self.package_reader.get_binary_content(f"word/{image_path}")
                    if binary:
                        return binary
            except Exception as exc:
                logger.debug(f"Nie udało się załadować obrazu {image_path} z pakietu: {exc}")

        # Try filesystem
        if image_path:
            try:
                path_obj = Path(image_path)
                if path_obj.exists() and path_obj.is_file():
                    return path_obj.read_bytes()
            except Exception as exc:
                logger.debug(f"Nie udało się odczytać obrazu z dysku {image_path}: {exc}")

        return None
    
    def _render_page(self, c: canvas.Canvas, page: Any, timings: Optional[Dict[str, List[float]]] = None) -> None:
        """

        Renders single page.

        Args:
        c: ReportLab Canvas
        page: LayoutPage to render
        timings: Optional dictionary for collecting operation times

        """
        import time
        # Pass timings to _ensure_bitmap_path via instance attribute
        self._current_timings = timings
        
        if hasattr(page, "number"):
            try:
                self._current_page_number = int(page.number)
            except (TypeError, ValueError):
                self._current_page_number = 1
        else:
            self._current_page_number = 1
        # Pobierz rozmiar strony
        if hasattr(page, 'size'):
            width = page.size.width
            height = page.size.height
        else:
            width, height = self.page_size
        
        # Opcjonalna ramka strony (debug)
        # c.setStrokeColor(Color(0.8, 0.8, 0.8))
        # c.setLineWidth(0.5)
        # c.rect(0, 0, width, height)
        
        # Render blocks in order
        # First render headers and footers, then the rest
        # Check if block is in header/footer based on block_type and content
        header_blocks = []
        footer_blocks = []
        body_blocks = []
        watermark_blocks = []  # Watermarks are rendered first
        
        # Check if page should skip headers and footers
        skip_headers_footers = getattr(page, 'skip_headers_footers', False)
        
        # Profile block sorting and content resolution
        t0_sort = time.time()
        t0_resolve_content = 0.0
        resolve_content_count = 0
        for block in page.blocks:
            # Check if block is in header/footer based on type or context
            t0_resolve = time.time()
            content_value, _ = self._resolve_content(block.content)
            t0_resolve_content += time.time() - t0_resolve
            resolve_content_count += 1
            content = content_value if isinstance(content_value, dict) else {}
            header_footer_context = content.get("header_footer_context")
            
            # Wykryj watermarks: textboxy z pozycjonowaniem absolutnym w headerach
            is_watermark = False
            # Check if block is marked as watermark
            if content.get("is_watermark") or block.block_type == "textbox" and header_footer_context == "header":
                # Check if textbox has absolute positioning (anchor)
                anchor_info = content.get("anchor_info") or {}
                anchor_type = anchor_info.get("anchor_type", "")
                position = anchor_info.get("position", {})
                
                # If anchor (absolute positioning) or marked as watermark, treat as watermark
                if content.get("is_watermark") or anchor_type == "anchor" or position:
                    is_watermark = True
            
            if is_watermark:
                watermark_blocks.append(block)
                continue
            
            # If page should skip headers and footers, don't add them to lists
            if skip_headers_footers:
                if block.block_type == "header" or header_footer_context == "header":
                    continue  # Skip headers
                elif block.block_type == "footer" or header_footer_context == "footer":
                    continue  # Skip footers
            
            if block.block_type == "header" or header_footer_context == "header":
                header_blocks.append(block)
            elif block.block_type == "footer" or header_footer_context == "footer":
                footer_blocks.append(block)
            elif block.block_type == "footnotes":
                # Footnotes are rendered after footer, but before page end
                footer_blocks.append(block)  # Dodaj do footer_blocks, ale renderuj przed footer
            else:
                body_blocks.append(block)
        
        sort_time = time.time() - t0_sort
        if timings is not None:
            if 'render_sort_blocks' not in timings:
                timings['render_sort_blocks'] = []
            timings['render_sort_blocks'].append(sort_time)
            if 'render_resolve_content' not in timings:
                timings['render_resolve_content'] = []
            timings['render_resolve_content'].append(t0_resolve_content)
            if 'render_resolve_content_count' not in timings:
                timings['render_resolve_content_count'] = []
            timings['render_resolve_content_count'].append(resolve_content_count)
        
        # Renderuj watermarks jako pierwsze (na tle, przed wszystkimi innymi elementami)
        t0 = time.time()
        for block in watermark_blocks:
            try:
                self._draw_watermark(c, block, width, height)
            except Exception as e:
                logger.warning(f"Błąd podczas renderowania watermark: {e}", exc_info=True)
        if timings is not None:
            if 'render_watermarks' not in timings:
                timings['render_watermarks'] = []
            timings['render_watermarks'].append(time.time() - t0)
        
        # Render in order: headers, body, footnotes, footers
        # First extract footnotes from footer_blocks
        footnote_blocks = [b for b in footer_blocks if b.block_type == "footnotes"]
        actual_footer_blocks = [b for b in footer_blocks if b.block_type != "footnotes"]
        
        t0 = time.time()
        header_table_time = 0.0
        header_paragraph_time = 0.0
        header_image_time = 0.0
        header_textbox_time = 0.0
        header_decorator_time = 0.0
        header_other_time = 0.0
        
        for block in header_blocks:
            try:
                # Check actual block type in content
                content_value, _ = self._resolve_content(block.content)
                content = content_value if isinstance(content_value, dict) else {}
                block_type = content.get("type") or block.block_type
                
                block_t0 = time.time()
                if block_type == "table":
                    self._draw_table(c, block)
                    header_table_time += time.time() - block_t0
                elif block_type == "paragraph":
                    self._draw_paragraph(c, block)
                    header_paragraph_time += time.time() - block_t0
                elif block_type == "image":
                    self._draw_image(c, block, timings)
                    header_image_time += time.time() - block_t0
                elif block_type == "textbox":
                    self._draw_textbox(c, block)
                    header_textbox_time += time.time() - block_t0
                elif block_type == "decorator":
                    self._draw_decorator(c, block)
                    header_decorator_time += time.time() - block_t0
                else:
                    self._draw_header(c, block)
                    header_other_time += time.time() - block_t0
            except Exception as e:
                logger.warning(f"Błąd podczas renderowania header: {e}")
                self._draw_error_placeholder(c, block, str(e))
        if timings is not None:
            if 'render_headers' not in timings:
                timings['render_headers'] = []
            timings['render_headers'].append(time.time() - t0)
            if 'render_headers_table' not in timings:
                timings['render_headers_table'] = []
            timings['render_headers_table'].append(header_table_time)
            if 'render_headers_paragraph' not in timings:
                timings['render_headers_paragraph'] = []
            timings['render_headers_paragraph'].append(header_paragraph_time)
            if 'render_headers_image' not in timings:
                timings['render_headers_image'] = []
            timings['render_headers_image'].append(header_image_time)
            if 'render_headers_textbox' not in timings:
                timings['render_headers_textbox'] = []
            timings['render_headers_textbox'].append(header_textbox_time)
            if 'render_headers_decorator' not in timings:
                timings['render_headers_decorator'] = []
            timings['render_headers_decorator'].append(header_decorator_time)
            if 'render_headers_other' not in timings:
                timings['render_headers_other'] = []
            timings['render_headers_other'].append(header_other_time)
        
        # Extract endnotes from body_blocks (rendered as separate blocks)
        endnote_blocks = [b for b in body_blocks if b.block_type == "endnotes"]
        actual_body_blocks = [b for b in body_blocks if b.block_type != "endnotes"]
        
        t0 = time.time()
        paragraph_time = 0.0
        table_time = 0.0
        image_time = 0.0
        textbox_time = 0.0
        decorator_time = 0.0
        for block in actual_body_blocks:
            try:
                block_t0 = time.time()
                match block.block_type:
                    case "paragraph":
                        self._draw_paragraph(c, block)
                        paragraph_time += time.time() - block_t0
                    case "table":
                        self._draw_table(c, block)
                        table_time += time.time() - block_t0
                    case "image":
                        self._draw_image(c, block, timings)
                        image_time += time.time() - block_t0
                    case "textbox":
                        self._draw_textbox(c, block)
                        textbox_time += time.time() - block_t0
                    case "decorator":
                        self._draw_decorator(c, block)
                        decorator_time += time.time() - block_t0
                    case _:
                        self._draw_generic(c, block)
            except Exception as e:
                logger.warning(f"Błąd podczas renderowania bloku {block.block_type}: {e}")
                # Render simple placeholder in case of error
                self._draw_error_placeholder(c, block, str(e))
        if timings is not None:
            if 'render_body_total' not in timings:
                timings['render_body_total'] = []
            timings['render_body_total'].append(time.time() - t0)
            if 'render_paragraphs' not in timings:
                timings['render_paragraphs'] = []
            timings['render_paragraphs'].append(paragraph_time)
            if 'render_tables' not in timings:
                timings['render_tables'] = []
            timings['render_tables'].append(table_time)
            if 'render_images' not in timings:
                timings['render_images'] = []
            timings['render_images'].append(image_time)
            if 'render_textboxes' not in timings:
                timings['render_textboxes'] = []
            timings['render_textboxes'].append(textbox_time)
            if 'render_decorators' not in timings:
                timings['render_decorators'] = []
            timings['render_decorators'].append(decorator_time)
        
        # Renderuj endnotes po body blocks, ale przed footnotes
        t0 = time.time()
        for block in endnote_blocks:
            try:
                self._draw_endnotes(c, block)
            except Exception as e:
                logger.warning(f"Błąd podczas renderowania endnotes: {e}")
                self._draw_error_placeholder(c, block, str(e))
        if timings is not None:
            if 'render_endnotes' not in timings:
                timings['render_endnotes'] = []
            timings['render_endnotes'].append(time.time() - t0)
        
        # Renderuj footnotes przed footer
        t0 = time.time()
        for block in footnote_blocks:
            try:
                self._draw_footnotes(c, block)
            except Exception as e:
                logger.warning(f"Błąd podczas renderowania footnotes: {e}")
                self._draw_error_placeholder(c, block, str(e))
        if timings is not None:
            if 'render_footnotes' not in timings:
                timings['render_footnotes'] = []
            timings['render_footnotes'].append(time.time() - t0)
        
        t0 = time.time()
        for block in actual_footer_blocks:
            try:
                # Check actual block type in content
                content_value, _ = self._resolve_content(block.content)
                content = content_value if isinstance(content_value, dict) else {}
                block_type = content.get("type") or block.block_type
                
                if block_type == "table":
                    self._draw_table(c, block)
                elif block_type == "paragraph":
                    self._draw_paragraph(c, block)
                elif block_type == "image":
                    self._draw_image(c, block, timings)
                elif block_type == "textbox":
                    self._draw_textbox(c, block)
                elif block_type == "decorator":
                    self._draw_decorator(c, block)
                else:
                    self._draw_footer(c, block)
            except Exception as e:
                logger.warning(f"Błąd podczas renderowania footer: {e}")
                self._draw_error_placeholder(c, block, str(e))
        if timings is not None:
            if 'render_footers' not in timings:
                timings['render_footers'] = []
            timings['render_footers'].append(time.time() - t0)
        
        # Clear _current_timings
        self._current_timings = None
    
    # ----------------------------------------------------------------------
    # Block rendering
    # ----------------------------------------------------------------------
    
    def _draw_paragraph(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """
        Renderuje paragraf tekstu.
        
        Args:
            c: ReportLab Canvas
            block: LayoutBlock typu "paragraph"
        """
        style = block.style or {}
        if not isinstance(style, dict):
            style = {}
        rect = block.frame

        # Get text and payload from content (before drawing background to know full extent)
        content_value, payload_candidate = self._resolve_content(block.content)
        marker = content_value.get("marker") if isinstance(content_value, dict) else None
        header_footer_context = content_value.get("header_footer_context") if isinstance(content_value, dict) else None
        # Check if this is first paragraph segment (for numbering markers)
        pagination_segment_index = content_value.get("_pagination_segment_index") if isinstance(content_value, dict) else None

        paragraph_payload: Optional[ParagraphLayout] = None
        if isinstance(block.content, BlockContent) and isinstance(block.content.payload, ParagraphLayout):
            paragraph_payload = block.content.payload
        elif isinstance(payload_candidate, ParagraphLayout):
            paragraph_payload = payload_candidate
        elif isinstance(content_value, dict):
            candidate = content_value.get("layout_payload") or content_value.get("_layout_payload")
            if isinstance(candidate, ParagraphLayout):
                paragraph_payload = candidate

        paint_rect = rect
        if paragraph_payload and isinstance(paragraph_payload.metadata, dict):
            frame_info = paragraph_payload.metadata.get("frame_original")
            if isinstance(frame_info, dict):
                try:
                    frame_x = float(frame_info.get("x", rect.x))
                    frame_width = float(frame_info.get("width", rect.width))
                    frame_height = float(frame_info.get("height", rect.height))
                    paint_rect = Rect(frame_x, rect.y, frame_width, frame_height)
                    # Adjust height if available in metadata
                    if frame_height:
                        paint_rect.height = frame_height
                except (TypeError, ValueError):
                    paint_rect = rect

        group_draw = style.get("_border_group_draw", True)
        border_rect = paint_rect

        # Renderuj shadow, background i border przed tekstem
        try:
            borders_override = style.get("_borders_to_draw")
            if group_draw:
                draw_shadow(c, paint_rect, style)
                draw_background(c, paint_rect, style)
                if borders_override:
                    draw_border(c, border_rect, {"borders": borders_override})
                else:
                    draw_border(c, border_rect, style)
            else:
                if borders_override:
                    draw_border(c, border_rect, {"borders": borders_override})
        except Exception as e:
            logger.debug(f"Błąd renderowania background/border: {e}")

        between_spec = style.get("_border_between_top")
        if isinstance(between_spec, dict):
            try:
                boundary_y = rect.y + rect.height
                between_rect = Rect(border_rect.x, boundary_y, border_rect.width, 0.0)
                draw_border(c, between_rect, {"borders": {"top": between_spec}})
            except Exception as exc:
                logger.debug(f"Błąd renderowania linii between: {exc}")

        if paragraph_payload:
            self._draw_paragraph_from_layout(
                c,
                rect,
                paragraph_payload,
                style,
                marker,
                header_footer_context,
                pagination_segment_index=pagination_segment_index,
            )
            return

        # Fallback: renderowanie bez payloadu
        text = ""
        images = []
        
        if isinstance(content_value, dict):
            text = content_value.get("text", "")
            images = content_value.get("images", [])
        elif isinstance(content_value, str):
            text = content_value
        elif content_value is None:
            text = ""
        else:
            text = str(content_value) if isinstance(content_value, (int, float)) else ""
        
        # Render images if present
        if images:
            for img in images:
                try:
                    # Get image path
                    img_path = self._resolve_image_path(img)
                    if not img_path:
                        logger.debug(f"Image in paragraph could not be resolved: {img}")
                        continue
                    
                    # Pobierz wymiary obrazu
                    img_width = None
                    img_height = None
                    if isinstance(img, dict):
                        img_width = img.get("width")
                        img_height = img.get("height")
                    elif hasattr(img, 'width'):
                        img_width = img.width
                    elif hasattr(img, 'height'):
                        img_height = img.height
                    
                    # Calculate available area for image
                    available_width = rect.width
                    available_height = rect.height
                    
                    # If no dimensions, use available area
                    if img_width is None or img_height is None:
                        render_width = available_width
                        render_height = available_height
                    else:
                        # Convert from EMU to points if needed
                        from ..geometry import emu_to_points
                        if img_width > 10000:  # Prawdopodobnie EMU
                            img_width = emu_to_points(img_width)
                        if img_height > 10000:  # Prawdopodobnie EMU
                            img_height = emu_to_points(img_height)
                        
                        # Scale image to available area preserving aspect ratio
                        scale_w = available_width / img_width if img_width > 0 else 1.0
                        scale_h = available_height / img_height if img_height > 0 else 1.0
                        scale = min(scale_w, scale_h, 1.0)  # Don't enlarge
                        
                        render_width = img_width * scale
                        render_height = img_height * scale
                    
                    # Image position (centered in paragraph)
                    img_x = rect.x + (available_width - render_width) / 2
                    img_y = rect.y + (available_height - render_height) / 2
                    
                    # Renderuj obraz
                    c.drawImage(
                        img_path,
                        img_x,
                        img_y,
                        width=render_width,
                        height=render_height,
                        preserveAspectRatio=True,
                        mask="auto"
                    )
                except Exception as e:
                    logger.warning(f"Błąd renderowania obrazu w paragrafie: {e}")
        
        if not text:
            return
        
        # Pobierz style
        font_name = style.get("font_name", "Helvetica")
        font_size = float(style.get("font_size", 11))
        alignment = style.get("alignment") or style.get("text_align") or style.get("align", "left")
        color = style.get("color", "#000000")
        
        # Ustaw font i kolor
        try:
            c.setFillColor(self._hex_to_rgb(color))
            c.setFont(font_name, font_size)
        except Exception as e:
            logger.warning(f"Błąd ustawiania fontu/koloru: {e}, używam domyślnych")
            c.setFillColor(black)
            c.setFont("Helvetica", font_size)
        
        # Text layout using TextMetricsEngine
        try:
            # Ensure style is dict
            if not isinstance(style, dict):
                style = {}
            layout: TextLayout = self.metrics.layout_text(text, style, rect.width)
        except Exception as e:
            logger.warning(f"Błąd layoutowania tekstu: {e}, używam prostego podziału")
            # Fallback: simple line splitting
            words = text.split()
            lines = []
            current_line = []
            current_width = 0
            space_width = c.stringWidth(" ", font_name, font_size)
            
            for word in words:
                word_width = c.stringWidth(word, font_name, font_size)
                if current_width + word_width + (space_width if current_line else 0) <= rect.width:
                    if current_line:
                        current_line.append(" ")
                        current_width += space_width
                    current_line.append(word)
                    current_width += word_width
                else:
                    if current_line:
                        lines.append("".join(current_line))
                    current_line = [word]
                    current_width = word_width
            
            if current_line:
                lines.append("".join(current_line))
            
            layout = TextLayout(
                width=rect.width,
                height=len(lines) * font_size * 1.2,
                line_count=len(lines),
                lines=lines
            )
        
        # Renderuj linie
        line_height = font_size * float(style.get("line_spacing_factor", 1.2))
        y_cursor = rect.y + rect.height
        
        for line in layout.lines:
            if not line.strip():
                y_cursor -= line_height
                continue
            
            # Calculate text width
            try:
                text_width = self.metrics.measure_text(line, style)["width"]
            except Exception:
                text_width = c.stringWidth(line, font_name, font_size)
            
            # Calculate X position using TextAlignmentEngine
            x = self.aligner.calculate_text_position(rect, text_width, style)
            
            # Renderuj tekst
            c.drawString(x, y_cursor, line)
            y_cursor -= line_height

    def _draw_decorator(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """

        Renders decorator block (background/border/shadow) common for paragraph group.

        """
        style = block.style or {}
        if not isinstance(style, dict):
            style = {}
        rect = block.frame
        padding_x = 2.0
        padded_rect = Rect(
            rect.x - padding_x,
            rect.y,
            rect.width + 2 * padding_x,
            rect.height,
        )
        content_value, _ = self._resolve_content(block.content)
        between_lines = []
        if isinstance(content_value, dict):
            between_lines = content_value.get("between_lines") or []
        elif isinstance(block.content, dict):
            between_lines = block.content.get("between_lines") or []
        try:
            draw_shadow(c, padded_rect, style)
            draw_background(c, padded_rect, style)
            draw_border(c, padded_rect, style)
            if between_lines:
                for entry in between_lines:
                    if not isinstance(entry, dict):
                        continue
                    spec = entry.get("spec")
                    y_line = entry.get("y")
                    if not isinstance(spec, dict):
                        continue
                    try:
                        y_value = float(y_line)
                    except (TypeError, ValueError):
                        continue
                    line_rect = Rect(padded_rect.x, y_value, padded_rect.width, 0.0)
                    draw_border(c, line_rect, {"borders": {"top": spec}})
        except Exception as exc:
            logger.debug(f"Błąd renderowania dekoratora: {exc}")

    def _draw_paragraph_from_layout(
        self,
        c: canvas.Canvas,
        rect: Rect,
        payload: ParagraphLayout,
        base_style: Dict[str, Any],
        marker: Optional[Dict[str, Any]],
        header_footer_context: Optional[str] = None,
        pagination_segment_index: Optional[int] = None,
    ) -> None:
        """

        Renders paragraph based on ready ParagraphLayout (without re-layouting).

        """
        import time
        t0_func = time.perf_counter()
        t0_setup = time.perf_counter()
        
        padding_top, padding_right, padding_bottom, padding_left = (
            payload.style.padding if payload.style else (0.0, 0.0, 0.0, 0.0)
        )

        default_font_name = (
            base_style.get("font_name")
            or payload.metadata.get("font_name")
            or payload.metadata.get("font_ascii")
            or "Helvetica"
        )
        default_font_size_value = (
            base_style.get("font_size")
            or payload.metadata.get("font_size")
            or payload.metadata.get("raw_style", {}).get("font_size")
            or 11.0
        )
        # Use normalize_font_size to convert half-points to points (same as in paragraph text)
        try:
            from ..assembler.utils import normalize_font_size
            default_font_size = normalize_font_size(default_font_size_value) or 11.0
        except (TypeError, ValueError, ImportError):
            try:
                default_font_size = float(default_font_size_value)
            except (TypeError, ValueError):
                default_font_size = 11.0
        text_left = rect.x + padding_left
        text_top = rect.top - padding_top - (0.75 * default_font_size )

        default_color_value = (
            base_style.get("color")
            or payload.metadata.get("font_color")
            or payload.metadata.get("color")
            or "#000000"
        )
        default_color = self._color_to_reportlab(default_color_value, "#000000")
        
        setup_time = time.perf_counter() - t0_setup

        first_line_baseline = None
        if payload.lines:
            first_line_baseline = text_top - payload.lines[0].baseline_y

        # Draw list marker (if exists) - only for first paragraph segment
        # Marker should be rendered only when:
        # - pagination_segment_index jest None (nie jest segmentowany paragraf) LUB
        # - pagination_segment_index equals 0 (first segment)
        should_render_marker = marker and (pagination_segment_index is None or pagination_segment_index == 0)
        if should_render_marker:
            marker_text = (
                marker.get("text")
                or marker.get("label")
                or marker.get("display")
                or marker.get("bullet")
                or ""
            )
            marker_suffix_raw = marker.get("suffix", "")
            marker_suffix = ""
            if isinstance(marker_suffix_raw, str):
                normalized_suffix = marker_suffix_raw.strip().lower()
                if normalized_suffix in {"tab", "tabulation"}:
                    marker_suffix = ""
                elif normalized_suffix in {"space"}:
                    marker_suffix = " "
                elif normalized_suffix in {"none", "-"}:
                    marker_suffix = ""
                else:
                    marker_suffix = marker_suffix_raw
            elif marker_suffix_raw:
                marker_suffix = str(marker_suffix_raw)
            if marker_suffix and marker_suffix not in marker_text:
                marker_text += marker_suffix

            marker_x = marker.get("x")
            if marker_x is None:
                marker_x = text_left - 10.0
            marker_baseline = first_line_baseline if first_line_baseline is not None else (rect.top - padding_top - 0.75 * default_font_size)
            baseline_shift = marker.get("baseline_adjust") or marker.get("baseline_shift")
            if baseline_shift is not None:
                try:
                    marker_baseline += float(baseline_shift)
                except (TypeError, ValueError):
                    pass

            marker_font_name = (
                marker.get("font_name")
                or marker.get("font_ascii")
                or default_font_name
            )
            # Force using font_size from first text run in paragraph for marker
            # Pobierz font_size z pierwszego runu tekstu w pierwszej linii
            marker_font_size = default_font_size
            if payload.lines and len(payload.lines) > 0:
                first_line = payload.lines[0]
                for inline in first_line.items:
                    if inline.kind in ("text_run", "field"):
                        data = inline.data or {}
                        run_style = data.get("style") or {}
                        # Pobierz font_size z pierwszego runu tekstu
                        first_run_font_size_val = run_style.get("font_size") or run_style.get("size") or default_font_size
                        try:
                            from ..assembler.utils import normalize_font_size
                            first_run_font_size = normalize_font_size(first_run_font_size_val) or default_font_size
                        except (TypeError, ValueError, ImportError):
                            try:
                                first_run_font_size = float(first_run_font_size_val)
                            except (TypeError, ValueError):
                                first_run_font_size = default_font_size
                        marker_font_size = first_run_font_size
                        break  # Use font_size from first text run
            
            
            marker_color_value = marker.get("color") or default_color_value
            marker_color = self._color_to_reportlab(marker_color_value, default_color_value)

            try:
                c.setFont(marker_font_name, marker_font_size)
            except Exception:
                c.setFont("Helvetica", marker_font_size)
            c.setFillColor(marker_color)
            if marker_text:
                c.drawString(float(marker_x), marker_baseline, marker_text)

        # Set default values for further rendering
        c.setFillColor(default_color)
        try:
            c.setFont(default_font_name, default_font_size)
        except Exception:
            c.setFont("Helvetica", default_font_size)

        raw_style = payload.metadata.get("raw_style", {}) if isinstance(payload.metadata, dict) else {}
        paragraph_alignment = (
            base_style.get("text_align")
            or base_style.get("alignment")
            or base_style.get("justify")
            or raw_style.get("justification")
            or raw_style.get("alignment")
            or ""
        )
        paragraph_alignment = str(paragraph_alignment).lower() if paragraph_alignment else ""
        if paragraph_alignment in {"both", "justify"}:
            paragraph_alignment = "justify"
        elif paragraph_alignment in {"center", "right", "left"}:
            pass
        else:
            paragraph_alignment = ""

        is_body_context = not header_footer_context
        if is_body_context and not paragraph_alignment:
            paragraph_alignment = "justify"

        t0_lines = time.perf_counter()
        lines_time = 0.0
        inline_items_time = 0.0
        rust_calls_time = 0.0
        line_count = 0
        inline_count = 0
        
        for line_index, line in enumerate(payload.lines):
            t0_line = time.perf_counter()
            line_count += 1
            baseline_y = text_top - line.baseline_y
            if baseline_y + line.height < rect.bottom:
                continue

            try:
                c.setFont(default_font_name, default_font_size)
            except Exception:
                c.setFont("Helvetica", default_font_size)
            c.setFillColor(default_color)

            line_start_x = text_left + line.offset_x
            line_content_width = 0.0
            for inline in line.items:
                line_content_width = max(line_content_width, inline.x + inline.width)
            
            # For table cells, use rect.width (which accounts for cell padding) instead of line.available_width
            # line.available_width may not account for cell padding if payload was created before padding calculation
            effective_available_width = max(rect.width, line.available_width)
            extra_space_total = max(effective_available_width - line_content_width, 0.0)

            if paragraph_alignment == "center" and line_content_width > 0.0:
                line_start_x += extra_space_total / 2.0
            elif paragraph_alignment == "right" and line_content_width > 0.0:
                line_start_x += extra_space_total

            apply_justification = False
            word_spacing_delta = 0.0
            space_token_count = 0
            if (
                paragraph_alignment == "justify"
                and is_body_context
                and line.available_width > 0.0
                and line_index < len(payload.lines) - 1
            ):
                has_inline_image = any(
                    inline.kind in ("inline_image", "inline_textbox") for inline in line.items
                )
                if not has_inline_image:
                    extra_space = line.available_width - line_content_width
                    if extra_space > 0.1:
                        for inline in line.items:
                            if inline.kind in ("text_run", "field"):
                                data = inline.data or {}
                                space_token_count += int(data.get("space_count") or 0)
                                if not data.get("space_count"):
                                    text_value = (
                                        data.get("text")
                                        or data.get("display")
                                        or data.get("value")
                                        or ""
                                    )
                                    if text_value:
                                        space_token_count += text_value.count(" ")
                        if space_token_count > 0:
                            word_spacing_delta = extra_space / space_token_count
                            apply_justification = True

            cumulative_extra = 0.0
            t0_inline = time.perf_counter()

            for inline_idx, inline in enumerate(line.items):
                t0_inline_item = time.perf_counter()
                inline_count += 1
                item_x = line_start_x + inline.x + cumulative_extra

                if inline.kind in ("text_run", "field"):
                    data = inline.data or {}
                    if inline.kind == "field":
                        text = self._resolve_field_text(data.get("field"))
                        # For field codes, use actual text width instead of inline.width
                        # to avoid too large gaps
                        if text:
                            # Calculate actual field code text width
                            run_style_temp = data.get("style") or {}
                            font_name_temp = self._select_font_variant(
                                run_style_temp.get("font_name")
                                or run_style_temp.get("font_ascii")
                                or run_style_temp.get("font_hAnsi")
                                or default_font_name,
                                run_style_temp,
                            )
                            font_size_temp_val = run_style_temp.get("font_size") or run_style_temp.get("size") or default_font_size
                            try:
                                from ..assembler.utils import normalize_font_size
                                font_size_temp = normalize_font_size(font_size_temp_val) or default_font_size
                            except (TypeError, ValueError, ImportError):
                                try:
                                    font_size_temp = float(font_size_temp_val)
                                except (TypeError, ValueError):
                                    font_size_temp = default_font_size
                            
                            # Calculate actual text width
                            try:
                                actual_width = c.stringWidth(text, font_name_temp, font_size_temp)
                                # Save difference between estimated and actual width
                                width_diff = actual_width - inline.width
                                if abs(width_diff) > 0.1:  # Only if difference is significant
                                    # Update inline.width to actual width
                                    inline.width = actual_width
                                    # Adjust cumulative_extra so next runs are shifted by the difference
                                    cumulative_extra += width_diff
                            except Exception:
                                # Fallback: use original width
                                pass
                    else:
                        text = data.get("text") or data.get("display") or ""
                    if text is None:
                        text = ""

                    run_style_source = data.get("style") or {}
                    run_style = dict(run_style_source) if isinstance(run_style_source, dict) else {}
                    # Inline attributes might be provided separately from style dict
                    inline_flag_map = {
                        "bold": data.get("bold"),
                        "italic": data.get("italic"),
                        "underline": data.get("underline"),
                        "strike_through": data.get("strike_through")
                        or data.get("strikethrough")
                        or data.get("strike"),
                        "superscript": data.get("superscript"),
                        "subscript": data.get("subscript"),
                        "highlight": data.get("highlight"),
                    }
                    for key, value in inline_flag_map.items():
                        if value not in (None, False, ""):
                            if key == "strike_through":
                                run_style["strike_through"] = bool(value)
                            else:
                                run_style[key] = value
                    font_name = self._select_font_variant(
                        run_style.get("font_name")
                        or run_style.get("font_ascii")
                        or run_style.get("font_hAnsi")
                        or default_font_name,
                        run_style,
                    )
                    
                    # Check if superscript/subscript BEFORE getting font_size
                    is_superscript = run_style.get("superscript") or data.get("superscript")
                    is_subscript = run_style.get("subscript") or data.get("subscript")
                    
                    font_size_val = run_style.get("font_size") or run_style.get("size") or default_font_size
                    # Use normalize_font_size to convert half-points to points
                    try:
                        from ..assembler.utils import normalize_font_size
                        font_size = normalize_font_size(font_size_val) or default_font_size
                    except (TypeError, ValueError, ImportError):
                        try:
                            font_size = float(font_size_val)
                        except (TypeError, ValueError):
                            font_size = default_font_size
                    
                    
                    # If font_size looks reduced (e.g. < 70% default_font_size) and we have superscript/subscript,
                    # it was probably already reduced earlier - restore original size
                    # In footnotes we use ORIGINAL run font_size (not reduced)
                    if (is_superscript or is_subscript) and font_size < default_font_size * 0.7:
                        # Font_size was probably already reduced, restore original (like in footnotes)
                        original_font_size = font_size / 0.58
                        # Don't reduce again - already reduced
                        # font_size pozostaje bez zmian
                    else:
                        # Zapisz oryginalny font_size przed zmniejszeniem (dla obliczenia baseline_shift)
                        original_font_size = font_size
                        # Zmniejsz font_size dla superscript i subscript (tak samo jak w footnotes: 0.58 * font_size)
                        if is_superscript or is_subscript:
                            font_size = original_font_size * 0.58  # Tak samo jak w footnotes

                    color_value = (
                        run_style.get("color")
                        or run_style.get("font_color")
                        or default_color_value
                    )
                    fill_color = self._color_to_reportlab(color_value, default_color_value)

                    # Calculate baseline_shift same as in footnotes (using original font_size)
                    # In footnotes we use: superscript_baseline_shift = font_size * 0.33 (where font_size is original size)
                    if is_superscript:
                        # Always use same calculation as in footnotes: 0.33 * original_font_size
                        baseline_shift = original_font_size * 0.33
                    elif is_subscript:
                        # For subscript shift down
                        baseline_shift = -original_font_size * 0.25
                    else:
                        # For normal text use baseline_shift from data (if exists)
                        baseline_shift = data.get("baseline_shift", 0.0)
                    
                    run_baseline = baseline_y + baseline_shift

                    extra_width = 0.0
                    if apply_justification and word_spacing_delta > 0.0:
                        space_multiplier = int(data.get("space_count") or 0)
                        if space_multiplier:
                            # For superscript/subscript spaces should have reduced width
                            # (proporcjonalnie do zmniejszonego font_size)
                            if is_superscript or is_subscript:
                                # Reduce space width proportionally to reduced font_size
                                # font_size is already reduced (0.58 * original), so spaces should also be smaller
                                # Ale word_spacing_delta jest obliczony dla normalnego font_size,
                                # so we need to scale it
                                space_scale_factor = 0.58  # Tak samo jak zmniejszenie font_size
                                extra_width = word_spacing_delta * space_multiplier * space_scale_factor
                            else:
                                extra_width = word_spacing_delta * space_multiplier

                    effective_width = inline.width + extra_width

                    highlight_value = data.get("highlight") or run_style.get("highlight")
                    highlight_color = self._resolve_highlight_color(highlight_value)
                    if highlight_color:
                        c.saveState()
                        try:
                            c.setFillColor(self._color_to_reportlab(highlight_color, highlight_color))
                            c.rect(
                                item_x,
                                run_baseline - inline.descent,
                                effective_width,
                                inline.ascent + inline.descent,
                                fill=1,
                                stroke=0,
                            )
                        finally:
                            c.restoreState()

                    t0_rust = time.perf_counter()
                    try:
                        c.setFont(font_name, font_size)
                    except Exception:
                        c.setFont("Helvetica", font_size)
                    c.setFillColor(fill_color)
                    if text:
                        c.drawString(item_x, run_baseline, text)
                    rust_calls_time += time.perf_counter() - t0_rust

                    hyperlink_url = self._resolve_hyperlink_url(run_style.get("hyperlink"), text)
                    if hyperlink_url and effective_width > 0.0:
                        link_rect = (
                            item_x,
                            run_baseline - inline.descent,
                            item_x + effective_width,
                            run_baseline + inline.ascent,
                        )
                        try:
                            c.linkURL(hyperlink_url, link_rect, relative=0)
                        except Exception:
                            logger.debug(f"Nie udało się zarejestrować linkURL: {hyperlink_url}")

                    if run_style.get("underline"):
                        c.saveState()
                        try:
                            c.setStrokeColor(fill_color)
                            c.setLineWidth(max(font_size * 0.055, 0.4))
                            underline_y = run_baseline - max(font_size * 0.15, 0.6)
                            c.line(item_x, underline_y, item_x + effective_width, underline_y)
                        finally:
                            c.restoreState()

                    if run_style.get("strike_through") or run_style.get("strikethrough"):
                        c.saveState()
                        try:
                            c.setStrokeColor(fill_color)
                            c.setLineWidth(max(font_size * 0.05, 0.4))
                            strike_y = run_baseline + max(font_size * 0.3, 0.6)
                            c.line(item_x, strike_y, item_x + effective_width, strike_y)
                        finally:
                            c.restoreState()
                    
                    # Render footnote/endnote references
                    footnote_refs = data.get("footnote_refs") or run_style.get("footnote_refs", [])
                    endnote_refs = data.get("endnote_refs") or run_style.get("endnote_refs", [])
                    
                    if footnote_refs or endnote_refs:
                        # Renderuj numery footnotes/endnotes jako superskrypt
                        ref_numbers = []
                        if footnote_refs:
                            if isinstance(footnote_refs, str):
                                footnote_refs = [footnote_refs]
                            elif not isinstance(footnote_refs, list):
                                footnote_refs = []
                            # Get numbers from footnote_renderer if available
                            for ref_id in footnote_refs:
                                ref_number = str(ref_id)  # Fallback: use ID
                                # Try to get number from renderer if available
                                if self.footnote_renderer:
                                    try:
                                        num = self.footnote_renderer.get_footnote_number(str(ref_id))
                                        if num is not None:
                                            ref_number = str(num)
                                    except Exception:
                                        pass
                                ref_numbers.append(ref_number)
                        
                        if endnote_refs:
                            if isinstance(endnote_refs, str):
                                endnote_refs = [endnote_refs]
                            elif not isinstance(endnote_refs, list):
                                endnote_refs = []
                            for ref_id in endnote_refs:
                                ref_number = str(ref_id)
                                if self.footnote_renderer:
                                    try:
                                        num = self.footnote_renderer.get_endnote_number(str(ref_id))
                                        if num is not None:
                                            ref_number = str(num)
                                    except Exception:
                                        pass
                                ref_numbers.append(ref_number)
                        
                        if ref_numbers:
                            # Renderuj numery jako superskrypt (np. "1", "2")
                            # In DOCX footnote references are by default superscript
                            ref_text = "".join([str(n) for n in ref_numbers])  # No spaces, directly after text
                            
                            # Superscript: smaller font (about 58-60% size) and higher (about 33% font_size)
                            ref_font_size = font_size * 0.58  # Standardowy rozmiar superscript
                            superscript_baseline_shift = font_size * 0.33  # Standardowy baseline shift dla superscript
                            ref_spacing = 1.0  # Spacing between text and index
                            
                            c.saveState()
                            try:
                                c.setFont(font_name, ref_font_size)
                                c.setFillColor(fill_color)
                                
                                # If run has no text (only footnote_refs), render index directly at item_x
                                # Otherwise render after text
                                if not text or text.strip() == "":
                                    # Run with only footnote_refs - render index directly at run position
                                    ref_x = item_x
                                else:
                                    # Run with text - render index after text
                                    # Index width is already included in inline.width by assembler
                                    ref_x = item_x + effective_width + ref_spacing  # Spacing after text
                                
                                ref_y = run_baseline + superscript_baseline_shift  # Baseline shift dla superscript
                                c.drawString(ref_x, ref_y, ref_text)
                            finally:
                                c.restoreState()
                            
                            # Index width is already included in inline.width by assembler,
                            # so no need to add to cumulative_extra

                    cumulative_extra += extra_width

                elif inline.kind == "inline_image":
                    image_data = inline.data.get("image") if isinstance(inline.data, dict) else None
                    if not image_data:
                        continue

                    img_path = self._resolve_image_path(image_data)
                    if not img_path:
                        continue

                    width = inline.width or inline.data.get("width") or 0.0
                    height = (inline.ascent + inline.descent) or inline.data.get("height") or 0.0
                    bottom = baseline_y - inline.descent

                    try:
                        c.drawImage(
                            img_path,
                            item_x,
                            bottom,
                            width=width,
                            height=height,
                            preserveAspectRatio=True,
                            mask="auto",
                        )
                    except Exception as exc:
                        logger.debug(f"Nie udało się narysować inline image: {exc}")

                elif inline.kind == "inline_textbox":
                    textbox = inline.data.get("textbox") if isinstance(inline.data, dict) else None
                    paragraph_payload_inline = None
                    if isinstance(textbox, ParagraphLayout):
                        paragraph_payload_inline = textbox
                    elif isinstance(textbox, dict):
                        candidate = textbox.get("layout_payload") or textbox.get("_layout_payload")
                        if isinstance(candidate, ParagraphLayout):
                            paragraph_payload_inline = candidate

                    if paragraph_payload_inline:
                        textbox_rect = Rect(
                            x=item_x,
                            y=baseline_y - inline.descent,
                            width=inline.width,
                            height=inline.ascent + inline.descent,
                        )
                        self._draw_paragraph_from_layout(
                            c,
                            textbox_rect,
                            paragraph_payload_inline,
                            {},
                            None,
                            header_footer_context,
                            pagination_segment_index=None,  # Inline textboxes are not segmented
                        )
            
            # End of inline items loop - measure time
            inline_items_time += time.perf_counter() - t0_inline
            
            # End of line loop - measure time
            lines_time += time.perf_counter() - t0_line
        
        total_lines_time = time.perf_counter() - t0_lines

        # Restore default color
        c.setFillColor(default_color)

        if payload.overlays:
            self._draw_overlays(c, payload.overlays, header_footer_context)
        
        # Track timing if available
        func_time = time.perf_counter() - t0_func
        if hasattr(self, '_current_timings') and self._current_timings is not None:
            if 'draw_paragraph_from_layout' not in self._current_timings:
                self._current_timings['draw_paragraph_from_layout'] = []
            self._current_timings['draw_paragraph_from_layout'].append(func_time)
            # Store detailed timings
            if 'draw_paragraph_setup' not in self._current_timings:
                self._current_timings['draw_paragraph_setup'] = []
            self._current_timings['draw_paragraph_setup'].append(setup_time)
            if 'draw_paragraph_lines' not in self._current_timings:
                self._current_timings['draw_paragraph_lines'] = []
            self._current_timings['draw_paragraph_lines'].append(lines_time)
            if 'draw_paragraph_inline_items' not in self._current_timings:
                self._current_timings['draw_paragraph_inline_items'] = []
            self._current_timings['draw_paragraph_inline_items'].append(inline_items_time)
            if 'draw_paragraph_rust_calls' not in self._current_timings:
                self._current_timings['draw_paragraph_rust_calls'] = []
            self._current_timings['draw_paragraph_rust_calls'].append(rust_calls_time)
            # Store counts for analysis
            if 'draw_paragraph_line_count' not in self._current_timings:
                self._current_timings['draw_paragraph_line_count'] = []
            self._current_timings['draw_paragraph_line_count'].append(line_count)
            if 'draw_paragraph_inline_count' not in self._current_timings:
                self._current_timings['draw_paragraph_inline_count'] = []
            self._current_timings['draw_paragraph_inline_count'].append(inline_count)
    
    def _draw_overlays(
        self,
        c: canvas.Canvas,
        overlays: List[OverlayBox],
        header_footer_context: Optional[str] = None,
    ) -> None:
        for overlay in overlays:
            frame = overlay.frame
            if overlay.kind == "image":
                image_source = overlay.payload.get("image") or overlay.payload.get("source") or overlay.payload.get("content")
                if not image_source:
                    continue
                img_path = self._resolve_image_path(image_source)
                if not img_path:
                    continue
                try:
                    c.drawImage(
                        img_path,
                        frame.x,
                        frame.y,
                        width=frame.width,
                        height=frame.height,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                except Exception as exc:
                    logger.debug(f"Nie udało się narysować overlay image: {exc}")
            elif overlay.kind == "textbox":
                overlay_payload = overlay.payload if isinstance(overlay.payload, dict) else {}
                paragraph_payload = overlay_payload.get("layout_payload")
                if not isinstance(paragraph_payload, ParagraphLayout):
                    textbox_payload = overlay_payload.get("textbox") or overlay_payload.get("content") or overlay_payload.get("layout")
                    if isinstance(textbox_payload, ParagraphLayout):
                        paragraph_payload = textbox_payload
                    elif isinstance(textbox_payload, dict):
                        candidate = textbox_payload.get("layout_payload") or textbox_payload.get("_layout_payload")
                        if isinstance(candidate, ParagraphLayout):
                            paragraph_payload = candidate

                if isinstance(paragraph_payload, ParagraphLayout):
                    textbox_style = overlay_payload.get("style") or {}
                    self._draw_paragraph_from_layout(
                        c,
                        overlay.frame,
                        paragraph_payload,
                        textbox_style,
                        None,
                        header_footer_context,
                        pagination_segment_index=None,  # Overlays are not segmented
                    )
                else:
                    textbox_style = overlay_payload.get("style") or {}
                    textbox_text = overlay_payload.get("text") or ""
                    textbox_block = LayoutBlock(
                        frame=overlay.frame,
                        block_type="textbox",
                        content={"text": textbox_text, "style": textbox_style},
                        style=textbox_style or {},
                    )
                    self._draw_textbox(c, textbox_block)
    def _parse_cell_margins(self, cell: Any, default_margin: float = 0.0) -> Dict[str, float]:
        """

        Parses cell margins from DOCX (twips) to points.

        Args:
        cell: Cell (can be dict, string, or TableCell object)
        default_margin: Default margin in points (if no margins specified)

        Returns:
        Dict with margins: {"top": float, "bottom": float, "left": float, "right": float}

        """
        margins = {
            "top": default_margin,
            "bottom": default_margin,
            "left": default_margin,
            "right": default_margin
        }
        
        # Get margins from cell
        cell_margins = None
        if hasattr(cell, 'cell_margins'):
            cell_margins = cell.cell_margins
        elif hasattr(cell, 'margins'):
            cell_margins = cell.margins
        elif isinstance(cell, dict):
            cell_margins = cell.get("margins") or cell.get("cell_margins")
        
        # If no margins in cell, check in style/styles
        if not cell_margins:
            # Check cell.styles (from parser) - parser saves margins in styles['margins']
            if isinstance(cell, dict):
                cell_styles = cell.get("styles", {})
                if isinstance(cell_styles, dict):
                    cell_margins = cell_styles.get("margins")
            elif hasattr(cell, 'styles'):
                cell_styles = cell.styles if isinstance(cell.styles, dict) else {}
                cell_margins = cell_styles.get("margins")
            
            # If still none, check in cell.style (from style_bridge)
            if not cell_margins:
                cell_style = {}
                if hasattr(cell, 'style'):
                    cell_style = cell.style if isinstance(cell.style, dict) else {}
                elif isinstance(cell, dict):
                    cell_style = cell.get("style", {})
                
                cell_margins = cell_style.get("margins") or cell_style.get("cell_margins")
        
        # Parsuj marginesy z twips na punkty
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
                if margin_data in (None, "", {}):
                    continue
                unit = ""
                raw_value = None
                if isinstance(margin_data, dict):
                    raw_value = (
                        margin_data.get("w")
                        or margin_data.get("width")
                        or margin_data.get("value")
                        or margin_data.get("val")
                    )
                    unit = str(margin_data.get("type") or margin_data.get("unit") or "").lower()
                else:
                    raw_value = margin_data
                
                # If raw_value is empty string or None, skip
                if raw_value in (None, "", {}, "auto"):
                    continue
                
                # Konwertuj na float
                try:
                    numeric = float(raw_value)
                except (TypeError, ValueError):
                    logger.debug(f"Failed to convert margin value to float: {raw_value} (key: {margin_key})")
                    continue
                
                # Konwertuj z twips na punkty
                # In DOCX, tcMar always uses dxa (twips), so if unit is empty but value is large (>50), it's probably twips
                if unit in {"dxa", "twip", "twips"}:
                    numeric = twips_to_points(numeric)
                elif unit == "pt" or unit == "point" or unit == "points":
                    # Already in points
                    pass
                elif not unit and abs(numeric) > 50:
                    # Probably twips (typical values are 100-500 twips = 5-25 pt)
                    numeric = twips_to_points(numeric)
                # If unit is empty and value is small, assume it's already points
                
                side_key = margin_map.get(margin_key.lower(), margin_key.lower())
                if side_key in margins:
                    margins[side_key] = max(numeric, 0.0)
                    logger.debug(f"Parsed cell margin {side_key}: {numeric} pt (from {raw_value} {unit or 'unknown unit'})")

        gap_value = None
        if hasattr(cell, "cell_spacing"):
            gap_value = getattr(cell, "cell_spacing")
        elif hasattr(cell, "cellSpacing"):
            gap_value = getattr(cell, "cellSpacing")
        elif isinstance(cell, dict):
            gap_value = (
                cell.get("cell_spacing")
                or cell.get("cellSpacing")
                or cell.get("spacing_between_cells")
                or cell.get("table_cell_spacing")
            )
        if gap_value in (None, "", {}):
            gap_value = default_margin
        try:
            gap_numeric = float(gap_value)
        except (TypeError, ValueError):
            gap_numeric = default_margin
        if gap_numeric and gap_numeric > 0.0:
            gap_pt = gap_numeric / 2.0 if gap_numeric > default_margin else gap_numeric / 2.0
            margins["left"] = max(margins["left"], gap_pt)
            margins["right"] = max(margins["right"], gap_pt)
            margins["top"] = max(margins["top"], gap_pt)
            margins["bottom"] = max(margins["bottom"], gap_pt)
        
        return margins
    
    @staticmethod
    def _normalize_horizontal_alignment(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            candidate = (
                value.get("val")
                or value.get("value")
                or value.get("alignment")
                or value.get("jc")
                or value.get("text_align")
            )
            if candidate is not None:
                value = candidate
        if value in (None, "", {}, False):
            return None
        token = str(value).strip().lower()
        if not token:
            return None
        mapping = {
            "centre": "center",
            "middle": "center",
            "center": "center",
            "right": "right",
            "end": "right",
            "left": "left",
            "start": "left",
            "both": "justify",
            "justify": "justify",
        }
        normalized = mapping.get(token, token)
        if normalized in {"left", "center", "right", "justify"}:
            return normalized
        return None

    @staticmethod
    def _normalize_vertical_alignment(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            candidate = value.get("val") or value.get("value") or value.get("alignment")
            if candidate is not None:
                value = candidate
        if value in (None, "", {}, False):
            return None
        token = str(value).strip().lower()
        if not token:
            return None
        mapping = {
            "centre": "center",
            "middle": "center",
            "center": "center",
            "top": "top",
            "bottom": "bottom",
            "baseline": "bottom",
            "start": "top",
            "end": "bottom",
        }
        normalized = mapping.get(token, token)
        if normalized in {"top", "center", "bottom"}:
            return normalized
        return None

    def _resolve_cell_horizontal_alignment(
        self,
        cell: Any,
        cell_style: Dict[str, Any],
        content_items: Optional[List[Any]] = None,
    ) -> Optional[str]:
        candidates: List[Any] = []
        for key in (
            "text_align",
            "alignment",
            "align",
            "h_align",
            "hAlign",
            "jc",
            "justify",
        ):
            if key in cell_style:
                candidates.append(cell_style.get(key))
        if hasattr(cell, "alignment"):
            candidates.append(getattr(cell, "alignment"))
        if hasattr(cell, "text_align"):
            candidates.append(getattr(cell, "text_align"))
        if isinstance(cell, dict):
            for key in ("text_align", "alignment", "align", "jc", "justify"):
                if key in cell:
                    candidates.append(cell.get(key))
            raw_style = cell.get("style")
            if isinstance(raw_style, dict):
                for key in ("text_align", "alignment", "align", "jc", "justify"):
                    if key in raw_style:
                        candidates.append(raw_style.get(key))
        for candidate in candidates:
            normalized = self._normalize_horizontal_alignment(candidate)
            if normalized:
                return normalized
        if content_items:
            for item in content_items:
                style = self._extract_style(item)
                for key in ("text_align", "alignment", "align", "jc", "justify"):
                    if key in style:
                        normalized = self._normalize_horizontal_alignment(style.get(key))
                        if normalized:
                            return normalized
                if isinstance(item, dict):
                    raw = item.get("style")
                    if isinstance(raw, dict):
                        normalized = self._normalize_horizontal_alignment(
                            raw.get("justification") or raw.get("alignment")
                        )
                        if normalized:
                            return normalized
        return None

    def _resolve_cell_vertical_alignment(self, cell: Any, cell_style: Dict[str, Any]) -> Optional[str]:
        candidates: List[Any] = []
        for key in ("vertical_align", "vAlign", "valign"):
            if key in cell_style:
                candidates.append(cell_style.get(key))
        if hasattr(cell, "vertical_align"):
            candidates.append(getattr(cell, "vertical_align"))
        if isinstance(cell, dict):
            for key in ("vertical_align", "vAlign", "valign"):
                if key in cell:
                    candidates.append(cell.get(key))
            raw_style = cell.get("style")
            if isinstance(raw_style, dict):
                for key in ("vertical_align", "vAlign", "valign"):
                    if key in raw_style:
                        candidates.append(raw_style.get(key))
        for candidate in candidates:
            normalized = self._normalize_vertical_alignment(candidate)
            if normalized:
                return normalized
        return None

    def _draw_table(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """

        Renders table as rectangles and text in cells.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of type "table"

        """
        rect = block.frame
        content_value, _payload = self._resolve_content(block.content)
        content = content_value if isinstance(content_value, dict) else {}
        style = block.style or {}
        if not isinstance(style, dict):
            style = {}
        table_header_footer_context = content.get("header_footer_context") if isinstance(content, dict) else None
        
        def _border_spec_visible(raw: Any) -> bool:
            if not raw:
                return False
            if isinstance(raw, dict):
                style_token = raw.get("val") or raw.get("style")
                if isinstance(style_token, str) and style_token.strip().lower() in {"none", "nil"}:
                    return False
                width_value: Optional[float] = None
                raw_width = raw.get("width")
                if raw_width is not None:
                    try:
                        width_value = float(raw_width)
                    except (TypeError, ValueError):
                        width_value = None
                if width_value is None and raw.get("sz") is not None:
                    try:
                        width_value = float(raw.get("sz")) / 8.0
                    except (TypeError, ValueError):
                        width_value = None
                if isinstance(width_value, (int, float)) and width_value <= 0:
                    return False
                return True
            if isinstance(raw, str):
                return raw.strip().lower() not in {"", "none", "nil", "0"}
            if isinstance(raw, (int, float)):
                return float(raw) > 0.0
            return bool(raw)

        def _normalize_inside_spec(raw: Any) -> Optional[Dict[str, Any]]:
            if not _border_spec_visible(raw):
                return None
            if isinstance(raw, dict):
                spec = dict(raw)
                style_token = spec.get("style") or spec.get("val")
                if style_token:
                    spec["style"] = style_token
                width_value = spec.get("width")
                if width_value is None and spec.get("sz") is not None:
                    try:
                        width_value = float(spec.get("sz")) / 8.0
                    except (TypeError, ValueError):
                        width_value = None
                if isinstance(width_value, (int, float)):
                    spec["width"] = float(width_value)
                color_value = spec.get("color")
                if not color_value and spec.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color"):
                    spec["color"] = spec.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color")
                return spec
            if isinstance(raw, (int, float)):
                width_value = max(float(raw), 0.0)
                if width_value <= 0.0:
                    return None
                return {"width": width_value, "style": "solid", "color": "#000000"}
            if isinstance(raw, str) and raw.strip():
                token = raw.strip()
                if token.lower() in {"none", "nil"}:
                    return None
                return {"style": token}
            return None

        style_borders = style.get("borders") if isinstance(style.get("borders"), dict) else {}
        table_borders_style = dict(style_borders)
        inside_h_raw = table_borders_style.get("insideH") or table_borders_style.get("insideh")
        inside_v_raw = table_borders_style.get("insideV") or table_borders_style.get("insidev")
        table_inside_h_spec = _normalize_inside_spec(inside_h_raw)
        table_inside_v_spec = _normalize_inside_spec(inside_v_raw)
        inside_h_visible = bool(table_inside_h_spec)
        inside_v_visible = bool(table_inside_v_spec)
        table_has_borders = bool(table_borders_style)
        draw_default_cell_grid = False

        # Debug: check if this is table from footer/header
        if hasattr(block, 'page_number'):
            logger.debug(f"Rendering table on page {block.page_number}, block_type: {block.block_type}")
        
        # Render background and border for entire table
        try:
            draw_background(c, rect, style)
            draw_border(c, rect, style)
        except Exception as e:
            logger.debug(f"Błąd renderowania background/border tabeli: {e}")
        
        # Pobierz wiersze
        rows = content.get("rows", []) if isinstance(content, dict) else []
        if not rows:
            logger.debug(f"Table has no rows")
            return
        
        logger.debug(f"Table has {len(rows)} rows")
        
        # Pobierz style
        font_name = style.get("font_name", "Helvetica")
        font_size = float(style.get("font_size", 10))
        cell_padding = float(style.get("cell_padding", 0.0))
        default_row_height = float(style.get("row_height", 18.0))
        
        # Convert rows to cell lists
        processed_rows: List[List[Any]] = []
        row_styles: List[Dict[str, Any]] = []
        for row in rows:
            row_style: Dict[str, Any] = {}
            if isinstance(row, (list, tuple)):
                processed_rows.append(list(row))
                row_styles.append({})
            elif isinstance(row, dict):
                # For dict, check if has cells
                row_style = row.get("style") if isinstance(row.get("style"), dict) else {}
                if "cells" in row:
                    cells = row["cells"]
                    if isinstance(cells, list):
                        processed_rows.append(cells)
                        row_styles.append(row_style)
                    else:
                        processed_rows.append([cells])
                        row_styles.append(row_style)
                else:
                    # May be directly a list of cells
                    processed_rows.append([row])
                    row_styles.append(row_style)
            elif hasattr(row, "cells"):
                # Obiekt TableRow z atrybutem cells
                row_style = row.style if isinstance(getattr(row, "style", None), dict) else {}
                processed_rows.append(list(row.cells))
                row_styles.append(row_style)
            elif hasattr(row, "__iter__") and not isinstance(row, str):
                # Iterable ale nie string
                processed_rows.append(list(row))
                row_styles.append({})
            else:
                processed_rows.append([row])
                row_styles.append({})
        
        rows = processed_rows
        
        # Debug: check first rows of table
        if len(rows) > 0:
            logger.debug(f"Table has {len(rows)} rows, first row has {len(rows[0])} cells")
        
        # Try to get previously calculated row heights and column widths from LayoutAssembler
        layout_info = content.get("layout_info", {})
        row_heights = layout_info.get("row_heights")
        col_widths = layout_info.get("col_widths")
        
        # If no saved heights, calculate them (fallback)
        if row_heights is None or len(row_heights) != len(rows):
            # Calculate column widths (equal)
            num_cols = max(len(row) for row in rows) if rows else 1
            col_width = rect.width / num_cols if num_cols > 0 else rect.width
            col_widths = [col_width] * num_cols
            
            # Calculate height of each row based on cell contents
            # row_height = max(min_row_height, max(cell.height for cell in row))
            min_row_height = default_row_height
            row_heights = []
            for row in rows:
                cell_heights = []
                cells = row if isinstance(row, list) else [row]
                
                for cell in cells:
                    # Get cell text
                    cell_text = ""
                    if hasattr(cell, 'get_text'):
                        cell_text = cell.get_text()
                    elif isinstance(cell, dict):
                        cell_text = str(cell.get("text", cell.get("content", "")))
                    else:
                        cell_text = str(cell)
                    
                    # Get cell styles
                    cell_style = {}
                    if hasattr(cell, 'style'):
                        cell_style = cell.style if isinstance(cell.style, dict) else {}
                    elif isinstance(cell, dict):
                        cell_style = cell.get("style", {})
                    
                    # Check if cell has specified height
                    cell_height = None
                    if hasattr(cell, 'height') and cell.height is not None:
                        cell_height = float(cell.height)
                    elif isinstance(cell, dict) and 'height' in cell:
                        cell_height = float(cell.get("height"))
                    
                    # If no specified height, calculate based on text
                    if cell_height is None:
                        if cell_text:
                            try:
                                # Use width of appropriate column
                                cell_col_width = col_widths[cell_idx] if cell_idx < len(col_widths) else col_widths[0] if col_widths else rect.width / len(cells)
                                # Use style from cell or table style as fallback
                                cell_text_style = {**style, **cell_style}
                                text_layout: TextLayout = self.metrics.layout_text(
                                    cell_text,
                                    cell_text_style,
                                    cell_col_width - 2 * cell_padding,
                                )
                                # Cell height = number of lines * line_height + padding
                                cell_height = len(text_layout.lines) * text_layout.line_height + (2 * cell_padding)
                            except Exception as e:
                                logger.debug(f"Błąd obliczania wysokości komórki: {e}, używam domyślnej")
                                # Fallback: szacuj na podstawie liczby linii tekstu
                                cell_font_size = float(cell_style.get("font_size", style.get("font_size", font_size)))
                                cell_line_spacing = float(cell_style.get("line_spacing", 1.2))
                                lines = max(1, len(cell_text.splitlines()))
                                cell_height = lines * cell_font_size * cell_line_spacing + (2 * cell_padding)
                        else:
                            # Empty cell - use minimum height
                            cell_height = min_row_height
                
                    if cell_height is not None:
                        cell_heights.append(cell_height)
                
                # row_height = max(min_row_height, max(cell_height for cell in row))
                max_cell_height = max(cell_heights) if cell_heights else min_row_height
                row_height = max(min_row_height, max_cell_height)
                row_heights.append(row_height)
        else:
            # Use saved values from LayoutAssembler
            if col_widths is None or len(col_widths) == 0:
                # Fallback: even distribution
                num_cols = max(len(row) for row in rows) if rows else 1
                col_width = rect.width / num_cols if num_cols > 0 else rect.width
                col_widths = [col_width] * num_cols
            
            # Scale column widths if sum doesn't match table width
            total_width = sum(col_widths)
            if total_width > 0 and abs(total_width - rect.width) > 0.1:
                scale = rect.width / total_width
                col_widths = [w * scale for w in col_widths]
        
        # Render rows from top
        y = rect.y + rect.height
        
        # Track vertical merge - which cells are part of merge
        vertical_merge_tracker = {}  # {(row_idx, col_idx): (start_row, rowspan)}
        
        total_columns = len(col_widths) if col_widths else (max(len(row) for row in rows) if rows else 0)

        for row_idx, row in enumerate(rows):
            x = rect.x
            row_height = row_heights[row_idx]
            row_style = row_styles[row_idx] if row_styles and row_idx < len(row_styles) else {}
            row_rect = Rect(rect.x, y - row_height, rect.width, row_height)
            try:
                draw_background(c, row_rect, row_style)
                draw_border(c, row_rect, row_style)
            except Exception:
                pass
            
            # Cells are already a list
            cells = row if isinstance(row, list) else [row]
            
            # Render cells
            col_idx = 0
            cell_idx = 0
            while cell_idx < len(cells):
                cell = cells[cell_idx]
                
                # Pobierz grid_span (colspan) i vertical_merge
                grid_span = 1
                vertical_merge = None
                vertical_merge_type = None
                
                if hasattr(cell, 'grid_span'):
                    grid_span = cell.grid_span or 1
                elif isinstance(cell, dict):
                    grid_span = cell.get("grid_span") or cell.get("gridSpan") or 1
                    if isinstance(grid_span, str):
                        try:
                            grid_span = int(grid_span)
                        except (ValueError, TypeError):
                            grid_span = 1
                
                if hasattr(cell, 'vertical_merge_type'):
                    vertical_merge_type = cell.vertical_merge_type
                elif hasattr(cell, 'vertical_merge'):
                    vertical_merge = cell.vertical_merge
                elif isinstance(cell, dict):
                    vertical_merge_type = cell.get("vertical_merge_type") or cell.get("vMerge")
                    if isinstance(vertical_merge_type, dict):
                        vertical_merge_type = vertical_merge_type.get("val")
                
                # Check if cell is part of vertical merge (continue)
                if vertical_merge_type == "continue" or (vertical_merge and vertical_merge_type != "restart"):
                    # This is merge continuation - skip rendering but shift x
                    # Width = sum of column widths it spans
                    cell_width = sum(col_widths[col_idx:col_idx + grid_span]) if col_idx + grid_span <= len(col_widths) else col_widths[col_idx] if col_idx < len(col_widths) else rect.width / len(cells)
                    x += cell_width
                    col_idx += grid_span
                    cell_idx += 1
                    continue
                
                # Calculate cell width (may span multiple columns if grid_span > 1)
                if col_idx + grid_span <= len(col_widths):
                    cell_width = sum(col_widths[col_idx:col_idx + grid_span])
                else:
                    # Fallback: use single column width
                    cell_width = col_widths[col_idx] if col_idx < len(col_widths) else rect.width / len(cells)
                
                # Calculate cell height (may span multiple rows if vertical merge)
                cell_rowspan = 1
                if vertical_merge_type == "restart":
                    # This is start of vertical merge - find how many rows it spans
                    # We need to track columns because grid_span can change positions
                    # For simplicity, we check next rows and look for cells with vMerge="continue"
                    # in same column position (accounting for grid_span)
                    current_col_pos = col_idx
                    for next_row_idx in range(row_idx + 1, len(rows)):
                        next_row = rows[next_row_idx]
                        next_cells = next_row if isinstance(next_row, list) else [next_row]
                        
                        # Find cell that starts at same column position
                        next_col_pos = 0
                        found_continue = False
                        for next_cell_idx, next_cell in enumerate(next_cells):
                            next_grid_span = 1
                            if hasattr(next_cell, 'grid_span'):
                                next_grid_span = next_cell.grid_span or 1
                            elif isinstance(next_cell, dict):
                                next_grid_span = next_cell.get("grid_span") or next_cell.get("gridSpan") or 1
                                if isinstance(next_grid_span, str):
                                    try:
                                        next_grid_span = int(next_grid_span)
                                    except (ValueError, TypeError):
                                        next_grid_span = 1
                            
                            # Check if this is cell at same column position
                            if next_col_pos == current_col_pos:
                                next_vmerge = None
                                if hasattr(next_cell, 'vertical_merge_type'):
                                    next_vmerge = next_cell.vertical_merge_type
                                elif isinstance(next_cell, dict):
                                    next_vmerge = next_cell.get("vertical_merge_type") or next_cell.get("vMerge")
                                    if isinstance(next_vmerge, dict):
                                        next_vmerge = next_vmerge.get("val")
                                
                                if next_vmerge == "continue":
                                    cell_rowspan += 1
                                    found_continue = True
                                break
                            
                            next_col_pos += next_grid_span
                        
                        if not found_continue:
                            break
                
                # Calculate cell height (sum of row heights it spans)
                if cell_rowspan > 1:
                    cell_height = sum(row_heights[row_idx:row_idx + cell_rowspan])
                else:
                    cell_height = row_heights[row_idx]
                
                cell_rect = Rect(x, y - cell_height, cell_width, cell_height)
                
                # Render background and border for cell
                cell_style = {}
                if hasattr(cell, 'style'):
                    cell_style = cell.style if isinstance(cell.style, dict) else {}
                elif isinstance(cell, dict):
                    cell_style = cell.get("style", {})

                effective_cell_style: Dict[str, Any] = dict(cell_style) if isinstance(cell_style, dict) else {}
                effective_borders: Dict[str, Any] = {}
                if isinstance(effective_cell_style.get("borders"), dict):
                    effective_borders = dict(effective_cell_style.get("borders") or {})
                elif effective_cell_style.get("border"):
                    base_spec = effective_cell_style.get("border")
                    if isinstance(base_spec, dict):
                        for side_name in ("top", "bottom", "left", "right"):
                            effective_borders.setdefault(side_name, dict(base_spec))

                if table_inside_v_spec and col_idx > 0 and col_idx < total_columns:
                    if "left" not in effective_borders:
                        effective_borders["left"] = dict(table_inside_v_spec)
                if table_inside_h_spec and row_idx > 0:
                    if "top" not in effective_borders:
                        effective_borders["top"] = dict(table_inside_h_spec)

                if effective_borders:
                    effective_cell_style["borders"] = effective_borders

                if draw_default_cell_grid:
                    c.setStrokeColor(black)
                    c.setLineWidth(0.5)
                    c.rect(cell_rect.x, cell_rect.y, cell_rect.width, cell_rect.height)

                try:
                    draw_background(c, cell_rect, effective_cell_style)
                    draw_border(c, cell_rect, effective_cell_style)
                except Exception:
                    pass

                cell_margins = self._parse_cell_margins(cell, default_margin=cell_padding)
                cell_content_items = self._extract_cell_content(cell)
                horizontal_align = self._resolve_cell_horizontal_alignment(cell, effective_cell_style, cell_content_items)
                vertical_align = self._resolve_cell_vertical_alignment(cell, effective_cell_style)
                style_override: Dict[str, Any] = {}
                if horizontal_align:
                    style_override["alignment"] = horizontal_align
                    style_override["text_align"] = horizontal_align
                    if horizontal_align == "justify":
                        style_override["justify"] = horizontal_align
                cell_context = (
                    f"table_cell_{table_header_footer_context}"
                    if table_header_footer_context
                    else "table_cell"
                )
                if cell_content_items and self._render_cell_paragraphs(
                    c,
                    cell_content_items,
                    cell_rect,
                    cell_margins,
                    cell_context,
                    style_override or None,
                    vertical_align,
                ):
                    x += cell_width
                    col_idx += grid_span
                    cell_idx += 1
                    continue
                
                # Get text and images from cell
                # Handle TableCell objects (with get_text method) and dict
                cell_text = ""
                cell_images = []
                seen_cell_images: Dict[str, bool] = {}

                def _add_cell_image(img: Any) -> None:
                    if not img:
                        return
                    key = self._make_image_unique_key(img)
                    if key in seen_cell_images:
                        return
                    seen_cell_images[key] = True
                    cell_images.append(img)
                
                if hasattr(cell, 'get_text'):
                    # Obiekt TableCell
                    cell_text = cell.get_text()
                    # Get images from cell (TableCell inherits from Body)
                    if hasattr(cell, 'get_images'):
                        for img in cell.get_images() or []:
                            _add_cell_image(img)
                    elif hasattr(cell, 'images'):
                        for img in cell.images or []:
                            _add_cell_image(img)
                    
                    # Check content for images (paragraphs may contain images)
                    if hasattr(cell, 'content'):
                        for item in cell.content:
                            # Check if this is an image
                            if hasattr(item, 'type') and item.type == 'image':
                                _add_cell_image(item)
                            elif isinstance(item, dict) and item.get("type") == "image":
                                _add_cell_image(item)
                            # Check if this is a drawing (may contain image)
                            elif isinstance(item, dict) and item.get("type") == "drawing":
                                # Drawing may contain image - check content
                                drawing_content = item.get("content", [])
                                for drawing_item in drawing_content:
                                    if isinstance(drawing_item, dict):
                                        # Check if drawing_item has relationship_id or path
                                        if drawing_item.get("relationship_id") or drawing_item.get("path") or drawing_item.get("image_path"):
                                            # To jest obraz w drawing
                                            # If has relationship_id but no path, try to get path
                                            if drawing_item.get("relationship_id") and not drawing_item.get("path") and not drawing_item.get("image_path"):
                                                # Need to get path from relationship - for now add with relationship_id
                                                # Path should already be in drawing_item if parsed correctly
                                                logger.debug(f"Drawing item has relationship_id but no path: {drawing_item.get('relationship_id')}")
                                            _add_cell_image(drawing_item)
                            # Check if this is paragraph with images
                            # Check if this is paragraph with images
                            elif hasattr(item, 'images'):
                                if item.images:
                                    images_list = item.images if isinstance(item.images, list) else [item.images]
                                    for img in images_list:
                                        _add_cell_image(img)
                                    logger.info(f"Found {len(images_list)} images in paragraph in cell at row {row_idx}, col {col_idx}")
                            elif isinstance(item, dict) and "images" in item:
                                images = item["images"]
                                imgs = images if isinstance(images, list) else [images]
                                for img in imgs:
                                    _add_cell_image(img)
                            # Check runs in paragraph
                            elif hasattr(item, 'runs'):
                                for run in item.runs:
                                    if hasattr(run, 'images') and run.images:
                                        run_images = run.images if isinstance(run.images, list) else [run.images]
                                        for img in run_images:
                                            _add_cell_image(img)
                                    elif isinstance(run, dict) and "images" in run:
                                        images = run["images"]
                                        imgs = images if isinstance(images, list) else [images]
                                        for img in imgs:
                                            _add_cell_image(img)
                                    # Check if run has drawings (for Run objects)
                                    elif hasattr(run, 'drawings') and run.drawings:
                                        for drawing in run.drawings:
                                            if hasattr(drawing, 'content'):
                                                drawing_content = drawing.content if isinstance(drawing.content, list) else [drawing.content]
                                                for drawing_item in drawing_content:
                                                    if hasattr(drawing_item, 'path') or hasattr(drawing_item, 'image_path'):
                                                        _add_cell_image(drawing_item)
                                                    elif isinstance(drawing_item, dict):
                                                        if drawing_item.get("relationship_id") or drawing_item.get("path") or drawing_item.get("image_path"):
                                                            _add_cell_image(drawing_item)
                                    # Check if run has drawings (for dict)
                                    elif isinstance(run, dict) and "drawings" in run:
                                        drawings = run["drawings"]
                                        for drawing in drawings:
                                            if isinstance(drawing, dict) and drawing.get("type") == "drawing":
                                                drawing_content = drawing.get("content", [])
                                                for drawing_item in drawing_content:
                                                    if isinstance(drawing_item, dict):
                                                        if drawing_item.get("relationship_id") or drawing_item.get("path") or drawing_item.get("image_path"):
                                                            _add_cell_image(drawing_item)
                    
                    # Also check children (for Body objects)
                    if hasattr(cell, 'children'):
                        for child in cell.children:
                            if hasattr(child, 'type') and child.type == 'image':
                                _add_cell_image(child)
                            elif isinstance(child, dict) and child.get("type") == "image":
                                _add_cell_image(child)
                elif isinstance(cell, dict):
                    cell_text = str(cell.get("text", cell.get("content", "")))
                    # Check if there are images in dict
                    if "images" in cell:
                        imgs = cell["images"] if isinstance(cell["images"], list) else [cell["images"]]
                        for img in imgs:
                            _add_cell_image(img)
                    elif "content" in cell:
                        # Check content for images
                        content = cell["content"]
                        if isinstance(content, list):
                            for item in content:
                                # Check if this is an image
                                if isinstance(item, dict) and item.get("type") == "image":
                                    _add_cell_image(item)
                                elif hasattr(item, 'type') and item.type == 'image':
                                    _add_cell_image(item)
                                # Check if this is a drawing (may contain image)
                                elif isinstance(item, dict) and item.get("type") == "drawing":
                                    # Drawing may contain image - check content
                                    drawing_content = item.get("content", [])
                                    for drawing_item in drawing_content:
                                        if isinstance(drawing_item, dict):
                                            # Check if drawing_item has relationship_id or path
                                            if drawing_item.get("relationship_id") or drawing_item.get("path") or drawing_item.get("image_path"):
                                                # To jest obraz w drawing
                                                _add_cell_image(drawing_item)
                                # Check if this is paragraph with images
                                elif isinstance(item, dict) and "images" in item:
                                    images = item["images"]
                                    imgs = images if isinstance(images, list) else [images]
                                    for img in imgs:
                                        _add_cell_image(img)
                                elif hasattr(item, 'images') and item.images:
                                    images_list = item.images if isinstance(item.images, list) else [item.images]
                                    for img in images_list:
                                        _add_cell_image(img)
                                # Check if this is paragraph with runs containing drawing
                                elif isinstance(item, dict) and item.get("type") == "paragraph":
                                    # Check runs in paragraph
                                    runs = item.get("runs", [])
                                    for run in runs:
                                        if isinstance(run, dict):
                                            # Check if run has drawings
                                            drawings = run.get("drawings", [])
                                            for drawing in drawings:
                                                if isinstance(drawing, dict) and drawing.get("type") == "drawing":
                                                    # Check content in drawing
                                                    drawing_content = drawing.get("content", [])
                                                    for drawing_item in drawing_content:
                                                        if isinstance(drawing_item, dict):
                                                            # Check if drawing_item has relationship_id or path
                                                            if drawing_item.get("relationship_id") or drawing_item.get("path") or drawing_item.get("image_path"):
                                                                # To jest obraz w drawing
                                                                _add_cell_image(drawing_item)
                else:
                    cell_text = str(cell)
                
                # Debug: check what's in cell (for all cells in first rows)
                if row_idx < 5:
                    if hasattr(cell, 'content'):
                        logger.info(f"Cell (obj) at row {row_idx}, col {col_idx} has {len(cell.content)} content items")
                        for idx, item in enumerate(cell.content):
                            item_type = type(item).__name__ if hasattr(item, '__class__') else type(item)
                            has_images = hasattr(item, 'images') and item.images
                            is_dict = isinstance(item, dict)
                            item_dict_type = item.get("type") if is_dict else None
                            logger.info(f"  Content {idx}: {item_type}, is_dict: {is_dict}, dict_type: {item_dict_type}, has images attr: {has_images}")
                            if has_images:
                                logger.info(f"    Images: {item.images}")
                            if is_dict and item.get("type") == "drawing":
                                drawing_content = item.get("content", [])
                                logger.info(f"    Drawing content: {len(drawing_content)} items")
                                for d_idx, d_item in enumerate(drawing_content):
                                    if isinstance(d_item, dict):
                                        logger.info(f"      Drawing item {d_idx}: relationship_id={d_item.get('relationship_id')}, path={d_item.get('path')}")
                    elif isinstance(cell, dict):
                        cell_content = cell.get("content", [])
                        logger.info(f"Cell (dict) at row {row_idx}, col {col_idx} has {len(cell_content)} content items")
                        for idx, item in enumerate(cell_content):
                            is_dict = isinstance(item, dict)
                            item_dict_type = item.get("type") if is_dict else None
                            logger.info(f"  Content {idx}: is_dict: {is_dict}, dict_type: {item_dict_type}")
                            if is_dict and item.get("type") == "drawing":
                                drawing_content = item.get("content", [])
                                logger.info(f"    Drawing content: {len(drawing_content)} items")
                                for d_idx, d_item in enumerate(drawing_content):
                                    if isinstance(d_item, dict):
                                        logger.info(f"      Drawing item {d_idx}: relationship_id={d_item.get('relationship_id')}, path={d_item.get('path')}")
                
                # Debug: check if images were found
                if cell_images:
                    logger.info(f"Found {len(cell_images)} images in cell at row {row_idx}, col {col_idx}")
                elif row_idx < 5:
                    logger.info(f"No images found in cell at row {row_idx}, col {col_idx}, cell_images={len(cell_images)}")
                
                # Render images in cell (before text)
                if cell_images:
                    logger.info(f"Found {len(cell_images)} images in cell at row {row_idx}, col {col_idx}")
                    cell_margins = self._parse_cell_margins(cell, default_margin=cell_padding)
                    for img in cell_images:
                        try:
                            # Get image path
                            img_path = self._resolve_image_path(img)
                            
                            if not img_path:
                                logger.debug(f"Image in cell could not be resolved: {img}")
                                continue
                            
                            # Pobierz wymiary obrazu
                            img_width = None
                            img_height = None
                            if isinstance(img, dict):
                                img_width = img.get("width")
                                img_height = img.get("height")
                            elif hasattr(img, 'width'):
                                img_width = img.width
                            elif hasattr(img, 'height'):
                                img_height = img.height
                            
                            # Calculate available area for image (with margins)
                            available_width = cell_rect.width - cell_margins["left"] - cell_margins["right"]
                            available_height = cell_rect.height - cell_margins["top"] - cell_margins["bottom"]
                            
                            # If no dimensions, use available area
                            if img_width is None or img_height is None:
                                render_width = available_width
                                render_height = available_height
                            else:
                                # Convert from EMU to points if needed
                                from ..geometry import emu_to_points
                                if img_width > 10000:  # Prawdopodobnie EMU
                                    img_width = emu_to_points(img_width)
                                if img_height > 10000:  # Prawdopodobnie EMU
                                    img_height = emu_to_points(img_height)
                                
                                # Scale image to available area preserving aspect ratio
                                scale_w = available_width / img_width if img_width > 0 else 1.0
                                scale_h = available_height / img_height if img_height > 0 else 1.0
                                scale = min(scale_w, scale_h, 1.0)  # Don't enlarge
                                
                                render_width = img_width * scale
                                render_height = img_height * scale
                            
                            logger.info(
                                f"Rendering image in cell: {img_path}, width={render_width}, height={render_height}"
                            )

                            # Image position (aligned to top edge)
                            img_x = cell_rect.x + cell_margins["left"]
                            img_y = cell_rect.y + cell_rect.height - cell_margins["top"] - render_height
                            min_y = cell_rect.y + cell_margins["bottom"]
                            if img_y < min_y:
                                img_y = min_y
                            
                            # Renderuj obraz
                            c.drawImage(
                                img_path,
                                img_x,
                                img_y,
                                width=render_width,
                                height=render_height,
                                preserveAspectRatio=True,
                                mask="auto"
                            )
                        except Exception as e:
                            logger.debug(f"Błąd renderowania obrazu w komórce: {e}")
                
                # Render text in cell
                if cell_text:
                    # Get cell margins
                    cell_margins = self._parse_cell_margins(cell, default_margin=cell_padding)
                    
                    c.setFont(font_name, font_size)
                    c.setFillColor(black)
                    # Text position accounting for margins
                    # For vertical merge, text should be vertically centered
                    text_x = x + cell_margins["left"]
                    if cell_rowspan > 1:
                        # Center text vertically for cells with rowspan
                        text_y = y - cell_height + cell_margins["bottom"] + (cell_height - cell_margins["top"] - cell_margins["bottom"]) / 2
                    else:
                        text_y = y - cell_height + cell_margins["bottom"]
                    
                    # Use TextMetricsEngine for proper text wrapping in cell
                    try:
                        # Ensure cell_style is dict
                        if not isinstance(cell_style, dict):
                            cell_style = {}
                        # Use style from cell or table style as fallback
                        cell_text_style = {**style, **cell_style}
                        # Available width = cell width - left and right margins
                        text_width = cell_rect.width - cell_margins["left"] - cell_margins["right"]
                        text_layout: TextLayout = self.metrics.layout_text(cell_text, cell_text_style, text_width)
                        
                        # Render each text line
                        line_y = text_y
                        for line in text_layout.lines:
                            if line_y < cell_rect.y:  # Don't render outside cell
                                break
                            c.drawString(text_x, line_y, line.text)
                            line_y -= text_layout.line_height
                    except Exception as e:
                        logger.debug(f"Błąd layoutowania tekstu w komórce: {e}, używam prostego drawString")
                        # Fallback: simple drawString (but without length limit)
                        # Split text into lines if too long
                        max_width = cell_rect.width - cell_margins["left"] - cell_margins["right"]
                        words = cell_text.split()
                        line_text = ""
                        line_y = text_y
                        for word in words:
                            test_line = line_text + (" " if line_text else "") + word
                            test_width = c.stringWidth(test_line, font_name, font_size)
                            if test_width > max_width and line_text:
                                c.drawString(text_x, line_y, line_text)
                                line_y -= font_size * 1.2
                                line_text = word
                                if line_y < cell_rect.y:
                                    break
                            else:
                                line_text = test_line
                        if line_text and line_y >= cell_rect.y:
                            c.drawString(text_x, line_y, line_text)
                
                x += cell_width
                col_idx += grid_span
                cell_idx += 1
            
            y -= row_heights[row_idx]
    
    def _draw_image(self, c: canvas.Canvas, block: LayoutBlock, timings: Optional[Dict[str, List[float]]] = None) -> None:
        """

        Renders image.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of type "image"
        timings: Optional dictionary for collecting operation times

        """
        import time
        
        rect = block.frame
        t0 = time.time()
        content_value, _ = self._resolve_content(block.content)
        content = content_value if isinstance(content_value, dict) else {}
        if timings is not None:
            if 'image_resolve_content' not in timings:
                timings['image_resolve_content'] = []
            timings['image_resolve_content'].append(time.time() - t0)
        
        # Get path to image (WMF/EMF handling)
        t0 = time.time()
        path = self._resolve_image_path(content)
        if timings is not None:
            if 'image_resolve_path' not in timings:
                timings['image_resolve_path'] = []
            timings['image_resolve_path'].append(time.time() - t0)
        
        if not path:
            rel_id_display = content.get("relationship_id") or content.get("rel_id") or "?"
            logger.debug(f"Image has no resolvable path, relationship_id: {rel_id_display}")
            c.setStrokeColor(Color(0.6, 0.6, 0.6))
            c.setLineWidth(1.0)
            c.rect(rect.x, rect.y, rect.width, rect.height)
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(rect.x + 5, rect.y + rect.height / 2, f"[Image: {rel_id_display}]")
            return
        
        try:
            # Renderuj obraz
            t0 = time.time()
            c.drawImage(
                path,
                rect.x,
                rect.y,
                width=rect.width,
                height=rect.height,
                preserveAspectRatio=True,
                mask="auto"
            )
            if timings is not None:
                if 'image_draw' not in timings:
                    timings['image_draw'] = []
                timings['image_draw'].append(time.time() - t0)
        except Exception as e:
            logger.warning(f"Błąd renderowania obrazu {path}: {e}")
            # Placeholder in case of error
            c.setStrokeColor(Color(0.8, 0.2, 0.2))
            c.setLineWidth(1.0)
            c.rect(rect.x, rect.y, rect.width, rect.height)
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(rect.x + 5, rect.y + rect.height / 2, f"[Image Error: {e}]")
    
    def _draw_watermark(self, c: canvas.Canvas, block: LayoutBlock, page_width: float, page_height: float) -> None:
        """

        Renders watermark on page.
        Watermarks can be text (textbox) or image, rendered as transparent in center of page with rotation.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of type "textbox" or "image" with absolute positioning in header
        page_width: Page width in points
        page_height: Page height in points

        """
        content_value, _ = self._resolve_content(block.content)
        content = content_value if isinstance(content_value, dict) else {}
        style = block.style or {}
        if not isinstance(style, dict):
            style = {}
        
        scale_factor = 1.5

        # Check watermark type (image, textbox or vml_shape)
        watermark_type = content.get("type", block.block_type or "textbox")
        watermark_data = content.get("content", content)
        
        # If watermark is VML shape (text watermark)
        if watermark_type == "vml_shape" or (isinstance(watermark_data, dict) and watermark_data.get("type") == "vml_shape"):
            # Renderuj VML shape jako tekstowy watermark
            vml_data = watermark_data if isinstance(watermark_data, dict) else {}
            text = vml_data.get("text_content", "")
            if not text:
                logger.warning(f"VML shape watermark has no text content")
                return
            
            # Get properties from VML shape
            properties = vml_data.get("properties", {})
            # Use exactly the font that's in VML - don't modify name
            # In VML watermarks, font weight is encoded in path geometry (outline)
            # Word converts text to vector path that already has encoded weight
            # If font-family contains Bold/SemiBold variant, it will be used, if not - we use normal
            font_name = properties.get("font_name", "Helvetica")
            if not font_name:
                font_name = "Helvetica"
            
            # In VML watermarks font-size from textpath is only symbolic value (usually 1pt)
            # Actual size comes from v:shape dimensions (width and height)
            # Calculate actual font size based on shape dimensions
            shape_width = properties.get("shape_width") or vml_data.get("size", {}).get("width")
            shape_height = properties.get("shape_height") or vml_data.get("size", {}).get("height")
            
            # If no shape dimensions, use default values
            if not shape_width or not shape_height:
                # Default dimensions for watermark (about 400x100 pt)
                shape_width = 400.0
                shape_height = 100.0
                logger.warning(f"VML shape has no dimensions, using defaults: {shape_width}x{shape_height}pt")
            else:
                shape_width = float(shape_width)
                shape_height = float(shape_height)

            shape_width *= scale_factor
            shape_height *= scale_factor
            
            # Calculate actual font size based on shape dimensions
            # In VML watermarks Word scales text to fill shape with dimensions width x height
            # Strategy: use font_size = height (109.05pt), then scale ONLY width to width
            # Height remains unchanged (109.05pt)
            font_size = shape_height
            
            # Get color from fillcolor or default
            fillcolor = properties.get("fillcolor", "silver")
            # Convert color names to hex
            color_map = {
                "silver": "#C0C0C0",
                "gray": "#808080",
                "grey": "#808080",
                "black": "#000000",
                "white": "#FFFFFF",
            }
            color = color_map.get(fillcolor.lower(), fillcolor)
            if isinstance(color, str) and not color.startswith("#"):
                color = f"#{color}"
            
            # Get rotation from properties or default
            # Rotation may already be converted to range -180 to 180
            # In VML rotation:315 means 315° clockwise
            # In ReportLab, rotate() takes angle where positive = counter-clockwise
            # So we need to flip sign so watermark tilts to the right
            rotation_raw = float(properties.get("rotation", -45.0))
            rotation = -rotation_raw  # Flip sign so watermark tilts to the right
            
            # Default transparency can be overridden globally or per watermark
            opacity = self._resolve_watermark_opacity(block, vml_data, default=0.3)
            
            # Parse color
            from reportlab.lib import colors
            try:
                if color.startswith('#'):
                    rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
                    watermark_color = colors.Color(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0, alpha=opacity)
                else:
                    watermark_color = colors.Color(0.8, 0.8, 0.8, alpha=opacity)
            except Exception:
                watermark_color = colors.Color(0.8, 0.8, 0.8, alpha=opacity)
            
            # Renderuj watermark
            c.saveState()
            try:
                self._apply_canvas_opacity(c, opacity)
                c.setFillColor(watermark_color)
                c.setStrokeColor(watermark_color)
                
                # Position - center of page
                center_x = page_width / 2
                center_y = page_height / 2
                
                # Translate to center and rotate
                c.translate(center_x, center_y)
                c.rotate(rotation)
                
                # Set font - try different font name variants
                actual_font_name = font_name
                font_variants = [
                    font_name,
                    font_name.replace(' ', ''),
                    font_name.replace('-Bold', 'Bold'),
                ]
                
                for variant in font_variants:
                    try:
                        c.setFont(variant, font_size)
                        actual_font_name = variant
                        break
                    except Exception:
                        continue
                else:
                    # Fallback to Helvetica if no variant worked
                    c.setFont('Helvetica', font_size)
                    actual_font_name = 'Helvetica'
                
                # Measure actual text width and scale only width
                try:
                    actual_text_width = c.stringWidth(text, actual_font_name, font_size)
                    target_width = shape_width * 0.9
                    width_scale_factor = target_width / actual_text_width if actual_text_width > 0 else 1.0
                    width_scale_factor = max(0.5, min(2.0, width_scale_factor))
                    c.scale(width_scale_factor, 1.0)
                    text_width = actual_text_width
                except Exception as e:
                    logger.warning(f"Failed to measure text width: {e}, using estimated width without scaling")
                    text_width = len(text) * font_size * 0.6
                
                # Draw text centered
                c.drawString(-text_width / 2, -font_size / 2, text)
                
            finally:
                c.restoreState()
            return

        # If watermark is an image
        if watermark_type == "image" or watermark_type == "Image" or isinstance(watermark_data, dict) and (watermark_data.get("path") or watermark_data.get("image_path") or watermark_data.get("relationship_id")):
            # Renderuj obraz jako watermark
            image_data = watermark_data if isinstance(watermark_data, dict) else {}
            
            # Get image path (use _resolve_image_path to convert WMF/EMF to PNG)
            img_path = self._resolve_image_path(image_data)
            if not img_path:
                # Fallback: use direct path
                img_path = image_data.get("path") or image_data.get("image_path")
            
            if not img_path:
                logger.debug(f"Watermark image has no path. image_data={image_data}")
                return
            
            # Pobierz wymiary obrazu
            from ..geometry import emu_to_points
            img_width = image_data.get("width", 0)
            img_height = image_data.get("height", 0)
            
            # Convert from EMU to points if needed
            if img_width > 10000:
                img_width = emu_to_points(img_width)
            if img_height > 10000:
                img_height = emu_to_points(img_height)
            
            # If no dimensions, use defaults
            if img_width <= 0 or img_height <= 0:
                img_width = page_width * 0.8
                img_height = img_width * 0.3  # Zachowaj proporcje

            img_width *= scale_factor
            img_height *= scale_factor
            
            # Default values for watermarks
            angle = 45.0  # Rotation angle (diagonally)
            opacity = self._resolve_watermark_opacity(block, image_data, default=0.5)
            
            # Check if anchor_info has position information
            anchor_info = content.get("anchor_info") or {}
            position = anchor_info.get("position", {})
            
            # Position - center of page
            center_x = page_width / 2
            center_y = page_height / 2
            
            # If image has positioning, use it
            if position:
                x_rel = position.get("x_rel") or position.get("relativeFrom_h", "page")
                y_rel = position.get("y_rel") or position.get("relativeFrom_v", "page")
                
                from ..geometry import twips_to_points
                
                x_offset = position.get("x", 0)
                y_offset = position.get("y", 0)
                
                # Convert if EMU (usually > 10000)
                if x_offset > 10000:
                    x_offset = emu_to_points(x_offset)
                elif x_offset > 100:
                    x_offset = twips_to_points(x_offset)
                
                if y_offset > 10000:
                    y_offset = emu_to_points(y_offset)
                elif y_offset > 100:
                    y_offset = twips_to_points(y_offset)
                
                # Calculate position depending on relativeFrom
                if x_rel == "page":
                    center_x = x_offset
                elif x_rel == "margin":
                    center_x = self.page_config.base_margins.left + x_offset if hasattr(self, 'page_config') else x_offset
                else:
                    center_x = page_width / 2 + x_offset
                
                if y_rel == "page":
                    center_y = page_height - y_offset  # PDF coordinates: Y=0 na dole
                elif y_rel == "margin":
                    center_y = page_height - (self.page_config.base_margins.top + y_offset) if hasattr(self, 'page_config') else page_height - y_offset
                else:
                    center_y = page_height / 2 - y_offset
            
            # Renderuj obraz jako watermark
            c.saveState()
            try:
                self._apply_canvas_opacity(c, opacity)
                # Set transparency
                from reportlab.lib import colors
                watermark_color = colors.Color(1.0, 1.0, 1.0, alpha=opacity)
                c.setFillColor(watermark_color)
                
                # Translate to center and rotate
                c.translate(center_x, center_y)
                c.rotate(angle)
                
                # Draw image centered
                try:
                    from reportlab.lib.utils import ImageReader
                    img_reader = ImageReader(img_path)
                    c.drawImage(img_reader, -img_width / 2, -img_height / 2, width=img_width, height=img_height, mask='auto', preserveAspectRatio=True)
                except Exception as e:
                    logger.warning(f"Błąd podczas renderowania watermark image: {e}")
            finally:
                c.restoreState()
            return
        
        # If watermark is textbox (text)
        # Pobierz tekst z content
        text = ""
        # Check if content contains textbox data
        textbox_data = content.get("content")
        if isinstance(textbox_data, dict):
            # To jest textbox dict z layout_engine
            text = textbox_data.get("text", "")
            # If no text, check content in textbox_data
            if not text:
                textbox_content = textbox_data.get("content")
                if isinstance(textbox_content, list):
                    # Content to lista runs
                    text_parts = []
                    for run in textbox_content:
                        if isinstance(run, dict):
                            run_text = run.get("text", "")
                            if run_text:
                                text_parts.append(run_text)
                        elif hasattr(run, "text"):
                            run_text = getattr(run, "text", "")
                            if run_text:
                                text_parts.append(run_text)
                        elif hasattr(run, "get_text"):
                            run_text = run.get_text()
                            if run_text:
                                text_parts.append(run_text)
                    text = " ".join(text_parts)
                elif isinstance(textbox_content, str):
                    text = textbox_content
        
        if isinstance(content_value, dict):
            # Try to get text from different places
            if not text:
                text = (content.get("content") or content.get("text") or "")
            
            # If no text directly, check runs
            if not text:
                runs = content.get("runs") or content.get("runs_payload") or []
                if isinstance(runs, list):
                    text_parts = []
                    for run in runs:
                        if isinstance(run, dict):
                            run_text = run.get("text", "")
                            if run_text:
                                text_parts.append(run_text)
                        elif hasattr(run, "text"):
                            run_text = getattr(run, "text", "")
                            if run_text:
                                text_parts.append(run_text)
                    text = " ".join(text_parts)
        elif isinstance(content_value, str):
            text = content_value
        
        if not text:
            logger.debug(f"Watermark block has no text content. content_value={type(content_value)}, content={content}")
            return
        
        # Get watermark properties from style
        font_size = float(style.get("font_size", 72.0))
        # Convert from half-points if needed
        if font_size > 100:
            font_size = font_size / 2.0

        font_size *= scale_factor
        
        font_name = style.get("font_name", "Helvetica-Bold")
        if not font_name:
            font_name = "Helvetica-Bold"
        
        color = style.get("color", "#CCCCCC")
        if isinstance(color, str) and not color.startswith("#"):
            color = f"#{color}"
        
        # Default values for watermarks
        angle = 45.0  # Rotation angle (diagonally)
        opacity = self._resolve_watermark_opacity(block, content, default=0.5)
        
        # Check if anchor_info has position and rotation information
        anchor_info = content.get("anchor_info") or {}
        position = anchor_info.get("position", {})
        
        # Parse color
        from reportlab.lib import colors
        try:
            if color.startswith('#'):
                rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
                watermark_color = colors.Color(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0, alpha=opacity)
            else:
                watermark_color = colors.Color(0.8, 0.8, 0.8, alpha=opacity)
        except Exception:
            watermark_color = colors.Color(0.8, 0.8, 0.8, alpha=opacity)
        
        # Renderuj watermark
        c.saveState()
        try:
            self._apply_canvas_opacity(c, opacity)
            c.setFillColor(watermark_color)
            c.setStrokeColor(watermark_color)
            
            # Position - center of page
            center_x = page_width / 2
            center_y = page_height / 2
            
            # If textbox has positioning, use it
            if position:
                x_rel = position.get("x_rel") or position.get("relativeFrom_h", "page")
                y_rel = position.get("y_rel") or position.get("relativeFrom_v", "page")
                
                # Convert EMU to points if needed
                from ..geometry import emu_to_points, twips_to_points
                
                x_offset = position.get("x", 0)
                y_offset = position.get("y", 0)
                
                # Convert if EMU (usually > 10000)
                if x_offset > 10000:
                    x_offset = emu_to_points(x_offset)
                elif x_offset > 100:
                    x_offset = twips_to_points(x_offset)
                
                if y_offset > 10000:
                    y_offset = emu_to_points(y_offset)
                elif y_offset > 100:
                    y_offset = twips_to_points(y_offset)
                
                # Calculate position depending on relativeFrom
                if x_rel == "page":
                    center_x = x_offset
                elif x_rel == "margin":
                    center_x = self.page_config.base_margins.left + x_offset if hasattr(self, 'page_config') else x_offset
                else:
                    center_x = page_width / 2 + x_offset
                
                if y_rel == "page":
                    center_y = page_height - y_offset  # PDF coordinates: Y=0 na dole
                elif y_rel == "margin":
                    center_y = page_height - (self.page_config.base_margins.top + y_offset) if hasattr(self, 'page_config') else page_height - y_offset
                else:
                    center_y = page_height / 2 - y_offset
            
            # Translate to center and rotate
            c.translate(center_x, center_y)
            c.rotate(angle)
            
            # Set font
            try:
                # Try to use font, if doesn't exist use Helvetica-Bold
                c.setFont(font_name, font_size)
            except Exception:
                c.setFont('Helvetica-Bold', font_size)
            
            # Calculate text width for centering
            try:
                text_width = c.stringWidth(text, font_name, font_size)
            except Exception:
                text_width = len(text) * font_size * 0.6
            
            # Draw text centered
            c.drawString(-text_width / 2, -font_size / 2, text)
            
        finally:
            c.restoreState()
    
    def _resolve_watermark_opacity(self, block, content_value, default: float) -> float:
        """
        Determine watermark opacity from override, content hints or default.
        """
        if self.watermark_opacity_override is not None:
            return self.watermark_opacity_override

        explicit = self._extract_watermark_opacity_hint(content_value, include_generic=True)
        if explicit is None and hasattr(block, "style") and isinstance(block.style, dict):
            explicit = self._extract_watermark_opacity_hint(block.style, include_generic=False)

        if explicit is not None:
            return explicit

        return default

    def _extract_watermark_opacity_hint(self, value, *, include_generic: bool = True) -> Optional[float]:
        """
        Recursively search for watermark opacity hint inside nested structures.
        """
        try_keys = ("watermark_opacity", "opacity") if include_generic else ("watermark_opacity",)
        if isinstance(value, dict):
            for key in try_keys:
                if key in value:
                    try:
                        normalized = self._normalize_opacity_value(value[key])
                        if normalized is not None:
                            return normalized
                    except Exception:
                        continue
            for child in value.values():
                result = self._extract_watermark_opacity_hint(child, include_generic=include_generic)
                if result is not None:
                    return result
        elif isinstance(value, (list, tuple)):
            for item in value:
                result = self._extract_watermark_opacity_hint(item, include_generic=include_generic)
                if result is not None:
                    return result
        return None

    def _apply_canvas_opacity(self, canvas_obj, opacity: float) -> None:
        """
        Apply opacity to canvas if backend exposes setOpacity (Rust).
        """
        if opacity is None:
            return
        setter = getattr(canvas_obj, "setOpacity", None)
        if callable(setter):
            try:
                setter(opacity)
            except Exception:
                logger.debug("Failed to set canvas opacity via Rust canvas", exc_info=True)

    def _draw_textbox(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """

        Renders TextBox as rectangle with text.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of type "textbox"

        """
        rect = block.frame
        content_value, _ = self._resolve_content(block.content)
        content = content_value if isinstance(content_value, dict) else {}
        style = block.style or {}
        if not isinstance(style, dict):
            style = {}
        
        # Renderuj background i border
        try:
            draw_background(c, rect, style)
            draw_border(c, rect, style)
        except Exception as e:
            logger.debug(f"Błąd renderowania background/border textbox: {e}")
            # Fallback: prosty rect
            c.setStrokeColor(Color(0.6, 0.6, 0.6))
            c.setLineWidth(0.5)
            c.rect(rect.x, rect.y, rect.width, rect.height)
        
        # Pobierz tekst
        text = content.get("content") or content.get("text", "")
        if not text:
            return
        
        # Renderuj tekst
        font_name = style.get("font_name", "Helvetica")
        font_size = float(style.get("font_size", 10))
        c.setFont(font_name, font_size)
        c.setFillColor(black)
        c.drawString(rect.x + 5, rect.y + rect.height - 15, str(text)[:100])  # Limit length
    
    def _draw_header(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """

        Renders header - similar to paragraph with borders and background, supports images.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of type "header"

        """
        style = block.style or {}
        if not isinstance(style, dict):
            style = {}
        rect = block.frame
        
        # Renderuj background i border przed tekstem
        try:
            draw_background(c, rect, style)
            draw_border(c, rect, style)
        except Exception as e:
            logger.debug(f"Błąd renderowania background/border header: {e}")
        
        # Get content - may contain text and images
        content_value, _payload = self._resolve_content(block.content)
        images = []
        text = ""
        
        if isinstance(content_value, dict):
            text = content_value.get("text", content_value.get("content", ""))
            images = content_value.get("images", [])
        elif isinstance(content_value, str):
            text = content_value
        elif content_value is None:
            text = ""
        else:
            text = str(content_value) if isinstance(content_value, (int, float)) else ""
        
        # Render images if present
        if images:
            x = rect.x
            y = rect.y + rect.height / 2  # Vertical centering
            for img in images:
                img_width = None
                img_height = None
                img_path = self._resolve_image_path(img)
                if not img_path:
                    logger.debug(f"Header image could not be resolved: {img}")
                    continue
                
                # Pobierz wymiary obrazu
                if hasattr(img, "width") and hasattr(img, "height"):
                    img_width = img.width
                    img_height = img.height
                elif isinstance(img, dict):
                    img_width = img.get("width")
                    img_height = img.get("height")
                
                if img_path:
                    # Renderuj obraz
                    try:
                        # If no dimensions, use defaults
                        if img_width is None or img_height is None:
                            calc_width = rect.width / len(images) if len(images) > 1 else rect.width
                            calc_height = min(rect.height, calc_width * 0.3)  # Zachowaj proporcje
                        else:
                            # Konwertuj EMU na punkty (1 EMU = 1/914400 cala, 1 cal = 72 punkty)
                            calc_width = (img_width / 914400.0) * 72
                            calc_height = (img_height / 914400.0) * 72
                            # Adjust to available space
                            if calc_width > rect.width:
                                scale = rect.width / calc_width
                                calc_width = rect.width
                                calc_height *= scale
                            if calc_height > rect.height:
                                scale = rect.height / calc_height
                                calc_height = rect.height
                                calc_width *= scale
                        
                        c.drawImage(
                            img_path,
                            x,
                            y - calc_height / 2,
                            width=calc_width,
                            height=calc_height,
                            preserveAspectRatio=True,
                            mask="auto"
                        )
                        x += calc_width + 5  # Add spacing between images
                    except Exception as e:
                        logger.warning(f"Błąd renderowania obrazu w header: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
        
        # Render text if present
        if text:
            # Renderuj tekst jak paragraph
            self._draw_paragraph(c, block)
    
    def _draw_footer(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """

        Renders footer - similar to paragraph with borders and background, supports images.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of type "footer"

        """
        style = block.style or {}
        if not isinstance(style, dict):
            style = {}
        rect = block.frame
        
        # Renderuj background i border przed tekstem
        try:
            draw_background(c, rect, style)
            draw_border(c, rect, style)
        except Exception as e:
            logger.debug(f"Błąd renderowania background/border footer: {e}")
        
        # Get content - may contain text and images
        content_value, _payload = self._resolve_content(block.content)
        images = []
        text = ""
        
        if isinstance(content_value, dict):
            text = content_value.get("text", content_value.get("content", ""))
            images = content_value.get("images", [])
        elif isinstance(content_value, str):
            text = content_value
        elif content_value is None:
            text = ""
        else:
            text = str(content_value) if isinstance(content_value, (int, float)) else ""
        
        # Render images if present
        if images:
            x = rect.x
            y = rect.y + rect.height / 2  # Vertical centering
            for img in images:
                img_width = None
                img_height = None
                img_path = self._resolve_image_path(img)
                if not img_path:
                    logger.debug(f"Footer image could not be resolved: {img}")
                    continue
                
                # Pobierz wymiary obrazu
                if hasattr(img, "width") and hasattr(img, "height"):
                    img_width = img.width
                    img_height = img.height
                elif isinstance(img, dict):
                    img_width = img.get("width")
                    img_height = img.get("height")
                
                if img_path:
                    # Renderuj obraz
                    try:
                        # If no dimensions, use defaults
                        if img_width is None or img_height is None:
                            calc_width = rect.width / len(images) if len(images) > 1 else rect.width
                            calc_height = min(rect.height, calc_width * 0.3)  # Zachowaj proporcje
                        else:
                            # Konwertuj EMU na punkty (1 EMU = 1/914400 cala, 1 cal = 72 punkty)
                            calc_width = (img_width / 914400.0) * 72
                            calc_height = (img_height / 914400.0) * 72
                            # Adjust to available space
                            if calc_width > rect.width:
                                scale = rect.width / calc_width
                                calc_width = rect.width
                                calc_height *= scale
                            if calc_height > rect.height:
                                scale = rect.height / calc_height
                                calc_height = rect.height
                                calc_width *= scale
                        
                        c.drawImage(
                            img_path,
                            x,
                            y - calc_height / 2,
                            width=calc_width,
                            height=calc_height,
                            preserveAspectRatio=True,
                            mask="auto"
                        )
                        x += calc_width + 5  # Add spacing between images
                    except Exception as e:
                        logger.warning(f"Błąd renderowania obrazu w footer: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
        
        # Render text if present
        if text:
            # Renderuj tekst jak paragraph
            self._draw_paragraph(c, block)
    
    def _draw_footnotes(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """

        Renders footnotes block with numbers and content.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of type "footnotes"

        """
        rect = block.frame
        content_value, _ = self._resolve_content(block.content)
        content = content_value if isinstance(content_value, dict) else {}
        
        footnotes = content.get('footnotes', [])
        if not footnotes:
            return
        
        # Ustaw font dla footnotes
        font_name = "DejaVuSans"
        font_size = 9.0  # Mniejszy font dla footnotes
        c.setFont(font_name, font_size)
        c.setFillColor(black)
        
        # Renderuj separator line (kreska) nad footnotes
        # Separator is 40% of body width and aligned to left
        separator_y = rect.y + rect.height - 4.0  # 4pt from top of block (in PDF coordinates, Y=0 at bottom)
        separator_width = rect.width * 0.4  # 40% of body width
        separator_x = rect.x  # Aligned to left
        
        c.saveState()
        try:
            c.setStrokeColor(black)
            c.setLineWidth(0.5)  # Cienka linia
            c.line(separator_x, separator_y, separator_x + separator_width, separator_y)
        finally:
            c.restoreState()
        
        # Starting position for text (from bottom of page in PDF coordinates)
        # Leave 4pt spacing under separator line
        y = separator_y - 4.0 - font_size  # Start from separator line with spacing
        x_start = rect.x
        line_height = font_size * 1.2
        # max_width will be calculated dynamically for each footnote (index width + spacing)
        
        for footnote in footnotes:
            if y < rect.y:
                # No space for more footnotes
                break
            
            footnote_number = footnote.get('number', '?')
            footnote_content = footnote.get('content', '')
            
            # Render footnote number as superscript (same as in main text)
            # Superscript: smaller font (58% size) and higher (33% baseline shift)
            ref_font_size = font_size * 0.58  # Standardowy rozmiar superscript
            superscript_baseline_shift = font_size * 0.33  # Standardowy baseline shift dla superscript
            
            c.saveState()
            try:
                c.setFont(font_name, ref_font_size)
                c.setFillColor(black)
                number_text = str(footnote_number)
                number_y = y + superscript_baseline_shift  # Higher than baseline
                c.drawString(x_start, number_y, number_text)
                number_width = c.stringWidth(number_text, font_name, ref_font_size)
            finally:
                c.restoreState()
            
            # Render footnote content
            # Leave spacing after index (2pt) and start from there
            text_x = x_start + number_width + 2  # 2pt spacing after index
            current_y = y
            
            # Calculate available width for content (from text_x to right edge)
            max_width = rect.x + rect.width - text_x
            
            # Wrap text if needed
            if isinstance(footnote_content, str):
                # Use TextMetricsEngine for text wrapping
                try:
                    from ..text_metrics import TextMetricsEngine
                    metrics = TextMetricsEngine()
                    wrapped_lines = metrics.wrap_text(
                        footnote_content,
                        max_width,
                        font_name,
                        font_size
                    )
                    
                    for line in wrapped_lines:
                        if current_y < rect.y:
                            break
                        c.drawString(text_x, current_y, line)
                        current_y -= line_height
                except Exception:
                    # Fallback: simple wrap using stringWidth
                    words = footnote_content.split()
                    current_line = ""
                    for word in words:
                        test_line = current_line + (" " if current_line else "") + word
                        test_width = c.stringWidth(test_line, font_name, font_size)
                        if test_width > max_width and current_line:
                            c.drawString(text_x, current_y, current_line)
                            current_y -= line_height
                            current_line = word
                            if current_y < rect.y:
                                break
                        else:
                            current_line = test_line
                    if current_line and current_y >= rect.y:
                        c.drawString(text_x, current_y, current_line)
                        current_y -= line_height
            else:
                # If content is not string, try to convert
                content_str = str(footnote_content)
                # Wrap long text
                words = content_str.split()
                current_line = ""
                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    test_width = c.stringWidth(test_line, font_name, font_size)
                    if test_width > max_width and current_line:
                        c.drawString(text_x, current_y, current_line)
                        current_y -= line_height
                        current_line = word
                        if current_y < rect.y:
                            break
                    else:
                        current_line = test_line
                if current_line and current_y >= rect.y:
                    c.drawString(text_x, current_y, current_line)
                    current_y -= line_height
            
            # Move to next footnote
            y = current_y - line_height * 0.5  # Add spacing between footnotes
    
    def _draw_endnotes(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """

        Renders endnotes block with numbers and content.
        Looks exactly the same as footnotes.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of type "endnotes"

        """
        rect = block.frame
        content_value, _ = self._resolve_content(block.content)
        content = content_value if isinstance(content_value, dict) else {}
        
        endnotes = content.get('endnotes', [])
        if not endnotes:
            return
        
        # Ustaw font dla endnotes (tak samo jak footnotes)
        font_name = "DejaVuSans"
        font_size = 9.0  # Mniejszy font dla endnotes (jak footnotes)
        c.setFont(font_name, font_size)
        c.setFillColor(black)
        
        # Renderuj separator line (kreska) nad endnotes (tak samo jak footnotes)
        # Separator is 40% of body width and aligned to left
        separator_y = rect.y + rect.height - 4.0  # 4pt from top of block (in PDF coordinates, Y=0 at bottom)
        separator_width = rect.width * 0.4  # 40% of body width
        separator_x = rect.x  # Aligned to left
        
        c.saveState()
        try:
            c.setStrokeColor(black)
            c.setLineWidth(0.5)  # Cienka linia
            c.line(separator_x, separator_y, separator_x + separator_width, separator_y)
        finally:
            c.restoreState()
        
        # Starting position for text (from bottom of page in PDF coordinates)
        # Leave 4pt spacing under separator line
        y = separator_y - 4.0 - font_size  # Start from separator line with spacing
        x_start = rect.x
        line_height = font_size * 1.2
        # max_width will be calculated dynamically for each endnote (index width + spacing)
        
        for endnote in endnotes:
            if y < rect.y:
                # No space for more endnotes
                break
            
            endnote_number = endnote.get('number', '?')
            endnote_content = endnote.get('content', '')
            
            # Render endnote number as superscript (same as in main text and footnotes)
            # Superscript: smaller font (58% size) and higher (33% baseline shift)
            ref_font_size = font_size * 0.58  # Standardowy rozmiar superscript
            superscript_baseline_shift = font_size * 0.33  # Standardowy baseline shift dla superscript
            
            c.saveState()
            try:
                c.setFont(font_name, ref_font_size)
                c.setFillColor(black)
                number_text = str(endnote_number)
                number_y = y + superscript_baseline_shift  # Higher than baseline
                c.drawString(x_start, number_y, number_text)
                number_width = c.stringWidth(number_text, font_name, ref_font_size)
            finally:
                c.restoreState()
            
            # Render endnote content
            # Leave spacing after index (2pt) and start from there
            text_x = x_start + number_width + 2  # 2pt spacing after index
            current_y = y
            
            # Calculate available width for content (from text_x to right edge)
            max_width = rect.x + rect.width - text_x
            
            # Wrap text if needed (same as footnotes)
            if isinstance(endnote_content, str):
                # Use TextMetricsEngine for text wrapping
                try:
                    from ..text_metrics import TextMetricsEngine
                    metrics = TextMetricsEngine()
                    wrapped_lines = metrics.wrap_text(
                        endnote_content,
                        max_width,
                        font_name,
                        font_size
                    )
                    
                    for line in wrapped_lines:
                        if current_y < rect.y:
                            break
                        c.drawString(text_x, current_y, line)
                        current_y -= line_height
                except Exception:
                    # Fallback: simple wrap using stringWidth
                    words = endnote_content.split()
                    current_line = ""
                    for word in words:
                        test_line = current_line + (" " if current_line else "") + word
                        test_width = c.stringWidth(test_line, font_name, font_size)
                        if test_width > max_width and current_line:
                            c.drawString(text_x, current_y, current_line)
                            current_y -= line_height
                            current_line = word
                            if current_y < rect.y:
                                break
                        else:
                            current_line = test_line
                    if current_line and current_y >= rect.y:
                        c.drawString(text_x, current_y, current_line)
                        current_y -= line_height
            else:
                # If content is not string, try to convert
                content_str = str(endnote_content)
                # Wrap long text
                words = content_str.split()
                current_line = ""
                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    test_width = c.stringWidth(test_line, font_name, font_size)
                    if test_width > max_width and current_line:
                        c.drawString(text_x, current_y, current_line)
                        current_y -= line_height
                        current_line = word
                        if current_y < rect.y:
                            break
                    else:
                        current_line = test_line
                if current_line and current_y >= rect.y:
                    c.drawString(text_x, current_y, current_line)
                    current_y -= line_height
            
            y = current_y - line_height * 0.5  # Spacing between endnotes
    
    def _draw_generic(self, c: canvas.Canvas, block: LayoutBlock) -> None:
        """

        Default renderer for unknown types.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock of unknown type

        """
        rect = block.frame
        c.setStrokeColor(Color(0.8, 0.8, 0.8))
        c.setLineWidth(0.5)
        c.rect(rect.x, rect.y, rect.width, rect.height)
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(Color(0.5, 0.5, 0.5))
        c.drawString(rect.x + 5, rect.y + rect.height - 10, f"[{block.block_type}]")
    
    def _draw_error_placeholder(self, c: canvas.Canvas, block: LayoutBlock, error: str) -> None:
        """

        Renders error placeholder for block.

        Args:
        c: ReportLab Canvas
        block: LayoutBlock with error
        error: Error message

        """
        rect = block.frame
        c.setStrokeColor(Color(1.0, 0.2, 0.2))
        c.setLineWidth(1.0)
        c.rect(rect.x, rect.y, rect.width, rect.height)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(Color(1.0, 0.2, 0.2))
        c.drawString(rect.x + 5, rect.y + rect.height - 10, f"[ERROR: {error[:50]}]")
    
    # ----------------------------------------------------------------------
    # Pomocnicze metody
    # ----------------------------------------------------------------------
    
    def _select_font_variant(self, font_name: Optional[str], style: Dict[str, Any]) -> str:
        """
        Dobiera wariant fontu (bold/italic) na podstawie stylu.
        """
        bold = bool(style.get("bold"))
        italic = bool(style.get("italic"))
        return resolve_font_variant(font_name, bold, italic)

    def _resolve_field_text(self, field_info: Optional[Dict[str, Any]]) -> str:
        if not field_info or not isinstance(field_info, dict):
            return ""

        field_type = str(field_info.get("field_type") or field_info.get("type") or "").upper()
        # Use current _current_page_number value (set before page rendering)
        current_page = self._current_page_number if self._current_page_number > 0 else 1
        total_pages = self._total_pages if self._total_pages > 0 else 1
        
        context = {
            "current_page": current_page,
            "total_pages": total_pages,
        }

        instruction = (
            field_info.get("instruction")
            or field_info.get("instr")
            or field_info.get("code")
            or ""
        )

        try:
            field_model = Field()
            if instruction:
                field_model.set_instr(instruction)
            else:
                if field_type:
                    field_model.field_type = field_type
                field_model.format_info = field_info.get("format_info") or {}
            field_model.update_context(context)
            calculated = field_model.calculate_value(context)
            if calculated:
                return str(calculated)
        except Exception:
            pass

        fallback = (
            field_info.get("result")
            or field_info.get("value")
            or field_info.get("display")
            or field_info.get("text")
            or ""
        )
        if field_type == "PAGE" and not fallback:
            return str(context["current_page"])
        if field_type == "NUMPAGES" and not fallback:
            return str(context["total_pages"])
        return str(fallback)

    def _resolve_hyperlink_url(self, hyperlink: Optional[Dict[str, Any]], fallback_text: str) -> Optional[str]:
        """
        Wyznacza docelowy URL dla hyperlinku.
        """

        def _normalize(candidate: Any, mode: str) -> Optional[str]:
            if candidate in (None, "", {}):
                return None
            url = str(candidate).strip()
            if not url:
                return None
            mode_token = mode.lower()
            if mode_token == "external":
                return url
            lowered = url.lower()
            if lowered.startswith(
                ("http://", "https://", "mailto:", "ftp://", "ftps://", "news:", "tel:", "sms:", "file://")
            ):
                return url
            return None

        if isinstance(hyperlink, dict):
            target_mode = str(hyperlink.get("target_mode") or "").lower()
            for key in ("url", "href", "target", "relationship_target"):
                candidate = hyperlink.get(key)
                normalized = _normalize(candidate, target_mode)
                if normalized:
                    return normalized
            anchor_value = hyperlink.get("anchor")
            if anchor_value and str(anchor_value).strip():
                # We don't render internal bookmarks as URL - no mapping in PDF.
                return None

        text_candidate = (fallback_text or "").strip()
        return _normalize(text_candidate, "")

    @staticmethod
    def _resolve_highlight_color(value: Any) -> Optional[str]:
        """

        Maps highlight color names to HEX values.

        """
        if not value:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized or normalized in {"auto", "none", "transparent"}:
                return None
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
            }
            return highlight_map.get(normalized, value)
        return None

    def _color_to_reportlab(self, value: Any, fallback: str = "#000000") -> Color:
        """

        Converts various color representations to ReportLab Color object.

        """
        if isinstance(value, Color):
            return value
        if hasattr(value, "r") and hasattr(value, "g") and hasattr(value, "b"):
            r = getattr(value, "r", 0.0)
            g = getattr(value, "g", 0.0)
            b = getattr(value, "b", 0.0)
            a = getattr(value, "a", 1.0)
            return Color(r, g, b, alpha=a)
        if isinstance(value, dict):
            try:
                r = float(value.get("r", 0.0))
                g = float(value.get("g", 0.0))
                b = float(value.get("b", 0.0))
                a = float(value.get("a", 1.0))
                if r > 1.0 or g > 1.0 or b > 1.0:
                    r /= 255.0
                    g /= 255.0
                    b /= 255.0
                return Color(r, g, b, alpha=a)
            except (TypeError, ValueError):
                pass
        if isinstance(value, str) and value:
            return self._hex_to_rgb(value)
        return self._hex_to_rgb(fallback)

    def _hex_to_rgb(self, hex_color: str) -> Color:
        """
        Konwersja #RRGGBB → ReportLab Color.
        
        Args:
            hex_color: Kolor w formacie HEX (#RRGGBB lub RRGGBB)
            
        Returns:
            ReportLab Color object
        """
        if not hex_color:
            return black
        token = str(hex_color).strip()
        if not token or token.lower() in {"auto", "none", "transparent"}:
            return black

        hex_color = token.lstrip("#")
        
        # Handle different formats
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
        elif len(hex_color) == 3:
            r = int(hex_color[0], 16) / 15.0
            g = int(hex_color[1], 16) / 15.0
            b = int(hex_color[2], 16) / 15.0
        else:
            logger.warning(f"Nieprawidłowy format koloru: {hex_color}, używam czarnego")
            return black
        
        return Color(r, g, b)


def _parallel_render_chunk(task: Tuple[List[int], str]) -> str:
    """
    Worker helper — render a subset of pages to a temporary PDF file.
    """
    indices, output_path = task
    if _PARALLEL_LAYOUT is None or _PARALLEL_PAGE_SIZE is None:
        raise RuntimeError("Parallel worker nie został poprawnie zainicjowany.")

    chunk_layout = UnifiedLayout()
    # Copy pages from original layout - page.number is already set correctly
    chunk_layout.pages = [_PARALLEL_LAYOUT.pages[i] for i in indices]
    chunk_layout.current_page = len(chunk_layout.pages) + 1

    compiler = PDFCompiler(
        output_path=output_path,
        page_size=_PARALLEL_PAGE_SIZE,
        package_reader=_PARALLEL_PACKAGE_READER,
        parallelism=1,
    )
    total_pages = _PARALLEL_TOTAL_PAGES if _PARALLEL_TOTAL_PAGES > 0 else len(_PARALLEL_LAYOUT.pages)
    compiler._total_pages = max(total_pages, 1)
    
    # In parallel mode page.number already contains proper page number from original layout
    # We don't use start_page_number - use page.number directly
    compiler._render_sequential(chunk_layout, start_page_number=None)
    return output_path

