//! List marker rendering
//! 
//! Handles rendering of list markers (bullet points, numbering, etc.)

use crate::canvas::PdfCanvas;
use crate::geometry::parse_color;
use pdf_writer::Name;
use serde_json;

/// Render list marker
pub fn render_marker(
    canvas: &mut PdfCanvas,
    pdf: &mut pdf_writer::Pdf,
    fonts_registry: &mut crate::font_registry::FontRegistry,
    marker: &serde_json::Map<String, serde_json::Value>,
    x: f64,
    y: f64,
    default_font_name: &str,
    default_font_size: f64,
    default_color: &str,
) -> Result<(), pyo3::PyErr> {
    // Get marker text - prioritize marker_override_text if available
    let marker_text = marker.get("marker_override_text")
        .or_else(|| marker.get("text"))
        .or_else(|| marker.get("label"))
        .or_else(|| marker.get("display"))
        .or_else(|| marker.get("bullet"))
        .and_then(|v| v.as_str())
        .unwrap_or("");
    
    if marker_text.is_empty() {
        return Ok(());
    }
    
    // Get marker suffix
    let marker_suffix_raw = marker.get("suffix").and_then(|v| v.as_str()).unwrap_or("");
    let marker_suffix = match marker_suffix_raw.trim().to_lowercase().as_str() {
        "tab" | "tabulation" => "",
        "space" => " ",
        "none" | "-" => "",
        _ => marker_suffix_raw,
    };
    
    let full_marker_text = if marker_suffix.is_empty() || marker_text.contains(marker_suffix) {
        marker_text.to_string()
    } else {
        format!("{}{}", marker_text, marker_suffix)
    };
    
    // Get marker style
    let marker_font_name = marker.get("font_name")
        .or_else(|| marker.get("font_ascii"))
        .and_then(|v| v.as_str())
        .unwrap_or(default_font_name);
    
    let marker_font_size = marker.get("font_size")
        .or_else(|| marker.get("size"))
        .and_then(|v| v.as_f64())
        .unwrap_or(default_font_size);
    
    let marker_color_value = marker.get("color")
        .and_then(|v| v.as_str())
        .unwrap_or(default_color);
    
    let marker_color = parse_color(&serde_json::json!(marker_color_value));
    
    // Get baseline adjustment
    let baseline_adjust = marker.get("baseline_adjust")
        .or_else(|| marker.get("baseline_shift"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    
    let marker_y = y + baseline_adjust;
    
    // Render marker
    canvas.save_state();
    canvas.set_fill_color(marker_color);
    
    // Get font reference from registry
    let font_ref = fonts_registry.get_or_builtin(pdf, marker_font_name);
    
    canvas.set_font(font_ref, marker_font_size);
    canvas.draw_string(x, marker_y, &full_marker_text);
    canvas.restore_state();
    
    Ok(())
}

