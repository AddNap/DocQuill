"""
Command-line interface for DocQuill.

Usage:
    docquill input.docx --format pdf --output output.pdf
    docquill input.docx --format html --output output.html
    docquill input.docx --format json --output output.json
    docquill info input.docx
"""

import argparse
import sys
import os
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="docquill",
        description="DocQuill - Professional DOCX document processing library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  docquill document.docx --format pdf --output out.pdf
  docquill document.docx --format html --output out.html
  docquill document.docx --format json --output out.json
  docquill info document.docx
  docquill version
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Convert command (default)
    convert_parser = subparsers.add_parser("convert", help="Convert DOCX to other formats")
    convert_parser.add_argument("input", help="Input DOCX file")
    convert_parser.add_argument(
        "-f", "--format",
        choices=["pdf", "html", "json", "text", "markdown"],
        default="pdf",
        help="Output format (default: pdf)"
    )
    convert_parser.add_argument(
        "-o", "--output",
        help="Output file path (default: input name with new extension)"
    )
    convert_parser.add_argument(
        "--backend",
        choices=["rust", "reportlab"],
        default="rust",
        help="PDF backend (default: rust)"
    )
    convert_parser.add_argument(
        "--editable",
        action="store_true",
        help="Generate editable HTML (for html format)"
    )
    convert_parser.add_argument(
        "--embed-images",
        action="store_true",
        help="Embed images as data URIs in HTML"
    )
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show document information")
    info_parser.add_argument("input", help="Input DOCX file")
    info_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    # Version command
    subparsers.add_parser("version", help="Show version information")
    
    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run layout pipeline and export JSON")
    pipeline_parser.add_argument("input", help="Input DOCX file")
    pipeline_parser.add_argument(
        "-o", "--output",
        help="Output JSON file path"
    )
    pipeline_parser.add_argument(
        "--format",
        choices=["optimized", "full"],
        default="optimized",
        help="JSON format: optimized (AI-ready) or full"
    )
    
    # Add positional argument for backward compatibility (convert is default)
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Input DOCX file (for direct conversion)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["pdf", "html", "json", "text", "markdown"],
        help="Output format"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path"
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit"
    )
    
    return parser


def cmd_convert(args):
    """Handle convert command."""
    from .api import Document
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        ext_map = {
            "pdf": ".pdf",
            "html": ".html",
            "json": ".json",
            "text": ".txt",
            "markdown": ".md",
        }
        output_path = input_path.with_suffix(ext_map.get(args.format, ".pdf"))
    
    print(f"📄 Opening: {input_path}")
    doc = Document(str(input_path))
    
    if args.format == "pdf":
        print(f"🖨️  Rendering PDF with {args.backend} backend...")
        doc.to_pdf(str(output_path), backend=args.backend)
    elif args.format == "html":
        print(f"🌐 Generating HTML (editable={args.editable})...")
        doc.to_html(
            str(output_path),
            editable=getattr(args, "editable", False),
            embed_images_as_data_uri=getattr(args, "embed_images", False)
        )
    elif args.format == "json":
        print("📊 Exporting to JSON...")
        doc.to_json(str(output_path), optimized=True)
    elif args.format == "text":
        print("📝 Exporting to plain text...")
        model = doc.to_model()
        text = "\n".join(
            getattr(el, "text", "") or el.get_text() if hasattr(el, "get_text") else ""
            for el in model.elements
        )
        output_path.write_text(text, encoding="utf-8")
    elif args.format == "markdown":
        print("📝 Exporting to Markdown...")
        from .export import MarkdownExporter
        exporter = MarkdownExporter(doc)
        md_content = exporter.export_to_string()
        output_path.write_text(md_content, encoding="utf-8")
    
    print(f"✅ Saved: {output_path}")
    return 0


def cmd_info(args):
    """Handle info command."""
    import json
    from .api import Document
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1
    
    doc = Document(str(input_path))
    stats = doc.get_stats()
    metadata = doc.get_metadata()
    
    info = {
        "file": str(input_path),
        "size_bytes": input_path.stat().st_size,
        "metadata": metadata,
        "stats": stats,
    }
    
    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False, default=str))
    else:
        print(f"📄 File: {input_path}")
        print(f"   Size: {input_path.stat().st_size:,} bytes")
        print()
        print("📋 Metadata:")
        for key, value in (metadata or {}).items():
            if value:
                print(f"   {key}: {value}")
        print()
        print("📊 Statistics:")
        for key, value in (stats or {}).items():
            print(f"   {key}: {value}")
    
    return 0


def cmd_version(args=None):
    """Handle version command."""
    from .version import __version__
    print(f"DocQuill v{__version__}")
    print("Professional DOCX document processing library")
    print("https://github.com/AddNap/DocQuill")
    return 0


def cmd_pipeline(args):
    """Handle pipeline command."""
    from .api import Document
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".json")
    
    print(f"📄 Opening: {input_path}")
    doc = Document(str(input_path))
    
    print("⚙️  Running layout pipeline...")
    layout = doc.pipeline()
    
    optimized = args.format == "optimized"
    print(f"📊 Exporting JSON (optimized={optimized})...")
    doc.to_json(str(output_path), optimized=optimized)
    
    print(f"✅ Saved: {output_path}")
    print(f"   Pages: {len(layout.pages)}")
    print(f"   Blocks: {sum(len(p.blocks) for p in layout.pages)}")
    
    return 0


def main():
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle --version flag
    if getattr(args, "version", False):
        return cmd_version()
    
    # Handle subcommands
    if args.command == "convert":
        return cmd_convert(args)
    elif args.command == "info":
        return cmd_info(args)
    elif args.command == "version":
        return cmd_version(args)
    elif args.command == "pipeline":
        return cmd_pipeline(args)
    
    # Handle backward-compatible direct file argument
    if getattr(args, "input_file", None):
        # Create a namespace that looks like convert args
        class ConvertArgs:
            def __init__(self, input_file, format_, output):
                self.input = input_file
                self.format = format_ or "pdf"
                self.output = output
                self.backend = "rust"
                self.editable = False
                self.embed_images = False
        
        convert_args = ConvertArgs(
            args.input_file,
            getattr(args, "format", None),
            getattr(args, "output", None)
        )
        return cmd_convert(convert_args)
    
    # No command specified, show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

