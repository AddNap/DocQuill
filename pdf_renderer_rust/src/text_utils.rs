//! Text utilities for PDF rendering
//!
//! ⚠️ NOTE: These utilities are DEPRECATED and should NOT be used in the renderer.
//! Layout calculations (text wrapping, position calculation) should be performed
//! by the Python LayoutAssembler, not in the Rust renderer.
//!
//! The renderer should only render pre-calculated layouts from the assembler.

// Unused imports removed

/// Simple text layout for wrapping text into lines
#[allow(dead_code)]
pub struct TextLayout {
    pub lines: Vec<String>,
    pub line_height: f64,
    pub total_height: f64,
}

impl TextLayout {
    #[allow(dead_code)]
    pub fn new(lines: Vec<String>, font_size: f64, line_spacing_factor: f64) -> Self {
        let line_height = font_size * line_spacing_factor;
        let total_height = lines.len() as f64 * line_height;
        Self {
            lines,
            line_height,
            total_height,
        }
    }
}

/// [DEPRECATED] Simple text wrapping - splits text into words and wraps to fit width
///
/// ⚠️ WARNING: This function performs layout calculations, which violates the architecture
/// principle that the renderer should only render pre-calculated blocks.
///
/// This function should NOT be used. The assembler should provide a `ParagraphLayout`
/// with pre-calculated lines instead.
///
/// This is kept for backward compatibility but should be removed in the future.
#[allow(dead_code)]
pub fn wrap_text_simple(text: &str, max_width: f64, font_size: f64, line_spacing_factor: f64) -> TextLayout {
    // Simple estimation: assume average character width is ~0.6 * font_size
    // This is a rough approximation - proper implementation would use font metrics
    let avg_char_width = font_size * 0.6;
    let chars_per_line = (max_width / avg_char_width).max(1.0) as usize;
    
    let words: Vec<&str> = text.split_whitespace().collect();
    let mut lines = Vec::new();
    let mut current_line = String::new();
    
    for word in words {
        let test_line = if current_line.is_empty() {
            word.to_string()
        } else {
            format!("{} {}", current_line, word)
        };
        
        // Simple check: if line would be too long, start new line
        if test_line.len() > chars_per_line && !current_line.is_empty() {
            lines.push(current_line.clone());
            current_line = word.to_string();
        } else {
            current_line = test_line;
        }
    }
    
    if !current_line.is_empty() {
        lines.push(current_line);
    }
    
    // If no lines, add empty line
    if lines.is_empty() {
        lines.push(String::new());
    }
    
    TextLayout::new(lines, font_size, line_spacing_factor)
}

/// [DEPRECATED] Calculate text alignment X position
///
/// ⚠️ WARNING: This function performs layout calculations, which violates the architecture
/// principle that the renderer should only render pre-calculated blocks.
///
/// This function should NOT be used. The assembler should provide a `ParagraphLayout`
/// with pre-calculated positions instead.
///
/// This is kept for backward compatibility but should be removed in the future.
#[allow(dead_code)]
pub fn calculate_text_x_position(
    rect_x: f64,
    rect_width: f64,
    text_width: f64,
    alignment: &str,
) -> f64 {
    match alignment.to_lowercase().as_str() {
        "center" | "centre" => rect_x + (rect_width - text_width) / 2.0,
        "right" => rect_x + rect_width - text_width,
        "justify" | "both" => rect_x, // For justify, we'll use left for now
        _ => rect_x, // left or default
    }
}

