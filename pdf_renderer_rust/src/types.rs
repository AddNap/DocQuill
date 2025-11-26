//! Type definitions for PDF rendering

use serde::{Deserialize, Serialize};
use serde_json;

/// Rectangle with position and size
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Rect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

impl Rect {
    pub fn new(x: f64, y: f64, width: f64, height: f64) -> Self {
        Self { x, y, width, height }
    }
    
    pub fn top(&self) -> f64 {
        self.y + self.height
    }
    
    pub fn bottom(&self) -> f64 {
        self.y
    }
    
    pub fn left(&self) -> f64 {
        self.x
    }
    
    pub fn right(&self) -> f64 {
        self.x + self.width
    }
}

/// Size with width and height
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Size {
    pub width: f64,
    pub height: f64,
}

impl Size {
    pub fn new(width: f64, height: f64) -> Self {
        Self { width, height }
    }
}

/// Margins
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Margins {
    pub top: f64,
    pub bottom: f64,
    pub left: f64,
    pub right: f64,
}

impl Margins {
    pub fn new(top: f64, bottom: f64, left: f64, right: f64) -> Self {
        Self { top, bottom, left, right }
    }
}

/// Color representation
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Color {
    pub r: f64,
    pub g: f64,
    pub b: f64,
}

impl Color {
    pub fn rgb(r: f64, g: f64, b: f64) -> Self {
        Self { r, g, b }
    }
    
    pub fn from_hex(hex: &str) -> Result<Self, String> {
        let hex = hex.trim_start_matches('#');
        if hex.len() != 6 {
            return Err("Invalid hex color".to_string());
        }
        
        let r = u8::from_str_radix(&hex[0..2], 16)
            .map_err(|_| "Invalid hex color")? as f64 / 255.0;
        let g = u8::from_str_radix(&hex[2..4], 16)
            .map_err(|_| "Invalid hex color")? as f64 / 255.0;
        let b = u8::from_str_radix(&hex[4..6], 16)
            .map_err(|_| "Invalid hex color")? as f64 / 255.0;
        
        Ok(Self { r, g, b })
    }
    
    pub fn black() -> Self {
        Self { r: 0.0, g: 0.0, b: 0.0 }
    }
    
    pub fn white() -> Self {
        Self { r: 1.0, g: 1.0, b: 1.0 }
    }
}

/// Layout block content type
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum BlockContent {
    Paragraph {
        text: String,
        lines: Vec<TextLine>,
    },
    Table {
        rows: Vec<TableRow>,
    },
    Image {
        path: Option<String>,
        data: Option<Vec<u8>>,
    },
    TextBox {
        content: String,
    },
    Decorator {
        kind: String,
    },
}

/// Text line for paragraph rendering
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextLine {
    pub text: String,
    pub x: f64,
    pub y: f64,
    pub font_name: String,
    pub font_size: f64,
    pub color: String,
}

/// Table row
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableRow {
    pub cells: Vec<TableCell>,
}

/// Table cell
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableCell {
    pub content: String,
    pub rect: Rect,
}

/// Layout block
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LayoutBlock {
    pub frame: Rect,
    pub block_type: String,
    pub content: serde_json::Value, // Flexible content representation
    pub style: serde_json::Value,   // Flexible style representation
    pub page_number: Option<u32>,
}

/// Layout page
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LayoutPage {
    pub number: u32,
    pub size: Size,
    pub margins: Margins,
    pub blocks: Vec<LayoutBlock>,
    pub skip_headers_footers: bool,
}

/// Unified layout (entire document)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnifiedLayout {
    pub pages: Vec<LayoutPage>,
}

/// Text style for rendering text runs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextStyle {
    pub font_name: Option<String>,
    pub font_size: Option<f64>,
    pub color: Option<String>,
    pub bold: Option<bool>,
    pub italic: Option<bool>,
    pub underline: Option<bool>,
}

impl TextStyle {
    /// Create default text style
    pub fn default() -> Self {
        Self {
            font_name: Some("Helvetica".to_string()),
            font_size: Some(11.0),
            color: Some("#000000".to_string()),
            bold: Some(false),
            italic: Some(false),
            underline: Some(false),
        }
    }
    
    /// Parse from JSON value with fallback to defaults
    pub fn from_json(value: &serde_json::Value) -> Self {
        use crate::json_helpers;
        Self {
            font_name: json_helpers::get_str_opt(value, "font_name")
                .or_else(|| json_helpers::get_str_opt(value, "font_ascii"))
                .or_else(|| json_helpers::get_str_opt(value, "font_hAnsi"))
                .map(|s| s.to_string()),
            font_size: json_helpers::get_f64_opt(value, "font_size")
                .or_else(|| {
                    // Try parsing as string (e.g., "18" from runs_payload)
                    // Note: font_size from runs_payload is in half-points, so divide by 2
                    value.get("font_size")
                        .and_then(|v| v.as_str())
                        .and_then(|s| s.parse::<f64>().ok())
                        .map(|size| size / 2.0) // Convert from half-points to points
                })
                .or_else(|| json_helpers::get_f64_opt(value, "size")),
            color: json_helpers::get_str_opt(value, "color")
                .map(|s| s.to_string()),
            bold: value.get("bold").and_then(|v| v.as_bool()),
            italic: value.get("italic").and_then(|v| v.as_bool()),
            underline: value.get("underline").and_then(|v| v.as_bool()),
        }
    }
    
    /// Get font name with default
    pub fn font_name(&self) -> &str {
        self.font_name.as_deref().unwrap_or("Helvetica")
    }
    
    /// Get font size with default
    pub fn font_size(&self) -> f64 {
        self.font_size.unwrap_or(11.0)
    }
    
    /// Get color with default
    pub fn color(&self) -> &str {
        self.color.as_deref().unwrap_or("#000000")
    }
}

/// Paragraph style for rendering paragraphs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParagraphStyle {
    pub font_name: Option<String>,
    pub font_size: Option<f64>,
    pub color: Option<String>,
    pub text_align: Option<String>, // "left", "center", "right", "justify"
    pub alignment: Option<String>,  // Alternative name for text_align
    pub padding: Option<Margins>,
    pub line_height: Option<f64>,
    pub background_color: Option<String>,
}

impl ParagraphStyle {
    /// Create default paragraph style
    pub fn default() -> Self {
        Self {
            font_name: Some("Helvetica".to_string()),
            font_size: Some(11.0),
            color: Some("#000000".to_string()),
            text_align: Some("left".to_string()),
            alignment: None,
            padding: None,
            line_height: None,
            background_color: None,
        }
    }
    
    /// Parse from JSON value with fallback to defaults
    pub fn from_json(value: &serde_json::Value) -> Self {
        use crate::json_helpers;
        Self {
            font_name: json_helpers::get_str_opt(value, "font_name")
                .map(|s| s.to_string()),
            font_size: json_helpers::get_f64_opt(value, "font_size"),
            color: json_helpers::get_str_opt(value, "color")
                .map(|s| s.to_string()),
            text_align: json_helpers::get_str_opt(value, "text_align")
                .map(|s| s.to_string()),
            alignment: json_helpers::get_str_opt(value, "alignment")
                .map(|s| s.to_string()),
            padding: value.get("padding")
                .and_then(|p| p.as_array())
                .map(|p| {
                    Margins::new(
                        if p.len() > 0 { json_helpers::get_f64_or(&p[0], "", 0.0) } else { 0.0 },
                        if p.len() > 1 { json_helpers::get_f64_or(&p[1], "", 0.0) } else { 0.0 },
                        if p.len() > 2 { json_helpers::get_f64_or(&p[2], "", 0.0) } else { 0.0 },
                        if p.len() > 3 { json_helpers::get_f64_or(&p[3], "", 0.0) } else { 0.0 },
                    )
                }),
            line_height: json_helpers::get_f64_opt(value, "line_height"),
            background_color: json_helpers::get_str_opt(value, "background_color")
                .map(|s| s.to_string()),
        }
    }
    
    /// Get text alignment with default
    pub fn text_align(&self) -> &str {
        self.text_align.as_deref()
            .or_else(|| self.alignment.as_deref())
            .unwrap_or("left")
    }
    
    /// Get font name with default
    pub fn font_name(&self) -> &str {
        self.font_name.as_deref().unwrap_or("Helvetica")
    }
    
    /// Get font size with default
    pub fn font_size(&self) -> f64 {
        self.font_size.unwrap_or(11.0)
    }
    
    /// Get color with default
    pub fn color(&self) -> &str {
        self.color.as_deref().unwrap_or("#000000")
    }
    
    /// Get padding with default (all zeros)
    pub fn padding(&self) -> Margins {
        self.padding.unwrap_or(Margins::new(0.0, 0.0, 0.0, 0.0))
    }
}

