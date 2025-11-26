//! EMF format parser and converter

use crate::svg_writer::SvgWriter;
use crate::emfplus::EmfPlusParser;
use crate::emf_records;
use std::io::Cursor;

/// Check if data is EMF format
pub fn is_emf_format(data: &[u8]) -> bool {
    data.len() >= 4 
        && data[0] == 0x01 
        && data[1] == 0x00 
        && data[2] == 0x00 
        && data[3] == 0x00
}

/// Convert EMF data to SVG string
pub fn convert_emf_to_svg(data: &[u8]) -> Result<String, Box<dyn std::error::Error>> {
    if !is_emf_format(data) {
        return Err("Invalid EMF format".into());
    }

    // Parse EMF header to get dimensions, frame size (physical size), header size, and initial view transform
    let (_bounds_width, _bounds_height, frame_width_mm, frame_height_mm, header_size, initial_view_transform) = parse_emf_header(data)?;
    
    // Create temporary SVG writer to parse records and get final view transform
    let mut temp_svg = SvgWriter::new(100, 100);
    let final_view_transform = match parse_emf_records(data, header_size, &mut temp_svg, initial_view_transform) {
        Ok(transform) => transform,
        Err(_) => initial_view_transform,
    };
    
    // Calculate SVG dimensions using rclFrame (physical size in mm) as primary source
    // This is the default size that applications like Word, Excel, PowerPoint use
    // Convert from millimeters to pixels at 96 DPI (standard web DPI)
    // 1 mm = 3.779527559 pixels at 96 DPI
    const MM_TO_PX: f64 = 3.779527559;
    let frame_width_px = frame_width_mm * MM_TO_PX;
    let frame_height_px = frame_height_mm * MM_TO_PX;
    
    // Also calculate dimensions from viewport extents (logical units) for content scaling
    let svg_width_logical = final_view_transform.viewport_ext_x.max(1) as f64;
    let svg_height_logical = final_view_transform.viewport_ext_y.max(1) as f64;
    
    // Calculate maximum possible coordinate based on window extents and viewport scale
    let scale_x = if final_view_transform.window_ext_x != 0 {
        final_view_transform.viewport_ext_x as f64 / final_view_transform.window_ext_x as f64
    } else {
        1.0
    };
    let scale_y = if final_view_transform.window_ext_y != 0 {
        final_view_transform.viewport_ext_y as f64 / final_view_transform.window_ext_y as f64
    } else {
        1.0
    };
    
    // Maximum possible coordinates after transformation (assume window bounds cover all content)
    let max_possible_x = (final_view_transform.window_ext_x as f64 * scale_x).max(svg_width_logical);
    let max_possible_y = (final_view_transform.window_ext_y as f64 * scale_y).max(svg_height_logical);
    
    eprintln!("EMF Header - rclFrame (physical size): {:.2}mm x {:.2}mm ({:.2}px x {:.2}px)", 
              frame_width_mm, frame_height_mm, frame_width_px, frame_height_px);
    eprintln!("EMF Header - rclBounds (logical units): {:.2} x {:.2}", _bounds_width, _bounds_height);
    eprintln!("Final viewport extents: ({}, {})", final_view_transform.viewport_ext_x, final_view_transform.viewport_ext_y);
    eprintln!("Final window extents: ({}, {})", final_view_transform.window_ext_x, final_view_transform.window_ext_y);
    eprintln!("Scale: ({}, {})", scale_x, scale_y);
    
    // Use frame size (physical size) as the SVG dimensions if valid
    // This ensures the SVG has the correct default size as intended by the EMF file
    // If frame size is invalid or zero, fall back to calculated logical dimensions
    let svg_width = if frame_width_px > 0.0 && frame_width_px.is_finite() {
        frame_width_px
    } else {
        max_possible_x.max(2000.0)
    };
    
    let svg_height = if frame_height_px > 0.0 && frame_height_px.is_finite() {
        frame_height_px
    } else {
        max_possible_y.max(2000.0)
    };
    
    eprintln!("SVG dimensions (using rclFrame): {:.2}x{:.2}", svg_width, svg_height);
    
    // Normalize dimensions
    let width = normalize_dimension(svg_width);
    let height = normalize_dimension(svg_height);

    // Create SVG writer with correct dimensions (using rclFrame from EMF header)
    // Note: EMF+ uses the same EMF header (rclFrame/rclBounds) for size information,
    // so it doesn't need its own size handling - it uses the SVG writer created here
    let mut svg = SvgWriter::new(width, height);
    
    // Try to parse EMF records
    let mut rendered_gdi = false;
    
    // Parse EMF GDI records (basic implementation) - reset state with final transform
    match parse_emf_records(data, header_size, &mut svg, initial_view_transform) {
        Ok(_) => rendered_gdi = true,
        Err(e) => {
            eprintln!("EMF GDI parsing failed: {}", e);
        }
    }

    // Parse EMF+ records
    // EMF+ is an extension of EMF that adds advanced graphics features but uses the same
    // header structure. The SVG writer already has the correct size from rclFrame above.
    let mut emfplus_parser = EmfPlusParser::new(data, &mut svg);
    emfplus_parser.parse();

    if !rendered_gdi && !emfplus_parser.has_detected_records() {
        eprintln!("Warning: EMF rendering failed and no EMF+ records detected; output may be empty.");
    }

    Ok(svg.finish())
}

/// Parse EMF header to extract dimensions, header size, and initial view transform
/// Returns: (bounds_width, bounds_height, frame_width_mm, frame_height_mm, header_size, view_transform)
/// frame_width_mm and frame_height_mm are in millimeters (converted from HIMETRIC 0.01mm units)
fn parse_emf_header(data: &[u8]) -> Result<(f64, f64, f64, f64, u32, ViewTransform), Box<dyn std::error::Error>> {
    if data.len() < 40 {
        return Err("EMF header too small".into());
    }

    use byteorder::{LittleEndian, ReadBytesExt};
    let mut cursor = Cursor::new(data);
    
    // Read record type (should be 1 for EMR_HEADER)
    let _record_type = cursor.read_u32::<LittleEndian>()?;
    
    // Read record size - this tells us the actual header size
    let header_size = cursor.read_u32::<LittleEndian>()?;
    
    // Read bounds (RECTL structure: 4 i32 values) - in logical units
    let left = cursor.read_i32::<LittleEndian>()?;
    let top = cursor.read_i32::<LittleEndian>()?;
    let right = cursor.read_i32::<LittleEndian>()?;
    let bottom = cursor.read_i32::<LittleEndian>()?;
    
    let width = (right - left) as f64;
    let height = (bottom - top) as f64;
    
    // Read frame (RECTL structure: 4 i32 values) - in .01mm units (HIMETRIC)
    // This is the physical size that applications like Word use to determine image size
    let frame_left = cursor.read_i32::<LittleEndian>()?;
    let frame_top = cursor.read_i32::<LittleEndian>()?;
    let frame_right = cursor.read_i32::<LittleEndian>()?;
    let frame_bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Convert from HIMETRIC (0.01mm) to millimeters
    let frame_width_mm = ((frame_right - frame_left) as f64) / 100.0;
    let frame_height_mm = ((frame_bottom - frame_top) as f64) / 100.0;
    
    // Read signature (should be 0x464D4520 "EMF ")
    let _signature = cursor.read_u32::<LittleEndian>()?;
    
    // Read version (should be 0x00010000)
    let _version = cursor.read_u32::<LittleEndian>()?;
    
    // Read size of EMF metafile in bytes
    let _bytes = cursor.read_u32::<LittleEndian>()?;
    
    // Read number of records
    let _records = cursor.read_u32::<LittleEndian>()?;
    
    // Read number of handles
    let _handles = cursor.read_u16::<LittleEndian>()?;
    
    // Reserved (2 bytes)
    let _reserved = cursor.read_u16::<LittleEndian>()?;
    
    // Read description strings length and offset (skip for now)
    let _description_length = cursor.read_u32::<LittleEndian>()?;
    let _description_offset = cursor.read_u32::<LittleEndian>()?;
    
    // Read pixel dimensions
    let _pixels_x = cursor.read_u32::<LittleEndian>()?;
    let _pixels_y = cursor.read_u32::<LittleEndian>()?;
    
    // Read millimeter dimensions
    let _millimeters_x = cursor.read_u32::<LittleEndian>()?;
    let _millimeters_y = cursor.read_u32::<LittleEndian>()?;
    
    // Initialize view transform from header
    // Default: viewport extents match frame dimensions, window extents match bounds
    let view_transform = ViewTransform {
        window_org_x: 0,
        window_org_y: 0,
        window_ext_x: (right - left),
        window_ext_y: (bottom - top),
        viewport_org_x: 0,
        viewport_org_y: 0,
        viewport_ext_x: (right - left),
        viewport_ext_y: (bottom - top),
    };
    
    Ok((width, height, frame_width_mm, frame_height_mm, header_size, view_transform))
}

/// Current path being built
struct CurrentPath {
    commands: Vec<String>,
    is_active: bool,
}

impl CurrentPath {
    fn new() -> Self {
        Self {
            commands: Vec::new(),
            is_active: false,
        }
    }
    
    fn begin(&mut self) {
        self.commands.clear();
        self.is_active = true;
    }
    
    fn end(&mut self) -> String {
        let path = self.commands.join(" ");
        self.commands.clear();
        self.is_active = false;
        path
    }
    
    fn moveto(&mut self, x: f64, y: f64, transform: &ViewTransform) {
        let (tx, ty) = transform.transform(x, y);
        self.commands.push(format!("M {} {}", tx, ty));
    }
    
    fn lineto(&mut self, x: f64, y: f64, transform: &ViewTransform) {
        let (tx, ty) = transform.transform(x, y);
        self.commands.push(format!("L {} {}", tx, ty));
    }
    
    fn bezier_to(&mut self, cx1: f64, cy1: f64, cx2: f64, cy2: f64, ex: f64, ey: f64, transform: &ViewTransform) {
        let (tcx1, tcy1) = transform.transform(cx1, cy1);
        let (tcx2, tcy2) = transform.transform(cx2, cy2);
        let (tex, tey) = transform.transform(ex, ey);
        self.commands.push(format!("C {} {} {} {} {} {}", tcx1, tcy1, tcx2, tcy2, tex, tey));
    }
    
    fn close(&mut self) {
        self.commands.push("Z".to_string());
    }
}

/// Font information
#[derive(Clone)]
struct FontInfo {
    face_name: String,
    height: i32,  // Font height in logical units
    weight: u32,  // Font weight (400 = normal, 700 = bold)
    italic: bool,
    underline: bool,
    strikeout: bool,
}

/// Window and viewport transformation
#[derive(Clone, Copy)]
struct ViewTransform {
    window_org_x: i32,
    window_org_y: i32,
    window_ext_x: i32,
    window_ext_y: i32,
    viewport_org_x: i32,
    viewport_org_y: i32,
    viewport_ext_x: i32,
    viewport_ext_y: i32,
}

impl ViewTransform {
    fn new() -> Self {
        Self {
            window_org_x: 0,
            window_org_y: 0,
            window_ext_x: 1,
            window_ext_y: 1,
            viewport_org_x: 0,
            viewport_org_y: 0,
            viewport_ext_x: 1,
            viewport_ext_y: 1,
        }
    }
    
    /// Transform logical coordinates to device coordinates
    fn transform(&self, x: f64, y: f64) -> (f64, f64) {
        // Calculate scale factors
        let scale_x = if self.window_ext_x != 0 {
            self.viewport_ext_x as f64 / self.window_ext_x as f64
        } else {
            1.0
        };
        
        let scale_y = if self.window_ext_y != 0 {
            self.viewport_ext_y as f64 / self.window_ext_y as f64
        } else {
            1.0
        };
        
        // Transform coordinates
        let device_x = (x - self.window_org_x as f64) * scale_x + self.viewport_org_x as f64;
        let device_y = (y - self.window_org_y as f64) * scale_y + self.viewport_org_y as f64;
        
        // Debug first few transforms
        static mut DEBUG_COUNT: u32 = 0;
        unsafe {
            if DEBUG_COUNT < 3 {
                eprintln!("Transform: logical=({}, {}) -> device=({}, {}), scale=({}, {}), window_ext=({}, {}), viewport_ext=({}, {})", 
                    x, y, device_x, device_y, scale_x, scale_y, 
                    self.window_ext_x, self.window_ext_y, 
                    self.viewport_ext_x, self.viewport_ext_y);
                DEBUG_COUNT += 1;
            }
        }
        
        (device_x, device_y)
    }
}

/// Graphics state for EMF parsing
struct GraphicsState {
    current_pen_color: u32,      // ARGB
    current_brush_color: u32,    // ARGB
    current_text_color: u32,     // ARGB
    current_bk_color: u32,       // ARGB
    current_font: Option<FontInfo>,
    pen_table: Vec<Option<PenInfo>>,
    brush_table: Vec<Option<BrushInfo>>,
    font_table: Vec<Option<FontInfo>>,
    current_path: CurrentPath,
    view_transform: ViewTransform,
}

impl Default for GraphicsState {
    fn default() -> Self {
        Self {
            current_pen_color: 0xFF000000,      // Black
            current_brush_color: 0xFFFFFFFF,  // White
            current_text_color: 0xFF000000,    // Black
            current_bk_color: 0xFFFFFFFF,     // White
            current_font: Some(FontInfo {
                face_name: "Arial".to_string(),
                height: 12,
                weight: 400,
                italic: false,
                underline: false,
                strikeout: false,
            }),
            pen_table: vec![None; 256],
            brush_table: vec![None; 256],
            font_table: vec![None; 256],
            current_path: CurrentPath::new(),
            view_transform: ViewTransform::new(),
        }
    }
}

/// Pen information
#[derive(Clone)]
struct PenInfo {
    color: u32,  // ARGB
    width: u32,  // Width in logical units
    style: u32,  // Pen style
}

/// Brush information
#[derive(Clone)]
struct BrushInfo {
    color: u32,  // ARGB
    style: u32,  // Brush style
}

/// Parse EMF records (basic implementation)
fn parse_emf_records(data: &[u8], header_size: u32, svg: &mut SvgWriter, initial_view_transform: ViewTransform) -> Result<ViewTransform, Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    let mut cursor = Cursor::new(data);
    
    // Skip header (use actual header size from EMF header)
    cursor.set_position(header_size as u64);
    
    let mut state = GraphicsState::default();
    state.view_transform = initial_view_transform;
    let mut record_count = 0;
    
    // Parse records
    while cursor.position() < data.len() as u64 {
        if cursor.position() + 8 > data.len() as u64 {
            break;
        }
        
        let record_type = cursor.read_u32::<LittleEndian>()?;
        let record_size = cursor.read_u32::<LittleEndian>()?;
        
        if record_size < 8 {
            break;
        }
        
        let data_size = record_size - 8;
        if cursor.position() + data_size as u64 > data.len() as u64 {
            break;
        }
        
        let record_start = cursor.position() as usize;
        let record_end = record_start + data_size as usize;
        
        // Handle EMR_COMMENT (type 70) for EMF+ records
        if record_type == emf_records::EMR_GDICOMMENT {
            // EMF+ records are handled separately
            cursor.set_position(record_end as u64);
            continue;
        }
        
        // Handle EOF
        if record_type == emf_records::EMR_EOF {
            break;
        }
        
        record_count += 1;
        
        // Debug: log record types (first 20 records)
        if record_count <= 20 {
            eprintln!("Record {}: type={} ({}) size={}", 
                     record_count, 
                     record_type,
                     emf_records::get_record_type_name(record_type),
                     record_size);
        }
        
        // Parse record based on type
        match record_type {
            emf_records::EMR_SETWINDOWORGEX => {
                if data_size >= 8 {
                    state.view_transform.window_org_x = cursor.read_i32::<LittleEndian>()?;
                    state.view_transform.window_org_y = cursor.read_i32::<LittleEndian>()?;
                    eprintln!("SETWINDOWORGEX: ({}, {})", state.view_transform.window_org_x, state.view_transform.window_org_y);
                }
            }
            emf_records::EMR_SETWINDOWEXTEX => {
                if data_size >= 8 {
                    state.view_transform.window_ext_x = cursor.read_i32::<LittleEndian>()?;
                    state.view_transform.window_ext_y = cursor.read_i32::<LittleEndian>()?;
                    eprintln!("SETWINDOWEXTEX: ({}, {})", state.view_transform.window_ext_x, state.view_transform.window_ext_y);
                }
            }
            emf_records::EMR_SETVIEWPORTORGEX => {
                if data_size >= 8 {
                    state.view_transform.viewport_org_x = cursor.read_i32::<LittleEndian>()?;
                    state.view_transform.viewport_org_y = cursor.read_i32::<LittleEndian>()?;
                    eprintln!("SETVIEWPORTORGEX: ({}, {})", state.view_transform.viewport_org_x, state.view_transform.viewport_org_y);
                }
            }
            emf_records::EMR_SETVIEWPORTEXTEX => {
                if data_size >= 8 {
                    state.view_transform.viewport_ext_x = cursor.read_i32::<LittleEndian>()?;
                    state.view_transform.viewport_ext_y = cursor.read_i32::<LittleEndian>()?;
                    eprintln!("SETVIEWPORTEXTEX: ({}, {})", state.view_transform.viewport_ext_x, state.view_transform.viewport_ext_y);
                }
            }
            emf_records::EMR_SETTEXTCOLOR => {
                if data_size >= 4 {
                    state.current_text_color = cursor.read_u32::<LittleEndian>()?;
                }
            }
            emf_records::EMR_SETBKCOLOR => {
                if data_size >= 4 {
                    state.current_bk_color = cursor.read_u32::<LittleEndian>()?;
                }
            }
            emf_records::EMR_CREATEPEN => {
                handle_createpen(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_CREATEBRUSHINDIRECT => {
                handle_createbrushindirect(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_SELECTOBJECT => {
                handle_selectobject(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_SELECTPALETTE => {
                // Palette selection - skip for now
            }
            emf_records::EMR_DELETEOBJECT => {
                handle_deleteobject(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_RECTANGLE => {
                handle_rectangle(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_ELLIPSE => {
                handle_ellipse(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYLINE => {
                handle_polyline(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYGON => {
                handle_polygon(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYLINE16 => {
                handle_polyline16(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYGON16 => {
                handle_polygon16(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYPOLYLINE => {
                handle_polypolyline(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYPOLYGON => {
                handle_polypolygon(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYPOLYLINE16 => {
                handle_polypolyline16(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYPOLYGON16 => {
                handle_polypolygon16(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_BEGINPATH => {
                state.current_path.begin();
            }
            emf_records::EMR_ENDPATH => {
                // Path ended - don't render yet, wait for FILLPATH or STROKEPATH
            }
            emf_records::EMR_CLOSEFIGURE => {
                state.current_path.close();
            }
            emf_records::EMR_MOVETOEX => {
                handle_movetoex(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_LINETO => {
                handle_lineto(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_POLYBEZIERTO => {
                handle_polybezierto(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_POLYBEZIERTO16 => {
                handle_polybezierto16(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_FILLPATH => {
                handle_fillpath(&mut cursor, svg, &mut state, data_size)?;
            }
            emf_records::EMR_STROKEPATH => {
                handle_strokepath(&mut cursor, svg, &mut state, data_size)?;
            }
            emf_records::EMR_STROKEANDFILLPATH => {
                handle_strokeandfillpath(&mut cursor, svg, &mut state, data_size)?;
            }
            emf_records::EMR_EXTCREATEFONTINDIRECTW => {
                handle_extcreatefontindirectw(&mut cursor, &mut state, data_size)?;
            }
            emf_records::EMR_EXTTEXTOUTA => {
                handle_exttextouta(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_EXTTEXTOUTW => {
                handle_exttextoutw(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYTEXTOUTA => {
                handle_polytextouta(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_POLYTEXTOUTW => {
                handle_polytextoutw(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_BITBLT => {
                handle_bitblt(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_STRETCHBLT => {
                handle_stretchblt(&mut cursor, svg, &state, data_size)?;
            }
            emf_records::EMR_STRETCHDIBITS => {
                handle_stretchdibits(&mut cursor, svg, &state, data_size)?;
            }
            _ => {
                // Unknown or unsupported record type - skip
            }
        }
        
        // Ensure cursor is at the end of the record
        cursor.set_position(record_end as u64);
    }
    
    if record_count > 0 {
        eprintln!("Parsed {} EMF records", record_count);
    }
    
    Ok(state.view_transform)
}

/// Handle EMR_RECTANGLE record
fn handle_rectangle(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    _data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if cursor.position() as usize + 16 > cursor.get_ref().len() {
        return Ok(());
    }
    
    let left = cursor.read_i32::<LittleEndian>()? as f64;
    let top = cursor.read_i32::<LittleEndian>()? as f64;
    let right = cursor.read_i32::<LittleEndian>()? as f64;
    let bottom = cursor.read_i32::<LittleEndian>()? as f64;
    
    // Transform coordinates
    let (x1, y1) = state.view_transform.transform(left, top);
    let (x2, y2) = state.view_transform.transform(right, bottom);
    
    let x = x1.min(x2);
    let y = y1.min(y2);
    let width = (x2 - x1).abs();
    let height = (y2 - y1).abs();
    
    let color = argb_to_svg_color(state.current_brush_color);
    svg.add_rect(x, y, width, height, Some(&color), None);
    
    Ok(())
}

/// Handle EMR_ELLIPSE record
fn handle_ellipse(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    _data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if cursor.position() as usize + 16 > cursor.get_ref().len() {
        return Ok(());
    }
    
    let left = cursor.read_i32::<LittleEndian>()? as f64;
    let top = cursor.read_i32::<LittleEndian>()? as f64;
    let right = cursor.read_i32::<LittleEndian>()? as f64;
    let bottom = cursor.read_i32::<LittleEndian>()? as f64;
    
    // Transform coordinates
    let (x1, y1) = state.view_transform.transform(left, top);
    let (x2, y2) = state.view_transform.transform(right, bottom);
    
    let x = x1.min(x2);
    let y = y1.min(y2);
    let width = (x2 - x1).abs();
    let height = (y2 - y1).abs();
    
    // Create ellipse path
    let cx = x + width / 2.0;
    let cy = y + height / 2.0;
    let rx = width / 2.0;
    let ry = height / 2.0;
    
    let path = format!("M {} {} m -{},0 a {},{} 0 1,0 {},0 a {},{} 0 1,0 -{},0", 
                       cx, cy, rx, rx, ry, rx * 2.0, rx, ry, rx * 2.0);
    
    let color = argb_to_svg_color(state.current_brush_color);
    svg.add_path(&path, Some(&color), None);
    
    Ok(())
}

/// Handle EMR_POLYLINE record
fn handle_polyline(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 8 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read point count
    let point_count = cursor.read_u32::<LittleEndian>()?;
    
    if point_count == 0 || point_count > 10000 {
        return Ok(());
    }
    
    // Read points
    let mut path = String::new();
    for i in 0..point_count {
        if cursor.position() as usize + 8 > cursor.get_ref().len() {
            break;
        }
        let x = cursor.read_i32::<LittleEndian>()? as f64;
        let y = cursor.read_i32::<LittleEndian>()? as f64;
        
        // Transform coordinates
        let (tx, ty) = state.view_transform.transform(x, y);
        
        if i == 0 {
            path.push_str(&format!("M {} {}", tx, ty));
        } else {
            path.push_str(&format!(" L {} {}", tx, ty));
        }
    }
    
    let color = argb_to_svg_color(state.current_pen_color);
    svg.add_path(&path, None, Some(&color));
    
    Ok(())
}

/// Handle EMR_POLYGON record
fn handle_polygon(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 8 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read point count
    let point_count = cursor.read_u32::<LittleEndian>()?;
    
    if point_count == 0 || point_count > 10000 {
        return Ok(());
    }
    
    // Read points
    let mut path = String::new();
    for i in 0..point_count {
        if cursor.position() as usize + 8 > cursor.get_ref().len() {
            break;
        }
        let x = cursor.read_i32::<LittleEndian>()? as f64;
        let y = cursor.read_i32::<LittleEndian>()? as f64;
        
        // Transform coordinates
        let (tx, ty) = state.view_transform.transform(x, y);
        
        if i == 0 {
            path.push_str(&format!("M {} {}", tx, ty));
        } else {
            path.push_str(&format!(" L {} {}", tx, ty));
        }
    }
    path.push_str(" Z");
    
    let color = argb_to_svg_color(state.current_brush_color);
    svg.add_path(&path, Some(&color), None);
    
    Ok(())
}

/// Handle EMR_POLYLINE16 record
fn handle_polyline16(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 8 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read point count
    let point_count = cursor.read_u32::<LittleEndian>()?;
    
    if point_count == 0 || point_count > 10000 {
        return Ok(());
    }
    
    // Read points (16-bit coordinates)
    let mut path = String::new();
    for i in 0..point_count {
        if cursor.position() as usize + 4 > cursor.get_ref().len() {
            break;
        }
        let x = cursor.read_i16::<LittleEndian>()? as f64;
        let y = cursor.read_i16::<LittleEndian>()? as f64;
        
        // Transform coordinates
        let (tx, ty) = state.view_transform.transform(x, y);
        
        if i == 0 {
            path.push_str(&format!("M {} {}", tx, ty));
        } else {
            path.push_str(&format!(" L {} {}", tx, ty));
        }
    }
    
    let color = argb_to_svg_color(state.current_pen_color);
    svg.add_path(&path, None, Some(&color));
    
    Ok(())
}

/// Handle EMR_POLYGON16 record
fn handle_polygon16(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 8 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read point count
    let point_count = cursor.read_u32::<LittleEndian>()?;
    
    if point_count == 0 || point_count > 10000 {
        return Ok(());
    }
    
    // Read points (16-bit coordinates)
    let mut path = String::new();
    for i in 0..point_count {
        if cursor.position() as usize + 4 > cursor.get_ref().len() {
            break;
        }
        let x = cursor.read_i16::<LittleEndian>()? as f64;
        let y = cursor.read_i16::<LittleEndian>()? as f64;
        
        // Transform coordinates
        let (tx, ty) = state.view_transform.transform(x, y);
        
        if i == 0 {
            path.push_str(&format!("M {} {}", tx, ty));
        } else {
            path.push_str(&format!(" L {} {}", tx, ty));
        }
    }
    path.push_str(" Z");
    
    let color = argb_to_svg_color(state.current_brush_color);
    svg.add_path(&path, Some(&color), None);
    
    Ok(())
}

/// Handle EMR_POLYPOLYLINE record
fn handle_polypolyline(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 12 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read polygon count
    let polygon_count = cursor.read_u32::<LittleEndian>()?;
    
    if polygon_count == 0 || polygon_count > 1000 {
        return Ok(());
    }
    
    // Read point counts for each polygon
    let mut point_counts = Vec::new();
    let mut total_points = 0u32;
    for _ in 0..polygon_count {
        let count = cursor.read_u32::<LittleEndian>()?;
        point_counts.push(count);
        total_points += count;
    }
    
    if total_points > 10000 {
        return Ok(());
    }
    
    // Read all points
    let color = argb_to_svg_color(state.current_pen_color);
    
    for &point_count in &point_counts {
        let mut path = String::new();
        for i in 0..point_count {
            if cursor.position() as usize + 8 > cursor.get_ref().len() {
                break;
            }
            let x = cursor.read_i32::<LittleEndian>()? as f64;
            let y = cursor.read_i32::<LittleEndian>()? as f64;
            
            // Transform coordinates
            let (tx, ty) = state.view_transform.transform(x, y);
            
            if i == 0 {
                path.push_str(&format!("M {} {}", tx, ty));
            } else {
                path.push_str(&format!(" L {} {}", tx, ty));
            }
        }
        svg.add_path(&path, None, Some(&color));
    }
    
    Ok(())
}

/// Handle EMR_POLYPOLYGON record
fn handle_polypolygon(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 12 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read polygon count
    let polygon_count = cursor.read_u32::<LittleEndian>()?;
    
    if polygon_count == 0 || polygon_count > 1000 {
        return Ok(());
    }
    
    // Read point counts for each polygon
    let mut point_counts = Vec::new();
    let mut total_points = 0u32;
    for _ in 0..polygon_count {
        let count = cursor.read_u32::<LittleEndian>()?;
        point_counts.push(count);
        total_points += count;
    }
    
    if total_points > 10000 {
        return Ok(());
    }
    
    // Read all points
    let color = argb_to_svg_color(state.current_brush_color);
    
    for &point_count in &point_counts {
        let mut path = String::new();
        for i in 0..point_count {
            if cursor.position() as usize + 8 > cursor.get_ref().len() {
                break;
            }
            let x = cursor.read_i32::<LittleEndian>()? as f64;
            let y = cursor.read_i32::<LittleEndian>()? as f64;
            
            // Transform coordinates
            let (tx, ty) = state.view_transform.transform(x, y);
            
            if i == 0 {
                path.push_str(&format!("M {} {}", tx, ty));
            } else {
                path.push_str(&format!(" L {} {}", tx, ty));
            }
        }
        path.push_str(" Z");
        svg.add_path(&path, Some(&color), None);
    }
    
    Ok(())
}

/// Handle EMR_POLYPOLYLINE16 record
fn handle_polypolyline16(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 12 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read polygon count
    let polygon_count = cursor.read_u32::<LittleEndian>()?;
    
    if polygon_count == 0 || polygon_count > 1000 {
        return Ok(());
    }
    
    // Read point counts for each polygon
    let mut point_counts = Vec::new();
    let mut total_points = 0u32;
    for _ in 0..polygon_count {
        let count = cursor.read_u32::<LittleEndian>()?;
        point_counts.push(count);
        total_points += count;
    }
    
    if total_points > 10000 {
        return Ok(());
    }
    
    // Read all points (16-bit coordinates)
    let color = argb_to_svg_color(state.current_pen_color);
    
    for &point_count in &point_counts {
        let mut path = String::new();
        for i in 0..point_count {
            if cursor.position() as usize + 4 > cursor.get_ref().len() {
                break;
            }
            let x = cursor.read_i16::<LittleEndian>()? as f64;
            let y = cursor.read_i16::<LittleEndian>()? as f64;
            
            // Transform coordinates
            let (tx, ty) = state.view_transform.transform(x, y);
            
            if i == 0 {
                path.push_str(&format!("M {} {}", tx, ty));
            } else {
                path.push_str(&format!(" L {} {}", tx, ty));
            }
        }
        svg.add_path(&path, None, Some(&color));
    }
    
    Ok(())
}

/// Handle EMR_POLYPOLYGON16 record
fn handle_polypolygon16(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 12 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read polygon count
    let polygon_count = cursor.read_u32::<LittleEndian>()?;
    
    if polygon_count == 0 || polygon_count > 1000 {
        return Ok(());
    }
    
    // Read point counts for each polygon
    let mut point_counts = Vec::new();
    let mut total_points = 0u32;
    for _ in 0..polygon_count {
        let count = cursor.read_u32::<LittleEndian>()?;
        point_counts.push(count);
        total_points += count;
    }
    
    if total_points > 10000 {
        return Ok(());
    }
    
    // Read all points (16-bit coordinates)
    let color = argb_to_svg_color(state.current_brush_color);
    
    for &point_count in &point_counts {
        let mut path = String::new();
        for i in 0..point_count {
            if cursor.position() as usize + 4 > cursor.get_ref().len() {
                break;
            }
            let x = cursor.read_i16::<LittleEndian>()? as f64;
            let y = cursor.read_i16::<LittleEndian>()? as f64;
            
            // Transform coordinates
            let (tx, ty) = state.view_transform.transform(x, y);
            
            if i == 0 {
                path.push_str(&format!("M {} {}", tx, ty));
            } else {
                path.push_str(&format!(" L {} {}", tx, ty));
            }
        }
        path.push_str(" Z");
        svg.add_path(&path, Some(&color), None);
    }
    
    Ok(())
}

/// Handle EMR_CREATEPEN record
fn handle_createpen(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 20 {
        return Ok(());
    }
    
    // Read pen index (ihPen)
    let pen_index = cursor.read_u32::<LittleEndian>()? as usize;
    if pen_index >= 256 {
        return Ok(());
    }
    
    // Read LOGPEN structure
    let pen_style = cursor.read_u32::<LittleEndian>()?;
    let width_x = cursor.read_u32::<LittleEndian>()?;
    let _width_y = cursor.read_u32::<LittleEndian>()?;
    let color = cursor.read_u32::<LittleEndian>()?;
    
    state.pen_table[pen_index] = Some(PenInfo {
        color,
        width: width_x,
        style: pen_style,
    });
    
    Ok(())
}

/// Handle EMR_CREATEBRUSHINDIRECT record
fn handle_createbrushindirect(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 16 {
        return Ok(());
    }
    
    // Read brush index (ihBrush)
    let brush_index = cursor.read_u32::<LittleEndian>()? as usize;
    if brush_index >= 256 {
        return Ok(());
    }
    
    // Read LOGBRUSH structure
    let brush_style = cursor.read_u32::<LittleEndian>()?;
    let color = cursor.read_u32::<LittleEndian>()?;
    let _hatch = cursor.read_u32::<LittleEndian>()?;
    
    state.brush_table[brush_index] = Some(BrushInfo {
        color,
        style: brush_style,
    });
    
    Ok(())
}

/// Handle EMR_SELECTOBJECT record
fn handle_selectobject(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 4 {
        return Ok(());
    }
    
    let object_index = cursor.read_u32::<LittleEndian>()? as usize;
    
    // Check if it's a pen, brush, or font
    if object_index < 256 {
        if let Some(pen) = &state.pen_table[object_index] {
            state.current_pen_color = pen.color;
        }
        if let Some(brush) = &state.brush_table[object_index] {
            state.current_brush_color = brush.color;
        }
        if let Some(font) = &state.font_table[object_index] {
            state.current_font = Some(font.clone());
        }
    }
    
    Ok(())
}

/// Handle EMR_DELETEOBJECT record
fn handle_deleteobject(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 4 {
        return Ok(());
    }
    
    let object_index = cursor.read_u32::<LittleEndian>()? as usize;
    
    if object_index < 256 {
        state.pen_table[object_index] = None;
        state.brush_table[object_index] = None;
    }
    
    Ok(())
}

/// Handle EMR_MOVETOEX record
fn handle_movetoex(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    _data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if cursor.position() as usize + 8 > cursor.get_ref().len() {
        return Ok(());
    }
    
    let x = cursor.read_i32::<LittleEndian>()? as f64;
    let y = cursor.read_i32::<LittleEndian>()? as f64;
    
    state.current_path.moveto(x, y, &state.view_transform);
    
    Ok(())
}

/// Handle EMR_LINETO record
fn handle_lineto(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    _data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if cursor.position() as usize + 8 > cursor.get_ref().len() {
        return Ok(());
    }
    
    let x = cursor.read_i32::<LittleEndian>()? as f64;
    let y = cursor.read_i32::<LittleEndian>()? as f64;
    
    state.current_path.lineto(x, y, &state.view_transform);
    
    Ok(())
}

/// Handle EMR_POLYBEZIERTO record
fn handle_polybezierto(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 8 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read point count
    let point_count = cursor.read_u32::<LittleEndian>()?;
    
    if point_count == 0 || point_count > 10000 || point_count % 3 != 0 {
        return Ok(());
    }
    
    // Read Bezier control points (groups of 3: 2 control + 1 end)
    let bezier_count = point_count / 3;
    for _ in 0..bezier_count {
        if cursor.position() as usize + 24 > cursor.get_ref().len() {
            break;
        }
        let cx1 = cursor.read_i32::<LittleEndian>()? as f64;
        let cy1 = cursor.read_i32::<LittleEndian>()? as f64;
        let cx2 = cursor.read_i32::<LittleEndian>()? as f64;
        let cy2 = cursor.read_i32::<LittleEndian>()? as f64;
        let ex = cursor.read_i32::<LittleEndian>()? as f64;
        let ey = cursor.read_i32::<LittleEndian>()? as f64;
        
        state.current_path.bezier_to(cx1, cy1, cx2, cy2, ex, ey, &state.view_transform);
    }
    
    Ok(())
}

/// Handle EMR_POLYBEZIERTO16 record
fn handle_polybezierto16(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 8 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read point count
    let point_count = cursor.read_u32::<LittleEndian>()?;
    
    if point_count == 0 || point_count > 10000 || point_count % 3 != 0 {
        return Ok(());
    }
    
    // Read Bezier control points (groups of 3: 2 control + 1 end) - 16-bit coordinates
    let bezier_count = point_count / 3;
    for _ in 0..bezier_count {
        if cursor.position() as usize + 12 > cursor.get_ref().len() {
            break;
        }
        let cx1 = cursor.read_i16::<LittleEndian>()? as f64;
        let cy1 = cursor.read_i16::<LittleEndian>()? as f64;
        let cx2 = cursor.read_i16::<LittleEndian>()? as f64;
        let cy2 = cursor.read_i16::<LittleEndian>()? as f64;
        let ex = cursor.read_i16::<LittleEndian>()? as f64;
        let ey = cursor.read_i16::<LittleEndian>()? as f64;
        
        state.current_path.bezier_to(cx1, cy1, cx2, cy2, ex, ey, &state.view_transform);
    }
    
    Ok(())
}

/// Handle EMR_FILLPATH record
fn handle_fillpath(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    // Read bounding box (RECTL) - 16 bytes
    if data_size >= 16 {
        let _left = cursor.read_i32::<LittleEndian>()?;
        let _top = cursor.read_i32::<LittleEndian>()?;
        let _right = cursor.read_i32::<LittleEndian>()?;
        let _bottom = cursor.read_i32::<LittleEndian>()?;
    }
    
    // The actual path data is in current_path
    let path_data = state.current_path.end();
    if !path_data.is_empty() {
        let color = argb_to_svg_color(state.current_brush_color);
        svg.add_path(&path_data, Some(&color), None);
    }
    
    Ok(())
}

/// Handle EMR_STROKEPATH record
fn handle_strokepath(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    // Read bounding box (RECTL) - 16 bytes
    if data_size >= 16 {
        let _left = cursor.read_i32::<LittleEndian>()?;
        let _top = cursor.read_i32::<LittleEndian>()?;
        let _right = cursor.read_i32::<LittleEndian>()?;
        let _bottom = cursor.read_i32::<LittleEndian>()?;
    }
    
    // The actual path data is in current_path
    let path_data = state.current_path.end();
    if !path_data.is_empty() {
        let color = argb_to_svg_color(state.current_pen_color);
        svg.add_path(&path_data, None, Some(&color));
    }
    
    Ok(())
}

/// Handle EMR_STROKEANDFILLPATH record
fn handle_strokeandfillpath(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    // Read bounding box (RECTL) - 16 bytes
    if data_size >= 16 {
        let _left = cursor.read_i32::<LittleEndian>()?;
        let _top = cursor.read_i32::<LittleEndian>()?;
        let _right = cursor.read_i32::<LittleEndian>()?;
        let _bottom = cursor.read_i32::<LittleEndian>()?;
    }
    
    // The actual path data is in current_path
    let path_data = state.current_path.end();
    if !path_data.is_empty() {
        let fill_color = argb_to_svg_color(state.current_brush_color);
        let stroke_color = argb_to_svg_color(state.current_pen_color);
        svg.add_path(&path_data, Some(&fill_color), Some(&stroke_color));
    }
    
    Ok(())
}

/// Handle EMR_EXTCREATEFONTINDIRECTW record
fn handle_extcreatefontindirectw(
    cursor: &mut Cursor<&[u8]>,
    state: &mut GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 20 {
        return Ok(());
    }
    
    // Read font index (ihFont)
    let font_index = cursor.read_u32::<LittleEndian>()? as usize;
    if font_index >= 256 {
        return Ok(());
    }
    
    // Read LOGFONTW structure
    let height = cursor.read_i32::<LittleEndian>()?;
    let width = cursor.read_i32::<LittleEndian>()?;
    let _escapement = cursor.read_i32::<LittleEndian>()?;
    let _orientation = cursor.read_i32::<LittleEndian>()?;
    let weight = cursor.read_u32::<LittleEndian>()?;
    let italic = cursor.read_u8()? != 0;
    let underline = cursor.read_u8()? != 0;
    let strikeout = cursor.read_u8()? != 0;
    let _charset = cursor.read_u8()?;
    let _out_precision = cursor.read_u8()?;
    let _clip_precision = cursor.read_u8()?;
    let _quality = cursor.read_u8()?;
    let _pitch_and_family = cursor.read_u8()?;
    
    // Read face name (32 WCHAR = 64 bytes)
    let mut face_name_chars = Vec::new();
    for _ in 0..32 {
        if cursor.position() as usize + 2 > cursor.get_ref().len() {
            break;
        }
        let ch = cursor.read_u16::<LittleEndian>()?;
        if ch == 0 {
            break;
        }
        face_name_chars.push(ch);
    }
    
    if !face_name_chars.is_empty() {
        let face_name = String::from_utf16_lossy(&face_name_chars);
        
        state.font_table[font_index] = Some(FontInfo {
            face_name: face_name.trim().to_string(),
            height: if height < 0 { -height } else { height },
            weight,
            italic,
            underline,
            strikeout,
        });
    }
    
    Ok(())
}

/// Handle EMR_EXTTEXTOUTA record (ANSI text)
fn handle_exttextouta(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 60 {
        return Ok(());
    }
    
    // Read EMRTEXT structure
    let ptl_reference_x = cursor.read_i32::<LittleEndian>()?;
    let ptl_reference_y = cursor.read_i32::<LittleEndian>()?;
    let n_chars = cursor.read_u32::<LittleEndian>()?;
    let _off_string = cursor.read_u32::<LittleEndian>()?;
    let _options = cursor.read_u32::<LittleEndian>()?;
    let _rcl = cursor.read_i32::<LittleEndian>()?; // RECTL (4 i32s)
    let _rcl2 = cursor.read_i32::<LittleEndian>()?;
    let _rcl3 = cursor.read_i32::<LittleEndian>()?;
    let _rcl4 = cursor.read_i32::<LittleEndian>()?;
    let _off_dx = cursor.read_u32::<LittleEndian>()?;
    
    // Read text string (ANSI)
    let mut text_bytes = Vec::new();
    for _ in 0..n_chars.min(256) {
        if cursor.position() as usize + 1 > cursor.get_ref().len() {
            break;
        }
        let byte = cursor.read_u8()?;
        if byte == 0 {
            break;
        }
        text_bytes.push(byte);
    }
    
    if !text_bytes.is_empty() {
        let text = String::from_utf8_lossy(&text_bytes);
        
        // Get font info
        let font_family = state.current_font.as_ref()
            .map(|f| f.face_name.as_str())
            .unwrap_or("Arial");
        let font_size = state.current_font.as_ref()
            .map(|f| f.height as f64)
            .unwrap_or(12.0);
        let text_color = argb_to_svg_color(state.current_text_color);
        
        // Position (using reference point) - transform coordinates
        let (x, y) = state.view_transform.transform(ptl_reference_x as f64, ptl_reference_y as f64);
        
        svg.add_text_styled(x, y, &text, Some(font_family), Some(font_size), Some(&text_color));
    }
    
    Ok(())
}

/// Handle EMR_EXTTEXTOUTW record (Unicode text)
fn handle_exttextoutw(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 60 {
        return Ok(());
    }
    
    // Read EMRTEXT structure
    let ptl_reference_x = cursor.read_i32::<LittleEndian>()?;
    let ptl_reference_y = cursor.read_i32::<LittleEndian>()?;
    let n_chars = cursor.read_u32::<LittleEndian>()?;
    let _off_string = cursor.read_u32::<LittleEndian>()?;
    let _options = cursor.read_u32::<LittleEndian>()?;
    let _rcl = cursor.read_i32::<LittleEndian>()?; // RECTL (4 i32s)
    let _rcl2 = cursor.read_i32::<LittleEndian>()?;
    let _rcl3 = cursor.read_i32::<LittleEndian>()?;
    let _rcl4 = cursor.read_i32::<LittleEndian>()?;
    let _off_dx = cursor.read_u32::<LittleEndian>()?;
    
    // Read text string (Unicode UTF-16LE)
    let max_chars = n_chars.min(256) as usize;
    let mut chars = Vec::new();
    
    for _ in 0..max_chars {
        if cursor.position() as usize + 2 > cursor.get_ref().len() {
            break;
        }
        let ch = cursor.read_u16::<LittleEndian>()?;
        if ch == 0 {
            break;
        }
        chars.push(ch);
    }
    
    if !chars.is_empty() {
        let text = String::from_utf16_lossy(&chars);
        
        // Get font info
        let font_family = state.current_font.as_ref()
            .map(|f| f.face_name.as_str())
            .unwrap_or("Arial");
        let font_size = state.current_font.as_ref()
            .map(|f| f.height as f64)
            .unwrap_or(12.0);
        let text_color = argb_to_svg_color(state.current_text_color);
        
        // Position - transform coordinates
        let (x, y) = state.view_transform.transform(ptl_reference_x as f64, ptl_reference_y as f64);
        
        svg.add_text_styled(x, y, &text, Some(font_family), Some(font_size), Some(&text_color));
    }
    
    Ok(())
}

/// Handle EMR_POLYTEXTOUTA record (multiple ANSI text strings)
fn handle_polytextouta(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 8 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read number of strings
    let n_strings = cursor.read_u32::<LittleEndian>()?;
    
    if n_strings == 0 || n_strings > 100 {
        return Ok(());
    }
    
    // Process each text string
    for _ in 0..n_strings {
        if cursor.position() as usize + 60 > cursor.get_ref().len() {
            break;
        }
        
        // Read EMRTEXT structure for each string
        let ptl_reference_x = cursor.read_i32::<LittleEndian>()?;
        let ptl_reference_y = cursor.read_i32::<LittleEndian>()?;
        let n_chars = cursor.read_u32::<LittleEndian>()?;
        let _off_string = cursor.read_u32::<LittleEndian>()?;
        let _options = cursor.read_u32::<LittleEndian>()?;
        let _rcl = cursor.read_i32::<LittleEndian>()?;
        let _rcl2 = cursor.read_i32::<LittleEndian>()?;
        let _rcl3 = cursor.read_i32::<LittleEndian>()?;
        let _rcl4 = cursor.read_i32::<LittleEndian>()?;
        let _off_dx = cursor.read_u32::<LittleEndian>()?;
        
        // Read ANSI text
        let max_chars = n_chars.min(256) as usize;
        let mut text_bytes = Vec::new();
        
        for _ in 0..max_chars {
            if cursor.position() as usize + 1 > cursor.get_ref().len() {
                break;
            }
            let byte = cursor.read_u8()?;
            if byte == 0 {
                break;
            }
            text_bytes.push(byte);
        }
        
        if !text_bytes.is_empty() {
            let text = String::from_utf8_lossy(&text_bytes);
            
            let font_family = state.current_font.as_ref()
                .map(|f| f.face_name.as_str())
                .unwrap_or("Arial");
            let font_size = state.current_font.as_ref()
                .map(|f| f.height as f64)
                .unwrap_or(12.0);
            let text_color = argb_to_svg_color(state.current_text_color);
            
            // Transform coordinates
            let (x, y) = state.view_transform.transform(ptl_reference_x as f64, ptl_reference_y as f64);
            
            svg.add_text_styled(x, y, &text, Some(font_family), Some(font_size), Some(&text_color));
        }
    }
    
    Ok(())
}

/// Handle EMR_POLYTEXTOUTW record (multiple Unicode text strings)
fn handle_polytextoutw(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 8 {
        return Ok(());
    }
    
    // Read bounding box (RECTL)
    let _left = cursor.read_i32::<LittleEndian>()?;
    let _top = cursor.read_i32::<LittleEndian>()?;
    let _right = cursor.read_i32::<LittleEndian>()?;
    let _bottom = cursor.read_i32::<LittleEndian>()?;
    
    // Read number of strings
    let n_strings = cursor.read_u32::<LittleEndian>()?;
    
    if n_strings == 0 || n_strings > 100 {
        return Ok(());
    }
    
    // Process each text string
    for _ in 0..n_strings {
        if cursor.position() as usize + 60 > cursor.get_ref().len() {
            break;
        }
        
        // Read EMRTEXT structure for each string
        let ptl_reference_x = cursor.read_i32::<LittleEndian>()?;
        let ptl_reference_y = cursor.read_i32::<LittleEndian>()?;
        let n_chars = cursor.read_u32::<LittleEndian>()?;
        let _off_string = cursor.read_u32::<LittleEndian>()?;
        let _options = cursor.read_u32::<LittleEndian>()?;
        let _rcl = cursor.read_i32::<LittleEndian>()?;
        let _rcl2 = cursor.read_i32::<LittleEndian>()?;
        let _rcl3 = cursor.read_i32::<LittleEndian>()?;
        let _rcl4 = cursor.read_i32::<LittleEndian>()?;
        let _off_dx = cursor.read_u32::<LittleEndian>()?;
        
        // Read Unicode text
        let mut chars = Vec::new();
        for _ in 0..n_chars.min(256) {
            if cursor.position() as usize + 2 > cursor.get_ref().len() {
                break;
            }
            let ch = cursor.read_u16::<LittleEndian>()?;
            if ch == 0 {
                break;
            }
            chars.push(ch);
        }
        
        if !chars.is_empty() {
            let text = String::from_utf16_lossy(&chars);
            
            let font_family = state.current_font.as_ref()
                .map(|f| f.face_name.as_str())
                .unwrap_or("Arial");
            let font_size = state.current_font.as_ref()
                .map(|f| f.height as f64)
                .unwrap_or(12.0);
            let text_color = argb_to_svg_color(state.current_text_color);
            
            // Transform coordinates
            let (x, y) = state.view_transform.transform(ptl_reference_x as f64, ptl_reference_y as f64);
            
            svg.add_text_styled(x, y, &text, Some(font_family), Some(font_size), Some(&text_color));
        }
    }
    
    Ok(())
}

/// Extract bitmap data from EMF record and convert to PNG
fn extract_bitmap_data(
    cursor: &mut Cursor<&[u8]>,
    bi_width: i32,
    bi_height: i32,
    bi_bit_count: u16,
    bi_size_image: u32,
    bi_clr_used: u32,
) -> Result<Option<Vec<u8>>, Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    // Skip color table if present
    let color_table_size = if bi_bit_count <= 8 {
        let colors = if bi_clr_used > 0 { bi_clr_used } else { 1u32 << bi_bit_count };
        colors as usize * 4 // Each color is 4 bytes (RGBQUAD)
    } else {
        0
    };
    
    if cursor.position() as usize + color_table_size > cursor.get_ref().len() {
        return Ok(None);
    }
    
    // Skip color table
    for _ in 0..color_table_size {
        cursor.read_u8()?;
    }
    
    // Read bitmap data
    let bitmap_size = if bi_size_image > 0 {
        bi_size_image as usize
    } else {
        // Calculate bitmap size
        let width = bi_width.abs() as usize;
        let height = bi_height.abs() as usize;
        let bytes_per_pixel = (bi_bit_count as usize + 7) / 8;
        let row_size = ((width * bytes_per_pixel + 3) / 4) * 4; // Row size aligned to 4 bytes
        row_size * height
    };
    
    if bitmap_size == 0 || cursor.position() as usize + bitmap_size > cursor.get_ref().len() {
        return Ok(None);
    }
    
    // For now, we'll skip actual bitmap conversion to PNG
    // This would require implementing DIB to PNG conversion
    // which is complex and may require additional dependencies
    
    // Skip bitmap data
    for _ in 0..bitmap_size {
        cursor.read_u8()?;
    }
    
    Ok(None) // Return None for now - bitmap rendering not fully implemented
}

/// Handle EMR_BITBLT record (bitmap block transfer)
fn handle_bitblt(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    _state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 100 {
        return Ok(());
    }
    
    // Read destination rectangle
    let x_dest = cursor.read_i32::<LittleEndian>()?;
    let y_dest = cursor.read_i32::<LittleEndian>()?;
    let cx_dest = cursor.read_i32::<LittleEndian>()?;
    let cy_dest = cursor.read_i32::<LittleEndian>()?;
    
    // Read source rectangle
    let _x_src = cursor.read_i32::<LittleEndian>()?;
    let _y_src = cursor.read_i32::<LittleEndian>()?;
    let _cx_src = cursor.read_i32::<LittleEndian>()?;
    let _cy_src = cursor.read_i32::<LittleEndian>()?;
    
    // Read BITMAPINFOHEADER (40 bytes)
    let _bi_size = cursor.read_u32::<LittleEndian>()?;
    let bi_width = cursor.read_i32::<LittleEndian>()?;
    let bi_height = cursor.read_i32::<LittleEndian>()?;
    let _bi_planes = cursor.read_u16::<LittleEndian>()?;
    let bi_bit_count = cursor.read_u16::<LittleEndian>()?;
    let _bi_compression = cursor.read_u32::<LittleEndian>()?;
    let bi_size_image = cursor.read_u32::<LittleEndian>()?;
    let _bi_x_pels_per_meter = cursor.read_i32::<LittleEndian>()?;
    let _bi_y_pels_per_meter = cursor.read_i32::<LittleEndian>()?;
    let bi_clr_used = cursor.read_u32::<LittleEndian>()?;
    let _bi_clr_important = cursor.read_u32::<LittleEndian>()?;
    
    // Try to extract bitmap data
    if let Ok(Some(_bitmap_png)) = extract_bitmap_data(cursor, bi_width, bi_height, bi_bit_count, bi_size_image, bi_clr_used) {
        // If we successfully extracted bitmap, render it
        // For now, this is a placeholder - full bitmap rendering requires PNG encoding
        // svg.add_image(x_dest as f64, y_dest as f64, cx_dest as f64, cy_dest as f64, &bitmap_png, "image/png");
    } else {
        // Skip bitmap data
        extract_bitmap_data(cursor, bi_width, bi_height, bi_bit_count, bi_size_image, bi_clr_used)?;
    }
    
    Ok(())
}

/// Handle EMR_STRETCHBLT record (stretched bitmap block transfer)
fn handle_stretchblt(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    _state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 100 {
        return Ok(());
    }
    
    // Similar to BITBLT but with stretch mode
    // Read destination rectangle
    let x_dest = cursor.read_i32::<LittleEndian>()?;
    let y_dest = cursor.read_i32::<LittleEndian>()?;
    let cx_dest = cursor.read_i32::<LittleEndian>()?;
    let cy_dest = cursor.read_i32::<LittleEndian>()?;
    
    // Read source rectangle
    let _x_src = cursor.read_i32::<LittleEndian>()?;
    let _y_src = cursor.read_i32::<LittleEndian>()?;
    let _cx_src = cursor.read_i32::<LittleEndian>()?;
    let _cy_src = cursor.read_i32::<LittleEndian>()?;
    
    // Read stretch mode
    let _stretch_mode = cursor.read_u32::<LittleEndian>()?;
    
    // Read BITMAPINFOHEADER (40 bytes)
    let _bi_size = cursor.read_u32::<LittleEndian>()?;
    let bi_width = cursor.read_i32::<LittleEndian>()?;
    let bi_height = cursor.read_i32::<LittleEndian>()?;
    let _bi_planes = cursor.read_u16::<LittleEndian>()?;
    let bi_bit_count = cursor.read_u16::<LittleEndian>()?;
    let _bi_compression = cursor.read_u32::<LittleEndian>()?;
    let bi_size_image = cursor.read_u32::<LittleEndian>()?;
    let _bi_x_pels_per_meter = cursor.read_i32::<LittleEndian>()?;
    let _bi_y_pels_per_meter = cursor.read_i32::<LittleEndian>()?;
    let bi_clr_used = cursor.read_u32::<LittleEndian>()?;
    let _bi_clr_important = cursor.read_u32::<LittleEndian>()?;
    
    // Try to extract bitmap data
    if let Ok(Some(_bitmap_png)) = extract_bitmap_data(cursor, bi_width, bi_height, bi_bit_count, bi_size_image, bi_clr_used) {
        // If we successfully extracted bitmap, render it
        // svg.add_image(x_dest as f64, y_dest as f64, cx_dest as f64, cy_dest as f64, &bitmap_png, "image/png");
    } else {
        // Skip bitmap data
        extract_bitmap_data(cursor, bi_width, bi_height, bi_bit_count, bi_size_image, bi_clr_used)?;
    }
    
    Ok(())
}

/// Handle EMR_STRETCHDIBITS record (stretched DIB bitmap)
fn handle_stretchdibits(
    cursor: &mut Cursor<&[u8]>,
    svg: &mut SvgWriter,
    _state: &GraphicsState,
    data_size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use byteorder::{LittleEndian, ReadBytesExt};
    
    if data_size < 100 {
        return Ok(());
    }
    
    // Read destination rectangle
    let x_dest = cursor.read_i32::<LittleEndian>()?;
    let y_dest = cursor.read_i32::<LittleEndian>()?;
    let cx_dest = cursor.read_i32::<LittleEndian>()?;
    let cy_dest = cursor.read_i32::<LittleEndian>()?;
    
    // Read source rectangle
    let _x_src = cursor.read_i32::<LittleEndian>()?;
    let _y_src = cursor.read_i32::<LittleEndian>()?;
    let _cx_src = cursor.read_i32::<LittleEndian>()?;
    let _cy_src = cursor.read_i32::<LittleEndian>()?;
    
    // Read usage
    let _usage = cursor.read_u32::<LittleEndian>()?;
    
    // Read stretch mode
    let _stretch_mode = cursor.read_u32::<LittleEndian>()?;
    
    // Read BITMAPINFOHEADER (40 bytes)
    let _bi_size = cursor.read_u32::<LittleEndian>()?;
    let bi_width = cursor.read_i32::<LittleEndian>()?;
    let bi_height = cursor.read_i32::<LittleEndian>()?;
    let _bi_planes = cursor.read_u16::<LittleEndian>()?;
    let bi_bit_count = cursor.read_u16::<LittleEndian>()?;
    let _bi_compression = cursor.read_u32::<LittleEndian>()?;
    let bi_size_image = cursor.read_u32::<LittleEndian>()?;
    let _bi_x_pels_per_meter = cursor.read_i32::<LittleEndian>()?;
    let _bi_y_pels_per_meter = cursor.read_i32::<LittleEndian>()?;
    let bi_clr_used = cursor.read_u32::<LittleEndian>()?;
    let _bi_clr_important = cursor.read_u32::<LittleEndian>()?;
    
    // Try to extract bitmap data
    if let Ok(Some(_bitmap_png)) = extract_bitmap_data(cursor, bi_width, bi_height, bi_bit_count, bi_size_image, bi_clr_used) {
        // If we successfully extracted bitmap, render it
        // svg.add_image(x_dest as f64, y_dest as f64, cx_dest as f64, cy_dest as f64, &bitmap_png, "image/png");
    } else {
        // Skip bitmap data
        extract_bitmap_data(cursor, bi_width, bi_height, bi_bit_count, bi_size_image, bi_clr_used)?;
    }
    
    Ok(())
}

/// Convert ARGB color to SVG color string
fn argb_to_svg_color(argb: u32) -> String {
    let a = ((argb >> 24) & 0xFF) as u8;
    let r = ((argb >> 16) & 0xFF) as u8;
    let g = ((argb >> 8) & 0xFF) as u8;
    let b = (argb & 0xFF) as u8;
    
    // If alpha is 0, treat as fully opaque (common in EMF where alpha=0 means "use default")
    // Otherwise, use the actual alpha value
    if a == 0 {
        // Alpha 0 in EMF often means "use default opacity" (fully opaque)
        format!("#{:02x}{:02x}{:02x}", r, g, b)
    } else if a == 255 {
        format!("#{:02x}{:02x}{:02x}", r, g, b)
    } else {
        format!("rgba({},{},{},{})", r, g, b, a as f32 / 255.0)
    }
}

/// Normalize dimension value
fn normalize_dimension(value: f64) -> u32 {
    eprintln!("normalize_dimension called with: {}", value);
    if value.is_finite() && value > 0.0 && value < 20000.0 {
        let result = value.ceil() as u32;
        eprintln!("normalize_dimension returning: {}", result);
        result
    } else {
        eprintln!("normalize_dimension returning default: 800");
        800 // Default fallback
    }
}

