//! Font utilities for loading and registering TrueType fonts
//! 
//! This module provides lazy font loading - fonts are loaded on demand when
//! canvas_set_font() is called, not at renderer initialization.

use pdf_writer::types::{CidFontType, FontFlags, SystemInfo};
use pdf_writer::{Name, Pdf, Rect, Ref, Str};
use pyo3::prelude::*;
use std::collections::{BTreeMap, HashMap};
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use ttf_parser::Face;

/// Map Unicode code point to CID (Character ID) for Type0 fonts
pub type CidMap = HashMap<u32, u16>;

/// Font style variants
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum FontStyle {
    Regular,
    Bold,
    Italic,
    BoldItalic,
}

impl FontStyle {
    /// Parse font style from font name
    pub fn from_name(name: &str) -> Self {
        let lower = name.to_lowercase();
        let is_bold = lower.contains("bold") || lower.contains("-bd") || lower.ends_with("bd");
        let is_italic = lower.contains("italic") || lower.contains("oblique") 
            || lower.contains("-it") || lower.ends_with("it")
            || lower.contains("-i") && !lower.contains("-in");
        
        match (is_bold, is_italic) {
            (true, true) => FontStyle::BoldItalic,
            (true, false) => FontStyle::Bold,
            (false, true) => FontStyle::Italic,
            (false, false) => FontStyle::Regular,
        }
    }
}

/// Mapping of font family names to their file names on different platforms
struct FontFileMapping {
    /// Base font family name (lowercase, normalized)
    family: &'static str,
    /// Windows file names: [regular, bold, italic, bold_italic]
    windows: [&'static str; 4],
    /// Linux file names
    linux: [&'static str; 4],
    /// macOS file names
    macos: [&'static str; 4],
}

/// Common font mappings
static FONT_MAPPINGS: &[FontFileMapping] = &[
    FontFileMapping {
        family: "arial",
        windows: ["arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"],
        linux: ["Arial.ttf", "Arial-Bold.ttf", "Arial-Italic.ttf", "Arial-BoldItalic.ttf"],
        macos: ["Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial Bold Italic.ttf"],
    },
    FontFileMapping {
        family: "calibri",
        windows: ["calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"],
        linux: ["Calibri.ttf", "Calibri-Bold.ttf", "Calibri-Italic.ttf", "Calibri-BoldItalic.ttf"],
        macos: ["Calibri.ttf", "Calibri Bold.ttf", "Calibri Italic.ttf", "Calibri Bold Italic.ttf"],
    },
    FontFileMapping {
        family: "times new roman",
        windows: ["times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"],
        linux: ["Times-New-Roman.ttf", "Times-New-Roman-Bold.ttf", "Times-New-Roman-Italic.ttf", "Times-New-Roman-BoldItalic.ttf"],
        macos: ["Times New Roman.ttf", "Times New Roman Bold.ttf", "Times New Roman Italic.ttf", "Times New Roman Bold Italic.ttf"],
    },
    FontFileMapping {
        family: "segoe ui",
        windows: ["segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"],
        linux: ["SegoeUI.ttf", "SegoeUI-Bold.ttf", "SegoeUI-Italic.ttf", "SegoeUI-BoldItalic.ttf"],
        macos: ["Segoe UI.ttf", "Segoe UI Bold.ttf", "Segoe UI Italic.ttf", "Segoe UI Bold Italic.ttf"],
    },
    FontFileMapping {
        family: "tahoma",
        windows: ["tahoma.ttf", "tahomabd.ttf", "tahoma.ttf", "tahomabd.ttf"], // Tahoma has no italic
        linux: ["Tahoma.ttf", "Tahoma-Bold.ttf", "Tahoma.ttf", "Tahoma-Bold.ttf"],
        macos: ["Tahoma.ttf", "Tahoma Bold.ttf", "Tahoma.ttf", "Tahoma Bold.ttf"],
    },
    FontFileMapping {
        family: "verdana",
        windows: ["verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"],
        linux: ["Verdana.ttf", "Verdana-Bold.ttf", "Verdana-Italic.ttf", "Verdana-BoldItalic.ttf"],
        macos: ["Verdana.ttf", "Verdana Bold.ttf", "Verdana Italic.ttf", "Verdana Bold Italic.ttf"],
    },
    FontFileMapping {
        family: "georgia",
        windows: ["georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"],
        linux: ["Georgia.ttf", "Georgia-Bold.ttf", "Georgia-Italic.ttf", "Georgia-BoldItalic.ttf"],
        macos: ["Georgia.ttf", "Georgia Bold.ttf", "Georgia Italic.ttf", "Georgia Bold Italic.ttf"],
    },
    FontFileMapping {
        family: "courier new",
        windows: ["cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"],
        linux: ["Courier-New.ttf", "Courier-New-Bold.ttf", "Courier-New-Italic.ttf", "Courier-New-BoldItalic.ttf"],
        macos: ["Courier New.ttf", "Courier New Bold.ttf", "Courier New Italic.ttf", "Courier New Bold Italic.ttf"],
    },
    FontFileMapping {
        family: "dejavu sans",
        windows: ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"],
        linux: ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"],
        macos: ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"],
    },
    FontFileMapping {
        family: "liberation sans",
        windows: ["LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf"],
        linux: ["LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf"],
        macos: ["LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf"],
    },
    FontFileMapping {
        family: "helvetica",
        windows: ["arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"], // Helvetica → Arial on Windows
        linux: ["Helvetica.ttf", "Helvetica-Bold.ttf", "Helvetica-Oblique.ttf", "Helvetica-BoldOblique.ttf"],
        macos: ["Helvetica.ttc", "Helvetica.ttc", "Helvetica.ttc", "Helvetica.ttc"],
    },
];

/// Find bundled fonts directory from docquill Python package
/// This ensures consistency between Python (ReportLab) and Rust font metrics
fn find_bundled_fonts_dir() -> Option<PathBuf> {
    // Try to find docquill package fonts directory
    // The fonts are bundled at: site-packages/docquill/fonts/
    
    // Method 1: Use Python to find the package location
    if let Ok(output) = std::process::Command::new("python3")
        .args(["-c", "import docquill; import os; print(os.path.dirname(docquill.__file__))"])
        .output()
    {
        if output.status.success() {
            let package_dir = String::from_utf8_lossy(&output.stdout).trim().to_string();
            let fonts_dir = PathBuf::from(&package_dir).join("fonts");
            if fonts_dir.exists() {
                return Some(fonts_dir);
            }
        }
    }
    
    // Method 2: Try python (without 3 suffix, for Windows)
    if let Ok(output) = std::process::Command::new("python")
        .args(["-c", "import docquill; import os; print(os.path.dirname(docquill.__file__))"])
        .output()
    {
        if output.status.success() {
            let package_dir = String::from_utf8_lossy(&output.stdout).trim().to_string();
            let fonts_dir = PathBuf::from(&package_dir).join("fonts");
            if fonts_dir.exists() {
                return Some(fonts_dir);
            }
        }
    }
    
    // Method 3: Common site-packages locations
    let site_packages_patterns = [
        // Virtual environments
        ".venv/lib/python3.*/site-packages/docquill/fonts",
        "venv/lib/python3.*/site-packages/docquill/fonts",
        ".venv/Lib/site-packages/docquill/fonts",  // Windows venv
        "venv/Lib/site-packages/docquill/fonts",   // Windows venv
        // User install
        ".local/lib/python3.*/site-packages/docquill/fonts",
    ];
    
    if let Ok(home) = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE")) {
        for pattern in &site_packages_patterns {
            // Simple glob-like matching for python version
            for version in ["3.9", "3.10", "3.11", "3.12", "3.13"] {
                let path_str = pattern.replace("python3.*", &format!("python{}", version));
                let full_path = PathBuf::from(&home).join(&path_str);
                if full_path.exists() {
                    return Some(full_path);
                }
            }
        }
    }
    
    // Method 4: Check current working directory (development mode)
    if let Ok(cwd) = std::env::current_dir() {
        // Check packages/docquill_core/docquill/fonts/
        let dev_path = cwd.join("packages/docquill_core/docquill/fonts");
        if dev_path.exists() {
            return Some(dev_path);
        }
        
        // Check parent directories
        let mut dir = cwd.parent();
        for _ in 0..5 {
            if let Some(d) = dir {
                let dev_path = d.join("packages/docquill_core/docquill/fonts");
                if dev_path.exists() {
                    return Some(dev_path);
                }
                dir = d.parent();
            } else {
                break;
            }
        }
    }
    
    None
}

/// Get bundled font path for DejaVu Sans variants
/// These are the canonical fonts that match Python's ReportLab metrics
fn get_bundled_dejavu_font(style: FontStyle) -> Option<PathBuf> {
    let bundled_dir = find_bundled_fonts_dir()?;
    
    let filename = match style {
        FontStyle::Regular => "DejaVuSans.ttf",
        FontStyle::Bold => "DejaVuSans-Bold.ttf",
        FontStyle::Italic => "DejaVuSans-Oblique.ttf",
        FontStyle::BoldItalic => "DejaVuSans-BoldOblique.ttf",
    };
    
    let font_path = bundled_dir.join(filename);
    if font_path.exists() {
        Some(font_path)
    } else {
        None
    }
}

/// Get system fonts directories for the current platform
fn get_system_font_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    
    #[cfg(target_os = "windows")]
    {
        // Windows fonts directory
        if let Ok(windir) = std::env::var("WINDIR") {
            dirs.push(PathBuf::from(format!("{}\\Fonts", windir)));
        }
        dirs.push(PathBuf::from("C:\\Windows\\Fonts"));
        
        // User fonts
        if let Ok(localappdata) = std::env::var("LOCALAPPDATA") {
            dirs.push(PathBuf::from(format!("{}\\Microsoft\\Windows\\Fonts", localappdata)));
        }
    }
    
    #[cfg(target_os = "macos")]
    {
        dirs.push(PathBuf::from("/System/Library/Fonts"));
        dirs.push(PathBuf::from("/System/Library/Fonts/Supplemental"));
        dirs.push(PathBuf::from("/Library/Fonts"));
        if let Ok(home) = std::env::var("HOME") {
            dirs.push(PathBuf::from(format!("{}/Library/Fonts", home)));
        }
    }
    
    #[cfg(target_os = "linux")]
    {
        dirs.push(PathBuf::from("/usr/share/fonts/truetype"));
        dirs.push(PathBuf::from("/usr/share/fonts/TTF"));
        dirs.push(PathBuf::from("/usr/share/fonts"));
        dirs.push(PathBuf::from("/usr/local/share/fonts"));
        if let Ok(home) = std::env::var("HOME") {
            dirs.push(PathBuf::from(format!("{}/.fonts", home)));
            dirs.push(PathBuf::from(format!("{}/.local/share/fonts", home)));
        }
        // Common subdirectories
        dirs.push(PathBuf::from("/usr/share/fonts/truetype/dejavu"));
        dirs.push(PathBuf::from("/usr/share/fonts/truetype/liberation"));
        dirs.push(PathBuf::from("/usr/share/fonts/truetype/msttcorefonts"));
        dirs.push(PathBuf::from("/usr/share/fonts/dejavu"));
        dirs.push(PathBuf::from("/usr/share/fonts/liberation-sans"));
    }
    
    dirs
}

/// Normalize font family name for lookup
fn normalize_font_name(name: &str) -> String {
    name.to_lowercase()
        .replace("-", " ")
        .replace("_", " ")
        .trim()
        .to_string()
}

/// Find a font file in system directories
/// 
/// Args:
///     font_name: Font family name (e.g., "Calibri", "Arial", "Times New Roman")
///     style: Font style (Regular, Bold, Italic, BoldItalic)
/// 
/// Returns:
///     Path to font file if found, None otherwise
pub fn find_system_font(font_name: &str, style: FontStyle) -> Option<PathBuf> {
    let normalized = normalize_font_name(font_name);
    let font_dirs = get_system_font_dirs();
    
    // Find mapping for this font family
    let style_index = match style {
        FontStyle::Regular => 0,
        FontStyle::Bold => 1,
        FontStyle::Italic => 2,
        FontStyle::BoldItalic => 3,
    };
    
    // Try exact match first
    for mapping in FONT_MAPPINGS {
        if normalized == mapping.family || normalized.starts_with(mapping.family) {
            #[cfg(target_os = "windows")]
            let filename = mapping.windows[style_index];
            #[cfg(target_os = "macos")]
            let filename = mapping.macos[style_index];
            #[cfg(target_os = "linux")]
            let filename = mapping.linux[style_index];
            #[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
            let filename = mapping.linux[style_index];
            
            // Search in font directories
            for dir in &font_dirs {
                let path = dir.join(filename);
                if path.exists() {
                    return Some(path);
                }
                
                // Also try subdirectories (Linux often has fonts in subdirs)
                if let Ok(entries) = std::fs::read_dir(dir) {
                    for entry in entries.flatten() {
                        if entry.path().is_dir() {
                            let subpath = entry.path().join(filename);
                            if subpath.exists() {
                                return Some(subpath);
                            }
                        }
                    }
                }
            }
        }
    }
    
    // Try direct filename match (for fonts not in mapping)
    let possible_filenames = generate_font_filenames(font_name, style);
    for filename in &possible_filenames {
        for dir in &font_dirs {
            let path = dir.join(filename);
            if path.exists() {
                return Some(path);
            }
            
            // Check subdirectories
            if let Ok(entries) = std::fs::read_dir(dir) {
                for entry in entries.flatten() {
                    if entry.path().is_dir() {
                        let subpath = entry.path().join(filename);
                        if subpath.exists() {
                            return Some(subpath);
                        }
                    }
                }
            }
        }
    }
    
    None
}

/// Generate possible font filenames for a given font name and style
fn generate_font_filenames(font_name: &str, style: FontStyle) -> Vec<String> {
    let base = font_name.replace(" ", "");
    let base_with_dash = font_name.replace(" ", "-");
    
    let suffix = match style {
        FontStyle::Regular => vec!["", "-Regular"],
        FontStyle::Bold => vec!["-Bold", "bd", "-Bd", "b"],
        FontStyle::Italic => vec!["-Italic", "-Oblique", "i", "-It", "it"],
        FontStyle::BoldItalic => vec!["-BoldItalic", "-BoldOblique", "bi", "z", "-BI"],
    };
    
    let mut filenames = Vec::new();
    for s in &suffix {
        filenames.push(format!("{}{}.ttf", base, s));
        filenames.push(format!("{}{}.TTF", base, s));
        filenames.push(format!("{}{}.otf", base, s));
        filenames.push(format!("{}{}.OTF", base, s));
        filenames.push(format!("{}{}.ttf", base_with_dash, s));
        filenames.push(format!("{}{}.otf", base_with_dash, s));
    }
    
    filenames
}

/// Get fallback font for when requested font is not found
/// PRIORITY: Bundled DejaVu Sans first (ensures consistency with Python/ReportLab)
/// then system fonts as fallback
pub fn get_fallback_font(style: FontStyle) -> Option<PathBuf> {
    // HIGHEST PRIORITY: Bundled DejaVu Sans from docquill package
    // This ensures font metrics match Python's ReportLab calculations
    if let Some(path) = get_bundled_dejavu_font(style) {
        return Some(path);
    }
    
    // Fallback: Try system fonts
    let fallback_families = [
        "DejaVu Sans",  // Same font family as bundled
        "Arial",        // Available on Windows, often on Linux/macOS
        "Liberation Sans", // Common on Linux
        "Helvetica",    // macOS
        "Segoe UI",     // Windows
    ];
    
    for family in &fallback_families {
        if let Some(path) = find_system_font(family, style) {
            return Some(path);
        }
    }
    
    // Last resort: try to find ANY .ttf file in system fonts
    let font_dirs = get_system_font_dirs();
    for dir in &font_dirs {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().map(|e| e == "ttf" || e == "TTF").unwrap_or(false) {
                    return Some(path);
                }
            }
        }
    }
    
    None
}

/// Load TTF/OTF font from file path
pub fn load_font_file(path: &Path) -> PyResult<Vec<u8>> {
    if !path.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>(
            format!("Font file not found: {}", path.display()),
        ));
    }

    let mut file = File::open(path).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
            "Failed to open font file {}: {}",
            path.display(), e
        ))
    })?;

    let mut font_data = Vec::new();
    file.read_to_end(&mut font_data).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
            "Failed to read font file {}: {}",
            path.display(), e
        ))
    })?;

    // Validate font using ttf-parser
    Face::parse(&font_data, 0).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Invalid font file {}: {}",
            path.display(), e
        ))
    })?;

    Ok(font_data)
}

/// Load font file from string path (for backward compatibility)
pub fn load_font_file_str(path: &str) -> PyResult<Vec<u8>> {
    load_font_file(Path::new(path))
}

/// Add TrueType font to PDF as Type0 font (CIDFontType2)
/// Returns the font resource name and Unicode->CID mapping
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
        .find(|name| name.name_id == 1)
        .and_then(|name| name.to_string())
        .unwrap_or_else(|| format!("Font{}", font_id.get()));

    // Build Unicode -> CID/GID mapping from font's cmap table
    let mut cid_map = HashMap::new();
    let mut cid_to_gid_map = Vec::new();
    let mut cid_widths: BTreeMap<u16, i32> = BTreeMap::new();

    let default_width = 500_i32;

    // Iterate through BMP Unicode range to build mapping
    for code_point in 0x0000u32..=0xFFFFu32 {
        if let Some(ch) = char::from_u32(code_point) {
            if let Some(glyph_id) = face.glyph_index(ch) {
                let gid = glyph_id.0 as u16;
                let cid = gid;

                cid_map.entry(code_point).or_insert(cid);

                if cid_to_gid_map.len() <= cid as usize {
                    cid_to_gid_map.resize((cid + 1) as usize, 0u16);
                }
                cid_to_gid_map[cid as usize] = gid;

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

    // Create CIDToGIDMap stream
    let cid_to_gid_map_id = Ref::new(*next_ref_id);
    *next_ref_id += 1;

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

    // Prepare base font name
    let base_font_name = font_family.replace(' ', "#20");
    let base_font_boxed = base_font_name.clone().into_boxed_str();
    let base_font_static = Box::leak(base_font_boxed);
    let base_font_name = Name(base_font_static.as_bytes());

    // Build FontDescriptor
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

// Keep old functions for backward compatibility but mark as deprecated
#[deprecated(note = "Use find_system_font instead")]
pub fn find_dejavu_sans() -> Option<String> {
    find_system_font("DejaVu Sans", FontStyle::Regular)
        .or_else(|| get_fallback_font(FontStyle::Regular))
        .map(|p| p.to_string_lossy().to_string())
}

#[deprecated(note = "Use find_system_font instead")]
pub fn find_dejavu_sans_bold() -> Option<String> {
    find_system_font("DejaVu Sans", FontStyle::Bold)
        .or_else(|| get_fallback_font(FontStyle::Bold))
        .map(|p| p.to_string_lossy().to_string())
}

#[deprecated(note = "Use find_system_font instead")]
pub fn find_dejavu_sans_italic() -> Option<String> {
    find_system_font("DejaVu Sans", FontStyle::Italic)
        .or_else(|| get_fallback_font(FontStyle::Italic))
        .map(|p| p.to_string_lossy().to_string())
}

#[deprecated(note = "Use find_system_font instead")]
pub fn find_dejavu_sans_bold_italic() -> Option<String> {
    find_system_font("DejaVu Sans", FontStyle::BoldItalic)
        .or_else(|| get_fallback_font(FontStyle::BoldItalic))
        .map(|p| p.to_string_lossy().to_string())
}
