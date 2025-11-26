//! High-level Canvas-like API wrapper for pdf-writer
//!
//! Provides a ReportLab-like interface for canvas operations

use pdf_writer::{Content, Name, Str};
use std::collections::HashMap;

use crate::types::{Color, Rect};

/// Map Unicode code point to CID (Character ID) for Type0 fonts
pub type CidMap = HashMap<u32, u16>;

/// Canvas state for graphics operations
#[derive(Clone)]
struct CanvasState {
    fill_color: Color,
    stroke_color: Color,
    line_width: f64,
    font_name: Name<'static>,
    font_size: f64,
    dash_pattern: Option<(Vec<f64>, f64)>,
}

impl Default for CanvasState {
    fn default() -> Self {
        Self {
            fill_color: Color::black(),
            stroke_color: Color::black(),
            line_width: 1.0,
            font_name: Name(b"F1"), // Default font (Helvetica)
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
    // Cache for CID bytes: (code_point) -> [u8; 2]
    cid_cache: HashMap<u32, [u8; 2]>,
    cached_font: Option<Name<'static>>,
}

impl PdfCanvas {
    pub fn new() -> Self {
        Self {
            content: Content::new(),
            state: CanvasState::default(),
            state_stack: Vec::new(),
            cid_cache: HashMap::new(),
            cached_font: None,
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

    /// Get current font name
    pub fn get_font_name(&self) -> Name<'static> {
        self.state.font_name
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

    #[inline]
    pub fn set_fill_color(&mut self, color: Color) {
        self.state.fill_color = color;
        let (r, g, b) = (color.r as f32, color.g as f32, color.b as f32);
        self.content.set_fill_rgb(r, g, b);
    }

    #[inline]
    pub fn set_stroke_color(&mut self, color: Color) {
        self.state.stroke_color = color;
        let (r, g, b) = (color.r as f32, color.g as f32, color.b as f32);
        self.content.set_stroke_rgb(r, g, b);
    }

    #[inline]
    pub fn set_line_width(&mut self, width: f64) {
        self.state.line_width = width;
        self.content.set_line_width(width as f32);
    }

    pub fn set_dash(&mut self, pattern: Vec<f64>, offset: f64) {
        self.state.dash_pattern = Some((pattern.clone(), offset));
        let pattern_f32: Vec<f32> = pattern.iter().map(|&x| x as f32).collect();
        self.content
            .set_dash_pattern(pattern_f32.iter().copied(), offset as f32);
    }

    #[inline]
    pub fn set_font(&mut self, font_name: Name<'static>, size: f64) {
        // Clear CID cache if font changed
        if self.cached_font != Some(font_name) {
            self.cid_cache.clear();
            self.cached_font = Some(font_name);
        }
        self.state.font_name = font_name;
        self.state.font_size = size;
    }

    pub fn set_ext_graphics_state(&mut self, name: Name<'static>) {
        self.content.set_parameters(name);
    }

    // ===== Drawing =====

    #[inline]
    pub fn rect(&mut self, rect: Rect, fill: bool, stroke: bool) {
        self.content.rect(
            rect.x as f32,
            rect.y as f32,
            rect.width as f32,
            rect.height as f32,
        );
        if fill {
            self.content.fill_nonzero();
        }
        if stroke {
            self.content.stroke();
        }
    }

    pub fn round_rect(&mut self, rect: Rect, radius: f64, fill: bool, stroke: bool) {
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
        let c = r * 0.55228475;

        // Start from top-left corner (after rounded corner)
        self.content.move_to((x + r) as f32, (y + h) as f32);

        // Top edge
        self.content.line_to((x + w - r) as f32, (y + h) as f32);

        // Top-right rounded corner (bezier curve)
        self.content.cubic_to(
            (x + w - r + c) as f32,
            (y + h) as f32,
            (x + w) as f32,
            (y + h - r + c) as f32,
            (x + w) as f32,
            (y + h - r) as f32,
        );

        // Right edge
        self.content.line_to((x + w) as f32, (y + r) as f32);

        // Bottom-right rounded corner
        self.content.cubic_to(
            (x + w) as f32,
            (y + r - c) as f32,
            (x + w - r + c) as f32,
            y as f32,
            (x + w - r) as f32,
            y as f32,
        );

        // Bottom edge
        self.content.line_to((x + r) as f32, y as f32);

        // Bottom-left rounded corner
        self.content.cubic_to(
            (x + r - c) as f32,
            y as f32,
            x as f32,
            (y + r - c) as f32,
            x as f32,
            (y + r) as f32,
        );

        // Left edge
        self.content.line_to(x as f32, (y + h - r) as f32);

        // Top-left rounded corner
        self.content.cubic_to(
            x as f32,
            (y + h - r + c) as f32,
            (x + r - c) as f32,
            (y + h) as f32,
            (x + r) as f32,
            (y + h) as f32,
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

    #[inline]
    pub fn line(&mut self, x1: f64, y1: f64, x2: f64, y2: f64) {
        self.content.move_to(x1 as f32, y1 as f32);
        self.content.line_to(x2 as f32, y2 as f32);
        self.content.stroke();
    }

    // ===== Text =====

    /// Draw text string with a Type0 font (Identity-H).
    /// All fonts are expected to have a CID map; we panic otherwise.
    #[inline]
    pub fn draw_string(&mut self, x: f64, y: f64, text: &str, cid_map: &CidMap) {
        // Set fill color for text (text uses fill color, not stroke color)
        // Note: We don't check if color changed here because text rendering
        // typically uses the same color for multiple strings, and the check
        // is already done in set_fill_color if called separately
        let (r, g, b) = (
            self.state.fill_color.r as f32,
            self.state.fill_color.g as f32,
            self.state.fill_color.b as f32,
        );
        self.content.set_fill_rgb(r, g, b);

        self.content.begin_text();
        self.content
            .set_font(self.state.font_name, self.state.font_size as f32);
        self.content.next_line(x as f32, y as f32);

        // Type0 font: convert Unicode code points to CIDs using the map
        // Use cache to avoid repeated lookups for the same characters
        let mut cid_bytes = Vec::with_capacity(text.len() * 2);
        
        // Pre-cache space CID for fallback
        let space_cid_bytes = *self.cid_cache.entry(0x0020).or_insert_with(|| {
            if let Some(&space_cid) = cid_map.get(&0x0020) {
                [(space_cid >> 8) as u8, (space_cid & 0xFF) as u8]
            } else {
                [0, 0]
            }
        });
        
        for ch in text.chars() {
            let code_point = ch as u32;
            let cid_byte_pair = *self.cid_cache.entry(code_point).or_insert_with(|| {
                if let Some(&cid) = cid_map.get(&code_point) {
                    // Convert CID to 2-byte big-endian
                    [(cid >> 8) as u8, (cid & 0xFF) as u8]
                } else {
                    // Fallback to space or .notdef
                    space_cid_bytes
                }
            });
            cid_bytes.extend_from_slice(&cid_byte_pair);
        }
        // Use show_text if available (more efficient), otherwise fall back to show
        // Note: pdf-writer may not have show_text, so we use show
        self.content.show(Str(&cid_bytes));
        self.content.end_text();
    }

    // ===== Transformations =====

    #[inline]
    pub fn translate(&mut self, x: f64, y: f64) {
        self.content
            .transform([1.0, 0.0, 0.0, 1.0, x as f32, y as f32]);
    }

    #[inline]
    pub fn rotate(&mut self, angle_degrees: f64) {
        let angle_rad = angle_degrees.to_radians();
        let cos_a = angle_rad.cos() as f32;
        let sin_a = angle_rad.sin() as f32;
        self.content
            .transform([cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0]);
    }

    #[inline]
    pub fn scale(&mut self, sx: f64, sy: f64) {
        self.content
            .transform([sx as f32, 0.0, 0.0, sy as f32, 0.0, 0.0]);
    }

    pub fn transform(&mut self, matrix: [f32; 6]) {
        self.content.transform(matrix);
    }

    // ===== Images =====

    pub fn draw_image(
        &mut self,
        image_name: Name<'static>,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
    ) {
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
        self.content
            .transform([width as f32, 0.0, 0.0, height as f32, x as f32, y as f32]);
        self.content.x_object(image_name);
        self.content.restore_state();
    }
}

impl Default for PdfCanvas {
    fn default() -> Self {
        Self::new()
    }
}
