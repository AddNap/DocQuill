#!/bin/bash
# Build script for Rust EMF converter

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building Rust EMF converter..."

# Check if maturin is installed
if ! command -v maturin &> /dev/null; then
    echo "Error: maturin is not installed"
    echo "Install it with: pip install maturin"
    exit 1
fi

# Build in release mode
echo "Building Python extension..."
maturin build --release

echo ""
echo "Build complete!"
echo ""
echo "To install the extension:"
echo "  pip install target/wheels/emf_converter-*.whl"
echo ""
echo "Or use maturin develop for development:"
echo "  maturin develop"

