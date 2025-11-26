# Architecture Plan: Engine-Based Rendering System

## Overview

The goal is to create a comprehensive layout engine system that calculates all formatting, positioning, and styling **before** rendering, so that renderers are just output formatters.

## Current Architecture

```
Document → Parser → HTML/PDF Renderer → Output
```

**Problems:**
- Renderers handle both layout calculation AND output formatting
- No separation of concerns
- Duplication of logic between HTML and PDF
- Hard to maintain and extend

## New Architecture

```
Document → Parser → Engine → Renderer → Output
                        ↓
              FormatResolver
              NumberingEngine  
              PositionCalculator
              ListBuilder
```

## Components

### 1. FormatResolver (`format_resolver.py`)
**Purpose:** Resolves all formatting properties from document relationships

**Responsibilities:**
- Style resolution from styles.xml
- Numbering resolution from numbering.xml
- Border and shading application
- Color resolution (including theme colors)
- Alignment and indentation
- Font and text formatting

**Output:** Complete formatting dictionary with all properties resolved

### 2. NumberingEngine (NEW)
**Purpose:** Handles list formatting and numbering

**Responsibilities:**
- Group numbered paragraphs into lists
- Calculate list markers (numbers, bullets, letters)
- Handle multi-level lists
- Apply correct indentation
- Track numbering continuation

**Output:** List structure with calculated markers

### 3. PositionCalculator (NEW)
**Purpose:** Calculates all positional offsets and spacing

**Responsibilities:**
- Convert EMU/twips to target units
- Calculate margins and indents
- Calculate spacing (before/after)
- Calculate image positions
- Calculate table positions

**Output:** Calculated offsets in target units

### 4. ListBuilder (NEW)
**Purpose:** Builds correct HTML list structure

**Responsibilities:**
- Group consecutive numbered paragraphs
- Identify list start/end
- Determine list type (ordered/unordered)
- Apply list styles

**Output:** Properly structured list HTML/CSS

## Data Flow

### Step 1: Parse
```
DOCX → Parser → Document Model
```

### Step 2: Resolve Formatting
```
Document Model + Relationships → FormatResolver → Resolved Formatting
```

### Step 3: Build Lists
```
Numbered Paragraphs → NumberingEngine → List Structure
```

### Step 4: Calculate Positions
```
Elements + Formatting → PositionCalculator → Calculated Positions
```

### Step 5: Render
```
Resolved Data → HTML/PDF Renderer → Output
```

## Example: Render Numbered Paragraph

### Current (Problematic)
```python
# In HTML renderer
paragraph = get_paragraph()
if has_numbering(paragraph):
    # Calculate numbering inline
    # Render as <p> with number
```

### New (Clean)
```python
# In Engine
resolved = format_resolver.resolve_paragraph_formatting(paragraph)
if resolved['numbering']:
    list_info = numbering_engine.process_numbered_paragraph(paragraph, resolved)
    positions = position_calculator.calculate_indent(paragraph, resolved)
    
    # Return to renderer
    return {
        'type': 'list_item',
        'number': list_info['number'],
        'level': list_info['level'],
        'indent_mm': positions['indent_mm'],
        'content': paragraph['content']
    }

# In Renderer (simple)
if item['type'] == 'list_item':
    html = f'<li>{item["number"]}. {item["content"]}</li>'
```

## Implementation Priority

1. **NumberingEngine** - Fix list rendering (HIGHEST PRIORITY)
2. **FormatResolver** - Resolve all formatting properties
3. **PositionCalculator** - Calculate all positions
4. **ListBuilder** - Build correct HTML structure
5. **Integration** - Connect to renderers

## Benefits

✅ **Separation of Concerns:** Logic separated from output
✅ **Maintainability:** One place to fix formatting logic
✅ **Testability:** Each component can be tested independently
✅ **Extensibility:** Easy to add new renderers (Markdown, LaTeX, etc.)
✅ **Consistency:** Same logic for HTML and PDF
✅ **Performance:** Cached resolved formatting

## Migration Path

1. Create new engine components alongside existing code
2. Implement one feature at a time (start with lists)
3. Test thoroughly on Zapytanie_Ofertowe.docx
4. Gradually migrate renderers to use new system
5. Remove old inline logic

## Success Criteria

- ✅ Lists render correctly in HTML
- ✅ PDF output matches HTML formatting
- ✅ No duplicate logic between HTML and PDF renderers
- ✅ All formatting properties properly resolved
- ✅ Positions and spacing calculated accurately
- ✅ Renderers are simple and focused only on output
