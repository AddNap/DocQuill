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
        }
    }
    
    fn update_bounds(&mut self, x: f64, y: f64) {
        if self.auto_viewbox {
            // Skip very small coordinates - they're likely relative coords misinterpreted as absolute
            // or artifacts from EMF parsing. Real content typically starts at larger coordinates.
            if x < 50.0 && y < 50.0 {
                return;  // Skip this point for bounds calculation
            }
            self.min_x = self.min_x.min(x);
            self.min_y = self.min_y.min(y);
            self.max_x = self.max_x.max(x);
            self.max_y = self.max_y.max(y);
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
        // Parse path to extract coordinates for bounds and filtering
        let parts: Vec<&str> = path_data.split_whitespace().collect();
        let mut coords: Vec<(f64, f64)> = Vec::new();
        let mut i = 0;
        
        while i < parts.len() {
            match parts[i] {
                "M" | "L" => {
                    if i + 2 < parts.len() {
                        if let (Ok(x), Ok(y)) = (parts[i+1].parse::<f64>(), parts[i+2].parse::<f64>()) {
                            coords.push((x, y));
                        }
                        i += 3;
                    } else {
                        i += 1;
                    }
                }
                "C" => {
                    // C x1 y1 x2 y2 x3 y3 - only endpoint (x3, y3) matters for path analysis
                    if i + 6 < parts.len() {
                        if let (Ok(x), Ok(y)) = (parts[i+5].parse::<f64>(), parts[i+6].parse::<f64>()) {
                            coords.push((x, y));
                        }
                        i += 7;
                    } else {
                        i += 1;
                    }
                }
                "Z" => {
                    i += 1;
                }
                _ => {
                    i += 1;
                }
            }
        }
        
        // Check if path uses L (lineto) commands - bezier curves are real shapes
        let uses_lineto = path_data.contains(" L ") || 
                         (path_data.starts_with("M ") && 
                          path_data.len() > 10 && 
                          !path_data.contains(" C "));
        
        // Filter artifact paths where most points after the first have y=0 or very small y
        // This pattern indicates relative coordinates misinterpreted as absolute
        // Real shapes don't have multiple consecutive points at y=0
        if uses_lineto && coords.len() >= 3 {
            let zero_y_count = coords.iter().skip(1).filter(|(_, y)| *y < 1.0).count();
            let non_first_count = coords.len() - 1;
            
            // If most points after first have y≈0, it's an artifact (filter entire path)
            if zero_y_count >= non_first_count / 2 && zero_y_count >= 2 {
                return;
            }
        }
        
        // Modify paths starting near origin - remove first segment instead of filtering entire path
        // Pattern: M small_x 0 L big_x big_y ... -> M big_x big_y ...
        let mut final_path_data = path_data.to_string();
        if uses_lineto && coords.len() >= 2 {
            let (start_x, start_y) = coords[0];
            let starts_near_origin = start_x < 10.0 && start_y < 1.0;
            
            if starts_near_origin {
                let (x2, y2) = coords[1];
                let first_seg_dist = ((x2 - start_x).powi(2) + (y2 - start_y).powi(2)).sqrt();
                
                // If first segment is long, remove it by starting path from second point
                if first_seg_dist > 200.0 {
                    // Find "M x y L" pattern and replace with "M" at second point
                    let parts: Vec<&str> = path_data.split_whitespace().collect();
                    if parts.len() >= 6 && parts[0] == "M" && parts[3] == "L" {
                        // Rebuild path: M second_x second_y rest...
                        let rest = parts[6..].join(" ");
                        final_path_data = format!("M {} {} {}", parts[4], parts[5], rest);
                    }
                }
            }
        }
        
        // Update bounds with valid coordinates (skip first if it was near origin)
        for (x, y) in &coords {
            self.update_bounds(*x, *y);
        }
        
        // Add path to SVG (use modified path if first segment was removed)
        let mut path = Path::new().set("d", final_path_data.as_str());
        
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
        // Use actual content bounds as viewBox origin - this removes empty margins
        let (vb_x, vb_y, vb_width, vb_height) = if self.min_x != f64::MAX && self.max_x > self.min_x && 
                                                   self.min_y != f64::MAX && self.max_y > self.min_y {
            // Use actual content bounds - this crops out empty margins
            let content_width = self.max_x - self.min_x;
            let content_height = self.max_y - self.min_y;
            (self.min_x, self.min_y, content_width, content_height)
        } else {
            // Fallback to rclFrame dimensions starting at 0,0
            (0.0, 0.0, self.width as f64, self.height as f64)
        };
        
        // SVG dimensions: use rclFrame aspect ratio but scale up for quality
        let scale_factor = 2.0_f64.max(vb_width / self.width as f64).max(vb_height / self.height as f64);
        let svg_width = (self.width as f64 * scale_factor).ceil() as u32;
        let svg_height = (self.height as f64 * scale_factor).ceil() as u32;

        let mut document = Document::new()
            .set("width", svg_width)
            .set("height", svg_height)
            .set("viewBox", format!("{:.2} {:.2} {:.2} {:.2}", vb_x, vb_y, vb_width, vb_height))
            .set("preserveAspectRatio", "none");
        
        for element in self.elements {
            document = document.add(element);
        }

        document.to_string()
    }
}
