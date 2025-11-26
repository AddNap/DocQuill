//! EMF/WMF to SVG Converter
//!
//! High-quality converter for EMF/WMF files to SVG format.
//! This is a Rust rewrite of the Java converter using FreeHEP.

use pyo3::prelude::*;
use std::fs;
use std::path::Path;

pub mod emf;
pub mod wmf;
mod svg_writer;
mod emfplus;
mod emf_records;

/// Convert EMF/WMF file to SVG
///
/// Args:
///     input_path: Path to input EMF/WMF file
///     output_path: Path to output SVG file
///
/// Returns:
///     True if conversion successful, False otherwise
#[pyfunction]
fn convert_emf_to_svg(input_path: &str, output_path: &str) -> PyResult<bool> {
    let input = Path::new(input_path);
    if !input.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>(
            format!("Input file not found: {}", input_path)
        ));
    }

    let data = fs::read(input).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
        format!("Failed to read input file: {}", e)
    ))?;
    
    // Detect format
    let is_emf = emf::is_emf_format(&data);
    let is_wmf = wmf::is_wmf_format(&data);
    
    if !is_emf && !is_wmf {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Input file must be EMF or WMF format"
        ));
    }

    let svg_content = if is_emf {
        emf::convert_emf_to_svg(&data).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("EMF conversion failed: {}", e)
        ))?
    } else {
        wmf::convert_wmf_to_svg(&data).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("WMF conversion failed: {}", e)
        ))?
    };

    fs::write(output_path, svg_content).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
        format!("Failed to write output file: {}", e)
    ))?;
    
    // Verify output file was created
    let output = Path::new(output_path);
    if !output.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyIOError, _>(
            "Output SVG file was not created"
        ));
    }
    let metadata = output.metadata().map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
        format!("Failed to get output file metadata: {}", e)
    ))?;
    if metadata.len() == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyIOError, _>(
            "Output SVG file is empty"
        ));
    }

    Ok(true)
}

/// Convert EMF/WMF bytes to SVG string
///
/// Args:
///     emf_data: EMF/WMF data as bytes
///
/// Returns:
///     SVG content as string
#[pyfunction]
fn convert_emf_bytes_to_svg(emf_data: &[u8]) -> PyResult<String> {
    let is_emf = emf::is_emf_format(emf_data);
    let is_wmf = wmf::is_wmf_format(emf_data);
    
    if !is_emf && !is_wmf {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Input must be EMF or WMF data"
        ));
    }

    if is_emf {
        emf::convert_emf_to_svg(emf_data).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("EMF conversion failed: {}", e)
        ))
    } else {
        wmf::convert_wmf_to_svg(emf_data).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("WMF conversion failed: {}", e)
        ))
    }
}

/// Python module definition
#[pymodule]
fn emf_converter(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(convert_emf_to_svg, m)?)?;
    m.add_function(wrap_pyfunction!(convert_emf_bytes_to_svg, m)?)?;
    Ok(())
}

