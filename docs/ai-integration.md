# AI Integration

DocQuill provides structured data export designed for AI/ML processing, enabling document understanding, automated editing, and content generation workflows.

## Overview

The AI integration workflow:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   DOCX      │────▶│   Layout    │────▶│    AI/ML    │────▶│   Output    │
│   Input     │     │   JSON      │     │  Processing │     │ DOCX/PDF/   │
│             │     │             │     │             │     │   HTML      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## JSON Export Format

### Basic Export

```python
from docquill import Document

doc = Document.open("document.docx")

# Export to JSON (runs pipeline internally)
doc.to_json("layout.json", optimized=True)
```

### JSON Structure

```json
{
  "version": "2.0",
  "format": "optimized_pipeline",
  "metadata": {
    "total_pages": 9,
    "current_page": 10,
    "source": "DocQuill LayoutPipeline"
  },
  "styles": [
    {
      "style_name": "Normal",
      "font_size": 11.0,
      "spacing": {
        "before": "120",
        "after": "120",
        "line": "276",
        "lineRule": "auto"
      },
      "justification": "left",
      "borders": { ... },
      "shading": "#FFFFFF"
    }
  ],
  "media": [
    {
      "path": "word/media/image1.png",
      "rel_id": "rId5",
      "width": 1920,
      "height": 1080
    }
  ],
  "pages": [
    {
      "n": 1,
      "size": [595.0, 842.0],
      "margins": [72, 72, 72, 72],
      "blocks": [
        {
          "f": [72.0, 750.0, 451.0, 20.0],
          "t": "paragraph",
          "s": 0,
          "c": {
            "type": "paragraph",
            "text": "Document Title",
            "runs": [
              {
                "text": "Document Title",
                "bold": true,
                "font_size": 24
              }
            ]
          },
          "uid": "para_001",
          "seq": 1
        },
        {
          "f": [72.0, 500.0, 451.0, 150.0],
          "t": "table",
          "s": 5,
          "c": {
            "type": "table",
            "rows": [
              {
                "cells": [
                  { "text": "Header 1" },
                  { "text": "Header 2" }
                ]
              }
            ]
          }
        }
      ],
      "h": [0, 1],
      "f": [15, 16]
    }
  ]
}
```

### Field Reference

| Field | Description |
|-------|-------------|
| `f` | Frame: `[x, y, width, height]` in points |
| `t` | Block type: `paragraph`, `table`, `image`, `header`, `footer`, `footnotes`, `endnotes` |
| `s` | Style index (references `styles` array) |
| `c` | Content object (type-specific) |
| `uid` | Source element unique ID |
| `seq` | Sequence number in document order |
| `h` | Header block indices (page-level) |
| `f` | Footer block indices (page-level) |
| `m` | Media index (for images) |

## AI Use Cases

### 1. Document Understanding / QA

Extract information with positional context:

```python
import json
from docquill import Document

doc = Document.open("contract.docx")
doc.to_json("contract_layout.json", optimized=True)

with open("contract_layout.json") as f:
    data = json.load(f)

# Find all text blocks with their positions
for page in data["pages"]:
    for block in page["blocks"]:
        if block["t"] == "paragraph":
            text = block["c"].get("text", "")
            x, y, w, h = block["f"]
            print(f"Page {page['n']}: '{text[:50]}...' at ({x}, {y})")
```

### 2. Content Extraction

Extract tables for structured data:

```python
def extract_tables(layout_json):
    tables = []
    for page in layout_json["pages"]:
        for block in page["blocks"]:
            if block["t"] == "table":
                rows = block["c"].get("rows", [])
                table_data = []
                for row in rows:
                    row_data = [cell.get("text", "") for cell in row.get("cells", [])]
                    table_data.append(row_data)
                tables.append({
                    "page": page["n"],
                    "position": block["f"],
                    "data": table_data
                })
    return tables
```

### 3. Layout Analysis

Identify document structure:

```python
def analyze_structure(layout_json):
    structure = {
        "pages": len(layout_json["pages"]),
        "paragraphs": 0,
        "tables": 0,
        "images": 0,
        "headers": set(),
        "sections": []
    }
    
    for page in layout_json["pages"]:
        for block in page["blocks"]:
            block_type = block["t"]
            if block_type == "paragraph":
                structure["paragraphs"] += 1
                # Check for headings
                style_idx = block.get("s", 0)
                if style_idx < len(layout_json["styles"]):
                    style = layout_json["styles"][style_idx]
                    if "Heading" in style.get("style_name", ""):
                        structure["headers"].add(block["c"].get("text", ""))
            elif block_type == "table":
                structure["tables"] += 1
            elif block_type == "image":
                structure["images"] += 1
    
    return structure
```

### 4. Document Modification

Modify layout and reimport:

```python
import json
from docquill import Document
from docquill.importers import PipelineJSONImporter

# Export
doc = Document.open("original.docx")
doc.to_json("layout.json", optimized=True)

# Modify (e.g., via AI)
with open("layout.json") as f:
    data = json.load(f)

# Example: Update all paragraph text
for page in data["pages"]:
    for block in page["blocks"]:
        if block["t"] == "paragraph":
            original_text = block["c"].get("text", "")
            # AI processing here
            block["c"]["text"] = ai_process(original_text)

with open("modified_layout.json", "w") as f:
    json.dump(data, f)

# Reimport
importer = PipelineJSONImporter(
    json_path="modified_layout.json",
    source_docx_path="original.docx"  # For headers/footers
)
model = importer.to_document_model()

# Export to DOCX
from docquill.export import DOCXExporter
exporter = DOCXExporter(model)
exporter.save("modified.docx")
```

### 5. Template Generation

Generate documents from AI output:

```python
def generate_from_ai_response(ai_response, template_layout):
    """
    AI response format:
    {
        "title": "Generated Report",
        "sections": [
            {"heading": "Introduction", "content": "..."},
            {"heading": "Analysis", "content": "..."}
        ],
        "table_data": [["A", "B"], ["1", "2"]]
    }
    """
    # Clone template structure
    layout = json.loads(json.dumps(template_layout))
    
    # Find and fill placeholders
    for page in layout["pages"]:
        for block in page["blocks"]:
            if block["t"] == "paragraph":
                text = block["c"].get("text", "")
                if "{{TITLE}}" in text:
                    block["c"]["text"] = ai_response["title"]
                # ... more placeholder handling
    
    return layout
```

## LLM Integration Examples

### OpenAI / GPT Integration

```python
import openai
import json
from docquill import Document

def analyze_document_with_gpt(docx_path, question):
    # Export layout
    doc = Document.open(docx_path)
    doc.to_json("temp_layout.json", optimized=True)
    
    with open("temp_layout.json") as f:
        layout_data = json.load(f)
    
    # Extract text content
    text_content = []
    for page in layout_data["pages"]:
        for block in page["blocks"]:
            if block["t"] == "paragraph":
                text = block["c"].get("text", "")
                if text.strip():
                    text_content.append({
                        "page": page["n"],
                        "text": text,
                        "position": block["f"]
                    })
    
    # Query GPT
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are analyzing a document. Each text block includes its page number and position."
            },
            {
                "role": "user",
                "content": f"Document content:\n{json.dumps(text_content, indent=2)}\n\nQuestion: {question}"
            }
        ]
    )
    
    return response.choices[0].message.content
```

### Document Q&A System

```python
class DocumentQA:
    def __init__(self, docx_path):
        self.doc = Document.open(docx_path)
        self.doc.to_json("_temp_layout.json", optimized=True)
        
        with open("_temp_layout.json") as f:
            self.layout_data = json.load(f)
        
        self._build_index()
    
    def _build_index(self):
        """Build searchable index of document content."""
        self.blocks = []
        for page in self.layout_data["pages"]:
            for block in page["blocks"]:
                self.blocks.append({
                    "page": page["n"],
                    "type": block["t"],
                    "content": block["c"],
                    "position": block["f"],
                    "style": self.layout_data["styles"][block.get("s", 0)]
                })
    
    def find_by_content(self, query):
        """Find blocks containing query text."""
        results = []
        for block in self.blocks:
            if block["type"] == "paragraph":
                text = block["content"].get("text", "")
                if query.lower() in text.lower():
                    results.append(block)
        return results
    
    def get_section(self, heading):
        """Get all content under a heading."""
        section_content = []
        in_section = False
        
        for block in self.blocks:
            if block["type"] == "paragraph":
                style_name = block["style"].get("style_name", "")
                text = block["content"].get("text", "")
                
                if "Heading" in style_name:
                    if heading.lower() in text.lower():
                        in_section = True
                    elif in_section:
                        break  # Next heading, end section
                elif in_section:
                    section_content.append(text)
        
        return "\n".join(section_content)
```

## Multimodal AI Training

Export format suitable for training layout-aware models (LayoutLM, DocFormer, etc.):

```python
def export_for_training(layout_json, output_dir):
    """Export in format suitable for document AI training."""
    training_samples = []
    
    for page in layout_json["pages"]:
        page_width, page_height = page["size"]
        
        for block in page["blocks"]:
            if block["t"] == "paragraph":
                x, y, w, h = block["f"]
                
                # Normalize coordinates to [0, 1000]
                sample = {
                    "text": block["c"].get("text", ""),
                    "bbox": [
                        int(x / page_width * 1000),
                        int(y / page_height * 1000),
                        int((x + w) / page_width * 1000),
                        int((y + h) / page_height * 1000)
                    ],
                    "page": page["n"],
                    "label": classify_block(block, layout_json["styles"])
                }
                training_samples.append(sample)
    
    return training_samples

def classify_block(block, styles):
    """Classify block type for training labels."""
    style_idx = block.get("s", 0)
    if style_idx < len(styles):
        style_name = styles[style_idx].get("style_name", "")
        if "Heading1" in style_name:
            return "title"
        elif "Heading" in style_name:
            return "section_header"
    return "paragraph"
```

## Best Practices

### 1. Preserve Source Reference

Always keep `source_docx_path` when reimporting:

```python
importer = PipelineJSONImporter(
    json_data=modified_data,
    source_docx_path="original.docx"  # Required for headers/footers/images
)
```

### 2. Handle Large Documents

For large documents, process page by page:

```python
for page_idx, page in enumerate(layout_data["pages"]):
    # Process each page separately
    process_page(page)
    
    # Clear memory if needed
    if page_idx % 10 == 0:
        gc.collect()
```

### 3. Validate Modifications

Before reimporting, validate JSON structure:

```python
def validate_layout_json(data):
    assert "version" in data
    assert "pages" in data
    for page in data["pages"]:
        assert "blocks" in page
        for block in page["blocks"]:
            assert "f" in block  # frame
            assert "t" in block  # type
            assert len(block["f"]) == 4  # x, y, w, h
```

### 4. Maintain Style Consistency

When modifying text, preserve style indices:

```python
# DON'T change style index unless intentional
block["c"]["text"] = new_text  # OK
block["s"] = 999  # BAD - may reference non-existent style
```

## API Summary

```python
# Export
doc = Document.open("input.docx")
doc.to_json("layout.json", optimized=True)

# Import
from docquill.importers import PipelineJSONImporter

importer = PipelineJSONImporter(
    json_path="modified.json",
    source_docx_path="input.docx"
)

# To UnifiedLayout (for rendering)
layout = importer.to_unified_layout()

# To Document Model (for DOCX export)
model = importer.to_document_model()
```

