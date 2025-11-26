//! Helper functions for safe JSON parsing
//!
//! These functions provide safe access to JSON values with proper error handling,
//! avoiding unwrap() and providing clear error messages.

use crate::error::{RendererError, RendererResult};
use serde_json::Value;

/// Safely get a f64 value from JSON object
pub fn get_f64(obj: &Value, key: &str) -> RendererResult<f64> {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .ok_or_else(|| RendererError::InvalidValue(
            key.to_string(),
            format!("Expected f64, got: {:?}", obj.get(key))
        ))
}

/// Safely get a f64 value from JSON object with default
pub fn get_f64_or(obj: &Value, key: &str, default: f64) -> f64 {
    obj.get(key)
        .and_then(|v| v.as_f64())
        .unwrap_or(default)
}

/// Safely get a string value from JSON object
pub fn get_str<'a>(obj: &'a Value, key: &str) -> RendererResult<&'a str> {
    obj.get(key)
        .and_then(|v| v.as_str())
        .ok_or_else(|| RendererError::InvalidValue(
            key.to_string(),
            format!("Expected string, got: {:?}", obj.get(key))
        ))
}

/// Safely get a string value from JSON object with default
pub fn get_str_or<'a>(obj: &'a Value, key: &str, default: &'a str) -> &'a str {
    obj.get(key)
        .and_then(|v| v.as_str())
        .unwrap_or(default)
}

/// Safely get an array from JSON object
pub fn get_array<'a>(obj: &'a Value, key: &str) -> RendererResult<&'a Vec<Value>> {
    obj.get(key)
        .and_then(|v| v.as_array())
        .ok_or_else(|| RendererError::InvalidValue(
            key.to_string(),
            format!("Expected array, got: {:?}", obj.get(key))
        ))
}

/// Safely get an array from JSON object, returns empty vec if not found
pub fn get_array_or_empty(obj: &Value, key: &str) -> Vec<Value> {
    obj.get(key)
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

/// Safely get an object from JSON value
pub fn get_object<'a>(obj: &'a Value, key: &str) -> RendererResult<&'a serde_json::Map<String, Value>> {
    obj.get(key)
        .and_then(|v| v.as_object())
        .ok_or_else(|| RendererError::InvalidValue(
            key.to_string(),
            format!("Expected object, got: {:?}", obj.get(key))
        ))
}

/// Safely get a boolean value from JSON object
pub fn get_bool_or(obj: &Value, key: &str, default: bool) -> bool {
    obj.get(key)
        .and_then(|v| v.as_bool())
        .unwrap_or(default)
}

/// Safely get an optional f64 value
pub fn get_f64_opt(obj: &Value, key: &str) -> Option<f64> {
    obj.get(key).and_then(|v| v.as_f64())
}

/// Safely get an optional string value
pub fn get_str_opt<'a>(obj: &'a Value, key: &str) -> Option<&'a str> {
    obj.get(key).and_then(|v| v.as_str())
}

/// Safely get an optional array value
pub fn get_array_opt<'a>(obj: &'a Value, key: &str) -> Option<&'a Vec<Value>> {
    obj.get(key).and_then(|v| v.as_array())
}

/// Safely get an optional object value
pub fn get_object_opt<'a>(obj: &'a Value, key: &str) -> Option<&'a serde_json::Map<String, Value>> {
    obj.get(key).and_then(|v| v.as_object())
}

