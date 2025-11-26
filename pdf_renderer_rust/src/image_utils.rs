//! Image utilities for PDF rendering

use image::{DynamicImage, GenericImageView, ImageFormat};
use image::io::Reader as ImageReader;
use std::fs::File;
use std::io::{BufReader, Cursor};
use std::path::Path;
use pdf_writer::{Pdf, Ref, Name, Content};
use pyo3::prelude::*;
use resvg::usvg::{Tree, Options};
use resvg::tiny_skia::Pixmap;

/// Load image from file path
/// For WMF/EMF files, returns SVG content as string instead of DynamicImage
/// For other formats, returns DynamicImage as before
pub enum ImageData {
    Image(DynamicImage),
    Svg(String),
}

pub fn load_image(path: &str) -> PyResult<ImageData> {
    let path_obj = Path::new(path);
    if !path_obj.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>(
            format!("Image file not found: {}", path)
        ));
    }
    
    // Check if file is WMF/EMF - convert to PNG via SVG
    let ext = path_obj.extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_lowercase())
        .unwrap_or_default();
    
    if ext == "wmf" || ext == "emf" {
        // Convert WMF/EMF to SVG, return SVG content (conversion to PNG happens in add_image_to_pdf)
        let wmf_data = std::fs::read(path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to read WMF/EMF file {}: {}", path, e)
            ))?;
        
        // Convert to SVG using emf_converter
        let svg_content = if emf_converter::emf::is_emf_format(&wmf_data) {
            emf_converter::emf::convert_emf_to_svg(&wmf_data)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Failed to convert EMF to SVG: {}", e)
                ))?
        } else if emf_converter::wmf::is_wmf_format(&wmf_data) {
            emf_converter::wmf::convert_wmf_to_svg(&wmf_data)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Failed to convert WMF to SVG: {}", e)
                ))?
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "File is not EMF or WMF format"
            ));
        };
        
        return Ok(ImageData::Svg(svg_content));
    }
    
    let file = File::open(path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
            format!("Failed to open image file {}: {}", path, e)
        ))?;
    
    let reader = BufReader::new(file);
    let img = ImageReader::new(reader)
        .with_guessed_format()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Failed to read image format: {}", e)
        ))?
        .decode()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Failed to decode image: {}", e)
        ))?;
    
    Ok(ImageData::Image(img))
}

pub fn load_image_from_bytes(data: &[u8], mime_type: Option<&str>) -> PyResult<ImageData> {
    // Check if data is WMF/EMF format - convert to SVG in Rust
    // Always check format first, even if mime_type is provided (it might be wrong)
    if emf_converter::emf::is_emf_format(data) {
        eprintln!("   Detected EMF format ({} bytes), converting to SVG in Rust", data.len());
        let svg_content = emf_converter::emf::convert_emf_to_svg(data)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to convert EMF to SVG: {}", e)
            ))?;
        eprintln!("   EMF converted to SVG ({} bytes)", svg_content.len());
        return Ok(ImageData::Svg(svg_content));
    }
    
    if emf_converter::wmf::is_wmf_format(data) {
        eprintln!("   Detected WMF format ({} bytes), converting to SVG in Rust", data.len());
        let svg_content = emf_converter::wmf::convert_wmf_to_svg(data)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to convert WMF to SVG: {}", e)
            ))?;
        eprintln!("   WMF converted to SVG ({} bytes)", svg_content.len());
        return Ok(ImageData::Svg(svg_content));
    }
    
    // If mime_type says image/svg+xml, attempt to parse as SVG string
    if let Some(mt) = mime_type {
        if mt == "image/svg+xml" {
            let svg_content = std::str::from_utf8(data)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Invalid UTF-8 SVG data: {}", e)
                ))?;
            return Ok(ImageData::Svg(svg_content.to_string()));
        }
    }

    let cursor = Cursor::new(data);
    let mut reader = ImageReader::new(cursor);
    if let Some(mt) = mime_type {
        if let Some(fmt) = image_format_from_mime(mt) {
            reader.set_format(fmt);
        }
    }
    let reader = reader
        .with_guessed_format()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Failed to detect image format from stream: {}", e)
        ))?;
    let img = reader.decode()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Failed to decode image from stream: {}", e)
        ))?;
    Ok(ImageData::Image(img))
}

fn image_format_from_mime(mime_type: &str) -> Option<ImageFormat> {
    match mime_type {
        "image/png" => Some(ImageFormat::Png),
        "image/jpeg" | "image/jpg" => Some(ImageFormat::Jpeg),
        "image/gif" => Some(ImageFormat::Gif),
        "image/webp" => Some(ImageFormat::WebP),
        "image/bmp" => Some(ImageFormat::Bmp),
        _ => None,
    }
}

/// Convert SVG to PNG using dimensions from DOCX (in EMU)
/// Also saves the PNG to a temporary file for debugging
fn convert_svg_to_png(svg_content: &str, width_emu: Option<f64>, height_emu: Option<f64>) -> PyResult<DynamicImage> {
    let opt = Options::default();
    let fontdb = resvg::usvg::fontdb::Database::new();
    let tree = Tree::from_str(svg_content, &opt, &fontdb)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Failed to parse SVG: {}", e)
        ))?;
    
    let size = tree.size();
    let svg_width = size.width();
    let svg_height = size.height();
    
    // Store SVG dimensions in points for later use
    let svg_width_pt = svg_width as f64;
    let svg_height_pt = svg_height as f64;
    
    eprintln!("   SVG viewBox: {}x{}", svg_width, svg_height);
    
    // Calculate target size using wp:extent from DOCX
    // wp:extent specifies the desired display size in the document
    // SVG from rclFrame may be larger, so we scale it to match wp:extent
    let (target_width, target_height) = if let (Some(width_emu), Some(height_emu)) = (width_emu, height_emu) {
        // Convert EMU to points (wp:extent is in EMU)
        let emu_to_pt = 72.0 / 914400.0;
        let docx_width_pt = width_emu * emu_to_pt;
        let docx_height_pt = height_emu * emu_to_pt;
        
        eprintln!("   wp:extent: {}x{} EMU = {:.2}x{:.2} pt", width_emu, height_emu, docx_width_pt, docx_height_pt);
        eprintln!("   SVG from rclFrame: {:.2}x{:.2} pt", svg_width, svg_height);
        
        // Use wp:extent as the target size (this is what DOCX wants to display)
        // Use 300 DPI for high-quality PNG rendering
        // 1 point = 1/72 inch, so at 300 DPI: 1 point = 300/72 = 4.166... pixels
        let target_dpi = 300.0;
        let pixels_per_point = target_dpi / 72.0; // 300/72 = 4.166...
        let target_w = (docx_width_pt * pixels_per_point) as u32;
        let target_h = (docx_height_pt * pixels_per_point) as u32;
        
        eprintln!("   SVG conversion: scaling from {}x{} pt (rclFrame) to {}x{} pt (wp:extent) = {}x{} pixels at {} DPI", 
            svg_width, svg_height, docx_width_pt, docx_height_pt, target_w, target_h, target_dpi);
        
        (target_w, target_h)
    } else {
        // Fallback: use SVG dimensions at high resolution (300 DPI)
        // Use 300 DPI for high-quality PNG rendering
        let target_dpi = 300.0;
        let pixels_per_point = target_dpi / 72.0; // 300/72 = 4.166...
        
        let target_w = (svg_width * pixels_per_point) as u32;
        let target_h = (svg_height * pixels_per_point) as u32;
        
        eprintln!("   SVG conversion: original={}x{} pt, target={}x{} pixels at {} DPI (no DOCX dims)", 
            svg_width, svg_height, target_w, target_h, target_dpi);
        
        (target_w, target_h)
    };
    
    let mut pixmap = Pixmap::new(target_width, target_height)
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Failed to create pixmap for SVG"
        ))?;
    
    // Calculate scale transform to scale SVG from rclFrame size to wp:extent size
    // SVG has dimensions from rclFrame (e.g., 299x609 pt)
    // Target has dimensions from wp:extent (e.g., 62.35x126.70 pt)
    // We need to scale SVG to match wp:extent exactly (non-uniform scaling is OK if wp:extent specifies it)
    // wp:extent is the authoritative size from DOCX, so we should match it exactly
    let scale_x = target_width as f32 / svg_width;
    let scale_y = target_height as f32 / svg_height;
    eprintln!("   Scale transform: x={:.4}, y={:.4} (from {}x{} to {}x{})", 
        scale_x, scale_y, svg_width, svg_height, target_width, target_height);
    eprintln!("   Aspect ratios: SVG={:.4}, target={:.4}", 
        svg_width / svg_height, target_width as f64 / target_height as f64);
    // Use non-uniform scaling to match wp:extent exactly - DOCX specifies the exact size
    let transform = resvg::tiny_skia::Transform::from_scale(scale_x, scale_y);
    
    // Render SVG to pixmap using resvg with scaling
    resvg::render(
        &tree,
        transform,
        &mut pixmap.as_mut()
    );
    
    // Convert pixmap to DynamicImage
    // resvg uses BGRA format, we need RGBA
    let mut rgba_data = Vec::with_capacity((pixmap.width() * pixmap.height() * 4) as usize);
    for chunk in pixmap.data().chunks_exact(4) {
        rgba_data.push(chunk[2]); // R
        rgba_data.push(chunk[1]); // G
        rgba_data.push(chunk[0]); // B
        rgba_data.push(chunk[3]); // A
    }
    
    let img = image::RgbaImage::from_raw(
        pixmap.width(),
        pixmap.height(),
        rgba_data
    ).ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
        "Failed to create image from pixmap"
    ))?;
    
    let dynamic_img = DynamicImage::ImageRgba8(img);
    
    // Save image to temporary file for debugging
    let temp_path = format!("/tmp/svg_converted_{}.png", std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs());
    dynamic_img.save(&temp_path).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
        format!("Failed to save debug image: {}", e)
    ))?;
    eprintln!("   Saved converted image to: {} (size: {}x{} pixels, full SVG size: {:.2}x{:.2} pt)", 
        temp_path, pixmap.width(), pixmap.height(), svg_width_pt, svg_height_pt);
    
    Ok(dynamic_img)
}

/// Add image to PDF and return image reference name
/// For SVG images, width_emu and height_emu should be provided from JSON
pub fn add_image_to_pdf(
    pdf: &mut Pdf,
    image_data: &ImageData,
    image_id: Ref,
    next_ref_id: &mut i32,
    width_emu: Option<f64>,
    height_emu: Option<f64>,
) -> PyResult<Name<'static>> {
    // Convert SVG to PNG if needed, otherwise use image directly
    let image = match image_data {
        ImageData::Svg(svg_content) => {
            convert_svg_to_png(svg_content, width_emu, height_emu)?
        }
        ImageData::Image(img) => img.clone(),
    };
    
    // Determine if image has alpha channel
    let has_alpha = matches!(image, DynamicImage::ImageRgba8(_)) || matches!(image, DynamicImage::ImageRgba16(_));
    // Convert to RGB (for color) and extract alpha as SMask if present
    let (image_data_vec, width, height, smask_data_opt): (Vec<u8>, u32, u32, Option<Vec<u8>>) = if has_alpha {
        let rgba = image.to_rgba8();
        let (w, h) = rgba.dimensions();
        let bytes = rgba.into_raw();
        // Split RGBA into RGB + Alpha
        let mut rgb: Vec<u8> = Vec::with_capacity((w * h * 3) as usize);
        let mut alpha: Vec<u8> = Vec::with_capacity((w * h) as usize);
        for chunk in bytes.chunks_exact(4) {
            rgb.push(chunk[0]);
            rgb.push(chunk[1]);
            rgb.push(chunk[2]);
            alpha.push(chunk[3]);
        }
        (rgb, w, h, Some(alpha))
    } else {
        let rgb = image.to_rgb8();
        let (w, h) = rgb.dimensions();
        (rgb.into_raw(), w, h, None)
    };
    
    eprintln!("   Adding image to PDF: id={}, size={}x{}, data_len={}", 
        image_id.get(), width, height, image_data_vec.len());
    
    // If alpha present, create SMask first (avoid overlapping mutable borrows)
    let mut smask_id_opt: Option<Ref> = None;
    {
        if let Some(smask_data) = smask_data_opt {
            let smask_id = Ref::new(*next_ref_id);
            *next_ref_id += 1;
            {
                let mut smask = pdf.image_xobject(smask_id, &smask_data);
                smask.width(width as i32);
                smask.height(height as i32);
                smask.color_space().device_gray();
                smask.bits_per_component(8);
            }
            smask_id_opt = Some(smask_id);
        }
    }
    
    // Create image XObject
    {
        let mut xobject = pdf.image_xobject(image_id, &image_data_vec);
        xobject.width(width as i32);
        xobject.height(height as i32);
        xobject.color_space().device_rgb();
        xobject.bits_per_component(8);
        if let Some(smask_id) = smask_id_opt {
            xobject.s_mask(smask_id);
        }
    }
    
    // Create name for image reference (e.g., "I1", "I2", etc.)
    // Use Box::leak to safely create a 'static reference
    let image_name_str = format!("I{}", image_id.get());
    let image_name_boxed = image_name_str.clone().into_boxed_str();
    let image_name_static = Box::leak(image_name_boxed);
    let image_name_bytes = image_name_static.as_bytes();
    
    eprintln!("   Image XObject created: name={}, id={}, filter=FlateDecode", image_name_str, image_id.get());
    
    Ok(Name(image_name_bytes))
}

pub fn add_image_from_bytes(
    pdf: &mut Pdf,
    data: &[u8],
    image_id: Ref,
    next_ref_id: &mut i32,
    mime_type: Option<&str>,
    width_emu: Option<f64>,
    height_emu: Option<f64>,
) -> PyResult<Name<'static>> {
    let img_data = load_image_from_bytes(data, mime_type)?;
    add_image_to_pdf(pdf, &img_data, image_id, next_ref_id, width_emu, height_emu)
}

/// Add image to PDF from file path
pub fn add_image_from_path(
    pdf: &mut Pdf,
    image_path: &str,
    image_id: Ref,
    next_ref_id: &mut i32,
) -> PyResult<(Name<'static>, u32, u32)> {
    let img_data = load_image(image_path)?;
    let (width, height) = match &img_data {
        ImageData::Image(img) => img.dimensions(),
        ImageData::Svg(_) => {
            // For SVG, dimensions will be determined during conversion
            // Use default dimensions for now
            (0, 0)
        }
    };
    let name = add_image_to_pdf(pdf, &img_data, image_id, next_ref_id, None, None)?;
    Ok((name, width, height))
}

/// Draw image on canvas
pub fn draw_image_on_canvas(
    canvas: &mut Content,
    image_name: Name<'static>,
    x: f32,
    y: f32,
    width: f32,
    height: f32,
) {
    canvas.save_state();
    // Create transformation matrix: [a b c d e f] where:
    // a = width, d = height, e = x, f = y
    // This scales and translates the image
    canvas.transform([width, 0.0, 0.0, height, x, y]);
    canvas.x_object(image_name);
    canvas.restore_state();
}

