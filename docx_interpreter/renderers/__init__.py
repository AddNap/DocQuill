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
        
        # Inicjalizuj NumberingFormatter jeśli numbering data jest dostępne
        self.numbering_formatter = None
        self._init_numbering_formatter()
        
        # Inicjalizuj FieldRenderer dla obsługi field codes
        self.field_renderer = FieldRenderer(context)
        
        # Inicjalizuj FootnoteRenderer dla obsługi footnotes i endnotes
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
        
        # Inicjalizuj WatermarkRenderer dla obsługi watermarków
        watermarks = getattr(document, 'watermarks', None) or []
        if hasattr(document, 'get_watermarks'):
            try:
                watermarks = document.get_watermarks() or []
            except Exception:
                pass
        self.watermark_renderer = WatermarkRenderer(watermarks)
        
        # Store watermarks for PDF rendering
        self._watermarks = watermarks
        
        # Inicjalizuj StyleManager dla obsługi stylów dokumentu
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

        # Renderuj sekcję footnotes i endnotes jeśli są
        footnotes_section = self.footnote_renderer.render_footnotes_section()
        endnotes_section = self.footnote_renderer.render_endnotes_section()
        footnotes_css = self.footnote_renderer.get_footnote_css()
        
        # Renderuj watermarki jeśli są
        # Default page size A4: 210mm x 297mm
        page_width_mm = 210.0
        page_height_mm = 297.0
        watermark_html = self.watermark_renderer.render_html(page_width_mm, page_height_mm)
        watermark_css = self.watermark_renderer.get_watermark_css()

        # Renderuj nagłówki i stopki jeśli są dostępne
        headers_html, headers_css = self._render_headers_footers('header')
        footers_html, footers_css = self._render_headers_footers('footer')
        
        # Generuj CSS z stylów dokumentu
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
        """Zbiera paragrafy i tabele z dokumentu w kolejności występowania."""
        elements = []
        
        # Jeśli dokument ma body z children, użyj ich kolejności
        if (hasattr(self.document, 'body') and 
            hasattr(self.document.body, 'children') and 
            hasattr(self.document.body.children, '__iter__')):
            try:
                for child in self.document.body.children:
                    # Sprawdź czy to tabela
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
        
        # Jeśli nie udało się zebrać z body.children, użyj get_paragraphs/get_tables
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
                    # get_tables() zwróciło Mock lub nie jest iterowalne
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
                    # get_images() zwróciło Mock lub nie jest iterowalne
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
        """Ekstraktuje dane paragrafu do słownika."""
        para_data = {
            'type': 'paragraph',
            'text': '',
            'runs': [],
            'numbering': None
        }
        
        # Sprawdź czy paragraf ma numbering (lista)
        if hasattr(para, 'numbering') and para.numbering:
            numbering_info = para.numbering
            if isinstance(numbering_info, dict):
                para_data['numbering'] = {
                    'id': numbering_info.get('id'),
                    'level': numbering_info.get('level', 0),
                    'format': numbering_info.get('format', 'decimal')
                }
            else:
                # Jeśli numbering jest w innym formacie, spróbuj wyciągnąć podstawowe info
                para_data['numbering'] = {
                    'id': getattr(numbering_info, 'id', None) or getattr(numbering_info, 'num_id', None),
                    'level': getattr(numbering_info, 'level', 0),
                    'format': getattr(numbering_info, 'format', 'decimal')
                }
        
        # Sprawdź czy paragraf ma field codes bezpośrednio jako children (nie w runach)
        para_fields = []
        if hasattr(para, 'children') and para.children:
            for child in para.children:
                # Sprawdź czy to Field
                if (hasattr(child, '__class__') and 
                    ('Field' in child.__class__.__name__ or 
                     hasattr(child, 'field_type') or 
                     hasattr(child, 'instr'))):
                    para_fields.append(child)
        
        # Jeśli paragraf ma field codes bezpośrednio, renderuj je jako osobny run
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
                # Sprawdź czy run ma obraz
                run_image = getattr(run, 'image', None)
                if run_image:
                    # Dodaj obraz jako specjalny element w paragrafie
                    if 'images' not in para_data:
                        para_data['images'] = []
                    para_data['images'].append({
                        'image': run_image,
                        'position': 'inline'  # Obraz inline w runie
                    })
                
                # Sprawdź czy run ma textbox
                run_textbox = getattr(run, 'textbox', None)
                if run_textbox:
                    # Dodaj textbox jako specjalny element
                    if 'textboxes' not in para_data:
                        para_data['textboxes'] = []
                    # Textbox to lista runów
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
                
                # Sprawdź czy run ma field codes (children typu Field)
                run_fields = []
                if hasattr(run, 'children') and run.children:
                    for child in run.children:
                        # Sprawdź czy to Field
                        if (hasattr(child, '__class__') and 
                            ('Field' in child.__class__.__name__ or 
                             hasattr(child, 'field_type') or 
                             hasattr(child, 'instr'))):
                            run_fields.append(child)
                
                # Jeśli run ma field codes, renderuj je
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
                
                # Jeśli run ma footnote references, zapisz je
                if run_footnote_refs:
                    if 'footnote_refs' not in para_data:
                        para_data['footnote_refs'] = []
                    para_data['footnote_refs'].extend(run_footnote_refs)
                
                # Jeśli run ma endnote references, zapisz je
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
        
        # Zbierz właściwości paragrafu (alignment, borders, background)
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
        # Zachowana dla kompatybilności wstecznej
        elements = self._collect_content_elements()
        return [e for e in elements if e.get('type') == 'paragraph']
    
    def _render_editable_body(self, content_elements: List[Dict[str, Any]]) -> str:
        """Renderuje body z contenteditable i formatowaniem, obsługując listy i tabele."""
        body_parts = []
        current_list = None  # (tag, level, list_items)
        list_items = []
        
        for i, elem in enumerate(content_elements):
            # Obsługa obrazów
            if elem.get('type') == 'image':
                # Zamknij otwartą listę jeśli jest
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
            
            # Obsługa tabel
            if elem.get('type') == 'table':
                # Zamknij otwartą listę jeśli jest
                if current_list:
                    items = current_list[3] if len(current_list) > 3 else list_items
                    list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                        for j, item in enumerate(items))
                    body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
                    list_items = []
                    current_list = None
                
                # Renderuj tabelę
                table_html = self._render_table_editable(elem)
                body_parts.append(table_html)
                continue
            
            # Obsługa paragrafów
            para = elem
            numbering = para.get('numbering')
            
            # Renderuj zawartość paragrafu
            if para['runs']:
                # Renderuj z formatowaniem runs
                run_parts = []
                for run in para['runs']:
                    text = escape(run['text'])
                    
                    # Zbuduj style string dla zagnieżdżonego formatowania
                    style_parts = []
                    
                    # Kolory i czcionki
                    if run.get('color'):
                        color = run.get('color')
                        # Upewnij się, że kolor jest w formacie hex
                        if not color.startswith('#'):
                            color = '#' + color
                        style_parts.append(f'color: {color}')
                    
                    if run.get('font_size'):
                        font_size = run.get('font_size')
                        # Konwertuj half-points do px (przybliżenie)
                        try:
                            if isinstance(font_size, str):
                                try:
                                    font_size = int(font_size)
                                except ValueError:
                                    font_size = None
                            elif not isinstance(font_size, (int, float)):
                                # Jeśli to Mock lub inny typ, pomiń
                                font_size = None
                            
                            if font_size is not None:
                                # Half-points do points, potem do px
                                points = font_size / 2
                                px = int(points * 1.33)  # 1pt ≈ 1.33px
                                style_parts.append(f'font-size: {px}px')
                        except (TypeError, ValueError):
                            # Jeśli konwersja się nie powiodła, pomiń font-size
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
                        font_size_unit = 'px'  # Domyślnie px (jak w kodzie powyżej)
                        
                        # Sprawdź czy font-size jest już w style_parts
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
                            # Spróbuj pobrać z run style (może być w różnych jednostkach)
                            run_style = run.get('style', {})
                            if isinstance(run_style, dict):
                                font_size_raw = run_style.get('font_size')
                                if font_size_raw:
                                    try:
                                        # Jeśli to half-points (jak w DOCX), konwertuj na px
                                        font_size_val = float(font_size_raw)
                                        # Half-points do points, potem do px
                                        points = font_size_val / 2
                                        current_font_size_px = points * 1.33
                                    except (TypeError, ValueError):
                                        pass
                        
                        if current_font_size_px:
                            # Zmniejsz font_size do 58% (tak samo jak w footnotes)
                            new_font_size_px = int(current_font_size_px * 0.58)
                            # Usuń stary font-size z style_parts jeśli istnieje
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
            
            # Obsługa list
            if numbering:
                # Użyj NumberingFormatter do określenia typu listy
                list_info = self._get_list_tag_from_numbering(numbering)
                if not list_info:
                    # Fallback do obecnej logiki
                    level = numbering.get('level', 0)
                    format_type = numbering.get('format', 'decimal')
                    is_bullet = format_type.lower() in ('bullet', 'disc', 'circle', 'square', 'none')
                    list_tag = 'ul' if is_bullet else 'ol'
                    list_info = (list_tag, int(level) if isinstance(level, (int, str)) else 0, format_type)
                
                list_tag, level, format_type = list_info
                
                # Jeśli zmieniła się lista (tag lub level), zamknij poprzednią
                if current_list and (current_list[0] != list_tag or current_list[1] != level):
                    # Zamknij poprzednią listę
                    items = current_list[3] if len(current_list) > 3 else list_items
                    list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                        for j, item in enumerate(items))
                    body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
                    list_items = []
                    current_list = None
                
                # Rozpocznij nową listę jeśli potrzeba
                if not current_list:
                    current_list = (list_tag, level, format_type, [])
                elif len(current_list) == 3:
                    # Konwertuj starą strukturę do nowej
                    old_items = current_list[2] if isinstance(current_list[2], list) else list_items
                    current_list = (current_list[0], current_list[1], format_type, old_items)
                
                # Dodaj element do listy
                if len(current_list) > 3:
                    current_list[3].append(para_html)
                else:
                    list_items.append(para_html)
            else:
                # Jeśli był otwarta lista, zamknij ją
                if current_list:
                    items = current_list[3] if len(current_list) > 3 else list_items
                    list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                        for j, item in enumerate(items))
                    body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
                    list_items = []
                    current_list = None
                
                # Zwykły paragraf z właściwościami
                para_style = self._build_paragraph_style(para)
                if para_style:
                    body_parts.append(f'<p contenteditable="true" data-para-id="{len(body_parts)}" style="{para_style}">{para_html}</p>')
                else:
                    body_parts.append(f'<p contenteditable="true" data-para-id="{len(body_parts)}">{para_html}</p>')
        
        # Zamknij ostatnią listę jeśli jest otwarta
        if current_list:
            items = current_list[3] if len(current_list) > 3 else list_items
            list_html = '\n'.join(f'  <li contenteditable="true" data-para-id="{len(body_parts) + j}">{item}</li>' 
                                for j, item in enumerate(items))
            body_parts.append(f'<{current_list[0]}>\n{list_html}\n</{current_list[0]}>')
        
        return '\n'.join(body_parts)
    
    def _init_numbering_formatter(self) -> None:
        """Inicjalizuje NumberingFormatter jeśli numbering data jest dostępne."""
        try:
            from ..engine.numbering_formatter import NumberingFormatter
            
            # Spróbuj pobrać numbering data z dokumentu
            numbering_data = None
            
            # Sprawdź różne możliwe lokalizacje numbering data
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
            
            # Jeśli mamy numbering data, utwórz formatter
            if numbering_data:
                self.numbering_formatter = NumberingFormatter(numbering_data)
        except (ImportError, AttributeError, Exception) as e:
            # Jeśli nie można zainicjalizować, użyj fallback (obecna logika)
            self.numbering_formatter = None
    
    def _build_paragraph_style(self, para_data: Dict[str, Any]) -> str:
        """
        Buduje CSS style string dla paragrafu na podstawie jego właściwości.
        
        Args:
            para_data: Dane paragrafu z właściwościami
            
        Returns:
            CSS style string lub pusty string
        """
        style_parts = []
        
        # Wyrównanie tekstu
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
        
        # Tło/Cieniowanie
        background = para_data.get('background')
        if background:
            bg_css = self._background_to_css(background)
            if bg_css:
                style_parts.append(bg_css)
        
        # Cień
        shadow = para_data.get('shadow')
        if shadow:
            shadow_css = self._shadow_to_css(shadow)
            if shadow_css:
                style_parts.append(shadow_css)
        
        # Odstępy
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
        
        # Wcięcia
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
        Konwertuje obramowania DOCX do CSS border.
        
        Args:
            borders: Słownik z obramowaniami
            
        Returns:
            CSS border string
        """
        if not borders or not isinstance(borders, dict):
            return ''
        
        style_parts = []
        
        # Sprawdź czy to pojedyncze obramowanie
        if 'all' in borders or 'default' in borders:
            border_spec = borders.get('all') or borders.get('default')
            if border_spec:
                border_css = self._border_spec_to_css(border_spec)
                if border_css:
                    style_parts.append(f'border: {border_css}')
        else:
            # Osobne obramowania dla każdej strony
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
        Konwertuje specyfikację obramowania do CSS.
        
        Args:
            border_spec: Specyfikacja obramowania (dict lub inny format)
            
        Returns:
            CSS border string (np. "1px solid #000000")
        """
        if not border_spec:
            return ''
        
        if isinstance(border_spec, dict):
            # Pobierz szerokość
            width = border_spec.get('width') or border_spec.get('sz')
            if width:
                try:
                    # Jeśli width jest w twips (sz), konwertuj do px
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
        Konwertuje tło/cieniowanie DOCX do CSS background-color.
        
        Args:
            background: Tło (dict lub string)
            
        Returns:
            CSS background-color string
        """
        if not background:
            return ''
        
        if isinstance(background, dict):
            # Sprawdź różne możliwe klucze dla koloru tła
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
        Konwertuje cień DOCX do CSS box-shadow.
        
        Args:
            shadow: Cień (dict)
            
        Returns:
            CSS box-shadow string
        """
        if not shadow or not isinstance(shadow, dict):
            return ''
        
        # Pobierz właściwości cienia
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
        Określa tag HTML listy (<ul> lub <ol>) na podstawie numbering.
        Używa NumberingFormatter jeśli dostępny, w przeciwnym razie używa prostego formatu.
        
        Returns:
            Tuple (tag, level, format_type) - tag HTML, poziom, typ formatu
        """
        if not numbering:
            return None
        
        num_id = numbering.get('id')
        level = numbering.get('level', 0)
        format_type = numbering.get('format', 'decimal')
        
        # Jeśli mamy NumberingFormatter, użyj go do określenia formatu
        if self.numbering_formatter and num_id:
            try:
                formatted = self.numbering_formatter.format(num_id, str(level))
                if formatted:
                    format_type = formatted.get('format', format_type)
            except Exception:
                # Fallback do prostego formatu
                pass
        
        # Określ czy to bullet czy numbered
        is_bullet = format_type.lower() in ('bullet', 'disc', 'circle', 'square', 'none')
        list_tag = 'ul' if is_bullet else 'ol'
        
        return (list_tag, int(level) if isinstance(level, (int, str)) else 0, format_type)
    
    def _render_table_editable(self, table_data: Dict[str, Any]) -> str:
        """Renderuje tabelę jako edytowalny HTML."""
        table = table_data.get('table')
        if not table:
            return ''
        
        html_parts = ['<table contenteditable="true" data-table-id="0">']
        
        # Renderuj wiersze
        if hasattr(table, 'rows'):
            for row_idx, row in enumerate(table.rows):
                row_html = ['<tr>']
                
                # Renderuj komórki
                if hasattr(row, 'cells'):
                    for cell_idx, cell in enumerate(row.cells):
                        # Określ czy to header cell
                        is_header = getattr(row, 'is_header_row', False) or getattr(row, 'header', False)
                        cell_tag = 'th' if is_header else 'td'
                        
                        # Renderuj zawartość komórki (paragrafy)
                        cell_content = self._render_cell_content(cell)
                        
                        row_html.append(f'  <{cell_tag} contenteditable="true" data-row="{row_idx}" data-cell="{cell_idx}">{cell_content}</{cell_tag}>')
                
                row_html.append('</tr>')
                html_parts.append('\n'.join(row_html))
        
        html_parts.append('</table>')
        return '\n'.join(html_parts)
    
    def _render_cell_content(self, cell: Any) -> str:
        """Renderuje zawartość komórki (paragrafy z formatowaniem)."""
        if not cell:
            return ''
        
        # Jeśli komórka ma metodę get_paragraphs, użyj jej
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
        
        # Renderuj zawartość tekstową
        if para_data.get('runs'):
            # Renderuj z formatowaniem runs
            run_parts = []
            for run in para_data['runs']:
                text = escape(run['text'])
                
                # Dodaj footnote references jeśli są
                if run.get('footnote_refs'):
                    for footnote_id in run['footnote_refs']:
                        footnote_ref_html = self.footnote_renderer.render_footnote_reference(footnote_id)
                        text += footnote_ref_html
                
                # Dodaj endnote references jeśli są
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
        
        # Renderuj obrazy inline (po tekście)
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
        """Renderuje prostą tabelę (non-editable) z zaawansowanym CSS positioning."""
        table = table_data.get('table')
        if not table:
            return '<table></table>'
        
        # Pobierz właściwości tabeli
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
        
        # Renderuj tabelę
        html_parts = [f'<table{class_attr}{style_attr}>']
        
        # Renderuj wiersze
        if hasattr(table, 'rows'):
            for row_idx, row in enumerate(table.rows):
                row_html = ['<tr>']
                
                # Renderuj komórki
                if hasattr(row, 'cells'):
                    for cell_idx, cell in enumerate(row.cells):
                        # Określ czy to header cell
                        is_header = getattr(row, 'is_header_row', False) or getattr(row, 'header', False)
                        cell_tag = 'th' if is_header else 'td'
                        
                        # Pobierz style komórki
                        cell_style = self._get_cell_style(cell)
                        cell_style_attr = f' style="{"; ".join([f"{k}: {v}" for k, v in cell_style.items()])}"' if cell_style else ""
                        
                        # Renderuj zawartość komórki
                        cell_content = self._render_cell_content(cell)
                        
                        row_html.append(f'  <{cell_tag}{cell_style_attr}>{cell_content}</{cell_tag}>')
                
                row_html.append('</tr>')
                html_parts.append('\n'.join(row_html))
        
        html_parts.append('</table>')
        return '\n'.join(html_parts)
    
    def _get_cell_style(self, cell: Any) -> Dict[str, str]:
        """Pobiera style dla komórki tabeli."""
        style = {}
        
        if not cell:
            return style
        
        # Sprawdź właściwości komórki
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
        
        # Pobierz właściwości obrazu
        width = getattr(image, 'width', 0) or getattr(image, 'get_width', lambda: 0)()
        height = getattr(image, 'height', 0) or getattr(image, 'get_height', lambda: 0)()
        alt_text = getattr(image, 'get_alt', lambda: '')() or getattr(image, 'alt_text', '')
        rel_id = getattr(image, 'rel_id', '') or getattr(image, 'get_rel_id', lambda: '')()
        
        # Spróbuj pobrać src (ścieżkę do obrazu)
        src = ''
        if hasattr(image, 'get_src'):
            src = image.get_src()
        elif hasattr(image, 'part_path'):
            src = image.part_path or ''
        
        # Jeśli nie ma src, użyj rel_id jako identyfikatora
        if not src and rel_id:
            src = f"image_{rel_id}"
        
        # Konwertuj wymiary (jeśli są w EMU, konwertuj do px)
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
        Renderuje nagłówki lub stopki w HTML.
        
        Args:
            type_name: 'header' lub 'footer'
            
        Returns:
            Tuple (html_content, css_styles)
        """
        html_parts = []
        css_parts = []
        
        # Spróbuj pobrać headers/footers z dokumentu
        headers_footers = []
        
        # Sprawdź różne źródła danych
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
        
        # Jeśli nie ma metody get_headers/get_footers, sprawdź parser
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
        
        # Renderuj każdy header/footer
        for idx, hf in enumerate(headers_footers):
            hf_id = f"{type_name}-{idx}"
            hf_html_parts = []
            
            # Pobierz zawartość header/footer
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
            
            # Renderuj elementy zawartości
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
                        # Renderuj tabelę
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
            
            # Jeśli nie ma zawartości, spróbuj pobrać tekst
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
            
            # Utwórz kontener dla header/footer
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
        
        # Pobierz właściwości obrazu
        width = getattr(image, 'width', None) or element.get('width')
        height = getattr(image, 'height', None) or element.get('height')
        alt_text = getattr(image, 'get_alt', lambda: '')() or getattr(image, 'alt_text', '') or element.get('alt_text', '')
        rel_id = getattr(image, 'rel_id', '') or getattr(image, 'get_rel_id', lambda: '')() or element.get('rel_id', '')
        
        # Spróbuj pobrać src (ścieżkę do obrazu)
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
        
        # Jeśli nie ma src, użyj rel_id jako identyfikatora
        if not src and rel_id:
            src = f"media/{rel_id}"
        
        # Jeśli nadal nie ma src, użyj domyślnego
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
        """Renderuje tabelę w header/footer."""
        # Użyj istniejącej metody renderowania tabel
        if isinstance(element, dict) and 'table' in element:
            table = element['table']
            if hasattr(table, 'to_html'):
                return table.to_html()
        
        # Fallback: prosty render
        return '<table><tr><td>Table content</td></tr></table>'
    
    def _generate_document_styles_css(self) -> str:
        """
        Generuje CSS z stylów dokumentu używając StyleManager.
        
        Returns:
            CSS string z definicjami stylów
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
            
            # Dodaj reguły CSS jeśli są
            if css_rules:
                css_parts.append(f"{css_selector} {{")
                css_parts.append("  " + "\n  ".join(css_rules))
                css_parts.append("}")
        
        css_parts.append("</style>")
        
        return "\n".join(css_parts) if len(css_parts) > 2 else ""
    
    def _get_table_positioning_css(self) -> str:
        """
        Generuje CSS dla zaawansowanego pozycjonowania tabel.
        
        Returns:
            CSS string z regułami pozycjonowania tabel
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
        return """
        <script>
            // Zapisz zmiany do localStorage
            document.addEventListener('DOMContentLoaded', function() {
                const paragraphs = document.querySelectorAll('p[contenteditable="true"]');
                
                paragraphs.forEach(function(p) {
                    // Zapisz przy zmianie
                    p.addEventListener('input', function() {
                        saveContent();
                    });
                    
                    // Obsługa skrótów klawiszowych
                    p.addEventListener('keydown', function(e) {
                        // Ctrl+B - bold
                        if (e.ctrlKey && e.key === 'b') {
                            e.preventDefault();
                            document.execCommand('bold', false, null);
                        }
                        // Ctrl+I - italic
                        if (e.ctrlKey && e.key === 'i') {
                            e.preventDefault();
                            document.execCommand('italic', false, null);
                        }
                        // Ctrl+U - underline
                        if (e.ctrlKey && e.key === 'u') {
                            e.preventDefault();
                            document.execCommand('underline', false, null);
                        }
                    });
                });
                
                // Wczytaj zapisane dane
                loadContent();
            });
            
            function saveContent() {
                const paragraphs = document.querySelectorAll('p[contenteditable="true"]');
                const content = Array.from(paragraphs).map(p => p.innerHTML);
                localStorage.setItem('docx_content', JSON.stringify(content));
            }
            
            function loadContent() {
                const saved = localStorage.getItem('docx_content');
                if (saved) {
                    try {
                        const content = JSON.parse(saved);
                        const paragraphs = document.querySelectorAll('p[contenteditable="true"]');
                        content.forEach((html, i) => {
                            if (paragraphs[i]) {
                                paragraphs[i].innerHTML = html;
                            }
                        });
                    } catch (e) {
                        console.error('Failed to load saved content:', e);
                    }
                }
            }
        </script>
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

