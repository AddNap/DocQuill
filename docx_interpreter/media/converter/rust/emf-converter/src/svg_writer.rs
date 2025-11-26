//! SVG writer for generating SVG output

use svg::Document;
use svg::node::element::{Rectangle, Image, Text, Path};
use svg::node::Text as TextNode;

/// SVG writer for building SVG documents
pub struct SvgWriter {
    width: u32,
    height: u32,
    elements: Vec<svg::node::element::Element>,
    auto_viewbox: bool,  // If true, calculate viewBox from element bounds
    min_x: f64,
    min_y: f64,
    max_x: f64,
    max_y: f64,
    content_min_x: f64,  // Min X excluding paths starting near origin
    content_min_y: f64,  // Min Y excluding paths starting near origin
    content_max_x: f64,  // Max X excluding paths starting near origin
    content_max_y: f64,  // Max Y excluding paths starting near origin
}

impl SvgWriter {
    pub fn new(width: u32, height: u32) -> Self {
        Self {
            width,
            height,
            elements: Vec::new(),
            auto_viewbox: true,
            min_x: f64::MAX,
            min_y: f64::MAX,
            max_x: f64::MIN,
            max_y: f64::MIN,
            content_min_x: f64::MAX,
            content_min_y: f64::MAX,
            content_max_x: f64::MIN,
            content_max_y: f64::MIN,
        }
    }
    
    fn update_bounds(&mut self, x: f64, y: f64) {
        if self.auto_viewbox {
            self.min_x = self.min_x.min(x);
            self.min_y = self.min_y.min(y);
            self.max_x = self.max_x.max(x);
            self.max_y = self.max_y.max(y);
        }
    }
    
    fn update_content_bounds(&mut self, x: f64, y: f64, is_near_origin: bool) {
        if self.auto_viewbox && !is_near_origin {
            // Only update content bounds if not near origin (exclude radiating lines)
            self.content_min_x = self.content_min_x.min(x);
            self.content_min_y = self.content_min_y.min(y);
            self.content_max_x = self.content_max_x.max(x);
            self.content_max_y = self.content_max_y.max(y);
        }
    }

    /// Add a rectangle to the SVG
    pub fn add_rect(&mut self, x: f64, y: f64, width: f64, height: f64, fill: Option<&str>, stroke: Option<&str>) {
        self.update_bounds(x, y);
        self.update_bounds(x + width, y + height);
        
        let mut rect = Rectangle::new()
            .set("x", x)
            .set("y", y)
            .set("width", width)
            .set("height", height);
        
        if let Some(fill_color) = fill {
            rect = rect.set("fill", fill_color);
        } else {
            rect = rect.set("fill", "none");
        }
        
        if let Some(stroke_color) = stroke {
            rect = rect.set("stroke", stroke_color);
        }
        
        self.elements.push(rect.into());
    }

    /// Add text to the SVG
    pub fn add_text(&mut self, x: f64, y: f64, text: &str) {
        let text_elem = Text::new()
            .set("x", x)
            .set("y", y)
            .set("font-family", "Arial")
            .set("font-size", 12)
            .add(TextNode::new(text));
        
        self.elements.push(text_elem.into());
    }

    /// Add text to the SVG with custom styling
    pub fn add_text_styled(&mut self, x: f64, y: f64, text: &str, font_family: Option<&str>, font_size: Option<f64>, fill_color: Option<&str>) {
        let mut text_elem = Text::new()
            .set("x", x)
            .set("y", y)
            .set("font-family", font_family.unwrap_or("Arial"))
            .set("font-size", font_size.unwrap_or(12.0));
        
        if let Some(color) = fill_color {
            text_elem = text_elem.set("fill", color);
        }
        
        text_elem = text_elem.add(TextNode::new(text));
        
        self.elements.push(text_elem.into());
    }

    /// Add an image to the SVG (as base64 embedded)
    pub fn add_image(&mut self, x: f64, y: f64, width: f64, height: f64, image_data: &[u8], mime_type: &str) {
        use base64::{Engine as _, engine::general_purpose};
        let base64_data = general_purpose::STANDARD.encode(image_data);
        let data_uri = format!("data:{};base64,{}", mime_type, base64_data);
        
        let image = Image::new()
            .set("x", x)
            .set("y", y)
            .set("width", width)
            .set("height", height)
            .set("href", data_uri);
        
        self.elements.push(image.into());
    }

    /// Add a path to the SVG
    pub fn add_path(&mut self, path_data: &str, fill: Option<&str>, stroke: Option<&str>) {
        // Extract all numbers from path data for bounds calculation
        // Simple approach: extract all numbers and pair them as (x, y) coordinates
        let numbers: Vec<f64> = path_data
            .split_whitespace()
            .filter_map(|s| {
                // Try to parse as number, ignoring command letters
                s.parse::<f64>().ok()
            })
            .collect();
        
        // Check if path uses L (lineto) commands - needed for filtering logic
        let uses_lineto = path_data.contains(" L ") || 
                         (path_data.starts_with("M ") && 
                          path_data.len() > 10 && 
                          !path_data.contains(" C "));
        
        // Check if path has artifacts that create visible lines:
        // 1. Long segments going TO origin (position reset commands) - filter entire path
        // 2. Long first segment FROM origin (radiating lines) - remove first segment, keep rest
        let should_filter_entire_path = if numbers.len() >= 4 {
            let xs: Vec<f64> = numbers.iter().step_by(2).cloned().collect();
            let ys: Vec<f64> = numbers.iter().skip(1).step_by(2).cloned().collect();
            
            if xs.is_empty() || ys.is_empty() {
                false
            } else {
                if !uses_lineto {
                    false  // Paths with bezier curves are actual shapes
                } else {
                    let start_x = xs[0];
                    let start_y = ys[0];
                    // Check for two types of artifacts:
                    // 1. Long segments going TO origin (position reset commands)
                    // 2. Paths starting near origin with very long first segment (radiating lines)
                    let mut has_long_segment_to_origin = false;
                    for i in 0..(xs.len().min(ys.len()) - 1) {
                        let x1 = xs[i];
                        let y1 = ys[i];
                        let x2 = xs[i + 1];
                        let y2 = ys[i + 1];
                        
                        // Check if segment goes to near origin (position reset)
                        let goes_to_origin = x2 < 50.0 && y2 < 50.0;
                        if goes_to_origin {
                            let dist = ((x2 - x1).powi(2) + (y2 - y1).powi(2)).sqrt();
                            if dist > 300.0 {
                                has_long_segment_to_origin = true;
                                break;
                            }
                        }
                    }
                    
                    // Check if starts near origin with very long first segment (radiating line)
                    // Filter ALL paths with long first segment if they use L commands (lineto)
                    // Even complex shapes with many points create visible lines if first segment is long
                    // Paths with C (bezier) commands are real shapes and should be preserved
                    let starts_at_origin = start_x < 10.0 && start_y < 10.0;
                    let has_long_first_segment = if starts_at_origin && xs.len() >= 2 && ys.len() >= 2 {
                        let first_seg_dist = ((xs[1] - xs[0]).powi(2) + (ys[1] - ys[0]).powi(2)).sqrt();
                        // Filter if first segment is very long (>300 pixels)
                        // This creates a visible radiating line from origin
                        // Only filter paths using L commands, not C (bezier) commands
                        first_seg_dist > 300.0
                    } else {
                        false
                    };
                    
                    // Filter entire path if has long segment going TO origin (position reset)
                    // For paths with long first segment FROM origin, we'll modify them instead
                    has_long_segment_to_origin
                }
            }
        } else {
            false
        };
        
        // Check if path has long first segment FROM origin (radiating line)
        // Instead of filtering, we'll modify the path to remove the first segment
        let mut modified_path_data = path_data.to_string();
        let has_long_first_segment_from_origin = if numbers.len() >= 4 {
            let xs: Vec<f64> = numbers.iter().step_by(2).cloned().collect();
            let ys: Vec<f64> = numbers.iter().skip(1).step_by(2).cloned().collect();
            
            if !xs.is_empty() && !ys.is_empty() {
                let start_x = xs[0];
                let start_y = ys[0];
                let starts_at_origin = start_x < 10.0 && start_y < 10.0;
                
                if starts_at_origin && xs.len() >= 2 && ys.len() >= 2 && uses_lineto {
                    let first_seg_dist = ((xs[1] - xs[0]).powi(2) + (ys[1] - ys[0]).powi(2)).sqrt();
                    
                    if first_seg_dist > 300.0 {
                        // Modify path: remove first M and L, start from second point
                        // Parse path to find first L command
                        let parts: Vec<&str> = path_data.split_whitespace().collect();
                        if parts.len() >= 6 && parts[0] == "M" && parts[3] == "L" {
                            // Rebuild path starting from second point (first L destination)
                            let new_start_x = parts[4];
                            let new_start_y = parts[5];
                            let rest = parts[6..].join(" ");
                            modified_path_data = format!("M {} {} {}", new_start_x, new_start_y, rest);
                            true
                        } else {
                            false
                        }
                    } else {
                        false
                    }
                } else {
                    false
                }
            } else {
                false
            }
        } else {
            false
        };
        
        // Filter entire path if it has position reset (long segment TO origin)
        if should_filter_entire_path {
            // Still update bounds for viewBox calculation, but don't add to elements
            for chunk in numbers.chunks(2) {
                if chunk.len() >= 2 {
                    self.update_bounds(chunk[0], chunk[1]);
                }
            }
            return;  // Don't add this path to SVG
        }
        
        // Use modified path if first segment was removed
        let final_path_data = if has_long_first_segment_from_origin {
            &modified_path_data
        } else {
            path_data
        };
        
        // Update bounds with all coordinate pairs (use original path_data for bounds)
        for chunk in numbers.chunks(2) {
            if chunk.len() >= 2 {
                self.update_bounds(chunk[0], chunk[1]);
                self.update_content_bounds(chunk[0], chunk[1], false);
            }
        }
        
        let mut path = Path::new().set("d", final_path_data);
        
        if let Some(fill_color) = fill {
            path = path.set("fill", fill_color);
        } else {
            path = path.set("fill", "none");
        }
        
        if let Some(stroke_color) = stroke {
            path = path.set("stroke", stroke_color);
        }
        
        self.elements.push(path.into());
    }

    /// Finish and generate SVG string
    pub fn finish(self) -> String {
        // Use calculated bounds if available, otherwise use provided dimensions or large safe values
        let vb_x = if self.min_x != f64::MAX { self.min_x.min(0.0) } else { 0.0 };
        let vb_y = if self.min_y != f64::MAX { self.min_y.min(0.0) } else { 0.0 };
        
        // Check if we have valid bounds that are significantly larger than initial dimensions
        // If bounds are too small (close to initial dimensions), they're likely incorrect
        let has_valid_bounds = self.min_x != f64::MAX && self.max_x > self.min_x && 
                               self.min_y != f64::MAX && self.max_y > self.min_y &&
                               (self.max_x - self.min_x) > (self.width as f64 * 1.5) &&
                               (self.max_y - self.min_y) > (self.height as f64 * 1.5);
        
        // Use dimensions from rclFrame (passed to SvgWriter::new) as the base for viewBox
        // rclFrame represents the physical size of the EMF content
        // However, we should use the actual content bounds to ensure nothing is clipped
        // If we have valid bounds, use them; otherwise fall back to rclFrame dimensions
        let (vb_width, vb_height) = if self.min_x != f64::MAX && self.max_x > self.min_x && 
                                      self.max_y > self.min_y {
            // Use calculated bounds to ensure all content is visible
            // Add small padding to avoid edge clipping
            let padding = 10.0;
            ((self.max_x - vb_x + padding).max(self.width as f64), 
             (self.max_y - vb_y + padding).max(self.height as f64))
        } else {
            // Use rclFrame dimensions (passed to SvgWriter::new as width/height)
            (self.width as f64, self.height as f64)
        };
        
        eprintln!("SvgWriter finish: bounds=({}, {}) to ({}, {}), has_valid={}, viewBox=({}, {}, {}, {})", 
            self.min_x, self.min_y, self.max_x, self.max_y, has_valid_bounds, vb_x, vb_y, vb_width, vb_height);
        
        // Calculate clip area - exclude paths starting near origin (0,0) which are often artifacts
        // Use content bounds (excluding paths near origin) if available
        // But ensure we don't clip too aggressively - use actual bounds if they're reasonable
        let clip_x = if self.content_min_x != f64::MAX && self.content_min_x > 50.0 {
            (self.content_min_x - 10.0).max(0.0)  // Add small padding, ensure non-negative
        } else if self.min_x != f64::MAX && self.min_x > 0.0 {
            self.min_x.max(0.0)  // Use actual min_x if available
        } else {
            0.0  // Start from 0 if no artifacts detected
        };
        let clip_y = if self.content_min_y != f64::MAX && self.content_min_y > 50.0 {
            (self.content_min_y - 10.0).max(0.0)  // Add small padding, ensure non-negative
        } else if self.min_y != f64::MAX && self.min_y > 0.0 {
            self.min_y.max(0.0)  // Use actual min_y if available
        } else {
            0.0  // Start from 0 if no artifacts detected
        };
        let clip_width = if self.content_max_x != f64::MIN && self.content_max_x > clip_x {
            (self.content_max_x - clip_x + 20.0).max(vb_width - clip_x)  // Use full width if needed
        } else if self.max_x > clip_x {
            (self.max_x - clip_x + 20.0).max(vb_width - clip_x)
        } else {
            vb_width - clip_x  // Use full viewBox width
        };
        let clip_height = if self.content_max_y != f64::MIN && self.content_max_y > clip_y {
            (self.content_max_y - clip_y + 20.0).max(vb_height - clip_y)  // Use full height if needed
        } else if self.max_y > clip_y {
            (self.max_y - clip_y + 20.0).max(vb_height - clip_y)
        } else {
            vb_height - clip_y  // Use full viewBox height
        };
        
        eprintln!("Clip area: x={}, y={}, w={}, h={}, content_bounds=({}, {}) to ({}, {})", 
            clip_x, clip_y, clip_width, clip_height,
            self.content_min_x, self.content_min_y, self.content_max_x, self.content_max_y);
        
        // Create clip path to exclude unwanted paths from top-left corner
        use svg::node::element::{ClipPath, Rectangle as ClipRect};
        let clip_path = ClipPath::new()
            .set("id", "content-clip")
            .add(ClipRect::new()
                .set("x", clip_x)
                .set("y", clip_y)
                .set("width", clip_width)
                .set("height", clip_height));
        
        let mut document = Document::new()
            .set("width", vb_width.ceil() as u32)
            .set("height", vb_height.ceil() as u32)
            .set("viewBox", format!("{} {} {} {}", vb_x, vb_y, vb_width, vb_height))
            .add(clip_path);
        
        // Add elements with clip-path applied
        use svg::node::element::Group;
        let mut group = Group::new().set("clip-path", "url(#content-clip)");
        for element in self.elements {
            group = group.add(element);
        }
        document = document.add(group);

        document.to_string()
    }
}

