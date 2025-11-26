//! Simplified Canvas API for Rust PDF renderer
//! 
//! This module provides a minimal canvas-like API that matches ReportLab's Canvas operations.
//! All business logic stays in Python - Rust only handles low-level PDF operations.

use pdf_writer::{Pdf, Content, Ref, Name, Finish};
use std::collections::HashMap;

/// Color representation (RGB)
#[derive(Clone, Copy, Debug)]
pub struct Color {
    pub r: f64,
    pub g: f64,
    pub b: f64,
}

impl Color {
    pub fn from_rgb(r: f64, g: f64, b: f64) -> Self {
        Self { r, g, b }
    }
    
    pub fn black() -> Self {
        Self { r: 0.0, g: 0.0, b: 0.0 }
    }
    
    pub fn white() -> Self {
        Self { r: 1.0, g: 1.0, b: 1.0 }
    }
}

/// Transform matrix (6 values: a, b, c, d, e, f)
#[derive(Clone, Debug)]
pub struct Transform {
    pub a: f64,
    pub b: f64,
    pub c: f64,
    pub d: f64,
    pub e: f64,
    pub f: f64,
}

impl Transform {
    pub fn identity() -> Self {
        Self {
            a: 1.0, b: 0.0, c: 0.0,
            d: 1.0, e: 0.0, f: 0.0,
        }
    }
}

/// Canvas state (for saveState/restoreState)
#[derive(Clone, Debug)]
struct CanvasState {
    fill_color: Color,
    stroke_color: Color,
    line_width: f64,
    dash_pattern: Option<Vec<f64>>,
    font_name: String,
    font_size: f64,
    transform: Transform,
}

impl Default for CanvasState {
    fn default() -> Self {
        Self {
            fill_color: Color::black(),
            stroke_color: Color::black(),
            line_width: 1.0,
            dash_pattern: None,
            font_name: "Helvetica".to_string(),
            font_size: 12.0,
            transform: Transform::identity(),
        }
    }
}

/// Simple Canvas for rendering a single page
/// This is a minimal implementation that only handles canvas operations.
pub struct SimpleCanvas {
    content: Content,
    state: CanvasState,
    state_stack: Vec<CanvasState>,
    // Font registry (simple - just track font names)
    font_registry: HashMap<String, Name<'static>>,
    next_font_id: u32,
}

impl SimpleCanvas {
    pub fn new() -> Self {
        let mut canvas = Self {
            content: Content::new(),
            state: CanvasState::default(),
            state_stack: Vec::new(),
            font_registry: HashMap::new(),
            next_font_id: 1,
        };
        
        // Initialize with default state
        canvas.apply_state();
        canvas
    }
    
    /// Apply current state to content
    fn apply_state(&mut self) {
        // Set fill color
        self.content.set_fill_rgb(
            self.state.fill_color.r as f32,
            self.state.fill_color.g as f32,
            self.state.fill_color.b as f32,
        );
        
        // Set stroke color
        self.content.set_stroke_rgb(
            self.state.stroke_color.r as f32,
            self.state.stroke_color.g as f32,
            self.state.stroke_color.b as f32,
        );
        
        // Set line width
        self.content.set_line_width(self.state.line_width as f32);
        
        // Set dash pattern
        if let Some(ref dash) = self.state.dash_pattern {
            if dash.len() >= 2 {
                self.content.set_dash(
                    dash.iter().map(|&v| v as f32).collect::<Vec<_>>().as_slice(),
                    dash[0] as f32, // phase
                );
            }
        } else {
            self.content.set_dash(&[], 0.0);
        }
        
        // Apply transform
        self.content.transform([
            self.state.transform.a as f32,
            self.state.transform.b as f32,
            self.state.transform.c as f32,
            self.state.transform.d as f32,
            self.state.transform.e as f32,
            self.state.transform.f as f32,
        ]);
    }
    
    // Canvas operations (matching ReportLab API)
    
    pub fn save_state(&mut self) {
        self.state_stack.push(self.state.clone());
    }
    
    pub fn restore_state(&mut self) {
        if let Some(prev_state) = self.state_stack.pop() {
            self.state = prev_state;
            self.apply_state();
        }
    }
    
    pub fn set_fill_color(&mut self, color: Color) {
        self.state.fill_color = color;
        self.content.set_fill_rgb(
            color.r as f32,
            color.g as f32,
            color.b as f32,
        );
    }
    
    pub fn set_stroke_color(&mut self, color: Color) {
        self.state.stroke_color = color;
        self.content.set_stroke_rgb(
            color.r as f32,
            color.g as f32,
            color.b as f32,
        );
    }
    
    pub fn set_line_width(&mut self, width: f64) {
        self.state.line_width = width;
        self.content.set_line_width(width as f32);
    }
    
    pub fn set_dash(&mut self, pattern: Vec<f64>) {
        if pattern.is_empty() {
            self.state.dash_pattern = None;
            self.content.set_dash(&[], 0.0);
        } else {
            self.state.dash_pattern = Some(pattern.clone());
            let phase = if pattern.len() > 0 { pattern[0] } else { 0.0 };
            self.content.set_dash(
                pattern.iter().map(|&v| v as f32).collect::<Vec<_>>().as_slice(),
                phase as f32,
            );
        }
    }
    
    pub fn set_font(&mut self, name: &str, size: f64) {
        self.state.font_name = name.to_string();
        self.state.font_size = size;
        // Note: Font registration is handled separately
    }
    
    pub fn rect(&mut self, x: f64, y: f64, width: f64, height: f64, fill: bool, stroke: bool) {
        self.content.rect(x as f32, y as f32, width as f32, height as f32);
        if fill {
            self.content.fill();
        }
        if stroke {
            self.content.stroke();
        }
    }
    
    pub fn round_rect(&mut self, x: f64, y: f64, width: f64, height: f64, radius: f64, fill: bool, stroke: bool) {
        // Simple rounded rect using bezier curves
        // For now, use regular rect (can be improved later)
        self.rect(x, y, width, height, fill, stroke);
    }
    
    pub fn line(&mut self, x1: f64, y1: f64, x2: f64, y2: f64) {
        self.content.move_to(x1 as f32, y1 as f32);
        self.content.line_to(x2 as f32, y2 as f32);
        self.content.stroke();
    }
    
    pub fn draw_string(&mut self, x: f64, y: f64, text: &str) {
        // Note: This is a placeholder - actual text rendering needs font handling
        // For now, we'll need to handle this at a higher level
        // TODO: Implement proper text rendering with font support
    }
    
    pub fn translate(&mut self, x: f64, y: f64) {
        let t = &mut self.state.transform;
        t.e += x;
        t.f += y;
        self.content.transform([
            t.a as f32, t.b as f32,
            t.c as f32, t.d as f32,
            t.e as f32, t.f as f32,
        ]);
    }
    
    pub fn rotate(&mut self, angle: f64) {
        // Rotation is complex - for now, use transform
        // TODO: Implement proper rotation
    }
    
    pub fn scale(&mut self, x: f64, y: f64) {
        let t = &mut self.state.transform;
        t.a *= x;
        t.d *= y;
        self.content.transform([
            t.a as f32, t.b as f32,
            t.c as f32, t.d as f32,
            t.e as f32, t.f as f32,
        ]);
    }
    
    pub fn transform(&mut self, matrix: [f64; 6]) {
        self.state.transform = Transform {
            a: matrix[0], b: matrix[1],
            c: matrix[2], d: matrix[3],
            e: matrix[4], f: matrix[5],
        };
        self.content.transform([
            matrix[0] as f32, matrix[1] as f32,
            matrix[2] as f32, matrix[3] as f32,
            matrix[4] as f32, matrix[5] as f32,
        ]);
    }
    
    /// Finish rendering and return content bytes
    pub fn finish(self) -> Vec<u8> {
        self.content.finish()
    }
}

