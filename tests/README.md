# Test Suite for docx_interpreter

This directory contains comprehensive unit tests for the docx_interpreter project using pytest.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest configuration and fixtures
├── pytest.ini                  # Pytest settings
├── requirements.txt            # Test dependencies
├── run_tests.py               # Test runner script
├── README.md                  # This file
├── files/                     # Test files
│   └── Zapytanie_Ofertowe.docx # Real DOCX file for integration tests
├── parsers/                   # Parser tests
│   ├── __init__.py
│   ├── test_package_reader.py
│   └── test_xml_parser.py
├── renderers/                 # Renderer tests
│   ├── __init__.py
│   ├── test_html_renderer.py
│   └── test_pdf_renderer.py
├── engines/                   # Layout engine tests
│   ├── __init__.py
│   └── test_hybrid_layout_estimator.py
└── Interpreter/               # Main interpreter tests
    ├── __init__.py
    └── test_document.py
```

## Test Categories

### Unit Tests
- **Parsers**: Test individual parser components
- **Renderers**: Test HTML, PDF, and DOCX renderers
- **Layout Engines**: Test layout estimation and pagination
- **Models**: Test document model classes
- **Utils**: Test utility functions

### Integration Tests
- **Real DOCX Files**: Tests using actual DOCX documents
- **End-to-End Workflows**: Complete document processing pipelines
- **Performance Tests**: Memory usage and execution time validation

### Roundtrip Tests
- **XML Roundtrip**: Test DOCX -> parse -> export -> compare with source
- **XML Comparison**: Test XML normalization and comparison
- **XML Diff Analysis**: Test advanced XML diffing and difference analysis
- **XML Validation**: Test XML structure, namespaces, encoding, and completeness
- **XML Performance**: Test XML processing performance and memory usage

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r tests/requirements.txt
```

### Using the Test Runner Script

```bash
# Run all tests
python tests/run_tests.py all

# Run specific test categories
python tests/run_tests.py unit
python tests/run_tests.py integration
python tests/run_tests.py parser
python tests/run_tests.py renderer
python tests/run_tests.py layout

# Run with coverage
python tests/run_tests.py coverage

# Run in parallel
python tests/run_tests.py parallel

# Run specific test file
python tests/run_tests.py --test-path tests/parsers/test_package_reader.py

# Check dependencies
python tests/run_tests.py check
```

### Using pytest Directly

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/parsers/test_package_reader.py

# Run tests with markers
pytest tests/ -m unit
pytest tests/ -m integration
pytest tests/ -m slow

# Run with coverage
pytest tests/ --cov=docx_interpreter --cov-report=html

# Run in parallel
pytest tests/ -n auto

# Run with verbose output
pytest tests/ -v

# Run specific test function
pytest tests/parsers/test_package_reader.py::TestPackageReader::test_init_with_valid_docx
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Slow-running tests
- `@pytest.mark.parser`: Parser-specific tests
- `@pytest.mark.renderer`: Renderer-specific tests
- `@pytest.mark.layout`: Layout engine tests
- `@pytest.mark.performance`: Performance tests
- `@pytest.mark.roundtrip`: Roundtrip tests
- `@pytest.mark.xml`: XML-related tests
- `@pytest.mark.diff`: XML diff analysis tests

## Test Fixtures

Common fixtures available in `conftest.py`:

- `temp_dir`: Temporary directory for test files
- `sample_docx_path`: Path to sample DOCX file
- `real_docx_path`: Path to real DOCX file for integration tests
- `mock_document`: Mock document object
- `mock_paragraph`: Mock paragraph object
- `mock_table`: Mock table object
- `mock_image`: Mock image object
- `mock_run`: Mock run object
- `render_options`: Common renderer options
- `html_renderer`: HTML renderer instance
- `pdf_renderer`: PDF renderer instance
- `docx_renderer`: DOCX renderer instance

## Integration Tests

Integration tests use the real DOCX file `Zapytanie_Ofertowe.docx` to test:

- Document loading and parsing
- Content extraction
- Layout computation
- HTML/PDF rendering
- Performance validation
- Memory usage monitoring

## Roundtrip Tests

Roundtrip tests validate the complete document processing pipeline:

- **XML Roundtrip**: DOCX -> parse -> export -> compare with source
- **XML Comparison**: Normalize and compare XML documents
- **XML Diff Analysis**: Advanced difference analysis and reporting
- **XML Validation**: Structure, namespaces, encoding, and completeness
- **XML Performance**: Processing speed and memory usage validation

### Roundtrip Test Features

- **XML Normalization**: Remove namespace prefixes, normalize whitespace
- **Element Comparison**: Compare element counts, types, and attributes
- **Text Analysis**: Compare text content and word similarity
- **Structure Analysis**: Compare XML structure and depth
- **Attribute Analysis**: Compare element attributes
- **Namespace Analysis**: Compare XML namespaces
- **Diff Reporting**: Generate detailed difference reports
- **Performance Monitoring**: Track processing time and memory usage

## Performance Testing

Performance tests validate:

- Document loading time (< 5 seconds)
- Parsing time (< 10 seconds)
- Layout computation time (< 15 seconds)
- Memory usage (< 100MB increase)
- Concurrent access safety

## XML Testing

XML tests validate document processing and roundtrip functionality:

- **XML Roundtrip**: Complete DOCX -> XML -> DOCX cycle
- **XML Comparison**: Normalized XML document comparison
- **XML Diff Analysis**: Advanced difference detection and reporting
- **XML Validation**: Well-formed XML and structure validation
- **XML Performance**: Processing speed and memory usage
- **XML Consistency**: Multiple exports produce identical results
- **XML Error Handling**: Graceful handling of malformed XML
- **XML Custom Options**: Custom namespace, indentation, and encoding

## Coverage

To generate coverage reports:

```bash
# HTML coverage report
pytest tests/ --cov=docx_interpreter --cov-report=html

# Terminal coverage report
pytest tests/ --cov=docx_interpreter --cov-report=term-missing

# XML coverage report
pytest tests/ --cov=docx_interpreter --cov-report=xml
```

Coverage reports are generated in the `htmlcov/` directory.

## Continuous Integration

Tests are designed to run in CI/CD environments:

- No external dependencies
- Deterministic results
- Fast execution
- Clear error messages
- Comprehensive coverage

## Test Data

- **Mock Objects**: Used for unit tests to isolate components
- **Real DOCX Files**: Used for integration tests to validate real-world scenarios
- **Temporary Files**: Created and cleaned up automatically

## Debugging Tests

To debug failing tests:

```bash
# Run with maximum verbosity
pytest tests/ -vvv

# Run specific test with debugging
pytest tests/parsers/test_package_reader.py::TestPackageReader::test_init_with_valid_docx -vvv

# Run with pdb debugger
pytest tests/ --pdb

# Run with print statements
pytest tests/ -s
```

## Adding New Tests

When adding new tests:

1. Follow the naming convention: `test_*.py`
2. Use descriptive test names: `test_function_name_scenario`
3. Add appropriate markers: `@pytest.mark.unit`
4. Use fixtures for common setup
5. Include both positive and negative test cases
6. Add docstrings explaining test purpose
7. Update this README if adding new test categories

## Roundtrip Testing

Roundtrip tests are a critical part of the test suite, ensuring that:

- Documents can be parsed and exported without data loss
- XML structure is preserved during processing
- Text content is maintained accurately
- Formatting and styling are preserved
- Performance remains within acceptable limits

### Roundtrip Test Structure

```
tests/Interpreter/
├── test_roundtrip.py              # Basic roundtrip tests
├── test_xml_comparison.py         # XML comparison and normalization
├── test_xml_diff.py              # Advanced XML diff analysis
└── test_integration_roundtrip.py  # Integration roundtrip tests
```

### Roundtrip Test Features

- **XML Normalization**: Remove namespace prefixes, normalize whitespace
- **Element Comparison**: Compare element counts, types, and attributes
- **Text Analysis**: Compare text content and word similarity
- **Structure Analysis**: Compare XML structure and depth
- **Attribute Analysis**: Compare element attributes
- **Namespace Analysis**: Compare XML namespaces
- **Diff Reporting**: Generate detailed difference reports
- **Performance Monitoring**: Track processing time and memory usage

## Test Best Practices

- **Isolation**: Each test should be independent
- **Deterministic**: Tests should produce consistent results
- **Fast**: Unit tests should run quickly
- **Clear**: Test names should describe what they test
- **Comprehensive**: Cover edge cases and error conditions
- **Maintainable**: Easy to understand and modify

## Roundtrip Test Best Practices

- **XML Normalization**: Always normalize XML before comparison
- **Namespace Handling**: Remove namespace prefixes for comparison
- **Whitespace Normalization**: Handle whitespace differences
- **Element Comparison**: Compare element counts and types
- **Text Analysis**: Compare text content and word similarity
- **Structure Analysis**: Compare XML structure and depth
- **Attribute Analysis**: Compare element attributes
- **Namespace Analysis**: Compare XML namespaces
- **Diff Reporting**: Generate detailed difference reports
- **Performance Monitoring**: Track processing time and memory usage

## Test Summary

The test suite now includes comprehensive testing for:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Roundtrip Tests**: DOCX -> parse -> export -> compare
- **XML Tests**: XML processing and comparison
- **Performance Tests**: Speed and memory usage validation
- **Error Handling Tests**: Graceful error handling
- **Custom Options Tests**: Configuration and customization
- **Diff Analysis Tests**: Advanced difference detection
- **Report Generation Tests**: Detailed analysis reporting

All tests are designed to be:
- **Fast**: Quick execution for development
- **Reliable**: Consistent results across runs
- **Comprehensive**: Cover all major functionality
- **Maintainable**: Easy to understand and modify
- **Well-documented**: Clear purpose and usage

## Test Files Overview

```
tests/
├── __init__.py                     # Test package initialization
├── conftest.py                     # Pytest configuration and fixtures
├── pytest.ini                     # Pytest settings
├── requirements.txt                # Test dependencies
├── run_tests.py                    # Test runner script
├── README.md                       # This documentation
├── files/                          # Test files
│   └── Zapytanie_Ofertowe.docx     # Real DOCX file for integration tests
├── parsers/                        # Parser tests
│   ├── __init__.py
│   ├── test_package_reader.py
│   └── test_xml_parser.py
├── renderers/                      # Renderer tests
│   ├── __init__.py
│   ├── test_html_renderer.py
│   └── test_pdf_renderer.py
├── engines/                        # Layout engine tests
│   ├── __init__.py
│   └── test_hybrid_layout_estimator.py
└── Interpreter/                    # Main interpreter tests
    ├── __init__.py
    ├── test_document.py
    ├── test_models.py
    ├── test_utils.py
    ├── test_cli.py
    ├── test_export.py
    ├── test_layout.py
    ├── test_roundtrip.py
    ├── test_xml_comparison.py
    ├── test_xml_diff.py
    └── test_integration_roundtrip.py
```

## Test Coverage

The test suite provides comprehensive coverage for:

- **Document Processing**: Loading, parsing, and exporting
- **XML Handling**: Parsing, validation, and comparison
- **Layout Engine**: Page layout and pagination
- **Renderers**: HTML, PDF, and DOCX output
- **Models**: Document structure and content
- **Utils**: Utility functions and helpers
- **CLI**: Command-line interface
- **Export**: Various export formats
- **Roundtrip**: Complete document processing cycle
- **Performance**: Speed and memory usage
- **Error Handling**: Graceful error management
- **Custom Options**: Configuration and customization

## Test Execution

To run the complete test suite:

```bash
# Run all tests
python tests/run_tests.py all

# Run specific test categories
python tests/run_tests.py unit
python tests/run_tests.py integration
python tests/run_tests.py roundtrip

# Run with coverage
python tests/run_tests.py coverage

# Run in parallel
python tests/run_tests.py parallel
```

## Test Results

The test suite provides:

- **Comprehensive Coverage**: All major functionality tested
- **Fast Execution**: Quick feedback for development
- **Reliable Results**: Consistent across runs
- **Clear Reporting**: Detailed test results and coverage
- **Easy Maintenance**: Well-organized and documented
- **Performance Monitoring**: Speed and memory usage tracking
- **Error Handling**: Graceful error management
- **Custom Options**: Configuration and customization testing

## Test Features

### Roundtrip Testing
- **XML Roundtrip**: Complete DOCX -> parse -> export -> compare cycle
- **XML Normalization**: Remove namespace prefixes, normalize whitespace
- **Element Comparison**: Compare element counts, types, and attributes
- **Text Analysis**: Compare text content and word similarity
- **Structure Analysis**: Compare XML structure and depth
- **Attribute Analysis**: Compare element attributes
- **Namespace Analysis**: Compare XML namespaces
- **Diff Reporting**: Generate detailed difference reports
- **Performance Monitoring**: Track processing time and memory usage

### XML Testing
- **XML Validation**: Well-formed XML and structure validation
- **XML Comparison**: Normalized XML document comparison
- **XML Diff Analysis**: Advanced difference detection and reporting
- **XML Performance**: Processing speed and memory usage
- **XML Consistency**: Multiple exports produce identical results
- **XML Error Handling**: Graceful handling of malformed XML
- **XML Custom Options**: Custom namespace, indentation, and encoding

### Integration Testing
- **Real DOCX Files**: Tests using actual DOCX documents
- **End-to-End Workflows**: Complete document processing pipelines
- **Performance Tests**: Memory usage and execution time validation
- **Error Handling**: Graceful error management
- **Custom Options**: Configuration and customization testing

## Test Quality

The test suite ensures:

- **Data Integrity**: Documents are processed without data loss
- **XML Fidelity**: XML structure and content are preserved
- **Performance**: Processing remains within acceptable limits
- **Reliability**: Consistent results across multiple runs
- **Maintainability**: Easy to understand and modify
- **Coverage**: All major functionality is tested
- **Documentation**: Clear purpose and usage for each test
- **Error Handling**: Graceful management of edge cases
- **Customization**: Support for various configuration options
- **Reporting**: Detailed analysis and difference detection

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the project root is in Python path
2. **Missing Dependencies**: Install requirements.txt
3. **File Not Found**: Check that test files exist in tests/files/
4. **Permission Errors**: Ensure test directories are writable

### Roundtrip Test Issues

1. **XML Parsing Errors**: Check that exported XML is well-formed
2. **Namespace Issues**: Ensure namespace handling is consistent
3. **Whitespace Differences**: Normalize whitespace before comparison
4. **Element Count Mismatches**: Check element extraction logic
5. **Text Content Differences**: Verify text extraction and normalization
6. **Performance Issues**: Monitor memory usage and processing time
7. **Diff Report Generation**: Check diff analysis and reporting logic

### Getting Help

- Check pytest documentation: https://docs.pytest.org/
- Review test output for specific error messages
- Use `pytest --collect-only` to see available tests
- Use `pytest --fixtures` to see available fixtures
- Check XML diff reports for detailed difference analysis
- Monitor performance metrics for optimization opportunities
