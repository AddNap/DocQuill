#!/usr/bin/env python3
"""Test script for Rust EMF/WMF converter"""

import sys
import os
from pathlib import Path

# Add project root to path
# test_converter.py is in: docx_interpreter/media/converter/rust/emf-converter/tests/
# project root is 5 levels up: tests -> emf-converter -> rust -> converter -> media -> docx_interpreter -> root
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

def test_wmf_conversion():
    """Test WMF to SVG conversion"""
    try:
        import emf_converter
    except ImportError:
        print("Error: emf_converter module not found. Build it first with:")
        print("  cd docx_interpreter/media/converter/rust/emf-converter")
        print("  maturin develop")
        return False
    
    # Try multiple possible paths
    possible_paths = [
        project_root / "tests" / "files" / "image1.wmf",
        Path("tests/files/image1.wmf"),
        Path(__file__).parent.parent.parent.parent.parent / "tests" / "files" / "image1.wmf",
    ]
    
    wmf_file = None
    for path in possible_paths:
        if path.exists():
            wmf_file = path
            break
    
    if wmf_file is None:
        print(f"Error: WMF file not found. Tried:")
        for path in possible_paths:
            print(f"  - {path}")
        return False
    
    output_svg = project_root / "output" / "test_wmf_output.svg"
    
    # Ensure output directory exists
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Converting {wmf_file} to {output_svg}...")
    
    try:
        result = emf_converter.convert_emf_to_svg(str(wmf_file), str(output_svg))
        if result:
            print(f"✓ Conversion successful! Output: {output_svg}")
            
            # Check file size
            if output_svg.exists():
                size = output_svg.stat().st_size
                print(f"  Output file size: {size} bytes")
                
                # Read first few lines
                with open(output_svg, 'r') as f:
                    lines = f.readlines()[:10]
                    print("\n  First 10 lines of SVG:")
                    for i, line in enumerate(lines, 1):
                        print(f"    {i}: {line.strip()}")
                
                return True
            else:
                print("✗ Output file was not created")
                return False
        else:
            print("✗ Conversion returned False")
            return False
    except Exception as e:
        print(f"✗ Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_wmf_bytes_conversion():
    """Test WMF bytes to SVG string conversion"""
    try:
        import emf_converter
    except ImportError:
        print("Error: emf_converter module not found")
        return False
    
    # Try multiple possible paths
    possible_paths = [
        project_root / "tests" / "files" / "image1.wmf",
        Path("tests/files/image1.wmf"),
        Path(__file__).parent.parent.parent.parent.parent / "tests" / "files" / "image1.wmf",
    ]
    
    wmf_file = None
    for path in possible_paths:
        if path.exists():
            wmf_file = path
            break
    
    if wmf_file is None:
        print(f"Error: WMF file not found. Tried:")
        for path in possible_paths:
            print(f"  - {path}")
        return False
    
    print(f"\nTesting bytes conversion for {wmf_file}...")
    
    try:
        with open(wmf_file, 'rb') as f:
            wmf_data = f.read()
        
        print(f"  Read {len(wmf_data)} bytes")
        
        svg_content = emf_converter.convert_emf_bytes_to_svg(wmf_data)
        
        print(f"✓ Bytes conversion successful!")
        print(f"  SVG content length: {len(svg_content)} characters")
        print(f"  First 200 characters:")
        print(f"    {svg_content[:200]}...")
        
        return True
    except Exception as e:
        print(f"✗ Bytes conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Rust EMF/WMF Converter")
    print("=" * 60)
    
    success1 = test_wmf_conversion()
    success2 = test_wmf_bytes_conversion()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)

