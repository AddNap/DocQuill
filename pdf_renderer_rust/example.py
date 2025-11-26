#!/usr/bin/env python3
"""
Example usage of PDF renderer Rust module.
"""

import json
import pdf_renderer_rust

def main():
    # Create renderer
    renderer = pdf_renderer_rust.PdfRenderer("output_rust.pdf", 595.0, 842.0)  # A4
    
    # Create a simple layout
    layout = {
        "pages": [{
            "number": 1,
            "size": {"width": 595.0, "height": 842.0},
            "margins": {"top": 72.0, "bottom": 72.0, "left": 72.0, "right": 72.0},
            "blocks": [
                {
                    "frame": {"x": 100.0, "y": 700.0, "width": 400.0, "height": 50.0},
                    "block_type": "paragraph",
                    "content": {"text": "Hello, World from Rust!"},
                    "style": {
                        "font_name": "Helvetica",
                        "font_size": 24.0,
                        "color": "#000000"
                    }
                },
                {
                    "frame": {"x": 100.0, "y": 600.0, "width": 400.0, "height": 30.0},
                    "block_type": "paragraph",
                    "content": {"text": "This is rendered using pdf-writer in Rust."},
                    "style": {
                        "font_name": "Helvetica",
                        "font_size": 12.0,
                        "color": "#333333"
                    }
                },
                {
                    "frame": {"x": 100.0, "y": 500.0, "width": 200.0, "height": 100.0},
                    "block_type": "image",
                    "content": {"path": "test.png"},
                    "style": {}
                }
            ]
        }]
    }
    
    # Render layout
    layout_json = json.dumps(layout)
    renderer.render_layout(layout_json)
    
    # Save PDF
    renderer.save()
    print("PDF saved to output_rust.pdf")

if __name__ == "__main__":
    main()

