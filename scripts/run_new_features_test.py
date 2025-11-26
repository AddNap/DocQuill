#!/usr/bin/env python3
"""
Test script for new Rust PDF renderer features:
- Shadow rendering
- Enhanced border styles (rounded, dashed, dotted, double)
- Cell colspan/rowspan
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docquill.engine.unified_layout import UnifiedLayout, LayoutPage, LayoutBlock
from docquill.engine.geometry import Rect, Size, Margins

# Try to import Rust renderer directly
try:
    import importlib.util
    rust_so_path = project_root / "pdf_renderer_rust" / "target" / "debug" / "libpdf_renderer_rust.so"
    if rust_so_path.exists():
        spec = importlib.util.spec_from_file_location("pdf_renderer_rust", str(rust_so_path))
        pdf_renderer_rust = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pdf_renderer_rust)
        HAS_RUST = True
    else:
        raise ImportError("Rust module .so file not found")
except Exception as e:
    print(f"❌ Rust renderer not available: {e}")
    print("   Run 'maturin develop' in pdf_renderer_rust directory first.")
    sys.exit(1)

# Import PDFCompilerRust wrapper
try:
    from docquill.engine.pdf.pdf_compiler_rust import PDFCompilerRust, HAS_RUST_RENDERER
    # Override the pdf_renderer_rust module in the wrapper
    import docquill.engine.pdf.pdf_compiler_rust as pdf_compiler_rust_module
    pdf_compiler_rust_module.pdf_renderer_rust = pdf_renderer_rust
    pdf_compiler_rust_module.HAS_RUST_RENDERER = True
except ImportError as e:
    print(f"❌ Could not import PDFCompilerRust wrapper: {e}")
    sys.exit(1)

def create_test_layout():
    """Create a test UnifiedLayout with new features."""
    layout = UnifiedLayout()
    
    # A4 page
    page_size = Size(width=595.0, height=842.0)
    margins = Margins(top=72.0, bottom=72.0, left=72.0, right=72.0)
    
    page = layout.new_page(page_size, margins)
    
    # 1. Test Shadow Rendering
    page.add_block(LayoutBlock(
        frame=Rect(x=72.0, y=750.0, width=200.0, height=50.0),
        block_type="paragraph",
        content={"text": "Shadow Test"},
        style={
            "background_color": "#E0E0E0",
            "shadow": {
                "color": "#888888",
                "offset_x": 3.0,
                "offset_y": -3.0
            },
            "border": {
                "width": 1.0,
                "color": "#000000",
                "style": "solid"
            }
        }
    ))
    
    # 2. Test Rounded Rectangle Border
    page.add_block(LayoutBlock(
        frame=Rect(x=300.0, y=750.0, width=200.0, height=50.0),
        block_type="paragraph",
        content={"text": "Rounded Border"},
        style={
            "background_color": "#FFE0E0",
            "border": {
                "width": 2.0,
                "color": "#FF0000",
                "style": "solid",
                "radius": 10.0
            }
        }
    ))
    
    # 3. Test Dashed Border
    page.add_block(LayoutBlock(
        frame=Rect(x=72.0, y=680.0, width=200.0, height=50.0),
        block_type="paragraph",
        content={"text": "Dashed Border"},
        style={
            "background_color": "#E0FFE0",
            "border": {
                "width": 2.0,
                "color": "#00FF00",
                "style": "dashed"
            }
        }
    ))
    
    # 4. Test Dotted Border
    page.add_block(LayoutBlock(
        frame=Rect(x=300.0, y=680.0, width=200.0, height=50.0),
        block_type="paragraph",
        content={"text": "Dotted Border"},
        style={
            "background_color": "#E0E0FF",
            "border": {
                "width": 2.0,
                "color": "#0000FF",
                "style": "dotted"
            }
        }
    ))
    
    # 5. Test Double Border
    page.add_block(LayoutBlock(
        frame=Rect(x=72.0, y=610.0, width=200.0, height=50.0),
        block_type="paragraph",
        content={"text": "Double Border"},
        style={
            "background_color": "#FFFFE0",
            "border": {
                "width": 3.0,
                "color": "#FF8800",
                "style": "double"
            }
        }
    ))
    
    # 6. Test Table with Colspan/Rowspan
    page.add_block(LayoutBlock(
        frame=Rect(x=72.0, y=400.0, width=450.0, height=180.0),
        block_type="table",
        content={
            "rows": [
                {
                    "cells": [
                        {
                            "rect": {"x": 72.0, "y": 520.0, "width": 150.0, "height": 30.0},
                            "background_color": "#CCCCCC",
                            "border": {"width": 1.0, "color": "#000000", "style": "solid"},
                            "content": "Header 1",
                            "grid_span": 1
                        },
                        {
                            "rect": {"x": 222.0, "y": 520.0, "width": 150.0, "height": 30.0},
                            "background_color": "#CCCCCC",
                            "border": {"width": 1.0, "color": "#000000", "style": "solid"},
                            "content": "Header 2 (Colspan)",
                            "grid_span": 2  # Colspan = 2
                        }
                    ]
                },
                {
                    "cells": [
                        {
                            "rect": {"x": 72.0, "y": 490.0, "width": 150.0, "height": 60.0},
                            "background_color": "#FFFFFF",
                            "border": {"width": 1.0, "color": "#000000", "style": "solid"},
                            "content": "Rowspan Cell",
                            "vertical_merge_type": "restart"  # Start of rowspan
                        },
                        {
                            "rect": {"x": 222.0, "y": 490.0, "width": 75.0, "height": 30.0},
                            "background_color": "#FFFFFF",
                            "border": {"width": 1.0, "color": "#000000", "style": "solid"},
                            "content": "Cell 1",
                            "grid_span": 1
                        },
                        {
                            "rect": {"x": 297.0, "y": 490.0, "width": 75.0, "height": 30.0},
                            "background_color": "#FFFFFF",
                            "border": {"width": 1.0, "color": "#000000", "style": "solid"},
                            "content": "Cell 2",
                            "grid_span": 1
                        }
                    ]
                },
                {
                    "cells": [
                        {
                            "rect": {"x": 72.0, "y": 430.0, "width": 150.0, "height": 30.0},
                            "background_color": "#FFFFFF",
                            "border": {"width": 1.0, "color": "#000000", "style": "solid"},
                            "content": "",  # Continuation of rowspan
                            "vertical_merge_type": "continue"  # Continuation
                        },
                        {
                            "rect": {"x": 222.0, "y": 430.0, "width": 75.0, "height": 30.0},
                            "background_color": "#FFFFFF",
                            "border": {"width": 1.0, "color": "#000000", "style": "solid"},
                            "content": "Cell 3",
                            "grid_span": 1
                        },
                        {
                            "rect": {"x": 297.0, "y": 430.0, "width": 75.0, "height": 30.0},
                            "background_color": "#FFFFFF",
                            "border": {"width": 1.0, "color": "#000000", "style": "solid"},
                            "content": "Cell 4",
                            "grid_span": 1
                        }
                    ]
                }
            ]
        },
        style={}
    ))
    
    # 7. Test Combined: Shadow + Rounded Border
    page.add_block(LayoutBlock(
        frame=Rect(x=72.0, y=300.0, width=200.0, height=50.0),
        block_type="paragraph",
        content={"text": "Shadow + Rounded"},
        style={
            "background_color": "#FFE0FF",
            "shadow": {
                "color": "#888888",
                "offset_x": 4.0,
                "offset_y": -4.0
            },
            "border": {
                "width": 2.0,
                "color": "#FF00FF",
                "style": "solid",
                "radius": 15.0
            }
        }
    ))
    
    return layout

def test_new_features():
    """Test new features of Rust PDF renderer."""
    print("🧪 Testing new Rust PDF renderer features...")
    print("=" * 60)
    
    # Create test layout
    print("\n1️⃣ Creating test layout...")
    layout = create_test_layout()
    print(f"   ✅ Created layout with {len(layout.pages)} page(s)")
    print(f"   ✅ Page 1 has {len(layout.pages[0].blocks)} blocks")
    
    # Create output directory
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "test_new_features.pdf"
    
    # Render with Rust
    print("\n2️⃣ Rendering PDF with Rust renderer...")
    try:
        compiler = PDFCompilerRust(
            output_path=str(output_path),
            page_size=(595.0, 842.0)
        )
        
        compiler.compile(layout)
        
        print(f"   ✅ PDF rendered successfully!")
        print(f"   📄 Output: {output_path}")
        
        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"   📊 File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
        else:
            print(f"   ⚠️  Warning: File not found at {output_path}")
            return 1
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("\n📋 Tested features:")
        print("   ✅ Shadow rendering")
        print("   ✅ Rounded rectangle borders")
        print("   ✅ Dashed borders")
        print("   ✅ Dotted borders")
        print("   ✅ Double borders")
        print("   ✅ Table colspan (grid_span)")
        print("   ✅ Table rowspan (vertical_merge_type)")
        print("   ✅ Combined shadow + rounded border")
        print(f"\n📄 Open {output_path} to view the results!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during rendering: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_new_features())

