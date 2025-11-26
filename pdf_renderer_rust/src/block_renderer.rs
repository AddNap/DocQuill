//! BlockRenderer – facade for rendering layout blocks onto PdfCanvas
use pyo3::prelude::*;
use pdf_writer::{Pdf, Ref, Name};
use std::collections::HashMap;
use serde_json;
use crate::canvas::PdfCanvas;
use crate::types::{LayoutBlock, Rect, Color};
use crate::geometry::parse_color;
use crate::font_registry::FontRegistry;
use crate::image_registry::ImageRegistry;
use log::warn;

pub struct BlockRenderer;

impl BlockRenderer {
    pub fn render_block(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts: &mut FontRegistry,
        images: &mut ImageRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        block: &LayoutBlock,
        current_page: u32,
        total_pages: u32,
    ) -> PyResult<()> {
        match block.block_type.as_str() {
            "paragraph" => Self::render_paragraph(canvas, pdf, fonts, images, block, current_page, total_pages),
            "table" => Self::render_table(canvas, pdf, fonts, images, images_used_on_current_page, block, current_page, total_pages),
            "image" => Self::render_image(canvas, pdf, fonts, images, images_used_on_current_page, block),
            "header" | "footer" | "footnotes" | "endnotes" | "decorator" => {
                // Placeholder – can be specialized later
                Self::render_generic(canvas, block)
            }
            _ => Self::render_generic(canvas, block),
        }
    }

    pub(crate) fn render_paragraph(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts: &mut FontRegistry,
        images: &mut ImageRegistry,
        block: &LayoutBlock,
        current_page: u32,
        total_pages: u32,
    ) -> PyResult<()> {
        // Delegate to renderer.rs implementation (now uses FontRegistry and ImageRegistry)
        let mut images_used_on_current_page: HashMap<Name<'static>, Ref> = HashMap::new();
        crate::renderer::PdfRenderer::render_paragraph(
            canvas,
            pdf,
            fonts,
            images,
            &mut images_used_on_current_page,
            block,
            current_page,
            total_pages,
        )
    }

    pub fn render_table(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        fonts: &mut FontRegistry,
        images: &mut ImageRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        block: &LayoutBlock,
        current_page: u32,
        total_pages: u32,
    ) -> PyResult<()> {
        let rect = &block.frame;
        let content = &block.content;
        
        eprintln!("🔍 Rendering table block: rect={:?}, content_keys={:?}", rect, content.as_object().map(|o| o.keys().collect::<Vec<_>>()));
        
        // Draw table background (if specified)
        if let Some(bg_color) = block.style.get("background_color") {
            let color = parse_color(bg_color);
            canvas.save_state();
            canvas.set_fill_color(color);
            canvas.rect(*rect, true, false);
            canvas.restore_state();
        }
        
        // Draw table border (if specified, or default thin border)
        if let Some(border) = block.style.get("border") {
            Self::draw_border(canvas, rect, border)?;
        } else if let Some(borders) = block.style.get("borders") {
            Self::draw_borders(canvas, rect, borders)?;
        } else {
            // Default: draw thin border around table
            canvas.save_state();
            canvas.set_stroke_color(Color::rgb(0.0, 0.0, 0.0));
            canvas.set_line_width(0.5);
            canvas.rect(*rect, false, true);
            canvas.restore_state();
        }
        
        // Get col_widths and row_heights from layout_info
        let layout_info = content.get("layout_info").and_then(|v| v.as_object());
        let col_widths: Vec<f64> = layout_info
            .and_then(|li| li.get("col_widths"))
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_f64()).collect())
            .unwrap_or_else(|| {
                // Fallback: equal widths
                let num_cols = content.get("rows")
                    .and_then(|v| v.as_array())
                    .and_then(|rows| rows.first())
                    .and_then(|row| row.get("cells"))
                    .and_then(|v| v.as_array())
                    .map(|cells| cells.len())
                    .unwrap_or(1);
                vec![rect.width / num_cols as f64; num_cols]
            });
        
        let row_heights: Vec<f64> = layout_info
            .and_then(|li| li.get("row_heights"))
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_f64()).collect())
            .unwrap_or_else(|| {
                // Fallback: equal heights
                let num_rows = content.get("rows")
                    .and_then(|v| v.as_array())
                    .map(|rows| rows.len())
                    .unwrap_or(1);
                vec![rect.height / num_rows as f64; num_rows]
            });
        
        eprintln!("  Table layout: {} cols (widths: {:?}), {} rows (heights: {:?})", col_widths.len(), col_widths, row_heights.len(), row_heights);
        
        // Use provided images_used_on_current_page (no need to create new one)
        
        // Get table rows
        if let Some(rows) = content.get("rows").and_then(|v| v.as_array()) {
            eprintln!("✅ Found {} rows in table", rows.len());
            // Limit number of rows to prevent infinite loops (safety limit: 1000 rows)
            let max_rows = rows.len().min(1000);
            if rows.len() > max_rows {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Table has too many rows: {} (max 1000)", rows.len())
                ));
            }
            
            // Track which cells are merged (to skip rendering merged cells)
            let mut rendered_cells: std::collections::HashSet<(usize, usize)> = std::collections::HashSet::new();
            
            for (row_idx, row) in rows.iter().take(max_rows).enumerate() {
                if let Some(cells) = row.get("cells").and_then(|v| v.as_array()) {
                    eprintln!("  Row {}: {} cells", row_idx, cells.len());
                    // Limit number of cells per row (safety limit: 100 cells per row)
                    let max_cells = cells.len().min(100);
                    if cells.len() > max_cells {
                        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                            format!("Row {} has too many cells: {} (max 100)", row_idx, cells.len())
                        ));
                    }
                    
                    let mut col_idx = 0;
                    
                    for (_cell_idx, cell) in cells.iter().take(max_cells).enumerate() {
                        // Get grid_span (colspan) - how many columns this cell spans
                        let grid_span = cell.get("grid_span")
                            .or_else(|| cell.get("gridSpan"))
                            .and_then(|v| {
                                if let Some(n) = v.as_u64() {
                                    Some(n as usize)
                                } else if let Some(s) = v.as_str() {
                                    s.parse::<usize>().ok()
                                } else {
                                    None
                                }
                            })
                            .unwrap_or(1);
                        
                        // Get vertical_merge_type (rowspan) - "restart" means start of merge, "continue" means continuation
                        let vertical_merge_type = cell.get("vertical_merge_type")
                            .or_else(|| cell.get("vMerge"))
                            .and_then(|v| {
                                if let Some(s) = v.as_str() {
                                    Some(s)
                                } else if let Some(obj) = v.as_object() {
                                    obj.get("val").and_then(|v| v.as_str())
                                } else {
                                    None
                                }
                            });
                        
                        // Skip cells that are continuations of vertical merges
                        if vertical_merge_type == Some("continue") {
                            col_idx += grid_span;
                            continue;
                        }
                        
                        // Calculate rowspan by checking subsequent rows
                        let mut cell_rowspan = 1;
                        if vertical_merge_type == Some("restart") {
                            // Count how many rows this cell spans
                            // Limit to prevent infinite loops (max 100 rows span)
                            let max_rowspan_check = (row_idx + 1 + 100).min(rows.len());
                            for next_row_idx in (row_idx + 1)..max_rowspan_check {
                                if let Some(next_row) = rows.get(next_row_idx) {
                                    if let Some(next_cells) = next_row.get("cells").and_then(|v| v.as_array()) {
                                        // Find cell at same column position (accounting for grid_span)
                                        let mut next_col_pos = 0;
                                        let mut found_continue = false;
                                        
                                        for next_cell in next_cells {
                                            let next_grid_span = next_cell.get("grid_span")
                                                .or_else(|| next_cell.get("gridSpan"))
                                                .and_then(|v| {
                                                    if let Some(n) = v.as_u64() {
                                                        Some(n as usize)
                                                    } else if let Some(s) = v.as_str() {
                                                        s.parse::<usize>().ok()
                                                    } else {
                                                        None
                                                    }
                                                })
                                                .unwrap_or(1);
                                            
                                            let next_vmerge = next_cell.get("vertical_merge_type")
                                                .or_else(|| next_cell.get("vMerge"))
                                                .and_then(|v| {
                                                    if let Some(s) = v.as_str() {
                                                        Some(s)
                                                    } else if let Some(obj) = v.as_object() {
                                                        obj.get("val").and_then(|v| v.as_str())
                                                    } else {
                                                        None
                                                    }
                                                });
                                            
                                            // Check if this cell is at the right column position
                                            if next_col_pos == col_idx && next_vmerge == Some("continue") {
                                                cell_rowspan += 1;
                                                found_continue = true;
                                                break;
                                            }
                                            
                                            next_col_pos += next_grid_span;
                                        }
                                        
                                        if !found_continue {
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Check if this cell should be rendered (not already rendered as part of a merge)
                        if rendered_cells.contains(&(row_idx, col_idx)) {
                            col_idx += grid_span;
                            continue;
                        }
                        
                        // Mark all cells covered by this cell as rendered
                        for r in row_idx..(row_idx + cell_rowspan) {
                            for c in col_idx..(col_idx + grid_span) {
                                rendered_cells.insert((r, c));
                            }
                        }
                        
                        // Calculate cell rect if not present
                        let cell_rect = if let Some(cell_rect_json) = cell.get("rect") {
                            // Use existing rect
                            serde_json::from_value(cell_rect_json.clone())
                                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                                    format!("Failed to parse cell rect: {}", e)
                                ))?
                        } else {
                            // Calculate rect from col_widths and row_heights
                            // Calculate cell width (sum of column widths it spans)
                            let cell_width = if col_idx + grid_span <= col_widths.len() {
                                col_widths[col_idx..col_idx + grid_span].iter().sum()
                            } else if col_idx < col_widths.len() {
                                col_widths[col_idx]
                            } else {
                                rect.width / col_widths.len() as f64 * grid_span as f64
                            };
                            
                            // Calculate cell height (sum of row heights it spans)
                            let cell_height = if row_idx + cell_rowspan <= row_heights.len() {
                                row_heights[row_idx..row_idx + cell_rowspan].iter().sum()
                            } else if row_idx < row_heights.len() {
                                row_heights[row_idx]
                            } else {
                                rect.height / row_heights.len() as f64 * cell_rowspan as f64
                            };
                            
                            // Calculate X position (sum of column widths before this cell)
                            let cell_x = rect.x + col_widths[0..col_idx].iter().sum::<f64>();
                            
                            // Calculate Y position (top of table minus sum of row heights before this cell)
                            let cell_y = rect.top() - row_heights[0..row_idx].iter().sum::<f64>() - cell_height;
                            
                            Rect::new(cell_x, cell_y, cell_width, cell_height)
                        };
                        
                        eprintln!("    Cell [{}, {}]: rect={:?}, grid_span={}, rowspan={}", row_idx, col_idx, cell_rect, grid_span, cell_rowspan);
                        
                        // Draw cell background
                        if let Some(bg_color) = cell.get("background_color") {
                            let color = parse_color(bg_color);
                            canvas.save_state();
                            canvas.set_fill_color(color);
                            canvas.rect(cell_rect, true, false);
                            canvas.restore_state();
                        }
                        
                        // Draw cell border
                        if let Some(border) = cell.get("border") {
                            Self::draw_border(canvas, &cell_rect, border)?;
                        } else if let Some(borders) = cell.get("borders") {
                            Self::draw_borders(canvas, &cell_rect, borders)?;
                        } else {
                            // Default: draw thin border if no border specified
                            canvas.save_state();
                            canvas.set_stroke_color(Color::rgb(200.0 / 255.0, 200.0 / 255.0, 200.0 / 255.0));
                            canvas.set_line_width(0.5);
                            canvas.rect(cell_rect, false, true);
                            canvas.restore_state();
                        }
                        
                        // Draw cell content - check for paragraphs, content array, or simple text
                        let cell_content = cell.get("content");
                        let cell_style = cell.get("style");
                        
                        eprintln!("      Cell content type: paragraphs={}, content_array={}, text={}, content_obj={}", 
                            cell.get("paragraphs").is_some(),
                            cell_content.and_then(|c| c.as_array()).is_some(),
                            cell_content.and_then(|c| c.as_str()).is_some(),
                            cell_content.and_then(|c| c.as_object()).is_some()
                        );
                        
                        // Check if cell has paragraphs (list of paragraph blocks)
                        if let Some(paragraphs) = cell.get("paragraphs").and_then(|v| v.as_array()) {
                            eprintln!("      Rendering {} paragraphs in cell", paragraphs.len());
                            // Render paragraphs in cell
                            crate::renderer::PdfRenderer::render_cell_paragraphs(
                                canvas, pdf, fonts, images,
                                images_used_on_current_page, &cell_rect, paragraphs, cell_style,
                                current_page, total_pages,
                            )?;
                        } else if let Some(content_array) = cell_content.and_then(|c| c.as_array()) {
                            // Content is an array (paragraphs, images, etc.)
                            eprintln!("      Rendering {} items from content array in cell", content_array.len());
                            
                            // Log first item structure for debugging
                            if let Some(first_item) = content_array.first() {
                                if let Some(obj) = first_item.as_object() {
                                    let keys: Vec<_> = obj.keys().collect();
                                    eprintln!("      First item keys: {:?}", keys);
                                    if let Some(layout_payload) = obj.get("layout_payload").or_else(|| obj.get("_layout_payload")) {
                                        if let Some(layout_obj) = layout_payload.as_object() {
                                            let layout_keys: Vec<_> = layout_obj.keys().collect();
                                            eprintln!("      layout_payload keys: {:?}", layout_keys);
                                            if let Some(lines) = layout_obj.get("lines") {
                                                if let Some(lines_arr) = lines.as_array() {
                                                    eprintln!("      layout_payload has {} lines", lines_arr.len());
                                                    // Check for inline images in first line
                                                    if let Some(first_line) = lines_arr.first() {
                                                        if let Some(line_obj) = first_line.as_object() {
                                                            if let Some(items) = line_obj.get("items") {
                                                                if let Some(items_arr) = items.as_array() {
                                                                    eprintln!("      First line has {} items", items_arr.len());
                                                                    for (idx, item) in items_arr.iter().enumerate() {
                                                                        if let Some(item_obj) = item.as_object() {
                                                                            let item_kind = item_obj.get("kind").and_then(|v| v.as_str());
                                                                            if item_kind == Some("inline_image") {
                                                                                eprintln!("      Item {} is inline_image", idx);
                                                                            }
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Extract paragraphs from content array
                            let paragraphs: Vec<serde_json::Value> = content_array.iter()
                                .filter(|item| {
                                    // Check if item is a paragraph (has type="paragraph" or has layout_payload or has runs/children)
                                    if let Some(obj) = item.as_object() {
                                        obj.get("type").and_then(|v| v.as_str()) == Some("paragraph")
                                            || obj.get("layout_payload").is_some()
                                            || obj.get("_layout_payload").is_some()
                                            || obj.get("lines").is_some()
                                            || obj.get("runs").is_some()
                                            || obj.get("children").is_some()
                                    } else {
                                        false
                                    }
                                })
                                .cloned()
                                .collect();
                            
                            if !paragraphs.is_empty() {
                                eprintln!("      Found {} paragraphs in content array", paragraphs.len());
                                crate::renderer::PdfRenderer::render_cell_paragraphs(
                                    canvas, pdf, fonts, images,
                                    images_used_on_current_page, &cell_rect, &paragraphs, cell_style,
                                    current_page, total_pages,
                                )?;
                            } else {
                                eprintln!("      No paragraphs found in content array - treating all items as paragraphs");
                                // Fallback: treat all items as paragraphs
                                let all_items: Vec<serde_json::Value> = content_array.iter().cloned().collect();
                                crate::renderer::PdfRenderer::render_cell_paragraphs(
                                    canvas, pdf, fonts, images,
                                    images_used_on_current_page, &cell_rect, &all_items, cell_style,
                                    current_page, total_pages,
                                )?;
                            }
                        } else if let Some(_text) = cell_content.and_then(|c| c.as_str()) {
                            // Simple text content - draw_text is deprecated, skip for now
                            // The assembler should provide layout_payload instead
                            eprintln!("      ⚠️  Simple text in cell (draw_text deprecated) - skipping");
                        } else if let Some(content_obj) = cell_content.and_then(|c| c.as_object()) {
                            // Content might be a dict with layout_payload or text
                            if content_obj.get("layout_payload").is_some() 
                                || content_obj.get("_layout_payload").is_some()
                                || content_obj.get("lines").is_some() {
                                // Has ParagraphLayout payload
                                let default_style = serde_json::json!({});
                                let cell_style = cell_style.unwrap_or(&default_style);
                                crate::renderer::PdfRenderer::render_paragraph_from_layout(
                                    canvas, pdf, fonts, images,
                                    images_used_on_current_page, &cell_rect, cell_content.unwrap(), cell_style,
                                    current_page, total_pages,
                                )?;
                            } else if let Some(_text) = content_obj.get("text").and_then(|v| v.as_str()) {
                                // Has text field - draw_text is deprecated, skip for now
                                eprintln!("      ⚠️  Simple text in cell (draw_text deprecated) - skipping");
                            }
                        }
                        
                        col_idx += grid_span;
                    }
                }
            }
        } else {
            eprintln!("⚠️  Table block has no 'rows' array in content");
            // Try to render table background and border even if no rows
            if let Some(bg_color) = content.get("background_color") {
                let color = parse_color(bg_color);
                canvas.save_state();
                canvas.set_fill_color(color);
                canvas.rect(*rect, true, false);
                canvas.restore_state();
            }
            
            if let Some(border) = content.get("border") {
                Self::draw_border(canvas, rect, border)?;
            } else if let Some(borders) = content.get("borders") {
                Self::draw_borders(canvas, rect, borders)?;
            }
        }
        
        Ok(())
    }

    /// Render image directly with parameters (no LayoutBlock needed)
    pub fn render_image_direct(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        _fonts: &mut FontRegistry,
        images: &mut ImageRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        image_path: &str,
        width_emu: Option<f64>,
        height_emu: Option<f64>,
    ) -> PyResult<()> {
        // Load image - returns (Ref, Name)
        let (image_id, image_name) = images.get_or_create_from_path_with_dims(
            pdf,
            image_path,
            width_emu,
            height_emu,
        )?;
        
        // Register image for current page
        if !images_used_on_current_page.contains_key(&image_name) {
            images_used_on_current_page.insert(image_name.clone(), image_id);
        }
        
        // Draw image
        canvas.draw_image(image_name, x, y, width, height);
        
        Ok(())
    }
    
    pub fn render_image(
        canvas: &mut PdfCanvas,
        pdf: &mut Pdf,
        _fonts: &mut FontRegistry,
        images: &mut ImageRegistry,
        images_used_on_current_page: &mut HashMap<Name<'static>, Ref>,
        block: &LayoutBlock,
    ) -> PyResult<()> {
        let rect = &block.frame;
        let content = &block.content;

        // Try to resolve path from common fields
        let path_opt = content.get("path")
            .and_then(|v| v.as_str())
            .or_else(|| content.get("image_path").and_then(|v| v.as_str()))
            .or_else(|| content.get("data").and_then(|d| d.get("path")).and_then(|v| v.as_str()));

        if let Some(path) = path_opt {
            // Get or create image XObject via registry
            let (id, name) = images.get_or_create_from_path(pdf, path)?;
            
            // Add image to page resources
            images_used_on_current_page.insert(name, id);

            // Determine target size (preserve aspect ratio if width/height provided)
            let img_w = content.get("width").and_then(|v| v.as_f64()).unwrap_or(rect.width);
            let img_h = content.get("height").and_then(|v| v.as_f64()).unwrap_or(rect.height);
            let scale_x = rect.width / img_w;
            let scale_y = rect.height / img_h;
            let scale = scale_x.min(scale_y).min(1.0);
            let draw_w = img_w * scale;
            let draw_h = img_h * scale;
            let x = rect.x + (rect.width - draw_w) / 2.0;
            let y = rect.y + (rect.height - draw_h) / 2.0;

            canvas.draw_image(name, x, y, draw_w, draw_h);
            Ok(())
        } else {
            // No path – log warning
            warn!("Image block has no path in content: {:?}", content.as_object().map(|o| o.keys().collect::<Vec<_>>()));
            Ok(())
        }
    }

    fn render_generic(_canvas: &mut PdfCanvas, _block: &LayoutBlock) -> PyResult<()> {
        // TODO: Fallback drawing if needed
        Ok(())
    }

    /// Draw border (helper function for table rendering)
    fn draw_border(canvas: &mut PdfCanvas, rect: &Rect, border: &serde_json::Value) -> PyResult<()> {
        let width = border.get("width").and_then(|v| v.as_f64()).unwrap_or(1.0);
        let default_border_color = serde_json::json!("#000000");
        let color = border.get("color").unwrap_or(&default_border_color);
        let style_name = border.get("style")
            .or_else(|| border.get("val"))
            .and_then(|v| v.as_str())
            .unwrap_or("solid");
        let radius = border.get("radius").and_then(|v| v.as_f64()).unwrap_or(0.0);
        
        canvas.save_state();
        canvas.set_stroke_color(parse_color(color));
        canvas.set_line_width(width);
        
        // Apply border style
        match style_name.to_lowercase().as_str() {
            "dashed" | "dash" => canvas.set_dash(vec![6.0, 3.0], 0.0),
            "dotted" | "dot" => canvas.set_dash(vec![1.0, 2.0], 0.0),
            "double" => {
                // Double border: draw two lines
                let half_width = width / 2.0;
                canvas.set_line_width(half_width);
                if radius > 0.0 {
                    canvas.round_rect(*rect, radius, false, true);
                    let inner_rect = Rect::new(
                        rect.x + half_width,
                        rect.y + half_width,
                        rect.width - width,
                        rect.height - width,
                    );
                    canvas.round_rect(inner_rect, radius.max(0.0), false, true);
                } else {
                    canvas.rect(*rect, false, true);
                    let inner_rect = Rect::new(
                        rect.x + half_width,
                        rect.y + half_width,
                        rect.width - width,
                        rect.height - width,
                    );
                    canvas.rect(inner_rect, false, true);
                }
                canvas.restore_state();
                return Ok(());
            },
            _ => {
                // solid or unknown - no dash pattern
            }
        }
        
        // Draw border rectangle
        if radius > 0.0 {
            canvas.round_rect(*rect, radius, false, true);
        } else {
            canvas.rect(*rect, false, true);
        }
        
        canvas.restore_state();
        
        Ok(())
    }

    /// Draw borders (all sides) - helper function for table rendering
    fn draw_borders(canvas: &mut PdfCanvas, rect: &Rect, borders: &serde_json::Value) -> PyResult<()> {
        let sides = ["top", "bottom", "left", "right"];
        
        for side in &sides {
            if let Some(border) = borders.get(side) {
                let width = border.get("width").and_then(|v| v.as_f64()).unwrap_or(1.0);
                let default_color = serde_json::json!("#000000");
                let color = border.get("color").unwrap_or(&default_color);
                
                canvas.save_state();
                canvas.set_stroke_color(parse_color(color));
                canvas.set_line_width(width);
                
                match *side {
                    "top" => canvas.line(rect.left(), rect.top(), rect.right(), rect.top()),
                    "bottom" => canvas.line(rect.left(), rect.bottom(), rect.right(), rect.bottom()),
                    "left" => canvas.line(rect.left(), rect.bottom(), rect.left(), rect.top()),
                    "right" => canvas.line(rect.right(), rect.bottom(), rect.right(), rect.top()),
                    _ => {}
                }
                canvas.restore_state();
            }
        }
        
        Ok(())
    }
}


