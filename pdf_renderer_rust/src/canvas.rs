//! High-level Canvas-like API wrapper for pdf-writer
//! 
//! Provides a ReportLab-like interface for easier migration

use pdf_writer::{Content, Name, Str};

use crate::types::{Color, Rect as OurRect};
use crate::unicode_utils::unicode_to_winansi;

/// Canvas state for graphics operations
#[derive(Clone)]
pub struct CanvasState {
    pub fill_color: Color,
    pub stroke_color: Color,
    pub line_width: f64,
    pub font_name: Name<'static>,
    pub font_size: f64,
    pub dash_pattern: Option<(Vec<f64>, f64)>,
}

impl Default for CanvasState {
    fn default() -> Self {
        Self {
            fill_color: Color::black(),
            stroke_color: Color::black(),
            line_width: 1.0,
            font_name: Name(b"F1"), // Default font (must be registered)
            font_size: 12.0,
            dash_pattern: None,
        }
    }
}

/// High-level Canvas wrapper for pdf-writer
pub struct PdfCanvas {
    content: Content,
    state: CanvasState,
    state_stack: Vec<CanvasState>,
}

impl PdfCanvas {
    pub fn new() -> Self {
        Self {
            content: Content::new(),
            state: CanvasState::default(),
            state_stack: Vec::new(),
        }
    }
    
    /// Get mutable reference to content
    pub fn content_mut(&mut self) -> &mut Content {
        &mut self.content
    }
    
    /// Get content (for finalizing)
    pub fn finish(self) -> Vec<u8> {
        self.content.finish()
    }
    
    // ===== State Management =====
    
    pub fn save_state(&mut self) {
        self.state_stack.push(self.state.clone());
        self.content.save_state();
    }
    
    pub fn restore_state(&mut self) {
        if let Some(state) = self.state_stack.pop() {
            self.state = state;
            self.content.restore_state();
        }
    }
    
    // ===== Colors =====
    
    pub fn set_fill_color(&mut self, color: Color) {
        self.state.fill_color = color;
        let (r, g, b) = (color.r as f32, color.g as f32, color.b as f32);
        self.content.set_fill_rgb(r, g, b);
    }
    
    pub fn set_stroke_color(&mut self, color: Color) {
        self.state.stroke_color = color;
        let (r, g, b) = (color.r as f32, color.g as f32, color.b as f32);
        self.content.set_stroke_rgb(r, g, b);
    }
    
    /// Set graphics state with opacity (for watermarks, etc.)
    /// Note: pdf-writer doesn't directly support opacity, but we can use ExtGState
    /// For now, this is a placeholder - full implementation requires ExtGState dictionary
    #[allow(dead_code)]
    pub fn set_opacity(&mut self, _opacity: f64) {
        // TODO: Implement ExtGState with opacity when pdf-writer API supports it
        // For now, we'll use a workaround by adjusting color alpha
        // This is a limitation - we can't set global opacity easily
    }
    
    // ===== Drawing =====
    
    pub fn rect(&mut self, rect: OurRect, fill: bool, stroke: bool) {
        self.content.rect(
            rect.x as f32, 
            rect.y as f32, 
            rect.width as f32, 
            rect.height as f32
        );
        if fill {
            self.content.fill_nonzero();
        }
        if stroke {
            self.content.stroke();
        }
    }
    
    pub fn round_rect(&mut self, rect: OurRect, radius: f64, fill: bool, stroke: bool) {
        // Clamp radius to half of the smaller dimension
        let max_radius = rect.width.min(rect.height) / 2.0;
        let r = radius.min(max_radius).max(0.0);
        
        if r <= 0.0 {
            // No rounding, use regular rectangle
            self.rect(rect, fill, stroke);
            return;
        }
        
        let x = rect.x;
        let y = rect.y;
        let w = rect.width;
        let h = rect.height;
        
        // Control point offset for bezier curves (approximation for circular arc)
        // Using 0.55228475 * radius gives a good approximation of a quarter circle
        let c = r * 0.55228475;
        
        // Start from top-left corner (after rounded corner)
        self.content.move_to((x + r) as f32, (y + h) as f32);
        
        // Top edge
        self.content.line_to((x + w - r) as f32, (y + h) as f32);
        
        // Top-right rounded corner (bezier curve)
        self.content.cubic_to(
            (x + w - r + c) as f32, (y + h) as f32,  // Control point 1
            (x + w) as f32, (y + h - r + c) as f32,  // Control point 2
            (x + w) as f32, (y + h - r) as f32,      // End point
        );
        
        // Right edge
        self.content.line_to((x + w) as f32, (y + r) as f32);
        
        // Bottom-right rounded corner
        self.content.cubic_to(
            (x + w) as f32, (y + r - c) as f32,      // Control point 1
            (x + w - r + c) as f32, y as f32,        // Control point 2
            (x + w - r) as f32, y as f32,            // End point
        );
        
        // Bottom edge
        self.content.line_to((x + r) as f32, y as f32);
        
        // Bottom-left rounded corner
        self.content.cubic_to(
            (x + r - c) as f32, y as f32,            // Control point 1
            x as f32, (y + r - c) as f32,            // Control point 2
            x as f32, (y + r) as f32,                // End point
        );
        
        // Left edge
        self.content.line_to(x as f32, (y + h - r) as f32);
        
        // Top-left rounded corner
        self.content.cubic_to(
            x as f32, (y + h - r + c) as f32,        // Control point 1
            (x + r - c) as f32, (y + h) as f32,      // Control point 2
            (x + r) as f32, (y + h) as f32,          // End point
        );
        
        // Close path
        self.content.close_path();
        
        if fill {
            self.content.fill_nonzero();
        }
        if stroke {
            self.content.stroke();
        }
    }
    
    pub fn line(&mut self, x1: f64, y1: f64, x2: f64, y2: f64) {
        self.content.move_to(x1 as f32, y1 as f32);
        self.content.line_to(x2 as f32, y2 as f32);
        self.content.stroke();
    }
    
    // ===== Text =====
    
    pub fn set_font(&mut self, font_name: Name<'static>, size: f64) {
        self.state.font_name = font_name;
        self.state.font_size = size;
    }
    
    pub fn draw_string(&mut self, x: f64, y: f64, text: &str) {
        self.content.begin_text();
        self.content.set_font(self.state.font_name, self.state.font_size as f32);
        self.content.next_line(x as f32, y as f32);
        
        // Check if this is a Type0 font (TrueType font for Polish characters)
        // Type0 fonts use Identity-H encoding and need Unicode directly as CID
        let is_type0_font = {
            // Type0 fonts are typically named F4, F5, F6, etc. (F1-F3 are standard fonts)
            // We can check if font name starts with "F" and has a number > 3
            let font_name_bytes = self.state.font_name.0;
            if font_name_bytes.len() >= 2 && font_name_bytes[0] == b'F' {
                // Safely get the rest of the bytes (skip first byte)
                // Use get() to safely access bytes without panicking
                if let Some(rest_bytes) = font_name_bytes.get(1..) {
                    if let Ok(font_num_str) = std::str::from_utf8(rest_bytes) {
                    if let Ok(font_num) = font_num_str.parse::<i32>() {
                        font_num > 3 // F4, F5, F6, etc. are Type0 fonts
                        } else {
                            false
                        }
                    } else {
                        false
                    }
                } else {
                    false
                }
            } else {
                false
            }
        };
        
        if is_type0_font {
            // For Type0 fonts with Identity-H encoding, use Unicode directly as CID
            // Each Unicode character becomes a 2-byte CID (big-endian)
            let mut cid_bytes = Vec::new();
            for ch in text.chars() {
                let code_point = ch as u32;
                // Convert to 2-byte big-endian CID
                cid_bytes.push((code_point >> 8) as u8);
                cid_bytes.push((code_point & 0xFF) as u8);
            }
            self.content.show(Str(&cid_bytes));
        } else {
            // For standard fonts (Type1), convert Unicode to WinAnsiEncoding
            // This supports Polish characters (ą, ć, ę, ł, ń, ó, ś, ź, ż) and other Latin-1 extended characters
            let winansi_bytes = unicode_to_winansi(text);
            self.content.show(Str(&winansi_bytes));
        }
        self.content.end_text();
    }
    
    /// Draw text with justification using manual spacing
    /// This allows precise spacing control for word spacing adjustment
    /// segments: Vec of (text, spacing_offset) pairs
    /// spacing_offset is in points (will be converted to text space units)
    pub fn draw_string_justified(&mut self, x: f64, y: f64, segments: &[(String, f64)]) {
        self.content.begin_text();
        self.content.set_font(self.state.font_name, self.state.font_size as f32);
        self.content.next_line(x as f32, y as f32);
        
        // Check if this is a Type0 font
        let is_type0_font = {
            let font_name_bytes = self.state.font_name.0;
            if font_name_bytes.len() >= 2 && font_name_bytes[0] == b'F' {
                // Safely get the rest of the bytes (skip first byte)
                if let Some(rest_bytes) = font_name_bytes.get(1..) {
                    if let Ok(font_num_str) = std::str::from_utf8(rest_bytes) {
                        if let Ok(font_num) = font_num_str.parse::<i32>() {
                            font_num > 3
                        } else {
                            false
                        }
                    } else {
                        false
                    }
                } else {
                    false
                }
            } else {
                false
            }
        };
        
        // Draw segments with manual spacing
        for (text, spacing_offset) in segments {
            // Draw text segment
            if is_type0_font {
                // For Type0 fonts, convert Unicode to CID bytes
                let mut cid_bytes = Vec::new();
                for ch in text.chars() {
                    let code_point = ch as u32;
                    cid_bytes.push((code_point >> 8) as u8);
                    cid_bytes.push((code_point & 0xFF) as u8);
                }
                self.content.show(Str(&cid_bytes));
            } else {
                // For standard fonts, use WinAnsi encoding
                let winansi_bytes = unicode_to_winansi(text);
                self.content.show(Str(&winansi_bytes));
            }
            
            // Apply spacing offset by moving text position
            // spacing_offset is in points, convert to text space units (1/1000 of font size)
            if *spacing_offset != 0.0 {
                let offset_text_space = spacing_offset / self.state.font_size;
                self.content.next_line(offset_text_space as f32, 0.0);
            }
        }
        
        self.content.end_text();
    }
    
    // ===== Transformations =====
    
    pub fn translate(&mut self, x: f64, y: f64) {
        self.content.transform([1.0, 0.0, 0.0, 1.0, x as f32, y as f32]);
    }
    
    pub fn rotate(&mut self, angle_degrees: f64) {
        let angle_rad = angle_degrees.to_radians();
        let cos_a = angle_rad.cos() as f32;
        let sin_a = angle_rad.sin() as f32;
        self.content.transform([cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0]);
    }
    
    pub fn scale(&mut self, sx: f64, sy: f64) {
        self.content.transform([sx as f32, 0.0, 0.0, sy as f32, 0.0, 0.0]);
    }
    
    // ===== Line Styles =====
    
    pub fn set_line_width(&mut self, width: f64) {
        self.state.line_width = width;
        self.content.set_line_width(width as f32);
    }
    
    pub fn set_dash(&mut self, pattern: Vec<f64>, offset: f64) {
        self.state.dash_pattern = Some((pattern.clone(), offset));
        let pattern_f32: Vec<f32> = pattern.iter().map(|&x| x as f32).collect();
        self.content.set_dash_pattern(pattern_f32.iter().copied(), offset as f32);
    }
    
    // ===== Images =====
    
    pub fn draw_image(&mut self, image_name: Name<'static>, x: f64, y: f64, width: f64, height: f64) {
        self.content.save_state();
        // PDF transformation matrix: [a b c d e f]
        // Where:
        //   a = horizontal scaling (width)
        //   b = horizontal skew (0 for images)
        //   c = vertical skew (0 for images)
        //   d = vertical scaling (height)
        //   e = horizontal translation (x)
        //   f = vertical translation (y)
        // 
        // In PDF, Y-axis increases upward, and images are drawn from bottom-left corner.
        // ReportLab's drawImage uses: x, y, width, height where y is the bottom coordinate.
        // The transformation matrix scales the 1x1 unit image to width x height and translates it to (x, y).
        // Note: PDF images are 1x1 unit by default, so we scale by width and height.
        // The y coordinate is already calculated correctly (baseline_y - descent) in the renderer.
        // 
        // IMPORTANT: The transformation matrix positions the bottom-left corner of the image at (x, y).
        // The image is then scaled to width x height from that point.
        let image_name_str = String::from_utf8_lossy(image_name.0);
        eprintln!("   Canvas.draw_image: name={}, transform=[{}, 0, 0, {}, {}, {}]", 
            image_name_str, width, height, x, y);
        self.content.transform([width as f32, 0.0, 0.0, height as f32, x as f32, y as f32]);
        self.content.x_object(image_name);
        self.content.restore_state();
    }
}

impl Default for PdfCanvas {
    fn default() -> Self {
        Self::new()
    }
}

