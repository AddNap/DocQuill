//! Text formatting utilities
//! 
//! Handles superscript, subscript, underline, strike-through, highlight, etc.

use crate::canvas::PdfCanvas;
use crate::geometry::parse_color;
use crate::types::Color;
use pdf_writer::Name;

/// Text formatting options
#[derive(Debug, Clone, Copy)]
pub struct TextFormatting {
    pub superscript: bool,
    pub subscript: bool,
    pub underline: bool,
    pub strike_through: bool,
    pub highlight: Option<Color>,
}

impl Default for TextFormatting {
    fn default() -> Self {
        Self {
            superscript: false,
            subscript: false,
            underline: false,
            strike_through: false,
            highlight: None,
        }
    }
}

impl TextFormatting {
    /// Parse formatting from style object
    pub fn from_style(style: Option<&serde_json::Map<String, serde_json::Value>>) -> Self {
        let mut formatting = Self::default();
        
        if let Some(s) = style {
            formatting.superscript = s.get("superscript")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            
            formatting.subscript = s.get("subscript")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            
            formatting.underline = s.get("underline")
                .or_else(|| s.get("underlined"))
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            
            formatting.strike_through = s.get("strike_through")
                .or_else(|| s.get("strikethrough"))
                .or_else(|| s.get("strike"))
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            
            // Parse highlight color
            if let Some(highlight) = s.get("highlight") {
                if let Some(color) = highlight.as_str() {
                    formatting.highlight = Some(parse_color(&serde_json::json!(color)));
                } else if let Some(color_obj) = highlight.as_object() {
                    if let Some(color_str) = color_obj.get("color").and_then(|v| v.as_str()) {
                        formatting.highlight = Some(parse_color(&serde_json::json!(color_str)));
                    }
                }
            }
        }
        
        formatting
    }
    
    /// Calculate font size adjustment for superscript/subscript
    pub fn adjusted_font_size(&self, original_size: f64) -> f64 {
        if self.superscript || self.subscript {
            original_size * 0.58
        } else {
            original_size
        }
    }
    
    /// Calculate baseline shift for superscript/subscript
    pub fn baseline_shift(&self, original_size: f64) -> f64 {
        if self.superscript {
            original_size * 0.33
        } else if self.subscript {
            -original_size * 0.25
        } else {
            0.0
        }
    }
}

/// Render text with formatting
pub fn render_formatted_text(
    canvas: &mut PdfCanvas,
    x: f64,
    y: f64,
    text: &str,
    font_name: Name<'static>,
    font_size: f64,
    color: Color,
    formatting: &TextFormatting,
) {
    let adjusted_size = formatting.adjusted_font_size(font_size);
    let baseline_shift = formatting.baseline_shift(font_size);
    let text_y = y + baseline_shift;
    
    canvas.save_state();
    
    // Set font and color
    canvas.set_font(font_name, adjusted_size);
    canvas.set_fill_color(color);
    
    // Draw highlight background if needed
    if let Some(highlight_color) = formatting.highlight {
        // Calculate text width (approximate)
        let text_width = text.len() as f64 * adjusted_size * 0.6; // Approximate width
        let highlight_height = adjusted_size * 1.2;
        
        canvas.save_state();
        canvas.set_fill_color(highlight_color);
        canvas.rect(
            crate::types::Rect::new(x, text_y - highlight_height * 0.8, text_width, highlight_height),
            true,
            false,
        );
        canvas.restore_state();
    }
    
    // Draw text
    canvas.draw_string(x, text_y, text);
    
    // Draw underline if needed
    if formatting.underline {
        let underline_y = text_y - adjusted_size * 0.1;
        let text_width = text.len() as f64 * adjusted_size * 0.6; // Approximate width
        
        canvas.save_state();
        canvas.set_stroke_color(color);
        canvas.set_line_width(adjusted_size * 0.05);
        canvas.line(x, underline_y, x + text_width, underline_y);
        canvas.restore_state();
    }
    
    // Draw strike-through if needed
    if formatting.strike_through {
        let strike_y = text_y + adjusted_size * 0.3;
        let text_width = text.len() as f64 * adjusted_size * 0.6; // Approximate width
        
        canvas.save_state();
        canvas.set_stroke_color(color);
        canvas.set_line_width(adjusted_size * 0.05);
        canvas.line(x, strike_y, x + text_width, strike_y);
        canvas.restore_state();
    }
    
    canvas.restore_state();
}

