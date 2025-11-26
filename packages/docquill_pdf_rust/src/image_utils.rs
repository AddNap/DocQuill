//! Image utilities for PDF rendering

use image::DynamicImage;
use pdf_writer::{Name, Pdf, Ref};
use pyo3::prelude::*;

/// Add image to PDF from bytes
/// Returns the XObject name for the image
pub fn add_image_to_pdf(
    pdf: &mut Pdf,
    image_data: &[u8],
    image_id: Ref,
    next_ref_id: &mut i32,
) -> PyResult<Name<'static>> {
    // Try to decode image
    let img = image::load_from_memory(image_data).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to decode image: {}", e))
    })?;

    // Determine if image has alpha channel
    let has_alpha =
        matches!(img, DynamicImage::ImageRgba8(_)) || matches!(img, DynamicImage::ImageRgba16(_));

    // Convert to RGB and extract alpha as SMask if present
    let (rgb_data, width, height, smask_data_opt) = if has_alpha {
        let rgba = img.to_rgba8();
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
        let rgb = img.to_rgb8();
        let (w, h) = rgb.dimensions();
        (rgb.into_raw(), w, h, None)
    };

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
        let mut xobject = pdf.image_xobject(image_id, &rgb_data);
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

    Ok(Name(image_name_bytes))
}
