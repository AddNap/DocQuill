#!/usr/bin/env python3
"""
Test script for Rust PDF renderer integration.

Compares Rust renderer with ReportLab renderer.
"""

import sys
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docquill.parser.package_reader import PackageReader
from docquill.parser.xml_parser import XMLParser
from docquill.engine.layout_pipeline import LayoutPipeline
from docquill.engine.geometry import Size, Margins
from docquill.engine.page_engine import PageConfig
from docquill.engine.pdf.pdf_compiler import PDFCompiler as PDFCompilerPython

# Try to import Rust renderer directly
try:
    import importlib.util
    rust_so_path = project_root / "pdf_renderer_rust" / "target" / "debug" / "libpdf_renderer_rust.so"
    if rust_so_path.exists():
        spec = importlib.util.spec_from_file_location("pdf_renderer_rust", str(rust_so_path))
        pdf_renderer_rust = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pdf_renderer_rust)
        # Override the pdf_renderer_rust module in the wrapper
        import docquill.engine.pdf.pdf_compiler_rust as pdf_compiler_rust_module
        pdf_compiler_rust_module.pdf_renderer_rust = pdf_renderer_rust
        pdf_compiler_rust_module.HAS_RUST_RENDERER = True
        from docquill.engine.pdf.pdf_compiler_rust import PDFCompilerRust
    else:
        raise ImportError("Rust module .so file not found")
except Exception as e:
    logger.warning(f"Rust renderer not available: {e}")
    PDFCompilerRust = None

def test_rust_renderer():
    """Test Rust renderer with a real document."""
    # Paths
    input_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    output_rust = project_root / "output" / "test_rust.pdf"
    output_python = project_root / "output" / "test_python.pdf"
    
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1
    
    logger.info(f"Testing Rust PDF renderer...")
    logger.info(f"Input: {input_path}")
    
    try:
        # 1. Parse document
        logger.info("Step 1: Parsing document...")
        package_reader = PackageReader(input_path)
        xml_parser = XMLParser(package_reader)
        
        page_config = PageConfig(
            page_size=Size(595, 842),
            base_margins=Margins(top=72, bottom=72, left=72, right=72)
        )
        pipeline = LayoutPipeline(page_config)
        xml_parser.image_cache = pipeline.image_cache
        
        body = xml_parser.parse_body()
        logger.info(f"Parsed: {len(body.children)} elements")
        
        # Preconvert images
        from docquill.parser.image_preconverter import preconvert_images_from_model
        from docquill.media import MediaConverter
        media_converter = MediaConverter()
        preconvert_images_from_model(body, package_reader, pipeline.image_cache, media_converter)
        
        # Note: Headers/footers parsing may not be available in XMLParser
        # Skip for now - images in headers/footers will be handled by layout engine if needed
        pipeline.image_cache.wait_for_all(timeout=60.0)
        
        # 2. Create layout
        logger.info("Step 2: Creating layout...")
        class DocumentAdapter:
            def __init__(self, body_obj, parser):
                self.elements = body_obj.children if hasattr(body_obj, 'children') else []
                self.parser = parser
        
        document_model = DocumentAdapter(body, xml_parser)
        
        sections = xml_parser.parse_sections()
        margins = Margins(top=72, bottom=72, left=72, right=72)
        
        if sections and len(sections) > 0:
            section = sections[0]
            if 'margins' in section:
                docx_margins = section['margins']
                from docquill.engine.geometry import twips_to_points
                
                def get_margin_twips(key, default=1440):
                    val = docx_margins.get(key, default)
                    if isinstance(val, str):
                        try:
                            return int(val)
                        except (ValueError, TypeError):
                            return default
                    return int(val) if val is not None else default
                
                margins = Margins(
                    top=twips_to_points(get_margin_twips('top', 1440)),
                    bottom=twips_to_points(get_margin_twips('bottom', 1440)),
                    left=twips_to_points(get_margin_twips('left', 1440)),
                    right=twips_to_points(get_margin_twips('right', 1440))
                )
        
        page_config = PageConfig(
            page_size=Size(595, 842),
            base_margins=margins
        )
        
        pipeline.layout_assembler.package_reader = package_reader
        
        unified_layout = pipeline.process(
            document_model,
            apply_headers_footers=True,
            validate=False
        )
        
        logger.info(f"Layout created: {len(unified_layout.pages)} pages")
        
        # 3. Test Rust renderer
        logger.info("Step 3: Testing Rust renderer...")
        rust_time = None
        if PDFCompilerRust is None:
            logger.warning("⚠️  Rust renderer not available, skipping...")
        else:
            try:
                start_time = time.time()
                compiler_rust = PDFCompilerRust(
                    output_path=str(output_rust),
                    page_size=(595.0, 842.0),
                    package_reader=package_reader,
                )
                output_file = compiler_rust.compile(unified_layout)
                rust_time = time.time() - start_time
                logger.info(f"✅ Rust renderer: {rust_time:.3f}s")
                logger.info(f"📄 PDF saved to: {output_file}")
            except Exception as e:
                logger.error(f"❌ Rust renderer failed: {e}", exc_info=True)
                rust_time = None
        
        # 4. Test Python renderer (for comparison)
        logger.info("Step 4: Testing Python renderer (for comparison)...")
        try:
            start_time = time.time()
            compiler_python = PDFCompilerPython(
                output_path=str(output_python),
                page_size=(595, 842),
                package_reader=package_reader,
            )
            compiler_python.compile(unified_layout)
            python_time = time.time() - start_time
            logger.info(f"✅ Python renderer: {python_time:.3f}s")
            
            if rust_time:
                speedup = python_time / rust_time
                logger.info(f"📊 Speedup: {speedup:.2f}x")
        except Exception as e:
            logger.error(f"❌ Python renderer failed: {e}", exc_info=True)
            python_time = None
        
        logger.info("✅ Test completed!")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(test_rust_renderer())


