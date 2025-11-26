"""
Importer JSON do UnifiedLayout i Document Model.

Umożliwia odwrócenie procesu: JSON → UnifiedLayout → Document Model → DOCX

UWAGA: To jest uproszczona konwersja - UnifiedLayout ma pozycjonowanie i paginację,
które nie są w Document Model. Ta implementacja odtwarza podstawową strukturę dokumentu.

Używa podejścia podobnego do normalize_docx:
1. JSON → UnifiedLayout (deserializacja)
2. UnifiedLayout → Document Model (uproszczona konwersja)
3. Document Model → DOCX (przez DOCXExporter)
"""

import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from ..engine.unified_layout import UnifiedLayout, LayoutPage, LayoutBlock
from ..engine.geometry import Rect, Size, Margins
from ..models.paragraph import Paragraph
from ..models.run import Run
from ..models.table import Table
from ..models.image import Image

logger = logging.getLogger(__name__)


class PipelineJSONImporter:
    """
    Importer JSON zoptymalizowanego formatu pipeline.
    
    Konwertuje JSON z powrotem do UnifiedLayout, a następnie do Document Model.
    """
    
    def __init__(self, json_data: Optional[Dict[str, Any]] = None, json_path: Optional[Path] = None, source_docx_path: Optional[Path] = None):
        """
        Args:
            json_data: Dane JSON (dict) - jeśli podane, json_path jest ignorowany
            json_path: Ścieżka do pliku JSON
            source_docx_path: Ścieżka do oryginalnego DOCX (dla odczytu header/footer)
        """
        if json_data is not None:
            self.json_data = json_data
        elif json_path:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.json_data = json.load(f)
        else:
            raise ValueError("Musisz podać json_data lub json_path")
        
        self.source_docx_path = Path(source_docx_path) if source_docx_path else None
        self._package_reader = None
        self._xml_parser = None
        
        self._styles_map: Dict[int, Dict[str, Any]] = {}
        self._media_map: Dict[int, Dict[str, Any]] = {}
        self.styles_list: List[Dict[str, Any]] = []
        self.media_list: List[Dict[str, Any]] = []
        self._load_maps()
        
        # Załaduj package_reader jeśli mamy source_docx_path
        if self.source_docx_path and self.source_docx_path.exists():
            from ..parser.package_reader import PackageReader
            from ..parser.xml_parser import XMLParser
            self._package_reader = PackageReader(self.source_docx_path)
            self._xml_parser = XMLParser(self._package_reader)
    
    def _load_maps(self):
        """Ładuje mapy stylów i media z JSON."""
        # Style
        styles = self.json_data.get('styles', [])
        self.styles_list = styles
        for i, style in enumerate(styles):
            self._styles_map[i] = style
        
        # Media
        media = self.json_data.get('media', [])
        self.media_list = media
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
        media_id = block_data.get('m')  # Media ID z JSON
        
        # Jeśli mamy media_id, dodaj go do content (dla późniejszego użycia)
        if media_id is not None:
            if isinstance(content, dict):
                content['_media_id'] = media_id
                content['m'] = media_id  # Dodaj też jako 'm' dla zgodności
            else:
                # Jeśli content nie jest dict, stwórz dict
                content = {
                    'type': block_type,
                    'm': media_id,
                    '_media_id': media_id
                }
        
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
        
        # Paragraph - może być bezpośrednio lub w BlockContent
        if content_type == 'paragraph' or (block_type == 'paragraph' and content_type != 'BlockContent'):
            para_dict = {
                'type': 'paragraph',
                'text': content_data.get('text', '')
            }
            # Dodaj runs jeśli są (z eksportu JSON)
            if 'runs' in content_data:
                para_dict['runs'] = content_data.get('runs', [])
            # Dodaj list info jeśli jest
            if 'list' in content_data:
                para_dict['list'] = content_data.get('list')
            # Dodaj paragraph_properties jeśli są
            if 'paragraph_properties' in content_data:
                para_dict['paragraph_properties'] = content_data.get('paragraph_properties')
            return para_dict
        
        # Table
        if content_type == 'table' or block_type == 'table':
            # Zwróć pełną strukturę tabeli z JSON (zachowaj wszystkie dane)
            table_dict = {
                'type': 'table',
                'rows': content_data.get('rows', [])
            }
            # Dodaj dodatkowe właściwości tabeli jeśli są
            if 'columns' in content_data:
                table_dict['columns'] = content_data.get('columns')
            if 'style' in content_data:
                table_dict['style'] = content_data.get('style')
            if 'borders' in content_data:
                table_dict['borders'] = content_data.get('borders')
            if 'cell_margins' in content_data:
                table_dict['cell_margins'] = content_data.get('cell_margins')
            return table_dict
        
        # Image
        if content_type == 'image' or block_type == 'image':
            media_id = content_data.get('m')
            image_dict = {
                'type': 'image'
            }
            
            if media_id is not None and isinstance(media_id, int) and media_id < len(self.media_list):
                # Użyj danych z media_list
                media = self.media_list[media_id]
                image_dict['path'] = media.get('path')
                image_dict['rel_id'] = media.get('rel_id')
                image_dict['width'] = media.get('width')
                image_dict['height'] = media.get('height')
                # Dodaj media_id dla późniejszego użycia
                image_dict['m'] = media_id
            else:
                # Fallback - wyciągnij bezpośrednio z content_data
                image_dict['path'] = content_data.get('path')
                image_dict['rel_id'] = content_data.get('rel_id')
                image_dict['width'] = content_data.get('width')
                image_dict['height'] = content_data.get('height')
                if media_id is not None:
                    image_dict['m'] = media_id
            
            return image_dict
        
        # BlockContent
        if content_type == 'BlockContent':
            payload_data = content_data.get('payload', {})
            # Deserializuj payload rekurencyjnie
            payload = self._deserialize_content(payload_data, block_type)
            
            # Jeśli payload to dict, zachowaj strukturę
            result = {
                'type': 'BlockContent',
                'payload': payload
            }
            
            # WAŻNE: Zachowaj runs, list, paragraph_properties z content_data
            # (są one bezpośrednio w content, nie w payload)
            if 'runs' in content_data:
                result['runs'] = content_data.get('runs', [])
            if 'list' in content_data:
                result['list'] = content_data.get('list')
            if 'paragraph_properties' in content_data:
                result['paragraph_properties'] = content_data.get('paragraph_properties')
            
            # Dodaj raw jeśli istnieje
            if 'raw' in content_data:
                result['raw'] = content_data.get('raw')
            
            return result
        
        # Generic - może zawierać text, runs, list, etc.
        if content_type == 'generic':
            # Zwróć cały content_data (może zawierać text, data, runs, list, etc.)
            # To jest ważne, bo wiele bloków ma type: "generic" ale zawiera runs, list, etc.
            return content_data
        
        # Sprawdź czy content_data ma runs, list, paragraph_properties bezpośrednio (niezależnie od type)
        # To jest dla bloków gdzie runs/list są bezpośrednio w content (nie w payload)
        if 'runs' in content_data or 'list' in content_data or 'paragraph_properties' in content_data:
            # Zwróć cały content_data z zachowaniem struktury
            return content_data
        
        # Domyślnie zwróć content_data
        return content_data
    
    def to_document_model(self) -> Any:
        """
        Konwertuje JSON do Document Model.
        
        Obsługuje dwa formaty JSON:
        1. Nowy format: body, headers, footers (z LayoutStructure)
        2. Stary format: pages z blokami (z UnifiedLayout)
        
        Returns:
            Document Model (obiekt z atrybutami body, headers, footers)
        """
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
        
        # Sprawdź czy JSON ma nowy format (body, headers, footers)
        has_new_format = 'body' in self.json_data or 'headers' in self.json_data or 'footers' in self.json_data
        
        if has_new_format:
            # Nowy format - bezpośrednio z LayoutStructure
            # Eksportuj body elementy
            body_elements = self.json_data.get('body', [])
            for element_data in body_elements:
                element = self._element_from_dict(element_data)
                if element:
                    body.children.append(element)
                    if hasattr(element, 'runs'):
                        body.paragraphs.append(element)
                    elif hasattr(element, 'rows'):
                        body.tables.append(element)
                    elif hasattr(element, 'path') or hasattr(element, 'rel_id'):
                        body.images.append(element)
            
            # Eksportuj headers
            headers_data = self.json_data.get('headers', {})
            for header_type, header_elements in headers_data.items():
                if header_elements:
                    headers[header_type] = [
                        self._element_from_dict(elem) for elem in header_elements
                        if self._element_from_dict(elem) is not None
                    ]
            
            # Eksportuj footers
            footers_data = self.json_data.get('footers', {})
            for footer_type, footer_elements in footers_data.items():
                if footer_elements:
                    footers[footer_type] = [
                        self._element_from_dict(elem) for elem in footer_elements
                        if self._element_from_dict(elem) is not None
                    ]
        else:
            # Stary format - użyj UnifiedLayout
            unified_layout = self.to_unified_layout()
            
            # Najpierw spróbuj załadować headers/footers z oryginalnego DOCX (jeśli dostępny)
            if self._xml_parser and self._package_reader:
                # Załaduj headers/footers z oryginalnego dokumentu używając rId z sekcji
                sections = self.json_data.get('sections', [])
            for section in sections:
                # Headers
                section_headers = section.get('headers', [])
                for hdr_ref in section_headers:
                    hdr_type = hdr_ref.get('type', 'default')
                    hdr_id = hdr_ref.get('id')  # rId
                    if hdr_id:
                        # Znajdź plik header odpowiadający rId
                        header_path = self._find_header_footer_path(hdr_id, 'header')
                        if header_path:
                            try:
                                # Użyj parse_header bezpośrednio
                                # Tymczasowo ustaw _current_part_path dla parsera
                                old_part_path = getattr(self._xml_parser, '_current_part_path', None)
                                old_rel_file = getattr(self._xml_parser, '_current_relationship_file', None)
                                self._xml_parser._current_part_path = header_path
                                self._xml_parser._current_relationship_file = header_path.replace('.xml', '.xml.rels').replace('word/', 'word/_rels/')
                                
                                header_body = self._xml_parser.parse_header()
                                
                                # Przywróć stare wartości
                                if old_part_path:
                                    self._xml_parser._current_part_path = old_part_path
                                if old_rel_file:
                                    self._xml_parser._current_relationship_file = old_rel_file
                                
                                if header_body and hasattr(header_body, 'children'):
                                    # Konwertuj children na elementy modelu
                                    for child in header_body.children:
                                        element = self._convert_body_child_to_model(child)
                                        if element:
                                            if hdr_type not in headers:
                                                headers[hdr_type] = []
                                            headers[hdr_type].append(element)
                            except Exception as e:
                                logger.warning(f"Failed to parse header {hdr_id}: {e}")
                
                # Footers
                section_footers = section.get('footers', [])
                for ftr_ref in section_footers:
                    ftr_type = ftr_ref.get('type', 'default')
                    ftr_id = ftr_ref.get('id')  # rId
                    if ftr_id:
                        # Znajdź plik footer odpowiadający rId
                        footer_path = self._find_header_footer_path(ftr_id, 'footer')
                        if footer_path:
                            try:
                                # Użyj parse_footer bezpośrednio
                                # Tymczasowo ustaw _current_part_path dla parsera
                                old_part_path = getattr(self._xml_parser, '_current_part_path', None)
                                old_rel_file = getattr(self._xml_parser, '_current_relationship_file', None)
                                self._xml_parser._current_part_path = footer_path
                                self._xml_parser._current_relationship_file = footer_path.replace('.xml', '.xml.rels').replace('word/', 'word/_rels/')
                                
                                footer_body = self._xml_parser.parse_footer()
                                
                                # Przywróć stare wartości
                                if old_part_path:
                                    self._xml_parser._current_part_path = old_part_path
                                if old_rel_file:
                                    self._xml_parser._current_relationship_file = old_rel_file
                                
                                if footer_body and hasattr(footer_body, 'children'):
                                    # Konwertuj children na elementy modelu
                                    for child in footer_body.children:
                                        element = self._convert_body_child_to_model(child)
                                        if element:
                                            if ftr_type not in footers:
                                                footers[ftr_type] = []
                                            footers[ftr_type].append(element)
                            except Exception as e:
                                logger.warning(f"Failed to parse footer {ftr_id}: {e}")
                
            # Użyj set do deduplikacji headers/footers na podstawie ich zawartości
            # Klucz to hash zawartości, wartość to element
            seen_headers = {}  # hash -> element
            seen_footers = {}  # hash -> element
            
            # Przejdź przez wszystkie strony i zbierz elementy body (zawsze)
            # Headers/footers mogą być już załadowane z DOCX, ale body zawsze trzeba przetworzyć
            # TYLKO dla starego formatu (gdy unified_layout istnieje)
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
                # Header bloki - sprawdź zarówno header_indices jak i block_type
                # WAŻNE: Jeśli header jest już załadowany z oryginalnego DOCX, pomiń bloki header z unified_layout
                is_header = (i in header_indices) or (block.block_type == 'header')
                if is_header:
                    # Jeśli header jest już załadowany z oryginalnego DOCX, pomiń bloki z unified_layout
                    if headers or footers:
                        # Header/footer już załadowany z DOCX, pomiń
                        continue
                    
                    element = self._block_to_model_element(block)
                    if element:
                        # Utwórz hash zawartości dla deduplikacji
                        content_hash = self._get_content_hash(element)
                        if content_hash not in seen_headers:
                            seen_headers[content_hash] = element
                        if 'default' not in headers:
                            headers['default'] = []
                        headers['default'].append(element)
                    continue
                
                # Footer bloki - sprawdź zarówno footer_indices jak i block_type
                # WAŻNE: Jeśli footer jest już załadowany z oryginalnego DOCX, pomiń bloki footer z unified_layout
                is_footer = (i in footer_indices) or (block.block_type == 'footer')
                if is_footer:
                    # Jeśli footer jest już załadowany z oryginalnego DOCX, pomiń bloki z unified_layout
                    # (żeby uniknąć duplikacji i dodawania tabel z footera do body)
                    if headers or footers:
                        # Footer już załadowany z DOCX, pomiń
                        continue
                    
                    element = self._block_to_model_element(block)
                    if element:
                        # Utwórz hash zawartości dla deduplikacji
                        content_hash = self._get_content_hash(element)
                        if content_hash not in seen_footers:
                            seen_footers[content_hash] = element
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
        
        # Dodaj _sections z JSON (dla regenerate_wordml)
        # Konwertuj sections z JSON na format oczekiwany przez XMLExporter
        json_sections = self.json_data.get('sections', [])
        model._sections = []
        for json_section in json_sections:
            section = {}
            
            # Skopiuj podstawowe właściwości sekcji
            if 'page_size' in json_section:
                section['page_size'] = json_section['page_size']
            if 'margins' in json_section:
                section['margins'] = json_section['margins']
            if 'orientation' in json_section:
                section['orientation'] = json_section['orientation']
            
            # Konwertuj headers/footers z JSON (pełne elementy) na referencje z rId
            # Musimy znaleźć rId dla headers/footers używając relacji
            section_headers = []
            section_footers = []
            
            # Mapuj headers/footers z modelu na rId używając relacji
            # Najpierw sprawdź, czy mamy już załadowane headers/footers w modelu
            # i użyj ich do mapowania na rId
            header_type_to_rId = {}  # typ -> rId
            footer_type_to_rId = {}  # typ -> rId
            
            # Sprawdź relacje w document.xml.rels (jeśli dostępne)
            if self._package_reader:
                try:
                    rels_path = 'word/_rels/document.xml.rels'
                    rels_xml = self._package_reader.get_xml_content(rels_path)
                    if rels_xml:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(rels_xml)
                        ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
                        
                        # Mapuj target -> rId dla headers/footers
                        header_map = {}  # target -> (rId, type)
                        footer_map = {}  # target -> (rId, type)
                        
                        for rel in root.findall('.//r:Relationship', ns):
                            rel_id = rel.get('Id')
                            rel_type = rel.get('Type', '')
                            target = rel.get('Target', '')
                            
                            if 'header' in rel_type.lower():
                                # Określ typ header (default, first, even, odd)
                                hdr_type = 'default'
                                if 'first' in target.lower():
                                    hdr_type = 'first'
                                elif 'even' in target.lower():
                                    hdr_type = 'even'
                                elif 'odd' in target.lower():
                                    hdr_type = 'odd'
                                header_map[target] = (rel_id, hdr_type)
                                header_type_to_rId[hdr_type] = rel_id
                            
                            elif 'footer' in rel_type.lower():
                                # Określ typ footer (default, first, even, odd)
                                ftr_type = 'default'
                                if 'first' in target.lower():
                                    ftr_type = 'first'
                                elif 'even' in target.lower():
                                    ftr_type = 'even'
                                elif 'odd' in target.lower():
                                    ftr_type = 'odd'
                                footer_map[target] = (rel_id, ftr_type)
                                footer_type_to_rId[ftr_type] = rel_id
                        
                        # Konwertuj headers z JSON na referencje
                        json_headers = json_section.get('headers', [])
                        if isinstance(json_headers, list):
                            for hdr_ref in json_headers:
                                if isinstance(hdr_ref, dict):
                                    hdr_id = hdr_ref.get('id')  # rId z JSON
                                    hdr_type = hdr_ref.get('type', 'default')
                                    if hdr_id:
                                        section_headers.append({'type': hdr_type, 'id': hdr_id})
                        elif isinstance(json_headers, dict):
                            # Headers jako dict z typami (nowy format) - użyj header_type_to_rId
                            for hdr_type in json_headers.keys():
                                if hdr_type in header_type_to_rId:
                                    section_headers.append({'type': hdr_type, 'id': header_type_to_rId[hdr_type]})
                                elif hdr_type == 'first' and 'first' not in header_type_to_rId:
                                    # Fallback: jeśli 'first' nie istnieje, użyj 'default' lub pierwszego dostępnego
                                    if 'default' in header_type_to_rId:
                                        section_headers.append({'type': hdr_type, 'id': header_type_to_rId['default']})
                                    elif header_type_to_rId:
                                        first_rId = list(header_type_to_rId.values())[0]
                                        section_headers.append({'type': hdr_type, 'id': first_rId})
                                elif hdr_type == 'default' and 'default' not in header_type_to_rId and header_type_to_rId:
                                    # Fallback: użyj pierwszego dostępnego rId
                                    first_rId = list(header_type_to_rId.values())[0]
                                    section_headers.append({'type': hdr_type, 'id': first_rId})
                        
                        # Konwertuj footers z JSON na referencje
                        json_footers = json_section.get('footers', [])
                        if isinstance(json_footers, list):
                            for ftr_ref in json_footers:
                                if isinstance(ftr_ref, dict):
                                    ftr_id = ftr_ref.get('id')  # rId z JSON
                                    ftr_type = ftr_ref.get('type', 'default')
                                    if ftr_id:
                                        section_footers.append({'type': ftr_type, 'id': ftr_id})
                        elif isinstance(json_footers, dict):
                            # Footers jako dict z typami (nowy format) - użyj footer_type_to_rId
                            for ftr_type in json_footers.keys():
                                if ftr_type in footer_type_to_rId:
                                    section_footers.append({'type': ftr_type, 'id': footer_type_to_rId[ftr_type]})
                                elif ftr_type == 'default' and 'default' not in footer_type_to_rId and footer_type_to_rId:
                                    # Fallback: użyj pierwszego dostępnego rId
                                    first_rId = list(footer_type_to_rId.values())[0]
                                    section_footers.append({'type': ftr_type, 'id': first_rId})
                
                except Exception as e:
                    logger.debug(f"Failed to map header/footer references: {e}")
            
            # Jeśli nie znaleziono rId, spróbuj użyć relacji z JSON sections
            if not section_headers and not section_footers:
                json_headers = json_section.get('headers', [])
                json_footers = json_section.get('footers', [])
                
                if isinstance(json_headers, list):
                    section_headers = [h for h in json_headers if isinstance(h, dict) and 'id' in h]
                if isinstance(json_footers, list):
                    section_footers = [f for f in json_footers if isinstance(f, dict) and 'id' in f]
            
            if section_headers:
                section['headers'] = section_headers
            if section_footers:
                section['footers'] = section_footers
            
            if section:
                model._sections.append(section)
        
        return model
    
    def _find_header_footer_path(self, rel_id: str, hf_type: str) -> Optional[str]:
        """
        Znajduje ścieżkę do pliku header/footer na podstawie rel_id.
        
        Args:
            rel_id: Relationship ID (np. 'rId8')
            hf_type: 'header' lub 'footer'
            
        Returns:
            Ścieżka do pliku header/footer lub None
        """
        if not self._package_reader:
            return None
        
        # Sprawdź relationships w document.xml.rels
        rels_path = 'word/_rels/document.xml.rels'
        try:
            rels_xml = self._package_reader.get_xml_content(rels_path)
            if rels_xml:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(rels_xml)
                ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
                for rel in root.findall('.//r:Relationship', ns):
                    if rel.get('Id') == rel_id:
                        target = rel.get('Target', '')
                        # Normalizuj ścieżkę
                        if target.startswith('/'):
                            target = target[1:]
                        elif not target.startswith('word/'):
                            target = f'word/{target}'
                        return target
        except Exception as e:
            logger.warning(f"Failed to find {hf_type} path for {rel_id}: {e}")
        
        return None
    
    def _convert_body_child_to_model(self, child: Any) -> Optional[Any]:
        """
        Konwertuje child z Body na element modelu.
        
        Args:
            child: Element z Body (Paragraph, Table, Image)
            
        Returns:
            Element modelu lub None
        """
        # Sprawdź typ elementu
        if hasattr(child, 'runs'):
            # Paragraph - już jest w formacie modelu
            return child
        elif hasattr(child, 'rows'):
            # Table - już jest w formacie modelu
            return child
        elif hasattr(child, 'path') or hasattr(child, 'rel_id'):
            # Image - już jest w formacie modelu
            return child
        
        return None
    
    def _get_content_hash(self, element: Any) -> str:
        """
        Tworzy hash zawartości elementu dla deduplikacji.
        
        Args:
            element: Element (Paragraph, Table, Image, etc.)
            
        Returns:
            Hash string reprezentujący zawartość
        """
        import hashlib
        
        # Zbierz tekstową reprezentację zawartości
        content_parts = []
        
        if hasattr(element, 'runs') and element.runs:
            # Paragraph z runs
            for run in element.runs:
                if hasattr(run, 'text') and run.text:
                    content_parts.append(str(run.text))
        elif hasattr(element, 'text') and element.text:
            # Element z tekstem
            content_parts.append(str(element.text))
        elif hasattr(element, 'rows') and element.rows:
            # Table
            for row in element.rows:
                if hasattr(row, 'cells'):
                    for cell in row.cells:
                        if hasattr(cell, 'children'):
                            for child in cell.children:
                                if hasattr(child, 'runs'):
                                    for run in child.runs:
                                        if hasattr(run, 'text') and run.text:
                                            content_parts.append(str(run.text))
        elif hasattr(element, 'path') and element.path:
            # Image
            content_parts.append(str(element.path))
        
        # Jeśli nie ma zawartości, użyj typu elementu jako hash
        if not content_parts:
            element_type = type(element).__name__
            content_parts.append(element_type)
        
        # Utwórz hash z zawartości
        content_str = '|'.join(content_parts)
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()
    
    def _element_from_dict(self, element_data: Dict[str, Any]) -> Optional[Any]:
        """
        Konwertuje dict z JSON (z LayoutStructure) na element Document Model.
        
        Args:
            element_data: Dict z JSON (type, style, runs, rows, etc.)
            
        Returns:
            Element modelu (Paragraph, Table, Image) lub None
        """
        if not isinstance(element_data, dict):
            return None
        
        element_type = element_data.get('type')
        if not element_type:
            return None
        
        if element_type == 'paragraph':
            # Utwórz Paragraph
            from ..models.paragraph import Paragraph
            paragraph = Paragraph()
            paragraph.id = element_data.get('id') or f"para_{id(element_data)}"
            paragraph.style = element_data.get('style', {})
            
            # Dodaj runs
            runs_data = element_data.get('runs', [])
            if runs_data:
                from ..models.run import Run
                paragraph.runs = []
                for run_data in runs_data:
                    run = Run()
                    run.text = run_data.get('text', '')
                    run.bold = run_data.get('bold', False)
                    run.italic = run_data.get('italic', False)
                    run.underline = run_data.get('underline', False)
                    run.font_name = run_data.get('font_name')
                    run.font_size = run_data.get('font_size')
                    run.color = run_data.get('color')
                    paragraph.runs.append(run)
            else:
                # Fallback - jeśli nie ma runs, utwórz run z tekstem
                from ..models.run import Run
                text = element_data.get('text', '')
                if text:
                    run = Run()
                    run.text = text
                    paragraph.runs = [run]
            
            # Dodaj list info jeśli jest dostępne
            list_info = element_data.get('list')
            if list_info:
                level = list_info.get('level', 0)
                numbering_id = list_info.get('numbering_id')
                if numbering_id is not None:
                    paragraph.set_list(level, numbering_id)
            
            return paragraph
        
        elif element_type == 'table':
            # Utwórz Table
            from ..models.table import Table, TableRow, TableCell
            table = Table()
            table.id = element_data.get('id') or f"table_{id(element_data)}"
            table.style = element_data.get('style', {})
            
            # Dodaj rows
            rows_data = element_data.get('rows', [])
            table.rows = []
            for row_data in rows_data:
                row = TableRow()
                cells_data = row_data.get('cells', [])
                row.cells = []
                for cell_data in cells_data:
                    cell = TableCell()
                    # Serializuj bloki w komórce
                    blocks_data = cell_data.get('blocks', [])
                    cell.children = []
                    for block_data in blocks_data:
                        block_element = self._element_from_dict(block_data)
                        if block_element:
                            cell.children.append(block_element)
                    # Dodaj colspan/rowspan
                    if 'colspan' in cell_data:
                        cell.colspan = cell_data.get('colspan')
                    if 'rowspan' in cell_data:
                        cell.rowspan = cell_data.get('rowspan')
                    row.cells.append(cell)
                table.rows.append(row)
            
            return table
        
        elif element_type == 'image':
            # Utwórz Image
            from ..models.image import Image
            image = Image()
            image.path = element_data.get('path')
            image.rel_id = element_data.get('rel_id')
            image.width = element_data.get('width')
            image.height = element_data.get('height')
            return image
        
        return None
    
    def _block_to_model_element(self, block: LayoutBlock) -> Any:
        """Konwertuje LayoutBlock na element Document Model (obiekt Paragraph/Table/Image)."""
        block_type = block.block_type
        
        # Header i footer bloki są traktowane tak samo jak paragrafy/tabele/obrazy
        # w zależności od ich zawartości
        if block_type in ('header', 'footer'):
            # Sprawdź zawartość bloku - może być paragraph, table, image
            if isinstance(block.content, dict):
                content_type = block.content.get('type')
                if content_type == 'table':
                    # Traktuj jako tabelę
                    block_type = 'table'
                elif content_type == 'image':
                    # Traktuj jako obraz
                    block_type = 'image'
                else:
                    # Domyślnie traktuj jako paragraf
                    block_type = 'paragraph'
            else:
                # Domyślnie traktuj jako paragraf
                block_type = 'paragraph'
        
        if block_type == 'paragraph':
            # Utwórz Paragraph
            paragraph = Paragraph()
            paragraph.id = block.source_uid or f"para_{id(block)}"
            paragraph.style = block.style.copy() if block.style else {}
            
            # Sprawdź czy content ma runs (z eksportu JSON)
            runs_data = None
            list_info = None
            if isinstance(block.content, dict):
                # Sprawdź bezpośrednio 'runs'
                if 'runs' in block.content:
                    runs_data = block.content.get('runs', [])
                # Sprawdź w payload.runs (dla BlockContent)
                elif 'payload' in block.content:
                    payload = block.content.get('payload', {})
                    if isinstance(payload, dict):
                        if 'runs' in payload:
                            runs_data = payload.get('runs', [])
                        # Sprawdź też list w payload
                        if 'list' in payload:
                            list_info = payload.get('list')
                # Sprawdź bezpośrednio 'list'
                if 'list' in block.content:
                    list_info = block.content.get('list')
            
            # Jeśli mamy runs, użyj ich (zachowaj formatowanie)
            if runs_data:
                paragraph.runs = []
                for run_data in runs_data:
                    if isinstance(run_data, dict):
                        run = Run()
                        run.id = f"run_{id(run)}"
                        run.text = run_data.get('text', '')
                        
                        # Dodaj formatowanie run
                        run.style = {}
                        if run_data.get('bold'):
                            run.style['bold'] = True
                        if run_data.get('italic'):
                            run.style['italic'] = True
                        if run_data.get('underline'):
                            run.style['underline'] = True
                        if 'font_name' in run_data:
                            run.style['font_name'] = run_data.get('font_name')
                        if 'font_size' in run_data:
                            run.style['font_size'] = run_data.get('font_size')
                        if 'color' in run_data:
                            run.style['color'] = run_data.get('color')
                        if 'highlight' in run_data:
                            run.style['highlight'] = run_data.get('highlight')
                        if run_data.get('superscript'):
                            run.style['superscript'] = True
                        if run_data.get('subscript'):
                            run.style['subscript'] = True
                        if run_data.get('strike'):
                            run.style['strike'] = True
                        
                        paragraph.runs.append(run)
            else:
                # Fallback: Wyciągnij tekst i utwórz pojedynczy Run
                text = self._extract_text_from_content(block.content)
                if text:
                    run = Run()
                    run.text = text
                    run.style = block.style.get('run_style', {}) if isinstance(block.style, dict) else {}
                    paragraph.runs = [run]
            
            # Dodaj informacje o liście jeśli są
            if list_info and isinstance(list_info, dict):
                # Ustaw paragraf jako element listy
                level = list_info.get('level', 0)
                numbering_id = list_info.get('numbering_id')
                if numbering_id:
                    # Konwertuj numbering_id na odpowiedni format
                    try:
                        # Spróbuj jako int
                        numbering_id_int = int(numbering_id)
                        paragraph.set_list(level=level, numbering_id=numbering_id_int)
                    except (ValueError, TypeError):
                        # Użyj jako string
                        paragraph.set_list(level=level, numbering_id=str(numbering_id))
                else:
                    # Użyj domyślnego numbering_id
                    paragraph.set_list(level=level, numbering_id=1)
            
            return paragraph
        
        elif block_type == 'table':
            # Utwórz Table
            from ..models.table import TableRow, TableCell
            
            table = Table()
            table.id = block.source_uid or f"table_{id(block)}"
            table.style = block.style.copy() if block.style else {}
            
            # Wyciągnij wiersze
            rows_data = self._extract_table_rows(block.content)
            table.rows = []
            
            for row_data in rows_data:
                # Utwórz TableRow
                table_row = TableRow()
                
                for cell_data in row_data:
                    # Utwórz TableCell
                    table_cell = TableCell()
                    table_cell.id = f"cell_{id(table_cell)}"
                    
                    # Wyciągnij tekst z komórki
                    cell_text = ''
                    if isinstance(cell_data, dict):
                        # Sprawdź bezpośrednio 'text'
                        cell_text = cell_data.get('text', '')
                        # Sprawdź w 'blocks' (zagnieżdżone bloki w komórce)
                        if not cell_text and 'blocks' in cell_data:
                            blocks = cell_data.get('blocks', [])
                            text_parts = []
                            for block_item in blocks:
                                if isinstance(block_item, dict):
                                    block_text = block_item.get('text', '')
                                    if block_text:
                                        text_parts.append(block_text)
                            cell_text = ' '.join(text_parts)
                    
                    # Dodaj paragraf z tekstem do komórki
                    if cell_text:
                        cell_para = Paragraph()
                        cell_para.id = f"para_{id(cell_para)}"
                        cell_run = Run()
                        cell_run.id = f"run_{id(cell_run)}"
                        cell_run.text = cell_text
                        cell_para.runs = [cell_run]
                        table_cell.children.append(cell_para)
                    
                    # Dodaj właściwości komórki (colspan, rowspan, borders, margins)
                    if isinstance(cell_data, dict):
                        if 'colspan' in cell_data:
                            table_cell.grid_span = cell_data.get('colspan', 1)
                        if 'rowspan' in cell_data:
                            table_cell.set_vertical_merge(cell_data.get('rowspan', 1))
                        if 'borders' in cell_data:
                            table_cell.cell_borders = cell_data.get('borders')
                        if 'margins' in cell_data:
                            table_cell.cell_margins = cell_data.get('margins')
                    
                    table_row.add_cell(table_cell)
                
                table.add_row(table_row)
            
            return table
        
        elif block_type == 'image':
            # Utwórz Image
            image = Image()
            image.id = block.source_uid or f"image_{id(block)}"
            
            # Sprawdź media_id z content (zapisanego w _deserialize_block)
            media_id = None
            if isinstance(block.content, dict):
                # Sprawdź _media_id (zapisany podczas deserializacji)
                media_id = block.content.get('_media_id')
                # Fallback - sprawdź 'm' bezpośrednio
                if media_id is None:
                    media_id = block.content.get('m')
                # Sprawdź w payload
                if media_id is None and 'payload' in block.content:
                    payload = block.content['payload']
                    if isinstance(payload, dict):
                        media_id = payload.get('m')
            
            # Jeśli mamy media_id, użyj danych z media_list
            if media_id is not None and isinstance(media_id, int) and media_id < len(self.media_list):
                media_info = self.media_list[media_id]
                image.path = media_info.get('path')
                image.rel_id = media_info.get('rel_id')
                # Dodatkowe informacje z media
                if 'width' in media_info:
                    image.width = media_info.get('width')
                if 'height' in media_info:
                    image.height = media_info.get('height')
            else:
                # Fallback - wyciągnij bezpośrednio z content
                if isinstance(block.content, dict):
                    image.path = block.content.get('path') or self._extract_image_path(block.content)
                    image.rel_id = block.content.get('rel_id') or self._extract_image_rel_id(block.content)
                    if 'width' in block.content:
                        image.width = block.content.get('width')
                    if 'height' in block.content:
                        image.height = block.content.get('height')
                else:
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
    
    def _extract_text_from_content(self, content: Any, depth: int = 0) -> str:
        """Wyciąga tekst z content (rekurencyjnie).
        
        Struktura w JSON:
        - BlockContent: {type: "BlockContent", payload: {type: "generic", text: "..."}}
        - ParagraphLayout: {type: "paragraph", text: "..."}
        - TableLayout: {type: "table", rows: [...]}
        """
        if depth > 10:  # Ochrona przed nieskończoną rekursją
            return ''
        
        if content is None:
            return ''
        
        if isinstance(content, str):
            # Jeśli to nie jest tylko typ (np. "paragraph"), zwróć jako tekst
            if content and content not in ['paragraph', 'table', 'image', 'BlockContent', 'generic']:
                return content
            return ''
        
        if isinstance(content, dict):
            # PRIORYTET 1: Sprawdź bezpośrednio 'text' (dla ParagraphLayout)
            if 'text' in content:
                text = content.get('text', '')
                if text and isinstance(text, str) and len(text.strip()) > 0:
                    return text
            
            # PRIORYTET 2: Sprawdź w payload.text (dla BlockContent z generic/paragraph)
            if 'payload' in content:
                payload = content['payload']
                if isinstance(payload, dict):
                    # Sprawdź payload.text (najczęstszy przypadek - BlockContent z generic payload)
                    if 'text' in payload:
                        text = payload.get('text', '')
                        if text and isinstance(text, str) and len(text.strip()) > 0:
                            return text
                    # Sprawdź czy payload ma type: "paragraph" z text
                    if payload.get('type') == 'paragraph' and 'text' in payload:
                        text = payload.get('text', '')
                        if text and isinstance(text, str) and len(text.strip()) > 0:
                            return text
                    # Rekurencyjnie przeszukaj payload (może być zagnieżdżony)
                    payload_text = self._extract_text_from_content(payload, depth + 1)
                    if payload_text:
                        return payload_text
            
            # PRIORYTET 3: Sprawdź w innych możliwych lokalizacjach
            for key in ['value', 'data', 'content', 'text_content']:
                if key in content:
                    text = self._extract_text_from_content(content[key], depth + 1)
                    if text:
                        return text
            
            # PRIORYTET 4: Rekurencyjnie przeszukaj wszystkie wartości (ale pomiń 'type')
            for key, value in content.items():
                if key not in ['type', 'blocks']:  # Pomiń pole 'type' i 'blocks' (dla tabel)
                    text = self._extract_text_from_content(value, depth + 1)
                    if text:
                        return text
        
        if isinstance(content, list):
            # Zbierz tekst z wszystkich elementów
            texts = []
            for item in content:
                text = self._extract_text_from_content(item, depth + 1)
                if text:
                    texts.append(text)
            return ' '.join(texts) if texts else ''
        
        return ''
    
    def _extract_table_rows(self, content: Any) -> List[List[Dict[str, Any]]]:
        """Wyciąga wiersze tabeli z content.
        
        Struktura w JSON:
        - BlockContent: {type: "BlockContent", payload: {type: "table", rows: [...]}}
        - TableLayout: {type: "table", rows: [...]}
        - Dict z type: "table" i rows: [...] (z _deserialize_content)
        """
        if isinstance(content, dict):
            # PRIORYTET 1: Sprawdź bezpośrednio 'rows' (dla TableLayout lub dict z _deserialize_content)
            if 'rows' in content:
                rows = content.get('rows', [])
                if rows:
                    return rows
            
            # PRIORYTET 2: Sprawdź w payload.rows (dla BlockContent z table)
            if 'payload' in content:
                payload = content['payload']
                if isinstance(payload, dict):
                    if 'rows' in payload:
                        rows = payload.get('rows', [])
                        if rows:
                            return rows
                    # Sprawdź czy payload to dict z type: "table"
                    if payload.get('type') == 'table' and 'rows' in payload:
                        return payload.get('rows', [])
            
            # PRIORYTET 3: Sprawdź w 'table' (dla zagnieżdżonych tabel)
            if 'table' in content:
                table_data = content.get('table', {})
                if isinstance(table_data, dict) and 'rows' in table_data:
                    return table_data.get('rows', [])
            
            # PRIORYTET 4: Sprawdź czy content to dict z type: "table" (z _deserialize_content)
            if content.get('type') == 'table' and 'rows' in content:
                rows = content.get('rows', [])
                if rows:
                    return rows
        
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

