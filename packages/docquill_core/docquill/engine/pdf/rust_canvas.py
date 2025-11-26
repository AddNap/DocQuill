"""
Rust Canvas Wrapper - Canvas-like API for Rust PDF renderer.

This module provides a ReportLab Canvas-compatible API that delegates to Rust renderer.
All business logic stays in Python - Rust only handles low-level PDF operations.
"""

import logging
import time
from typing import Optional, Union, Tuple, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import Rust renderer
try:
    import rust_pdf_canvas
    HAS_RUST_RENDERER = True
except ImportError:
    HAS_RUST_RENDERER = False
    rust_pdf_canvas = None


class RustCanvas:
    """
    Canvas-like wrapper for Rust PDF renderer.
    
    Provides the same API as ReportLab Canvas, but delegates to Rust renderer.
    This allows PDFCompiler to use Rust renderer without changing business logic.
    """
    
    def __init__(self, rust_renderer, page_width: float, page_height: float, metrics_engine=None, batch_size: int = 0):
        """
        Initialize Rust Canvas wrapper.
        
        Args:
            rust_renderer: Rust PdfRenderer instance (from pdf_renderer_rust)
            page_width: Page width in points
            page_height: Page height in points
            metrics_engine: Optional TextMetricsEngine for text width measurement
            batch_size: Maximum number of commands to batch before flushing (default: 500)
                        Set to 0 to disable batching (immediate execution)
        """
        if not HAS_RUST_RENDERER:
            raise ImportError("rust_pdf_canvas not available")
        
        self._renderer = rust_renderer
        self._page_width = page_width
        self._page_height = page_height
        self._metrics_engine = metrics_engine
        self._batch_size = batch_size
        self._batch_commands = []  # List of command dicts to batch
        
        # Performance tracking (lightweight - just counting, no timing overhead)
        self._call_count = 0
        self._rust_call_time = 0.0
        self._enable_profiling = False  # Set to True to enable detailed profiling (adds timing overhead)
        
        # Canvas state tracking (for compatibility with ReportLab)
        self._current_fill_color = (0.0, 0.0, 0.0)  # RGB
        self._current_stroke_color = (0.0, 0.0, 0.0)  # RGB
        self._current_line_width = 1.0
        self._current_font_name = "Helvetica"
        self._current_font_size = 12.0
        self._current_dash = None
    
    # Canvas operations (matching ReportLab API)
    
    def _call_rust(self, method_name: str, *args, **kwargs):
        """
        Helper method to call Rust renderer method with optional profiling.
        
        Args:
            method_name: Name of the method to call on self._renderer
            *args, **kwargs: Arguments to pass to the method
        """
        if self._enable_profiling:
            t0 = time.perf_counter()
            method = getattr(self._renderer, method_name)
            result = method(*args, **kwargs)
            elapsed = time.perf_counter() - t0
            self._call_count += 1
            self._rust_call_time += elapsed
            return result
        else:
            method = getattr(self._renderer, method_name)
            return method(*args, **kwargs)
    
    def get_profiling_stats(self) -> dict:
        """Get profiling statistics (call count and total time)."""
        return {
            "call_count": self._call_count,
            "rust_call_time": self._rust_call_time,
            "avg_call_time": self._rust_call_time / self._call_count if self._call_count > 0 else 0.0,
        }
    
    def reset_profiling(self):
        """Reset profiling statistics."""
        self._call_count = 0
        self._rust_call_time = 0.0
    
    def _add_command(self, cmd_dict: dict):
        """Add a command to the batch queue."""
        if self._batch_size == 0:
            # Batching disabled - execute immediately by calling Rust methods directly
            # This avoids dict creation/parsing overhead
            cmd_type = cmd_dict.get("type")
            try:
                # Count calls (lightweight, no timing overhead)
                self._call_count += 1
                
                if cmd_type == "SaveState":
                    self._renderer.canvas_save_state()
                elif cmd_type == "RestoreState":
                    self._renderer.canvas_restore_state()
                elif cmd_type == "SetFillColor":
                    self._renderer.canvas_set_fill_color(cmd_dict["r"], cmd_dict["g"], cmd_dict["b"])
                elif cmd_type == "SetStrokeColor":
                    self._renderer.canvas_set_stroke_color(cmd_dict["r"], cmd_dict["g"], cmd_dict["b"])
                elif cmd_type == "SetLineWidth":
                    self._renderer.canvas_set_line_width(cmd_dict["width"])
                elif cmd_type == "SetDash":
                    self._renderer.canvas_set_dash(cmd_dict["pattern"])
                elif cmd_type == "SetFont":
                    self._renderer.canvas_set_font(cmd_dict["name"], cmd_dict["size"])
                elif cmd_type == "SetOpacity":
                    self._renderer.canvas_set_opacity(cmd_dict["opacity"])
                elif cmd_type == "Rect":
                    self._renderer.canvas_rect(cmd_dict["x"], cmd_dict["y"], cmd_dict["width"], cmd_dict["height"], cmd_dict["fill"], cmd_dict["stroke"])
                elif cmd_type == "RoundRect":
                    self._renderer.canvas_round_rect(cmd_dict["x"], cmd_dict["y"], cmd_dict["width"], cmd_dict["height"], cmd_dict["radius"], cmd_dict["fill"], cmd_dict["stroke"])
                elif cmd_type == "Line":
                    self._renderer.canvas_line(cmd_dict["x1"], cmd_dict["y1"], cmd_dict["x2"], cmd_dict["y2"])
                elif cmd_type == "DrawString":
                    self._renderer.canvas_draw_string(cmd_dict["x"], cmd_dict["y"], cmd_dict["text"])
                elif cmd_type == "DrawImage":
                    self._renderer.canvas_draw_image(cmd_dict["x"], cmd_dict["y"], cmd_dict["width"], cmd_dict["height"], cmd_dict["image_data"])
                elif cmd_type == "Translate":
                    self._renderer.canvas_translate(cmd_dict["x"], cmd_dict["y"])
                elif cmd_type == "Rotate":
                    self._renderer.canvas_rotate(cmd_dict["angle"])
                elif cmd_type == "Scale":
                    self._renderer.canvas_scale(cmd_dict["x"], cmd_dict["y"])
                elif cmd_type == "Transform":
                    self._renderer.canvas_transform(cmd_dict["matrix"])
                else:
                    logger.warning(f"Unknown command type: {cmd_type}")
            except Exception as e:
                if not hasattr(self, '_error_logged'):
                    logger.error(f"Error executing command {cmd_type}: {type(e).__name__}: {e}", exc_info=True)
                    self._error_logged = True
                raise
        else:
            self._batch_commands.append(cmd_dict)
            # Auto-flush if batch is full
            if len(self._batch_commands) >= self._batch_size:
                self._flush_batch()
    
    def _execute_command_directly(self, cmd: dict):
        """Execute a single command directly without batching."""
        cmd_type = cmd.get("type")
        try:
            if cmd_type == "SaveState":
                self._renderer.canvas_save_state()
            elif cmd_type == "RestoreState":
                self._renderer.canvas_restore_state()
            elif cmd_type == "SetFillColor":
                self._renderer.canvas_set_fill_color(cmd["r"], cmd["g"], cmd["b"])
            elif cmd_type == "SetStrokeColor":
                self._renderer.canvas_set_stroke_color(cmd["r"], cmd["g"], cmd["b"])
            elif cmd_type == "SetLineWidth":
                self._renderer.canvas_set_line_width(cmd["width"])
            elif cmd_type == "SetDash":
                self._renderer.canvas_set_dash(cmd["pattern"])
            elif cmd_type == "SetFont":
                self._renderer.canvas_set_font(cmd["name"], cmd["size"])
            elif cmd_type == "SetOpacity":
                self._renderer.canvas_set_opacity(cmd["opacity"])
            elif cmd_type == "Rect":
                self._renderer.canvas_rect(cmd["x"], cmd["y"], cmd["width"], cmd["height"], cmd["fill"], cmd["stroke"])
            elif cmd_type == "RoundRect":
                self._renderer.canvas_round_rect(cmd["x"], cmd["y"], cmd["width"], cmd["height"], cmd["radius"], cmd["fill"], cmd["stroke"])
            elif cmd_type == "Line":
                self._renderer.canvas_line(cmd["x1"], cmd["y1"], cmd["x2"], cmd["y2"])
            elif cmd_type == "DrawString":
                self._renderer.canvas_draw_string(cmd["x"], cmd["y"], cmd["text"])
            elif cmd_type == "DrawImage":
                self._renderer.canvas_draw_image(cmd["x"], cmd["y"], cmd["width"], cmd["height"], cmd["image_data"])
            elif cmd_type == "Translate":
                self._renderer.canvas_translate(cmd["x"], cmd["y"])
            elif cmd_type == "Rotate":
                self._renderer.canvas_rotate(cmd["angle"])
            elif cmd_type == "Scale":
                self._renderer.canvas_scale(cmd["x"], cmd["y"])
            elif cmd_type == "Transform":
                self._renderer.canvas_transform(cmd["matrix"])
            else:
                logger.warning(f"Unknown command type: {cmd_type}")
        except Exception as e:
            # Log error but don't crash - this helps debug the issue
            if not hasattr(self, '_error_logged'):
                logger.error(f"Error executing command {cmd_type}: {type(e).__name__}: {e}", exc_info=True)
                self._error_logged = True
            raise
    
    def _flush_batch(self, commands: Optional[List[dict]] = None):
        """Flush batched commands to Rust renderer."""
        if commands is None:
            commands = self._batch_commands
            self._batch_commands = []
        
        if not commands:
            return
        
        # Call Rust batch API
        # Rust expects &PyList, which PyO3 will convert automatically from Python list
        try:
            # Check if method exists first
            if not hasattr(self._renderer, 'canvas_run_batch'):
                raise AttributeError("canvas_run_batch method not found")
            
            # Pass the list directly - PyO3 should convert Python list to &PyList automatically
            # Log first batch to verify it's being called
            if not hasattr(self, '_batch_first_call_logged'):
                logger.info(f"Using batch API: flushing {len(commands)} commands")
                self._batch_first_call_logged = True
            
            # Try to call batch API - PyO3 should handle conversion
            try:
                self._renderer.canvas_run_batch(commands)
            except TypeError as te:
                # If PyO3 can't convert automatically, try converting to PyList manually
                import pyo3
                import sys
                # This shouldn't be necessary, but if it fails, we'll use fallback
                raise te
        except (AttributeError, TypeError) as e:
            # Fallback: if batch API doesn't exist or has wrong signature, execute commands individually
            # Only log once to avoid spam
            if not hasattr(self, '_batch_fallback_logged'):
                logger.warning(f"canvas_run_batch not available or failed ({type(e).__name__}: {e}), falling back to individual calls")
                self._batch_fallback_logged = True
            for cmd in commands:
                cmd_type = cmd.get("type")
                if cmd_type == "SaveState":
                    self._renderer.canvas_save_state()
                elif cmd_type == "RestoreState":
                    self._renderer.canvas_restore_state()
                elif cmd_type == "SetFillColor":
                    self._renderer.canvas_set_fill_color(cmd["r"], cmd["g"], cmd["b"])
                elif cmd_type == "SetStrokeColor":
                    self._renderer.canvas_set_stroke_color(cmd["r"], cmd["g"], cmd["b"])
                elif cmd_type == "SetLineWidth":
                    self._renderer.canvas_set_line_width(cmd["width"])
                elif cmd_type == "SetDash":
                    self._renderer.canvas_set_dash(cmd["pattern"])
                elif cmd_type == "SetFont":
                    self._renderer.canvas_set_font(cmd["name"], cmd["size"])
                elif cmd_type == "SetOpacity":
                    self._renderer.canvas_set_opacity(cmd["opacity"])
                elif cmd_type == "Rect":
                    self._renderer.canvas_rect(cmd["x"], cmd["y"], cmd["width"], cmd["height"], cmd["fill"], cmd["stroke"])
                elif cmd_type == "RoundRect":
                    self._renderer.canvas_round_rect(cmd["x"], cmd["y"], cmd["width"], cmd["height"], cmd["radius"], cmd["fill"], cmd["stroke"])
                elif cmd_type == "Line":
                    self._renderer.canvas_line(cmd["x1"], cmd["y1"], cmd["x2"], cmd["y2"])
                elif cmd_type == "DrawString":
                    self._renderer.canvas_draw_string(cmd["x"], cmd["y"], cmd["text"])
                elif cmd_type == "DrawImage":
                    self._renderer.canvas_draw_image(cmd["x"], cmd["y"], cmd["width"], cmd["height"], cmd["image_data"])
                elif cmd_type == "Translate":
                    self._renderer.canvas_translate(cmd["x"], cmd["y"])
                elif cmd_type == "Rotate":
                    self._renderer.canvas_rotate(cmd["angle"])
                elif cmd_type == "Scale":
                    self._renderer.canvas_scale(cmd["x"], cmd["y"])
                elif cmd_type == "Transform":
                    self._renderer.canvas_transform(cmd["matrix"])
    
    def saveState(self):
        """Save current canvas state."""
        self._add_command({"type": "SaveState"})
    
    def restoreState(self):
        """Restore previous canvas state."""
        self._add_command({"type": "RestoreState"})
    
    def setFillColor(self, color):
        """
        Set fill color.
        
        Args:
            color: Color object or tuple (r, g, b) or hex string
        """
        rgb = self._parse_color(color)
        self._current_fill_color = rgb
        self._add_command({"type": "SetFillColor", "r": rgb[0], "g": rgb[1], "b": rgb[2]})
    
    def setStrokeColor(self, color):
        """
        Set stroke color.
        
        Args:
            color: Color object or tuple (r, g, b) or hex string
        """
        rgb = self._parse_color(color)
        self._current_stroke_color = rgb
        self._add_command({"type": "SetStrokeColor", "r": rgb[0], "g": rgb[1], "b": rgb[2]})
    
    def setLineWidth(self, width: float):
        """Set line width."""
        self._current_line_width = width
        self._add_command({"type": "SetLineWidth", "width": width})
    
    def setDash(self, *args):
        """
        Set dash pattern.
        
        Args:
            *args: Dash pattern (e.g., [6, 3] or 6, 3)
        """
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            pattern = list(args[0])
        else:
            pattern = list(args)
        self._current_dash = pattern
        self._add_command({"type": "SetDash", "pattern": pattern})
    
    def setFont(self, name: str, size: float):
        """Set font name and size."""
        self._current_font_name = name
        self._current_font_size = size
        self._add_command({"type": "SetFont", "name": name, "size": size})
    
    def setOpacity(self, opacity: float):
        """Set current drawing opacity (0.0 - 1.0)."""
        try:
            value = max(0.0, min(1.0, float(opacity)))
        except (TypeError, ValueError):
            value = 1.0
        self._add_command({"type": "SetOpacity", "opacity": value})
    
    def rect(self, x: float, y: float, width: float, height: float, fill: int = 0, stroke: int = 1):
        """
        Draw rectangle.
        
        Args:
            x, y: Position
            width, height: Dimensions
            fill: 1 to fill, 0 otherwise
            stroke: 1 to stroke, 0 otherwise
        """
        self._add_command({
            "type": "Rect",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "fill": bool(fill),
            "stroke": bool(stroke),
        })
    
    def roundRect(self, x: float, y: float, width: float, height: float, radius: float, fill: int = 0, stroke: int = 1):
        """
        Draw rounded rectangle.
        
        Args:
            x, y: Position
            width, height: Dimensions
            radius: Corner radius
            fill: 1 to fill, 0 otherwise
            stroke: 1 to stroke, 0 otherwise
        """
        self._add_command({
            "type": "RoundRect",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "radius": radius,
            "fill": bool(fill),
            "stroke": bool(stroke),
        })
    
    def line(self, x1: float, y1: float, x2: float, y2: float):
        """Draw line from (x1, y1) to (x2, y2)."""
        self._add_command({"type": "Line", "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    
    def drawString(self, x: float, y: float, text: str):
        """
        Draw text string.
        
        Args:
            x, y: Position
            text: Text to draw
        """
        self._add_command({"type": "DrawString", "x": x, "y": y, "text": text})
    
    def drawImage(self, image_path: Union[str, Path], x: float, y: float, width: Optional[float] = None, height: Optional[float] = None, mask: Optional[str] = None, preserveAspectRatio: bool = False):
        """
        Draw image.
        
        Args:
            image_path: Path to image file
            x, y: Position
            width, height: Dimensions (optional)
            mask: Mask mode (ignored for now)
            preserveAspectRatio: Whether to preserve aspect ratio (ignored for now)
        """
        # Load image data
        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Use provided dimensions or detect from image
        if width is None or height is None:
            # Try to detect dimensions (simplified - would need image library)
            if width is None:
                width = 100.0  # Default
            if height is None:
                height = 100.0  # Default
        
        self._add_command({
            "type": "DrawImage",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "image_data": image_data,
        })
    
    def translate(self, x: float, y: float):
        """Translate coordinate system."""
        self._add_command({"type": "Translate", "x": x, "y": y})
    
    def rotate(self, angle: float):
        """Rotate coordinate system (degrees)."""
        # Convert degrees to radians (Rust expects radians)
        import math
        radians = math.radians(angle)
        self._add_command({"type": "Rotate", "angle": radians})
    
    def scale(self, x: float, y: float):
        """Scale coordinate system."""
        self._add_command({"type": "Scale", "x": x, "y": y})
    
    def transform(self, a: float, b: float, c: float, d: float, e: float, f: float):
        """Apply transformation matrix."""
        self._add_command({"type": "Transform", "matrix": [a, b, c, d, e, f]})
    
    def setPageSize(self, size: Tuple[float, float]):
        """Set page size."""
        width, height = size
        self._page_width = width
        self._page_height = height
        # Note: Page size is set when creating new page, this just updates tracking
        try:
            self._renderer.set_page_size(width, height)
        except AttributeError:
            # Method might not exist, just update local tracking
            pass
    
    def showPage(self):
        """Finish current page and start new one."""
        # Flush any pending batched commands before page change
        self._flush_batch()
        # This is handled by the renderer, not the canvas
        pass
    
    def flush(self):
        """Manually flush all batched commands."""
        self._flush_batch()
    
    def stringWidth(self, text: str, font_name: str, font_size: float) -> float:
        """
        Calculate text width.
        
        Args:
            text: Text to measure
            font_name: Font name
            font_size: Font size in points
            
        Returns:
            Width in points
        """
        # Use TextMetricsEngine if available (same as ReportLab Canvas)
        if self._metrics_engine is not None:
            try:
                style = {
                    "font_name": font_name,
                    "font_size": font_size,
                }
                result = self._metrics_engine.measure_text(text, style)
                return result.get("width", 0.0)
            except Exception:
                pass
        
        # Fallback: simple estimation based on character count
        # Average character width for most fonts is approximately 0.6 * font_size
        avg_char_width = font_size * 0.6
        return len(text) * avg_char_width
    
    # Helper methods
    
    def _parse_color(self, color) -> Tuple[float, float, float]:
        """
        Parse color to RGB tuple (0.0-1.0).
        
        Supports:
        - ReportLab Color objects
        - Tuples (r, g, b) in 0.0-1.0 range
        - Hex strings (#RRGGBB)
        """
        # ReportLab Color object
        if hasattr(color, 'red') and hasattr(color, 'green') and hasattr(color, 'blue'):
            return (color.red, color.green, color.blue)
        
        # Tuple or list
        if isinstance(color, (tuple, list)):
            if len(color) >= 3:
                # Normalize to 0.0-1.0 range
                r, g, b = color[0], color[1], color[2]
                if r > 1.0 or g > 1.0 or b > 1.0:
                    # Assume 0-255 range
                    return (r / 255.0, g / 255.0, b / 255.0)
                return (r, g, b)
        
        # Hex string
        if isinstance(color, str) and color.startswith('#'):
            color = color[1:]
            if len(color) == 6:
                r = int(color[0:2], 16) / 255.0
                g = int(color[2:4], 16) / 255.0
                b = int(color[4:6], 16) / 255.0
                return (r, g, b)
        
        # Default to black
        logger.warning(f"Could not parse color: {color}, using black")
        return (0.0, 0.0, 0.0)

