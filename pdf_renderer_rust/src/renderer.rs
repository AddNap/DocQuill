//! Main PDF renderer implementation
//!
//! ## Architecture
//!
//! This renderer is a "dumb renderer" - it does NOT perform any layout calculations.
//! All layout calculations (positions, dimensions, text wrapping, line breaking) are
//! performed by the Python LayoutAssembler. This renderer only renders the pre-calculated
//! blocks it receives.
//!
//! ## Data Flow
//!
//! ```
//! LayoutAssembler → UnifiedLayout (with pre-calculated ParagraphLayout) → Rust Renderer → PDF
//! ```
//!
//! The renderer expects:
//! - `ParagraphLayout` with pre-calculated lines, positions, and inline items
//! - `TableLayout` with pre-calculated cell positions
//! - `ImageLayout` with pre-calculated positions
//!
//! If a block doesn't have a pre-calculated layout payload, it should be considered
//! an error (assembler didn't prepare it correctly).

use pdf_writer::{Pdf, Rect as PdfRect, Name, Ref, Finish};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyBytes, PyAny, PyTuple};
use std::collections::HashMap;

use crate::canvas::PdfCanvas;
use crate::geometry::parse_color;
use crate::types::{UnifiedLayout, LayoutPage, LayoutBlock, Rect, Size, Margins, Color, ParagraphStyle, TextStyle};
use crate::field::resolve_field_text;
use crate::font_registry::FontRegistry;
use crate::image_registry::ImageRegistry;
use crate::block_renderer::BlockRenderer;
use crate::json_helpers;
use crate::text_layout::{LineBreaker, Justifier};
use crate::markers::render_marker;
use log::{debug, warn, error, info};
// Note: text_formatting, markers, overlays, justification modules are ready for use
// They will be integrated when implementing the corresponding features

/// Main PDF renderer class
#[pyclass]
pub struct PdfRenderer {
    pdf: Pdf,
    images_used_on_current_page: HashMap<Name<'static>, Ref>, // image_name -> image_id (for page resources)
    output_path: String,
    current_page: Option<(Ref, Ref, PdfCanvas)>, // (page_id, content_id, canvas)
    current_page_info: Option<(Ref, f64, f64)>, // (page_id, page_width, page_height) - stored before page creation
    pages: Vec<Ref>, // All page references
    page_tree_id: Option<Ref>,
    catalog_id: Option<Ref>,
    next_ref_id: i32, // Counter for generating unique Ref IDs
    current_page_number: u32, // Current page number (for field codes)
    total_pages: u32, // Total page count (for field codes)
    // Store font objects for manual injection into PDF bytes
    font_objects: Vec<(Ref, String)>, // (object_id, object_content) for manual PDF injection
    // Font and image registries
    fonts_registry: FontRegistry,
    images_registry: ImageRegistry,
}

#[pymethods]
impl PdfRenderer {
    #[new]
    fn new(output_path: String, _page_width: f64, _page_height: f64) -> Self {
        let mut pdf = Pdf::new();
        
        // Create references
        let catalog_id = Ref::new(1);
        let page_tree_id = Ref::new(2);
        
        // Set up catalog (page tree will be set up when first page is created)
        pdf.catalog(catalog_id).pages(page_tree_id);
        
        // Register default font (try DejaVu Sans first, fallback to Helvetica)
        let default_font_id = Ref::new(3);
        let default_font_ref = Name(b"F1");
        
        // Try to register DejaVu Sans as TTF font (better Unicode support, especially for Polish)
        let mut fonts_registry = FontRegistry::new(1000);
        let mut default_font_set = false;
        
        // Try common DejaVu Sans paths
        let dejavu_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/DejaVu Sans.ttf", // macOS
            "C:/Windows/Fonts/DejaVuSans.ttf", // Windows
        ];
        
        for dejavu_path in &dejavu_paths {
            if std::path::Path::new(dejavu_path).exists() {
                // Try to register DejaVu Sans as TTF
                if let Ok(dejavu_font_ref) = fonts_registry.get_or_register(&mut pdf, dejavu_path) {
                    // Register "DejaVu Sans" logical name
                    fonts_registry.insert("DejaVu Sans".to_string(), default_font_id, dejavu_font_ref);
                    fonts_registry.set_default_font(dejavu_font_ref);
                    default_font_set = true;
                    break;
                }
            }
        }
        
        // Fallback to Helvetica if DejaVu Sans not available
        if !default_font_set {
            pdf.type1_font(default_font_id).base_font(Name(b"Helvetica"));
            // Note: pdf-writer doesn't have .encoding() method for Type1 fonts
            // We rely on unicode_to_winansi() conversion in draw_string() to handle Polish characters
            // The font will use default encoding (StandardEncoding), but our conversion maps Unicode to WinAnsiEncoding bytes
            fonts_registry.insert("Helvetica".to_string(), default_font_id, default_font_ref);
            fonts_registry.set_default_font(default_font_ref);
        }
        
        Self {
            pdf,
            images_used_on_current_page: HashMap::new(),
            output_path,
            current_page: None,  // No page created yet
            pages: vec![],  // No pages yet
            page_tree_id: Some(page_tree_id),
            catalog_id: Some(catalog_id),
            next_ref_id: 4,  // Start from 4 (1=catalog, 2=page_tree, 3=default font)
            current_page_number: 1,
            total_pages: 1,
            current_page_info: None,
            font_objects: Vec::new(), // Store font objects for manual injection
            fonts_registry,
            images_registry: ImageRegistry::new(2000),
        }
    }
    
    /// Add a new page
    fn new_page(&mut self, page_width: f64, page_height: f64) -> PyResult<()> {
        // Save current page content and finalize page
        if let Some((page_id, content_id, canvas)) = self.current_page.take() {
            let content_bytes = canvas.finish();
            self.pdf.stream(content_id, &content_bytes);
            
            // Create and finish the previous page with all fonts in resources
            if let Some((prev_page_info_id, prev_page_width, prev_page_height)) = self.current_page_info.take() {
                let mut page = self.pdf.page(prev_page_info_id);
                page.media_box(PdfRect::new(0.0, 0.0, prev_page_width as f32, prev_page_height as f32));
                if let Some(page_tree_id) = self.page_tree_id {
                    page.parent(page_tree_id);
                }
                page.contents(content_id);
                
                // Add ALL registered fonts to resources (including TrueType fonts created during rendering)
                {
                    let mut resources = page.resources();
                    // Write fonts from registry
                    self.fonts_registry.write_resources(&mut resources);
                    
                    let images_count = self.images_used_on_current_page.len();
                    eprintln!(
                        "Finalizing previous page: registering {} images into resources",
                        images_count
                    );
                    // Add ALL images used on this page to resources
                    // pdf-writer's image_xobject() creates the XObject, but we need to register it in page Resources
                    // Similar to fonts, we use resources.x_objects().pair() to register images
                    if !self.images_used_on_current_page.is_empty() {
                        let mut xobject_dict = resources.x_objects();
                        for (image_name, image_id) in &self.images_used_on_current_page {
                            let image_name_str = String::from_utf8_lossy(image_name.0);
                            xobject_dict.pair(*image_name, *image_id);
                        }
                    }
                    // Also include registry-managed resources (migration path)
                    self.fonts_registry.write_resources(&mut resources);
                    self.images_registry.write_resources(&mut resources);
                }
                page.finish();
            }
        }
        
        // Clear images used on previous page (AFTER registering them in Resources)
        self.images_used_on_current_page.clear();
        
        // Create new page references
        let page_id = self.next_ref();
        let content_id = self.next_ref();
        
        // Add new page to pages list (page tree will be updated in save())
        self.pages.push(page_id);
        
        // Store page info - we'll create the page object when finalizing
        // This allows us to add all fonts (including TrueType fonts created during rendering) to resources
        self.current_page_info = Some((page_id, page_width, page_height));
        
        let mut canvas = PdfCanvas::new();
        // Set default font from registry if available
        if let Some(font_name) = self.fonts_registry.get_default_font() {
            canvas.set_font(font_name, 12.0);
        }
        self.current_page = Some((page_id, content_id, canvas));
        
        Ok(())
    }

    /// Register a TrueType/OpenType font and return its internal name (e.g. F4)
    ///
    /// This embeds the font and makes it available for subsequent pages.
    #[pyo3(text_signature = "(self, path)")]
    fn register_truetype_font(&mut self, path: String) -> PyResult<String> {
        // Use FontRegistry to register the font
        let (_font_id, font_name) = self.fonts_registry.get_or_create_type0(
            &mut self.pdf,
            &path,
            &path,
            &mut self.font_objects,
        )?;
        // Set as default font for new pages
        self.fonts_registry.set_default_font(font_name);
        // Return the font name as a String (e.g., "F4")
        let name_str = String::from_utf8_lossy(font_name.0).to_string();
        Ok(name_str)
    }
    
    /// Render UnifiedLayout (from JSON) - DEPRECATED, use render_unified_layout instead
    fn render_layout(&mut self, layout_json: &str) -> PyResult<()> {
        let layout: UnifiedLayout = serde_json::from_str(layout_json)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to parse layout JSON: {}", e)
            ))?;
        
        // Set total pages before rendering
        self.total_pages = layout.pages.len() as u32;
        if self.total_pages == 0 {
            self.total_pages = 1;
        }
        
        for (_page_index, page) in layout.pages.iter().enumerate() {
            // Set current page number
            self.current_page_number = page.number;
            
            // Log page margins for debugging
            debug!("Page {}: margins={:?}, size={:?}", page.number, page.margins, page.size);
            
            // Create new page
            self.new_page(page.size.width, page.size.height)?;
            
            // Render page blocks
            // Clone page to avoid borrowing issues
            let page_clone = page.clone();
            // Render page blocks (render_page_blocks_internal will get canvas internally)
            self.render_page_blocks_internal(&page_clone)?;
        }
        
        Ok(())
    }
    
    /// Set total pages (for field codes like PAGE/NUMPAGES)
    fn set_total_pages(&mut self, total: u32) -> PyResult<()> {
        self.total_pages = if total > 0 { total } else { 1 };
        Ok(())
    }
    
    /// Set current page number (for field codes)
    fn set_current_page_number(&mut self, page_num: u32) -> PyResult<()> {
        self.current_page_number = if page_num > 0 { page_num } else { 1 };
        Ok(())
    }

    /// Register an image stream (bytes) that can be referenced by stream_key in JSON payloads.
    #[pyo3(text_signature = "(self, key, data, mime_type=None)")]
    fn register_image_stream(&mut self, key: String, data: &PyBytes, mime_type: Option<String>) -> PyResult<()> {
        self.images_registry.register_stream(key, data.as_bytes().to_vec(), mime_type);
        Ok(())
    }
    
    /// Render image block with specific parameters
    fn render_image_block(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        image_path: String,
        width_emu: Option<f64>,
        height_emu: Option<f64>,
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        
        BlockRenderer::render_image_direct(
            canvas,
            &mut self.pdf,
            &mut self.fonts_registry,
            &mut self.images_registry,
            &mut self.images_used_on_current_page,
            x, y, width, height,
            &image_path,
            width_emu,
            height_emu,
        )
    }

    /// Render image block using previously registered stream key
    fn render_image_block_stream(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        stream_key: String,
        width_emu: Option<f64>,
        height_emu: Option<f64>,
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };

        let (image_id, image_name) = self.images_registry.get_or_create_from_stream(
            &mut self.pdf,
            &stream_key,
            width_emu,
            height_emu,
        )?;

        if !self.images_used_on_current_page.contains_key(&image_name) {
            self.images_used_on_current_page.insert(image_name, image_id);
        }

        canvas.draw_image(image_name, x, y, width, height);
        Ok(())
    }
    
    /// Render paragraph block - simple method, Python provides all data
    fn render_paragraph_block(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        content: &PyAny, // Python dict with layout_payload, runs_payload, etc.
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        
        let content = Self::py_any_to_json(content)?;
        
        // Rust just renders - no data extraction
        let style = serde_json::json!({});
        let rect = Rect::new(x, y, width, height);
        
        Self::render_paragraph_from_layout(
            canvas,
            &mut self.pdf,
            &mut self.fonts_registry,
            &mut self.images_registry,
            &mut self.images_used_on_current_page,
            &rect,
            &content,
            &style,
            self.current_page_number,
            self.total_pages,
        )
    }
    
    /// Render table block - simple method, Python provides all data
    fn render_table_block(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        content: &PyAny, // Python dict with rows, cells, content_array, etc.
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        
        let content = Self::py_any_to_json(content)?;
        
        // Rust just renders - no data extraction
        let rect = Rect::new(x, y, width, height);
        let block = LayoutBlock {
            frame: rect,
            block_type: "table".to_string(),
            content,
            style: serde_json::json!({}),
            page_number: None,
        };
        
        BlockRenderer::render_table(
            canvas,
            &mut self.pdf,
            &mut self.fonts_registry,
            &mut self.images_registry,
            &mut self.images_used_on_current_page,
            &block,
            self.current_page_number,
            self.total_pages,
        )
    }
    
    /// Render header block - simple method, Python provides all data
    fn render_header_block(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        content: &PyAny, // Python dict with images, overlays, layout_payload, etc.
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        
        let content = Self::py_any_to_json(content)?;
        
        eprintln!("   render_header_block: content keys={:?}", 
            content.as_object().map(|o| o.keys().collect::<Vec<_>>()));
        if let Some(payload) = content.get("payload").and_then(|p| p.as_object()) {
            eprintln!("   render_header_block: payload keys={:?}", payload.keys().collect::<Vec<_>>());
            if let Some(overlays) = payload.get("overlays").and_then(|v| v.as_array()) {
                eprintln!("   render_header_block: payload.overlays length={}", overlays.len());
            }
        }
        if let Some(overlays) = content.get("overlays").and_then(|v| v.as_array()) {
            eprintln!("   render_header_block: content.overlays length={}", overlays.len());
        }
        
        // Rust just renders - no data extraction
        let rect = Rect::new(x, y, width, height);
        let block = LayoutBlock {
            frame: rect,
            block_type: "header".to_string(),
            content,
            style: serde_json::json!({}),
            page_number: None,
        };
        
        Self::render_header(
            canvas,
            &mut self.pdf,
            &mut self.fonts_registry,
            &mut self.images_registry,
            &block,
            self.current_page_number,
            self.total_pages,
            &mut self.images_used_on_current_page,
        )
    }
    
    /// Render footer block - simple method, Python provides all data
    fn render_footer_block(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        content: &PyAny, // Python dict with images, overlays, layout_payload, etc.
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        
        let content = Self::py_any_to_json(content)?;
        
        // Rust just renders - no data extraction
        let rect = Rect::new(x, y, width, height);
        let block = LayoutBlock {
            frame: rect,
            block_type: "footer".to_string(),
            content,
            style: serde_json::json!({}),
            page_number: None,
        };
        
        Self::render_footer(
            canvas,
            &mut self.pdf,
            &mut self.fonts_registry,
            &mut self.images_registry,
            &block,
            self.current_page_number,
            self.total_pages,
            &mut self.images_used_on_current_page,
        )
    }

    /// Render footnotes block - Python provides serialized footnotes data
    fn render_footnotes_block(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        footnotes_list: Vec<(String, String)>, // Vec of (number, content) tuples
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };

        if footnotes_list.is_empty() {
            return Ok(());
        }

        let rect = Rect::new(x, y, width, height);
        
        // Set font for footnotes (smaller than body text)
        let font_name = "DejaVu Sans";
        let font_size = 9.0;
        let font_ref = self.fonts_registry.get_or_builtin(&mut self.pdf, font_name);
        
        canvas.save_state();
        canvas.set_font(font_ref, font_size);
        let black_color = Color::rgb(0.0, 0.0, 0.0);
        canvas.set_fill_color(black_color);
        
        // Draw separator line (40% width, aligned left)
        let separator_y = rect.y + rect.height - 4.0;
        let separator_width = rect.width * 0.4;
        let separator_x = rect.x;
        
        canvas.set_stroke_color(black_color);
        canvas.set_line_width(0.5);
        canvas.line(separator_x, separator_y, separator_x + separator_width, separator_y);
        
        // Render footnotes
        let mut y = separator_y - 4.0 - font_size;
        let x_start = rect.x;
        let line_height = font_size * 1.2;
        
        for (footnote_number, footnote_content) in footnotes_list {
            if y < rect.y {
                break; // No more space
            }
            
            // Render footnote number (as superscript)
            let ref_font_size = font_size * 0.58;
            let superscript_shift = font_size * 0.33;
            
            canvas.save_state();
            canvas.set_font(font_ref, ref_font_size);
            let number_y = y + superscript_shift;
            canvas.draw_string(x_start, number_y, &footnote_number);
            // Estimate number width (approximate)
            let number_width = ref_font_size * footnote_number.len() as f64 * 0.6;
            canvas.restore_state();
            
            // Render footnote content
            let text_x = x_start + number_width + 2.0;
            let max_width = rect.x + rect.width - text_x;
            
            // Simple text wrapping (basic implementation)
            let words: Vec<&str> = footnote_content.split_whitespace().collect();
            let mut current_line = String::new();
            let mut current_y = y;
            
            for word in words {
                let test_line = if current_line.is_empty() {
                    word.to_string()
                } else {
                    format!("{} {}", current_line, word)
                };
                
                // Estimate width (approximate: 0.6 * font_size per character)
                let estimated_width = test_line.len() as f64 * font_size * 0.6;
                
                if estimated_width > max_width && !current_line.is_empty() {
                    // Draw current line and start new line
                    canvas.draw_string(text_x, current_y, &current_line);
                    current_y -= line_height;
                    if current_y < rect.y {
                        break;
                    }
                    current_line = word.to_string();
                } else {
                    current_line = test_line;
                }
            }
            
            // Draw remaining line
            if !current_line.is_empty() && current_y >= rect.y {
                canvas.draw_string(text_x, current_y, &current_line);
            }
            
            y = current_y - line_height;
        }
        
        canvas.restore_state();
        
        Ok(())
    }

    /// Render endnotes block - Python provides serialized endnotes data
    fn render_endnotes_block(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        content: &PyAny,
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };

        let content = Self::py_any_to_json(content)?;

        let rect = Rect::new(x, y, width, height);
        let block = LayoutBlock {
            frame: rect,
            block_type: "endnotes".to_string(),
            content,
            style: serde_json::json!({}),
            page_number: None,
        };

        Self::render_endnotes(
            canvas,
            &mut self.pdf,
            &mut self.fonts_registry,
            &mut self.images_used_on_current_page,
            &block,
        )
    }
    
    /// Render rectangle/decorator block - simple method, Python provides all data
    fn render_rectangle_block(
        &mut self,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        fill_color: Option<String>, // Color as string (e.g., "#FF0000" or "rgb(255,0,0)")
        stroke_color: Option<String>, // Color as string
        line_width: Option<f64>, // Line width in points
    ) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        
        // Rust just draws - Python already extracted colors
        let rect = Rect::new(x, y, width, height);
        
        // Build style JSON from provided colors
        let mut style = serde_json::Map::new();
        if let Some(fill) = fill_color {
            style.insert("background_color".to_string(), serde_json::Value::String(fill));
        }
        if let Some(stroke) = stroke_color {
            style.insert("stroke_color".to_string(), serde_json::Value::String(stroke));
        }
        if let Some(lw) = line_width {
            if let Some(num) = serde_json::Number::from_f64(lw) {
                style.insert("line_width".to_string(), serde_json::Value::Number(num));
            }
        }
        
        let block = LayoutBlock {
            frame: rect,
            block_type: "rectangle".to_string(),
            content: serde_json::json!({}),
            style: serde_json::Value::Object(style),
            page_number: None,
        };
        
        Self::render_rectangle(canvas, &block)
    }
    
    /// Save PDF to file
    fn save(&mut self) -> PyResult<()> {
        // Save current page content and finalize page
        if let Some((page_id, content_id, canvas)) = self.current_page.take() {
            let content_bytes = canvas.finish();
            self.pdf.stream(content_id, &content_bytes);
            
            // Create and finish the page with all fonts in resources
            if let Some((page_info_id, page_width, page_height)) = self.current_page_info.take() {
                let mut page = self.pdf.page(page_info_id);
                page.media_box(PdfRect::new(0.0, 0.0, page_width as f32, page_height as f32));
                if let Some(page_tree_id) = self.page_tree_id {
                    page.parent(page_tree_id);
                }
                page.contents(content_id);
                
                // Add ALL registered fonts to resources (including TrueType fonts created during rendering)
                {
                    let mut resources = page.resources();
                    // Write fonts from registry
                    self.fonts_registry.write_resources(&mut resources);
                    
                    // Add ALL images used on this page to resources
                    // pdf-writer's image_xobject() creates the XObject, but we need to register it in page Resources
                    // Similar to fonts, we use resources.x_objects().pair() to register images
                    let images_count = self.images_used_on_current_page.len();
                    eprintln!(
                        "Finalizing page {}: registering {} images into resources",
                        self.current_page_number,
                        images_count
                    );
                    if !self.images_used_on_current_page.is_empty() {
                        let mut xobject_dict = resources.x_objects();
                        for (image_name, image_id) in &self.images_used_on_current_page {
                            let image_name_str = String::from_utf8_lossy(image_name.0);
                            xobject_dict.pair(*image_name, *image_id);
                        }
                    }
                    // Also include registry-managed resources (migration path)
                    self.fonts_registry.write_resources(&mut resources);
                    self.images_registry.write_resources(&mut resources);
                }
                page.finish();
            }
        }
        
        let page_count = self.pages.len();
        
        // Update page tree with all pages (only once, at the end)
        if let Some(page_tree_id) = self.page_tree_id {
            let page_count_i32 = page_count as i32;
            let mut pages_writer = self.pdf.pages(page_tree_id);
            
            // Use normal API - no limit on number of pages
            // kids() requires IntoIterator<Item = Ref>, so we need to clone the references
            if !self.pages.is_empty() {
                pages_writer.kids(self.pages.iter().cloned()).count(page_count_i32);
            } else {
                pages_writer.count(0);
            }
        }
        
        
        // Finish PDF and get bytes
        // finish() takes ownership, so we need to take pdf from self
        let pdf = std::mem::replace(&mut self.pdf, Pdf::new());
        let mut pdf_bytes = pdf.finish();
        
        info!("PDF generated: {} bytes ({:.2} MB)", 
            pdf_bytes.len(), pdf_bytes.len() as f64 / 1_048_576.0);
        
        // Inject font objects if any were created
        let font_objects = std::mem::take(&mut self.font_objects);
        if !font_objects.is_empty() {
            pdf_bytes = Self::inject_font_objects(pdf_bytes, &font_objects)?;
            info!("Font objects injected, new PDF size: {} bytes ({:.2} MB)", 
                pdf_bytes.len(), pdf_bytes.len() as f64 / 1_048_576.0);
        }
        
        // Ensure output directory exists
        if let Some(parent) = std::path::Path::new(&self.output_path).parent() {
            if let Err(e) = std::fs::create_dir_all(parent) {
                return Err(PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to create output directory {}: {}", parent.display(), e)
                ));
            }
        }
        
        // Write to file
        std::fs::write(&self.output_path, pdf_bytes)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to write PDF to {}: {}", self.output_path, e)
            ))?;
        
        info!("PDF saved to: {}", self.output_path);
        
        Ok(())
    }
    
    // ===== Canvas Operations (for RustCanvas wrapper) =====
    
    /// Save canvas state
    fn canvas_save_state(&mut self) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        canvas.save_state();
        Ok(())
    }
    
    /// Restore canvas state
    fn canvas_restore_state(&mut self) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        canvas.restore_state();
        Ok(())
    }
    
    /// Set fill color (RGB 0.0-1.0)
    fn canvas_set_fill_color(&mut self, r: f64, g: f64, b: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        let color = crate::types::Color { r, g, b };
        canvas.set_fill_color(color);
        Ok(())
    }
    
    /// Set stroke color (RGB 0.0-1.0)
    fn canvas_set_stroke_color(&mut self, r: f64, g: f64, b: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        let color = crate::types::Color { r, g, b };
        canvas.set_stroke_color(color);
        Ok(())
    }
    
    /// Set line width
    fn canvas_set_line_width(&mut self, width: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        canvas.set_line_width(width);
        Ok(())
    }
    
    /// Set dash pattern
    fn canvas_set_dash(&mut self, pattern: Vec<f64>) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
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
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        // Get font name from registry
        let font_name = self.fonts_registry.get_or_builtin(&mut self.pdf, &name);
        canvas.set_font(font_name, size);
        Ok(())
    }
    
    /// Draw rectangle
    fn canvas_rect(&mut self, x: f64, y: f64, width: f64, height: f64, fill: bool, stroke: bool) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        let rect = crate::types::Rect::new(x, y, width, height);
        canvas.rect(rect, fill, stroke);
        Ok(())
    }
    
    /// Draw rounded rectangle
    fn canvas_round_rect(&mut self, x: f64, y: f64, width: f64, height: f64, radius: f64, fill: bool, stroke: bool) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        let rect = crate::types::Rect::new(x, y, width, height);
        canvas.round_rect(rect, radius, fill, stroke);
        Ok(())
    }
    
    /// Draw line
    fn canvas_line(&mut self, x1: f64, y1: f64, x2: f64, y2: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        canvas.line(x1, y1, x2, y2);
        Ok(())
    }
    
    /// Draw text string
    fn canvas_draw_string(&mut self, x: f64, y: f64, text: String) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        canvas.draw_string(x, y, &text);
        Ok(())
    }
    
    /// Draw image from bytes
    fn canvas_draw_image(&mut self, x: f64, y: f64, width: f64, height: f64, image_data: Vec<u8>) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        // Create a unique key for this image
        // Use a simple approach: use length and first/last bytes as key
        let key = if image_data.len() > 16 {
            // Use first 8 and last 8 bytes for uniqueness
            let prefix: u64 = u64::from_be_bytes([
                image_data[0], image_data[1], image_data[2], image_data[3],
                image_data[4], image_data[5], image_data[6], image_data[7],
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
            format!("canvas_image_{:x}_{:x}_{}", prefix, suffix, image_data.len())
        } else {
            // For small images, use all bytes
            format!("canvas_image_{}_{}", image_data.len(), 
                image_data.iter().map(|b| format!("{:02x}", b)).collect::<String>())
        };
        
        // Register image stream
        self.images_registry.register_stream(key.clone(), image_data, None);
        
        // Get or create image from stream
        let (image_id, image_name) = self.images_registry.get_or_create_from_stream(
            &mut self.pdf,
            &key,
            None, // width_emu
            None, // height_emu
        )?;
        
        if !self.images_used_on_current_page.contains_key(&image_name) {
            self.images_used_on_current_page.insert(image_name, image_id);
        }
        
        canvas.draw_image(image_name, x, y, width, height);
        Ok(())
    }
    
    /// Translate coordinate system
    fn canvas_translate(&mut self, x: f64, y: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        canvas.translate(x, y);
        Ok(())
    }
    
    /// Rotate coordinate system (radians)
    fn canvas_rotate(&mut self, angle: f64) -> PyResult<()> {
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
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
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        canvas.scale(x, y);
        Ok(())
    }
    
    /// Apply transformation matrix [a, b, c, d, e, f]
    fn canvas_transform(&mut self, matrix: Vec<f64>) -> PyResult<()> {
        if matrix.len() != 6 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Transform matrix must have 6 elements"));
        }
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        canvas.content_mut().transform([
            matrix[0] as f32, matrix[1] as f32,
            matrix[2] as f32, matrix[3] as f32,
            matrix[4] as f32, matrix[5] as f32,
        ]);
        Ok(())
    }
    
    /// Set page size (for current page)
    /// Note: This only updates the stored page size info, actual page size is set in new_page()
    fn set_page_size(&mut self, width: f64, height: f64) -> PyResult<()> {
        // Update current page info if exists
        if let Some((page_id, _, _)) = self.current_page_info {
            self.current_page_info = Some((page_id, width, height));
        }
        Ok(())
    }
}

// Internal implementation methods (not exposed to Python)
impl PdfRenderer {
    /// Helper to generate next Ref ID
    fn next_ref(&mut self) -> Ref {
        let id = Ref::new(self.next_ref_id);
        self.next_ref_id += 1;
        id
    }
    
    fn py_any_to_json(value: &PyAny) -> PyResult<serde_json::Value> {
        if value.is_none() {
            return Ok(serde_json::Value::Null);
        }
        if let Ok(b) = value.extract::<bool>() {
            return Ok(serde_json::Value::Bool(b));
        }
        if let Ok(i) = value.extract::<i64>() {
            return Ok(serde_json::Value::Number(i.into()));
        }
        if let Ok(f) = value.extract::<f64>() {
            if let Some(num) = serde_json::Number::from_f64(f) {
                return Ok(serde_json::Value::Number(num));
            }
        }
        if let Ok(s) = value.extract::<String>() {
            return Ok(serde_json::Value::String(s));
        }
        if let Ok(list) = value.downcast::<PyList>() {
            let mut items = Vec::with_capacity(list.len());
            for item in list {
                items.push(Self::py_any_to_json(item)?);
            }
            return Ok(serde_json::Value::Array(items));
        }
        if let Ok(tuple) = value.downcast::<PyTuple>() {
            let mut items = Vec::with_capacity(tuple.len());
            for item in tuple {
                items.push(Self::py_any_to_json(item)?);
            }
            return Ok(serde_json::Value::Array(items));
        }
        if let Ok(dict) = value.downcast::<PyDict>() {
            let mut map = serde_json::Map::with_capacity(dict.len());
            for (k, v) in dict {
                let key = if let Ok(s) = k.extract::<String>() {
                    s
                } else {
                    k.str()?.to_str()?.to_string()
                };
                map.insert(key, Self::py_any_to_json(v)?);
            }
            return Ok(serde_json::Value::Object(map));
        }
        let repr = value.repr()?.to_string();
        Ok(serde_json::Value::String(repr))
    }
    /// Render a single page's blocks (internal method, not exposed to Python)
    fn render_page_blocks_internal(&mut self, page: &LayoutPage) -> PyResult<()> {
        // Verify we have a current page (canvas will be accessed in render_block_internal)
        if self.current_page.is_none() {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        }
        // Sort blocks: watermarks first, then headers, body, footnotes, footers
        let mut watermark_blocks = Vec::new();
        let mut header_blocks = Vec::new();
        let mut body_blocks = Vec::new();
        let mut footnote_blocks = Vec::new();
        let mut footer_blocks = Vec::new();
        
        for block in &page.blocks {
            let content = &block.content;
            let header_footer_context = content
                .get("header_footer_context")
                .and_then(|v| v.as_str());
            
            // Check if watermark
            if json_helpers::get_bool_or(content, "is_watermark", false) {
                watermark_blocks.push(block);
            } else if block.block_type == "header" || header_footer_context == Some("header") {
                header_blocks.push(block);
            } else if block.block_type == "footer" || header_footer_context == Some("footer") {
                footer_blocks.push(block);
            } else if block.block_type == "footnotes" {
                footnote_blocks.push(block);
            } else {
                body_blocks.push(block);
            }
        }
        
        // Render in order: watermarks, headers, body, footnotes, footers
        for block in watermark_blocks {
            self.render_block_internal(&block)?;
        }
        for block in header_blocks {
            self.render_block_internal(&block)?;
        }
        for block in body_blocks {
            self.render_block_internal(&block)?;
        }
        for block in footnote_blocks {
            self.render_block_internal(&block)?;
        }
        for block in footer_blocks {
            self.render_block_internal(&block)?;
        }
        
        Ok(())
    }
    
    /// Render a single block (internal method)
    fn render_block_internal(&mut self, block: &LayoutBlock) -> PyResult<()> {
        // Get mutable access to canvas
        let canvas = if let Some((_, _, ref mut c)) = self.current_page {
            c
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No current page"));
        };
        
        let current_page = self.current_page_number;
        let total_pages = self.total_pages;
        
        match block.block_type.as_str() {
            "paragraph" => {
                // Route through BlockRenderer to enable gradual migration
                BlockRenderer::render_paragraph(
                    canvas,
                    &mut self.pdf,
                    &mut self.fonts_registry,
                    &mut self.images_registry,
                    block,
                    current_page,
                    total_pages,
                )
            }
            "table" => {
                BlockRenderer::render_table(
                    canvas,
                    &mut self.pdf,
                    &mut self.fonts_registry,
                    &mut self.images_registry,
                    &mut self.images_used_on_current_page,
                    block,
                    current_page,
                    total_pages,
                )
            },
            "image" => {
                // Check if this is a watermark
                let content = &block.content;
                if json_helpers::get_bool_or(content, "is_watermark", false) {
                    Self::render_watermark(canvas, &mut self.pdf, &mut self.fonts_registry, &mut self.images_registry, block)
                } else {
                    BlockRenderer::render_image(
                        canvas,
                        &mut self.pdf,
                        &mut self.fonts_registry,
                        &mut self.images_registry,
                        &mut self.images_used_on_current_page,
                        block,
                    )
                }
            },
            "textbox" => {
                // Check if this is a watermark
                let content = &block.content;
                if json_helpers::get_bool_or(content, "is_watermark", false) {
                    Self::render_watermark(canvas, &mut self.pdf, &mut self.fonts_registry, &mut self.images_registry, block)
                } else {
                    Self::render_textbox(canvas, &mut self.pdf, &mut self.fonts_registry, &mut self.images_used_on_current_page, block)
                }
            },
            "header" => Self::render_header(canvas, &mut self.pdf, &mut self.fonts_registry, &mut self.images_registry, block, current_page, total_pages, &mut self.images_used_on_current_page),
            "footer" => Self::render_footer(canvas, &mut self.pdf, &mut self.fonts_registry, &mut self.images_registry, block, current_page, total_pages, &mut self.images_used_on_current_page),
            "footnotes" => Self::render_footnotes(canvas, &mut self.pdf, &mut self.fonts_registry, &mut self.images_used_on_current_page, block),
            "endnotes" => Self::render_endnotes(canvas, &mut self.pdf, &mut self.fonts_registry, &mut self.images_used_on_current_page, block),
            "decorator" => {
                // Decorators are typically borders/backgrounds between paragraphs
                Self::render_decorator(canvas, block)
            },
            "rectangle" | "rect" => {
                // Render as filled/stroked rectangle
                Self::render_rectangle(canvas, block)
            },
            "vml_shape" => {
                // VML shapes are typically rectangles or lines - render as rectangle
                Self::render_rectangle(canvas, block)
            },
            "spacer" => {
                // Spacer blocks don't need rendering - they're just for layout
                Ok(())
            },
            "list" | "list_item" => {
                // Lists are rendered as paragraphs with bullets
                // Delegate to paragraph rendering with list marker
                BlockRenderer::render_paragraph(
                    canvas,
                    &mut self.pdf,
                    &mut self.fonts_registry,
                    &mut self.images_registry,
                    block,
                    current_page,
                    total_pages,
                )
            },
            "overlay" => {
                // Overlays are handled separately in overlays.rs
                // For now, skip (they should be rendered at the end)
                Ok(())
            },
            "field" => {
                // Fields are typically rendered as part of paragraphs
                // For standalone fields, render as text
                BlockRenderer::render_paragraph(
                    canvas,
                    &mut self.pdf,
                    &mut self.fonts_registry,
                    &mut self.images_registry,
                    block,
                    current_page,
                    total_pages,
                )
            },
            "row" | "cell" => {
                // Rows and cells are handled within table rendering
                // Standalone rows/cells shouldn't exist, but handle gracefully
                warn!("Standalone row/cell block encountered - should be inside table");
                Ok(())
            },
            _ => {
                // Unknown block type - log warning but don't fail
                warn!("Unknown block type: {}", block.block_type);
                Ok(())
            }
        }
    }
    
    /// Render paragraph block
    ///
    /// This function expects a pre-calculated `ParagraphLayout` payload from the assembler.
    /// It does NOT perform any layout calculations - it only renders what it receives.
    ///
    /// If `ParagraphLayout` is missing, this indicates that the assembler didn't prepare
    /// the block correctly. In such cases, we log a warning and skip rendering.
    pub fn render_paragraph(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_registry: &mut crate::image_registry::ImageRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        block: &LayoutBlock,
        current_page_number: u32,
        total_pages: u32,
    ) -> PyResult<()> {
        let rect = &block.frame;
        let style = &block.style;
        let content = &block.content;
        
        // Draw shadow (before background and border)
        Self::draw_shadow(canvas, rect, style);
        
        // Draw background
        if let Some(bg_color) = style.get("background_color")
            .or_else(|| style.get("background"))
            .or_else(|| style.get("shading").and_then(|s| s.get("fill"))) {
            let color = parse_color(bg_color);
            canvas.save_state();
            canvas.set_fill_color(color);
            canvas.rect(*rect, true, false);
            canvas.restore_state();
        }
        
        // Draw border
        if let Some(border) = style.get("border") {
            Self::draw_border(canvas, rect, border)?;
        } else if let Some(borders) = style.get("borders") {
            Self::draw_borders(canvas, rect, borders)?;
        }
        
        // Check if we have ParagraphLayout payload (required from assembler)
        let has_paragraph_layout = content.get("layout_payload").is_some() 
            || content.get("_layout_payload").is_some()
            || content.get("lines").is_some();
        
        // Render overlays first (they should be behind text)
        let overlays = content.get("payload")
            .and_then(|p| p.as_object())
            .and_then(|p| p.get("overlays"))
            .and_then(|v| v.as_array())
            .or_else(|| {
                // Also check if content itself has overlays (for GenericLayout)
                if let Some(content_obj) = content.as_object() {
                    content_obj.get("overlays").and_then(|v| v.as_array())
                } else {
                    None
                }
            });
        
        if let Some(overlays_array) = overlays {
            if !overlays_array.is_empty() {
                debug!("Rendering {} overlays in paragraph", overlays_array.len());
                crate::overlays::render_overlays(
                    canvas,
                    pdf,
                    fonts_registry,
                    images_registry,
                    overlays_array,
                    images_used_on_current_page,
                )?;
            }
        }
        
        if has_paragraph_layout {
            // Render using pre-calculated ParagraphLayout from assembler
            Self::render_paragraph_from_layout(canvas, pdf, fonts_registry, images_registry, images_used_on_current_page, rect, content, style, current_page_number, total_pages)?;
        } else {
            // No ParagraphLayout payload - this is an error condition.
            // The assembler should have prepared the layout. We skip rendering and log a warning.
            // Note: We cannot use println! in PyO3, but we can return an error or just skip.
            // For now, we'll skip rendering silently to avoid breaking existing code.
            // TODO: Add proper logging mechanism or return an error
            return Ok(()); // Skip rendering - assembler didn't prepare the layout
        }
        
        Ok(())
    }
    
    /// Render table block
    pub fn render_table(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_registry: &mut crate::image_registry::ImageRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        block: &LayoutBlock,
        current_page_number: u32,
        total_pages: u32,
    ) -> PyResult<()> {
        let rect = &block.frame;
        let content = &block.content;
        
        // Draw table background (if specified)
        if let Some(bg_color) = block.style.get("background_color") {
            let color = parse_color(bg_color);
            canvas.save_state();
            canvas.set_fill_color(color);
            canvas.rect(*rect, true, false);
            canvas.restore_state();
        }
        
        // Draw table border (if specified, or default thin border)
        if let Some(border) = block.style.get("border") {
            Self::draw_border(canvas, rect, border)?;
        } else if let Some(borders) = block.style.get("borders") {
            Self::draw_borders(canvas, rect, borders)?;
        } else {
            // Default: draw thin border around table
            canvas.save_state();
            canvas.set_stroke_color(Color::rgb(0.0, 0.0, 0.0));
            canvas.set_line_width(0.5);
            canvas.rect(*rect, false, true);
            canvas.restore_state();
        }
        
        // Get col_widths and row_heights from layout_info
        let layout_info = content.get("layout_info").and_then(|v| v.as_object());
        let col_widths: Vec<f64> = layout_info
            .and_then(|li| li.get("col_widths"))
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_f64()).collect())
            .unwrap_or_else(|| {
                // Fallback: equal widths
                let num_cols = content.get("rows")
                    .and_then(|v| v.as_array())
                    .and_then(|rows| rows.first())
                    .and_then(|row| row.get("cells"))
                    .and_then(|v| v.as_array())
                    .map(|cells| cells.len())
                    .unwrap_or(1);
                vec![rect.width / num_cols as f64; num_cols]
            });
        
        let row_heights: Vec<f64> = layout_info
            .and_then(|li| li.get("row_heights"))
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_f64()).collect())
            .unwrap_or_else(|| {
                // Fallback: equal heights
                let num_rows = content.get("rows")
                    .and_then(|v| v.as_array())
                    .map(|rows| rows.len())
                    .unwrap_or(1);
                vec![rect.height / num_rows as f64; num_rows]
            });
        
        // Get table rows
        if let Some(rows) = content.get("rows").and_then(|v| v.as_array()) {
            // Limit number of rows to prevent infinite loops (safety limit: 1000 rows)
            let max_rows = rows.len().min(1000);
            if rows.len() > max_rows {
                // Log warning (but we can't use println! in PyO3, so we'll just limit)
                // Return error if too many rows
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Table has too many rows: {} (max 1000)", rows.len())
                ));
            }
            
            // Track which cells are merged (to skip rendering merged cells)
            let mut rendered_cells: std::collections::HashSet<(usize, usize)> = std::collections::HashSet::new();
            
            for (row_idx, row) in rows.iter().take(max_rows).enumerate() {
                if let Some(cells) = row.get("cells").and_then(|v| v.as_array()) {
                    // Limit number of cells per row (safety limit: 100 cells per row)
                    let max_cells = cells.len().min(100);
                    if cells.len() > max_cells {
                        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                            format!("Row {} has too many cells: {} (max 100)", row_idx, cells.len())
                        ));
                    }
                    
                    let mut col_idx = 0;
                    
                    for (cell_idx, cell) in cells.iter().take(max_cells).enumerate() {
                        // Get grid_span (colspan) - how many columns this cell spans
                        let grid_span = cell.get("grid_span")
                            .or_else(|| cell.get("gridSpan"))
                            .and_then(|v| {
                                if let Some(n) = v.as_u64() {
                                    Some(n as usize)
                                } else if let Some(s) = v.as_str() {
                                    s.parse::<usize>().ok()
                                } else {
                                    None
                                }
                            })
                            .unwrap_or(1);
                        
                        // Get vertical_merge_type (rowspan) - "restart" means start of merge, "continue" means continuation
                        let vertical_merge_type = cell.get("vertical_merge_type")
                            .or_else(|| cell.get("vMerge"))
                            .and_then(|v| {
                                if let Some(s) = v.as_str() {
                                    Some(s)
                                } else if let Some(obj) = v.as_object() {
                                    obj.get("val").and_then(|v| v.as_str())
                                } else {
                                    None
                                }
                            });
                        
                        // Skip cells that are continuations of vertical merges
                        if vertical_merge_type == Some("continue") {
                            col_idx += grid_span;
                            continue;
                        }
                        
                        // Calculate rowspan by checking subsequent rows
                        let mut cell_rowspan = 1;
                        if vertical_merge_type == Some("restart") {
                            // Count how many rows this cell spans
                            // Limit to prevent infinite loops (max 100 rows span)
                            let max_rowspan_check = (row_idx + 1 + 100).min(rows.len());
                            for next_row_idx in (row_idx + 1)..max_rowspan_check {
                                if let Some(next_row) = rows.get(next_row_idx) {
                                    if let Some(next_cells) = next_row.get("cells").and_then(|v| v.as_array()) {
                                        // Find cell at same column position (accounting for grid_span)
                                        let mut next_col_pos = 0;
                                        let mut found_continue = false;
                                        
                                        for next_cell in next_cells {
                                            let next_grid_span = next_cell.get("grid_span")
                                                .or_else(|| next_cell.get("gridSpan"))
                                                .and_then(|v| {
                                                    if let Some(n) = v.as_u64() {
                                                        Some(n as usize)
                                                    } else if let Some(s) = v.as_str() {
                                                        s.parse::<usize>().ok()
                                                    } else {
                                                        None
                                                    }
                                                })
                                                .unwrap_or(1);
                                            
                                            let next_vmerge = next_cell.get("vertical_merge_type")
                                                .or_else(|| next_cell.get("vMerge"))
                                                .and_then(|v| {
                                                    if let Some(s) = v.as_str() {
                                                        Some(s)
                                                    } else if let Some(obj) = v.as_object() {
                                                        obj.get("val").and_then(|v| v.as_str())
                                                    } else {
                                                        None
                                                    }
                                                });
                                            
                                            // Check if this cell is at the right column position
                                            if next_col_pos == col_idx && next_vmerge == Some("continue") {
                                                cell_rowspan += 1;
                                                found_continue = true;
                                                break;
                                            }
                                            
                                            next_col_pos += next_grid_span;
                                        }
                                        
                                        if !found_continue {
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Check if this cell should be rendered (not already rendered as part of a merge)
                        if rendered_cells.contains(&(row_idx, col_idx)) {
                            col_idx += grid_span;
                            continue;
                        }
                        
                        // Mark all cells covered by this cell as rendered
                        for r in row_idx..(row_idx + cell_rowspan) {
                            for c in col_idx..(col_idx + grid_span) {
                                rendered_cells.insert((r, c));
                            }
                        }
                        
                        // Calculate cell rect if not present
                        let cell_rect = if let Some(cell_rect_json) = cell.get("rect") {
                            // Use existing rect
                            serde_json::from_value(cell_rect_json.clone())
                                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                                    format!("Failed to parse cell rect: {}", e)
                                ))?
                        } else {
                            // Calculate rect from col_widths and row_heights
                            // Calculate cell width (sum of column widths it spans)
                            let cell_width = if col_idx + grid_span <= col_widths.len() {
                                col_widths[col_idx..col_idx + grid_span].iter().sum()
                            } else if col_idx < col_widths.len() {
                                col_widths[col_idx]
                            } else {
                                rect.width / col_widths.len() as f64 * grid_span as f64
                            };
                            
                            // Calculate cell height (sum of row heights it spans)
                            let cell_height = if row_idx + cell_rowspan <= row_heights.len() {
                                row_heights[row_idx..row_idx + cell_rowspan].iter().sum()
                            } else if row_idx < row_heights.len() {
                                row_heights[row_idx]
                            } else {
                                rect.height / row_heights.len() as f64 * cell_rowspan as f64
                            };
                            
                            // Calculate X position (sum of column widths before this cell)
                            let cell_x = rect.x + col_widths[0..col_idx].iter().sum::<f64>();
                            
                            // Calculate Y position (top of table minus sum of row heights before this cell)
                            let cell_y = rect.top() - row_heights[0..row_idx].iter().sum::<f64>() - cell_height;
                            
                            Rect::new(cell_x, cell_y, cell_width, cell_height)
                        };
                        
                        // Adjust cell rect if it spans multiple rows/columns
                        // The rect should already be calculated correctly by the layout engine,
                        // but we can verify or adjust if needed
                        
                        // Draw cell background
                        if let Some(bg_color) = cell.get("background_color") {
                            let color = parse_color(bg_color);
                            canvas.save_state();
                            canvas.set_fill_color(color);
                            canvas.rect(cell_rect, true, false);
                            canvas.restore_state();
                        }
                        
                        // Draw cell border
                        if let Some(border) = cell.get("border") {
                            Self::draw_border(canvas, &cell_rect, border)?;
                        } else if let Some(borders) = cell.get("borders") {
                            Self::draw_borders(canvas, &cell_rect, borders)?;
                        } else {
                            // Default: draw thin border if no border specified
                            canvas.save_state();
                            canvas.set_stroke_color(Color::rgb(200.0 / 255.0, 200.0 / 255.0, 200.0 / 255.0));
                            canvas.set_line_width(0.5);
                            canvas.rect(cell_rect, false, true);
                            canvas.restore_state();
                        }
                        
                        // Draw cell content - check for paragraphs, content array, or simple text
                        let cell_content = cell.get("content");
                        let cell_style = cell.get("style");
                        
                        // Check if cell has paragraphs (list of paragraph blocks)
                        if let Some(paragraphs) = cell.get("paragraphs").and_then(|v| v.as_array()) {
                            // Render paragraphs in cell
                            Self::render_cell_paragraphs(canvas, pdf, fonts_registry, images_registry, images_used_on_current_page, &cell_rect, paragraphs, cell_style, current_page_number, total_pages)?;
                        } else if let Some(content_array) = cell_content.and_then(|c| c.as_array()) {
                            // Content is an array (paragraphs, images, etc.)
                            
                            // Check for direct images in cell content array
                            for item in content_array {
                                if let Some(item_obj) = item.as_object() {
                                    if let Some(images) = item_obj.get("images").and_then(|v| v.as_array()) {
                                        // Render images from cell content
                                        eprintln!("      Found {} images in cell content array item", images.len());
                                        for (img_idx, img) in images.iter().enumerate() {
                                            let img_path = img.get("path")
                                                .or_else(|| img.get("image_path"))
                                                .and_then(|v| v.as_str());
                                            let stream_key = img.get("stream_key")
                                                .and_then(|v| v.as_str());
                                            // Get image dimensions from DOCX (in EMU) for proper SVG conversion
                                            let img_width_emu = img.get("width")
                                                .and_then(|v| v.as_f64().or_else(|| v.as_i64().map(|i| i as f64)));
                                            let img_height_emu = img.get("height")
                                                .and_then(|v| v.as_f64().or_else(|| v.as_i64().map(|i| i as f64)));
                                            
                                            if stream_key.is_some() || img_path.is_some() {
                                                eprintln!("      Rendering image {} from cell content array: stream_key={:?} path={:?}", img_idx, stream_key, img_path);
                                                let image_result = if let Some(key) = stream_key {
                                                    images_registry.get_or_create_from_stream(pdf, key, img_width_emu, img_height_emu)
                                                } else {
                                                    let path = img_path.unwrap_or_default();
                                                    images_registry.get_or_create_from_path_with_dims(pdf, path, img_width_emu, img_height_emu)
                                                };
                                                
                                                match image_result {
                                                    Ok((_image_id, image_name)) => {
                                                        images_used_on_current_page.insert(image_name, _image_id);
                                                        // Use cell dimensions for image size
                                                        let img_width = img_width_emu.unwrap_or(cell_rect.width * 0.3);
                                                        let img_height = img_height_emu.unwrap_or(cell_rect.height * 0.8);
                                                        // Convert EMU to points if needed
                                                        let emu_to_pt = 72.0 / 914400.0;
                                                        let final_width = if img_width > 1000.0 {
                                                            img_width * emu_to_pt
                                                        } else {
                                                            img_width
                                                        };
                                                        let final_height = if img_height > 1000.0 {
                                                            img_height * emu_to_pt
                                                        } else {
                                                            img_height
                                                        };
                                                        eprintln!("      Drawing image from cell content array at ({:.2}, {:.2}) size ({:.2}, {:.2})", cell_rect.x, cell_rect.y, final_width, final_height);
                                                        canvas.draw_image(image_name, cell_rect.x, cell_rect.y, final_width, final_height);
                                                    }
                                                    Err(e) => {
                                                        warn!("Failed to load image from cell content array[{}]: {}", img_idx, e);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Extract paragraphs from content array
                            // Collect as Vec<Value> (cloned) to match function signature
                            let paragraphs: Vec<serde_json::Value> = content_array.iter()
                                .filter(|item| {
                                    // Check if item is a paragraph (has type="paragraph" or has layout_payload or has runs/children)
                                    if let Some(obj) = item.as_object() {
                                        obj.get("type").and_then(|v| v.as_str()) == Some("paragraph")
                                            || obj.get("layout_payload").is_some()
                                            || obj.get("_layout_payload").is_some()
                                            || obj.get("lines").is_some()
                                            || obj.get("runs").is_some()
                                            || obj.get("children").is_some()
                                    } else {
                                        false
                                    }
                                })
                                .cloned()
                                .collect();
                            
                            if !paragraphs.is_empty() {
                                Self::render_cell_paragraphs(canvas, pdf, fonts_registry, images_registry, images_used_on_current_page, &cell_rect, &paragraphs, cell_style, current_page_number, total_pages)?;
                            } else {
                                // Fallback: treat all items as paragraphs
                                let all_items: Vec<serde_json::Value> = content_array.iter().cloned().collect();
                                Self::render_cell_paragraphs(canvas, pdf, fonts_registry, images_registry, images_used_on_current_page, &cell_rect, &all_items, cell_style, current_page_number, total_pages)?;
                            }
                        } else if let Some(text) = cell_content.and_then(|c| c.as_str()) {
                            // Simple text content - draw_text is deprecated, skip for now
                            warn!("Simple text in cell (draw_text deprecated) - skipping");
                        } else if let Some(content_obj) = cell_content.and_then(|c| c.as_object()) {
                            // Content might be a dict with layout_payload or text
                            if content_obj.get("layout_payload").is_some() 
                                || content_obj.get("_layout_payload").is_some()
                                || content_obj.get("lines").is_some() {
                                // Has ParagraphLayout payload
                                let default_style = serde_json::json!({});
                                let cell_style = cell_style.unwrap_or(&default_style);
                                Self::render_paragraph_from_layout(canvas, pdf, fonts_registry, images_registry, images_used_on_current_page, &cell_rect, cell_content.unwrap(), cell_style, current_page_number, total_pages)?;
                            } else if let Some(_text) = content_obj.get("text").and_then(|v| v.as_str()) {
                                // Has text field - draw_text is deprecated, skip for now
                                warn!("Simple text in cell (draw_text deprecated) - skipping");
                            }
                        }
                        
                        col_idx += grid_span;
                    }
                }
            }
        } else {
            warn!("Table block has no 'rows' array in content");
            // Try to render table background and border even if no rows
            if let Some(bg_color) = content.get("background_color") {
                let color = parse_color(bg_color);
                canvas.save_state();
                canvas.set_fill_color(color);
                canvas.rect(*rect, true, false);
                canvas.restore_state();
            }
            
            if let Some(border) = content.get("border") {
                Self::draw_border(canvas, rect, border)?;
            } else if let Some(borders) = content.get("borders") {
                Self::draw_borders(canvas, rect, borders)?;
            }
        }
        
        Ok(())
    }
    
    /// [DEPRECATED] Render image block - use BlockRenderer::render_image instead
    #[allow(dead_code)]
    pub fn render_image(
        _canvas: &mut PdfCanvas,
        _pdf: &mut Pdf,
        _fonts: &mut HashMap<String, (Ref, Name<'static>)>,
        _font_paths: &mut HashMap<String, String>,
        _next_ref_id: &mut i32,
        _block: &LayoutBlock,
        _font_objects: &mut Vec<(Ref, String)>,
    ) -> PyResult<()> {
        // This function is deprecated - use BlockRenderer::render_image instead
        Ok(())
    }
    
    /// Render image placeholder (fallback)
    fn render_image_placeholder(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        rect: &Rect,
        message: &str,
    ) -> PyResult<()> {
        canvas.save_state();
        canvas.set_stroke_color(Color::rgb(0.8, 0.8, 0.8));
        canvas.set_line_width(1.0);
        canvas.rect(*rect, false, true);
        
        // Draw placeholder text
        canvas.set_fill_color(Color::rgb(0.6, 0.6, 0.6));
        let font_ref = fonts_registry.get_or_builtin(pdf, "Helvetica-Oblique");
        canvas.set_font(font_ref, 10.0);
        let placeholder_text = if message.len() > 30 {
            {
                // Safely truncate message to 30 chars (handling Unicode)
                let truncated: String = message.chars().take(30).collect();
                format!("{}...", truncated)
            }
        } else {
            message.to_string()
        };
        canvas.draw_string(rect.x + 5.0, rect.y + rect.height / 2.0, &placeholder_text);
        canvas.restore_state();
        
        Ok(())
    }
    
    /// Render textbox block
    fn render_textbox(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        block: &LayoutBlock,
    ) -> PyResult<()> {
        let rect = &block.frame;
        let content = &block.content;
        let style = &block.style;
        
        // Draw background
        if let Some(bg_color) = style.get("background_color") {
            let color = parse_color(bg_color);
            canvas.save_state();
            canvas.set_fill_color(color);
            canvas.rect(*rect, true, false);
            canvas.restore_state();
        }
        
        // Draw text
        if let Some(text) = content.get("content").and_then(|v| v.as_str())
            .or_else(|| content.get("text").and_then(|v| v.as_str())) {
            // draw_text is deprecated - skip for now (assembler should provide layout_payload)
            warn!("Simple text in textbox (draw_text deprecated) - skipping");
        }
        
        Ok(())
    }
    
    /// Render rectangle/rect block (filled or stroked rectangle)
    fn render_rectangle(canvas: &mut PdfCanvas, block: &LayoutBlock) -> PyResult<()> {
        let rect = &block.frame;
        let style = &block.style;
        
        canvas.save_state();
        
        // Draw background (fill)
        if let Some(bg_color) = style.get("background_color")
            .or_else(|| style.get("background"))
            .or_else(|| style.get("fill")) {
            let color = parse_color(bg_color);
            canvas.set_fill_color(color);
            canvas.rect(*rect, true, false);
        }
        
        // Draw border (stroke)
        if let Some(border_color) = style.get("border_color")
            .or_else(|| style.get("stroke")) {
            let color = parse_color(border_color);
            let line_width = json_helpers::get_f64_opt(style, "border_width")
                .or_else(|| json_helpers::get_f64_opt(style, "line_width"))
                .unwrap_or(1.0);
            canvas.set_stroke_color(color);
            canvas.set_line_width(line_width);
            canvas.rect(*rect, false, true);
        } else if let Some(border) = style.get("border") {
            // Border can be a string like "1pt solid #000000" or an object
            Self::draw_border(canvas, rect, border)?;
        } else if let Some(borders) = style.get("borders") {
            // Multiple borders (top, right, bottom, left)
            Self::draw_borders(canvas, rect, borders)?;
        } else {
            // Default: draw thin border if no fill
            if style.get("background_color").is_none() && style.get("background").is_none() {
                canvas.set_stroke_color(Color::rgb(0.0, 0.0, 0.0));
                canvas.set_line_width(0.5);
                canvas.rect(*rect, false, true);
            }
        }
        
        canvas.restore_state();
        Ok(())
    }
    
    /// Render decorator block
    fn render_decorator(canvas: &mut PdfCanvas, block: &LayoutBlock) -> PyResult<()> {
        let rect = &block.frame;
        let style = &block.style;
        
        // Draw background
        if let Some(bg_color) = style.get("background_color") {
            let color = parse_color(bg_color);
            canvas.save_state();
            canvas.set_fill_color(color);
            canvas.rect(*rect, true, false);
            canvas.restore_state();
        }
        
        // Draw border
        if let Some(border) = style.get("border") {
            Self::draw_border(canvas, rect, border)?;
        }
        
        Ok(())
    }
    
    /// Render watermark block
    /// Watermarks are rendered with rotation and transparency, centered on the page
    fn render_watermark(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_registry: &mut crate::image_registry::ImageRegistry,
        block: &LayoutBlock,
    ) -> PyResult<()> {
        let rect = &block.frame;
        let content = &block.content;
        let style = &block.style;
        
        // Get watermark properties
        let watermark_type = content.get("type")
            .and_then(|v| v.as_str())
            .unwrap_or_else(|| block.block_type.as_str());
        
        // Get rotation angle (default -45 degrees)
        let rotation = style.get("rotation")
            .and_then(|v| v.as_f64())
            .unwrap_or(-45.0);
        
        // Calculate center of the page (use rect as page bounds)
        let center_x = rect.x + rect.width / 2.0;
        let center_y = rect.y + rect.height / 2.0;
        
        canvas.save_state();
        
        // Translate to center, rotate, then translate back
        canvas.translate(center_x, center_y);
        canvas.rotate(rotation);
        canvas.translate(-center_x, -center_y);
        
        // Render watermark content
        match watermark_type {
            "image" => {
                // Render as image watermark
                if let Some(image_path) = content.get("path").and_then(|v| v.as_str()) {
                    // Watermarks typically don't have EMU dimensions, use None
                    match images_registry.get_or_create_from_path(pdf, image_path) {
                        Ok((_image_id, image_name)) => {
                            // Scale image to reasonable watermark size
                            let watermark_width = rect.width.min(rect.height) * 0.6;
                            let watermark_height = watermark_width * (rect.height / rect.width);
                            let x = center_x - watermark_width / 2.0;
                            let y = center_y - watermark_height / 2.0;
                            canvas.draw_image(image_name, x, y, watermark_width, watermark_height);
                        }
                        Err(_) => {
                            // Fallback: render text placeholder
                            Self::render_watermark_text(canvas, pdf, fonts_registry, center_x, center_y, "WATERMARK", style)?;
                        }
                    }
                }
            }
            "textbox" | "vml_shape" | _ => {
                // Render as text watermark
                let text = content.get("text_content")
                    .or_else(|| content.get("text"))
                    .or_else(|| content.get("content"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("WATERMARK");
                
                Self::render_watermark_text(canvas, pdf, fonts_registry, center_x, center_y, text, style)?;
            }
        }
        
        canvas.restore_state();
        
        Ok(())
    }
    
    /// Render watermark text (helper for render_watermark)
    fn render_watermark_text(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        x: f64,
        y: f64,
        text: &str,
        style: &serde_json::Value,
    ) -> PyResult<()> {
        // Get font properties
        let font_name = style.get("font_name")
            .or_else(|| style.get("font"))
            .and_then(|v| v.as_str())
            .unwrap_or("Helvetica");
        
        let font_size = style.get("font_size")
            .or_else(|| style.get("size"))
            .and_then(|v| v.as_f64())
            .unwrap_or(72.0); // Large font for watermark
        
        // Get color (default to light gray)
        let default_color = serde_json::Value::String("#C0C0C0".to_string());
        let color_value = style.get("color")
            .or_else(|| style.get("fillcolor"))
            .unwrap_or(&default_color);
        
        let color = parse_color(color_value);
        
        // Get font
        let font_ref = fonts_registry.get_or_builtin(pdf, font_name);
        
        canvas.save_state();
        canvas.set_font(font_ref, font_size);
        canvas.set_fill_color(color);
        
        // Center text horizontally
        let text_x = x;
        let text_y = y;
        
        canvas.draw_string(text_x, text_y, text);
        canvas.restore_state();
        
        Ok(())
    }
    
    /// Render header block
    /// Headers are rendered similar to paragraphs but with special positioning
    fn render_header(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_registry: &mut crate::image_registry::ImageRegistry,
        block: &LayoutBlock,
        current_page_number: u32,
        total_pages: u32,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
    ) -> PyResult<()> {
        let rect = &block.frame;
        let content = &block.content;
        let style = &block.style;
        
        // Draw background and border
        if let Some(bg_color) = style.get("background_color") {
            let color = parse_color(bg_color);
            canvas.save_state();
            canvas.set_fill_color(color);
            canvas.rect(*rect, true, false);
            canvas.restore_state();
        }
        
        if let Some(border) = style.get("border") {
            Self::draw_border(canvas, rect, border)?;
        } else if let Some(borders) = style.get("borders") {
            Self::draw_borders(canvas, rect, borders)?;
        }
        
        // Check for images in header - try multiple locations
        // 1. Direct images in content (deduplicate by path, skip anchor images - they're in overlays)
        eprintln!("   render_header: checking for images in content.images");
        if let Some(images) = content.get("images").and_then(|v| v.as_array()) {
            eprintln!("   render_header: found {} images in content.images", images.len());
            // Deduplicate images by path to avoid rendering the same image twice
            // Also skip images with anchor_type="anchor" - they should be rendered as overlays, not here
            let mut seen_keys = std::collections::HashSet::new();
            let mut unique_images = Vec::new();
            for img in images {
                // Skip anchor images - they're handled in overlays
                let anchor_type = img.get("anchor_type")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                eprintln!("   Checking image: anchor_type={:?} img_keys={:?}", 
                    anchor_type,
                    img.as_object().map(|o| o.keys().collect::<Vec<_>>())
                );
                if anchor_type == "anchor" {
                    eprintln!("   Skipping anchor image (will be in overlays)");
                    continue; // Skip anchor images - they're in overlays
                }
                let stream_key = img.get("stream_key").and_then(|v| v.as_str());
                let img_path = img.get("path")
                    .or_else(|| img.get("image_path"))
                    .and_then(|v| v.as_str());
                let dedup_key = stream_key
                    .map(|k| format!("stream:{}", k))
                    .or_else(|| img_path.map(|p| format!("path:{}", p)));
                if let Some(key) = &dedup_key {
                    if seen_keys.insert(key.clone()) {
                        eprintln!("   Adding unique image with key={}", key);
                        unique_images.push(img);
                    } else {
                        eprintln!("   Skipping duplicate image with key={}", key);
                    }
                } else {
                    eprintln!("   Skipping image with no stream_key or path");
                }
            }
            
            if unique_images.is_empty() {
                // No unique images, skip
            } else {
                let mut x = rect.x;
                // For headers, position at top of rect; for footers, position at bottom
                // Use block_type to determine positioning
                let is_header_block = block.block_type == "header";
                // In PDF coordinates: Y=0 at bottom, Y increases upward
                // Header: position at top of rect (rect.y + rect.height is the top edge)
                // Footer: position at bottom of rect (rect.y is the bottom edge)
                let y = if is_header_block {
                    // Header: position at top of rect
                    rect.y + rect.height
                } else {
                    // Footer: position at bottom of rect
                    rect.y
                };
                
                debug!(
                    "Rendering {} unique images in {}: rect=({}, {}), size=({}, {}), base_y={}",
                    unique_images.len(),
                    if is_header_block { "header" } else { "footer" },
                    rect.x,
                    rect.y,
                    rect.width,
                    rect.height,
                    y
                );
                
                for img in unique_images {
                    let stream_key = img.get("stream_key").and_then(|v| v.as_str());
                    let img_path = img.get("path")
                        .or_else(|| img.get("image_path"))
                        .and_then(|v| v.as_str());
                    eprintln!(
                        "{} image candidate: stream_key={:?} path={:?} img_keys={:?}",
                        block.block_type,
                        stream_key,
                        img_path,
                        img.as_object().map(|o| o.keys().collect::<Vec<_>>())
                    );
                    if stream_key.is_none() && img_path.is_none() {
                        eprintln!(
                            "Skipping {} image with no stream_key/path (block rect=({}, {}))",
                            block.block_type,
                            rect.x,
                            rect.y
                        );
                        continue;
                    }
                    
                    // Get image dimensions from DOCX (in EMU) for proper SVG conversion
                    // Dimensions can be f64 or i64 in JSON
                    let width_emu = img.get("width")
                        .and_then(|v| {
                            v.as_i64().map(|i| i as f64)
                                .or_else(|| v.as_f64())
                        });
                    let height_emu = img.get("height")
                        .and_then(|v| {
                            v.as_i64().map(|i| i as f64)
                                .or_else(|| v.as_f64())
                        });
                    
                    if let (Some(w), Some(h)) = (width_emu, height_emu) {
                        eprintln!("   Header image dimensions from DOCX: {}x{} EMU", w, h);
                    } else {
                        eprintln!("   Header image: width_emu={:?}, height_emu={:?}, img_keys={:?}", 
                            width_emu, height_emu, 
                            img.as_object().map(|o| o.keys().collect::<Vec<_>>()));
                    }
                    
                    let image_result = if let Some(key) = stream_key {
                        eprintln!("Requesting image from stream key {}", key);
                        images_registry.get_or_create_from_stream(pdf, key, width_emu, height_emu)
                    } else if let Some(path) = img_path {
                        eprintln!("Requesting image from path {}", path);
                        images_registry.get_or_create_from_path_with_dims(pdf, path, width_emu, height_emu)
                    } else {
                        continue;
                    };
                    
                    match image_result {
                        Ok((_image_id, image_name)) => {
                            eprintln!(
                                "{} image registered name={} ref={:?}",
                                block.block_type,
                                String::from_utf8_lossy(image_name.0),
                                _image_id
                            );
                            images_used_on_current_page.insert(image_name, _image_id);
                            
                            // Calculate image size - convert from EMU to points if needed
                            // EMU to points: 914400 EMU = 1 inch = 72 points, so 1 point = 914400/72 = 12700 EMU
                            let emu_to_pt = 72.0 / 914400.0;
                            let raw_width = img.get("width").and_then(|v| v.as_f64()).unwrap_or(0.0);
                            let raw_height = img.get("height").and_then(|v| v.as_f64()).unwrap_or(0.0);
                            
                            // If dimensions are very large (> 1000), assume they're in EMU and convert
                            let img_width = if raw_width > 1000.0 {
                                raw_width * emu_to_pt
                            } else {
                                raw_width
                            };
                            let img_height = if raw_height > 1000.0 {
                                raw_height * emu_to_pt
                            } else {
                                raw_height
                            };
                            
                            // Use converted dimensions if valid, otherwise scale to fit rect
                            // Don't limit by rect.height * 2.0 - images in headers/footers can be taller than the rect
                            let final_width = if img_width > 0.0 {
                                // Use converted width, but don't exceed rect width
                                img_width.min(rect.width)
                            } else {
                                rect.width / images.len() as f64
                            };
                            
                            let final_height = if img_height > 0.0 {
                                // Use converted height - don't limit by rect.height, images can extend beyond rect
                                // But preserve aspect ratio if width was scaled
                                if img_width > 0.0 && final_width < img_width {
                                    let aspect = img_height / img_width;
                                    final_width * aspect
                                } else {
                                    img_height
                                }
                            } else {
                                rect.height * 0.8
                            };
                            
                            let source_label = stream_key.unwrap_or_else(|| img_path.unwrap_or(""));
                            debug!("Rendering image in header: source={}, size={}x{} (from {}x{} EMU), pos=({}, {})", 
                                source_label, final_width, final_height, raw_width, raw_height, x, y);
                            
                            // Position image: for headers, align to top; for footers, align to bottom
                            let image_y = if is_header_block {
                                // Header: align to top
                                y - final_height
                            } else {
                                // Footer: align to bottom
                                y
                            };
                            
                            canvas.draw_image(image_name, x, image_y, final_width, final_height);
                            x += final_width + 5.0; // Add spacing
                        }
                        Err(e) => {
                            warn!(
                                "Failed to load {} image (stream={:?} path={:?}): {}",
                                block.block_type,
                                stream_key,
                                img_path,
                                e
                            );
                            continue;
                        }
                    }
                }
            }
        }
        
        // 2. Render overlays (floating images/textboxes)
        // Overlays can be in payload.overlays or directly in content (for GenericLayout blocks)
        let overlays = content.get("payload")
            .and_then(|p| p.as_object())
            .and_then(|p| p.get("overlays"))
            .and_then(|v| v.as_array())
            .or_else(|| {
                // Also check if content itself has overlays (for GenericLayout)
                if let Some(content_obj) = content.as_object() {
                    content_obj.get("overlays").and_then(|v| v.as_array())
                } else {
                    None
                }
            });
        eprintln!("   render_header: checking for overlays, found={:?}", overlays.is_some());
        if let Some(ov) = &overlays {
            eprintln!("   render_header: overlays array length={}", ov.len());
        }
        
        if let Some(overlays_array) = overlays {
            if !overlays_array.is_empty() {
                let block_type_str = if block.block_type == "header" { "header" } else { "footer" };
                eprintln!("Rendering {} overlays in {}", overlays_array.len(), block_type_str);
                crate::overlays::render_overlays(
                    canvas,
                    pdf,
                    fonts_registry,
                    images_registry,
                    overlays_array,
                    images_used_on_current_page,
                )?;
            }
        }
        
        // Render text content (if has ParagraphLayout)
        if content.get("layout_payload").is_some() 
            || content.get("_layout_payload").is_some()
            || content.get("lines").is_some() {
            Self::render_paragraph_from_layout(canvas, pdf, fonts_registry, images_registry, images_used_on_current_page, rect, content, style, current_page_number, total_pages)?;
        } else if let Some(_text) = content.get("text").and_then(|v| v.as_str()) {
            // Simple text fallback - draw_text is deprecated
            warn!("Simple text in header (draw_text deprecated) - skipping");
        }
        
        Ok(())
    }
    
    /// Render footer block
    /// Footers are rendered similar to headers
    fn render_footer(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_registry: &mut crate::image_registry::ImageRegistry,
        block: &LayoutBlock,
        current_page_number: u32,
        total_pages: u32,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
    ) -> PyResult<()> {
        // Footers are rendered the same way as headers
        Self::render_header(canvas, pdf, fonts_registry, images_registry, block, current_page_number, total_pages, images_used_on_current_page)
    }
    
    /// Render footnotes block
    /// Footnotes are rendered with a separator line and numbered content
    fn render_footnotes(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        block: &LayoutBlock,
    ) -> PyResult<()> {
        let rect = &block.frame;
        let content = &block.content;
        
        // Get footnotes array
        let empty_vec: Vec<serde_json::Value> = Vec::new();
        let footnotes = content.get("footnotes")
            .and_then(|v| v.as_array())
            .unwrap_or(&empty_vec);
        
        if footnotes.is_empty() {
            return Ok(());
        }
        
        // Set font for footnotes (smaller than body text)
        let font_name = "Helvetica";
        let font_size = 9.0;
        let font_ref = fonts_registry.get_or_builtin(pdf, font_name);
        
        canvas.save_state();
        canvas.set_font(font_ref, font_size);
        let black_color = parse_color(&serde_json::Value::String("#000000".to_string()));
        canvas.set_fill_color(black_color);
        
        // Draw separator line (40% width, aligned left)
        let separator_y = rect.y + rect.height - 4.0;
        let separator_width = rect.width * 0.4;
        let separator_x = rect.x;
        
        canvas.set_stroke_color(black_color);
        canvas.set_line_width(0.5);
        canvas.line(separator_x, separator_y, separator_x + separator_width, separator_y);
        
        // Render footnotes
        let mut y = separator_y - 4.0 - font_size;
        let x_start = rect.x;
        let line_height = font_size * 1.2;
        
        for footnote in footnotes {
            if y < rect.y {
                break; // No more space
            }
            
            let footnote_number = footnote.get("number")
                .and_then(|v| v.as_str())
                .unwrap_or("?");
            
            let footnote_content = footnote.get("content")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            
            // Render footnote number (as superscript)
            let ref_font_size = font_size * 0.58;
            let superscript_shift = font_size * 0.33;
            
            canvas.save_state();
            canvas.set_font(font_ref, ref_font_size);
            let number_y = y + superscript_shift;
            canvas.draw_string(x_start, number_y, footnote_number);
            // Estimate number width (approximate)
            let number_width = ref_font_size * footnote_number.len() as f64 * 0.6;
            canvas.restore_state();
            
            // Render footnote content
            let text_x = x_start + number_width + 2.0;
            let max_width = rect.x + rect.width - text_x;
            
            // Simple text wrapping (basic implementation)
            let words: Vec<&str> = footnote_content.split_whitespace().collect();
            let mut current_line = String::new();
            let mut current_y = y;
            
            for word in words {
                let test_line = if current_line.is_empty() {
                    word.to_string()
                } else {
                    format!("{} {}", current_line, word)
                };
                
                // Estimate width (approximate: 0.6 * font_size per character)
                let estimated_width = test_line.len() as f64 * font_size * 0.6;
                
                if estimated_width > max_width && !current_line.is_empty() {
                    // Draw current line and start new line
                    canvas.draw_string(text_x, current_y, &current_line);
                    current_y -= line_height;
                    if current_y < rect.y {
                        break;
                    }
                    current_line = word.to_string();
                } else {
                    current_line = test_line;
                }
            }
            
            // Draw remaining line
            if !current_line.is_empty() && current_y >= rect.y {
                canvas.draw_string(text_x, current_y, &current_line);
            }
            
            y = current_y - line_height;
        }
        
        canvas.restore_state();
        
        Ok(())
    }
    
    /// Render endnotes block
    /// Endnotes are rendered similar to footnotes
    fn render_endnotes(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        block: &LayoutBlock,
    ) -> PyResult<()> {
        // Endnotes are rendered the same way as footnotes
        Self::render_footnotes(canvas, pdf, fonts_registry, images_used_on_current_page, block)
    }
    
    /// Render generic block
    fn render_generic(canvas: &mut PdfCanvas, block: &LayoutBlock) -> PyResult<()> {
        let rect = &block.frame;
        
        // Draw placeholder
        canvas.save_state();
        canvas.set_stroke_color(Color::rgb(0.8, 0.8, 0.8));
        canvas.set_line_width(0.5);
        canvas.rect(*rect, false, true);
        canvas.restore_state();
        
        Ok(())
    }
    
    /// Render paragraph from pre-calculated ParagraphLayout payload
    ///
    /// This function renders a paragraph using the pre-calculated layout from the assembler.
    /// All positions, line breaks, and inline item positions are already calculated.
    /// This function only renders what it receives - it does NOT perform any calculations.
    pub(crate) fn render_paragraph_from_layout(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_registry: &mut crate::image_registry::ImageRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        rect: &Rect,
        content: &serde_json::Value,
        base_style: &serde_json::Value,
        current_page_number: u32,
        total_pages: u32,
    ) -> PyResult<()> {
        eprintln!("      render_paragraph_from_layout called with rect={:?}", rect);
        // Get ParagraphLayout payload (required from assembler)
        let layout_payload = content.get("layout_payload")
            .or_else(|| content.get("_layout_payload"))
            .or_else(|| content.get("lines").map(|_| content)); // Fallback: use content if it has lines
        
        // Debug: log if layout_payload is missing
        if layout_payload.is_none() {
            // Try to see what keys are available in content
            if let Some(content_obj) = content.as_object() {
                let keys: Vec<&str> = content_obj.keys().map(|k| k.as_str()).collect();
                warn!("No layout_payload found. Content keys: {:?}", keys);
            }
        }
        
        // Parse paragraph style from base_style (needed for padding calculation and fallback)
        let mut para_style = ParagraphStyle::from_json(base_style);
        
        let layout = match layout_payload {
            Some(payload) => {
                // Debug: check if payload has lines
                if let Some(lines) = payload.get("lines").and_then(|l| l.as_array()) {
                    debug!("Found layout_payload with {} lines", lines.len());
                } else {
                    warn!("layout_payload found but has no lines array");
                }
                payload
            },
            None => {
                // Unified layout should always provide layout_payload with pre-calculated lines.
                // If layout_payload is missing, this is an error in the assembler.
                warn!(
                    "Paragraph has no layout_payload. Unified layout should provide pre-calculated layout_payload with lines. rect={:?}",
                    rect
                );
                // Log content keys for debugging
                if let Some(content_obj) = content.as_object() {
                    let keys: Vec<&str> = content_obj.keys().map(|k| k.as_str()).collect();
                    warn!("Content keys: {:?}", keys);
                    // Check if there's text in runs that should have been laid out
                    if let Some(runs) = content_obj.get("runs").and_then(|v| v.as_array()) {
                        warn!("Paragraph has {} runs but no layout_payload - assembler should create layout_payload with lines", runs.len());
                    }
                }
                return Ok(());
            }
        };
        
        // Override paragraph style with metadata if available
        let metadata = layout.get("metadata").and_then(|m| m.as_object());
        if let Some(meta) = metadata {
            if para_style.font_name.is_none() {
                para_style.font_name = meta.get("font_name")
                    .or_else(|| meta.get("font_ascii"))
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
            }
            if para_style.font_size.is_none() {
                para_style.font_size = meta.get("font_size").and_then(|v| v.as_f64());
            }
            if para_style.color.is_none() {
                para_style.color = meta.get("font_color")
                    .or_else(|| meta.get("color"))
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
            }
            if para_style.text_align.is_none() && para_style.alignment.is_none() {
                para_style.text_align = meta.get("raw_style")
                    .and_then(|s| s.as_object())
                    .and_then(|s| s.get("justification"))
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
            }
        }
        
        // Check for marker_override_text in metadata - this should override marker.text
        // Also check content.meta.marker_override_text (different key name)
        let marker_override_text = metadata
            .and_then(|m| m.get("marker_override_text"))
            .and_then(|v| v.as_str())
            .or_else(|| {
                content.get("meta")
                    .and_then(|m| m.as_object())
                    .and_then(|m| m.get("marker_override_text"))
                    .and_then(|v| v.as_str())
            });
        
        // Get padding
        let padding = para_style.padding();
        
        // Calculate text area (rect minus padding)
        let text_left = rect.x + padding.left;
        let text_top = rect.top() - padding.top;
        
        // Get paragraph alignment
        let paragraph_alignment = para_style.text_align();
        
        // Get defaults for font and color
        let default_font_name = para_style.font_name();
        let default_font_size = para_style.font_size();
        let default_color = para_style.color();
        
        // Get lines from layout
        let empty_lines: Vec<serde_json::Value> = vec![];
        let lines = json_helpers::get_array_opt(layout, "lines")
            .unwrap_or(&empty_lines);
        
        // Validate that we have lines (assembler should have prepared them)
        let lines_count = lines.len();
        if lines_count == 0 {
            // Unified layout should have everything pre-calculated.
            // If layout_payload exists but has no lines, this is an error in the assembler.
            warn!(
                "Paragraph has layout_payload but no lines. Unified layout should provide pre-calculated lines. rect={:?}",
                rect
            );
            // Log content keys for debugging
            if let Some(content_obj) = content.as_object() {
                let keys: Vec<&str> = content_obj.keys().map(|k| k.as_str()).collect();
                warn!("Content keys: {:?}", keys);
                // Check if there's text in runs that should have been laid out
                if let Some(runs) = content_obj.get("runs").and_then(|v| v.as_array()) {
                    warn!("Paragraph has {} runs but no lines - assembler should create layout_payload with lines", runs.len());
                }
            }
            return Ok(());
        }
        
        // Limit number of lines to prevent infinite loops (safety limit: 10000 lines per paragraph)
        const MAX_LINES: usize = 10000;
        if lines_count > MAX_LINES {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Paragraph has too many lines: {} (max {})", lines_count, MAX_LINES)
            ));
        }
        let max_lines = lines_count.min(MAX_LINES);
        
        // Get font metrics for proper baseline and line height calculation
        let font_metrics = fonts_registry.get_font_metrics(default_font_name, default_font_size);
        let scale = default_font_size / 1000.0; // Approximate scale (units_per_em is typically 1000)
        let line_height = font_metrics.line_height(scale);
        
        // Check for marker (list numbering/bullet) - render before first line
        // Marker can be in multiple locations:
        // 1. content.marker (direct)
        // 2. content.meta.marker (in metadata)
        // 3. content.payload.marker (in payload)
        // 4. content.raw.marker (in raw element)
        // 5. layout.marker (in layout payload)
        // 6. layout.metadata.marker (in layout metadata)
        let marker = content.get("marker")
            .and_then(|m| m.as_object())
            .or_else(|| {
                // Check content.meta.marker
                content.get("meta")
                    .and_then(|m| m.as_object())
                    .and_then(|m| m.get("marker"))
                    .and_then(|m| m.as_object())
            })
            .or_else(|| {
                // Check content.payload.marker
                content.get("payload")
                    .and_then(|p| p.as_object())
                    .and_then(|p| p.get("marker"))
                    .and_then(|m| m.as_object())
            })
            .or_else(|| {
                // Check layout.marker
                layout.get("marker").and_then(|m| m.as_object())
            })
            .or_else(|| {
                // Check layout.metadata.marker
                layout.get("metadata")
                    .and_then(|m| m.as_object())
                    .and_then(|m| m.get("marker"))
                    .and_then(|m| m.as_object())
            });
        
        // Also check content.raw.marker as fallback
        let marker_from_raw = if marker.is_none() {
            if let Some(content_obj) = content.as_object() {
                if let Some(raw) = content_obj.get("raw").and_then(|r| r.as_object()) {
                    if raw.contains_key("marker") {
                        eprintln!("   Found marker in content.raw, extracting...");
                        raw.get("marker").and_then(|m| m.as_object())
                    } else {
                        None
                    }
                } else {
                    None
                }
            } else {
                None
            }
        } else {
            None
        };
        
        // Use marker or marker_from_raw
        let marker_to_use = marker.or(marker_from_raw);
        
        // Debug: log marker detection (only for first few paragraphs to avoid spam)
        static mut MARKER_CHECK_COUNT: u32 = 0;
        unsafe {
            if MARKER_CHECK_COUNT < 5 {
                eprintln!("   Checking for marker in paragraph {}...", MARKER_CHECK_COUNT);
                if let Some(content_obj) = content.as_object() {
                    let content_keys: Vec<&str> = content_obj.keys().map(|k| k.as_str()).collect();
                    eprintln!("   Content keys: {:?}", content_keys);
                    if content_obj.contains_key("marker") {
                        eprintln!("   Found 'marker' key in content: {:?}", content_obj.get("marker"));
                    }
                    // Check meta - this is where marker_override_text should be
                    if let Some(meta) = content_obj.get("meta").and_then(|m| m.as_object()) {
                        let meta_keys: Vec<&str> = meta.keys().map(|k| k.as_str()).collect();
                        eprintln!("   Meta keys: {:?}", meta_keys);
                        if meta.contains_key("marker") {
                            eprintln!("   Found 'marker' in meta: {:?}", meta.get("marker"));
                        }
                        if meta.contains_key("marker_override_text") {
                            eprintln!("   Found 'marker_override_text' in meta: {:?}", meta.get("marker_override_text"));
                        }
                    }
                    // Check payload
                    if let Some(payload) = content_obj.get("payload").and_then(|p| p.as_object()) {
                        if payload.contains_key("marker") {
                            eprintln!("   Found 'marker' in payload: {:?}", payload.get("marker"));
                        }
                    }
                    // Check raw
                    if let Some(raw) = content_obj.get("raw").and_then(|r| r.as_object()) {
                        if raw.contains_key("marker") {
                            eprintln!("   Found 'marker' in raw: {:?}", raw.get("marker"));
                        }
                    }
                }
                if marker_to_use.is_some() {
                    eprintln!("   ✅ Found marker, will render");
                } else {
                    eprintln!("   ❌ No marker found");
                }
                MARKER_CHECK_COUNT += 1;
            }
        }
        
        // Render marker if present (before first line)
        // If marker_override_text is in metadata, use it to override marker.text
        if let Some(marker_obj) = marker_to_use {
            // Check if marker should be hidden
            let hidden_marker = marker_obj.get("hidden_marker")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            
            if !hidden_marker {
                // Get marker position - try multiple sources
                let marker_x = marker_obj.get("x")
                    .and_then(|v| v.as_f64())
                    .or_else(|| {
                        // Calculate from number_position or indent_left - indent_hanging
                        let number_position = marker_obj.get("number_position")
                            .and_then(|v| v.as_f64());
                        if let Some(pos) = number_position {
                            Some(rect.x + pos)
                        } else {
                            let indent_left = marker_obj.get("indent_left")
                                .and_then(|v| v.as_f64())
                                .unwrap_or(0.0);
                            let indent_hanging = marker_obj.get("indent_hanging")
                                .and_then(|v| v.as_f64())
                                .unwrap_or(0.0);
                            Some(rect.x + indent_left - indent_hanging)
                        }
                    })
                    .unwrap_or(text_left - 20.0); // Fallback: 20pt to the left
                
                // Get marker Y position - use baseline_offset from first line
                let first_line = lines.get(0);
                let marker_y = if let Some(first_line_obj) = first_line.and_then(|l| l.as_object()) {
                    let baseline_y = first_line_obj.get("baseline_y")
                        .and_then(|v| v.as_f64())
                        .unwrap_or(0.0);
                    let baseline_offset = marker_obj.get("baseline_offset")
                        .and_then(|v| v.as_f64())
                        .unwrap_or(0.0);
                    text_top - baseline_y + baseline_offset
                } else {
                    // Fallback: use text_top
                    text_top
                };
                
                debug!("Rendering marker at ({}, {}): marker={:?}, override_text={:?}", 
                    marker_x, marker_y, marker_obj, marker_override_text);
                
                // If we have override text from metadata, create a modified marker map with it
                // Since we can't modify the original map, we'll create a new one
                let marker_to_render = if let Some(override_text) = marker_override_text {
                    // Create a new marker map with override text
                    let mut marker_with_override = serde_json::Map::new();
                    // Copy all fields from original marker
                    for (k, v) in marker_obj.iter() {
                        marker_with_override.insert(k.clone(), v.clone());
                    }
                    // Add override text (this will be checked first by render_marker)
                    marker_with_override.insert("marker_override_text".to_string(), 
                        serde_json::Value::String(override_text.to_string()));
                    marker_with_override
                } else {
                    // Use original marker as-is
                    marker_obj.clone()
                };
                
                // Render marker using markers module
                if let Err(e) = render_marker(
                    canvas,
                    pdf,
                    fonts_registry,
                    &marker_to_render,
                    marker_x,
                    marker_y,
                    default_font_name,
                    default_font_size,
                    default_color,
                ) {
                    warn!("Failed to render marker: {}", e);
                }
            }
        }
        
        // Render each line
        for line in lines.iter().take(max_lines) {
            // Get baseline from line data or calculate from font metrics
            let baseline_y_from_line = json_helpers::get_f64_or(line, "baseline_y", 0.0);
            let offset_x = json_helpers::get_f64_or(line, "offset_x", 0.0);
            let available_width = json_helpers::get_f64_or(line, "available_width", rect.width);
            
            // Use provided baseline if available, otherwise calculate from metrics
            let baseline_y = if baseline_y_from_line > 0.0 {
                baseline_y_from_line
            } else {
                font_metrics.baseline_offset(scale)
            };
            
            // Calculate line Y position
            // In PDF, Y increases from bottom to top
            // text_top is at the top of the text area
            // baseline_y is relative to text_top (positive = below text_top)
            let line_y = text_top - baseline_y;
            
            // Skip if line is outside rect (below bottom)
            if line_y < rect.y {
                continue;
            }
            
            // Skip if line is outside rect (above top)
            if line_y > rect.top() {
                continue;
            }
            
            // Get line items
            let empty_items: Vec<serde_json::Value> = vec![];
            let items = json_helpers::get_array_opt(line, "items")
                .unwrap_or(&empty_items);
            
            // Skip lines with no items
            if items.is_empty() {
                continue;
            }
            
            // Limit number of items per line (safety limit: 1000 items per line)
            const MAX_ITEMS_PER_LINE: usize = 1000;
            if items.len() > MAX_ITEMS_PER_LINE {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Line has too many items: {} (max {})", items.len(), MAX_ITEMS_PER_LINE)
                ));
            }
            let max_items = items.len().min(MAX_ITEMS_PER_LINE);
            
            // Calculate line content width for alignment
            let mut line_content_width: f64 = 0.0;
            for item in items.iter().take(max_items) {
                let item_x = json_helpers::get_f64_or(item, "x", 0.0);
                let item_width = json_helpers::get_f64_or(item, "width", 0.0);
                line_content_width = line_content_width.max(item_x + item_width);
            }
            
            // Calculate line start X based on alignment
            let extra_space = (available_width - line_content_width).max(0.0);
            // Safely convert alignment to lowercase (handle Unicode)
            let alignment_lower = paragraph_alignment.to_lowercase();
            let line_start_x = text_left + offset_x + match alignment_lower.as_str() {
                "center" | "centre" => extra_space / 2.0,
                "right" => extra_space,
                "justify" | "both" => 0.0, // Justify will be handled per-item
                _ => 0.0, // left
            };
            
            // Get runs_payload for style mapping (styles are at paragraph level, not item level)
            let runs_payload = content.get("runs_payload")
                .or_else(|| content.get("runs"))
                .and_then(|v| v.as_array());
            
            // Track which run we're currently using for style
            // Items are split (e.g., "ZAPYTANIE", " ", "OFERTOWE" = 3 items, but 1 run)
            // We'll use a simple approach: try to match item text to run text, or use first available run
            let mut current_run_idx = 0;
            
            // Render inline items
            for item in items.iter().take(max_items) {
                let item_kind = json_helpers::get_str_or(item, "kind", "text_run");
                let item_x = json_helpers::get_f64_or(item, "x", 0.0);
                
                // Get item data - can be object or string
                let item_data = item.get("data");
                let item_data_obj = item_data
                    .and_then(|d| d.as_object());
                
                // Also try to get text directly from item (fallback)
                let item_text_direct = item.get("text")
                    .and_then(|v| v.as_str());
                
                match item_kind {
                    "image" => {
                        // Render image from item
                        if let Some(item_data_obj) = item_data_obj {
                            // Stream key (preferred) or image path from various locations
                            let stream_key = item_data_obj.get("stream_key")
                                .and_then(|v| v.as_str());
                            let img_path = item_data_obj.get("path")
                                .or_else(|| item_data_obj.get("image_path"))
                                .or_else(|| item_data_obj.get("src"))
                                .and_then(|v| v.as_str());
                            
                            eprintln!(
                                "Paragraph inline image candidate stream_key={:?} path={:?}",
                                stream_key,
                                img_path
                            );
                            
                            if stream_key.is_some() || img_path.is_some() {
                                // Get image dimensions from item (in EMU) for proper SVG conversion
                                let item_width_emu = json_helpers::get_f64_opt(item, "width");
                                let item_height_emu = json_helpers::get_f64_opt(item, "height");

                                let image_result = if let Some(key) = stream_key {
                                    eprintln!("Requesting inline image from stream key {}", key);
                                    images_registry.get_or_create_from_stream(pdf, key, item_width_emu, item_height_emu)
                                } else {
                                    let path = img_path.unwrap_or_default();
                                    eprintln!("Requesting inline image from path {}", path);
                                    images_registry.get_or_create_from_path_with_dims(pdf, path, item_width_emu, item_height_emu)
                                };

                                let source_label = stream_key.unwrap_or_else(|| img_path.unwrap_or("<inline-image>"));
                                match image_result {
                                    Ok((_image_id, image_name)) => {
                                        eprintln!(
                                            "Inline image resolved source={} name={} ref={:?}",
                                            source_label,
                                            String::from_utf8_lossy(image_name.0),
                                            _image_id
                                        );
                                        images_used_on_current_page.insert(image_name, _image_id);
                                        
                                        // Get image dimensions from item
                                        let item_width = item_width_emu.unwrap_or(0.0);
                                        let item_height = item_height_emu.unwrap_or(0.0);
                                        
                                        // Convert EMU to points if needed
                                        let emu_to_pt = 72.0 / 914400.0;
                                        let final_width = if item_width > 1000.0 {
                                            item_width * emu_to_pt
                                        } else if item_width > 0.0 {
                                            item_width
                                        } else {
                                            // Default size if not specified
                                            rect.width * 0.1
                                        };
                                        let final_height = if item_height > 1000.0 {
                                            item_height * emu_to_pt
                                        } else if item_height > 0.0 {
                                            item_height
                                        } else {
                                            // Default size if not specified
                                            final_width * 0.75 // Maintain aspect ratio
                                        };
                                        
                                        // Calculate image position
                                        let image_x = line_start_x + item_x;
                                        let image_y = line_y - final_height; // PDF: Y increases upward, images drawn from bottom-left
                                        
                                        canvas.draw_image(image_name, image_x, image_y, final_width, final_height);
                                    }
                                    Err(e) => {
                                        warn!("Failed to load image from item: {} - {}", source_label, e);
                                    }
                                }
                            }
                        }
                    }
                    "text_run" | "field" => {
                        // Get text from various locations
                        let text = if item_kind == "field" {
                            // For fields, resolve field text using field resolution
                            // Field data can be in item.data.field (nested) or item.data directly
                            let field_data = if let Some(item_data_obj) = item_data_obj {
                                // Try item.data.field first (nested structure from assembler)
                                item_data_obj.get("field")
                                    .and_then(|f| f.as_object())
                                    .or_else(|| Some(item_data_obj)) // Fallback to item.data directly
                            } else {
                                None
                            };
                            
                            let field_text = resolve_field_text(
                                field_data,
                                current_page_number,
                                total_pages
                            );
                            if !field_text.is_empty() {
                                debug!("Resolved field: page={}, total={}, text='{}'", 
                                    current_page_number, total_pages, field_text);
                            } else {
                                debug!("Field resolved to empty text: item_data={:?}, field_data={:?}", 
                                    item_data_obj, field_data);
                            }
                            field_text
                        } else {
                            // For text runs, try data.text first, then item.text
                            item_data_obj
                                .and_then(|d| d.get("text"))
                                .or_else(|| item_data_obj.and_then(|d| d.get("display")))
                                .and_then(|v| v.as_str())
                                .or_else(|| item_text_direct)
                                .unwrap_or("")
                                .to_string()
                        };
                        
                        if text.is_empty() {
                            continue;
                        }
                        
                        // Find the corresponding run for this item's text
                        // Simplified approach: try to find run that contains this text, or use current run
                        let mut matched_run_idx = None;
                        if let Some(runs) = runs_payload {
                            // Try to find run that contains this item's text
                            // Start from current_run_idx
                            for (run_idx, run) in runs.iter().enumerate().skip(current_run_idx) {
                                if let Some(run_text) = run.get("text").and_then(|v| v.as_str()) {
                                    // Check if run_text contains item text (simple substring match)
                                    if run_text.contains(&text) {
                                        matched_run_idx = Some(run_idx);
                                        // Move to next run after this one
                                        current_run_idx = run_idx + 1;
                                        break;
                                    }
                                }
                            }
                            
                            // Fallback: if no match found, use current_run_idx (or 0 if out of bounds)
                            if matched_run_idx.is_none() {
                                if current_run_idx < runs.len() {
                                    matched_run_idx = Some(current_run_idx);
                                } else if !runs.is_empty() {
                                    // Use last run if we've gone past all runs
                                    matched_run_idx = Some(runs.len() - 1);
                                }
                            }
                        }
                        
                        // Get item style - try multiple sources:
                        // 1. item.data.style (direct style in item)
                        // 2. item.style (style at item level)
                        // 3. runs_payload[matched_run_idx].style (style from runs_payload - most common)
                        let item_style_value = item_data_obj
                            .and_then(|d| d.get("style"))
                            .or_else(|| item.get("style"))
                            .or_else(|| {
                                // Try to get style from runs_payload using matched run index
                                if let Some(run_idx) = matched_run_idx {
                                    runs_payload
                                        .and_then(|runs| runs.get(run_idx))
                                        .and_then(|run| run.get("style"))
                                } else {
                                    None
                                }
                            });
                        
                        // Parse text style from item style or use defaults
                        let text_style = if let Some(style_val) = item_style_value {
                            let mut style = TextStyle::from_json(style_val);
                            // Override with defaults if not set
                            if style.font_name.is_none() {
                                style.font_name = Some(default_font_name.to_string());
                            }
                            if style.font_size.is_none() {
                                style.font_size = Some(default_font_size);
                            }
                            if style.color.is_none() {
                                style.color = Some(default_color.to_string());
                            }
                            style
                        } else {
                            // Use defaults
                            TextStyle {
                                font_name: Some(default_font_name.to_string()),
                                font_size: Some(default_font_size),
                                color: Some(default_color.to_string()),
                                bold: None,
                                italic: None,
                                underline: None,
                            }
                        };
                        
                        // Also check for color in item_data directly
                        let color = item_data_obj
                            .and_then(|d| d.get("color"))
                            .and_then(|v| v.as_str())
                            .unwrap_or(text_style.color());
                        
                        // Handle bold/italic font variants
                        let mut effective_font_name = text_style.font_name().to_string();
                        if text_style.bold == Some(true) && text_style.italic == Some(true) {
                            // Bold + Italic
                            effective_font_name = format!("{}-BoldOblique", effective_font_name);
                        } else if text_style.bold == Some(true) {
                            // Bold only
                            effective_font_name = format!("{}-Bold", effective_font_name);
                        } else if text_style.italic == Some(true) {
                            // Italic only
                            effective_font_name = format!("{}-Oblique", effective_font_name);
                        }
                        
                        let font_size = text_style.font_size();
                        
                        // Render text
                        canvas.save_state();
                        canvas.set_fill_color(parse_color(&serde_json::json!(color)));
                        // Automatically use TrueType font for Polish characters
                        let font_ref = fonts_registry.resolve_for_text(pdf, &effective_font_name, &text)?;
                        canvas.set_font(font_ref, font_size);
                        
                        // TODO: Handle underline if text_style.underline == Some(true)
                        
                        // Check if we need justification
                        if paragraph_alignment == "justify" || paragraph_alignment == "both" {
                            // Use justification for word spacing adjustment
                            let words: Vec<&str> = text.split_whitespace().collect();
                            if words.len() > 1 {
                                let justifier = Justifier::new(available_width, line_content_width);
                                let segments = justifier.generate_tj_array(&words);
                                canvas.draw_string_justified(line_start_x + item_x, line_y, &segments);
                            } else {
                                // Single word, no justification needed
                                canvas.draw_string(line_start_x + item_x, line_y, &text);
                            }
                        } else {
                            // Regular text rendering
                            canvas.draw_string(line_start_x + item_x, line_y, &text);
                        }
                        canvas.restore_state();
                    },
                    "inline_image" => {
                        // Render inline image
                        let item_width = json_helpers::get_f64_or(item, "width", 0.0);
                        // item_height will be calculated after getting image_data
                        
                        // Get image data from item.data.image (as in Python compiler)
                        let image_data = item_data_obj
                            .and_then(|d| d.get("image"))
                            .and_then(|v| v.as_object());
                        
                        // Try to get path from image data
                        let image_path = image_data
                            .and_then(|img| img.get("path").and_then(|v| v.as_str()))
                            .or_else(|| image_data.and_then(|img| img.get("image_path").and_then(|v| v.as_str())))
                            .or_else(|| item_data_obj.and_then(|d| d.get("path")).and_then(|v| v.as_str()))
                            .or_else(|| item_data_obj.and_then(|d| d.get("image_path")).and_then(|v| v.as_str()));
                        
                        // Get ascent and descent from assembler (already in points)
                        // Assembler creates: InlineBox(kind="inline_image", width=width_pt, ascent=..., descent=...)
                        // Python compiler: height = (inline.ascent + inline.descent) or inline.data.get("height") or 0.0
                        let item_ascent = json_helpers::get_f64_or(item, "ascent", 0.0);
                        let item_descent = json_helpers::get_f64_or(item, "descent", 0.0);
                        
                        // Calculate height: ascent + descent (as in Python compiler)
                        let item_height = if item_ascent > 0.0 || item_descent > 0.0 {
                            item_ascent + item_descent
                        } else {
                            // Fallback to height from data if ascent/descent not available
                            item.get("height")
                                .and_then(|v| v.as_f64())
                                .or_else(|| {
                                    item_data_obj.and_then(|d| d.get("height")).and_then(|v| v.as_f64())
                                })
                                .unwrap_or_else(|| {
                                    // Last fallback: use width if no height specified (square image)
                                    item_width
                                })
                        };
                        
                        if let Some(path) = image_path {
                            // Get image dimensions (in EMU) for proper SVG conversion
                            let item_width_emu = json_helpers::get_f64_opt(item, "width");
                            let item_height_emu = json_helpers::get_f64_opt(item, "height");
                            
                            // Use images_registry to get or create image
                            match images_registry.get_or_create_from_path_with_dims(pdf, path, item_width_emu, item_height_emu) {
                                Ok((image_id, image_name)) => {
                                    // Register image for page resources tracking
                                    images_used_on_current_page.insert(image_name, image_id);
                                            
                                            // Calculate image position
                                            // item_x is relative to line start, so add line_start_x
                                            let image_x = line_start_x + item_x;
                                            // In PDF coordinates, y=0 is at bottom, and y increases upward
                                            // baseline_y is the baseline of the line
                                            // For inline images, position at baseline minus descent (as in Python compiler)
                                            // Python: bottom = baseline_y - inline.descent
                                            // Use descent from item (already calculated by assembler in points)
                                            // line_y is the baseline position, so bottom of image = line_y - item_descent
                                            let image_y = line_y - item_descent;
                                            
                                            // Draw image
                                            canvas.draw_image(image_name, image_x, image_y, item_width, item_height);
                                },
                                Err(e) => {
                                    error!("Failed to load inline image: {} - {}", path, e);
                                }
                            }
                        } else {
                            warn!("Inline image item has no path (item_data: {:?})", item_data_obj);
                        }
                    },
                    "inline_textbox" => {
                        // TODO: Implement inline textboxes
                        // For now, skip
                    },
                    _ => {
                        // Unknown inline type, skip
                    }
                }
            }
        }
        
        // Render overlays (floating images/textboxes) - check multiple locations
        let overlays = content.get("payload")
            .and_then(|p| p.as_object())
            .and_then(|p| p.get("overlays"))
            .and_then(|v| v.as_array())
            .or_else(|| {
                // Also check if content itself has overlays
                if let Some(content_obj) = content.as_object() {
                    content_obj.get("overlays").and_then(|v| v.as_array())
                } else {
                    None
                }
            });
        
        if let Some(overlays_array) = overlays {
            if !overlays_array.is_empty() {
                eprintln!("render_paragraph_from_layout: rendering {} overlays", overlays_array.len());
                crate::overlays::render_overlays(
                    canvas,
                    pdf,
                    fonts_registry,
                    images_registry,
                    overlays_array,
                    images_used_on_current_page,
                )?;
            }
        }
        
        Ok(())
    }
    
    /// Render paragraphs in a table cell
    pub(crate) fn render_cell_paragraphs(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts_registry: &mut crate::font_registry::FontRegistry,
        images_registry: &mut crate::image_registry::ImageRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        cell_rect: &Rect,
        paragraphs: &[serde_json::Value],
        cell_style: Option<&serde_json::Value>,
        current_page_number: u32,
        total_pages: u32,
    ) -> PyResult<()> {
        // Get cell margins (default to 0)
        let cell_margins = cell_style
            .and_then(|s| s.get("margins"))
            .and_then(|m| m.as_object())
            .map(|m| {
                (
                    m.get("top").and_then(|v| v.as_f64()).unwrap_or(0.0),
                    m.get("bottom").and_then(|v| v.as_f64()).unwrap_or(0.0),
                    m.get("left").and_then(|v| v.as_f64()).unwrap_or(0.0),
                    m.get("right").and_then(|v| v.as_f64()).unwrap_or(0.0),
                )
            })
            .unwrap_or((0.0, 0.0, 0.0, 0.0));
        
        // Calculate inner rect (cell rect minus margins)
        let inner_rect = Rect::new(
            cell_rect.x + cell_margins.2, // left margin
            cell_rect.y + cell_margins.1, // bottom margin
            cell_rect.width - cell_margins.2 - cell_margins.3, // width minus left and right margins
            cell_rect.height - cell_margins.0 - cell_margins.1, // height minus top and bottom margins
        );
        
        // Get vertical alignment
        let _vertical_align = cell_style
            .and_then(|s| s.get("vertical_align"))
            .or_else(|| cell_style.and_then(|s| s.get("v_align")))
            .and_then(|v| v.as_str())
            .unwrap_or("top");
        
            // Render each paragraph
            let _current_y = inner_rect.top();
        
        for paragraph in paragraphs {
            // Handle case where paragraph is a string (serialized Python object)
            if let Some(para_str) = paragraph.as_str() {
                // Skip serialized Python objects (they don't contain renderable content)
                if para_str.starts_with("<") && para_str.contains("object") {
                    eprintln!("      Skipping serialized Python object: {}", para_str);
                    continue;
                }
                // If it's a plain string, try to render it
                let default_style = serde_json::json!({});
                let para_style = cell_style.unwrap_or(&default_style);
                let para_rect = Rect::new(
                    inner_rect.x,
                    inner_rect.y,
                    inner_rect.width,
                    inner_rect.height,
                );
                // draw_text is deprecated - skip for now (assembler should provide layout_payload)
                warn!("Simple text in cell (draw_text deprecated) - skipping");
                continue;
            }
            
            // Get paragraph content and style (paragraph is a JSON object)
            let para_content = paragraph.get("content")
                .or_else(|| paragraph.get("payload"))
                .unwrap_or(paragraph);
            
            let para_style = paragraph.get("style")
                .or_else(|| cell_style);
            
            // Calculate paragraph rect (full width, height will be calculated from content)
            let para_rect = Rect::new(
                inner_rect.x,
                inner_rect.y,
                inner_rect.width,
                inner_rect.height, // Will be adjusted based on content
            );
            
            eprintln!("      render_cell_paragraphs: cell_rect={:?}, inner_rect={:?}, para_rect={:?}", cell_rect, inner_rect, para_rect);
            
            // Check if paragraph has images array (separate from runs)
            if let Some(images) = para_content.get("images").and_then(|v| v.as_array()) {
                eprintln!("      Paragraph has {} images in images array", images.len());
                for (img_idx, image) in images.iter().enumerate() {
                    if let Some(img_obj) = image.as_object() {
                        let image_path = img_obj.get("path")
                            .or_else(|| img_obj.get("image_path"))
                            .and_then(|v| v.as_str());
                        let stream_key = img_obj.get("stream_key")
                            .and_then(|v| v.as_str());
                        let width_emu = img_obj.get("width")
                            .and_then(|v| v.as_f64().or_else(|| v.as_i64().map(|i| i as f64)));
                        let height_emu = img_obj.get("height")
                            .and_then(|v| v.as_f64().or_else(|| v.as_i64().map(|i| i as f64)));
                        
                        if stream_key.is_some() || image_path.is_some() {
                            eprintln!("      Rendering image {} from paragraph.images: stream_key={:?} path={:?}", img_idx, stream_key, image_path);
                            let image_result = if let Some(key) = stream_key {
                                images_registry.get_or_create_from_stream(pdf, key, width_emu, height_emu)
                            } else {
                                let path = image_path.unwrap_or_default();
                                images_registry.get_or_create_from_path_with_dims(pdf, path, width_emu, height_emu)
                            };
                            
                            match image_result {
                                Ok((_image_id, image_name)) => {
                                    images_used_on_current_page.insert(image_name, _image_id);
                                    
                                    // Convert EMU to points if needed
                                    let emu_to_pt = 72.0 / 914400.0;
                                    let final_width = if let Some(w) = width_emu {
                                        if w > 1000.0 {
                                            w * emu_to_pt
                                        } else {
                                            w
                                        }
                                    } else {
                                        para_rect.width * 0.3
                                    };
                                    let final_height = if let Some(h) = height_emu {
                                        if h > 1000.0 {
                                            h * emu_to_pt
                                        } else {
                                            h
                                        }
                                    } else {
                                        para_rect.height * 0.8
                                    };
                                    
                                    // Position image in cell (top-left for now)
                                    let image_x = para_rect.x;
                                    let image_y = para_rect.top() - final_height;
                                    eprintln!("      Drawing image from paragraph.images at ({:.2}, {:.2}) size ({:.2}, {:.2})", image_x, image_y, final_width, final_height);
                                    canvas.draw_image(image_name, image_x, image_y, final_width, final_height);
                                }
                                Err(e) => {
                                    warn!("Failed to load image from paragraph.images[{}]: {}", img_idx, e);
                                }
                            }
                        }
                    }
                }
            }
            
            // Check if paragraph has ParagraphLayout payload
            let has_layout = para_content.get("layout_payload").is_some()
                || para_content.get("_layout_payload").is_some()
                || para_content.get("lines").is_some();
            
            if has_layout {
                // Render using ParagraphLayout
                eprintln!("      Rendering paragraph with layout_payload in cell, para_rect={:?}", para_rect);
                let default_style = serde_json::json!({});
                let para_style = para_style.unwrap_or(&default_style);
                Self::render_paragraph_from_layout(canvas, pdf, fonts_registry, images_registry, images_used_on_current_page, &para_rect, para_content, para_style, current_page_number, total_pages)?;
            } else if let Some(runs) = para_content.get("runs").and_then(|v| v.as_array()) {
                // Paragraph has runs - check for inline images
                eprintln!("      Rendering paragraph with {} runs in cell", runs.len());
                let mut has_inline_images = false;
                for (run_idx, run) in runs.iter().enumerate() {
                    if let Some(run_obj) = run.as_object() {
                        // Log run keys for debugging
                        let run_keys: Vec<_> = run_obj.keys().collect();
                        eprintln!("      Run {} keys: {:?}", run_idx, run_keys);
                        // Check if run has an image
                        if let Some(image) = run_obj.get("image") {
                            has_inline_images = true;
                            eprintln!("      Run {} has image", run_idx);
                            // Extract image data
                            let image_path = image.as_object()
                                .and_then(|img| img.get("path").or_else(|| img.get("image_path")))
                                .and_then(|v| v.as_str());
                            let stream_key = image.as_object()
                                .and_then(|img| img.get("stream_key"))
                                .and_then(|v| v.as_str());
                            let width_emu = image.as_object()
                                .and_then(|img| img.get("width"))
                                .and_then(|v| v.as_f64().or_else(|| v.as_i64().map(|i| i as f64)));
                            let height_emu = image.as_object()
                                .and_then(|img| img.get("height"))
                                .and_then(|v| v.as_f64().or_else(|| v.as_i64().map(|i| i as f64)));
                            
                            if stream_key.is_some() || image_path.is_some() {
                                eprintln!("      Rendering inline image from run {}: stream_key={:?} path={:?}", run_idx, stream_key, image_path);
                                let image_result = if let Some(key) = stream_key {
                                    images_registry.get_or_create_from_stream(pdf, key, width_emu, height_emu)
                                } else {
                                    let path = image_path.unwrap_or_default();
                                    images_registry.get_or_create_from_path_with_dims(pdf, path, width_emu, height_emu)
                                };
                                
                                match image_result {
                                    Ok((_image_id, image_name)) => {
                                        images_used_on_current_page.insert(image_name, _image_id);
                                        
                                        // Convert EMU to points if needed
                                        let emu_to_pt = 72.0 / 914400.0;
                                        let final_width = if let Some(w) = width_emu {
                                            if w > 1000.0 {
                                                w * emu_to_pt
                                            } else {
                                                w
                                            }
                                        } else {
                                            para_rect.width * 0.3
                                        };
                                        let final_height = if let Some(h) = height_emu {
                                            if h > 1000.0 {
                                                h * emu_to_pt
                                            } else {
                                                h
                                            }
                                        } else {
                                            para_rect.height * 0.8
                                        };
                                        
                                        // Position image in cell (top-left for now)
                                        let image_x = para_rect.x;
                                        let image_y = para_rect.top() - final_height;
                                        eprintln!("      Drawing inline image at ({:.2}, {:.2}) size ({:.2}, {:.2})", image_x, image_y, final_width, final_height);
                                        canvas.draw_image(image_name, image_x, image_y, final_width, final_height);
                                    }
                                    Err(e) => {
                                        warn!("Failed to load inline image from run {}: {}", run_idx, e);
                                    }
                                }
                            }
                        }
                    }
                }
                
                // Even if there are no inline images, we should still try to render text from runs
                // Check if paragraph has layout_payload (might have been added after runs check)
                let has_layout_after_runs = para_content.get("layout_payload").is_some()
                    || para_content.get("_layout_payload").is_some()
                    || para_content.get("lines").is_some();
                
                if has_layout_after_runs {
                    // Render using ParagraphLayout (layout_payload was found)
                    eprintln!("      Rendering paragraph with layout_payload in cell (after runs check)");
                    let default_style = serde_json::json!({});
                    let para_style = para_style.unwrap_or(&default_style);
                    Self::render_paragraph_from_layout(canvas, pdf, fonts_registry, images_registry, images_used_on_current_page, &para_rect, para_content, para_style, current_page_number, total_pages)?;
                } else {
                    // No layout_payload - unified layout should provide pre-calculated layout_payload with lines
                    warn!("Paragraph in cell has runs but no layout_payload - assembler should create layout_payload with lines");
                }
            } else if let Some(text) = para_content.get("text").and_then(|v| v.as_str()) {
                // Simple text paragraph
                eprintln!("      Rendering simple text paragraph in cell: '{}'", text);
                let default_style = serde_json::json!({});
                let para_style = para_style.unwrap_or(&default_style);
                // draw_text is deprecated - skip for now (assembler should provide layout_payload)
                warn!("Simple text in cell (draw_text deprecated) - skipping");
            } else {
                warn!("Paragraph in cell has no layout_payload, no runs, and no text - skipping");
            }
            
            // TODO: Calculate actual paragraph height and adjust current_y
            // For now, we'll render paragraphs sequentially from top
        }
        
        Ok(())
    }
    
    /// [DEPRECATED] Draw text with layout calculations
    ///
    /// ⚠️ WARNING: This function performs layout calculations (text wrapping, position calculation),
    /// which violates the architecture principle that the renderer should only render pre-calculated
    /// blocks from the assembler.
    ///
    /// This function is kept for backward compatibility but should NOT be used.
    /// The assembler should always provide a `ParagraphLayout` payload with pre-calculated lines.
    ///
    /// If you see this function being called, it means the assembler didn't prepare the layout
    /// correctly. This should be fixed in the assembler, not worked around in the renderer.
    /// Draw shadow
    fn draw_shadow(canvas: &mut PdfCanvas, rect: &Rect, style: &serde_json::Value) {
        let shadow = style.get("shadow");
        if shadow.is_none() {
            return;
        }
        
        // Check if shadow is disabled (false)
        if let Some(shadow_bool) = shadow.and_then(|s| s.as_bool()) {
            if !shadow_bool {
                return;
            }
        }
        
        // Get shadow properties
        let (color, dx, dy) = if let Some(shadow_obj) = shadow.and_then(|s| s.as_object()) {
            let shadow_color = shadow_obj.get("color")
                .and_then(|v| v.as_str())
                .unwrap_or("#888888");
            let offset_x = shadow_obj.get("offset_x")
                .or_else(|| shadow_obj.get("dx"))
                .and_then(|v| v.as_f64())
                .unwrap_or(2.0);
            let offset_y = shadow_obj.get("offset_y")
                .or_else(|| shadow_obj.get("dy"))
                .and_then(|v| v.as_f64())
                .unwrap_or(-2.0);
            (shadow_color, offset_x, offset_y)
        } else {
            ("#888888", 2.0, -2.0)
        };
        
        // Draw shadow rectangle (offset and behind)
        canvas.save_state();
        canvas.set_fill_color(parse_color(&serde_json::json!(color)));
        let shadow_rect = Rect::new(
            rect.x + dx,
            rect.y + dy,
            rect.width,
            rect.height,
        );
        canvas.rect(shadow_rect, true, false);
        canvas.restore_state();
    }
    
    /// Draw border
    pub(crate) fn draw_border(canvas: &mut PdfCanvas, rect: &Rect, border: &serde_json::Value) -> PyResult<()> {
        let width = json_helpers::get_f64_or(border, "width", 1.0);
        let default_border_color = serde_json::json!("#000000");
        let color = border.get("color").unwrap_or(&default_border_color);
        let style_name = json_helpers::get_str_opt(border, "style")
            .or_else(|| json_helpers::get_str_opt(border, "val"))
            .unwrap_or("solid");
        let radius = json_helpers::get_f64_or(border, "radius", 0.0);
        
        canvas.save_state();
        canvas.set_stroke_color(parse_color(color));
        canvas.set_line_width(width);
        
        // Apply border style
        match style_name.to_lowercase().as_str() {
            "dashed" | "dash" => canvas.set_dash(vec![6.0, 3.0], 0.0),
            "dotted" | "dot" => canvas.set_dash(vec![1.0, 2.0], 0.0),
            "double" => {
                // Double border: draw two lines
                let half_width = width / 2.0;
                canvas.set_line_width(half_width);
                if radius > 0.0 {
                    canvas.round_rect(*rect, radius, false, true);
                    let inner_rect = Rect::new(
                        rect.x + half_width,
                        rect.y + half_width,
                        rect.width - width,
                        rect.height - width,
                    );
                    canvas.round_rect(inner_rect, radius.max(0.0), false, true);
                } else {
                    canvas.rect(*rect, false, true);
                    let inner_rect = Rect::new(
                        rect.x + half_width,
                        rect.y + half_width,
                        rect.width - width,
                        rect.height - width,
                    );
                    canvas.rect(inner_rect, false, true);
                }
                canvas.restore_state();
                return Ok(());
            },
            _ => {
                // solid or unknown - no dash pattern
            }
        }
        
        // Draw border rectangle
        if radius > 0.0 {
            canvas.round_rect(*rect, radius, false, true);
        } else {
            canvas.rect(*rect, false, true);
        }
        
        canvas.restore_state();
        
        Ok(())
    }
    
    /// Draw borders (all sides)
    pub(crate) fn draw_borders(canvas: &mut PdfCanvas, rect: &Rect, borders: &serde_json::Value) -> PyResult<()> {
        let sides = ["top", "bottom", "left", "right"];
        
        for side in &sides {
            if let Some(border) = borders.get(side) {
                let width = json_helpers::get_f64_or(border, "width", 1.0);
                let default_color = serde_json::json!("#000000");
                let color = border.get("color").unwrap_or(&default_color);
                
                canvas.save_state();
                canvas.set_stroke_color(parse_color(color));
                canvas.set_line_width(width);
                
                match *side {
                    "top" => canvas.line(rect.left(), rect.top(), rect.right(), rect.top()),
                    "bottom" => canvas.line(rect.left(), rect.bottom(), rect.right(), rect.bottom()),
                    "left" => canvas.line(rect.left(), rect.bottom(), rect.left(), rect.top()),
                    "right" => canvas.line(rect.right(), rect.bottom(), rect.right(), rect.top()),
                    _ => {}
                }
                canvas.restore_state();
            }
        }
        
        Ok(())
    }
    
    /// Inject font objects into PDF bytes after finish()
    /// 
    /// This function modifies the PDF bytes to insert font objects (FontDescriptor, CIDFont, Type0)
    /// before the xref table. The objects are inserted as properly formatted PDF indirect objects.
    fn inject_font_objects(
        mut pdf_bytes: Vec<u8>,
        font_objects: &[(Ref, String)],
    ) -> PyResult<Vec<u8>> {
        if font_objects.is_empty() {
            return Ok(pdf_bytes);
        }
        
        // Find the xref table position
        // PDF structure: ... objects ... xref ... trailer ... startxref ... %%EOF
        // We need to insert font objects before the xref table
        
        // First, find startxref to get the current xref offset
        let startxref_pos = pdf_bytes.windows(9)
            .rposition(|w| w == b"startxref")
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Could not find startxref in PDF before injection"
            ))?;
        
        eprintln!("   Found startxref at position {}", startxref_pos);
        
        // Get the current xref offset
        let mut startxref_value_start = startxref_pos + 9;
        // Skip whitespace
        while startxref_value_start < pdf_bytes.len() && 
              (pdf_bytes[startxref_value_start] == b' ' || 
               pdf_bytes[startxref_value_start] == b'\t' || 
               pdf_bytes[startxref_value_start] == b'\r' || 
               pdf_bytes[startxref_value_start] == b'\n') {
            startxref_value_start += 1;
        }
        
        let startxref_value_end = pdf_bytes[startxref_value_start..]
            .iter()
            .position(|&b| b == b'\n' || b == b'\r')
            .map(|pos| pos + startxref_value_start)
            .unwrap_or(pdf_bytes.len());
        
        let current_xref_offset = std::str::from_utf8(&pdf_bytes[startxref_value_start..startxref_value_end])
            .ok()
            .and_then(|s| s.trim().parse::<usize>().ok())
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Could not parse current xref offset"
            ))?;
        
        eprintln!("   Current xref offset: {}", current_xref_offset);
        
        // Search for "xref" keyword at the current offset
        let xref_pos = current_xref_offset;
        
        // Verify that xref is at this position
        if !pdf_bytes[xref_pos..].starts_with(b"xref") {
            // Try to find xref near the expected position
            let search_start = current_xref_offset.saturating_sub(10);
            let search_end = (current_xref_offset + 20).min(pdf_bytes.len());
            let xref_found = pdf_bytes[search_start..search_end]
                .windows(4)
                .position(|w| w == b"xref")
                .map(|pos| search_start + pos);
            
            let xref_pos = xref_found.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Could not find xref table at offset {} (searched from {} to {})", 
                    current_xref_offset, search_start, search_end)
            ))?;
            
            eprintln!("   Found xref table at position {} (expected {})", xref_pos, current_xref_offset);
        } else {
            eprintln!("   Found xref table at expected position {}", xref_pos);
        }
        
        // Build font objects content and track their positions
        let mut font_objects_content = Vec::new();
        let mut font_object_positions = Vec::new(); // (ref_id, position_in_pdf)
        
        for (ref_id, content) in font_objects {
            let object_start_pos = xref_pos + font_objects_content.len();
            font_object_positions.push((*ref_id, object_start_pos));
            font_objects_content.extend_from_slice(content.as_bytes());
            font_objects_content.push(b'\n');
        }
        
        let font_objects_content_len = font_objects_content.len();
        eprintln!("   Injecting {} bytes of font objects before xref", font_objects_content_len);
        
        // Insert font objects before xref
        pdf_bytes.splice(xref_pos..xref_pos, font_objects_content);
        
        // Now update startxref with new offset
        let new_xref_offset = xref_pos + font_objects_content_len;
        
        // Update xref table to include font objects
        // Find the trailer to get /Size
        let trailer_pos = pdf_bytes.windows(7)
            .rposition(|w| w == b"trailer")
            .ok_or_else(|| 
                PyErr::new::<pyo3::exceptions::PyValueError, _>("Could not find trailer")
            )?;
        
        // Parse /Size from trailer (simple string search)
        let trailer_section_start = trailer_pos + 7; // Skip "trailer"
        let trailer_section_end = pdf_bytes[trailer_section_start..]
            .iter()
            .position(|&b| b == b'>')
            .map(|pos| trailer_section_start + pos + 1)
            .unwrap_or(pdf_bytes.len());
        
        // Find /Size in trailer
        let size_pattern = b"/Size ";
        let size_pos_opt = pdf_bytes[trailer_section_start..trailer_section_end]
            .windows(size_pattern.len())
            .position(|w| w == size_pattern)
            .map(|pos| trailer_section_start + pos);
        
        let current_size = if let Some(size_pos) = size_pos_opt {
            // Parse the number after /Size
            let num_start = size_pos + size_pattern.len();
            let num_end = pdf_bytes[num_start..trailer_section_end]
                .iter()
                .position(|&b| b == b' ' || b == b'\n' || b == b'\r' || b == b'>')
                .map(|pos| num_start + pos)
                .unwrap_or(trailer_section_end);
            
            std::str::from_utf8(&pdf_bytes[num_start..num_end])
                .ok()
                .and_then(|s| s.trim().parse::<i32>().ok())
                .unwrap_or(12)
        } else {
            12
        };
        
        let new_size = current_size + font_objects.len() as i32;
        
        // Update /Size in trailer
        if let Some(size_pos) = size_pos_opt {
            let num_start = size_pos + size_pattern.len();
            let num_end = pdf_bytes[num_start..trailer_section_end]
                .iter()
                .position(|&b| b == b' ' || b == b'\n' || b == b'\r' || b == b'>')
                .map(|pos| num_start + pos)
                .unwrap_or(trailer_section_end);
            
            let new_size_str = format!("{}", new_size);
            pdf_bytes.splice(num_start..num_end, new_size_str.bytes());
        }
        
        // Build xref entries for font objects
        // Format: "offset generation n" (n = in-use, f = free)
        let mut xref_entries = Vec::new();
        for (ref_id, object_pos) in &font_object_positions {
            // Format: "0000000000 00000 n" (10 digits offset, 5 digits generation, n/f)
            let entry = format!("{:010} {:05} n \n", object_pos, 0);
            xref_entries.push((ref_id.get(), entry));
        }
        
        // Sort by ref_id
        xref_entries.sort_by_key(|(ref_id, _)| *ref_id);
        
        // Insert xref entries before "xref" keyword
        // First, find where to insert (after "xref\n")
        let xref_keyword_end = new_xref_offset + 4; // After "xref"
        let mut xref_insert_pos = xref_keyword_end;
        
        // Skip whitespace after "xref"
        while xref_insert_pos < pdf_bytes.len() && 
              (pdf_bytes[xref_insert_pos] == b' ' || 
               pdf_bytes[xref_insert_pos] == b'\t' || 
               pdf_bytes[xref_insert_pos] == b'\r' || 
               pdf_bytes[xref_insert_pos] == b'\n') {
            xref_insert_pos += 1;
        }
        
        // Build xref entries string
        let mut xref_entries_str = String::new();
        for (_ref_id, entry) in &xref_entries {
            xref_entries_str.push_str(entry);
        }
        
        // Insert xref entries
        if !xref_entries_str.is_empty() {
            pdf_bytes.splice(xref_insert_pos..xref_insert_pos, xref_entries_str.bytes());
            eprintln!("   Added {} xref entries for font objects", xref_entries.len());
        }
        
        // Find startxref again (it may have moved after insertion)
        let startxref_pos_after = pdf_bytes.windows(9)
            .rposition(|w| w == b"startxref")
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Could not find startxref after injection"
            ))?;
        
        // Find the number after "startxref" (skip whitespace)
        let mut startxref_value_start = startxref_pos_after + 9;
        // Skip whitespace (spaces, tabs, newlines)
        while startxref_value_start < pdf_bytes.len() && 
              (pdf_bytes[startxref_value_start] == b' ' || 
               pdf_bytes[startxref_value_start] == b'\t' || 
               pdf_bytes[startxref_value_start] == b'\r' || 
               pdf_bytes[startxref_value_start] == b'\n') {
            startxref_value_start += 1;
        }
        
        let startxref_value_end = pdf_bytes[startxref_value_start..]
            .iter()
            .position(|&b| b == b'\n' || b == b'\r')
            .map(|pos| pos + startxref_value_start)
            .unwrap_or(pdf_bytes.len());
        
        let new_xref_offset_str = format!("{}", new_xref_offset);
        
        // Replace the xref offset value
        let mut new_bytes = Vec::new();
        new_bytes.extend_from_slice(&pdf_bytes[..startxref_value_start]);
        new_bytes.extend_from_slice(new_xref_offset_str.as_bytes());
        new_bytes.extend_from_slice(&pdf_bytes[startxref_value_end..]);
        pdf_bytes = new_bytes;
        
        eprintln!("   Updated xref offset from {} to {}", current_xref_offset, new_xref_offset);
        
        Ok(pdf_bytes)
    }
    
    /// Convert Python object (dict) to LayoutBlock
    /// DEPRECATED: Not used in new direct call approach
    #[allow(dead_code)]
    fn py_object_to_layout_block(py: Python, obj: &PyObject) -> PyResult<LayoutBlock> {
        let dict = obj.downcast::<PyDict>(py)
            .map_err(|_| PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "block must be a dict"
            ))?;
        
        // Extract frame
        let frame = match dict.get_item("frame") {
            Ok(Some(frame_obj)) => {
                if let Ok(frame_dict) = frame_obj.downcast::<PyDict>() {
                    Self::py_dict_to_rect(py, frame_dict)?
                } else {
                    Rect::new(0.0, 0.0, 0.0, 0.0)
                }
            }
            _ => Rect::new(0.0, 0.0, 0.0, 0.0)
        };
        
        // Extract block_type
        let block_type = match dict.get_item("block_type") {
            Ok(Some(obj)) => obj.extract::<String>().ok(),
            _ => None
        }.unwrap_or("paragraph".to_string());
        
        // Extract page_number
        let page_number = match dict.get_item("page_number") {
            Ok(Some(obj)) => obj.extract::<u32>().ok(),
            _ => None
        };
        
        // Extract content - convert to serde_json::Value
        let content = match dict.get_item("content") {
            Ok(Some(obj)) => Self::py_object_to_json_value(py, obj)?,
            _ => serde_json::json!({})
        };
        
        // Extract style - convert to serde_json::Value
        let style = match dict.get_item("style") {
            Ok(Some(obj)) => Self::py_object_to_json_value(py, obj)?,
            _ => serde_json::json!({})
        };
        
        Ok(LayoutBlock {
            frame,
            block_type,
            content,
            style,
            page_number,
        })
    }
    
    /// Convert Python object (dict) to LayoutPage
    /// DEPRECATED: Not used in new direct call approach
    #[allow(dead_code)]
    fn py_object_to_layout_page(py: Python, obj: &PyObject) -> PyResult<LayoutPage> {
        let dict = obj.downcast::<PyDict>(py)
            .map_err(|_| PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "page must be a dict"
            ))?;
        
        // Extract number
        let number = match dict.get_item("number") {
            Ok(Some(obj)) => obj.extract::<u32>().ok(),
            _ => None
        }.unwrap_or(1);
        
        // Extract size
        let size = match dict.get_item("size") {
            Ok(Some(obj)) => {
                if let Ok(size_dict) = obj.downcast::<PyDict>() {
                    Self::py_dict_to_size(py, size_dict).unwrap_or_else(|_| Size::new(595.0, 842.0))
                } else {
                    Size::new(595.0, 842.0)
                }
            }
            _ => Size::new(595.0, 842.0) // A4 default
        };
        
        // Extract margins
        let margins = match dict.get_item("margins") {
            Ok(Some(obj)) => {
                if let Ok(margins_dict) = obj.downcast::<PyDict>() {
                    Self::py_dict_to_margins(py, margins_dict).unwrap_or_else(|_| Margins::new(72.0, 72.0, 72.0, 72.0))
                } else {
                    Margins::new(72.0, 72.0, 72.0, 72.0)
                }
            }
            _ => Margins::new(72.0, 72.0, 72.0, 72.0) // 1 inch default
        };
        
        // Extract blocks
        let blocks = match dict.get_item("blocks") {
            Ok(Some(obj)) => {
                if let Ok(blocks_list) = obj.downcast::<PyList>() {
                    let mut blocks_vec = Vec::new();
                    for block_item in blocks_list.iter() {
                        if let Ok(block) = Self::py_object_to_layout_block(py, &block_item.to_object(py)) {
                            blocks_vec.push(block);
                        }
                    }
                    blocks_vec
                } else {
                    Vec::new()
                }
            }
            _ => Vec::new()
        };
        
        Ok(LayoutPage {
            number,
            size,
            margins,
            blocks,
            skip_headers_footers: false,
        })
    }
    
    /// Convert Python dict to Rect
    /// DEPRECATED: Not used in new direct call approach
    #[allow(dead_code)]
    fn py_dict_to_rect(py: Python, dict: &PyDict) -> PyResult<Rect> {
        let x = match dict.get_item("x") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(0.0);
        let y = match dict.get_item("y") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(0.0);
        let width = match dict.get_item("width") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(0.0);
        let height = match dict.get_item("height") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(0.0);
        
        Ok(Rect::new(x, y, width, height))
    }
    
    /// Convert Python dict to Size
    /// DEPRECATED: Not used in new direct call approach
    #[allow(dead_code)]
    fn py_dict_to_size(py: Python, dict: &PyDict) -> PyResult<Size> {
        let width = match dict.get_item("width") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(595.0);
        let height = match dict.get_item("height") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(842.0);
        
        Ok(Size::new(width, height))
    }
    
    /// Convert Python dict to Margins
    /// DEPRECATED: Not used in new direct call approach
    #[allow(dead_code)]
    fn py_dict_to_margins(py: Python, dict: &PyDict) -> PyResult<Margins> {
        let top = match dict.get_item("top") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(72.0);
        let bottom = match dict.get_item("bottom") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(72.0);
        let left = match dict.get_item("left") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(72.0);
        let right = match dict.get_item("right") {
            Ok(Some(obj)) => obj.extract::<f64>().ok(),
            _ => None
        }.unwrap_or(72.0);
        
        Ok(Margins::new(top, bottom, left, right))
    }
    
    /// Convert Python object to serde_json::Value (recursive)
    /// DEPRECATED: Not used in new direct call approach
    #[allow(dead_code)]
    fn py_object_to_json_value(py: Python, obj: &PyAny) -> PyResult<serde_json::Value> {
        // Try dict first
        if let Ok(dict) = obj.downcast::<PyDict>() {
            let mut map = serde_json::Map::new();
            for (key, value) in dict.iter() {
                let key_str = key.extract::<String>()?;
                let value_json = Self::py_object_to_json_value(py, value)?;
                map.insert(key_str, value_json);
            }
            return Ok(serde_json::Value::Object(map));
        }
        
        // Try list
        if let Ok(list) = obj.downcast::<PyList>() {
            let mut vec = Vec::new();
            for item in list.iter() {
                vec.push(Self::py_object_to_json_value(py, item)?);
            }
            return Ok(serde_json::Value::Array(vec));
        }
        
        // Try string
        if let Ok(s) = obj.extract::<String>() {
            return Ok(serde_json::Value::String(s));
        }
        
        // Try number (int or float)
        if let Ok(i) = obj.extract::<i64>() {
            return Ok(serde_json::Value::Number(i.into()));
        }
        if let Ok(f) = obj.extract::<f64>() {
            return Ok(serde_json::Value::Number(
                serde_json::Number::from_f64(f).unwrap_or(serde_json::Number::from(0))
            ));
        }
        
        // Try bool
        if let Ok(b) = obj.extract::<bool>() {
            return Ok(serde_json::Value::Bool(b));
        }
        
        // Try None
        if obj.is_none() {
            return Ok(serde_json::Value::Null);
        }
        
        // Fallback: convert to string
        Ok(serde_json::Value::String(format!("{:?}", obj)))
    }
}
