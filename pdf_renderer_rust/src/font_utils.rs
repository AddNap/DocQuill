//! Font utilities for PDF rendering

use pdf_writer::{Pdf, Ref, Name, Filter, Rect as PdfRect};
use ttf_parser::Face;
use std::fs::File;
use std::io::Read;
use std::path::Path;
use pyo3::prelude::*;

/// Load TTF/OTF font from file path
pub fn load_font_file(path: &str) -> PyResult<Vec<u8>> {
    let path_obj = Path::new(path);
    if !path_obj.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>(
            format!("Font file not found: {}", path)
        ));
    }
    
    let mut file = File::open(path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
            format!("Failed to open font file {}: {}", path, e)
        ))?;
    
    let mut font_data = Vec::new();
    file.read_to_end(&mut font_data)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
            format!("Failed to read font file {}: {}", path, e)
        ))?;
    
    // Validate font using ttf-parser
    Face::parse(&font_data, 0)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Invalid font file {}: {}", path, e)
        ))?;
    
    Ok(font_data)
}

/// Add TrueType font to PDF
/// 
/// Embeds a TrueType font in the PDF document as a CIDFont (Type 0 font) with Unicode support.
/// This creates a complete font structure including:
/// - FontDescriptor with embedded font file
/// - CIDFont (Type 2 CIDFont)
/// - Type 0 font (wrapper) with ToUnicode CMap
/// 
/// Returns a font reference name that can be used in page resources.
/// 
/// Font objects are stored in font_objects for later injection into PDF bytes.
pub fn add_truetype_font(
    pdf: &mut Pdf,
    font_data: &[u8],
    font_id: Ref,
    next_ref_id: &mut i32,
    font_objects: &mut Vec<(Ref, String)>, // Store font objects for manual injection
) -> PyResult<Name<'static>> {
    // Validate font using ttf-parser
    let face = Face::parse(font_data, 0)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Invalid font file: {}", e)
        ))?;
    
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
    
    // Create font descriptor ID
    let font_descriptor_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;
    
    // Create CIDFont ID
    let cid_font_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;
    
    // Embed font file as stream
    let font_file_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;
    
    // Embed font file as stream - pdf-writer automatically finishes streams
    pdf.stream(font_file_id, font_data)
        .filter(Filter::FlateDecode)
        .pair(Name(b"Length1"), font_data.len() as i32);
    
    // Create font descriptor using pdf-writer's FontDescriptor API
    // Note: pdf-writer may not have direct FontDescriptor API, so we'll use stream/dict approach
    // Create font descriptor as a dictionary object
    let font_descriptor_dict_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;
    
    // Create font descriptor dictionary manually
    // We'll create it as a stream with dictionary content, or use insert() if available
    // For now, let's try using the lower-level API
    
    // Create ToUnicode CMap stream
    let to_unicode_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;
    
    // Create a proper ToUnicode CMap for Unicode support
    // This maps CID values to Unicode code points (Identity mapping: CID = Unicode)
    // For Identity-H encoding, CID values are the same as Unicode code points
    // We use beginbfrange with array to map CID ranges to Unicode ranges
    // For full Identity mapping, we map <CID> to <CID> (CID = Unicode code point)
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
// Identity mapping: CID = Unicode code point
// For Identity-H encoding, CID values are directly interpreted as Unicode code points
// Use multiple smaller ranges for better compatibility with different PDF readers
// Map 0x0000-0x00FF: Basic Latin and Latin-1 Supplement
1 beginbfrange
<0000> <00FF> <0000>
endbfrange
// Map 0x0100-0x017F: Latin Extended-A (includes Polish characters: ą, ć, ę, ł, ń, ś, ź, ż)
1 beginbfrange
<0100> <017F> <0100>
endbfrange
// Map 0x0180-0x024F: Latin Extended-B
1 beginbfrange
<0180> <024F> <0180>
endbfrange
// Map 0x0250-0x02AF: IPA Extensions
1 beginbfrange
<0250> <02AF> <0250>
endbfrange
// Map 0x02B0-0x02FF: Spacing Modifier Letters
1 beginbfrange
<02B0> <02FF> <02B0>
endbfrange
// Map 0x0300-0x036F: Combining Diacritical Marks
1 beginbfrange
<0300> <036F> <0300>
endbfrange
// Map 0x0370-0x03FF: Greek and Coptic
1 beginbfrange
<0370> <03FF> <0370>
endbfrange
// Map 0x0400-0x04FF: Cyrillic
1 beginbfrange
<0400> <04FF> <0400>
endbfrange
// Map 0x0500-0x052F: Cyrillic Supplement
1 beginbfrange
<0500> <052F> <0500>
endbfrange
// Map remaining ranges for full Unicode support
// Map 0x0530-0x1FFF: Various scripts
1 beginbfrange
<0530> <1FFF> <0530>
endbfrange
// Map 0x2000-0x2EFF: Symbols and punctuation
1 beginbfrange
<2000> <2EFF> <2000>
endbfrange
// Map 0x2F00-0xFFFF: Remaining Unicode ranges
1 beginbfrange
<2F00> <FFFF> <2F00>
endbfrange
end"
    );
    
    // Create ToUnicode CMap stream - pdf-writer automatically finishes streams when dropped
    pdf.stream(to_unicode_id, cmap_content.as_bytes())
        .filter(Filter::FlateDecode);
    
    // Create FontDescriptor dictionary using pdf-writer's manual object creation
    // pdf-writer doesn't have direct FontDescriptor API, so we'll use insert() method
    // to manually create dictionary objects
    
    // First, let's try using pdf-writer's insert() method if available
    // If not, we'll need to use a different approach
    
    // Create FontDescriptor dictionary manually using pdf-writer's insert() or similar method
    // We'll create the dictionary content as a properly formatted PDF object
    // and insert it directly into the PDF structure
    
    // Method 1: Try using pdf-writer's insert() method (if available)
    // This would allow us to insert raw PDF objects directly
    
    // Method 2: Create dictionary objects using pdf-writer's Dict API (if available)
    // This would be the cleanest approach
    
    // Method 3: Use raw PDF object creation with proper formatting
    // We'll create the objects as properly formatted PDF dictionaries
    
    // For now, we'll use Method 3 - create properly formatted PDF dictionary objects
    // These will be inserted as indirect objects in the PDF
    
    // CRITICAL: pdf-writer doesn't have direct API for creating CIDFont/Type0 fonts
    // Creating dictionary objects as streams doesn't work - PDF readers can't parse them
    //
    // SOLUTION: We need to manually inject the PDF objects into the final PDF bytes
    // This requires modifying the PDF after pdf.finish() to insert the dictionary objects
    //
    // For now, we'll prepare the dictionary content and store it for later injection
    // The font file is embedded, but the font structure needs to be injected manually
    
    // Prepare dictionary objects as properly formatted PDF indirect objects
    // FontDescriptor with all required fields for better compatibility
    // Flags: 32 = Symbolic font (bit 5), but we also need bit 6 (Nonsymbolic) for Unicode
    // Actually, for Unicode fonts, Flags should be 4 (Nonsymbolic) or 32 (Symbolic but with Unicode)
    // Let's use 4 (Nonsymbolic) for better compatibility
    let font_descriptor_obj = format!(
        "{} 0 obj\n<<\n/Type /FontDescriptor\n/FontName /{}\n/Flags 4\n/FontBBox [{} {} {} {}]\n/ItalicAngle 0\n/Ascent {}\n/Descent {}\n/CapHeight {}\n/StemV 80\n/FontFile2 {} 0 R\n>>\nendobj\n",
        font_descriptor_id.get(),
        font_family.replace(' ', "#20"),
        pdf_bbox[0], pdf_bbox[1], pdf_bbox[2], pdf_bbox[3],
        pdf_ascender,
        pdf_descender,
        pdf_ascender,
        font_file_id.get()
    );
    
    // Build widths (/W) array from TTF advances for a practical Unicode range
    // We use CIDs equal to Unicode code points for Identity-H.
    // To avoid massive objects, limit to 0x0020..0x024F (Latin + Latin-Extended A/B used for PL).
    let mut widths: Vec<i32> = Vec::new();
    let mut start_cid: u16 = 0x0020;
    let end_cid: u16 = 0x024F;
    for cid in start_cid..=end_cid {
        let ch = char::from_u32(cid as u32).unwrap_or('\u{0020}');
        let gid = face.glyph_index(ch).unwrap_or(ttf_parser::GlyphId(0));
        let adv = face.glyph_hor_advance(gid).unwrap_or(face.units_per_em() / 2);
        let width_pdf = ((adv as f32) * scale).round() as i32;
        widths.push(width_pdf.max(0));
    }
    // Create /W entry: [start [w1 w2 ...]] for the contiguous range
    let mut w_array = String::new();
    w_array.push_str(&format!("{} [", start_cid));
    for (i, w) in widths.iter().enumerate() {
        if i > 0 {
            w_array.push(' ');
        }
        w_array.push_str(&w.to_string());
    }
    w_array.push(']');
    
    // CIDFont with metrics and descriptor
    let cid_font_obj = format!(
        "{} 0 obj\n<<\n/Type /Font\n/Subtype /CIDFontType2\n/BaseFont /{}\n/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>\n/FontDescriptor {} 0 R\n/DW 500\n/W [{}]\n>>\nendobj\n",
        cid_font_id.get(),
        font_family.replace(' ', "#20"),
        font_descriptor_id.get(),
        w_array
    );
    
    let type0_font_obj = format!(
        "{} 0 obj\n<<\n/Type /Font\n/Subtype /Type0\n/BaseFont /{}\n/Encoding /Identity-H\n/DescendantFonts [{} 0 R]\n/ToUnicode {} 0 R\n>>\nendobj\n",
        font_id.get(),
        font_family.replace(' ', "#20"),
        cid_font_id.get(),
        to_unicode_id.get()
    );
    
    // Store these objects for later injection into PDF bytes
    // They will be injected by inject_font_objects() after pdf.finish()
    font_objects.push((font_descriptor_id, font_descriptor_obj));
    font_objects.push((cid_font_id, cid_font_obj));
    font_objects.push((font_id, type0_font_obj));
    
    eprintln!("✅ TrueType font structure prepared for injection");
    eprintln!("   Font: {}, Font ID: {}", font_family, font_id.get());
    eprintln!("   FontDescriptor ID: {}, CIDFont ID: {}, Type0 ID: {}",
        font_descriptor_id.get(), cid_font_id.get(), font_id.get());
    eprintln!("   Objects stored for manual injection into PDF bytes");
    
    // Create font name (e.g., "F1", "F2", etc.)
    let font_name = format!("F{}", font_id.get());
    // Leak the string to make it 'static - this is safe because font names are small and we need them for the PDF lifetime
    let font_name_static = Box::leak(font_name.into_boxed_str());
    let font_name_bytes = font_name_static.as_bytes();
    
    eprintln!("✅ TrueType font embedding: Complete font structure created");
    eprintln!("   Font: {}", font_family);
    eprintln!("   Font ID: {}, Font File ID: {}, Descriptor ID: {}, CIDFont ID: {}, ToUnicode ID: {}", 
        font_id.get(), font_file_id.get(), font_descriptor_id.get(), cid_font_id.get(), to_unicode_id.get());
    
    Ok(Name(font_name_bytes))
}

/// Get font name from TTF file
pub fn get_font_name_from_ttf(font_data: &[u8]) -> PyResult<String> {
    let face = Face::parse(font_data, 0)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Invalid font file: {}", e)
        ))?;
    
    // Try to get font family name
    let family_name = face
        .names()
        .into_iter()
        .find(|name| name.name_id == 1) // Family ID = 1
        .and_then(|name| name.to_string())
        .unwrap_or_else(|| "Unknown".to_string());
    
    Ok(family_name)
}

