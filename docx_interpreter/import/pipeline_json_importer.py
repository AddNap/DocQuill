"""
Importer JSON do UnifiedLayout i Document Model.

Umożliwia odwrócenie procesu: JSON → UnifiedLayout → Document Model → DOCX

UWAGA: To jest uproszczona konwersja - UnifiedLayout ma pozycjonowanie i paginację,
które nie są w Document Model. Ta implementacja odtwarza podstawową strukturę dokumentu.
"""

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from ..engine.unified_layout import UnifiedLayout, LayoutPage, LayoutBlock
from ..engine.geometry import Rect, Size, Margins
from ..models.paragraph import Paragraph
from ..models.run import Run
from ..models.table import Table
from ..models.image import Image


class PipelineJSONImporter:
    """
    Importer JSON zoptymalizowanego formatu pipeline.
    
    Konwertuje JSON z powrotem do UnifiedLayout, a następnie do Document Model.
    """
    
    def __init__(self, json_data: Optional[Dict[str, Any]] = None, json_path: Optional[Path] = None):
        """
        Args:
            json_data: Dane JSON (dict) - jeśli podane, json_path jest ignorowany
            json_path: Ścieżka do pliku JSON
        """
        if json_data is not None:
            self.json_data = json_data
        elif json_path:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.json_data = json.load(f)
        else:
            raise ValueError("Musisz podać json_data lub json_path")
        
        self._styles_map: Dict[int, Dict[str, Any]] = {}
        self._media_map: Dict[int, Dict[str, Any]] = {}
        self._load_maps()
    
    def _load_maps(self):
        """Ładuje mapy stylów i media z JSON."""
        # Style
        styles = self.json_data.get('styles', [])
        for i, style in enumerate(styles):
            self._styles_map[i] = style
        
        # Media
        media = self.json_data.get('media', [])
        for i, media_item in enumerate(media):
            self._media_map[i] = media_item
    
    def to_unified_layout(self) -> UnifiedLayout:
        """
        Konwertuje JSON do UnifiedLayout.
        
        Returns:
            UnifiedLayout z danymi z JSON
        """
        unified_layout = UnifiedLayout()
        
        pages_data = self.json_data.get('pages', [])
        for page_data in pages_data:
            # Deserializuj stronę
            page = self._deserialize_page(page_data)
            unified_layout.pages.append(page)
        
        # Ustaw current_page
        unified_layout.current_page = self.json_data.get('metadata', {}).get('current_page', 1)
        
        return unified_layout
    
    def _deserialize_page(self, page_data: Dict[str, Any]) -> LayoutPage:
        """Deserializuje stronę z JSON."""
        # Size
        size_data = page_data.get('size', [595.0, 842.0])
        if isinstance(size_data, list) and len(size_data) >= 2:
            size = Size(size_data[0], size_data[1])
        else:
            size = Size(595.0, 842.0)  # Domyślnie A4
        
        # Margins
        margins_data = page_data.get('margins', [72, 72, 72, 72])
        if isinstance(margins_data, list) and len(margins_data) >= 4:
            margins = Margins(
                top=margins_data[0],
                right=margins_data[1],
                bottom=margins_data[2],
                left=margins_data[3]
            )
        else:
            margins = Margins(72, 72, 72, 72)  # Domyślnie 1 cal
        
        # Utwórz stronę
        page = LayoutPage(
            number=page_data.get('n', 1),
            size=size,
            margins=margins,
            skip_headers_footers=page_data.get('skip_headers_footers', False)
        )
        
        # Deserializuj bloki
        blocks_data = page_data.get('blocks', [])
        for block_data in blocks_data:
            block = self._deserialize_block(block_data)
            page.blocks.append(block)
        
        return page
    
    def _deserialize_block(self, block_data: Dict[str, Any]) -> LayoutBlock:
        """Deserializuje blok z JSON."""
        # Frame
        frame_data = block_data.get('f', [0, 0, 0, 0])
        if isinstance(frame_data, list) and len(frame_data) >= 4:
            frame = Rect(
                x=frame_data[0],
                y=frame_data[1],
                width=frame_data[2],
                height=frame_data[3]
            )
        else:
            frame = Rect(0, 0, 0, 0)
        
        # Block type
        block_type = block_data.get('t', 'paragraph')
        
        # Style
        style_id = block_data.get('s')
        style = self._styles_map.get(style_id, {}) if style_id is not None else {}
        
        # Content
        content = self._deserialize_content(block_data.get('c', {}), block_type)
        
        # Opcjonalne pola
        page_number = block_data.get('p')
        source_uid = block_data.get('uid')
        sequence = block_data.get('seq')
        
        return LayoutBlock(
            frame=frame,
            block_type=block_type,
            content=content,
            style=style,
            page_number=page_number,
            source_uid=source_uid,
            sequence=sequence
        )
    
    def _deserialize_content(self, content_data: Dict[str, Any], block_type: str) -> Any:
        """Deserializuje content z JSON."""
        if not content_data:
            return None
        
        content_type = content_data.get('type', '')
        
        # Paragraph
        if content_type == 'paragraph' or block_type == 'paragraph':
            return {
                'type': 'paragraph',
                'text': content_data.get('text', '')
            }
        
        # Table
        if content_type == 'table' or block_type == 'table':
            return {
                'type': 'table',
                'rows': content_data.get('rows', [])
            }
        
        # Image
        if content_type == 'image' or block_type == 'image':
            media_id = content_data.get('m')
            if media_id is not None and media_id in self._media_map:
                media = self._media_map[media_id]
                return {
                    'type': 'image',
                    'path': media.get('path'),
                    'rel_id': media.get('rel_id'),
                    'width': media.get('width'),
                    'height': media.get('height')
                }
            return {
                'type': 'image',
                'path': content_data.get('path'),
                'rel_id': content_data.get('rel_id')
            }
        
        # BlockContent
        if content_type == 'BlockContent':
            payload = self._deserialize_content(content_data.get('payload', {}), block_type)
            return {
                'type': 'BlockContent',
                'payload': payload,
                'raw': content_data.get('raw')
            }
        
        # Generic
        return content_data
    
    def to_document_model(self) -> Any:
        """
        Konwertuje UnifiedLayout do Document Model.
        
        UWAGA: To jest uproszczona konwersja - UnifiedLayout ma pozycjonowanie
        i paginację, które nie są w Document Model. Ta metoda próbuje odtworzyć
        strukturę dokumentu na podstawie bloków.
        
        Returns:
            Document Model (obiekt z atrybutami body, headers, footers)
        """
        unified_layout = self.to_unified_layout()
        
        # Utwórz model dokumentu podobny do tego z parsera
        # Używamy SimpleNamespace lub dict do symulacji modelu
        from types import SimpleNamespace
        
        body = SimpleNamespace()
        body.children = []
        body.paragraphs = []
        body.tables = []
        body.images = []
        
        headers = {}
        footers = {}
        
        # Przejdź przez wszystkie strony i zbierz elementy
        for page in unified_layout.pages:
            # Sprawdź mapowanie header/footer z JSON (jeśli dostępne)
            page_data = None
            for p_data in self.json_data.get('pages', []):
                if p_data.get('n') == page.number:
                    page_data = p_data
                    break
            
            header_indices = set(page_data.get('h', [])) if page_data else set()
            footer_indices = set(page_data.get('f', [])) if page_data else set()
            
            for i, block in enumerate(page.blocks):
                # Header bloki
                if i in header_indices or block.block_type == 'header':
                    element = self._block_to_model_element(block)
                    if element:
                        if 'default' not in headers:
                            headers['default'] = []
                        headers['default'].append(element)
                    continue
                
                # Footer bloki
                if i in footer_indices or block.block_type == 'footer':
                    element = self._block_to_model_element(block)
                    if element:
                        if 'default' not in footers:
                            footers['default'] = []
                        footers['default'].append(element)
                    continue
                
                # Pomiń decorator
                if block.block_type == 'decorator':
                    continue
                
                # Body elementy
                element = self._block_to_model_element(block)
                if element:
                    body.children.append(element)
                    if block.block_type == 'paragraph':
                        body.paragraphs.append(element)
                    elif block.block_type == 'table':
                        body.tables.append(element)
                    elif block.block_type == 'image':
                        body.images.append(element)
        
        # Utwórz model dokumentu
        model = SimpleNamespace()
        model.body = body
        model.headers = headers
        model.footers = footers
        model.elements = body.children  # Dla kompatybilności
        
        return model
    
    def _block_to_model_element(self, block: LayoutBlock) -> Any:
        """Konwertuje LayoutBlock na element Document Model (obiekt Paragraph/Table/Image)."""
        block_type = block.block_type
        
        if block_type == 'paragraph':
            # Utwórz Paragraph
            paragraph = Paragraph()
            paragraph.id = block.source_uid or f"para_{id(block)}"
            paragraph.style = block.style.copy() if block.style else {}
            
            # Wyciągnij tekst i utwórz Run
            text = self._extract_text_from_content(block.content)
            if text:
                run = Run()
                run.text = text
                run.style = block.style.get('run_style', {}) if isinstance(block.style, dict) else {}
                paragraph.runs = [run]
            
            return paragraph
        
        elif block_type == 'table':
            # Utwórz Table
            table = Table()
            table.id = block.source_uid or f"table_{id(block)}"
            table.style = block.style.copy() if block.style else {}
            
            # Wyciągnij wiersze
            rows_data = self._extract_table_rows(block.content)
            table.rows = []
            for row_data in rows_data:
                row = []
                for cell_data in row_data:
                    # Utwórz komórkę jako Paragraph z tekstem
                    cell_para = Paragraph()
                    cell_text = cell_data.get('text', '')
                    if cell_text:
                        cell_run = Run()
                        cell_run.text = cell_text
                        cell_para.runs = [cell_run]
                    row.append(cell_para)
                table.rows.append(row)
            
            return table
        
        elif block_type == 'image':
            # Utwórz Image
            image = Image()
            image.id = block.source_uid or f"image_{id(block)}"
            image.path = self._extract_image_path(block.content)
            image.rel_id = self._extract_image_rel_id(block.content)
            image.style = block.style.copy() if block.style else {}
            
            return image
        
        return None
    
    def _block_to_element(self, block: LayoutBlock) -> Optional[Dict[str, Any]]:
        """Konwertuje LayoutBlock na element dict (dla kompatybilności)."""
        element = self._block_to_model_element(block)
        if element is None:
            return None
        
        # Konwertuj obiekt na dict
        if hasattr(element, '__dict__'):
            result = {
                'type': type(element).__name__.lower(),
                'id': getattr(element, 'id', None),
                'style': getattr(element, 'style', {})
            }
            
            if isinstance(element, Paragraph):
                result['text'] = self._extract_text_from_content(block.content)
            elif isinstance(element, Table):
                result['rows'] = self._extract_table_rows(block.content)
            elif isinstance(element, Image):
                result['path'] = getattr(element, 'path', None)
                result['rel_id'] = getattr(element, 'rel_id', None)
            
            return result
        
        return None
    
    def _extract_text_from_content(self, content: Any) -> str:
        """Wyciąga tekst z content."""
        if isinstance(content, dict):
            return content.get('text', '')
        elif isinstance(content, str):
            return content
        return ''
    
    def _extract_table_rows(self, content: Any) -> List[List[Dict[str, Any]]]:
        """Wyciąga wiersze tabeli z content."""
        if isinstance(content, dict):
            # Sprawdź różne możliwe struktury
            if 'rows' in content:
                return content.get('rows', [])
            elif 'table' in content:
                table_data = content.get('table', {})
                if isinstance(table_data, dict) and 'rows' in table_data:
                    return table_data.get('rows', [])
        return []
    
    def _extract_image_path(self, content: Any) -> Optional[str]:
        """Wyciąga ścieżkę obrazu z content."""
        if isinstance(content, dict):
            return content.get('path')
        return None
    
    def _extract_image_rel_id(self, content: Any) -> Optional[str]:
        """Wyciąga rel_id obrazu z content."""
        if isinstance(content, dict):
            return content.get('rel_id')
        return None

