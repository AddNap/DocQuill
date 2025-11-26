# Contributing to DocQuill

Thank you for your interest in contributing to DocQuill! This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Style Guidelines](#style-guidelines)

## Code of Conduct

Please be respectful and constructive in all interactions. We welcome contributors of all experience levels.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a new branch for your changes
4. Make your changes
5. Test your changes
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.9+
- Git
- (Optional) Rust toolchain for PDF renderer development

### Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/DocQuill.git
cd DocQuill

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install docquill_core in development mode
cd packages/docquill_core
pip install -e ".[dev]"

# (Optional) Build Rust PDF renderer
cd ../docquill_pdf_rust
pip install maturin
maturin develop --release
```

## Project Structure

```
DocQuill/
├── packages/
│   ├── docquill_core/           # Main Python package
│   │   ├── docquill/            # Source code
│   │   │   ├── parser/          # DOCX parsing
│   │   │   ├── layout/          # Layout engine
│   │   │   ├── engine/          # Core engines
│   │   │   ├── renderers/       # PDF/HTML renderers
│   │   │   ├── models/          # Document models
│   │   │   ├── styles/          # Style management
│   │   │   └── utils/           # Utilities
│   │   └── pyproject.toml
│   │
│   └── docquill_pdf_rust/       # Rust PDF renderer
│       ├── src/                 # Rust source
│       ├── Cargo.toml
│       └── pyproject.toml
│
├── tests/
│   ├── core/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── golden/                  # Golden file tests
│
├── docs/                        # Documentation
├── examples/                    # Example scripts
└── scripts/                     # Development scripts
```

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions/changes

### Commit Messages

Use clear, descriptive commit messages:

```
type: short description

Longer description if needed.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/core/parsers/test_xml_parser.py

# Run with coverage
pytest tests/ --cov=docquill --cov-report=html

# Run only fast tests
pytest tests/ -m "not slow"
```

### Writing Tests

- Place unit tests in `tests/core/`
- Place integration tests in `tests/integration/`
- Use descriptive test names: `test_parse_table_with_merged_cells`
- Include docstrings explaining what the test verifies

## Submitting Changes

1. Ensure all tests pass
2. Update documentation if needed
3. Add a changelog entry if applicable
4. Push your branch to your fork
5. Open a pull request against `main`

### Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Include screenshots for UI changes
- Ensure CI passes

## Style Guidelines

### Python

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use `black` for formatting
- Use `ruff` for linting

```bash
# Format code
black packages/docquill_core/docquill/

# Lint code
ruff check packages/docquill_core/docquill/
```

### Rust

- Follow standard Rust conventions
- Use `cargo fmt` for formatting
- Use `cargo clippy` for linting

### Documentation

- Use clear, concise language
- Include code examples where helpful
- Keep README and docs in sync

## Questions?

Feel free to open an issue for questions or discussions.

---

Thank you for contributing to DocQuill! 🎉

