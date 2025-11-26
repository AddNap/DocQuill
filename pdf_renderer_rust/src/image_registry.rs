//! Image registry abstraction for managing image XObjects and PDF resources
use std::collections::HashMap;
use pdf_writer::{Pdf, Ref, Name};
use pyo3::prelude::*;

pub struct ImageRegistry {
    next_ref_id: i32,
    // path (or unique key) → (image object id, XObject resource name)
    images: HashMap<String, (Ref, Name<'static>)>,
    streams: HashMap<String, ImageStream>,
}

struct ImageStream {
    data: Vec<u8>,
    mime_type: Option<String>,
}

impl ImageRegistry {
    pub fn new(start_ref: i32) -> Self {
        Self {
            next_ref_id: start_ref,
            images: HashMap::new(),
            streams: HashMap::new(),
        }
    }

    pub fn next_ref(&mut self) -> Ref {
        let r = Ref::new(self.next_ref_id);
        self.next_ref_id += 1;
        r
    }

    pub fn get(&self, key: &str) -> Option<(Ref, Name<'static>)> {
        self.images.get(key).copied()
    }

    pub fn insert(&mut self, key: String, id: Ref, name: Name<'static>) {
        self.images.insert(key, (id, name));
    }

    pub fn register_stream(&mut self, key: String, data: Vec<u8>, mime_type: Option<String>) {
        // Replace any existing cached image so it will be regenerated from new data
        self.images.remove(&key);
        self.streams.insert(key, ImageStream { data, mime_type });
    }

    /// Get or create an Image XObject from a file path
    /// Returns (image_object_id, xobject_name)
    pub fn get_or_create_from_path(
        &mut self,
        pdf: &mut Pdf,
        path: &str,
    ) -> pyo3::PyResult<(Ref, Name<'static>)> {
        self.get_or_create_from_path_with_dims(pdf, path, None, None)
    }
    
    /// Get or create an Image XObject from a file path with target dimensions (in EMU)
    /// Returns (image_object_id, xobject_name)
    pub fn get_or_create_from_path_with_dims(
        &mut self,
        pdf: &mut Pdf,
        path: &str,
        width_emu: Option<f64>,
        height_emu: Option<f64>,
    ) -> pyo3::PyResult<(Ref, Name<'static>)> {
        // Determine if this is a vector format (SVG/WMF/EMF) that needs dimensions for conversion
        // For vector formats, dimensions affect the converted PNG quality, so we cache separately
        // For raster formats (JPEG/PNG), dimensions don't affect XObject content, so we reuse the same XObject
        let is_vector_format = {
            let ext = std::path::Path::new(path)
                .extension()
                .and_then(|e| e.to_str())
                .map(|s| s.to_lowercase())
                .unwrap_or_default();
            ext == "svg" || ext == "wmf" || ext == "emf"
        };
        
        // Build cache key: include dimensions only for vector formats
        let cache_key = if is_vector_format {
            if let (Some(w), Some(h)) = (width_emu, height_emu) {
                format!("{}:{}x{}", path, w, h)
            } else {
                format!("{}:none", path)
            }
        } else {
            // For raster images, use path only (dimensions don't affect XObject content)
            path.to_string()
        };
        
        // Check if image is already cached
        if let Some(&(id, name)) = self.images.get(&cache_key) {
            return Ok((id, name));
        }
        
        // Load image (for WMF/EMF, this returns SVG content; conversion happens in add_image_to_pdf)
        let img_data = crate::image_utils::load_image(path)?;
        let image_id = self.next_ref();
        let mut counter = self.next_ref_id;
        // Pass dimensions to add_image_to_pdf for SVG conversion
        let name = crate::image_utils::add_image_to_pdf(pdf, &img_data, image_id, &mut counter, width_emu, height_emu)?;
        self.next_ref_id = counter;
        self.images.insert(cache_key, (image_id, name));
        Ok((image_id, name))
    }

    /// Get or create an Image XObject from an in-memory stream
    pub fn get_or_create_from_stream(
        &mut self,
        pdf: &mut Pdf,
        key: &str,
        width_emu: Option<f64>,
        height_emu: Option<f64>,
    ) -> PyResult<(Ref, Name<'static>)> {
        // First, try to determine if this is a vector format by checking mime_type
        // We need to check before removing from streams, so we clone the mime_type
        let mime_type_clone = self.streams.get(key).and_then(|s| s.mime_type.clone());
        let is_vector_format = mime_type_clone.as_ref()
            .map(|mime| mime == "image/svg+xml" || mime.contains("wmf") || mime.contains("emf"))
            .unwrap_or(false);
        
        // Build cache key: include dimensions only for vector formats
        // For raster images, dimensions don't affect XObject content, so we reuse the same XObject
        let cache_key = if is_vector_format {
            if let (Some(w), Some(h)) = (width_emu, height_emu) {
                format!("{}:{}x{}", key, w, h)
            } else {
                format!("{}:none", key)
            }
        } else {
            // For raster images, use key only (dimensions don't affect XObject content)
            key.to_string()
        };
        
        if let Some(&(id, name)) = self.images.get(&cache_key) {
            eprintln!(
                "ImageRegistry: reusing cached stream {} (dims {:?}) as {} ({:?})",
                key,
                (width_emu, height_emu),
                String::from_utf8_lossy(name.0),
                id
            );
            return Ok((id, name));
        }

        let stream = self.streams.remove(key)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                format!("Image stream not registered: {}", key)
            ))?;
        eprintln!(
            "ImageRegistry: creating image from stream {} (dims {:?}, {} bytes, mime={:?})",
            key,
            (width_emu, height_emu),
            stream.data.len(),
            stream.mime_type
        );

        let image_id = self.next_ref();
        let mut counter = self.next_ref_id;
        let name = crate::image_utils::add_image_from_bytes(
            pdf,
            &stream.data,
            image_id,
            &mut counter,
            stream.mime_type.as_deref(),
            width_emu,
            height_emu,
        )?;
        self.next_ref_id = counter;
        self.images.insert(cache_key, (image_id, name));
        Ok((image_id, name))
    }

    /// Write all registered images into page Resources
    pub fn write_resources<'a>(&self, resources: &mut pdf_writer::writers::Resources<'a>) {
        if self.images.is_empty() {
            return;
        }
        let mut dict = resources.x_objects();
        for (_k, (id, name)) in &self.images {
            dict.pair(*name, *id);
        }
    }
}


