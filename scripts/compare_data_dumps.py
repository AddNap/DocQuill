#!/usr/bin/env python3
"""
Script to compare data dumps between ReportLab and Rust renderers.
This will help identify differences in how data is passed to each renderer.
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docquill.engine.pdf.pdf_compiler import PdfCompiler
from docquill.engine.pdf.pdf_compiler_rust import PdfCompilerRust

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def dump_inline_image_data_reportlab(compiler, layout_block):
    """Extract and dump inline image data as ReportLab sees it."""
    dumps = []
    
    # Get layout payload from paragraph
    if hasattr(layout_block, 'content') and hasattr(layout_block.content, 'layout_payload'):
        layout_payload = layout_block.content.layout_payload
        
        if layout_payload and hasattr(layout_payload, 'lines'):
            for line_idx, line in enumerate(layout_payload.lines):
                if hasattr(line, 'items'):
                    for item_idx, inline in enumerate(line.items):
                        if hasattr(inline, 'kind') and inline.kind == "inline_image":
                            dump = {
                                "renderer": "ReportLab",
                                "line": line_idx,
                                "item": item_idx,
                                "kind": inline.kind,
                                "width": getattr(inline, 'width', None),
                                "height": getattr(inline, 'height', None),
                                "ascent": getattr(inline, 'ascent', None),
                                "descent": getattr(inline, 'descent', None),
                                "x": getattr(inline, 'x', None),
                                "data": {},
                            }
                            
                            # Extract data
                            if hasattr(inline, 'data'):
                                data = inline.data
                                if isinstance(data, dict):
                                    dump["data"] = {
                                        "keys": list(data.keys()),
                                        "image": data.get("image") if isinstance(data.get("image"), dict) else str(data.get("image"))[:100],
                                        "path": data.get("path"),
                                        "image_path": data.get("image_path"),
                                        "width": data.get("width"),
                                        "height": data.get("height"),
                                    }
                                else:
                                    dump["data"] = {"type": str(type(data)), "value": str(data)[:200]}
                            
                            dumps.append(dump)
    
    return dumps

def dump_inline_image_data_rust(compiler, layout_block):
    """Extract and dump inline image data as Rust sees it (after serialization)."""
    dumps = []
    
    # Serialize the layout block
    serialized = compiler._serialize_value(layout_block, _visited=set(), _depth=0)
    
    # Navigate to inline items
    if isinstance(serialized, dict):
        content = serialized.get("content", {})
        if isinstance(content, dict):
            layout_payload = content.get("layout_payload", {})
            if isinstance(layout_payload, dict):
                lines = layout_payload.get("lines", [])
                for line_idx, line in enumerate(lines):
                    if isinstance(line, dict):
                        items = line.get("items", [])
                        for item_idx, item in enumerate(items):
                            if isinstance(item, dict) and item.get("kind") == "inline_image":
                                dump = {
                                    "renderer": "Rust",
                                    "line": line_idx,
                                    "item": item_idx,
                                    "kind": item.get("kind"),
                                    "width": item.get("width"),
                                    "height": item.get("height"),
                                    "ascent": item.get("ascent"),
                                    "descent": item.get("descent"),
                                    "x": item.get("x"),
                                    "data": item.get("data", {}),
                                }
                                dumps.append(dump)
    
    return dumps

def compare_dumps(docx_path):
    """Compare data dumps between ReportLab and Rust renderers."""
    docx_path = Path(docx_path)
    if not docx_path.exists():
        logger.error(f"File not found: {docx_path}")
        return
    
    logger.info(f"📄 Processing: {docx_path}")
    
    # Create compilers
    reportlab_compiler = PdfCompiler(docx_path, "/tmp/test_reportlab.pdf")
    rust_compiler = PdfCompilerRust(docx_path, "/tmp/test_rust.pdf")
    
    # Get layout (we'll need to access the layout from the compiler)
    # For now, let's create a simple test by rendering a small part
    
    logger.info("🔍 Extracting layout data...")
    
    # We need to get the unified layout first
    from docquill.engine.unified_layout import UnifiedLayout
    from docquill.docx_interpreter import DocxInterpreter
    
    interpreter = DocxInterpreter(docx_path)
    layout = interpreter.create_layout()
    
    # Find paragraphs with inline images
    reportlab_dumps = []
    rust_dumps = []
    
    for page in layout.pages:
        for block in page.blocks:
            if block.block_type == "paragraph":
                # Get dumps from both renderers
                rl_dumps = dump_inline_image_data_reportlab(reportlab_compiler, block)
                rust_dumps_data = dump_inline_image_data_rust(rust_compiler, block)
                
                reportlab_dumps.extend(rl_dumps)
                rust_dumps.extend(rust_dumps_data)
                
                # Stop after finding first few for comparison
                if len(reportlab_dumps) > 0 and len(rust_dumps) > 0:
                    break
        if len(reportlab_dumps) > 0 and len(rust_dumps) > 0:
            break
    
    # Print comparison
    print("\n" + "="*80)
    print("COMPARISON: ReportLab vs Rust Data Dumps")
    print("="*80)
    
    if not reportlab_dumps and not rust_dumps:
        print("❌ No inline images found in document")
        return
    
    print(f"\n📊 Found {len(reportlab_dumps)} inline images in ReportLab view")
    print(f"📊 Found {len(rust_dumps)} inline images in Rust view")
    
    # Compare first matching items
    for i, (rl_dump, rust_dump) in enumerate(zip(reportlab_dumps[:3], rust_dumps[:3])):
        print(f"\n{'='*80}")
        print(f"INLINE IMAGE #{i+1}")
        print(f"{'='*80}")
        
        print("\n📋 REPORTLAB DUMP:")
        print(json.dumps(rl_dump, indent=2, default=str))
        
        print("\n📋 RUST DUMP (after serialization):")
        print(json.dumps(rust_dump, indent=2, default=str))
        
        # Compare key fields
        print("\n🔍 KEY DIFFERENCES:")
        for key in ["width", "height", "ascent", "descent", "x"]:
            rl_val = rl_dump.get(key)
            rust_val = rust_dump.get(key)
            if rl_val != rust_val:
                print(f"  ⚠️  {key}: ReportLab={rl_val}, Rust={rust_val}")
            else:
                print(f"  ✅ {key}: {rl_val}")
        
        # Compare data structure
        rl_data = rl_dump.get("data", {})
        rust_data = rust_dump.get("data", {})
        
        print("\n🔍 DATA STRUCTURE COMPARISON:")
        print(f"  ReportLab data keys: {list(rl_data.keys()) if isinstance(rl_data, dict) else 'N/A'}")
        print(f"  Rust data keys: {list(rust_data.keys()) if isinstance(rust_data, dict) else 'N/A'}")
        
        # Check image path
        rl_path = None
        if isinstance(rl_data, dict):
            rl_path = rl_data.get("path") or rl_data.get("image_path")
            if isinstance(rl_data.get("image"), dict):
                rl_path = rl_data["image"].get("path") or rl_data["image"].get("image_path") or rl_path
        
        rust_path = None
        if isinstance(rust_data, dict):
            rust_path = rust_data.get("path") or rust_data.get("image_path")
            if isinstance(rust_data.get("image"), dict):
                rust_path = rust_data["image"].get("path") or rust_data["image"].get("image_path") or rust_path
        
        if rl_path != rust_path:
            print(f"  ⚠️  Image path differs: ReportLab={rl_path}, Rust={rust_path}")
        else:
            print(f"  ✅ Image path: {rl_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python compare_data_dumps.py <path_to_docx>")
        sys.exit(1)
    
    compare_dumps(sys.argv[1])

