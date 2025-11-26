//! Rust PDF Canvas - Minimal PDF renderer with canvas operations only
//!
//! This module provides a minimal PDF renderer that only handles canvas operations.
//! All business logic stays in Python - Rust only handles low-level PDF operations.

mod canvas;
mod font_utils;
mod image_utils;
mod types;

use pdf_writer::{Finish, Name, Pdf, Ref};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

use canvas::PdfCanvas;
use types::{Color, Rect};

/// Map Unicode code point to CID (Character ID) for Type0 fonts
pub type CidMap = HashMap<u32, u16>;

// CanvasCommand is now parsed directly from Python dicts in canvas_run_batch
// This avoids pyo3 enum parsing complexity while maintaining zero-copy performance

/// Main PDF renderer class - minimal implementation
#[pyclass]
pub struct PdfCanvasRenderer {
    pdf: Pdf,
    output_path: String,
    current_page: Option<(Ref, Ref, PdfCanvas)>, // (page_id, content_id, canvas)
    current_page_info: Option<(Ref, f64, f64)>,  // (page_id, page_width, page_height)
    pages: Vec<Ref>,
    page_tree_id: Option<Ref>,
    catalog_id: Option<Ref>,
    next_ref_id: i32,
    // Font registry (simple - just track font names and IDs)
    font_registry: HashMap<String, (Name<'static>, Ref)>, // font_name -> (Name, Ref)
    fonts_used_on_current_page: HashMap<Name<'static>, Ref>, // font_name -> font_id
    next_font_id: u32,
    // CID maps for Type0 fonts: font_name -> Unicode -> CID mapping
    type0_cid_maps: HashMap<Name<'static>, CidMap>, // Maps font Name to Unicode->CID mapping
    // ExtGState registry (opacity, etc.)
    ext_graphics_states: HashMap<u32, (Name<'static>, Ref)>, // alpha_key -> (Name, Ref)
    ext_graphics_states_used_on_current_page: HashMap<Name<'static>, Ref>,
    // Image registry
    images_used_on_current_page: HashMap<Name<'static>, Ref>,
    images_registry: HashMap<String, (Ref, Name<'static>)>,
    next_image_id: i32,
}

#[pymethods]
impl PdfCanvasRenderer {
    #[new]
    fn new(output_path: String, _page_width: f64, _page_height: f64) -> Self {
        let mut pdf = Pdf::new();

        // Create references
        let catalog_id = Ref::new(1);
        let page_tree_id = Ref::new(2);

        // Set up catalog
        pdf.catalog(catalog_id).pages(page_tree_id);

        // Try to register DejaVu Sans as default font (better Unicode support, especially for Polish)
        let mut font_registry = HashMap::new();
        let default_font_id = Ref::new(3);
        let mut next_ref = 4;

        // CID maps for Type0 fonts
        let mut type0_cid_maps = HashMap::new();

        // Try common DejaVu Sans paths
        if let Some(dejavu_path) = font_utils::find_dejavu_sans() {
            if let Ok(font_data) = font_utils::load_font_file(&dejavu_path) {
                if let Ok((font_name, cid_map)) = font_utils::add_truetype_font(
                    &mut pdf,
                    &font_data,
                    default_font_id,
                    &mut next_ref,
                ) {
                    font_registry.insert("DejaVu Sans".to_string(), (font_name, default_font_id));
                    font_registry.insert("DejaVuSans".to_string(), (font_name, default_font_id));
                    type0_cid_maps.insert(font_name, cid_map);
                }
            }
        }

        if font_registry.is_empty() {
            panic!(
                "DejaVu Sans TTF not found. Place DejaVuSans.ttf in assets/fonts/ \
or install it system-wide so Unicode text can be rendered."
            );
        }

        // Register DejaVu Sans variants if available
        // Bold
        if let Some(bold_path) = font_utils::find_dejavu_sans_bold() {
            if let Ok(font_data) = font_utils::load_font_file(&bold_path) {
                let bold_font_id = Ref::new(next_ref);
                next_ref += 1;
                if let Ok((font_name, cid_map)) =
                    font_utils::add_truetype_font(&mut pdf, &font_data, bold_font_id, &mut next_ref)
                {
                    font_registry.insert("DejaVu Sans-Bold".to_string(), (font_name, bold_font_id));
                    font_registry.insert("DejaVuSans-Bold".to_string(), (font_name, bold_font_id));
                    type0_cid_maps.insert(font_name, cid_map);
                }
            }
        }

        // Italic
        if let Some(italic_path) = font_utils::find_dejavu_sans_italic() {
            if let Ok(font_data) = font_utils::load_font_file(&italic_path) {
                let italic_font_id = Ref::new(next_ref);
                next_ref += 1;
                if let Ok((font_name, cid_map)) = font_utils::add_truetype_font(
                    &mut pdf,
                    &font_data,
                    italic_font_id,
                    &mut next_ref,
                ) {
                    font_registry.insert(
                        "DejaVu Sans-Oblique".to_string(),
                        (font_name, italic_font_id),
                    );
                    font_registry.insert(
                        "DejaVuSans-Oblique".to_string(),
                        (font_name, italic_font_id),
                    );
                    font_registry.insert(
                        "DejaVu Sans-Italic".to_string(),
                        (font_name, italic_font_id),
                    );
                    font_registry
                        .insert("DejaVuSans-Italic".to_string(), (font_name, italic_font_id));
                    type0_cid_maps.insert(font_name, cid_map);
                }
            }
        }

        // Bold Italic
        if let Some(bold_italic_path) = font_utils::find_dejavu_sans_bold_italic() {
            if let Ok(font_data) = font_utils::load_font_file(&bold_italic_path) {
                let bold_italic_font_id = Ref::new(next_ref);
                next_ref += 1;
                if let Ok((font_name, cid_map)) = font_utils::add_truetype_font(
                    &mut pdf,
                    &font_data,
                    bold_italic_font_id,
                    &mut next_ref,
                ) {
                    font_registry.insert(
                        "DejaVu Sans-BoldOblique".to_string(),
                        (font_name, bold_italic_font_id),
                    );
                    font_registry.insert(
                        "DejaVuSans-BoldOblique".to_string(),
                        (font_name, bold_italic_font_id),
                    );
                    font_registry.insert(
                        "DejaVu Sans-BoldItalic".to_string(),
                        (font_name, bold_italic_font_id),
                    );
                    font_registry.insert(
                        "DejaVuSans-BoldItalic".to_string(),
                        (font_name, bold_italic_font_id),
                    );
                    type0_cid_maps.insert(font_name, cid_map);
                }
            }
        }

        Self {
            pdf,
            output_path,
            current_page: None,
            current_page_info: None,
            pages: vec![],
            page_tree_id: Some(page_tree_id),
            catalog_id: Some(catalog_id),
            next_ref_id: next_ref,
            font_registry,
            fonts_used_on_current_page: HashMap::new(),
            next_font_id: 2,
            type0_cid_maps, // CID maps for Type0 fonts
            ext_graphics_states: HashMap::new(),
            ext_graphics_states_used_on_current_page: HashMap::new(),
            images_used_on_current_page: HashMap::new(),
            images_registry: HashMap::new(),
            next_image_id: 2000, // Start from 2000 to avoid conflicts
        }
    }

    /// Add a new page
    fn new_page(&mut self, page_width: f64, page_height: f64) -> PyResult<()> {
        // Save current page content and finalize page
        if let Some((_page_id, content_id, canvas)) = self.current_page.take() {
            let content_bytes = canvas.finish();
            self.pdf.stream(content_id, &content_bytes);

            // Create and finish the previous page
            if let Some((prev_page_info_id, prev_page_width, prev_page_height)) =
                self.current_page_info.take()
            {
                let mut page = self.pdf.page(prev_page_info_id);
                page.media_box(pdf_writer::Rect::new(
                    0.0,
                    0.0,
                    prev_page_width as f32,
                    prev_page_height as f32,
                ));
                if let Some(page_tree_id) = self.page_tree_id {
                    page.parent(page_tree_id);
                }
                page.contents(content_id);

                // Add fonts and images to resources in a single dictionary
                {
                    let mut resources = page.resources();
                    if !self.fonts_used_on_current_page.is_empty() {
                        let mut fonts = resources.fonts();
                        for (font_name, font_id) in &self.fonts_used_on_current_page {
                            fonts.pair(*font_name, *font_id);
                        }
                    }
                    if !self.images_used_on_current_page.is_empty() {
                        let mut xobject_dict = resources.x_objects();
                        for (image_name, image_id) in &self.images_used_on_current_page {
                            xobject_dict.pair(*image_name, *image_id);
                        }
                    }
                    if !self.ext_graphics_states_used_on_current_page.is_empty() {
                        let mut ext_states = resources.ext_g_states();
                        for (name, gs_ref) in &self.ext_graphics_states_used_on_current_page {
                            ext_states.pair(*name, *gs_ref);
                        }
                    }
                }

                page.finish();
            }
        }

        // Clear images and fonts used on previous page
        self.images_used_on_current_page.clear();
        self.fonts_used_on_current_page.clear();
        self.ext_graphics_states_used_on_current_page.clear();

        // Create new page references
        let page_id = Ref::new(self.next_ref_id);
        self.next_ref_id += 1;
        let content_id = Ref::new(self.next_ref_id);
        self.next_ref_id += 1;

        // Store page info
        self.current_page_info = Some((page_id, page_width, page_height));

        // Create new canvas
        let canvas = PdfCanvas::new();
        self.current_page = Some((page_id, content_id, canvas));

        // Add to pages list
        self.pages.push(page_id);

        // Always register the Unicode-safe default font for the page
        let (default_font_name, default_font_id) = self
            .font_registry
            .get("DejaVu Sans")
            .or_else(|| self.font_registry.get("DejaVuSans"))
            .copied()
            .expect("DejaVu Sans Type0 font must be registered");
        if !self
            .fonts_used_on_current_page
            .contains_key(&default_font_name)
        {
            self.fonts_used_on_current_page
                .insert(default_font_name, default_font_id);
        }

        Ok(())
    }

    /// Save PDF to file
    fn save(&mut self) -> PyResult<()> {
        // Save current page content and finalize page
        if let Some((_page_id, content_id, canvas)) = self.current_page.take() {
            let content_bytes = canvas.finish();
            self.pdf.stream(content_id, &content_bytes);

            // Create and finish the page
            if let Some((page_info_id, page_width, page_height)) = self.current_page_info.take() {
                let mut page = self.pdf.page(page_info_id);
                page.media_box(pdf_writer::Rect::new(
                    0.0,
                    0.0,
                    page_width as f32,
                    page_height as f32,
                ));
                if let Some(page_tree_id) = self.page_tree_id {
                    page.parent(page_tree_id);
                }
                page.contents(content_id);

                // Add resources (fonts, images, ext graphics states)
                {
                    let mut resources = page.resources();
                    if !self.fonts_used_on_current_page.is_empty() {
                        let mut fonts = resources.fonts();
                        for (font_name, font_id) in &self.fonts_used_on_current_page {
                            fonts.pair(*font_name, *font_id);
                        }
                    }
                    if !self.images_used_on_current_page.is_empty() {
                        let mut xobject_dict = resources.x_objects();
                        for (image_name, image_id) in &self.images_used_on_current_page {
                            xobject_dict.pair(*image_name, *image_id);
                        }
                    }
                    if !self.ext_graphics_states_used_on_current_page.is_empty() {
                        let mut ext_states = resources.ext_g_states();
                        for (name, gs_ref) in &self.ext_graphics_states_used_on_current_page {
                            ext_states.pair(*name, *gs_ref);
                        }
                    }
                }

                page.finish();
            }
        }

        // Update page tree
        if let Some(page_tree_id) = self.page_tree_id {
            let mut page_tree = self.pdf.pages(page_tree_id);
            page_tree.kids(self.pages.iter().cloned());
            page_tree.count(self.pages.len() as i32);
        }

        // Finish PDF and get bytes
        let pdf = std::mem::replace(&mut self.pdf, Pdf::new());
        let pdf_bytes = pdf.finish();

        // Write to file
        std::fs::write(&self.output_path, pdf_bytes).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
                "Failed to write PDF to {}: {}",
                self.output_path, e
            ))
        })?;

        Ok(())
    }

    // ===== Canvas Operations =====

    /// Save canvas state
    fn canvas_save_state(&mut self) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        canvas.save_state();
        Ok(())
    }

    /// Restore canvas state
    fn canvas_restore_state(&mut self) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        canvas.restore_state();
        Ok(())
    }

    /// Set fill color (RGB 0.0-1.0)
    fn canvas_set_fill_color(&mut self, r: f64, g: f64, b: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        let color = Color { r, g, b };
        canvas.set_fill_color(color);
        Ok(())
    }

    /// Set stroke color (RGB 0.0-1.0)
    fn canvas_set_stroke_color(&mut self, r: f64, g: f64, b: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        let color = Color { r, g, b };
        canvas.set_stroke_color(color);
        Ok(())
    }

    /// Set line width
    fn canvas_set_line_width(&mut self, width: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        canvas.set_line_width(width);
        Ok(())
    }

    /// Set dash pattern
    fn canvas_set_dash(&mut self, pattern: Vec<f64>) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        if pattern.is_empty() {
            canvas.set_dash(vec![], 0.0);
        } else {
            let phase = if pattern.len() > 0 { pattern[0] } else { 0.0 };
            canvas.set_dash(pattern, phase);
        }
        Ok(())
    }

    /// Set font name and size
    fn canvas_set_font(&mut self, name: String, size: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };

        // Get or create font
        let (font_name, font_id) = if let Some(&(name_ref, id_ref)) = self.font_registry.get(&name)
        {
            (name_ref, id_ref)
        } else {
            // Try to find font with different name variations
            let mut found_font = None;

            // Try common variations
            let variations = vec![
                name.replace("-", " "),
                name.replace(" ", "-"),
                name.replace("Bold", "-Bold"),
                name.replace("Italic", "-Italic"),
                name.replace("Oblique", "-Oblique"),
            ];

            for variant in variations {
                if let Some(&font) = self.font_registry.get(&variant) {
                    found_font = Some(font);
                    break;
                }
            }

            // Fallback to default Type0 font (DejaVu Sans family)
            let default_font = found_font.unwrap_or_else(|| {
                self.font_registry
                    .get("DejaVu Sans")
                    .or_else(|| self.font_registry.get("DejaVuSans"))
                    .copied()
                    .expect("DejaVu Sans Type0 font must be registered")
            });

            // Cache the mapping for future use
            self.font_registry.insert(name.clone(), default_font);
            default_font
        };

        // Register font for current page
        if !self.fonts_used_on_current_page.contains_key(&font_name) {
            self.fonts_used_on_current_page.insert(font_name, font_id);
        }

        canvas.set_font(font_name, size);
        Ok(())
    }

    /// Set current graphics state opacity (both fill and stroke)
    fn canvas_set_opacity(&mut self, opacity: f64) -> PyResult<()> {
        let clamped = opacity.clamp(0.0, 1.0);
        let alpha_key = (clamped * 1000.0).round() as u32;
        let (name, gs_ref) =
            self.get_or_create_ext_graphics_state(alpha_key, clamped as f32);

        {
            let canvas = if let Some((_, _, ref mut c)) = self.current_page {
                c
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                    "No current page",
                ));
            };
            canvas.set_ext_graphics_state(name);
        }

        self.ext_graphics_states_used_on_current_page
            .insert(name, gs_ref);
        Ok(())
    }

    /// Draw rectangle
    fn canvas_rect(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        fill: bool,
        stroke: bool,
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        let rect = Rect::new(x, y, width, height);
        canvas.rect(rect, fill, stroke);
        Ok(())
    }

    /// Draw rounded rectangle
    fn canvas_round_rect(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        radius: f64,
        fill: bool,
        stroke: bool,
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        let rect = Rect::new(x, y, width, height);
        canvas.round_rect(rect, radius, fill, stroke);
        Ok(())
    }

    /// Draw line
    fn canvas_line(&mut self, x1: f64, y1: f64, x2: f64, y2: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        canvas.line(x1, y1, x2, y2);
        Ok(())
    }

    /// Draw text string
    fn canvas_draw_string(&mut self, x: f64, y: f64, text: String) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };

        // Get current font name from canvas
        let current_font_name = canvas.get_font_name();

        // Require CID map for every font (all fonts are Type0)
        let cid_map = self.type0_cid_maps.get(&current_font_name).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "No CID map registered for font {:?}",
                current_font_name
            ))
        })?;

        canvas.draw_string(x, y, &text, cid_map);
        Ok(())
    }

    /// Draw image from bytes
    fn canvas_draw_image(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        image_data: Vec<u8>,
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };

        // Create a unique key for this image
        // Use a simple approach: use length and first/last bytes as key
        let key = if image_data.len() > 16 {
            // Use first 8 and last 8 bytes for uniqueness
            let prefix: u64 = u64::from_be_bytes([
                image_data[0],
                image_data[1],
                image_data[2],
                image_data[3],
                image_data[4],
                image_data[5],
                image_data[6],
                image_data[7],
            ]);
            let suffix: u64 = u64::from_be_bytes([
                image_data[image_data.len() - 8],
                image_data[image_data.len() - 7],
                image_data[image_data.len() - 6],
                image_data[image_data.len() - 5],
                image_data[image_data.len() - 4],
                image_data[image_data.len() - 3],
                image_data[image_data.len() - 2],
                image_data[image_data.len() - 1],
            ]);
            format!(
                "canvas_image_{:x}_{:x}_{}",
                prefix,
                suffix,
                image_data.len()
            )
        } else {
            // For small images, use all bytes
            format!(
                "canvas_image_{}_{}",
                image_data.len(),
                image_data
                    .iter()
                    .map(|b| format!("{:02x}", b))
                    .collect::<String>()
            )
        };

        // Check if image is already registered
        let (image_id, image_name) = if let Some(&(id, name)) = self.images_registry.get(&key) {
            (id, name)
        } else {
            // Register new image
            let image_id = Ref::new(self.next_image_id);
            self.next_image_id += 1;

            let image_name = image_utils::add_image_to_pdf(
                &mut self.pdf,
                &image_data,
                image_id,
                &mut self.next_image_id,
            )?;

            self.images_registry.insert(key, (image_id, image_name));
            (image_id, image_name)
        };

        // Register image for current page
        if !self.images_used_on_current_page.contains_key(&image_name) {
            self.images_used_on_current_page
                .insert(image_name, image_id);
        }

        // Draw image on canvas
        canvas.draw_image(image_name, x, y, width, height);
        Ok(())
    }

    /// Translate coordinate system
    fn canvas_translate(&mut self, x: f64, y: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        canvas.translate(x, y);
        Ok(())
    }

    /// Rotate coordinate system (radians)
    fn canvas_rotate(&mut self, angle: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        // Convert radians to degrees (canvas.rotate expects degrees)
        let angle_degrees = angle.to_degrees();
        canvas.rotate(angle_degrees);
        Ok(())
    }

    /// Scale coordinate system
    fn canvas_scale(&mut self, x: f64, y: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        canvas.scale(x, y);
        Ok(())
    }

    /// Apply transformation matrix [a, b, c, d, e, f]
    fn canvas_transform(&mut self, matrix: Vec<f64>) -> PyResult<()> {
        if matrix.len() != 6 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Transform matrix must have 6 elements",
            ));
        }
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "No current page",
            ));
        };
        canvas.transform([
            matrix[0] as f32,
            matrix[1] as f32,
            matrix[2] as f32,
            matrix[3] as f32,
            matrix[4] as f32,
            matrix[5] as f32,
        ]);
        Ok(())
    }

    /// Set page size (for current page)
    fn set_page_size(&mut self, width: f64, height: f64) -> PyResult<()> {
        // Update current page info if exists
        if let Some((page_id, _, _)) = self.current_page_info {
            self.current_page_info = Some((page_id, width, height));
        }
        Ok(())
    }

    /// Execute a batch of canvas commands in a single Python↔Rust call
    /// This dramatically reduces overhead compared to individual method calls
    /// Commands should be passed as a list of dicts, each with a "type" key and corresponding fields
    /// Example: [{"type": "SetFont", "name": "DejaVu Sans", "size": 12.0}, {"type": "DrawString", "x": 0.0, "y": 0.0, "text": "Hello"}]
    fn canvas_run_batch(&mut self, commands: &PyAny) -> PyResult<()> {
        // Convert PyAny to PyList
        let commands_list: &PyList = commands.downcast()?;
        for cmd_obj in commands_list.iter() {
            let cmd_dict = cmd_obj.downcast::<PyDict>()?;
            let cmd_type: String = cmd_dict.get_item("type")?
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'type' key in command"))?
                .extract()?;
            
            match cmd_type.as_str() {
                "SaveState" => {
                    self.canvas_save_state()?;
                }
                "RestoreState" => {
                    self.canvas_restore_state()?;
                }
                "SetFillColor" => {
                    let r: f64 = cmd_dict.get_item("r")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'r'"))?.extract()?;
                    let g: f64 = cmd_dict.get_item("g")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'g'"))?.extract()?;
                    let b: f64 = cmd_dict.get_item("b")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'b'"))?.extract()?;
                    self.canvas_set_fill_color(r, g, b)?;
                }
                "SetStrokeColor" => {
                    let r: f64 = cmd_dict.get_item("r")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'r'"))?.extract()?;
                    let g: f64 = cmd_dict.get_item("g")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'g'"))?.extract()?;
                    let b: f64 = cmd_dict.get_item("b")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'b'"))?.extract()?;
                    self.canvas_set_stroke_color(r, g, b)?;
                }
                "SetLineWidth" => {
                    let width: f64 = cmd_dict.get_item("width")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'width'"))?.extract()?;
                    self.canvas_set_line_width(width)?;
                }
                "SetDash" => {
                    let pattern: Vec<f64> = cmd_dict.get_item("pattern")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'pattern'"))?.extract()?;
                    self.canvas_set_dash(pattern)?;
                }
                "SetFont" => {
                    let name: String = cmd_dict.get_item("name")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'name'"))?.extract()?;
                    let size: f64 = cmd_dict.get_item("size")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'size'"))?.extract()?;
                    self.canvas_set_font(name, size)?;
                }
                "SetOpacity" => {
                    let opacity: f64 = cmd_dict.get_item("opacity")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'opacity'"))?.extract()?;
                    self.canvas_set_opacity(opacity)?;
                }
                "Rect" => {
                    let x: f64 = cmd_dict.get_item("x")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'x'"))?.extract()?;
                    let y: f64 = cmd_dict.get_item("y")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'y'"))?.extract()?;
                    let width: f64 = cmd_dict.get_item("width")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'width'"))?.extract()?;
                    let height: f64 = cmd_dict.get_item("height")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'height'"))?.extract()?;
                    let fill: bool = cmd_dict.get_item("fill")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'fill'"))?.extract()?;
                    let stroke: bool = cmd_dict.get_item("stroke")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'stroke'"))?.extract()?;
                    self.canvas_rect(x, y, width, height, fill, stroke)?;
                }
                "RoundRect" => {
                    let x: f64 = cmd_dict.get_item("x")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'x'"))?.extract()?;
                    let y: f64 = cmd_dict.get_item("y")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'y'"))?.extract()?;
                    let width: f64 = cmd_dict.get_item("width")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'width'"))?.extract()?;
                    let height: f64 = cmd_dict.get_item("height")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'height'"))?.extract()?;
                    let radius: f64 = cmd_dict.get_item("radius")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'radius'"))?.extract()?;
                    let fill: bool = cmd_dict.get_item("fill")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'fill'"))?.extract()?;
                    let stroke: bool = cmd_dict.get_item("stroke")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'stroke'"))?.extract()?;
                    self.canvas_round_rect(x, y, width, height, radius, fill, stroke)?;
                }
                "Line" => {
                    let x1: f64 = cmd_dict.get_item("x1")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'x1'"))?.extract()?;
                    let y1: f64 = cmd_dict.get_item("y1")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'y1'"))?.extract()?;
                    let x2: f64 = cmd_dict.get_item("x2")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'x2'"))?.extract()?;
                    let y2: f64 = cmd_dict.get_item("y2")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'y2'"))?.extract()?;
                    self.canvas_line(x1, y1, x2, y2)?;
                }
                "DrawString" => {
                    let x: f64 = cmd_dict.get_item("x")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'x'"))?.extract()?;
                    let y: f64 = cmd_dict.get_item("y")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'y'"))?.extract()?;
                    let text: String = cmd_dict.get_item("text")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'text'"))?.extract()?;
                    self.canvas_draw_string(x, y, text)?;
                }
                "DrawImage" => {
                    let x: f64 = cmd_dict.get_item("x")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'x'"))?.extract()?;
                    let y: f64 = cmd_dict.get_item("y")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'y'"))?.extract()?;
                    let width: f64 = cmd_dict.get_item("width")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'width'"))?.extract()?;
                    let height: f64 = cmd_dict.get_item("height")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'height'"))?.extract()?;
                    let image_data: Vec<u8> = cmd_dict.get_item("image_data")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'image_data'"))?.extract()?;
                    self.canvas_draw_image(x, y, width, height, image_data)?;
                }
                "Translate" => {
                    let x: f64 = cmd_dict.get_item("x")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'x'"))?.extract()?;
                    let y: f64 = cmd_dict.get_item("y")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'y'"))?.extract()?;
                    self.canvas_translate(x, y)?;
                }
                "Rotate" => {
                    let angle: f64 = cmd_dict.get_item("angle")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'angle'"))?.extract()?;
                    self.canvas_rotate(angle)?;
                }
                "Scale" => {
                    let x: f64 = cmd_dict.get_item("x")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'x'"))?.extract()?;
                    let y: f64 = cmd_dict.get_item("y")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'y'"))?.extract()?;
                    self.canvas_scale(x, y)?;
                }
                "Transform" => {
                    let matrix: Vec<f64> = cmd_dict.get_item("matrix")?.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing 'matrix'"))?.extract()?;
                    self.canvas_transform(matrix)?;
                }
                _ => {
                    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        format!("Unknown command type: {}", cmd_type)
                    ));
                }
            }
        }
        Ok(())
    }
}

impl PdfCanvasRenderer {
    fn get_or_create_ext_graphics_state(
        &mut self,
        alpha_key: u32,
        alpha: f32,
    ) -> (Name<'static>, Ref) {
        if let Some(&(name, ref_id)) = self.ext_graphics_states.get(&alpha_key) {
            return (name, ref_id);
        }

        let gs_ref = Ref::new(self.next_ref_id);
        self.next_ref_id += 1;

        let name_str = format!("GS{}", gs_ref.get());
        let name_boxed = name_str.into_boxed_str();
        let name_static = Box::leak(name_boxed);
        let name = Name(name_static.as_bytes());

        {
            let mut ext = self.pdf.ext_graphics(gs_ref);
            ext.non_stroking_alpha(alpha).stroking_alpha(alpha);
        }

        self.ext_graphics_states.insert(alpha_key, (name, gs_ref));
        (name, gs_ref)
    }
}

/// Python module for PDF canvas rendering
#[pymodule]
fn rust_pdf_canvas(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PdfCanvasRenderer>()?;
    Ok(())
}
