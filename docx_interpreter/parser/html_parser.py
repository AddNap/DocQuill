"""
HTML Parser - parsuje HTML z contenteditable i aktualizuje dokument DOCX.

Obsługuje:
- Parsowanie HTML z contenteditable
- Konwersję HTML do paragrafów i runs
- Zachowanie podstawowego formatowania (bold, italic, underline)
- Aktualizację dokumentu na podstawie edytowanego HTML
"""

from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from html.parser import HTMLParser
from html import unescape

logger = logging.getLogger(__name__)


class HTMLContentParser(HTMLParser):
    """Parser HTML który ekstraktuje tekst i formatowanie z contenteditable."""
    
    def __init__(self):
        super().__init__()
        self.paragraphs: List[Dict[str, Any]] = []
        self.tables: List[Dict[str, Any]] = []  # Tabele
        self.images: List[Dict[str, Any]] = []  # Obrazy
        self.current_paragraph: Optional[Dict[str, Any]] = None
        self.current_run: Optional[Dict[str, Any]] = None
        self.tag_stack: List[str] = []
        self.formatting_stack: List[Dict[str, Any]] = []  # Stack dla zagnieżdżonego formatowania
        self.current_list: Optional[Dict[str, Any]] = None  # Informacje o aktualnej liście
        self.list_level: int = 0  # Poziom zagnieżdżenia list
        # Stan tabeli
        self.current_table: Optional[Dict[str, Any]] = None
        self.current_row: Optional[Dict[str, Any]] = None
        self.current_cell: Optional[Dict[str, Any]] = None
        self.in_table: bool = False
    
    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Obsługuje otwierające tagi HTML."""
        tag_lower = tag.lower()
        self.tag_stack.append(tag_lower)
        
        # Parsuj atrybuty style
        style_dict = {}
        for attr_name, attr_value in attrs:
            if attr_name.lower() == 'style' and attr_value:
                style_dict = self._parse_style(attr_value)
            elif attr_name.lower() == 'color':
                style_dict['color'] = attr_value
            elif attr_name.lower() == 'style':
                # Atrybut style może być już przetworzony
                pass
        
        # Połącz style z atrybutów z formatowaniem z tagu
        formatting = {}
        
        if tag_lower == 'p':
            # Nowy paragraf
            # Jeśli jesteśmy w tabeli, nie dodawaj do głównej listy paragrafów
            if self.current_paragraph:
                if self.in_table and self.current_cell:
                    # Dodaj do komórki
                    self.current_cell['paragraphs'].append(self.current_paragraph)
                else:
                    # Dodaj do głównej listy paragrafów
                    self.paragraphs.append(self.current_paragraph)
            
            self.current_paragraph = {
                'runs': [],
                'text': '',
                'numbering': None
            }
            self.current_run = None
            self.formatting_stack = []
        
        elif tag_lower in ('ul', 'ol'):
            # Rozpocznij listę
            self.list_level += 1
            self.current_list = {
                'tag': tag_lower,
                'level': self.list_level - 1,  # Poziom listy (0-based)
                'format': 'bullet' if tag_lower == 'ul' else 'decimal'
            }
        
        elif tag_lower == 'li':
            # Element listy - utwórz nowy paragraf z numbering
            if self.current_paragraph:
                self.paragraphs.append(self.current_paragraph)
            
            self.current_paragraph = {
                'runs': [],
                'text': '',
                'numbering': None
            }
            
            # Ustaw numbering jeśli jesteśmy w liście
            if self.current_list:
                self.current_paragraph['numbering'] = {
                    'id': str(hash(self.current_list['tag'] + str(self.current_list['level']))),  # Generuj unikalny ID
                    'level': self.current_list['level'],
                    'format': self.current_list['format']
                }
            
            self.current_run = None
            self.formatting_stack = []
        
        elif tag_lower == 'table':
            # Rozpocznij tabelę
            # Zamknij poprzedni paragraf jeśli jest otwarty
            if self.current_paragraph:
                self.paragraphs.append(self.current_paragraph)
                self.current_paragraph = None
            
            self.in_table = True
            self.current_table = {
                'rows': [],
                'type': 'table'
            }
        
        elif tag_lower == 'tr':
            # Rozpocznij wiersz tabeli
            if self.in_table and self.current_table:
                # Zamknij poprzednią komórkę jeśli jest otwarta
                if self.current_cell:
                    if self.current_row:
                        self.current_row['cells'].append(self.current_cell)
                    self.current_cell = None
                
                self.current_row = {
                    'cells': [],
                    'is_header': False
                }
        
        elif tag_lower in ('td', 'th'):
            # Rozpocznij komórkę tabeli
            if self.in_table and self.current_table and self.current_row:
                # Zamknij poprzednią komórkę jeśli jest otwarta
                if self.current_cell:
                    self.current_row['cells'].append(self.current_cell)
                
                # Utwórz nową komórkę
                self.current_cell = {
                    'paragraphs': [],
                    'is_header': tag_lower == 'th'
                }
                
                # Ustaw is_header dla wiersza jeśli to <th>
                if tag_lower == 'th':
                    self.current_row['is_header'] = True
                
                # Utwórz nowy paragraf dla komórki
                self.current_paragraph = {
                    'runs': [],
                    'text': '',
                    'numbering': None
                }
                self.current_run = None
                self.formatting_stack = []
        
        elif tag_lower in ('strong', 'b'):
            # Bold
            formatting['bold'] = True
        
        elif tag_lower in ('em', 'i'):
            # Italic
            formatting['italic'] = True
        
        elif tag_lower == 'u':
            # Underline
            formatting['underline'] = True
        
        elif tag_lower in ('span', 'font'):
            # Span/Font może mieć style, color, font-size, font-family
            if 'color' in style_dict:
                formatting['color'] = style_dict['color']
            if 'font-size' in style_dict:
                formatting['font_size'] = style_dict['font-size']
            if 'font-family' in style_dict:
                formatting['font_name'] = style_dict['font-family']
        
        elif tag_lower == 'img':
            # Obraz - zamknij poprzedni paragraf jeśli jest otwarty
            if self.current_paragraph:
                if self.in_table and self.current_cell:
                    self.current_cell['paragraphs'].append(self.current_paragraph)
                else:
                    self.paragraphs.append(self.current_paragraph)
                self.current_paragraph = None
            
            # Parsuj atrybuty obrazu
            image_data = {
                'src': '',
                'alt': '',
                'width': None,
                'height': None,
                'rel_id': ''
            }
            
            for attr_name, attr_value in attrs:
                attr_lower = attr_name.lower()
                if attr_lower == 'src':
                    image_data['src'] = attr_value or ''
                elif attr_lower == 'alt':
                    image_data['alt'] = attr_value or ''
                elif attr_lower == 'width':
                    try:
                        image_data['width'] = int(attr_value)
                    except (ValueError, TypeError):
                        pass
                elif attr_lower == 'height':
                    try:
                        image_data['height'] = int(attr_value)
                    except (ValueError, TypeError):
                        pass
                elif attr_lower == 'data-image-id':
                    image_data['rel_id'] = attr_value or ''
            
            # Jeśli nie ma rel_id, wygeneruj z src
            if not image_data['rel_id'] and image_data['src']:
                import hashlib
                image_data['rel_id'] = hashlib.md5(image_data['src'].encode()).hexdigest()[:8]
            
            self.images.append(image_data)
        
        # Dodaj formatowanie do stacku
        if formatting or style_dict:
            # Połącz formatowanie z obecnego stacku z nowym formatowaniem
            combined_formatting = {}
            
            # Zacznij od formatowania z poprzedniego poziomu (jeśli istnieje)
            if self.formatting_stack:
                combined_formatting.update(self.formatting_stack[-1])
            
            # Dodaj nowe formatowanie (nadpisuje poprzednie)
            combined_formatting.update(formatting)
            combined_formatting.update(style_dict)
            
            # Dodaj do stacku
            self.formatting_stack.append(combined_formatting)
            
            # Rozpocznij nowy run jeśli jest formatowanie
            if self.current_paragraph:
                if self.current_run and self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                
                # Utwórz nowy run z połączonym formatowaniem
                new_run = {'text': ''}
                new_run.update(combined_formatting)
                self.current_run = new_run
    
    def handle_endtag(self, tag: str) -> None:
        """Obsługuje zamykające tagi HTML."""
        tag_lower = tag.lower()
        
        if tag_lower in self.tag_stack:
            self.tag_stack.remove(tag_lower)
        
        if tag_lower == 'p':
            # Zakończ paragraf
            if self.current_paragraph:
                if self.current_run and self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                self.current_paragraph['text'] = ''.join(
                    run.get('text', '') for run in self.current_paragraph['runs']
                )
                
                # Jeśli jesteśmy w tabeli, dodaj do komórki
                if self.in_table and self.current_cell:
                    self.current_cell['paragraphs'].append(self.current_paragraph)
                else:
                    # Dodaj do głównej listy paragrafów
                    self.paragraphs.append(self.current_paragraph)
                
                self.current_paragraph = None
                self.current_run = None
                self.formatting_stack = []
        
        elif tag_lower == 'li':
            # Zakończ element listy
            if self.current_paragraph:
                if self.current_run and self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                self.current_paragraph['text'] = ''.join(
                    run.get('text', '') for run in self.current_paragraph['runs']
                )
                self.paragraphs.append(self.current_paragraph)
                self.current_paragraph = None
                self.current_run = None
                self.formatting_stack = []
        
        elif tag_lower in ('ul', 'ol'):
            # Zakończ listę
            self.list_level = max(0, self.list_level - 1)
            if self.list_level == 0:
                self.current_list = None
        
        elif tag_lower == 'td' or tag_lower == 'th':
            # Zakończ komórkę tabeli
            if self.current_paragraph:
                if self.current_run and self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                self.current_paragraph['text'] = ''.join(
                    run.get('text', '') for run in self.current_paragraph['runs']
                )
                
                # Dodaj paragraf do komórki
                if self.current_cell:
                    self.current_cell['paragraphs'].append(self.current_paragraph)
                
                self.current_paragraph = None
                self.current_run = None
                self.formatting_stack = []
            
            # Dodaj komórkę do wiersza
            if self.current_cell and self.current_row:
                self.current_row['cells'].append(self.current_cell)
                self.current_cell = None
        
        elif tag_lower == 'tr':
            # Zakończ wiersz tabeli
            if self.current_cell:
                self.current_row['cells'].append(self.current_cell)
                self.current_cell = None
            
            if self.current_row and self.current_table:
                self.current_table['rows'].append(self.current_row)
                self.current_row = None
        
        elif tag_lower == 'table':
            # Zakończ tabelę
            if self.current_row:
                if self.current_cell:
                    self.current_row['cells'].append(self.current_cell)
                    self.current_cell = None
                self.current_table['rows'].append(self.current_row)
                self.current_row = None
            
            if self.current_table:
                self.tables.append(self.current_table)
                self.current_table = None
            
            self.in_table = False
        
        elif tag_lower in ('strong', 'b', 'em', 'i', 'u', 'span', 'font'):
            # Zakończ run z formatowaniem
            if self.formatting_stack:
                self.formatting_stack.pop()
            
            if self.current_run and self.current_paragraph:
                if self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                
                # Przywróć poprzednie formatowanie z stacku lub utwórz nowy run
                if self.formatting_stack:
                    # Przywróć formatowanie z poprzedniego poziomu
                    prev_formatting = self.formatting_stack[-1].copy()
                    prev_formatting['text'] = ''
                    self.current_run = prev_formatting
                else:
                    # Brak formatowania - zwykły run
                    self.current_run = {'text': ''}
    
    def handle_data(self, data: str) -> None:
        """Obsługuje tekst."""
        if not self.current_paragraph:
            # Tekst poza paragrafem - utwórz nowy paragraf
            self.current_paragraph = {
                'runs': [],
                'text': ''
            }
        
        if not self.current_run:
            # Utwórz domyślny run z formatowaniem ze stacku
            if self.formatting_stack:
                self.current_run = self.formatting_stack[-1].copy()
                self.current_run['text'] = ''
            else:
                self.current_run = {'text': ''}
        
        # Dodaj tekst do bieżącego run
        self.current_run['text'] += unescape(data)
    
    def _parse_style(self, style_str: str) -> Dict[str, Any]:
        """Parsuje atrybut style z HTML."""
        style_dict = {}
        
        if not style_str:
            return style_dict
        
        # Parsuj style="color: red; font-size: 12px; font-family: Arial;"
        for declaration in style_str.split(';'):
            declaration = declaration.strip()
            if not declaration:
                continue
            
            if ':' in declaration:
                prop, value = declaration.split(':', 1)
                prop = prop.strip().lower()
                value = value.strip()
                
                if prop == 'color':
                    # Konwertuj kolor do formatu hex (jeśli potrzeba)
                    color = self._normalize_color(value)
                    if color:
                        style_dict['color'] = color
                
                elif prop == 'font-size':
                    # Parsuj rozmiar czcionki (np. "12px", "1.2em", "12pt")
                    font_size = self._parse_font_size(value)
                    if font_size:
                        style_dict['font_size'] = font_size
                
                elif prop == 'font-family':
                    # Parsuj nazwę czcionki (usuń cudzysłowy jeśli są)
                    font_name = value.strip('"\'')
                    if font_name:
                        # Weź pierwszą czcionkę z listy
                        font_name = font_name.split(',')[0].strip()
                        style_dict['font_name'] = font_name
        
        return style_dict
    
    def _normalize_color(self, color: str) -> Optional[str]:
        """Normalizuje kolor do formatu hex (RRGGBB)."""
        color = color.strip().lower()
        
        # Jeśli już jest hex
        if color.startswith('#'):
            color = color[1:]
            if len(color) == 3:
                # Rozszerz #RGB do #RRGGBB
                color = ''.join(c * 2 for c in color)
            if len(color) == 6:
                return color.upper()
        
        # Nazwy kolorów HTML
        color_names = {
            'black': '000000',
            'white': 'FFFFFF',
            'red': 'FF0000',
            'green': '008000',
            'blue': '0000FF',
            'yellow': 'FFFF00',
            'cyan': '00FFFF',
            'magenta': 'FF00FF',
            'gray': '808080',
            'grey': '808080',
            'orange': 'FFA500',
            'purple': '800080',
            'brown': 'A52A2A',
            'pink': 'FFC0CB',
        }
        
        if color in color_names:
            return color_names[color]
        
        # RGB/RGBA format
        if color.startswith('rgb'):
            import re
            match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', color)
            if match:
                r, g, b = match.groups()
                return f"{int(r):02X}{int(g):02X}{int(b):02X}"
        
        return None
    
    def _parse_font_size(self, size_str: str) -> Optional[str]:
        """Parsuje rozmiar czcionki do formatu Word (half-points)."""
        size_str = size_str.strip().lower()
        
        # Usuń jednostki i parsuj liczbę
        import re
        match = re.match(r'([\d.]+)', size_str)
        if not match:
            return None
        
        size_value = float(match.group(1))
        
        # Konwertuj różne jednostki do punktów
        if 'px' in size_str:
            # 1px ≈ 0.75pt (przybliżenie)
            size_value = size_value * 0.75
        elif 'em' in size_str:
            # 1em ≈ 12pt (domyślny rozmiar)
            size_value = size_value * 12
        elif 'pt' in size_str:
            # Już w punktach
            pass
        else:
            # Załóżmy że to punkty
            pass
        
        # Konwertuj do half-points (Word używa half-points)
        half_points = int(size_value * 2)
        
        # Zwróć jako string (Word format)
        return str(half_points)
    
    def close(self) -> None:
        """Zakończ parsowanie."""
        # Zamknij otwarty paragraf jeśli jest
        if self.current_paragraph:
            if self.current_run and self.current_run.get('text'):
                self.current_paragraph['runs'].append(self.current_run)
            self.current_paragraph['text'] = ''.join(
                run.get('text', '') for run in self.current_paragraph['runs']
            )
            
            # Jeśli jesteśmy w tabeli, dodaj paragraf do komórki
            if self.in_table and self.current_cell:
                self.current_cell['paragraphs'].append(self.current_paragraph)
            else:
                self.paragraphs.append(self.current_paragraph)
            
            self.current_paragraph = None
        
        # Zamknij otwartą komórkę jeśli jest
        if self.current_cell:
            if self.current_row:
                self.current_row['cells'].append(self.current_cell)
            self.current_cell = None
        
        # Zamknij otwarty wiersz jeśli jest
        if self.current_row:
            if self.current_table:
                self.current_table['rows'].append(self.current_row)
            self.current_row = None
        
        # Zamknij otwartą tabelę jeśli jest
        if self.current_table:
            self.tables.append(self.current_table)
            self.current_table = None
        
        self.in_table = False
        super().close()


class HTMLParser:
    """
    Parser HTML który konwertuje edytowany HTML z powrotem do modelu DOCX.
    """
    
    def __init__(self, html_content: str):
        """
        Inicjalizuje parser HTML.
        
        Args:
            html_content: Zawartość HTML do parsowania
        """
        self.html_content = html_content
        self.parser = HTMLContentParser()
    
    def parse(self) -> Dict[str, Any]:
        """
        Parsuje HTML i zwraca paragrafy i tabele.
        
        Returns:
            Słownik z kluczami 'paragraphs' i 'tables'
        """
        try:
            # Wyczyść parser
            self.parser.paragraphs = []
            self.parser.tables = []
            self.parser.current_paragraph = None
            self.parser.current_run = None
            self.parser.tag_stack = []
            self.parser.formatting_stack = []
            self.parser.current_list = None
            self.parser.list_level = 0
            self.parser.current_table = None
            self.parser.current_row = None
            self.parser.current_cell = None
            self.parser.in_table = False
            self.parser.images = []
            
            # Parsuj HTML
            self.parser.feed(self.html_content)
            self.parser.close()
            
            return {
                'paragraphs': self.parser.paragraphs,
                'tables': self.parser.tables,
                'images': self.parser.images
            }
            
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            return {'paragraphs': [], 'tables': [], 'images': []}
    
    @staticmethod
    def parse_file(html_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Parsuje plik HTML.
        
        Args:
            html_path: Ścieżka do pliku HTML
            
        Returns:
            Słownik z kluczami 'paragraphs', 'tables' i 'images'
        """
        html_path = Path(html_path)
        if not html_path.exists():
            logger.error(f"HTML file not found: {html_path}")
            return {'paragraphs': [], 'tables': [], 'images': []}
        
        html_content = html_path.read_text(encoding='utf-8')
        parser = HTMLParser(html_content)
        return parser.parse()

