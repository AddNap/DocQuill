//! Text layout and line breaking
//!
//! This module provides text layout functionality including:
//! - Line breaking (word wrapping)
//! - Justification (word spacing adjustment)
//! - Text measurement
//! - Baseline and line height calculations

use crate::font_registry::FontRegistry;
use pdf_writer::Pdf;
use pyo3::prelude::*;

/// Represents a text run (span) with its style
#[derive(Debug, Clone)]
pub struct TextRun {
    pub text: String,
    pub font_name: String,
    pub font_size: f64,
    pub bold: bool,
    pub italic: bool,
}

/// Represents a line of text with its runs
#[derive(Debug, Clone)]
pub struct TextLine {
    pub runs: Vec<TextRun>,
    pub width: f64,
    pub height: f64,
    pub baseline: f64,
}

/// Line breaker for wrapping text
pub struct LineBreaker {
    max_width: f64,
}

impl LineBreaker {
    pub fn new(max_width: f64) -> Self {
        Self { max_width }
    }
    
    /// Break text into lines using simple word-based breaking
    /// This is a basic implementation - for production, consider UAX-14
    pub fn break_text(
        &self,
        text: &str,
        font_name: &str,
        font_size: f64,
        pdf: &mut Pdf,
        fonts_registry: &mut FontRegistry,
    ) -> pyo3::PyResult<Vec<TextLine>> {
        // For now, use simple space-based breaking
        // TODO: Implement UAX-14 Unicode line breaking
        
        let words: Vec<&str> = text.split_whitespace().collect();
        let mut lines = Vec::new();
        let mut current_line = Vec::new();
        let mut current_width = 0.0;
        
        // Get font reference for measurement
        let font_ref = fonts_registry.resolve_for_text(pdf, font_name, text)?;
        
        // Simple word spacing (approximate)
        let space_width = font_size * 0.3; // Approximate space width
        
        for word in words {
            // Measure word width (approximate: font_size * char_count * 0.6)
            let word_width = word.chars().count() as f64 * font_size * 0.6;
            
            // Check if word fits on current line
            let needed_width = if current_line.is_empty() {
                word_width
            } else {
                current_width + space_width + word_width
            };
            
            if needed_width <= self.max_width || current_line.is_empty() {
                // Add word to current line
                if !current_line.is_empty() {
                    current_width += space_width;
                }
                current_line.push(word);
                current_width += word_width;
            } else {
                // Finish current line and start new one
                if !current_line.is_empty() {
                    let line_text = current_line.join(" ");
                    lines.push(TextLine {
                        runs: vec![TextRun {
                            text: line_text,
                            font_name: font_name.to_string(),
                            font_size,
                            bold: false,
                            italic: false,
                        }],
                        width: current_width,
                        height: font_size * 1.2, // Approximate line height
                        baseline: font_size * 0.8, // Approximate baseline
                    });
                }
                
                // Start new line with current word
                current_line = vec![word];
                current_width = word_width;
            }
        }
        
        // Add last line if not empty
        if !current_line.is_empty() {
            let line_text = current_line.join(" ");
            lines.push(TextLine {
                runs: vec![TextRun {
                    text: line_text,
                    font_name: font_name.to_string(),
                    font_size,
                    bold: false,
                    italic: false,
                }],
                width: current_width,
                height: font_size * 1.2,
                baseline: font_size * 0.8,
            });
        }
        
        Ok(lines)
    }
}

/// Justification calculator for word spacing adjustment
pub struct Justifier {
    line_width: f64,
    content_width: f64,
}

impl Justifier {
    pub fn new(line_width: f64, content_width: f64) -> Self {
        Self {
            line_width,
            content_width,
        }
    }
    
    /// Calculate word spacing adjustment for justification
    /// Returns spacing to add between words
    pub fn calculate_spacing(&self, word_count: usize) -> f64 {
        if word_count <= 1 {
            return 0.0;
        }
        
        let extra_space = self.line_width - self.content_width;
        let spaces_count = (word_count - 1) as f64;
        
        if spaces_count > 0.0 {
            extra_space / spaces_count
        } else {
            0.0
        }
    }
    
    /// Generate PDF TJ array with spacing adjustments for justification
    /// Returns vector of (text, spacing_offset) pairs
    pub fn generate_tj_array(&self, words: &[&str]) -> Vec<(String, f64)> {
        let spacing = self.calculate_spacing(words.len());
        let mut result = Vec::new();
        
        for (i, word) in words.iter().enumerate() {
            result.push((word.to_string(), 0.0));
            
            // Add spacing after word (except last)
            if i < words.len() - 1 {
                result.push((" ".to_string(), spacing));
            }
        }
        
        result
    }
}

/// Font metrics for baseline and line height calculations
#[derive(Debug, Clone)]
pub struct FontMetrics {
    pub ascent: f64,
    pub descent: f64,
    pub leading: f64,
    pub line_gap: f64,
}

impl FontMetrics {
    /// Calculate line height from metrics
    /// scale: font_size / units_per_em (typically 1000 or 2048)
    pub fn line_height(&self, scale: f64) -> f64 {
        (self.ascent - self.descent) * scale + self.leading
    }
    
    /// Calculate baseline offset from top
    /// Returns offset from top of line to baseline
    pub fn baseline_offset(&self, scale: f64) -> f64 {
        self.ascent * scale
    }
    
    /// Get default metrics (approximate for standard fonts)
    pub fn default(font_size: f64) -> Self {
        // Approximate metrics for standard fonts
        // In production, these should come from TTF/OTF font files
        Self {
            ascent: font_size * 0.8,
            descent: font_size * 0.2,
            leading: font_size * 0.1,
            line_gap: font_size * 0.05,
        }
    }
    
    /// Extract metrics from TTF font file
    /// Returns metrics scaled to font_size
    pub fn from_ttf(font_data: &[u8], font_size: f64) -> pyo3::PyResult<Self> {
        use ttf_parser::Face;
        
        let face = Face::parse(font_data, 0)
            .map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to parse TTF font: {}", e)
            ))?;
        
        let units_per_em = face.units_per_em() as f64;
        let scale = font_size / units_per_em;
        
        // Get metrics from font
        let ascender = face.ascender() as f64;
        let descender = face.descender() as f64;
        let line_gap = face.line_gap() as f64;
        
        // Scale to font size
        let ascent = ascender * scale;
        let descent = descender.abs() * scale; // descender is usually negative
        let line_gap_scaled = line_gap * scale;
        
        // Leading is typically 20% of font size or line_gap, whichever is larger
        let leading = (line_gap_scaled).max(font_size * 0.2);
        
        Ok(Self {
            ascent,
            descent,
            leading,
            line_gap: line_gap_scaled,
        })
    }
}

/// Kerning utilities for adjusting character spacing
pub struct Kerning {
    kern_pairs: std::collections::HashMap<(u16, u16), f64>, // (left_glyph, right_glyph) -> kern_value
    units_per_em: f64,
}

impl Kerning {
    /// Extract kerning pairs from TTF font
    pub fn from_ttf(font_data: &[u8]) -> pyo3::PyResult<Self> {
        use ttf_parser::Face;
        
        let face = Face::parse(font_data, 0)
            .map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to parse TTF font for kerning: {}", e)
            ))?;
        
        let units_per_em = face.units_per_em() as f64;
        let mut kern_pairs = std::collections::HashMap::new();
        
        // Extract kerning pairs from font
        // Note: ttf-parser provides kerning via subtables
        // For now, we'll use a simplified approach
        // TODO: Implement full kerning table parsing
        
        Ok(Self {
            kern_pairs,
            units_per_em,
        })
    }
    
    /// Get kerning value for a pair of characters
    /// Returns adjustment in points (scaled to font_size)
    pub fn get_kern(&self, left_char: char, right_char: char, font_size: f64) -> f64 {
        // For now, return 0 (no kerning)
        // TODO: Implement actual kerning lookup
        // This would require:
        // 1. Convert chars to glyph IDs
        // 2. Look up (left_glyph, right_glyph) in kern_pairs
        // 3. Scale kern value to font_size
        0.0
    }
    
    /// Apply kerning to text segments
    /// Returns vector of (text, spacing_offset) pairs with kerning adjustments
    pub fn apply_kerning(&self, text: &str, font_size: f64) -> Vec<(String, f64)> {
        let mut result = Vec::new();
        let chars: Vec<char> = text.chars().collect();
        
        if chars.is_empty() {
            return result;
        }
        
        // Add first character
        result.push((chars[0].to_string(), 0.0));
        
        // Apply kerning between consecutive characters
        for i in 1..chars.len() {
            let kern_value = self.get_kern(chars[i-1], chars[i], font_size);
            result.push((chars[i].to_string(), kern_value));
        }
        
        result
    }
}

