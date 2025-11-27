//! WMF format parser and converter

use crate::svg_writer::SvgWriter;
use crate::emf::convert_emf_to_svg;

/// Check if data is WMF format
pub fn is_wmf_format(data: &[u8]) -> bool {
    // Check for placeable WMF header (starts with 0x9AC6CDD7)
    if data.len() >= 4 {
        let sig = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
        if sig == 0xCDD79AC6 {
            return true;
        }
    }
    
    // Check for standard WMF (starts with 0xD7CD)
    if data.len() >= 2 {
        let sig = u16::from_le_bytes([data[0], data[1]]);
        if sig == 0xCDD7 {
            return true;
        }
    }
    
    false
}

/// Convert WMF data to SVG string
pub fn convert_wmf_to_svg(data: &[u8]) -> Result<String, Box<dyn std::error::Error>> {
    if !is_wmf_format(data) {
        return Err("Invalid WMF format".into());
    }

    // Try to extract embedded EMF from WMF
    if let Some(embedded_emf) = extract_embedded_emf(data) {
        return convert_emf_to_svg(&embedded_emf);
    }

    // Parse WMF and convert to SVG
    let (width_px, height_px) = parse_wmf_size(data)?;
    let width = normalize_dimension(width_px);
    let height = normalize_dimension(height_px);

    eprintln!("WMF - Final SVG dimensions: {}x{} pixels", width, height);

    // For now, create a placeholder SVG
    // TODO: Implement full WMF parsing
    let mut svg = SvgWriter::new(width, height);
    svg.add_text(10.0, height as f64 / 2.0, "WMF conversion not yet fully implemented");
    
    Ok(svg.finish())
}

/// Extract embedded EMF from WMF (if present)
fn extract_embedded_emf(_data: &[u8]) -> Option<Vec<u8>> {
    // TODO: Implement WMF escape record parsing to extract embedded EMF
    // This would parse META_ESCAPE_ENHANCED_METAFILE records
    None
}

/// Parse WMF size from header
/// Returns size in pixels (converted from logical units using units_per_inch for placeable WMF)
fn parse_wmf_size(data: &[u8]) -> Result<(f64, f64), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    let mut cursor = std::io::Cursor::new(data);
    
    // Check for placeable WMF header (22 bytes)
    if data.len() >= 22 {
        // Check placeable header signature (0x9AC6CDD7 in little-endian)
        let sig = cursor.read_u32::<LittleEndian>()?;
        
        if sig == 0xCDD79AC6 {
            // Placeable WMF header found
            // This header contains bounding box and units_per_inch, which define the physical size
            cursor.set_position(6); // Skip handle (2 bytes) and reserved (4 bytes)
            let left = cursor.read_i16::<LittleEndian>()?;
            let top = cursor.read_i16::<LittleEndian>()?;
            let right = cursor.read_i16::<LittleEndian>()?;
            let bottom = cursor.read_i16::<LittleEndian>()?;
            let units_per_inch = cursor.read_u16::<LittleEndian>()?;
            
            // Calculate size in logical units
            let width_logical = (right - left) as f64;
            let height_logical = (bottom - top) as f64;
            
            if units_per_inch > 0 && width_logical > 0.0 && height_logical > 0.0 {
                // Convert from logical units to pixels at 96 DPI (standard web DPI)
                // This matches the approach used for EMF rclFrame conversion
                // 1 inch = units_per_inch logical units
                // 1 inch = 96 pixels (96 DPI)
                // Therefore: 1 logical unit = 96 / units_per_inch pixels
                let logical_to_px = 96.0 / units_per_inch as f64;
                let width_px = width_logical * logical_to_px;
                let height_px = height_logical * logical_to_px;
                
                eprintln!("WMF Placeable Header - BoundingBox: {}x{} logical units, {} units/inch", 
                          width_logical, height_logical, units_per_inch);
                eprintln!("WMF Placeable Header - Size: {:.2}px x {:.2}px (96 DPI)", width_px, height_px);
                
                return Ok((width_px.max(1.0), height_px.max(1.0)));
            } else if width_logical > 0.0 && height_logical > 0.0 {
                // If units_per_inch is 0 or invalid, use logical units directly
                // This is a fallback, but may not be accurate
                eprintln!("WMF Placeable Header - BoundingBox: {}x{} logical units (no units/inch, using as pixels)", 
                          width_logical, height_logical);
                return Ok((width_logical.max(1.0), height_logical.max(1.0)));
            }
        } else {
            // Standard WMF - try to read from metafile header
            cursor.set_position(0);
            // Standard WMF starts with record type and size
            // Try to read bounding box from metafile header if available
            if data.len() >= 18 {
                cursor.set_position(6); // Skip type and size
                let left = cursor.read_i16::<LittleEndian>()?;
                let top = cursor.read_i16::<LittleEndian>()?;
                let right = cursor.read_i16::<LittleEndian>()?;
                let bottom = cursor.read_i16::<LittleEndian>()?;
                
                let width = (right - left).abs() as f64;
                let height = (bottom - top).abs() as f64;
                if width > 0.0 && height > 0.0 {
                    eprintln!("WMF Standard Header - BoundingBox: {}x{} logical units (no units/inch, using as pixels)", 
                              width, height);
                    return Ok((width, height));
                }
            }
        }
    }
    
    // Fallback: default size
    eprintln!("WMF - No valid size found in header, using default: 800x600");
    Ok((800.0, 600.0))
}

/// Normalize dimension value
fn normalize_dimension(value: f64) -> u32 {
    if value.is_finite() && value > 0.0 && value < 20000.0 {
        value.ceil() as u32
    } else {
        800 // Default fallback
    }
}

