//! EMF+ parser for handling EMF+ records embedded in EMF files

use crate::svg_writer::SvgWriter;
use byteorder::{LittleEndian, ReadBytesExt};
use std::io::Cursor;

const EMR_COMMENT: u32 = 70;
const EMFPLUS_SIGNATURE: u32 = 0x2B464D45; // 'EMF+'
const EMFPLUS_FLAG_HAS_RECORDS: u32 = 0x00000001;
const OBJECT_TABLE_SIZE: usize = 256;

// EMF+ Record Types
const EMFPLUS_RECORD_OBJECT: u16 = 0x4008;
const EMFPLUS_RECORD_FILL_RECTS: u16 = 0x400A;
const EMFPLUS_RECORD_DRAW_RECTS: u16 = 0x400B;
const EMFPLUS_RECORD_FILL_PATH: u16 = 0x4014;
const EMFPLUS_RECORD_DRAW_PATH: u16 = 0x4015;
const EMFPLUS_RECORD_DRAW_IMAGE: u16 = 0x401A;
const EMFPLUS_RECORD_DRAW_STRING: u16 = 0x401C;
const EMFPLUS_RECORD_SET_WORLD_TRANSFORM: u16 = 0x402A;
const EMFPLUS_RECORD_RESET_WORLD_TRANSFORM: u16 = 0x402B;
const EMFPLUS_RECORD_MULTIPLY_WORLD_TRANSFORM: u16 = 0x402C;
const EMFPLUS_RECORD_TRANSLATE_WORLD_TRANSFORM: u16 = 0x402D;
const EMFPLUS_RECORD_SCALE_WORLD_TRANSFORM: u16 = 0x402E;
const EMFPLUS_RECORD_ROTATE_WORLD_TRANSFORM: u16 = 0x402F;
const EMFPLUS_RECORD_SAVE: u16 = 0x4025;
const EMFPLUS_RECORD_RESTORE: u16 = 0x4026;
const EMFPLUS_RECORD_RESET_CLIP: u16 = 0x4031;
const EMFPLUS_RECORD_SET_CLIP_RECT: u16 = 0x4032;
const EMFPLUS_RECORD_SET_CLIP_PATH: u16 = 0x4033;

// EMF+ Object Types
const EMFPLUS_OBJECT_BRUSH: u8 = 0x01;
const EMFPLUS_OBJECT_PEN: u8 = 0x02;
const EMFPLUS_OBJECT_PATH: u8 = 0x03;
const EMFPLUS_OBJECT_IMAGE: u8 = 0x05;
const EMFPLUS_OBJECT_FONT: u8 = 0x06;

// Brush Types
const BRUSH_TYPE_SOLID_COLOR: u32 = 0;
const BRUSH_TYPE_LINEAR_GRADIENT: u32 = 4;

/// Brush representation
#[derive(Clone)]
enum Brush {
    SolidColor(u32), // ARGB
    LinearGradient {
        start_color: u32,
        end_color: u32,
        rect: (f32, f32, f32, f32), // x, y, width, height
    },
}

/// Pen representation
#[derive(Clone)]
struct Pen {
    brush: Brush,
    width: f32,
}

/// Path representation (simplified - stores SVG path data)
#[derive(Clone)]
struct Path {
    svg_path: String,
}

/// Graphics state for save/restore
struct GraphicsState {
    transform: Transform,
}

/// 2D transformation matrix
#[derive(Clone, Copy)]
struct Transform {
    m11: f32, m12: f32,
    m21: f32, m22: f32,
    dx: f32, dy: f32,
}

impl Transform {
    fn identity() -> Self {
        Self {
            m11: 1.0, m12: 0.0,
            m21: 0.0, m22: 1.0,
            dx: 0.0, dy: 0.0,
        }
    }
}

/// EMF+ parser for parsing EMF+ comment records
pub struct EmfPlusParser<'a> {
    emf_data: &'a [u8],
    svg: &'a mut SvgWriter,
    detected_records: bool,
    brush_table: Vec<Option<Brush>>,
    pen_table: Vec<Option<Pen>>,
    path_table: Vec<Option<Path>>,
    current_transform: Transform,
    state_stack: Vec<GraphicsState>,
}

impl<'a> EmfPlusParser<'a> {
    pub fn new(emf_data: &'a [u8], svg: &'a mut SvgWriter) -> Self {
        Self {
            emf_data,
            svg,
            detected_records: false,
            brush_table: vec![None; OBJECT_TABLE_SIZE],
            pen_table: vec![None; OBJECT_TABLE_SIZE],
            path_table: vec![None; OBJECT_TABLE_SIZE],
            current_transform: Transform::identity(),
            state_stack: Vec::new(),
        }
    }

    pub fn has_detected_records(&self) -> bool {
        self.detected_records
    }

    /// Parse EMF+ records from EMF data
    pub fn parse(&mut self) {
        if self.emf_data.len() < 16 {
            return;
        }

        let mut cursor = Cursor::new(self.emf_data);
        
        // Skip EMF header (40 bytes)
        cursor.set_position(40);

        // Parse EMF records
        while cursor.position() < self.emf_data.len() as u64 {
            if cursor.position() + 8 > self.emf_data.len() as u64 {
                break;
            }

            let record_type = match cursor.read_u32::<LittleEndian>() {
                Ok(t) => t,
                Err(_) => break,
            };

            let record_size = match cursor.read_u32::<LittleEndian>() {
                Ok(s) => s,
                Err(_) => break,
            };

            if record_size < 8 {
                break;
            }

            let data_size = record_size - 8;
            if cursor.position() + data_size as u64 > self.emf_data.len() as u64 {
                break;
            }

            // Handle EMR_COMMENT for EMF+ records
            if record_type == EMR_COMMENT {
                let data_start = cursor.position() as usize;
                let data_end = (cursor.position() + data_size as u64) as usize;
                
                if data_end <= self.emf_data.len() {
                    let comment_data = &self.emf_data[data_start..data_end];
                    self.parse_comment(comment_data);
                }
            }

            // Skip record data
            cursor.set_position(cursor.position() + data_size as u64);
        }
    }

    /// Parse EMF+ comment record
    fn parse_comment(&mut self, record_data: &[u8]) {
        if record_data.len() < 4 {
            return;
        }

        let mut cursor = Cursor::new(record_data);
        let byte_count = match cursor.read_u32::<LittleEndian>() {
            Ok(c) => c,
            Err(_) => return,
        };

        let remaining = cursor.get_ref().len() - cursor.position() as usize;
        if byte_count <= 0 || byte_count as usize > remaining {
            return;
        }

        let payload = &cursor.get_ref()[cursor.position() as usize..(cursor.position() + byte_count as u64) as usize];
        
        if payload.len() < 16 {
            return;
        }

        let mut payload_cursor = Cursor::new(payload);
        let signature = match payload_cursor.read_u32::<LittleEndian>() {
            Ok(s) => s,
            Err(_) => return,
        };

        if signature != EMFPLUS_SIGNATURE {
            return;
        }

        let _version = match payload_cursor.read_u32::<LittleEndian>() {
            Ok(v) => v,
            Err(_) => return,
        };

        let flags = match payload_cursor.read_u32::<LittleEndian>() {
            Ok(f) => f,
            Err(_) => return,
        };

        let data_size = match payload_cursor.read_u32::<LittleEndian>() {
            Ok(s) => s,
            Err(_) => return,
        };

        if (flags & EMFPLUS_FLAG_HAS_RECORDS) == 0 {
            return;
        }

        let payload_remaining = payload_cursor.get_ref().len() - payload_cursor.position() as usize;
        if data_size == 0 || data_size as usize > payload_remaining {
            return;
        }

        let record_bytes = &payload[payload_cursor.position() as usize..(payload_cursor.position() + data_size as u64) as usize];
        self.parse_records(record_bytes);
    }

    /// Parse EMF+ records
    fn parse_records(&mut self, buffer: &[u8]) {
        let mut cursor = Cursor::new(buffer);

        while cursor.position() < buffer.len() as u64 {
            if cursor.position() + 12 > buffer.len() as u64 {
                break;
            }

            let type_code = match cursor.read_u16::<LittleEndian>() {
                Ok(t) => t,
                Err(_) => break,
            };

            let flags = match cursor.read_u16::<LittleEndian>() {
                Ok(f) => f,
                Err(_) => break,
            };

            let size_units = match cursor.read_u32::<LittleEndian>() {
                Ok(s) => s,
                Err(_) => break,
            };

            let _data_size_units = match cursor.read_u32::<LittleEndian>() {
                Ok(s) => s,
                Err(_) => break,
            };

            let size_bytes = size_units * 4;
            let payload_length = (size_bytes as i64 - 12).max(0) as u64;

            if cursor.position() + payload_length > buffer.len() as u64 {
                break;
            }

            let payload_start = cursor.position() as usize;
            let payload_end = payload_start + payload_length as usize;
            let payload = &buffer[payload_start..payload_end];

            // Mark that we detected records
            self.detected_records = true;

            // Handle record based on type
            self.handle_record(type_code, flags, payload);

            cursor.set_position(payload_end as u64);
        }
    }

    /// Handle a single EMF+ record
    fn handle_record(&mut self, record_type: u16, flags: u16, payload: &[u8]) {
        match record_type {
            EMFPLUS_RECORD_OBJECT => self.handle_object(flags, payload),
            EMFPLUS_RECORD_FILL_RECTS => self.handle_fill_rects(flags, payload),
            EMFPLUS_RECORD_DRAW_RECTS => self.handle_draw_rects(flags, payload),
            EMFPLUS_RECORD_FILL_PATH => self.handle_fill_path(flags, payload),
            EMFPLUS_RECORD_DRAW_PATH => self.handle_draw_path(flags, payload),
            EMFPLUS_RECORD_DRAW_IMAGE => self.handle_draw_image(flags, payload),
            EMFPLUS_RECORD_DRAW_STRING => self.handle_draw_string(flags, payload),
            EMFPLUS_RECORD_SET_WORLD_TRANSFORM => self.handle_set_world_transform(payload),
            EMFPLUS_RECORD_RESET_WORLD_TRANSFORM => self.reset_world_transform(),
            EMFPLUS_RECORD_MULTIPLY_WORLD_TRANSFORM => self.handle_multiply_world_transform(flags, payload),
            EMFPLUS_RECORD_TRANSLATE_WORLD_TRANSFORM => self.handle_translate_world_transform(flags, payload),
            EMFPLUS_RECORD_SCALE_WORLD_TRANSFORM => self.handle_scale_world_transform(flags, payload),
            EMFPLUS_RECORD_ROTATE_WORLD_TRANSFORM => self.handle_rotate_world_transform(flags, payload),
            EMFPLUS_RECORD_SAVE => self.handle_save(payload),
            EMFPLUS_RECORD_RESTORE => self.handle_restore(payload),
            EMFPLUS_RECORD_RESET_CLIP => self.reset_clip(),
            EMFPLUS_RECORD_SET_CLIP_RECT => self.handle_set_clip_rect(flags, payload),
            _ => {
                // Unknown record type - skip
            }
        }
    }

    /// Handle OBJECT record - creates brushes, pens, paths, etc.
    fn handle_object(&mut self, flags: u16, payload: &[u8]) {
        let object_id = (flags & 0xFF) as usize;
        let object_type = ((flags >> 8) & 0xFF) as u8;

        if object_id >= OBJECT_TABLE_SIZE {
            return;
        }

        match object_type {
            EMFPLUS_OBJECT_BRUSH => {
                if let Some(brush) = self.parse_brush(payload) {
                    self.brush_table[object_id] = Some(brush);
                }
            }
            EMFPLUS_OBJECT_PEN => {
                if let Some(pen) = self.parse_pen(payload) {
                    self.pen_table[object_id] = Some(pen);
                }
            }
            EMFPLUS_OBJECT_PATH => {
                if let Some(path) = self.parse_path(payload) {
                    self.path_table[object_id] = Some(path);
                }
            }
            _ => {
                // Other object types not yet implemented
            }
        }
    }

    /// Parse brush object
    fn parse_brush(&self, payload: &[u8]) -> Option<Brush> {
        if payload.len() < 8 {
            return None;
        }

        let mut cursor = Cursor::new(payload);
        let _version = cursor.read_u32::<LittleEndian>().ok()?;
        let brush_type = cursor.read_u32::<LittleEndian>().ok()?;

        match brush_type {
            BRUSH_TYPE_SOLID_COLOR => {
                let color = cursor.read_u32::<LittleEndian>().ok()?;
                Some(Brush::SolidColor(color))
            }
            BRUSH_TYPE_LINEAR_GRADIENT => {
                if payload.len() < 40 {
                    return None;
                }
                let _brush_flags = cursor.read_u32::<LittleEndian>().ok()?;
                let _wrap_mode = cursor.read_u32::<LittleEndian>().ok()?;
                let rect_x = cursor.read_f32::<LittleEndian>().ok()?;
                let rect_y = cursor.read_f32::<LittleEndian>().ok()?;
                let rect_width = cursor.read_f32::<LittleEndian>().ok()?;
                let rect_height = cursor.read_f32::<LittleEndian>().ok()?;
                let start_color = cursor.read_u32::<LittleEndian>().ok()?;
                let end_color = cursor.read_u32::<LittleEndian>().ok()?;
                
                Some(Brush::LinearGradient {
                    start_color,
                    end_color,
                    rect: (rect_x, rect_y, rect_width, rect_height),
                })
            }
            _ => None,
        }
    }

    /// Parse pen object
    fn parse_pen(&self, payload: &[u8]) -> Option<Pen> {
        if payload.len() < 20 {
            return None;
        }

        let mut cursor = Cursor::new(payload);
        let _version = cursor.read_u32::<LittleEndian>().ok()?;
        let _type = cursor.read_u32::<LittleEndian>().ok()?;
        let _pen_data_flags = cursor.read_u32::<LittleEndian>().ok()?;
        let _pen_unit = cursor.read_u32::<LittleEndian>().ok()?;
        let pen_width = cursor.read_f32::<LittleEndian>().ok()?;

        // Parse brush data
        let brush_payload = &payload[cursor.position() as usize..];
        let brush = self.parse_brush(brush_payload)?;

        Some(Pen {
            brush,
            width: pen_width.max(0.5),
        })
    }

    /// Parse path object (simplified)
    fn parse_path(&self, payload: &[u8]) -> Option<Path> {
        if payload.len() < 12 {
            return None;
        }

        let mut cursor = Cursor::new(payload);
        let _version = cursor.read_u32::<LittleEndian>().ok()?;
        let point_count = cursor.read_u32::<LittleEndian>().ok()?;
        let _path_flags = cursor.read_u32::<LittleEndian>().ok()?;

        if point_count == 0 {
            return Some(Path { svg_path: String::new() });
        }

        // Read points and types
        let coords_size = (point_count * 8) as usize; // 2 floats per point
        let types_size = point_count as usize;
        
        if cursor.position() as usize + coords_size + types_size > payload.len() {
            return None;
        }

        let mut svg_path = String::new();
        let mut coords = Vec::new();
        
        for _ in 0..point_count {
            let x = cursor.read_f32::<LittleEndian>().ok()?;
            let y = cursor.read_f32::<LittleEndian>().ok()?;
            coords.push((x, y));
        }

        let mut types = Vec::new();
        for _ in 0..point_count {
            let t = cursor.read_u8().ok()?;
            types.push(t);
        }

        // Build SVG path
        let mut i = 0;
        while i < point_count as usize {
            let point_type = types[i] & 0x07;
            let close = (types[i] & 0x80) != 0;
            
            match point_type {
                0 => { // Start
                    let (x, y) = coords[i];
                    svg_path.push_str(&format!("M {} {} ", x, y));
                }
                1 => { // Line
                    let (x, y) = coords[i];
                    svg_path.push_str(&format!("L {} {} ", x, y));
                    if close {
                        svg_path.push_str("Z ");
                    }
                }
                3 => { // Bezier
                    if i + 2 < point_count as usize {
                        let (cx1, cy1) = coords[i];
                        let (cx2, cy2) = coords[i + 1];
                        let (ex, ey) = coords[i + 2];
                        svg_path.push_str(&format!("C {} {} {} {} {} {} ", cx1, cy1, cx2, cy2, ex, ey));
                        if close {
                            svg_path.push_str("Z ");
                        }
                        i += 2;
                    }
                }
                _ => {}
            }
            i += 1;
        }

        Some(Path { svg_path })
    }

    /// Handle FILL_RECTS record
    fn handle_fill_rects(&mut self, flags: u16, payload: &[u8]) {
        if payload.len() < 8 {
            return;
        }

        let mut cursor = Cursor::new(payload);
        let brush_token = match cursor.read_u32::<LittleEndian>() {
            Ok(t) => t,
            Err(_) => return,
        };
        let rect_count = match cursor.read_u32::<LittleEndian>() {
            Ok(c) => c,
            Err(_) => return,
        };

        if rect_count == 0 {
            return;
        }

        let rectangles_are_integer = (flags & 0x4000) != 0;
        let brush_from_color = (flags & 0x8000) != 0;

        let brush = if brush_from_color {
            Some(Brush::SolidColor(brush_token))
        } else {
            let brush_id = (brush_token & 0xFF) as usize;
            if brush_id < OBJECT_TABLE_SIZE {
                self.brush_table[brush_id].clone()
            } else {
                None
            }
        };

        let fill_color = match &brush {
            Some(b) => self.brush_to_color(b),
            None => return,
        };

        for _ in 0..rect_count {
            let (x, y, width, height) = if rectangles_are_integer {
                let x = match cursor.read_i16::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let y = match cursor.read_i16::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let width = match cursor.read_i16::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let height = match cursor.read_i16::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                (x, y, width, height)
            } else {
                let x = match cursor.read_f32::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let y = match cursor.read_f32::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let width = match cursor.read_f32::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let height = match cursor.read_f32::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                (x, y, width, height)
            };

            self.svg.add_rect(x, y, width, height, Some(&fill_color), None);
        }
    }

    /// Handle DRAW_RECTS record
    fn handle_draw_rects(&mut self, flags: u16, payload: &[u8]) {
        if payload.len() < 4 {
            return;
        }

        let pen_id = (flags & 0xFF) as usize;
        let pen = if pen_id < OBJECT_TABLE_SIZE {
            self.pen_table[pen_id].clone()
        } else {
            return;
        };

        let pen = match pen {
            Some(p) => p,
            None => return,
        };

        let mut cursor = Cursor::new(payload);
        let rect_count = match cursor.read_u32::<LittleEndian>() {
            Ok(c) => c,
            Err(_) => return,
        };

        if rect_count == 0 {
            return;
        }

        let rectangles_are_integer = (flags & 0x4000) != 0;
        let stroke_color = self.brush_to_color(&pen.brush);

        for _ in 0..rect_count {
            let (x, y, width, height) = if rectangles_are_integer {
                let x = match cursor.read_i16::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let y = match cursor.read_i16::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let width = match cursor.read_i16::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let height = match cursor.read_i16::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                (x, y, width, height)
            } else {
                let x = match cursor.read_f32::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let y = match cursor.read_f32::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let width = match cursor.read_f32::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                let height = match cursor.read_f32::<LittleEndian>() {
                    Ok(v) => v as f64,
                    Err(_) => return,
                };
                (x, y, width, height)
            };

            self.svg.add_rect(x, y, width, height, None, Some(&stroke_color));
        }
    }

    /// Handle FILL_PATH record
    fn handle_fill_path(&mut self, flags: u16, payload: &[u8]) {
        let path_id = (flags & 0xFF) as usize;
        let path = if path_id < OBJECT_TABLE_SIZE {
            self.path_table[path_id].clone()
        } else {
            return;
        };

        let path = match path {
            Some(p) => p,
            None => return,
        };

        if payload.len() < 4 {
            return;
        }

        let mut cursor = Cursor::new(payload);
        let brush_token = match cursor.read_u32::<LittleEndian>() {
            Ok(t) => t,
            Err(_) => return,
        };
        let brush_from_color = (flags & 0x8000) != 0;

        let brush = if brush_from_color {
            Some(Brush::SolidColor(brush_token))
        } else {
            let brush_id = (brush_token & 0xFF) as usize;
            if brush_id < OBJECT_TABLE_SIZE {
                self.brush_table[brush_id].clone()
            } else {
                None
            }
        };

        let fill_color = match &brush {
            Some(b) => self.brush_to_color(b),
            None => return,
        };
        self.svg.add_path(&path.svg_path, Some(&fill_color), None);
    }

    /// Handle DRAW_PATH record
    fn handle_draw_path(&mut self, flags: u16, payload: &[u8]) {
        let path_id = (flags & 0xFF) as usize;
        let path = if path_id < OBJECT_TABLE_SIZE {
            self.path_table[path_id].clone()
        } else {
            return;
        };

        let path = match path {
            Some(p) => p,
            None => return,
        };

        if payload.len() < 4 {
            return;
        }

        let mut cursor = Cursor::new(payload);
        let pen_id = match cursor.read_u32::<LittleEndian>() {
            Ok(id) => id,
            Err(_) => return,
        };
        let pen_id_usize = (pen_id & 0xFF) as usize;
        let pen = if pen_id_usize < OBJECT_TABLE_SIZE {
            self.pen_table[pen_id_usize].clone()
        } else {
            return;
        };

        let pen = match pen {
            Some(p) => p,
            None => return,
        };

        let stroke_color = self.brush_to_color(&pen.brush);
        self.svg.add_path(&path.svg_path, None, Some(&stroke_color));
    }

    /// Handle DRAW_IMAGE record (simplified - placeholder)
    fn handle_draw_image(&mut self, _flags: u16, _payload: &[u8]) {
        // TODO: Implement image drawing
    }

    /// Handle DRAW_STRING record (simplified - placeholder)
    fn handle_draw_string(&mut self, _flags: u16, _payload: &[u8]) {
        // TODO: Implement string drawing
    }

    /// Handle SET_WORLD_TRANSFORM record
    fn handle_set_world_transform(&mut self, payload: &[u8]) {
        if payload.len() < 24 {
            return;
        }

        let mut cursor = Cursor::new(payload);
        if let (Ok(m11), Ok(m12), Ok(m21), Ok(m22), Ok(dx), Ok(dy)) = (
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
        ) {
            self.current_transform = Transform {
                m11, m12,
                m21, m22,
                dx, dy,
            };
        }
    }

    /// Reset world transform
    fn reset_world_transform(&mut self) {
        self.current_transform = Transform::identity();
    }

    /// Handle MULTIPLY_WORLD_TRANSFORM record
    fn handle_multiply_world_transform(&mut self, _flags: u16, payload: &[u8]) {
        if payload.len() < 24 {
            return;
        }

        let mut cursor = Cursor::new(payload);
        if let (Ok(m11), Ok(m12), Ok(m21), Ok(m22), Ok(dx), Ok(dy)) = (
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
        ) {
            let new_transform = Transform {
                m11, m12,
                m21, m22,
                dx, dy,
            };
            
            // Multiply transforms (simplified - just replace for now)
            self.current_transform = new_transform;
        }
    }

    /// Handle TRANSLATE_WORLD_TRANSFORM record
    fn handle_translate_world_transform(&mut self, _flags: u16, payload: &[u8]) {
        if payload.len() < 8 {
            return;
        }

        let mut cursor = Cursor::new(payload);
        if let (Ok(dx), Ok(dy)) = (
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
        ) {
            self.current_transform.dx += dx;
            self.current_transform.dy += dy;
        }
    }

    /// Handle SCALE_WORLD_TRANSFORM record
    fn handle_scale_world_transform(&mut self, _flags: u16, payload: &[u8]) {
        if payload.len() < 8 {
            return;
        }

        let mut cursor = Cursor::new(payload);
        if let (Ok(sx), Ok(sy)) = (
            cursor.read_f32::<LittleEndian>(),
            cursor.read_f32::<LittleEndian>(),
        ) {
            self.current_transform.m11 *= sx;
            self.current_transform.m22 *= sy;
        }
    }

    /// Handle ROTATE_WORLD_TRANSFORM record
    fn handle_rotate_world_transform(&mut self, _flags: u16, payload: &[u8]) {
        if payload.len() < 4 {
            return;
        }

        let mut cursor = Cursor::new(payload);
        if let Ok(angle_degrees) = cursor.read_f32::<LittleEndian>() {
            let angle_rad = angle_degrees.to_radians();
            let cos_a = angle_rad.cos();
            let sin_a = angle_rad.sin();
            
            // Rotate transform matrix
            let new_m11 = self.current_transform.m11 * cos_a - self.current_transform.m12 * sin_a;
            let new_m12 = self.current_transform.m11 * sin_a + self.current_transform.m12 * cos_a;
            let new_m21 = self.current_transform.m21 * cos_a - self.current_transform.m22 * sin_a;
            let new_m22 = self.current_transform.m21 * sin_a + self.current_transform.m22 * cos_a;
            
            self.current_transform.m11 = new_m11;
            self.current_transform.m12 = new_m12;
            self.current_transform.m21 = new_m21;
            self.current_transform.m22 = new_m22;
        }
    }

    /// Handle SAVE record
    fn handle_save(&mut self, _payload: &[u8]) {
        self.state_stack.push(GraphicsState {
            transform: self.current_transform,
        });
    }

    /// Handle RESTORE record
    fn handle_restore(&mut self, _payload: &[u8]) {
        if let Some(state) = self.state_stack.pop() {
            self.current_transform = state.transform;
        }
    }

    /// Reset clip region
    fn reset_clip(&mut self) {
        // TODO: Implement clipping
    }

    /// Handle SET_CLIP_RECT record
    fn handle_set_clip_rect(&mut self, _flags: u16, _payload: &[u8]) {
        // TODO: Implement clipping
    }

    /// Convert brush to SVG color string
    fn brush_to_color(&self, brush: &Brush) -> String {
        match brush {
            Brush::SolidColor(argb) => {
                let a = ((argb >> 24) & 0xFF) as u8;
                let r = ((argb >> 16) & 0xFF) as u8;
                let g = ((argb >> 8) & 0xFF) as u8;
                let b = (argb & 0xFF) as u8;
                if a == 255 {
                    format!("#{:02x}{:02x}{:02x}", r, g, b)
                } else {
                    format!("rgba({},{},{},{})", r, g, b, a as f32 / 255.0)
                }
            }
            Brush::LinearGradient { start_color, end_color: _, rect: _ } => {
                // For now, use start color as fallback
                // TODO: Implement proper gradient rendering
                let a = ((start_color >> 24) & 0xFF) as u8;
                let r = ((start_color >> 16) & 0xFF) as u8;
                let g = ((start_color >> 8) & 0xFF) as u8;
                let b = (start_color & 0xFF) as u8;
                if a == 255 {
                    format!("#{:02x}{:02x}{:02x}", r, g, b)
                } else {
                    format!("rgba({},{},{},{})", r, g, b, a as f32 / 255.0)
                }
            }
        }
    }
}
