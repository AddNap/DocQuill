//! Geometry utilities for PDF rendering

use pdf_writer::Rect as PdfRect;

/// Convert our Rect to pdf-writer Rect
pub fn rect_to_pdf(rect: &crate::types::Rect) -> PdfRect {
    PdfRect::new(
        rect.x as f32, 
        rect.y as f32, 
        rect.width as f32, 
        rect.height as f32
    )
}

/// Convert color to PDF RGB values (0.0-1.0)
pub fn color_to_pdf_rgb(color: &crate::types::Color) -> (f64, f64, f64) {
    (color.r, color.g, color.b)
}

/// Helper to parse color from various formats
pub fn parse_color(color_value: &serde_json::Value) -> crate::types::Color {
    match color_value {
        serde_json::Value::String(s) => {
            if s.starts_with('#') {
                crate::types::Color::from_hex(s).unwrap_or(crate::types::Color::black())
            } else {
                crate::types::Color::black()
            }
        }
        serde_json::Value::Array(arr) if arr.len() == 3 => {
            let r = arr[0].as_f64().unwrap_or(0.0);
            let g = arr[1].as_f64().unwrap_or(0.0);
            let b = arr[2].as_f64().unwrap_or(0.0);
            crate::types::Color::rgb(r, g, b)
        }
        _ => crate::types::Color::black(),
    }
}

