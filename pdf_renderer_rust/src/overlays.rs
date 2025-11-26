//! Overlay rendering
//! 
//! Handles rendering of overlay boxes (floating images/textboxes over paragraphs)

use crate::canvas::PdfCanvas;
use crate::types::Rect;
use crate::font_registry::FontRegistry;
use crate::image_registry::ImageRegistry;
use pdf_writer::{Pdf, Ref};
use serde_json;
use std::collections::HashMap;

/// Render overlay boxes
pub fn render_overlays(
    canvas: &mut PdfCanvas,
    pdf: &mut Pdf,
    fonts_registry: &mut FontRegistry,
    images_registry: &mut ImageRegistry,
    overlays: &[serde_json::Value],
    images_used_on_current_page: &mut HashMap<pdf_writer::Name<'static>, Ref>,
) -> Result<(), pyo3::PyErr> {
    // Deduplicate overlays by frame position and image path to avoid rendering the same overlay twice
    // Use String key instead of f64 tuple (f64 doesn't implement Hash)
    let mut seen_overlays: std::collections::HashSet<String> = std::collections::HashSet::new();
    
    for overlay in overlays {
        let overlay_obj = overlay.as_object().ok_or_else(|| {
            pyo3::PyErr::new::<pyo3::exceptions::PyValueError, _>("Overlay must be an object")
        })?;
        
        let kind = overlay_obj.get("kind")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        
        let frame_obj = overlay_obj.get("frame")
            .and_then(|f| f.as_object())
            .ok_or_else(|| {
                pyo3::PyErr::new::<pyo3::exceptions::PyValueError, _>("Overlay must have a frame")
            })?;
        
        let frame = Rect::new(
            frame_obj.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0),
            frame_obj.get("y").and_then(|v| v.as_f64()).unwrap_or(0.0),
            frame_obj.get("width").and_then(|v| v.as_f64()).unwrap_or(0.0),
            frame_obj.get("height").and_then(|v| v.as_f64()).unwrap_or(0.0),
        );
        
        let payload = overlay_obj.get("payload")
            .and_then(|p| p.as_object());
        
        // For image overlays, create a unique key based on frame position and image path
        if kind == "image" {
            let mut overlay_key = None;
            if let Some(payload_obj) = payload {
                // Try to get image path for deduplication
                let image_source = payload_obj.get("image")
                    .or_else(|| payload_obj.get("source"))
                    .or_else(|| payload_obj.get("content"))
                    .or_else(|| payload_obj.get("image_source"));
                
                eprintln!("   Overlay image candidate: payload_keys={:?} image_source={:?}", 
                    payload_obj.keys().collect::<Vec<_>>(),
                    image_source.is_some()
                );
                
                if let Some(img_src) = image_source {
                    let stream_key = img_src.as_object()
                        .and_then(|o| {
                            eprintln!("   Overlay image source keys={:?}", o.keys().collect::<Vec<_>>());
                            o.get("stream_key")
                        })
                        .and_then(|v| v.as_str());
                    eprintln!("   Overlay image stream_key={:?}", stream_key);
                    if let Some(key) = stream_key {
                        let cache_key = format!("{:.2}_{:.2}_stream_{}", 
                            (frame.x * 100.0).round() / 100.0,
                            (frame.y * 100.0).round() / 100.0,
                            key
                        );
                        overlay_key = Some(cache_key);
                    } else {
                        let img_path = img_src.as_str()
                            .or_else(|| {
                                img_src.as_object()
                                    .and_then(|o| o.get("path"))
                                    .and_then(|v| v.as_str())
                            });
                        
                        if let Some(path) = img_path {
                            // Use frame position (rounded to avoid floating point issues) and path as key
                            let key = format!("{:.2}_{:.2}_{}", 
                                (frame.x * 100.0).round() / 100.0,
                                (frame.y * 100.0).round() / 100.0,
                                path
                            );
                            overlay_key = Some(key);
                        }
                    }
                }
            }
            
            // Skip if we've already rendered this overlay
            if let Some(key) = overlay_key {
                if seen_overlays.contains(&key) {
                    continue; // Skip duplicate overlay
                }
                seen_overlays.insert(key);
            }
        }
        
        match kind {
            "image" => {
                // Try to get dimensions from overlay payload (image object)
                // Dimensions should be in payload.image.width/height (in EMU)
                let width_emu = payload.and_then(|p| p.get("image"))
                    .and_then(|img| img.as_object())
                    .and_then(|img_obj| img_obj.get("width"))
                    .and_then(|v| {
                        v.as_i64().map(|i| i as f64)
                            .or_else(|| v.as_f64())
                    })
                    .or_else(|| {
                        // Try from payload directly
                        payload.and_then(|p| p.get("width"))
                            .and_then(|v| {
                                v.as_i64().map(|i| i as f64)
                                    .or_else(|| v.as_f64())
                            })
                    });
                let height_emu = payload.and_then(|p| p.get("image"))
                    .and_then(|img| img.as_object())
                    .and_then(|img_obj| img_obj.get("height"))
                    .and_then(|v| {
                        v.as_i64().map(|i| i as f64)
                            .or_else(|| v.as_f64())
                    })
                    .or_else(|| {
                        // Try from payload directly
                        payload.and_then(|p| p.get("height"))
                            .and_then(|v| {
                                v.as_i64().map(|i| i as f64)
                                    .or_else(|| v.as_f64())
                            })
                    });
                
                if let (Some(w), Some(h)) = (width_emu, height_emu) {
                    eprintln!("   Overlay image dimensions from JSON: {}x{} EMU", w, h);
                }
                
                render_overlay_image(canvas, pdf, images_registry, &frame, payload, images_used_on_current_page, width_emu, height_emu)?;
            }
            "textbox" => {
                render_overlay_textbox(canvas, pdf, fonts_registry, images_registry, &frame, payload, images_used_on_current_page)?;
            }
            _ => {
                // Unknown overlay type, skip
            }
        }
    }
    
    Ok(())
}

fn render_overlay_image(
    canvas: &mut PdfCanvas,
    pdf: &mut Pdf,
    images_registry: &mut ImageRegistry,
    frame: &Rect,
    payload_opt: Option<&serde_json::Map<String, serde_json::Value>>,
    images_used_on_current_page: &mut HashMap<pdf_writer::Name<'static>, Ref>,
    width_emu: Option<f64>,
    height_emu: Option<f64>,
) -> Result<(), pyo3::PyErr> {
    if payload_opt.is_none() {
        return Ok(());
    }
    
    let payload = payload_opt.unwrap();
    
    // Get image source - try multiple locations
    let image_source = payload.get("image")
        .or_else(|| payload.get("source"))
        .or_else(|| payload.get("content"))
        .or_else(|| payload.get("image_source"));
    
    if image_source.is_none() {
        return Ok(());
    }
    
    let image_object = image_source.and_then(|s| s.as_object());
    // Try to get stream key or image path from various formats
    let stream_key = image_object
        .and_then(|o| o.get("stream_key"))
        .and_then(|v| v.as_str());
    let image_path = image_source
        .and_then(|s| s.as_str())
        .or_else(|| {
            image_object.and_then(|o| {
                o.get("path")
                    .or_else(|| o.get("image_path"))
                    .or_else(|| o.get("file_path"))
                    .or_else(|| o.get("src"))
                .and_then(|v| v.as_str())
            })
        });
    
    eprintln!(
        "Overlay image candidate stream_key={:?} path={:?}",
        stream_key,
        image_path
    );
    if stream_key.is_some() || image_path.is_some() {
        // Use dimensions passed as parameters (from overlay frame or payload)
        // If not provided, try to get from payload as fallback
        // payload is already &Map (after unwrap), so we use it directly
        let final_width_emu = width_emu.or_else(|| {
            payload
                .get("image")
                .and_then(|img| img.as_object())
                .and_then(|img_obj| img_obj.get("width"))
                .and_then(|v| {
                    v.as_i64().map(|i| i as f64)
                        .or_else(|| v.as_f64())
                })
                .or_else(|| {
                    // Try from payload directly
                    payload
                        .get("width")
                        .and_then(|v| {
                            v.as_i64().map(|i| i as f64)
                                .or_else(|| v.as_f64())
                        })
                })
        });
        let final_height_emu = height_emu.or_else(|| {
            payload
                .get("image")
                .and_then(|img| img.as_object())
                .and_then(|img_obj| img_obj.get("height"))
                .and_then(|v| {
                    v.as_i64().map(|i| i as f64)
                        .or_else(|| v.as_f64())
                })
                .or_else(|| {
                    // Try from payload directly
                    payload
                        .get("height")
                        .and_then(|v| {
                            v.as_i64().map(|i| i as f64)
                                .or_else(|| v.as_f64())
                        })
                })
        });
        
        if let (Some(w), Some(h)) = (final_width_emu, final_height_emu) {
            eprintln!("   Overlay image using dimensions: {}x{} EMU", w, h);
        }
        
        let image_result = if let Some(key) = stream_key {
            eprintln!("Requesting overlay image from stream key {}", key);
            images_registry.get_or_create_from_stream(pdf, key, final_width_emu, final_height_emu)
        } else {
            let path = image_path.unwrap_or_default();
            eprintln!("Requesting overlay image from path {}", path);
            images_registry.get_or_create_from_path_with_dims(pdf, path, final_width_emu, final_height_emu)
        };
        
        match image_result {
            Ok((_image_id, image_name)) => {
                eprintln!(
                    "Overlay image resolved name={} ref={:?}",
                    String::from_utf8_lossy(image_name.0),
                    _image_id
                );
                // Register image for current page
                images_used_on_current_page.insert(image_name, _image_id);
                
                // Use frame dimensions directly - frame should already be in PDF points
                // and account for the correct image size
                let render_width = frame.width;
                let render_height = frame.height;
                
                eprintln!("   Drawing overlay image: name={}, pos=({:.2}, {:.2}), size=({:.2}, {:.2})", 
                    String::from_utf8_lossy(image_name.0),
                    frame.x, frame.y, render_width, render_height);
                
                // Check if position is within reasonable page bounds (A4 is ~595x842 pt)
                // Log warning if image might be outside visible area
                if frame.y > 900.0 || frame.y < -100.0 {
                    eprintln!("   ⚠️  Warning: overlay Y position {:.2} seems outside normal page bounds (expected 0-842 for A4)", frame.y);
                }
                if frame.x > 700.0 || frame.x < -100.0 {
                    eprintln!("   ⚠️  Warning: overlay X position {:.2} seems outside normal page bounds (expected 0-595 for A4)", frame.x);
                }
                if render_width > 1000.0 || render_height > 1500.0 {
                    eprintln!("   ⚠️  Warning: overlay size {:.2}x{:.2} seems very large (expected <1000x1500 for A4)", render_width, render_height);
                }
                
                canvas.draw_image(image_name, frame.x, frame.y, render_width, render_height);
                eprintln!("   Overlay image drawn successfully");
            }
            Err(e) => {
                // Log error but don't fail - WMF files are not supported
                let error_msg = format!("{}", e);
                if error_msg.contains("WMF") {
                    let label = image_path.unwrap_or("<overlay>");
                    log::warn!("Skipping WMF image (not supported): {}", label);
                } else {
                    let label = image_path.unwrap_or("<overlay>");
                    log::warn!("Failed to load image {}: {}", label, error_msg);
                }
            }
        }
    }
    
    Ok(())
}

fn render_overlay_textbox(
    canvas: &mut PdfCanvas,
    pdf: &mut Pdf,
    fonts_registry: &mut FontRegistry,
    images_registry: &mut ImageRegistry,
    frame: &Rect,
    payload: Option<&serde_json::Map<String, serde_json::Value>>,
    images_used_on_current_page: &mut HashMap<pdf_writer::Name<'static>, Ref>,
) -> Result<(), pyo3::PyErr> {
    if payload.is_none() {
        return Ok(());
    }
    
    let payload = payload.unwrap();
    
    // Check for ParagraphLayout payload
    let has_layout = payload.get("layout_payload").is_some()
        || payload.get("_layout_payload").is_some()
        || payload.get("lines").is_some();
    
    if has_layout {
        // Get layout_payload from content
        let layout_payload = payload.get("layout_payload")
            .or_else(|| payload.get("_layout_payload"))
            .or_else(|| payload.get("lines"))
            .unwrap_or(&serde_json::Value::Null);
        
        let default_style = serde_json::json!({});
        let style = payload.get("style").unwrap_or(&default_style);
        
        // Render using render_paragraph_from_layout
        crate::renderer::PdfRenderer::render_paragraph_from_layout(
            canvas,
            pdf,
            fonts_registry,
            images_registry,
            images_used_on_current_page,
            frame,
            layout_payload,
            style,
            1, // current_page (overlays don't have page context)
            1, // total_pages
        )?;
    } else {
        // Simple text fallback - skip for now (draw_text is deprecated)
        // Overlays should use layout_payload for proper rendering
    }
    
    Ok(())
}

