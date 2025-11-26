//! Error types for PDF renderer
//!
//! This module defines custom error types for the PDF renderer,
//! providing clear error messages and proper error propagation.

use thiserror::Error;

/// Custom error type for PDF renderer operations
#[derive(Error, Debug)]
pub enum RendererError {
    #[error("Invalid layout: {0}")]
    InvalidLayout(String),

    #[error("Font error: {0}")]
    FontError(String),

    #[error("Image error: {0}")]
    ImageError(String),

    #[error("JSON parsing error: {0}")]
    JsonError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("PDF generation error: {0}")]
    PdfError(String),

    #[error("Invalid color: {0}")]
    InvalidColor(String),

    #[error("Invalid geometry: {0}")]
    InvalidGeometry(String),

    #[error("Missing required field: {0}")]
    MissingField(String),

    #[error("Invalid value for field '{0}': {1}")]
    InvalidValue(String, String),
}

/// Result type alias for renderer operations
pub type RendererResult<T> = Result<T, RendererError>;

/// Conversion from RendererError to PyErr
impl From<RendererError> for pyo3::PyErr {
    fn from(err: RendererError) -> Self {
        pyo3::PyErr::new::<pyo3::exceptions::PyValueError, _>(err.to_string())
    }
}

/// Helper to convert serde_json errors
impl From<serde_json::Error> for RendererError {
    fn from(err: serde_json::Error) -> Self {
        RendererError::JsonError(err.to_string())
    }
}

