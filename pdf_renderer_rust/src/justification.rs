//! Text justification utilities
//! 
//! Handles advanced text justification with word spacing

use serde_json;

/// Calculate word spacing for justified text
pub fn calculate_word_spacing(
    line_items: &[serde_json::Value],
    available_width: f64,
    content_width: f64,
) -> f64 {
    let extra_space = (available_width - content_width).max(0.0);
    
    if extra_space <= 0.1 {
        return 0.0;
    }
    
    // Count spaces in line
    let mut space_count = 0;
    
    for item in line_items {
        let item_data = item.get("data")
            .and_then(|d| d.as_object());
        
        if let Some(data) = item_data {
            // Check if item has space_count
            if let Some(count) = data.get("space_count").and_then(|v| v.as_i64()) {
                space_count += count as usize;
            } else {
                // Count spaces in text
                let text = data.get("text")
                    .or_else(|| data.get("display"))
                    .or_else(|| data.get("value"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                
                space_count += text.matches(' ').count();
            }
        }
    }
    
    if space_count > 0 {
        extra_space / space_count as f64
    } else {
        0.0
    }
}

/// Apply word spacing to line items
pub fn apply_word_spacing(
    items: &[serde_json::Value],
    word_spacing: f64,
) -> Vec<(usize, f64)> {
    let mut adjustments = Vec::new();
    let mut cumulative_extra = 0.0;
    
    for (idx, item) in items.iter().enumerate() {
        let item_data = item.get("data")
            .and_then(|d| d.as_object());
        
        if let Some(data) = item_data {
            let space_count = data.get("space_count")
                .and_then(|v| v.as_i64())
                .unwrap_or(0) as usize;
            
            if space_count > 0 {
                cumulative_extra += word_spacing * space_count as f64;
            } else {
                // Count spaces in text
                let text = data.get("text")
                    .or_else(|| data.get("display"))
                    .or_else(|| data.get("value"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                
                let spaces = text.matches(' ').count();
                if spaces > 0 {
                    cumulative_extra += word_spacing * spaces as f64;
                }
            }
            
            if cumulative_extra.abs() > 0.01 {
                adjustments.push((idx, cumulative_extra));
            }
        }
    }
    
    adjustments
}

