//! Font utilities for loading and registering TrueType fonts

use pdf_writer::types::{CidFontType, FontFlags, SystemInfo};
use pdf_writer::{Name, Pdf, Rect, Ref, Str};
use pyo3::prelude::*;
use std::collections::{BTreeMap, HashMap};
use std::fs::File;
use std::io::Read;
use std::path::Path;
use ttf_parser::Face;

/// Map Unicode code point to CID (Character ID) for Type0 fonts
pub type CidMap = HashMap<u32, u16>;

/// Load TTF/OTF font from file path
pub fn load_font_file(path: &str) -> PyResult<Vec<u8>> {
    let path_obj = Path::new(path);
    if !path_obj.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>(
            format!("Font file not found: {}", path),
        ));
    }

    let mut file = File::open(path).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
            "Failed to open font file {}: {}",
            path, e
        ))
    })?;

    let mut font_data = Vec::new();
    file.read_to_end(&mut font_data).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
            "Failed to read font file {}: {}",
            path, e
        ))
    })?;

    // Validate font using ttf-parser
    Face::parse(&font_data, 0).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Invalid font file {}: {}",
            path, e
        ))
    })?;

    Ok(font_data)
}

/// Add TrueType font to PDF as Type0 font (CIDFontType2)
/// Returns the font resource name and Unicode->CID mapping
///
/// Creates full Type0 font structure: FontDescriptor, CIDFont, Type0 font, CIDToGIDMap, and ToUnicode CMap.
/// CID mapping: For Identity-H encoding, we use GID (Glyph ID) as CID, creating a direct mapping
/// from Unicode code points to CIDs via the font's cmap table.
pub fn add_truetype_font(
    pdf: &mut Pdf,
    font_data: &[u8],
    font_id: Ref,
    next_ref_id: &mut i32,
) -> PyResult<(Name<'static>, CidMap)> {
    // Validate font using ttf-parser
    let face = Face::parse(font_data, 0).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid font file: {}", e))
    })?;

    // Get font metrics from TTF
    let units_per_em = face.units_per_em();
    let ascender = face.ascender() as f32;
    let descender = face.descender() as f32;

    // Calculate font metrics in PDF units (normalized to 1000 units)
    let scale = 1000.0 / units_per_em as f32;
    let pdf_ascender = (ascender * scale) as i32;
    let pdf_descender = (descender * scale) as i32;

    // Get font bounding box
    let bbox = face.global_bounding_box();
    let pdf_bbox = [
        (bbox.x_min as f32 * scale) as i32,
        (bbox.y_min as f32 * scale) as i32,
        (bbox.x_max as f32 * scale) as i32,
        (bbox.y_max as f32 * scale) as i32,
    ];

    // Get font name
    let font_family = face
        .names()
        .into_iter()
        .find(|name| name.name_id == 1) // Family ID = 1
        .and_then(|name| name.to_string())
        .unwrap_or_else(|| format!("Font{}", font_id.get()));

    // Build Unicode -> CID/GID mapping from font's cmap table
    // For Identity-H encoding, we use GID (Glyph ID) as CID
    // This creates a direct mapping: Unicode code point -> GID -> CID
    let mut cid_map = HashMap::new();
    let mut cid_to_gid_map = Vec::new();
    let mut cid_widths: BTreeMap<u16, i32> = BTreeMap::new();

    // Default width (half of 1000 units) used as fallback
    let default_width = 500_i32;

    // Iterate through BMP Unicode range to build mapping (covers Latin + punctuation + symbols)
    for code_point in 0x0000u32..=0xFFFFu32 {
        if let Some(ch) = char::from_u32(code_point) {
            if let Some(glyph_id) = face.glyph_index(ch) {
                let gid = glyph_id.0 as u16;
                // Use GID as CID for Identity-H encoding
                let cid = gid;

                // Store Unicode -> CID mapping (only first occurrence for a given Unicode code point)
                cid_map.entry(code_point).or_insert(cid);

                // Build CIDToGIDMap: CID -> GID (for Identity-H, CID == GID, but we still need the map)
                if cid_to_gid_map.len() <= cid as usize {
                    cid_to_gid_map.resize((cid + 1) as usize, 0u16);
                }
                cid_to_gid_map[cid as usize] = gid;

                // Capture advance width for this CID once
                if !cid_widths.contains_key(&cid) {
                    let width_pdf = face
                        .glyph_hor_advance(glyph_id)
                        .map(|adv| ((adv as f32) * scale).round() as i32)
                        .unwrap_or(default_width)
                        .max(0);
                    cid_widths.insert(cid, width_pdf);
                }
            }
        }
    }

    if cid_map.is_empty() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Font does not provide any Unicode glyphs in BMP range",
        ));
    }

    // Create font descriptor ID
    let font_descriptor_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;

    // Create CIDFont ID
    let cid_font_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;

    // Create CIDToGIDMap stream (maps CID to GID)
    let cid_to_gid_map_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;

    // Build CIDToGIDMap as binary stream (array of 2-byte big-endian GIDs)
    let mut cid_to_gid_bytes = Vec::new();
    for gid in &cid_to_gid_map {
        cid_to_gid_bytes.push((gid >> 8) as u8);
        cid_to_gid_bytes.push((gid & 0xFF) as u8);
    }

    pdf.stream(cid_to_gid_map_id, &cid_to_gid_bytes);

    // Embed font file as stream
    let font_file_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;

    pdf.stream(font_file_id, font_data)
        .pair(Name(b"Length1"), font_data.len() as i32);

    // Create ToUnicode CMap stream
    let to_unicode_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;

    // Create ToUnicode CMap using the CID map we built
    // This maps CID -> Unicode (reverse of Unicode -> CID)
    // We'll use beginbfchar for individual mappings to ensure accuracy
    // Build mappings from CID map
    // Use beginbfchar blocks (max 100 entries per block per PDF spec)
    let mut cid_unicode_pairs: Vec<(u16, u32)> = cid_map
        .iter()
        .map(|(&unicode, &cid)| (cid, unicode))
        .collect();
    cid_unicode_pairs.sort_by_key(|&(cid, _)| cid);

    let mut cmap_sections = String::new();
    for chunk in cid_unicode_pairs.chunks(100) {
        cmap_sections.push_str(&format!("{} beginbfchar\n", chunk.len()));
        for (cid, unicode) in chunk {
            cmap_sections.push_str(&format!("<{:04X}> <{:04X}>\n", cid, unicode));
        }
        cmap_sections.push_str("endbfchar\n");
    }

    let cmap_content = format!(
        "/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo
<< /Registry (Adobe)
   /Ordering (Identity)
   /Supplement 0
>> def
/CMapName /Adobe-Identity-UCS def
/CMapVersion 1.0 def
/CMapType 1 def
/WMode 0 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
{}
endcmap
CMapName currentdict /CMap defineresource pop
end
end",
        cmap_sections
    );

    pdf.stream(to_unicode_id, cmap_content.as_bytes());

    // Prepare base font name (PostScript-friendly)
    let base_font_name = font_family.replace(' ', "#20");
    let base_font_boxed = base_font_name.clone().into_boxed_str();
    let base_font_static = Box::leak(base_font_boxed);
    let base_font_name = Name(base_font_static.as_bytes());

    // Build FontDescriptor using pdf-writer
    {
        let mut font_descriptor = pdf.font_descriptor(font_descriptor_id);
        font_descriptor
            .name(base_font_name)
            .flags(FontFlags::SYMBOLIC)
            .bbox(Rect::new(
                pdf_bbox[0] as f32,
                pdf_bbox[1] as f32,
                pdf_bbox[2] as f32,
                pdf_bbox[3] as f32,
            ))
            .italic_angle(0.0)
            .ascent(pdf_ascender as f32)
            .descent(pdf_descender as f32)
            .cap_height(pdf_ascender as f32)
            .stem_v(80.0)
            .font_file2(font_file_id);
    }

    // Build CIDFont object with widths
    {
        let mut cid_font = pdf.cid_font(cid_font_id);
        cid_font
            .subtype(CidFontType::Type2)
            .base_font(base_font_name)
            .system_info(SystemInfo {
                registry: Str(b"Adobe"),
                ordering: Str(b"Identity"),
                supplement: 0,
            })
            .font_descriptor(font_descriptor_id)
            .default_width(default_width as f32)
            .cid_to_gid_map_stream(cid_to_gid_map_id);

        {
            let mut widths_writer = cid_font.widths();
            let mut cid_iter = cid_widths.into_iter().peekable();
            while let Some((start_cid, start_width)) = cid_iter.next() {
                let mut widths = vec![start_width];
                let mut last_cid = start_cid;
                while let Some((next_cid, next_width)) = cid_iter.peek() {
                    if *next_cid == last_cid + 1 {
                        widths.push(*next_width);
                        last_cid = *next_cid;
                        cid_iter.next();
                    } else {
                        break;
                    }
                }
                widths_writer.consecutive(start_cid, widths.iter().map(|w| *w as f32));
            }
        }
    }

    // Build Type0 font object
    {
        let mut type0_font = pdf.type0_font(font_id);
        type0_font
            .base_font(base_font_name)
            .encoding_predefined(Name(b"Identity-H"))
            .descendant_font(cid_font_id)
            .to_unicode(to_unicode_id);
    }

    // Generate font resource name
    let font_num = font_id.get();
    let font_name_str = format!("F{}", font_num);
    let font_name_boxed = font_name_str.clone().into_boxed_str();
    let font_name_static = Box::leak(font_name_boxed);
    let font_name_bytes = font_name_static.as_bytes();

    Ok((Name(font_name_bytes), cid_map))
}

/// Helper function to find font in assets/fonts directory
/// Searches from current working directory up to project root
fn find_font_in_assets(font_filename: &str) -> Option<String> {
    // Try current working directory and parent directories
    if let Ok(cwd) = std::env::current_dir() {
        let mut dir = Some(cwd.as_path());
        for _ in 0..10 {
            // Search up to 10 levels
            if let Some(d) = dir {
                let assets_path = d.join("assets").join("fonts").join(font_filename);
                if assets_path.exists() {
                    return Some(assets_path.to_string_lossy().to_string());
                }
                dir = d.parent();
            } else {
                break;
            }
        }
    }

    // Also try from executable location (for compiled binaries)
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let mut dir = Some(exe_dir);
            for _ in 0..10 {
                if let Some(d) = dir {
                    let assets_path = d.join("assets").join("fonts").join(font_filename);
                    if assets_path.exists() {
                        return Some(assets_path.to_string_lossy().to_string());
                    }
                    dir = d.parent();
                } else {
                    break;
                }
            }
        }
    }

    None
}

/// Try to find DejaVu Sans font
/// First checks assets/fonts in project directory, then system locations
pub fn find_dejavu_sans() -> Option<String> {
    // First, try project assets/fonts directory
    if let Some(path) = find_font_in_assets("DejaVuSans.ttf") {
        return Some(path);
    }

    // Fallback to system locations
    let paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/DejaVu Sans.ttf", // macOS
        "C:/Windows/Fonts/DejaVuSans.ttf",                    // Windows
    ];

    for path in &paths {
        if Path::new(path).exists() {
            return Some(path.to_string());
        }
    }

    None
}

/// Try to find DejaVu Sans Bold font
/// First checks assets/fonts in project directory, then system locations
pub fn find_dejavu_sans_bold() -> Option<String> {
    // First, try project assets/fonts directory
    if let Some(path) = find_font_in_assets("DejaVuSans-Bold.ttf") {
        return Some(path);
    }

    // Fallback to system locations
    let paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/DejaVu Sans Bold.ttf", // macOS
        "C:/Windows/Fonts/DejaVuSans-Bold.ttf",                    // Windows
    ];

    for path in &paths {
        if Path::new(path).exists() {
            return Some(path.to_string());
        }
    }

    None
}

/// Try to find DejaVu Sans Italic font
/// First checks assets/fonts in project directory, then system locations
pub fn find_dejavu_sans_italic() -> Option<String> {
    // First, try project assets/fonts directory
    if let Some(path) = find_font_in_assets("DejaVuSans-Oblique.ttf") {
        return Some(path);
    }

    // Fallback to system locations
    let paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf",
        "/System/Library/Fonts/Supplemental/DejaVu Sans Oblique.ttf", // macOS
        "C:/Windows/Fonts/DejaVuSans-Oblique.ttf",                    // Windows
    ];

    for path in &paths {
        if Path::new(path).exists() {
            return Some(path.to_string());
        }
    }

    None
}

/// Try to find DejaVu Sans Bold Italic font
/// First checks assets/fonts in project directory, then system locations
pub fn find_dejavu_sans_bold_italic() -> Option<String> {
    // First, try project assets/fonts directory
    if let Some(path) = find_font_in_assets("DejaVuSans-BoldOblique.ttf") {
        return Some(path);
    }

    // Fallback to system locations
    let paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-BoldOblique.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-BoldOblique.ttf",
        "/System/Library/Fonts/Supplemental/DejaVu Sans Bold Oblique.ttf", // macOS
        "C:/Windows/Fonts/DejaVuSans-BoldOblique.ttf",                     // Windows
    ];

    for path in &paths {
        if Path::new(path).exists() {
            return Some(path.to_string());
        }
    }

    None
}
