"""Rendering package providing PDF/HTML export functionality."""

from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

from ..engine.placeholder_resolver import PlaceholderResolver
from ..engine.geometry import Margins, Size
try:
    from ..engine.layout_engine import LayoutEngine as DocumentEngine
except ImportError:
    DocumentEngine = None
from .base_renderer import BaseRenderer, IRenderer
from .header_footer_renderer import HeaderFooterRenderer
from .image_renderer import ImageRenderer
from .list_renderer import ListRenderer
try:
    from .pdf_renderer import PdfRenderer
except ImportError:
    PdfRenderer = None
from .render_utils import ensure_margins, ensure_page_size
from .table_renderer import TableRenderer
from .text_renderer import TextRenderer
from .field_renderer import FieldRenderer
from .footnote_renderer import FootnoteRenderer
from .watermark_renderer import WatermarkRenderer


__all__ = [
    "BaseRenderer",
    "IRenderer",
    "PdfRenderer",
    "TextRenderer",
    "ImageRenderer",
    "TableRenderer",
    "HeaderFooterRenderer",
    "ListRenderer",
    "HTMLRenderer",
    "PDFRenderer",
    "DOCXRenderer",
]


class HTMLRenderer:
    """Basic HTML renderer that serialises document paragraphs."""

    def __init__(self, document, editable: bool = False, context: Optional[Dict[str, Any]] = None) -> None:
        self.document = document
        self.editable = editable
        self.placeholder_resolver = PlaceholderResolver(getattr(document, "placeholder_values", {}))
        
        # Initialize NumberingFormatter if numbering data is available
        self.numbering_formatter = None
        self._init_numbering_formatter()
        
        # Initialize FieldRenderer for field codes handling
        self.field_renderer = FieldRenderer(context)
        
        # Initialize FootnoteRenderer for footnotes and endnotes handling
        footnotes = getattr(document, 'footnotes', None) or {}
        if hasattr(document, 'get_footnotes'):
            try:
                footnotes = document.get_footnotes() or {}
            except Exception:
                pass
        
        endnotes = getattr(document, 'endnotes', None) or {}
        if hasattr(document, 'get_endnotes'):
            try:
                endnotes = document.get_endnotes() or {}
            except Exception:
                pass
        
        self.footnote_renderer = FootnoteRenderer(footnotes, endnotes)
        
        # Initialize WatermarkRenderer for watermarks handling
        watermarks = getattr(document, 'watermarks', None) or []
        if hasattr(document, 'get_watermarks'):
            try:
                watermarks = document.get_watermarks() or []
            except Exception:
                pass
        self.watermark_renderer = WatermarkRenderer(watermarks)
        
        # Store watermarks for PDF rendering
        self._watermarks = watermarks
        
        # Initialize StyleManager for document styles handling
        self.style_manager = None
        if hasattr(document, 'package_reader'):
            try:
                from ..styles.style_manager import StyleManager
                self.style_manager = StyleManager(document.package_reader)
                self.style_manager.load_styles()
            except Exception:
                pass

    def render(self) -> str:
        title = getattr(getattr(self.document, "metadata", None), "title", "Document")
        content_elements = self._collect_content_elements()

        if self.editable:
            body = self._render_editable_body(content_elements)
            css = self._get_editable_css()
            js = self._get_editable_js()
        else:
            # Render non-editable HTML
            body_parts = []
            for elem in content_elements:
                if elem.get('type') == 'table':
                    # Use table's to_html method if available
                    table = elem.get('table')
                    if table and hasattr(table, 'to_html'):
                        body_parts.append(table.to_html())
                    else:
                        # Fallback: render as simple table
                        body_parts.append(self._render_table_simple(elem))
                elif elem.get('type') == 'image':
                    # Render image
                    image_html = self._render_image_simple(elem)
                    body_parts.append(image_html)
                else:
                    # Paragraph with styling
                    para_text = elem.get('text', '') or ''
                    if para_text:
                        para_style = self._build_paragraph_style(elem)
                        if para_style:
                            body_parts.append(f'<p style="{para_style}">{escape(para_text)}</p>')
                        else:
                            body_parts.append(f"<p>{escape(para_text)}</p>")
            body = "\n".join(body_parts)
            css = ""
            js = ""

        # Render footnotes and endnotes section if present
        footnotes_section = self.footnote_renderer.render_footnotes_section()
        endnotes_section = self.footnote_renderer.render_endnotes_section()
        footnotes_css = self.footnote_renderer.get_footnote_css()
        
        # Render watermarks if present
        # Default page size A4: 210mm x 297mm
        page_width_mm = 210.0
        page_height_mm = 297.0
        watermark_html = self.watermark_renderer.render_html(page_width_mm, page_height_mm)
        watermark_css = self.watermark_renderer.get_watermark_css()

        # Render headers and footers if available
        headers_html, headers_css = self._render_headers_footers('header')
        footers_html, footers_css = self._render_headers_footers('footer')
        
        # Generate CSS from document styles
        document_styles_css = self._generate_document_styles_css()
        
        # Generuj CSS dla pozycjonowania tabel
        table_positioning_css = self._get_table_positioning_css()
        
        html = (
            "<!DOCTYPE html>\n"
            "<html><head><meta charset=\"utf-8\"><title>"
            f"{escape(str(title))}</title>"
            f"{css}"
            f"{footnotes_css}"
            f"{watermark_css}"
            f"{headers_css}"
            f"{footers_css}"
            f"{document_styles_css}"
            f"{table_positioning_css}"
            f"</head><body style=\"position: relative;\">\n"
            f"{headers_html}\n"
            f"{watermark_html}\n"
            f"{body}\n"
            f"{footnotes_section}\n"
            f"{endnotes_section}\n"
            f"{footers_html}\n"
            f"{js}"
            "</body></html>"
        )
        return html
    
    def _collect_content_elements(self) -> List[Dict[str, Any]]:
        """Collects paragraphs and tables from document in order of occurrence."""
        elements = []
        
        # If document has body with children, use their order
        if (hasattr(self.document, 'body') and 
            hasattr(self.document.body, 'children') and 
            hasattr(self.document.body.children, '__iter__')):
            try:
                for child in self.document.body.children:
                    # Check if this is a table
                    if hasattr(child, 'rows') and hasattr(child, 'get_rows'):
                        # To jest tabela
                        table_data = {
                            'type': 'table',
                            'table': child,
                            'rows': []
                        }
                        elements.append(table_data)
                    elif hasattr(child, 'rel_id') or (hasattr(child, '__class__') and 'Image' in child.__class__.__name__):
                        # To jest obraz
                        image_data = {
                            'type': 'image',
                            'image': child
                        }
                        elements.append(image_data)
                    elif hasattr(child, 'runs') or hasattr(child, 'get_text'):
                        # To jest paragraf
                        para_data = self._extract_paragraph_data(child)
                        elements.append(para_data)
            except (TypeError, AttributeError):
                # Fallback do get_paragraphs/get_tables
                pass
        
        # If collecting from body.children failed, use get_paragraphs/get_tables...
        if not elements and hasattr(self.document, "get_paragraphs"):
            # Zbierz paragrafy
            for para in self.document.get_paragraphs() or []:
                para_data = self._extract_paragraph_data(para)
                elements.append(para_data)
            
            # Zbierz tabele
            if hasattr(self.document, "get_tables"):
                try:
                    tables = self.document.get_tables()
                    if tables and hasattr(tables, '__iter__'):
                        for table in tables:
                            table_data = {
                                'type': 'table',
                                'table': table,
                                'rows': []
                            }
                            elements.append(table_data)
                except (TypeError, AttributeError):
                    # get_tables() returned Mock or is not iterable
                    pass
            
            # Zbierz obrazy
            if hasattr(self.document, "get_images"):
                try:
                    images = self.document.get_images()
                    if images and hasattr(images, '__iter__'):
                        for image in images:
                            image_data = {
                                'type': 'image',
                                'image': image
                            }
                            elements.append(image_data)
                except (TypeError, AttributeError):
                    # get_images() returned Mock or is not iterable
                    pass
        elif hasattr(self.document, "get_text"):
            # Fallback: tylko tekst
            for line in str(self.document.get_text()).splitlines():
                elements.append({
                    'type': 'paragraph',
                    'text': self.placeholder_resolver.resolve_text(line),
                    'runs': [],
                    'numbering': None
                })
        
        return elements
    
    def _extract_paragraph_data(self, para: Any) -> Dict[str, Any]:
        """Extracts paragraph data to dictionary."""
        para_data = {
            'type': 'paragraph',
            'text': '',
            'runs': [],
            'numbering': None
        }
        
        # Check if paragraph has numbering (list)
        if hasattr(para, 'numbering') and para.numbering:
            numbering_info = para.numbering
            if isinstance(numbering_info, dict):
                para_data['numbering'] = {
                    'id': numbering_info.get('id'),
                    'level': numbering_info.get('level', 0),
                    'format': numbering_info.get('format', 'decimal')
                }
            else:
                # If numbering is in different format, try to extract basic info...
                para_data['numbering'] = {
                    'id': getattr(numbering_info, 'id', None) or getattr(numbering_info, 'num_id', None),
                    'level': getattr(numbering_info, 'level', 0),
                    'format': getattr(numbering_info, 'format', 'decimal')
                }
        
        # Check if paragraph has field codes directly as children (not in...
        para_fields = []
        if hasattr(para, 'children') and para.children:
            for child in para.children:
                # Check if this is Field
                if (hasattr(child, '__class__') and 
                    ('Field' in child.__class__.__name__ or 
                     hasattr(child, 'field_type') or 
                     hasattr(child, 'instr'))):
                    para_fields.append(child)
        
        # If paragraph has field codes directly, render them as separate run...
        if para_fields:
            field_text = ""
            for field in para_fields:
                field_value = self.field_renderer.render_field(field)
                field_text += field_value
            
            if field_text:
                para_data['runs'].append({
                    'text': field_text,
                    'bold': False,
                    'italic': False,
                    'underline': False,
                    'field': True,
                })
                para_data['text'] += field_text
        
        # Check if para has runs attribute and it's not empty
        if hasattr(para, 'runs') and para.runs:
            for run in para.runs:
                # Check if run has image
                run_image = getattr(run, 'image', None)
                if run_image:
                    # Dodaj obraz jako specjalny element w paragrafie
                    if 'images' not in para_data:
                        para_data['images'] = []
                    para_data['images'].append({
                        'image': run_image,
                        'position': 'inline'  # Obraz inline w runie
                    })
                
                # Check if run has textbox
                run_textbox = getattr(run, 'textbox', None)
                if run_textbox:
                    # Dodaj textbox jako specjalny element
                    if 'textboxes' not in para_data:
                        para_data['textboxes'] = []
                    # Textbox is a list of runs
                    textbox_content = []
                    if isinstance(run_textbox, list):
                        for tb_run in run_textbox:
                            tb_text = getattr(tb_run, 'text', '') or ''
                            if tb_text:
                                textbox_content.append(self.placeholder_resolver.resolve_text(tb_text))
                    para_data['textboxes'].append({
                        'content': ' '.join(textbox_content),
                        'runs': run_textbox if isinstance(run_textbox, list) else []
                    })
                
                # Check if run has field codes (children of type Field)
                run_fields = []
                if hasattr(run, 'children') and run.children:
                    for child in run.children:
                        # Check if this is Field
                        if (hasattr(child, '__class__') and 
                            ('Field' in child.__class__.__name__ or 
                             hasattr(child, 'field_type') or 
                             hasattr(child, 'instr'))):
                            run_fields.append(child)
                
                # If run has field codes, render them
                if run_fields:
                    field_text = ""
                    for field in run_fields:
                        field_value = self.field_renderer.render_field(field)
                        field_text += field_value
                    
                    if field_text:
                        run_data = {
                            'text': field_text,
                            'bold': getattr(run, 'bold', False) or getattr(run, 'is_bold', lambda: False)(),
                            'italic': getattr(run, 'italic', False) or getattr(run, 'is_italic', lambda: False)(),
                            'underline': getattr(run, 'underline', False) or getattr(run, 'is_underline', lambda: False)(),
                            'color': getattr(run, 'color', None),
                            'font_size': getattr(run, 'font_size', None),
                            'font_name': getattr(run, 'font_name', None),
                            'field': True,  # Oznacz jako field
                        }
                        para_data['runs'].append(run_data)
                        para_data['text'] += run_data['text']
                
                # If run has footnote references, save them
                if run_footnote_refs:
                    if 'footnote_refs' not in para_data:
                        para_data['footnote_refs'] = []
                    para_data['footnote_refs'].extend(run_footnote_refs)
                
                # If run has endnote references, save them
                run_endnote_refs = getattr(run, 'endnote_refs', []) or []
                if run_endnote_refs:
                    if 'endnote_refs' not in para_data:
                        para_data['endnote_refs'] = []
                    para_data['endnote_refs'].extend(run_endnote_refs)
                
                run_text = getattr(run, 'text', '') or ''
                if run_text:
                    run_data = {
                        'text': self.placeholder_resolver.resolve_text(run_text),
                        'bold': getattr(run, 'bold', False) or getattr(run, 'is_bold', lambda: False)(),
                        'italic': getattr(run, 'italic', False) or getattr(run, 'is_italic', lambda: False)(),
                        'underline': getattr(run, 'underline', False) or getattr(run, 'is_underline', lambda: False)(),
                        'color': getattr(run, 'color', None),
                        'font_size': getattr(run, 'font_size', None),
                        'font_name': getattr(run, 'font_name', None),
                        'footnote_refs': run_footnote_refs if run_footnote_refs else None,
                        'endnote_refs': run_endnote_refs if run_endnote_refs else None,
                    }
                    para_data['runs'].append(run_data)
                    para_data['text'] += run_data['text']
        elif hasattr(para, "get_text"):
            para_data['text'] = self.placeholder_resolver.resolve_text(para.get_text())
        else:
            para_data['text'] = self.placeholder_resolver.resolve_text(str(getattr(para, "text", "")))
        
        # Collect paragraph properties (alignment, borders, background)
        para_data['alignment'] = getattr(para, 'alignment', None)
        para_data['borders'] = getattr(para, 'borders', None)
        para_data['background'] = getattr(para, 'background', None)
        para_data['shadow'] = getattr(para, 'shadow', None)
        para_data['spacing_before'] = getattr(para, 'spacing_before', None)
        para_data['spacing_after'] = getattr(para, 'spacing_after', None)
        para_data['left_indent'] = getattr(para, 'left_indent', None)
        para_data['right_indent'] = getattr(para, 'right_indent', None)
        
        return para_data
    
    def _collect_paragraphs_with_formatting(self) -> List[Dict[str, Any]]:
        """Zbiera paragrafy z formatowaniem (runs) i informacjami o listach."""
        # Preserved for backward compatibility
        elements = self._collect_content_elements()
        return [e for e in elements if e.get('type') == 'paragraph']
    
    def _render_editable_body(self, content_elements: List[Dict[str, Any]]) -> str:
        """Renders body with contenteditable and formatting, handling lists and tables..."""
        body_parts = []
        current_list = None  # (tag, level, list_items)
        list_items = []
        
        for i, elem in enumerate(content_elements):
            # Image handling
            if elem.get('type') == 'image':
                # Close open list if any
                if current_list:
                    items = current_list[3] if len(current_list) > 3 else list_items
                    list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                        for j, item in enumerate(items))
                    body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
                    list_items = []
                    current_list = None
                
                # Renderuj obraz
                image_html = self._render_image_editable(elem)
                body_parts.append(image_html)
                continue
            
            # Table handling
            if elem.get('type') == 'table':
                # Close open list if any
                if current_list:
                    items = current_list[3] if len(current_list) > 3 else list_items
                    list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                        for j, item in enumerate(items))
                    body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
                    list_items = []
                    current_list = None
                
                # Render table
                table_html = self._render_table_editable(elem)
                body_parts.append(table_html)
                continue
            
            # Paragraph handling
            para = elem
            numbering = para.get('numbering')
            
            # Render paragraph content
            if para['runs']:
                # Renderuj z formatowaniem runs
                run_parts = []
                for run in para['runs']:
                    text = escape(run['text'])
                    
                    # Build style string for nested formatting
                    style_parts = []
                    
                    # Kolory i czcionki
                    if run.get('color'):
                        color = run.get('color')
                        # Make sure color is in hex format
                        if not color.startswith('#'):
                            color = '#' + color
                        style_parts.append(f'color: {color}')
                    
                    if run.get('font_size'):
                        font_size = run.get('font_size')
                        # Convert half-points to px (approximation)
                        try:
                            if isinstance(font_size, str):
                                try:
                                    font_size = int(font_size)
                                except ValueError:
                                    font_size = None
                            elif not isinstance(font_size, (int, float)):
                                # If this is Mock or other type, skip
                                font_size = None
                            
                            if font_size is not None:
                                # Half-points do points, potem do px
                                points = font_size / 2
                                px = int(points * 1.33)  # 1pt ≈ 1.33px
                                style_parts.append(f'font-size: {px}px')
                        except (TypeError, ValueError):
                            # If conversion failed, skip font-size
                            pass
                    
                    if run.get('font_name'):
                        font_name = run.get('font_name')
                        style_parts.append(f"font-family: '{font_name}'")
                    
                    # Tagi HTML dla formatowania
                    tags = []
                    if run.get('bold'):
                        tags.append('strong')
                    if run.get('italic'):
                        tags.append('em')
                    if run.get('underline'):
                        tags.append('u')
                    
                    # Superscript i subscript
                    is_superscript = run.get('superscript') or run.get('vertical_align', '').lower() in ('superscript', 'sup')
                    is_subscript = run.get('subscript') or run.get('vertical_align', '').lower() in ('subscript', 'sub')
                    
                    # Zmniejsz font_size dla superscript i subscript (0.6 * font_size)
                    if is_superscript or is_subscript:
                        # Pobierz aktualny font_size z style_parts lub run
                        current_font_size_px = None
                        font_size_unit = 'px'  # Default px (as in code above)
                        
                        # Check if font-size is already in style_parts
                        for i, style_part in enumerate(style_parts):
                            if style_part.startswith('font-size:'):
                                try:
                                    font_size_str = style_part.split(':')[1].strip()
                                    if 'px' in font_size_str:
                                        current_font_size_px = float(font_size_str.replace('px', '').strip())
                                        font_size_unit = 'px'
                                    elif 'pt' in font_size_str:
                                        # Konwertuj pt na px (1pt ≈ 1.33px)
                                        current_font_size_px = float(font_size_str.replace('pt', '').strip()) * 1.33
                                        font_size_unit = 'px'
                                    break
                                except (ValueError, IndexError):
                                    pass
                        
                        if current_font_size_px is None:
                            # Try to get from run style (may be in various units)
                            run_style = run.get('style', {})
                            if isinstance(run_style, dict):
                                font_size_raw = run_style.get('font_size')
                                if font_size_raw:
                                    try:
                                        # If this is half-points (as in DOCX), convert to px
                                        font_size_val = float(font_size_raw)
                                        # Half-points do points, potem do px
                                        points = font_size_val / 2
                                        current_font_size_px = points * 1.33
                                    except (TypeError, ValueError):
                                        pass
                        
                        if current_font_size_px:
                            # Zmniejsz font_size do 58% (tak samo jak w footnotes)
                            new_font_size_px = int(current_font_size_px * 0.58)
                            # Remove old font-size from style_parts if exists
                            style_parts = [s for s in style_parts if not s.startswith('font-size:')]
                            # Dodaj nowy font-size
                            style_parts.append(f'font-size: {new_font_size_px}px')
                    
                    if is_superscript:
                        tags.append('sup')
                    elif is_subscript:
                        tags.append('sub')
                    
                    # Zastosuj tagi i style
                    if style_parts:
                        style_str = '; '.join(style_parts)
                        text = f'<span style="{style_str}">{text}</span>'
                    
                    if tags:
                        for tag in tags:
                            text = f"<{tag}>{text}</{tag}>"
                    
                    run_parts.append(text)
                
                para_html = ''.join(run_parts)
            else:
                para_html = escape(para['text'])
            
            # List handling
            if numbering:
                # Use NumberingFormatter to determine list type
                list_info = self._get_list_tag_from_numbering(numbering)
                if not list_info:
                    # Fallback do obecnej logiki
                    level = numbering.get('level', 0)
                    format_type = numbering.get('format', 'decimal')
                    is_bullet = format_type.lower() in ('bullet', 'disc', 'circle', 'square', 'none')
                    list_tag = 'ul' if is_bullet else 'ol'
                    list_info = (list_tag, int(level) if isinstance(level, (int, str)) else 0, format_type)
                
                list_tag, level, format_type = list_info
                
                # If list changed (tag or level), close previous
                if current_list and (current_list[0] != list_tag or current_list[1] != level):
                    # Close previous list
                    items = current_list[3] if len(current_list) > 3 else list_items
                    list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                        for j, item in enumerate(items))
                    body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
                    list_items = []
                    current_list = None
                
                # Start new list if needed
                if not current_list:
                    current_list = (list_tag, level, format_type, [])
                elif len(current_list) == 3:
                    # Convert old structure to new
                    old_items = current_list[2] if isinstance(current_list[2], list) else list_items
                    current_list = (current_list[0], current_list[1], format_type, old_items)
                
                # Dodaj element do listy
                if len(current_list) > 3:
                    current_list[3].append(para_html)
                else:
                    list_items.append(para_html)
            else:
                # If there was open list, close it
                if current_list:
                    items = current_list[3] if len(current_list) > 3 else list_items
                    list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                        for j, item in enumerate(items))
                    body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
                    list_items = []
                    current_list = None
                
                # Regular paragraph with properties
                para_style = self._build_paragraph_style(para)
                if para_style:
                    body_parts.append(f'<p contenteditable="true" data-para-id="{len(body_parts)}" style="{para_style}">{para_html}</p>')
                else:
                    body_parts.append(f'<p contenteditable="true" data-para-id="{len(body_parts)}">{para_html}</p>')
        
        # Close last list if open
        if current_list:
            items = current_list[3] if len(current_list) > 3 else list_items
            list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                for j, item in enumerate(items))
            body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
        
        return '\n'.join(body_parts)
    
    def _init_numbering_formatter(self) -> None:
        """Initializes NumberingFormatter if numbering data is available."""
        try:
            from ..engine.numbering_formatter import NumberingFormatter
            
            # Try to get numbering data from document
            numbering_data = None
            
            # Check various possible locations of numbering data
            if hasattr(self.document, 'numbering'):
                numbering_obj = self.document.numbering
                if hasattr(numbering_obj, 'abstract_numberings') and hasattr(numbering_obj, 'numbering_instances'):
                    numbering_data = {
                        'abstract_numberings': numbering_obj.abstract_numberings,
                        'numbering_instances': numbering_obj.numbering_instances
                    }
            elif hasattr(self.document, '_numbering_data'):
                numbering_data = self.document._numbering_data
            elif hasattr(self.document, 'get_numbering_data'):
                numbering_data = self.document.get_numbering_data()
            
            # If we have numbering data, create formatter
            if numbering_data:
                self.numbering_formatter = NumberingFormatter(numbering_data)
        except (ImportError, AttributeError, Exception) as e:
            # If cannot initialize, use fallback (current logic)
            self.numbering_formatter = None
    
    def _build_paragraph_style(self, para_data: Dict[str, Any]) -> str:
        """

        Builds CSS style string for paragraph based on its properties...
        """
        style_parts = []
        
        # Text alignment
        alignment = para_data.get('alignment')
        if alignment:
            # Konwertuj alignment DOCX do CSS text-align
            alignment_map = {
                'left': 'left',
                'center': 'center',
                'right': 'right',
                'justify': 'justify',
                'both': 'justify',
                'distribute': 'justify',
            }
            css_alignment = alignment_map.get(alignment.lower(), 'left')
            style_parts.append(f'text-align: {css_alignment}')
        
        # Obramowania
        borders = para_data.get('borders')
        if borders:
            border_css = self._borders_to_css(borders)
            if border_css:
                style_parts.append(border_css)
        
        # Background/Shading
        background = para_data.get('background')
        if background:
            bg_css = self._background_to_css(background)
            if bg_css:
                style_parts.append(bg_css)
        
        # Shadow
        shadow = para_data.get('shadow')
        if shadow:
            shadow_css = self._shadow_to_css(shadow)
            if shadow_css:
                style_parts.append(shadow_css)
        
        # Spacing
        spacing_before = para_data.get('spacing_before')
        if spacing_before and isinstance(spacing_before, (int, float, str)):
            try:
                # Konwertuj z twips do px (1 twip = 1/20 point, 1 point = 1.33px)
                px = int(float(spacing_before) / 20 * 1.33)
                style_parts.append(f'margin-top: {px}px')
            except (ValueError, TypeError):
                pass
        
        spacing_after = para_data.get('spacing_after')
        if spacing_after and isinstance(spacing_after, (int, float, str)):
            try:
                px = int(float(spacing_after) / 20 * 1.33)
                style_parts.append(f'margin-bottom: {px}px')
            except (ValueError, TypeError):
                pass
        
        # Indentation
        left_indent = para_data.get('left_indent')
        if left_indent and isinstance(left_indent, (int, float, str)):
            try:
                px = int(float(left_indent) / 20 * 1.33)
                style_parts.append(f'margin-left: {px}px')
            except (ValueError, TypeError):
                pass
        
        right_indent = para_data.get('right_indent')
        if right_indent and isinstance(right_indent, (int, float, str)):
            try:
                px = int(float(right_indent) / 20 * 1.33)
                style_parts.append(f'margin-right: {px}px')
            except (ValueError, TypeError):
                pass
        
        return '; '.join(style_parts) if style_parts else ''
    
    def _borders_to_css(self, borders: Dict[str, Any]) -> str:
        """

        Converts DOCX borders to CSS border.

        Args:...
        """
        if not borders or not isinstance(borders, dict):
            return ''
        
        style_parts = []
        
        # Check if this is single border
        if 'all' in borders or 'default' in borders:
            border_spec = borders.get('all') or borders.get('default')
            if border_spec:
                border_css = self._border_spec_to_css(border_spec)
                if border_css:
                    style_parts.append(f'border: {border_css}')
        else:
            # Separate borders for each side
            sides = ['top', 'right', 'bottom', 'left']
            for side in sides:
                if side in borders:
                    border_spec = borders[side]
                    border_css = self._border_spec_to_css(border_spec)
                    if border_css:
                        style_parts.append(f'border-{side}: {border_css}')
        
        return '; '.join(style_parts) if style_parts else ''
    
    def _border_spec_to_css(self, border_spec: Any) -> str:
        """

        Converts border specification to CSS.

        ...
        """
        if not border_spec:
            return ''
        
        if isinstance(border_spec, dict):
            # Get width
            width = border_spec.get('width') or border_spec.get('sz')
            if width:
                try:
                    # If width is in twips (sz), convert to px
                    if isinstance(width, str) and width.isdigit():
                        width = float(width)
                    if width > 10:  # Prawdopodobnie twips
                        width = width / 20.0  # twips do points
                    width_px = max(1, int(width * 1.33))  # points do px
                except (ValueError, TypeError):
                    width_px = 1
            else:
                width_px = 1
            
            # Pobierz styl
            style = border_spec.get('style') or border_spec.get('val') or 'solid'
            if style.lower() in ('none', 'nil'):
                return ''
            
            # Pobierz kolor
            color = border_spec.get('color') or border_spec.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color')
            if not color or color == 'auto':
                color = '#000000'
            elif not color.startswith('#'):
                color = '#' + color
            
            return f'{width_px}px {style} {color}'
        
        return ''
    
    def _background_to_css(self, background: Any) -> str:
        """

        Converts DOCX background/shading to CSS background-color.
        ...
        """
        if not background:
            return ''
        
        if isinstance(background, dict):
            # Check various possible keys for background color
            fill = background.get('fill') or background.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill')
            if fill:
                if not fill.startswith('#'):
                    fill = '#' + fill
                return f'background-color: {fill}'
        elif isinstance(background, str):
            if not background.startswith('#'):
                background = '#' + background
            return f'background-color: {background}'
        
        return ''
    
    def _shadow_to_css(self, shadow: Any) -> str:
        """

        Converts DOCX shadow to CSS box-shadow.

        Args...
        """
        if not shadow or not isinstance(shadow, dict):
            return ''
        
        # Get shadow properties
        offset_x = shadow.get('offset_x', 0) or shadow.get('offsetX', 0) or 0
        offset_y = shadow.get('offset_y', 0) or shadow.get('offsetY', 0) or 0
        blur = shadow.get('blur', 0) or shadow.get('blurRadius', 0) or 0
        color = shadow.get('color', '#000000') or '#000000'
        
        # Konwertuj jednostki (z twips do px)
        offset_x_px = int(float(offset_x) / 20 * 1.33) if offset_x else 0
        offset_y_px = int(float(offset_y) / 20 * 1.33) if offset_y else 0
        blur_px = int(float(blur) / 20 * 1.33) if blur else 0
        
        if not color.startswith('#'):
            color = '#' + color
        
        return f'box-shadow: {offset_x_px}px {offset_y_px}px {blur_px}px {color}'
    
    def _get_list_tag_from_numbering(self, numbering: Dict[str, Any]) -> tuple:
        """

        Determines HTML list tag (<ul> or <ol>) based on numbering...
        """
        if not numbering:
            return None
        
        num_id = numbering.get('id')
        level = numbering.get('level', 0)
        format_type = numbering.get('format', 'decimal')
        
        # If we have NumberingFormatter, use it to determine format
        if self.numbering_formatter and num_id:
            try:
                formatted = self.numbering_formatter.format(num_id, str(level))
                if formatted:
                    format_type = formatted.get('format', format_type)
            except Exception:
                # Fallback do prostego formatu
                pass
        
        # Determine if this is bullet or numbered
        is_bullet = format_type.lower() in ('bullet', 'disc', 'circle', 'square', 'none')
        list_tag = 'ul' if is_bullet else 'ol'
        
        return (list_tag, int(level) if isinstance(level, (int, str)) else 0, format_type)
    
    def _render_table_editable(self, table_data: Dict[str, Any]) -> str:
        """Renders table as editable HTML."""
        table = table_data.get('table')
        if not table:
            return ''
        
        html_parts = ['<table contenteditable="true" data-table-id="0">']
        
        # Renderuj wiersze
        if hasattr(table, 'rows'):
            for row_idx, row in enumerate(table.rows):
                row_html = ['<tr>']
                
                # Render cells
                if hasattr(row, 'cells'):
                    for cell_idx, cell in enumerate(row.cells):
                        # Determine if this is header cell
                        is_header = getattr(row, 'is_header_row', False) or getattr(row, 'header', False)
                        cell_tag = 'th' if is_header else 'td'
                        
                        # Render cell content (paragraphs)
                        cell_content = self._render_cell_content(cell)
                        
                        row_html.append(f'  <{cell_tag} contenteditable="true" data-row="{row_idx}" data-cell="{cell_idx}">{cell_content}</{cell_tag}>')
                
                row_html.append('</tr>')
                html_parts.append('\n'.join(row_html))
        
        html_parts.append('</table>')
        return '\n'.join(html_parts)
    
    def _render_cell_content(self, cell: Any) -> str:
        """Renders cell content (paragraphs with formatting)."""
        if not cell:
            return ''
        
        # If cell has get_paragraphs method, use it
        if hasattr(cell, 'get_paragraphs'):
            paragraphs = cell.get_paragraphs()
            para_parts = []
            for para in paragraphs:
                para_data = self._extract_paragraph_data(para)
                para_html = self._render_paragraph_html(para_data)
                para_parts.append(para_html)
            return '\n'.join(para_parts)
        elif hasattr(cell, 'get_text'):
            # Fallback: tylko tekst
            text = cell.get_text()
            return escape(text) if text else ''
        else:
            return ''
    
    def _render_paragraph_html(self, para_data: Dict[str, Any]) -> str:
        """Renderuje pojedynczy paragraf jako HTML."""
        para_parts = []
        
        # Renderuj textboxy (przed tekstem)
        if para_data.get('textboxes'):
            for textbox in para_data['textboxes']:
                textbox_html = self._render_textbox(textbox)
                para_parts.append(textbox_html)
        
        # Render text content
        if para_data.get('runs'):
            # Renderuj z formatowaniem runs
            run_parts = []
            for run in para_data['runs']:
                text = escape(run['text'])
                
                # Add footnote references if any
                if run.get('footnote_refs'):
                    for footnote_id in run['footnote_refs']:
                        footnote_ref_html = self.footnote_renderer.render_footnote_reference(footnote_id)
                        text += footnote_ref_html
                
                # Add endnote references if any
                if run.get('endnote_refs'):
                    for endnote_id in run['endnote_refs']:
                        endnote_ref_html = self.footnote_renderer.render_endnote_reference(endnote_id)
                        text += endnote_ref_html
                
                # Zbuduj style string
                style_parts = []
                if run.get('color'):
                    color = run.get('color')
                    if not color.startswith('#'):
                        color = '#' + color
                    style_parts.append(f'color: {color}')
                
                if run.get('font_size'):
                    font_size = run.get('font_size')
                    try:
                        if isinstance(font_size, str):
                            font_size = int(font_size)
                        elif not isinstance(font_size, (int, float)):
                            font_size = None
                        
                        if font_size is not None:
                            points = font_size / 2
                            px = int(points * 1.33)
                            style_parts.append(f'font-size: {px}px')
                    except (TypeError, ValueError):
                        pass
                
                if run.get('font_name'):
                    font_name = run.get('font_name')
                    style_parts.append(f"font-family: '{font_name}'")
                
                # Tagi HTML
                tags = []
                if run.get('bold'):
                    tags.append('strong')
                if run.get('italic'):
                    tags.append('em')
                if run.get('underline'):
                    tags.append('u')
                
                # Zastosuj style i tagi
                if style_parts:
                    style_str = '; '.join(style_parts)
                    text = f'<span style="{style_str}">{text}</span>'
                
                if tags:
                    for tag in tags:
                        text = f"<{tag}>{text}</{tag}>"
                
                run_parts.append(text)
            
            para_parts.append(''.join(run_parts))
        else:
            para_parts.append(escape(para_data.get('text', '')))
        
        # Render inline images (after text)
        if para_data.get('images'):
            for img_data in para_data['images']:
                image_html = self._render_image_editable(img_data)
                para_parts.append(image_html)
        
        para_content = ''.join(para_parts)
        
        # Dodaj style paragrafu
        para_style = self._build_paragraph_style(para_data)
        if para_style:
            return f'<p style="{para_style}">{para_content}</p>'
        else:
            return f'<p>{para_content}</p>'
    
    def _render_textbox(self, textbox_data: Dict[str, Any]) -> str:
        """
        Renderuje textbox jako HTML.
        
        Args:
            textbox_data: Dane textboxa z 'content' i 'runs'
            
        Returns:
            HTML dla textboxa
        """
        content = textbox_data.get('content', '')
        if not content:
            return ''
        
        # Renderuj textbox jako div z borderem (symulacja textboxa)
        return f'<div class="textbox" style="border: 1px solid #ccc; padding: 5px; margin: 5px 0; background-color: #f9f9f9;">{escape(content)}</div>'
    
    def _render_table_simple(self, table_data: Dict[str, Any]) -> str:
        """Renders simple table (non-editable) with advanced CSS positioning..."""
        table = table_data.get('table')
        if not table:
            return '<table></table>'
        
        # Get table properties
        table_style = {}
        table_class = "table-default"
        
        if hasattr(table, 'properties') and table.properties:
            props = table.properties
            if props.style:
                table_class = f"table-style-{props.style.replace(' ', '-').lower()}"
            
            # Pobierz style z properties
            if props.alignment:
                table_style['text-align'] = props.alignment
            if props.width:
                table_style['width'] = f"{props.width}pt" if isinstance(props.width, (int, float)) else str(props.width)
            if props.shading:
                fill = props.shading.get('fill') if isinstance(props.shading, dict) else None
                if fill:
                    if not fill.startswith('#'):
                        fill = f"#{fill}"
                    table_style['background-color'] = fill
        
        # Buduj style string
        style_parts = []
        if table_style:
            style_parts = [f"{k}: {v}" for k, v in table_style.items()]
        
        style_attr = f' style="{"; ".join(style_parts)}"' if style_parts else ""
        class_attr = f' class="{table_class}"' if table_class else ""
        
        # Render table
        html_parts = [f'<table{class_attr}{style_attr}>']
        
        # Renderuj wiersze
        if hasattr(table, 'rows'):
            for row_idx, row in enumerate(table.rows):
                row_html = ['<tr>']
                
                # Render cells
                if hasattr(row, 'cells'):
                    for cell_idx, cell in enumerate(row.cells):
                        # Determine if this is header cell
                        is_header = getattr(row, 'is_header_row', False) or getattr(row, 'header', False)
                        cell_tag = 'th' if is_header else 'td'
                        
                        # Get cell styles
                        cell_style = self._get_cell_style(cell)
                        cell_style_attr = f' style="{"; ".join([f"{k}: {v}" for k, v in cell_style.items()])}"' if cell_style else ""
                        
                        # Render cell content
                        cell_content = self._render_cell_content(cell)
                        
                        row_html.append(f'  <{cell_tag}{cell_style_attr}>{cell_content}</{cell_tag}>')
                
                row_html.append('</tr>')
                html_parts.append('\n'.join(row_html))
        
        html_parts.append('</table>')
        return '\n'.join(html_parts)
    
    def _get_cell_style(self, cell: Any) -> Dict[str, str]:
        """Gets styles for table cell."""
        style = {}
        
        if not cell:
            return style
        
        # Check cell properties
        if hasattr(cell, 'properties') and cell.properties:
            props = cell.properties
            
            # Vertical alignment
            if hasattr(props, 'vertical_align') and props.vertical_align:
                style['vertical-align'] = props.vertical_align
            elif hasattr(props, 'v_align') and props.v_align:
                style['vertical-align'] = props.v_align
            
            # Background color / shading
            if hasattr(props, 'shading') and props.shading:
                fill = props.shading.get('fill') if isinstance(props.shading, dict) else None
                if fill:
                    if not fill.startswith('#'):
                        fill = f"#{fill}"
                    style['background-color'] = fill
            
            # Borders
            if hasattr(props, 'borders') and props.borders:
                borders = props.borders if isinstance(props.borders, dict) else {}
                border_width = borders.get('width', '1pt')
                border_color = borders.get('color', '#000000')
                if not border_color.startswith('#'):
                    border_color = f"#{border_color}"
                style['border'] = f"{border_width} solid {border_color}"
            
            # Padding
            if hasattr(props, 'cell_margins') and props.cell_margins:
                margins = props.cell_margins if isinstance(props.cell_margins, dict) else {}
                padding_top = margins.get('top', '0pt')
                padding_right = margins.get('right', '0pt')
                padding_bottom = margins.get('bottom', '0pt')
                padding_left = margins.get('left', '0pt')
                style['padding'] = f"{padding_top} {padding_right} {padding_bottom} {padding_left}"
        
        return style
    
    def _render_image_editable(self, image_data: Dict[str, Any]) -> str:
        """Renderuje obraz jako edytowalny HTML."""
        image = image_data.get('image')
        if not image:
            return ''
        
        # Get image properties
        width = getattr(image, 'width', 0) or getattr(image, 'get_width', lambda: 0)()
        height = getattr(image, 'height', 0) or getattr(image, 'get_height', lambda: 0)()
        alt_text = getattr(image, 'get_alt', lambda: '')() or getattr(image, 'alt_text', '')
        rel_id = getattr(image, 'rel_id', '') or getattr(image, 'get_rel_id', lambda: '')()
        
        # Try to get src (image path)
        src = ''
        if hasattr(image, 'get_src'):
            src = image.get_src()
        elif hasattr(image, 'part_path'):
            src = image.part_path or ''
        
        # If no src, use rel_id as identifier
        if not src and rel_id:
            src = f"image_{rel_id}"
        
        # Convert dimensions (if in EMU, convert to px)
        # 1 EMU = 1/914400 cala, 1 cal = 96px
        if width > 1000:  # Prawdopodobnie EMU
            width_px = int(width / 914400 * 96)
        else:
            width_px = width
        
        if height > 1000:  # Prawdopodobnie EMU
            height_px = int(height / 914400 * 96)
        else:
            height_px = height
        
        # Zbuduj atrybuty
        attrs = []
        if width_px:
            attrs.append(f'width="{width_px}"')
        if height_px:
            attrs.append(f'height="{height_px}"')
        if alt_text:
            attrs.append(f'alt="{escape(alt_text)}"')
        if src:
            attrs.append(f'src="{escape(src)}"')
        else:
            attrs.append('src=""')
        
        attrs.append('contenteditable="false"')
        attrs.append(f'data-image-id="{rel_id}"')
        
        return f'<img {" ".join(attrs)} />'
    
    def _render_image_simple(self, image_data: Dict[str, Any]) -> str:
        """Renderuje prosty obraz (non-editable)."""
        return self._render_image_editable(image_data)
    
    def _render_headers_footers(self, type_name: str) -> tuple[str, str]:
        """

        Renders headers or footers in HTML.

        Args:
        ...
        """
        html_parts = []
        css_parts = []
        
        # Try to get headers/footers from document
        headers_footers = []
        
        # Check various data sources
        if hasattr(self.document, 'get_headers') and type_name == 'header':
            try:
                headers_footers = self.document.get_headers() or []
            except Exception:
                pass
        elif hasattr(self.document, 'get_footers') and type_name == 'footer':
            try:
                headers_footers = self.document.get_footers() or []
            except Exception:
                pass
        
        # If no get_headers/get_footers method, check parser
        if not headers_footers and hasattr(self.document, 'package_reader'):
            try:
                from ..parser.header_footer_parser import HeaderFooterParser
                parser = HeaderFooterParser(self.document.package_reader)
                if type_name == 'header':
                    headers_footers = list(parser.headers.values()) if hasattr(parser, 'headers') else []
                else:
                    headers_footers = list(parser.footers.values()) if hasattr(parser, 'footers') else []
            except Exception:
                pass
        
        if not headers_footers:
            return "", ""
        
        # Render each header/footer
        for idx, hf in enumerate(headers_footers):
            hf_id = f"{type_name}-{idx}"
            hf_html_parts = []
            
            # Get header/footer content
            content = []
            if isinstance(hf, dict):
                content = hf.get('content', []) or hf.get('elements', [])
            elif hasattr(hf, 'content'):
                content = hf.content if isinstance(hf.content, list) else [hf.content]
            elif hasattr(hf, 'get_content'):
                try:
                    content = hf.get_content() or []
                except Exception:
                    content = []
            
            # Render content elements
            for element in content:
                if isinstance(element, dict):
                    element_type = element.get('type', '')
                    if element_type == 'image' or 'image' in str(element).lower():
                        # Renderuj obraz
                        image_html = self._render_header_footer_image(element, type_name)
                        hf_html_parts.append(image_html)
                    elif element_type == 'paragraph' or 'paragraph' in str(element).lower():
                        # Renderuj paragraf
                        para_html = self._render_header_footer_paragraph(element, type_name)
                        hf_html_parts.append(para_html)
                    elif element_type == 'table' or 'table' in str(element).lower():
                        # Render table
                        table_html = self._render_header_footer_table(element, type_name)
                        hf_html_parts.append(table_html)
                elif hasattr(element, 'rel_id') or (hasattr(element, '__class__') and 'Image' in element.__class__.__name__):
                    # To jest obraz
                    image_html = self._render_header_footer_image({'image': element}, type_name)
                    hf_html_parts.append(image_html)
                elif hasattr(element, 'runs') or hasattr(element, 'get_text'):
                    # To jest paragraf
                    para_data = self._extract_paragraph_data(element)
                    para_html = self._render_header_footer_paragraph(para_data, type_name)
                    hf_html_parts.append(para_html)
            
            # If no content, try to get text
            if not hf_html_parts:
                text = ""
                if isinstance(hf, dict):
                    text = str(hf.get('text', ''))
                elif hasattr(hf, 'get_text'):
                    try:
                        text = hf.get_text() or ""
                    except Exception:
                        text = str(hf)
                else:
                    text = str(hf)
                
                if text:
                    hf_html_parts.append(f'<span>{escape(text)}</span>')
            
            # Create container for header/footer
            if hf_html_parts:
                newline = "\n"
                join_str = f"{newline}  "
                html_parts.append(
                    f'<div class="{type_name} {hf_id}" id="{hf_id}">{newline}'
                    f'  {join_str.join(hf_html_parts)}{newline}'
                    f'</div>'
                )
        
        # CSS dla headers/footers
        css_parts.append(f"""
        <style>
            .{type_name} {{
                position: fixed;
                width: 100%;
                max-width: 210mm; /* A4 width */
                margin: 0 auto;
                padding: 10px 20mm;
                box-sizing: border-box;
                z-index: 1000;
                background-color: white;
            }}
            .{type_name}.header-0,
            .{type_name}.header-1,
            .{type_name}.header-2 {{
                top: 0;
                border-bottom: 1px solid #ddd;
            }}
            .{type_name}.footer-0,
            .{type_name}.footer-1,
            .{type_name}.footer-2 {{
                bottom: 0;
                border-top: 1px solid #ddd;
            }}
            .{type_name} img {{
                max-width: 100%;
                height: auto;
                display: inline-block;
                vertical-align: middle;
            }}
            .{type_name} p {{
                margin: 0.3em 0;
            }}
            .{type_name} table {{
                width: 100%;
                border-collapse: collapse;
            }}
        </style>
        """)
        
        return "\n".join(html_parts), "\n".join(css_parts)
    
    def _render_header_footer_image(self, element: Dict[str, Any], type_name: str) -> str:
        """Renderuje obraz w header/footer."""
        image = element.get('image') or element
        if not image:
            return ""
        
        # Get image properties
        width = getattr(image, 'width', None) or element.get('width')
        height = getattr(image, 'height', None) or element.get('height')
        alt_text = getattr(image, 'get_alt', lambda: '')() or getattr(image, 'alt_text', '') or element.get('alt_text', '')
        rel_id = getattr(image, 'rel_id', '') or getattr(image, 'get_rel_id', lambda: '')() or element.get('rel_id', '')
        
        # Try to get src (image path)
        src = ''
        if hasattr(image, 'get_src'):
            src = image.get_src()
        elif hasattr(image, 'part_path'):
            src = image.part_path or ''
        elif hasattr(image, 'path'):
            src = image.path or ''
        elif element.get('image_path'):
            src = element.get('image_path')
        elif element.get('src'):
            src = element.get('src')
        
        # If no src, use rel_id as identifier
        if not src and rel_id:
            src = f"media/{rel_id}"
        
        # If still no src, use default
        if not src:
            src = "image.png"
        
        # Buduj atrybuty obrazu
        img_attrs = [f'alt="{escape(alt_text)}"']
        if width:
            img_attrs.append(f'width="{width}"')
        if height:
            img_attrs.append(f'height="{height}"')
        
        # Dodaj style dla pozycjonowania
        style_parts = []
        alignment = element.get('alignment', 'left')
        if alignment == 'center':
            style_parts.append('display: block; margin: 0 auto;')
        elif alignment == 'right':
            style_parts.append('float: right;')
        else:
            style_parts.append('float: left;')
        
        if style_parts:
            img_attrs.append(f'style="{"; ".join(style_parts)}"')
        
        return f'<img src="{escape(src)}" {" ".join(img_attrs)}>'
    
    def _render_header_footer_paragraph(self, para_data: Dict[str, Any], type_name: str) -> str:
        """Renderuje paragraf w header/footer."""
        return self._render_paragraph_html(para_data)
    
    def _render_header_footer_table(self, element: Dict[str, Any], type_name: str) -> str:
        """Renders table in header/footer."""
        # Use existing table rendering method
        if isinstance(element, dict) and 'table' in element:
            table = element['table']
            if hasattr(table, 'to_html'):
                return table.to_html()
        
        # Fallback: prosty render
        return '<table><tr><td>Table content</td></tr></table>'
    
    def _generate_document_styles_css(self) -> str:
        """

        Generates CSS from document styles using StyleManager.
        ...
        """
        if not self.style_manager:
            return ""
        
        css_parts = []
        css_parts.append("<style>")
        css_parts.append("/* Document Styles */")
        
        # Pobierz wszystkie style
        styles = self.style_manager.styles if hasattr(self.style_manager, 'styles') else {}
        
        for style_id, style_data in styles.items():
            style_type = style_data.get('type', 'paragraph')
            properties = style_data.get('properties', {})
            
            # Generuj CSS dla stylu
            css_selector = f".style-{style_id.replace(' ', '-').lower()}"
            css_rules = []
            
            # Paragraph styles
            if style_type == 'paragraph':
                para_props = properties.get('paragraph', {})
                run_props = properties.get('run', {})
                
                # Alignment
                alignment = para_props.get('alignment') or para_props.get('jc')
                if alignment:
                    css_rules.append(f"text-align: {alignment};")
                
                # Spacing
                spacing_before = para_props.get('spacing', {}).get('before')
                spacing_after = para_props.get('spacing', {}).get('after')
                if spacing_before:
                    css_rules.append(f"margin-top: {spacing_before}pt;")
                if spacing_after:
                    css_rules.append(f"margin-bottom: {spacing_after}pt;")
                
                # Indentation
                indent_left = para_props.get('indentation', {}).get('left')
                indent_right = para_props.get('indentation', {}).get('right')
                indent_first_line = para_props.get('indentation', {}).get('firstLine')
                if indent_left:
                    css_rules.append(f"margin-left: {indent_left}pt;")
                if indent_right:
                    css_rules.append(f"margin-right: {indent_right}pt;")
                if indent_first_line:
                    css_rules.append(f"text-indent: {indent_first_line}pt;")
                
                # Run properties (font, color, etc.)
                if run_props:
                    font_name = run_props.get('font_name') or run_props.get('font_ascii')
                    if font_name:
                        css_rules.append(f"font-family: '{font_name}', sans-serif;")
                    
                    font_size = run_props.get('font_size') or run_props.get('sz')
                    if font_size:
                        css_rules.append(f"font-size: {font_size}pt;")
                    
                    color = run_props.get('color')
                    if color:
                        if not color.startswith('#'):
                            color = f"#{color}"
                        css_rules.append(f"color: {color};")
                    
                    if run_props.get('bold'):
                        css_rules.append("font-weight: bold;")
                    if run_props.get('italic'):
                        css_rules.append("font-style: italic;")
                    if run_props.get('underline'):
                        css_rules.append("text-decoration: underline;")
            
            # Character styles
            elif style_type == 'character':
                run_props = properties.get('run', {})
                
                font_name = run_props.get('font_name') or run_props.get('font_ascii')
                if font_name:
                    css_rules.append(f"font-family: '{font_name}', sans-serif;")
                
                font_size = run_props.get('font_size') or run_props.get('sz')
                if font_size:
                    css_rules.append(f"font-size: {font_size}pt;")
                
                color = run_props.get('color')
                if color:
                    if not color.startswith('#'):
                        color = f"#{color}"
                    css_rules.append(f"color: {color};")
                
                if run_props.get('bold'):
                    css_rules.append("font-weight: bold;")
                if run_props.get('italic'):
                    css_rules.append("font-style: italic;")
                if run_props.get('underline'):
                    css_rules.append("text-decoration: underline;")
            
            # Table styles
            elif style_type == 'table':
                table_props = properties.get('table', {})
                
                # Borders
                borders = table_props.get('borders', {})
                if borders:
                    border_width = borders.get('width', '1pt')
                    border_color = borders.get('color', '#000000')
                    if not border_color.startswith('#'):
                        border_color = f"#{border_color}"
                    css_rules.append(f"border: {border_width} solid {border_color};")
                
                # Shading
                shading = table_props.get('shading', {}).get('fill')
                if shading:
                    if not shading.startswith('#'):
                        shading = f"#{shading}"
                    css_rules.append(f"background-color: {shading};")
            
            # Add CSS rules if any
            if css_rules:
                css_parts.append(f"{css_selector} {{")
                css_parts.append("  " + "\n  ".join(css_rules))
                css_parts.append("}")
        
        css_parts.append("</style>")
        
        return "\n".join(css_parts) if len(css_parts) > 2 else ""
    
    def _get_table_positioning_css(self) -> str:
        """

        Generates CSS for advanced table positioning.
        ...
        """
        return """
        <style>
            /* Table Positioning and Layout */
            table {
                border-collapse: collapse;
                border-spacing: 0;
                width: 100%;
                max-width: 100%;
                margin: 1em 0;
                display: table;
                table-layout: auto;
            }
            
            /* Table alignment */
            table[style*="text-align: center"],
            table.align-center {
                margin-left: auto;
                margin-right: auto;
            }
            
            table[style*="text-align: right"],
            table.align-right {
                margin-left: auto;
                margin-right: 0;
            }
            
            table[style*="text-align: left"],
            table.align-left {
                margin-left: 0;
                margin-right: auto;
            }
            
            /* Table wrapper for advanced positioning */
            .table-wrapper {
                position: relative;
                width: 100%;
                margin: 1em 0;
                overflow-x: auto;
            }
            
            .table-wrapper table {
                margin: 0;
            }
            
            /* Responsive table */
            @media (max-width: 768px) {
                table {
                    display: block;
                    width: 100%;
                    overflow-x: auto;
                    -webkit-overflow-scrolling: touch;
                }
                
                thead, tbody, tr {
                    display: block;
                }
                
                th, td {
                    display: block;
                    width: 100%;
                    box-sizing: border-box;
                }
            }
            
            /* Table cells */
            th, td {
                padding: 8px 12px;
                text-align: left;
                vertical-align: top;
                border: 1px solid #ddd;
            }
            
            th {
                font-weight: bold;
                background-color: #f5f5f5;
            }
            
            /* Table cell alignment */
            th[style*="text-align: center"],
            td[style*="text-align: center"],
            .cell-center {
                text-align: center;
            }
            
            th[style*="text-align: right"],
            td[style*="text-align: right"],
            .cell-right {
                text-align: right;
            }
            
            th[style*="vertical-align: middle"],
            td[style*="vertical-align: middle"],
            .cell-middle {
                vertical-align: middle;
            }
            
            th[style*="vertical-align: bottom"],
            td[style*="vertical-align: bottom"],
            .cell-bottom {
                vertical-align: bottom;
            }
            
            /* Table borders */
            table.bordered th,
            table.bordered td {
                border: 1px solid #000;
            }
            
            table.borderless th,
            table.borderless td {
                border: none;
            }
            
            /* Table spacing */
            table.spaced th,
            table.spaced td {
                padding: 12px 16px;
            }
            
            /* Table striped rows */
            table.striped tbody tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            
            /* Table hover effect */
            table.hoverable tbody tr:hover {
                background-color: #f0f0f0;
            }
        </style>
        """
    
    def _get_editable_css(self) -> str:
        """Zwraca CSS dla edytowalnego HTML."""
        return """
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            p[contenteditable="true"] {
                min-height: 1.2em;
                margin: 0.5em 0;
                padding: 0.2em;
                border: 1px solid transparent;
            }
            p[contenteditable="true"]:focus {
                outline: none;
                border-color: #4CAF50;
                background-color: #f9f9f9;
            }
            p[contenteditable="true"]:empty:before {
                content: "\\00a0";
                color: #999;
            }
        </style>
        """
    
    def _get_editable_js(self) -> str:
        """Zwraca JavaScript dla edytowalnego HTML."""
        """

        <script>
        // Save changes to localStorage
        ...
        """

    def save_to_file(self, html: str, output_path: Union[str, Path]) -> bool:
        Path(output_path).write_text(html, encoding="utf-8")
        return True

    def _collect_paragraph_text(self) -> Sequence[str]:
        if hasattr(self.document, "get_paragraphs"):
            paragraphs = []
            for paragraph in self.document.get_paragraphs() or []:
                if hasattr(paragraph, "get_text"):
                    paragraphs.append(self.placeholder_resolver.resolve_text(paragraph.get_text()))
                else:
                    paragraphs.append(
                        self.placeholder_resolver.resolve_text(str(getattr(paragraph, "text", "")))
                    )
            return paragraphs

        if hasattr(self.document, "get_text"):
            return [
                self.placeholder_resolver.resolve_text(line)
                for line in str(self.document.get_text()).splitlines()
            ]

        return []


class PDFRenderer:
    """High-level PDF renderer that integrates with the layout engine."""

    def __init__(
        self,
        document,
        *,
        page_size: Union[str, Size, Iterable[float]] = "A4",
        margins: Union[Margins, Iterable[float]] = (50, 50, 50, 50),
        dpi: float = 72.0,
    ) -> None:
        self.document = document
        self._page_size_tuple = ensure_page_size(page_size)
        self._page_size = Size(*self._page_size_tuple)
        self._margins = ensure_margins(margins)
        self._dpi = dpi

    def render(self, output_path: Optional[Union[str, Path]] = None) -> bytes:
        layout_pages = self._build_layout()
        pdf_renderer = PdfRenderer(self._page_size_tuple, self._margins, dpi=self._dpi)

        if output_path:
            pdf_renderer.render(layout_pages, str(output_path))
            return Path(output_path).read_bytes()

        buffer = BytesIO()
        pdf_renderer.render(layout_pages, buffer)
        return buffer.getvalue()

    def save_to_file(self, pdf_bytes: bytes, output_path: Union[str, Path]) -> bool:
        Path(output_path).write_bytes(pdf_bytes)
        return True

    def _build_layout(self):
        resolver = PlaceholderResolver(getattr(self.document, "placeholder_values", {}))
        numbering_data = getattr(self.document, "_numbering", None)
        engine = DocumentEngine(
            page_size=self._page_size,
            margins=self._margins,
            placeholder_resolver=resolver,
            numbering_data=numbering_data,
        )
        return engine.build_layout(self.document)


class DOCXRenderer:
    """Diagnostic renderer returning a textual structure representation."""

    def __init__(self, document) -> None:
        self.document = document

    def render(self) -> str:
        paragraphs = len(list(self.document.get_paragraphs() or [])) if hasattr(self.document, "get_paragraphs") else 0
        tables = len(list(self.document.get_tables() or [])) if hasattr(self.document, "get_tables") else 0
        images = len(list(self.document.get_images() or [])) if hasattr(self.document, "get_images") else 0

        resolver = PlaceholderResolver(getattr(self.document, "placeholder_values", {}))

        summary = [
            "DOCX Document Structure",
            f"Paragraphs: {paragraphs}",
            f"Tables: {tables}",
            f"Images: {images}",
        ]
        return "\n".join(resolver.resolve_text(part) for part in summary)

    def save_to_file(self, content: str, output_path: Union[str, Path]) -> bool:
        Path(output_path).write_text(content, encoding="utf-8")
        return True

