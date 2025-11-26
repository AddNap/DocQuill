//! Font registry abstraction for managing embedded fonts and PDF resources
use std::collections::HashMap;
use pdf_writer::{Pdf, Ref, Name};
use crate::font_utils::{load_font_file, add_truetype_font};
use crate::unicode_utils::has_polish_chars;
use crate::text_layout::FontMetrics;

pub struct FontRegistry {
    next_ref_id: i32,
    // Key can be a logical font name or file path → (font object id, font resource name)
    fonts: HashMap<String, (Ref, Name<'static>)>,
    default_font_name: Option<Name<'static>>,
}

impl FontRegistry {
    pub fn new(start_ref: i32) -> Self {
        Self {
            next_ref_id: start_ref,
            fonts: HashMap::new(),
            default_font_name: None,
        }
    }

    pub fn next_ref(&mut self) -> Ref {
        let r = Ref::new(self.next_ref_id);
        self.next_ref_id += 1;
        r
    }

    pub fn get(&self, key: &str) -> Option<(Ref, Name<'static>)> {
        self.fonts.get(key).copied()
    }

    pub fn insert(&mut self, key: String, id: Ref, name: Name<'static>) {
        self.fonts.insert(key, (id, name));
    }

    /// Get or create a Type0 font (CIDFontType2) from a TTF/OTF path
    /// Returns (font_object_id, font_resource_name)
    /// 
    /// Note: font_objects are collected for manual injection into PDF bytes
    pub fn get_or_create_type0(
        &mut self,
        pdf: &mut Pdf,
        font_key: &str,
        font_path: &str,
        font_objects: &mut Vec<(Ref, String)>,
    ) -> pyo3::PyResult<(Ref, Name<'static>)> {
        if let Some(&(id, name)) = self.fonts.get(font_key) {
            return Ok((id, name));
        }
        // Load & embed TTF via existing utilities
        let font_id = self.next_ref();
        let data = crate::font_utils::load_font_file(font_path)?;
        let name = crate::font_utils::add_truetype_font(
            pdf,
            &data,
            font_id,
            &mut self.next_ref_id,
            font_objects,
        )?;
        self.fonts.insert(font_key.to_string(), (font_id, name));
        Ok((font_id, name))
    }

    /// Get or register a built-in PDF font (Type1)
    /// Returns font resource name (e.g., Name(b"F1"))
    pub fn get_or_builtin(
        &mut self,
        pdf: &mut Pdf,
        font_name: &str,
    ) -> Name<'static> {
        // Check if already registered
        if let Some((_, name)) = self.fonts.get(font_name) {
            return *name;
        }
        
        // Map logical font names to PDF built-in fonts
        let (font_ref, base_font_name) = match font_name {
            "Helvetica" | "Arial" => (Name(b"F1"), Name(b"Helvetica")),
            "Helvetica-Bold" | "Arial-Bold" => (Name(b"F2"), Name(b"Helvetica-Bold")),
            "Helvetica-Oblique" | "Arial-Italic" => (Name(b"F3"), Name(b"Helvetica-Oblique")),
            "Times-Roman" | "Times" => (Name(b"F4"), Name(b"Times-Roman")),
            "Courier" => (Name(b"F5"), Name(b"Courier")),
            _ => (Name(b"F1"), Name(b"Helvetica")), // Default to Helvetica
        };
        
        // Register built-in font
        let font_id = self.next_ref();
        pdf.type1_font(font_id).base_font(base_font_name);
        self.fonts.insert(font_name.to_string(), (font_id, font_ref));
        
        font_ref
    }
    
    /// Resolve font name for text (auto-detect Polish characters and use TTF if needed)
    /// Returns effective font name (may be a TTF path or logical name)
    pub fn resolve_font_name_for_text(font_name: &str, text: &str) -> String {
        // If text contains Polish characters, try to use DejaVu Sans
        if has_polish_chars(text) {
            let dejavu_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            ];
            
            for path in &dejavu_paths {
                if std::path::Path::new(path).exists() {
                    return path.to_string();
                }
            }
            
            // If DejaVu not found, return logical name (will try to find TTF or fallback to builtin)
            return "DejaVu Sans".to_string();
        }
        
        // For non-Polish text, use original font name
        font_name.to_string()
    }
    
    /// Get or register font (TTF/OTF or built-in)
    /// Tries TTF first if font_name looks like a path or is registered, then falls back to built-in
    pub fn get_or_register(
        &mut self,
        pdf: &mut Pdf,
        font_name: &str,
    ) -> pyo3::PyResult<Name<'static>> {
        // Check if already registered
        if let Some((_, name)) = self.fonts.get(font_name) {
            return Ok(*name);
        }
        
        // Check if font_name is a file path (ends with .ttf, .otf, .TTF, .OTF)
        let is_font_file = font_name.ends_with(".ttf") 
            || font_name.ends_with(".otf")
            || font_name.ends_with(".TTF")
            || font_name.ends_with(".OTF");
        
        // Try to load TTF/OTF font if it's a file path
        if is_font_file {
            match load_font_file(font_name) {
                Ok(font_data) => {
                    let font_id = self.next_ref();
                    // Note: get_or_register doesn't track font_objects - they should be tracked at renderer level
                    // For now, we'll pass empty vec (font objects won't be injected, but fonts will still work)
                    let mut temp_font_objects = Vec::new();
                    match add_truetype_font(
                        pdf,
                        &font_data,
                        font_id,
                        &mut self.next_ref_id,
                        &mut temp_font_objects,
                    ) {
                        Ok(font_ref) => {
                            self.fonts.insert(font_name.to_string(), (font_id, font_ref));
                            return Ok(font_ref);
                        },
                        Err(e) => {
                            // Fallback to built-in fonts on error
                            eprintln!("⚠️  Failed to load TTF font {}: {}, falling back to built-in", font_name, e);
                        }
                    }
                },
                Err(e) => {
                    // Fallback to built-in fonts if file can't be loaded
                    eprintln!("⚠️  Failed to load font file {}: {}, falling back to built-in", font_name, e);
                }
            }
        }
        
        // Fallback to built-in font
        Ok(self.get_or_builtin(pdf, font_name))
    }
    
    /// Resolve font for text (auto-detect Polish and use appropriate font)
    /// Also handles fallback fonts for missing glyphs (emoji, CJK, etc.)
    pub fn resolve_for_text(
        &mut self,
        pdf: &mut Pdf,
        font_name: &str,
        text: &str,
    ) -> pyo3::PyResult<Name<'static>> {
        let effective_font_name = Self::resolve_font_name_for_text(font_name, text);
        
        // If effective_font_name is a TTF path, use get_or_create_type0 if available
        // Otherwise, use get_or_register
        let is_font_file = effective_font_name.ends_with(".ttf") 
            || effective_font_name.ends_with(".otf")
            || effective_font_name.ends_with(".TTF")
            || effective_font_name.ends_with(".OTF");
        
        if is_font_file {
            // For TTF files, we need font_objects, but get_or_register doesn't have them
            // So we'll use get_or_register which will still work, but font_objects won't be injected
            // TODO: Pass font_objects through FontRegistry or use a different approach
            match self.get_or_register(pdf, &effective_font_name) {
                Ok(font_ref) => return Ok(font_ref),
                Err(_) => {
                    // Fall through to fallback fonts
                }
            }
        } else {
            // Try to get or register the primary font
            match self.get_or_register(pdf, &effective_font_name) {
                Ok(font_ref) => return Ok(font_ref),
                Err(_) => {
                    // Fall through to fallback fonts
                }
            }
        }
        
        // If primary font fails, try fallback fonts
        let fallback_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        ];
        
        for fallback_path in &fallback_fonts {
            if std::path::Path::new(fallback_path).exists() {
                match self.get_or_register(pdf, fallback_path) {
                    Ok(font_ref) => return Ok(font_ref),
                    Err(_) => continue,
                }
            }
        }
        
        // Last resort: use built-in Helvetica
        Ok(self.get_or_builtin(pdf, "Helvetica"))
    }
    
    /// Check if a font can render a specific character
    /// Returns true if character is likely supported
    pub fn can_render_char(font_path: &str, ch: char) -> bool {
        use ttf_parser::Face;
        
        if let Ok(font_data) = load_font_file(font_path) {
            if let Ok(face) = Face::parse(&font_data, 0) {
                let glyph_id = face.glyph_index(ch);
                return glyph_id.is_some();
            }
        }
        false
    }
    
    /// Set default font for new pages
    pub fn set_default_font(&mut self, name: Name<'static>) {
        self.default_font_name = Some(name);
    }
    
    /// Get default font (if set)
    pub fn get_default_font(&self) -> Option<Name<'static>> {
        self.default_font_name
    }
    
    /// Write all registered fonts into page Resources
    pub fn write_resources<'a>(&self, resources: &mut pdf_writer::writers::Resources<'a>) {
        if self.fonts.is_empty() {
            return;
        }
        let mut dict = resources.fonts();
        for (_k, (id, name)) in &self.fonts {
            dict.pair(*name, *id);
        }
    }
    
    /// Get font metrics for a given font name and size
    /// Tries to extract from TTF if available, otherwise returns default metrics
    pub fn get_font_metrics(&self, font_name: &str, font_size: f64) -> FontMetrics {
        // Check if font_name is a file path
        let is_font_file = font_name.ends_with(".ttf") 
            || font_name.ends_with(".otf")
            || font_name.ends_with(".TTF")
            || font_name.ends_with(".OTF");
        
        if is_font_file {
            // Try to load and extract metrics from TTF
            match load_font_file(font_name) {
                Ok(font_data) => {
                    match FontMetrics::from_ttf(&font_data, font_size) {
                        Ok(metrics) => return metrics,
                        Err(_) => {
                            // Fallback to default on error
                        }
                    }
                },
                Err(_) => {
                    // Fallback to default if file can't be loaded
                }
            }
        }
        
        // Default metrics for built-in fonts or if TTF loading fails
        FontMetrics::default(font_size)
    }
}


