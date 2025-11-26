//! PDF Renderer for DoclingForge 2.0
//! 
//! High-performance PDF rendering using pdf-writer library.
//! Provides Python bindings via PyO3 for integration with Python codebase.

mod canvas;
mod geometry;
pub mod renderer;
mod types;
mod image_utils;
mod image_registry;
mod text_utils;
mod font_utils;
mod font_registry;
mod block_renderer;
mod field;
mod text_formatting;
mod markers;
mod overlays;
mod justification;
mod unicode_utils;
mod error;
mod json_helpers;
mod text_layout;

use pyo3::prelude::*;

use renderer::PdfRenderer;

/// Python module for PDF rendering
#[pymodule]
fn pdf_renderer_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PdfRenderer>()?;
    Ok(())
}
