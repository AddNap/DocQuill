#!/usr/bin/env python3
"""Script to generate PDF from Zapytanie Ofertowe using new pdfcompiler."""

import sys
from pathlib import Path
from docquill.document import Document
from compiler import PdfCompiler, CompilerOptions

def main():
    """Generate PDF from Zapytanie Ofertowe."""
    # Paths
    project_root = Path(__file__).parent
    input_path = project_root / "tests" / "files" / "Zapytanie_Ofertowe.docx"
    output_path = project_root / "output" / "Zapytanie_Ofertowe_pdfcompiler.pdf"
    
    # Create output directory if needed
    output_path.parent.mkdir(exist_ok=True)
    
    # Check if input file exists
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {input_path}")
        sys.exit(1)
    
    print(f"📄 Input file: {input_path}")
    print(f"📄 Output file: {output_path}")
    print(f"")
    
    try:
        # Load document
        print("🔄 Loading document...")
        document = Document.from_file(input_path)
        
        # Use new pdfcompiler backend
        print("🔄 Using new pdfcompiler architecture...")
        options = CompilerOptions(
            renderer="pdfcompiler",  # Use new architecture
        )
        
        # Compile
        print("🔄 Compiling to PDF...")
        compiler = PdfCompiler(document, output_path, options)
        result_path = compiler.compile()
        
        # Verify
        if result_path.exists():
            file_size = result_path.stat().st_size
            print(f"")
            print(f"✅ PDF generated successfully!")
            print(f"   Output: {result_path}")
            print(f"   Size: {file_size:,} bytes")
            print(f"   Pages: {compiler.context.total_pages}")
        else:
            print(f"❌ Error: PDF file was not created")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

