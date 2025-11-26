"""Rust PDF Canvas - Minimal PDF renderer with canvas operations only."""

import os
import sys
import importlib.util

# Get the directory where this __init__.py is located
_init_dir = os.path.dirname(os.path.abspath(__file__))
_so_path = os.path.join(_init_dir, 'rust_pdf_canvas.abi3.so')

# Also check site-packages
_site_packages_so = None
for site_path in sys.path:
    if 'site-packages' in site_path:
        candidate = os.path.join(site_path, 'rust_pdf_canvas', 'rust_pdf_canvas.abi3.so')
        if os.path.exists(candidate):
            _site_packages_so = candidate
            break

# Try to load from site-packages first, then from local directory
_so_to_load = _site_packages_so if _site_packages_so else (_so_path if os.path.exists(_so_path) else None)

try:
    if _so_to_load and os.path.exists(_so_to_load):
        spec = importlib.util.spec_from_file_location('rust_pdf_canvas', _so_to_load)
        rust_mod = importlib.util.module_from_spec(spec)
        sys.modules['rust_pdf_canvas.rust_pdf_canvas'] = rust_mod
        spec.loader.exec_module(rust_mod)
        PdfCanvasRenderer = rust_mod.PdfCanvasRenderer
        __all__ = ['PdfCanvasRenderer']
    else:
        PdfCanvasRenderer = None
        __all__ = []
except Exception as e:
    PdfCanvasRenderer = None
    __all__ = []
