//! Field code resolution
//! 
//! Handles resolution of field codes like PAGE, NUMPAGES, DATE, TIME, etc.

use serde_json;

/// Resolve field code to text value
/// Supports PAGE, NUMPAGES, DATE, TIME, and other field types
pub fn resolve_field_text(
    field_info: Option<&serde_json::Map<String, serde_json::Value>>,
    current_page: u32,
    total_pages: u32,
) -> String {
    if field_info.is_none() {
        return String::new();
    }
    
    let field = field_info.unwrap();
    
    // Get field type - try multiple keys
    let field_type = field.get("field_type")
        .or_else(|| field.get("type"))
        .or_else(|| field.get("fieldType"))
        .or_else(|| field.get("name"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_uppercase())
        .unwrap_or_else(|| String::new());
    
    // Get instruction - try multiple keys
    let instruction = field.get("instruction")
        .or_else(|| field.get("instr"))
        .or_else(|| field.get("code"))
        .or_else(|| field.get("field_code"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_uppercase())
        .unwrap_or_else(|| String::new());
    
    // Detect field type from instruction if not set
    let detected_type = if field_type.is_empty() && !instruction.is_empty() {
        if instruction.contains("PAGE") {
            "PAGE"
        } else if instruction.contains("NUMPAGES") || instruction.contains("NUM PAGES") {
            "NUMPAGES"
        } else if instruction.contains("DATE") {
            "DATE"
        } else if instruction.contains("TIME") {
            "TIME"
        } else {
            ""
        }
    } else {
        field_type.as_str()
    };
    
    // Resolve field value based on type
    match detected_type {
        "PAGE" => {
            // Return current page number
            let page_num = current_page.max(1);
            format!("{}", page_num)
        }
        "NUMPAGES" | "NUM PAGES" => {
            // Return total page count
            let total = total_pages.max(1);
            format!("{}", total)
        }
            "DATE" => {
                // Return current date (format: DD.MM.YYYY)
                // Use simple date formatting without external dependencies
                let now = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs();
                // Simple date calculation (approximate)
                let days_since_epoch = now / 86400;
                
                // Simple date formatting (approximate, doesn't account for leap years)
                // For now, use a placeholder - proper date formatting requires chrono
                let day = (days_since_epoch % 28) + 1;
                let month = ((days_since_epoch / 28) % 12) + 1;
                let year = 1970 + (days_since_epoch / 365);
                format!("{:02}.{:02}.{}", day, month, year)
            }
        "TIME" => {
            // Return current time (format: HH:MM:SS)
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs();
            let seconds_today = now % 86400;
            let hours = seconds_today / 3600;
            let minutes = (seconds_today % 3600) / 60;
            let seconds = seconds_today % 60;
            format!("{:02}:{:02}:{:02}", hours, minutes, seconds)
        }
        _ => {
            // Fallback: use result, value, display, or text
            field.get("result")
                .or_else(|| field.get("value"))
                .or_else(|| field.get("display"))
                .or_else(|| field.get("text"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        }
    }
}

