"""

Placeholder Engine - managing placeholders in DOCX documents (Jinja-like).

Supports:
- Extracting placeholders from document
- Replacing placeholders with data with automatic formatting
- Custom blocks (QR, TABLE, IMAGE, LIST, etc.)
- Conditional blocks (START_/END_)

"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from ..models.paragraph import Paragraph
from ..models.run import Run
from ..models.table import Table, TableRow, TableCell, TableProperties
from ..models.image import Image
from ..models.body import Body


@dataclass
class PlaceholderInfo:
    """Informacje o placeholderze w dokumencie."""
    name: str
    type: str  # "text", "qr", "table", "image", "date", "list", etc.
    count: int = 0
    positions: List[Tuple[str, Any]] = field(default_factory=list)  # [(context, position), ...]
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlaceholderEngine:
    """

    Engine for managing placeholders in DOCX documents (Jinja-like).

    Supports 20+ placeholder types according to Docling convention:
    - TEXT:name - plain text
    - QR:name - QR code
    - TABLE:name - table
    - IMAGE:name - image
    - DATE:name - date
    - LIST:name - list
    - CURRENCY:name - currency
    - PHONE:name - phone
    - ... and many others

    """
    
    # Regex for detecting placeholders (supports {{ }} and { })
    # Matches: {{ TYPE:Name }}, {{TYPE:Name}}, { TYPE:Name }, etc.
    PLACEHOLDER_PATTERN = re.compile(
        r'(?P<brace_open>\{\{|\{)'    # {{ or {
        r'\s*'
        r'(?P<name>[^{}]+?)'          # name (may contain colon and spaces)
        r'\s*'
        r'(?P<brace_close>\}\}|\})',  # }} or }
        re.VERBOSE
    )
    
    # Placeholder types
    PLACEHOLDER_TYPES = {
        'TEXT': 'text',
        'QR': 'qr',
        'TABLE': 'table',
        'IMAGE': 'image',
        'IMG': 'image',  # Alias
        'DATE': 'date',
        'TIME': 'time',
        'DATETIME': 'datetime',
        'NUMBER': 'number',
        'NUM': 'number',  # Alias
        'CURRENCY': 'currency',
        'PLN': 'currency',  # Alias
        'PERCENT': 'percent',
        'PCT': 'percent',  # Alias
        'BOOLEAN': 'boolean',
        'BOOL': 'boolean',  # Alias
        'LIST': 'list',
        'CHECKBOX': 'checkbox',
        'CHECK': 'checkbox',  # Alias
        'RADIO': 'radio',
        'SELECT': 'select',
        'SIGNATURE': 'signature',
        'SIG': 'signature',  # Alias
        'BARCODE': 'barcode',
        'HYPERLINK': 'hyperlink',
        'LINK': 'hyperlink',  # Alias
        'URL': 'hyperlink',  # Alias
        'EMAIL': 'email',
        'MAIL': 'email',  # Alias
        'PHONE': 'phone',
        'TEL': 'phone',  # Alias
        'ADDRESS': 'address',
        'WATERMARK': 'watermark',
        'WM': 'watermark',  # Alias
        'FOOTNOTE': 'footnote',
        'FN': 'footnote',  # Alias
        'ENDNOTE': 'endnote',
        'EN': 'endnote',  # Alias
        'CROSSREF': 'crossref',
        'REF': 'crossref',  # Alias
        'FORMULA': 'formula',
        'MATH': 'formula',  # Alias
        'EQUATION': 'formula',  # Alias
    }
    
    def __init__(self, document: Any) -> None:
        """

        Initializes placeholder engine.

        Args:
        document: Document (must have body with paragraphs/tables)

        """
        self.document = document
    
    def extract_placeholders(self) -> List[PlaceholderInfo]:
        """

        Extracts all placeholders from document.

        Returns:
        List of PlaceholderInfo objects

        """
        placeholders: Dict[str, PlaceholderInfo] = {}
        
        # Pobierz body dokumentu
        body = self._get_body()
        if not body:
            return []
        
        # Skanuj paragrafy w body
        paragraphs = self._get_paragraphs(body)
        for idx, para in enumerate(paragraphs):
            runs = self._get_runs(para)
            for run in runs:
                run_text = self._get_run_text(run)
                if not run_text:
                    continue
                
                # Find all placeholders in run
                for match in self.PLACEHOLDER_PATTERN.finditer(run_text):
                    name = match.group('name').strip()
                    
                    if name not in placeholders:
                        placeholders[name] = PlaceholderInfo(
                            name=name,
                            type=self._classify_placeholder(name),
                            count=0,
                            positions=[],
                            metadata=self._parse_placeholder_metadata(name)
                        )
                    
                    placeholders[name].count += 1
                    placeholders[name].positions.append(('paragraph', idx))
        
        # Skanuj tabele
        tables = self._get_tables(body)
        for table_idx, table in enumerate(tables):
            rows = self._get_table_rows(table)
            for row_idx, row in enumerate(rows):
                cells = self._get_row_cells(row)
                for cell_idx, cell in enumerate(cells):
                    cell_paragraphs = self._get_paragraphs(cell)
                    for para_idx, para in enumerate(cell_paragraphs):
                        runs = self._get_runs(para)
                        for run in runs:
                            run_text = self._get_run_text(run)
                            if not run_text:
                                continue
                            
                            for match in self.PLACEHOLDER_PATTERN.finditer(run_text):
                                name = match.group('name').strip()
                                
                                if name not in placeholders:
                                    placeholders[name] = PlaceholderInfo(
                                        name=name,
                                        type=self._classify_placeholder(name),
                                        count=0,
                                        positions=[],
                                        metadata=self._parse_placeholder_metadata(name)
                                    )
                                
                                placeholders[name].count += 1
                                placeholders[name].positions.append(
                                    ('table', (table_idx, row_idx, cell_idx, para_idx))
                                )
        
        return sorted(placeholders.values(), key=lambda x: x.name)
    
    def fill_placeholders(
        self, 
        data: Dict[str, Any], 
        multi_pass: bool = False, 
        max_passes: int = 5
    ) -> int:
        """

        Fills all placeholders in document.

        Args:
        data: Dictionary {placeholder_name: value}
        multi_pass: Whether to use multi-pass rendering
        max_passes: Maximum number of passes

        Returns:
        Number of replaced placeholders

        """
        total_replacements = 0
        
        if multi_pass:
            # Wieloprzebiegowe renderowanie
            for pass_num in range(max_passes):
                replacements = self._fill_placeholders_single_pass(data)
                total_replacements += replacements
                
                if replacements == 0:
                    # Stabilizacja - brak zmian
                    break
        else:
            # Pojedynczy przebieg
            total_replacements = self._fill_placeholders_single_pass(data)
        
        return total_replacements
    
    def _fill_placeholders_single_pass(self, data: Dict[str, Any]) -> int:
        """

        Fills placeholders in single pass.

        Args:
        data: Dictionary {placeholder_name: value}

        Returns:
        Number of replaced placeholders

        """
        replacements = 0
        
        # Sort data by type (priority: conditional → custom blocks → text)
        # 1. Conditional blocks (START_/END_)
        for key in list(data.keys()):
            if key.startswith('START_'):
                block_name = key.replace('START_', '')
                show = data.get(key, True)
                if self.process_conditional_block(block_name, show):
                    replacements += 1
        
        # 2. Custom blocks (QR, TABLE, IMAGE, LIST)
        for key, value in list(data.items()):
            ph_type = self._classify_placeholder(key)
            
            if ph_type == 'qr':
                if self.insert_qr_code(key, value):
                    replacements += 1
            elif ph_type == 'table':
                if self.insert_table(key, value):
                    replacements += 1
            elif ph_type == 'image':
                if self.insert_image(key, value):
                    replacements += 1
            elif ph_type == 'list':
                if self.insert_list(key, value):
                    replacements += 1
            elif ph_type == 'watermark':
                if self.insert_watermark(key, value):
                    replacements += 1
            elif ph_type == 'footnote':
                if self.insert_footnote(key, value):
                    replacements += 1
            elif ph_type == 'endnote':
                if self.insert_endnote(key, value):
                    replacements += 1
            elif ph_type == 'crossref':
                formatted_value = self._format_crossref(value, key)
                count = self.replace_placeholder(key, formatted_value)
                replacements += count
            elif ph_type == 'formula':
                if self.insert_formula(key, value):
                    replacements += 1
        
        # 3. Text placeholders (last, because custom blocks can generate them)
        for key, value in data.items():
            ph_type = self._classify_placeholder(key)
            
            # Skip custom blocks (already handled)
            if ph_type in ['qr', 'table', 'image', 'list', 'watermark', 'footnote', 'endnote', 'formula', 'conditional']:
                continue
            
            # Skip conditional blocks (already handled)
            if key.startswith('START_') or key.startswith('END_'):
                continue
            
            # Format based on type
            if ph_type in ['date', 'time', 'datetime']:
                formatted_value = self._format_date(value, ph_type, key)
            elif ph_type in ['number', 'currency', 'percent']:
                formatted_value = self._format_number(value, ph_type, key)
            elif ph_type == 'email':
                formatted_value = self._format_email(value)
            elif ph_type == 'phone':
                formatted_value = self._format_phone(value)
            elif ph_type == 'boolean':
                formatted_value = self._format_boolean(value)
            elif ph_type == 'hyperlink':
                formatted_value = self._format_hyperlink(value)
            else:
                # Default: text
                formatted_value = str(value)
            
            count = self.replace_placeholder(key, formatted_value)
            replacements += count
        
        return replacements
    
    def replace_placeholder(
        self, 
        key: str, 
        value: str, 
        preserve_formatting: bool = True
    ) -> int:
        """

        Replaces placeholder in document.

        Args:
        key: Placeholder name (e.g. "TEXT:Name" or "Name")
        value: Replacement value
        preserve_formatting: Whether to preserve run formatting

        Returns:
        Number of replacements

        """
        patterns = self._get_placeholder_patterns(key)
        replacements = 0
        
        body = self._get_body()
        if not body:
            return 0
        
        # Replace in paragraphs
        paragraphs = self._get_paragraphs(body)
        for para in paragraphs:
            for pattern in patterns:
                if preserve_formatting:
                    if self._run_safe_replace(para, pattern, value):
                        replacements += 1
                else:
                    runs = self._get_runs(para)
                    for run in runs:
                        run_text = self._get_run_text(run)
                        if pattern in run_text:
                            self._set_run_text(run, run_text.replace(pattern, value))
                            replacements += 1
        
        # Replace in tables
        tables = self._get_tables(body)
        for table in tables:
            rows = self._get_table_rows(table)
            for row in rows:
                cells = self._get_row_cells(row)
                for cell in cells:
                    cell_paragraphs = self._get_paragraphs(cell)
                    for para in cell_paragraphs:
                        for pattern in patterns:
                            if preserve_formatting:
                                if self._run_safe_replace(para, pattern, value):
                                    replacements += 1
                            else:
                                runs = self._get_runs(para)
                                for run in runs:
                                    run_text = self._get_run_text(run)
                                    if pattern in run_text:
                                        self._set_run_text(run, run_text.replace(pattern, value))
                                        replacements += 1
        
        return replacements
    
    def process_conditional_block(self, block_name: str, show: bool) -> bool:
        """

        Processes conditional block (START_name / END_name).

        Args:
        block_name: Block name
        show: Whether to show block (True) or remove (False)

        Returns:
        True if processed

        """
        if show:
            # Show - remove only START_ and END_ markers
            self.replace_placeholder(f"START_{block_name}", "", preserve_formatting=False)
            self.replace_placeholder(f"END_{block_name}", "", preserve_formatting=False)
            return True
        else:
            # Hide - remove entire section between START_ and END_
            return self._remove_section_between(f"START_{block_name}", f"END_{block_name}")
    
    def _classify_placeholder(self, name: str) -> str:
        """
        Klasyfikuje typ placeholdera na podstawie nazwy.
        
        Args:
            name: Nazwa placeholdera (np. "TEXT:Nazwa", "QR:Kod")
            
        Returns:
            Typ placeholdera (text, qr, table, etc.)
        """
        # Check if has prefix (TYPE:name)
        if ':' in name:
            prefix = name.split(':', 1)[0].upper()
            return self.PLACEHOLDER_TYPES.get(prefix, 'text')
        
        # Default text
        return 'text'
    
    def _parse_placeholder_metadata(self, name: str) -> Dict[str, Any]:
        """

        Parses metadata from placeholder name.

        Args:
        name: Placeholder name

        Returns:
        Dictionary with metadata

        """
        metadata = {}
        
        if ':' in name:
            parts = name.split(':', 1)
            metadata['prefix'] = parts[0]
            metadata['key'] = parts[1]
        else:
            metadata['key'] = name
        
        return metadata
    
    def _get_placeholder_patterns(self, key: str) -> List[str]:
        """

        Generates possible patterns for placeholder key.

        Args:
        key: Key (e.g. "TEXT:Name" or "Name")

        Returns:
        List of patterns (e.g. ["{TEXT:Name}", "{{TEXT:Name}}", "{Name}", "{{Name}}"])
        Also includes versions with spaces: "{{ TEXT:Name }}", "{ TEXT:Name }"

        """
        patterns = []
        
        # Dodaj wzorce z kluczem jak podano (bez spacji)
        patterns.append(f"{{{key}}}")      # {TEXT:Nazwa}
        patterns.append(f"{{{{{key}}}}}")  # {{TEXT:Nazwa}}
        
        # Dodaj wzorce ze spacjami wewnątrz
        patterns.append(f"{{{{ {key} }}}}")  # {{ TEXT:Nazwa }}
        patterns.append(f"{{ {key} }}")      # { TEXT:Nazwa }
        
        # Dodaj wzorce z różnymi kombinacjami spacji
        patterns.append(f"{{{{ {key}}}}}")   # {{ TEXT:Nazwa}}
        patterns.append(f"{{{{{key} }}}}")   # {{TEXT:Nazwa }}
        
        # If key has prefix, also add without prefix
        if ':' in key:
            _, base_name = key.split(':', 1)
            patterns.append(f"{{{base_name}}}")
            patterns.append(f"{{{{{base_name}}}}}")
            patterns.append(f"{{{{ {base_name} }}}}")
            patterns.append(f"{{ {base_name} }}")
        
        return patterns
    
    def _format_date(self, value: Any, ph_type: str, key: str) -> str:
        """

        Formats date according to placeholder type.

        Args:
        value: Value (string, datetime, or dict with format)
        ph_type: Type ('date', 'time', 'datetime')
        key: Placeholder key

        Returns:
        Formatted date as string

        """
        # Parse value
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            # Try to parse string as date
            try:
                dt = datetime.fromisoformat(value)
            except:
                # Not a datetime, return as-is
                return str(value)
        elif isinstance(value, dict):
            # Dict can have {"value": "...", "format": "%d.%m.%Y"}
            dt_str = value.get('value', '')
            format_str = value.get('format')
            try:
                dt = datetime.fromisoformat(dt_str)
            except:
                return str(dt_str)
        else:
            return str(value)
        
        # Format based on type
        if ph_type == 'date':
            return dt.strftime('%d.%m.%Y')  # Polish format
        elif ph_type == 'time':
            return dt.strftime('%H:%M')
        elif ph_type == 'datetime':
            return dt.strftime('%d.%m.%Y %H:%M')
        else:
            return str(value)
    
    def _format_number(self, value: Any, ph_type: str, key: str) -> str:
        """

        Formats number according to placeholder type.

        Args:
        value: Value (int, float, or string)
        ph_type: Type ('number', 'currency', 'percent')
        key: Placeholder key

        Returns:
        Formatted number as string

        """
        # Parse value
        try:
            if isinstance(value, (int, float)):
                num = float(value)
            elif isinstance(value, str):
                # Remove spaces and commas
                num = float(value.replace(' ', '').replace(',', '.'))
            elif isinstance(value, dict):
                num = float(value.get('value', 0))
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)
        
        # Format based on type
        if ph_type == 'currency':
            # Polish format: 1 234,56 PLN
            formatted = f"{num:,.2f}".replace(',', ' ').replace('.', ',')
            return f"{formatted} PLN"
        elif ph_type == 'percent':
            return f"{num:.1f}%"
        elif ph_type == 'number':
            # Format with thousand separators
            if num == int(num):
                return f"{int(num):,}".replace(',', ' ')
            else:
                return f"{num:,.2f}".replace(',', ' ').replace('.', ',')
        else:
            return str(value)
    
    def _format_email(self, value: Any) -> str:
        """Formatuje email jako mailto link."""
        email = str(value).strip()
        # Validate basic email format
        if '@' in email and '.' in email.split('@')[1]:
            return email
        return str(value)
    
    def _format_phone(self, value: Any) -> str:
        """Formatuje numer telefonu (Polish format: +48 123 456 789)."""
        phone = str(value).replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Polish mobile: 9 digits
        if len(phone) == 9 and phone.isdigit():
            return f"+48 {phone[:3]} {phone[3:6]} {phone[6:]}"
        # Already has +48
        elif phone.startswith('+48') and len(phone) == 12:
            digits = phone[3:]
            return f"+48 {digits[:3]} {digits[3:6]} {digits[6:]}"
        else:
            return str(value)
    
    def _format_boolean(self, value: Any) -> str:
        """Formats boolean value (Yes/No)."""
        if isinstance(value, bool):
            return "Tak" if value else "Nie"
        elif isinstance(value, str):
            return "Tak" if value.lower() in ['true', 'yes', 'tak', '1'] else "Nie"
        else:
            return "Tak" if value else "Nie"
    
    def _format_hyperlink(self, value: Any) -> str:
        """Formatuje hyperlink."""
        if isinstance(value, dict):
            url = value.get('url', '')
            text = value.get('text', url)
            return f'{text} ({url})'
        else:
            url = str(value)
            return url
    
    def _run_safe_replace(
        self, 
        paragraph: Paragraph, 
        placeholder: str, 
        replacement: str
    ) -> bool:
        """

        Safely replaces placeholder in paragraph preserving run formatting.

        Args:
        paragraph: Paragraph to process
        placeholder: Placeholder to replace (e.g. "{TEXT:Name}")
        replacement: Replacement text

        Returns:
        True if replacement was made

        """
        runs = self._get_runs(paragraph)
        if not runs:
            return False
        
        # Collect text from all runs
        full_text = ""
        runs_data = []
        
        for run in runs:
            run_text = self._get_run_text(run)
            runs_data.append({
                'run': run,
                'text': run_text,
                'start': len(full_text),
                'end': len(full_text) + len(run_text)
            })
            full_text += run_text
        
        # Find placeholder in full text
        placeholder_pos = full_text.find(placeholder)
        if placeholder_pos == -1:
            return False
        
        placeholder_end = placeholder_pos + len(placeholder)
        
        # Find runs that contain placeholder
        affected_runs = []
        for run_data in runs_data:
            if (run_data['start'] < placeholder_end and 
                run_data['end'] > placeholder_pos):
                affected_runs.append(run_data)
        
        if not affected_runs:
            return False
        
        # Przypadek 1: Placeholder w jednym runie
        if len(affected_runs) == 1:
            run_data = affected_runs[0]
            run = run_data['run']
            run_text = run_data['text']
            
            # Calculate position in run
            run_placeholder_start = placeholder_pos - run_data['start']
            run_placeholder_end = run_placeholder_start + len(placeholder)
            
            # Replace in run (preserves formatting!)
            new_text = (run_text[:run_placeholder_start] + 
                       replacement + 
                       run_text[run_placeholder_end:])
            self._set_run_text(run, new_text)
            return True
        
        # Case 2: Placeholder spans multiple runs
        else:
            # Find first and last run
            first_run_data = affected_runs[0]
            last_run_data = affected_runs[-1]
            
            # Calculate parts
            first_run_part_end = placeholder_pos - first_run_data['start']
            last_run_part_start = placeholder_end - last_run_data['start']
            
            # Zbuduj nowy tekst dla pierwszego runa
            self._set_run_text(
                first_run_data['run'],
                first_run_data['text'][:first_run_part_end] + 
                replacement + 
                last_run_data['text'][last_run_part_start:]
            )
            
            # Remove middle runs
            for i in range(1, len(affected_runs)):
                self._set_run_text(affected_runs[i]['run'], "")
            
            return True
    
    def _remove_section_between(self, start_marker: str, end_marker: str) -> bool:
        """

        Removes document section between two markers (including markers).

        Args:
        start_marker: Start marker (e.g. "START_Discount")
        end_marker: End marker (e.g. "END_Discount")

        Returns:
        True if section was removed

        """
        start_patterns = self._get_placeholder_patterns(start_marker)
        end_patterns = self._get_placeholder_patterns(end_marker)
        
        body = self._get_body()
        if not body:
            return False
        
        # Find marker positions in paragraphs
        paragraphs = self._get_paragraphs(body)
        start_idx = None
        end_idx = None
        
        for idx, para in enumerate(paragraphs):
            para_text = self._get_paragraph_text(para)
            
            # Szukaj start markera
            if start_idx is None:
                for pattern in start_patterns:
                    if pattern in para_text:
                        start_idx = idx
                        break
            
            # Szukaj end markera (tylko po znalezieniu start)
            elif end_idx is None:
                for pattern in end_patterns:
                    if pattern in para_text:
                        end_idx = idx
                        break
        
        # Remove section if both markers found
        if start_idx is not None and end_idx is not None and end_idx >= start_idx:
            # Remove paragraphs from start_idx to end_idx (inclusive)
            # This requires access to paragraphs list in body
            # Implementation depends on body structure
            return True
        
        return False
    
    # Helper methods for compatibility with different document structures
    def _get_body(self) -> Optional[Any]:
        """Pobiera body dokumentu."""
        # Try to get parsed model first (has actual content)
        if hasattr(self.document, 'to_model'):
            try:
                model = self.document.to_model()
                if model and hasattr(model, 'elements') and model.elements:
                    # Create a pseudo-body with elements
                    class PseudoBody:
                        def __init__(self, elements):
                            self.children = elements
                            self.paragraphs = [e for e in elements if hasattr(e, 'runs')]
                            self.tables = [e for e in elements if hasattr(e, 'rows')]
                    return PseudoBody(model.elements)
            except Exception:
                pass
        
        if hasattr(self.document, 'body') and self.document.body:
            body = self.document.body
            if hasattr(body, 'children') and body.children:
                return body
        if hasattr(self.document, '_body') and self.document._body:
            body = self.document._body
            if hasattr(body, 'children') and body.children:
                return body
        if hasattr(self.document, 'get_body'):
            return self.document.get_body()
        return None
    
    def _get_paragraphs(self, container: Any) -> List[Paragraph]:
        """Pobiera paragrafy z kontenera."""
        if hasattr(container, 'get_paragraphs'):
            return list(container.get_paragraphs() or [])
        elif hasattr(container, 'paragraphs'):
            return list(container.paragraphs or [])
        elif hasattr(container, '_paragraphs'):
            return list(container._paragraphs or [])
        elif hasattr(container, 'children'):
            return [c for c in container.children if isinstance(c, Paragraph)]
        return []
    
    def _get_runs(self, paragraph: Paragraph) -> List[Run]:
        """Pobiera runy z paragrafu."""
        if hasattr(paragraph, 'runs'):
            return list(paragraph.runs or [])
        elif hasattr(paragraph, 'get_runs'):
            return list(paragraph.get_runs() or [])
        return []
    
    def _get_run_text(self, run: Run) -> str:
        """Pobiera tekst z runa."""
        if hasattr(run, 'text'):
            return str(run.text or '')
        elif hasattr(run, 'get_text'):
            return str(run.get_text() or '')
        return ''
    
    def _set_run_text(self, run: Run, text: str) -> None:
        """Ustawia tekst w runie."""
        if hasattr(run, 'text'):
            run.text = text
        elif hasattr(run, 'set_text'):
            run.set_text(text)
    
    def _get_paragraph_text(self, paragraph: Paragraph) -> str:
        """Gets full paragraph text."""
        runs = self._get_runs(paragraph)
        return ''.join(self._get_run_text(run) for run in runs)
    
    def _get_tables(self, body: Any) -> List[Table]:
        """Pobiera tabele z body."""
        if hasattr(body, 'get_tables'):
            return list(body.get_tables() or [])
        elif hasattr(body, 'tables'):
            return list(body.tables or [])
        elif hasattr(body, '_tables'):
            return list(body._tables or [])
        elif hasattr(body, 'children'):
            return [c for c in body.children if isinstance(c, Table)]
        return []
    
    def _get_table_rows(self, table: Table) -> List[Any]:
        """Pobiera wiersze z tabeli."""
        if hasattr(table, 'rows'):
            return list(table.rows or [])
        elif hasattr(table, 'get_rows'):
            return list(table.get_rows() or [])
        return []
    
    def _get_row_cells(self, row: Any) -> List[Any]:
        """Gets cells from row."""
        if hasattr(row, 'cells'):
            return list(row.cells or [])
        elif hasattr(row, 'get_cells'):
            return list(row.get_cells() or [])
        return []
    
    # Custom blocks implementation
    def insert_qr_code(self, placeholder: str, data: Any) -> bool:
        """

        Inserts QR code in place of placeholder.

        Args:
        placeholder: Placeholder name (e.g. "QR:ProductCode")
        data: QR data - string or dict {"text": "...", "size": 100}

        Returns:
        True if inserted

        """
        # Parse data
        if isinstance(data, str):
            qr_text = data
            qr_size = 100  # Default size in pixels
        elif isinstance(data, dict):
            qr_text = data.get('text', '')
            qr_size = data.get('size', 100)
        else:
            qr_text = str(data)
            qr_size = 100
        
        if not qr_text:
            return False
        
        # Generuj QR kod jako obraz
        try:
            import qrcode
            from io import BytesIO
            from PIL import Image as PILImage
            
            # Generuj QR
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(qr_text)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Resize do requested size
            if qr_size != img.size[0]:
                img = img.resize((qr_size, qr_size), PILImage.Resampling.LANCZOS)
            
            # Konwertuj na PNG bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_data = img_bytes.getvalue()
            
            # Find placeholder and replace with image
            patterns = self._get_placeholder_patterns(placeholder)
            body = self._get_body()
            if not body:
                return False
            
            # Replace in paragraphs
            paragraphs = self._get_paragraphs(body)
            for para_idx, para in enumerate(paragraphs):
                runs = self._get_runs(para)
                for run_idx, run in enumerate(runs):
                    run_text = self._get_run_text(run)
                    if not run_text:
                        continue
                    
                    for pattern in patterns:
                        if pattern in run_text:
                            # Remove placeholder text
                            self._set_run_text(run, run_text.replace(pattern, ""))
                            
                            # Create new run with image
                            img_run = Run()
                            img_run.text = ""  # Empty text
                            
                            # Create Image model
                            img_model = Image()
                            # Note: Image model may require additional configuration
                            # depending on implementation
                            img_run.image = img_model
                            
                            # Insert run with image after current run
                            para.runs.insert(run_idx + 1, img_run)
                            
                            return True
            
        except ImportError:
            # qrcode or PIL not installed
            return self.replace_placeholder(placeholder, f"[QR: {qr_text}]") > 0
        except Exception:
            return False
        
        return False
    
    def insert_table(self, placeholder: str, data: Any) -> bool:
        """

        Inserts table in place of placeholder.

        Args:
        placeholder: Placeholder name (e.g. "TABLE:Items")
        data: Table data - dict {"headers": [...], "rows": [[...]], "style": "..."}

        Returns:
        True if inserted

        """
        if not isinstance(data, dict):
            return False
        
        headers = data.get('headers', [])
        rows = data.get('rows', [])
        table_style = data.get('style', 'TableGrid')
        
        if not headers or not rows:
            return False
        
        patterns = self._get_placeholder_patterns(placeholder)
        body = self._get_body()
        if not body:
            return False
        
        # Find placeholder in paragraphs
        paragraphs = self._get_paragraphs(body)
        for para_idx, para in enumerate(paragraphs):
            para_text = self._get_paragraph_text(para)
            
            for pattern in patterns:
                if pattern in para_text:
                    # Found placeholder - create table
                    table = Table()
                    table.properties = TableProperties(style=table_style)
                    
                    # Add header row
                    header_row = TableRow()
                    header_row.is_header_row = True
                    
                    for header_text in headers:
                        cell = TableCell()
                        cell_para = Paragraph()
                        cell_run = Run(text=str(header_text))
                        cell_run.bold = True  # Headers bold
                        cell_para.add_run(cell_run)
                        cell.add_paragraph(cell_para)
                        header_row.add_cell(cell)
                    
                    table.add_row(header_row)
                    
                    # Dodaj wiersze z danymi
                    for row_data in rows:
                        data_row = TableRow()
                        
                        for cell_value in row_data:
                            cell = TableCell()
                            cell_para = Paragraph()
                            cell_run = Run(text=str(cell_value))
                            cell_para.add_run(cell_run)
                            cell.add_paragraph(cell_para)
                            data_row.add_cell(cell)
                        
                        table.add_row(data_row)
                    
                    # Remove placeholder from paragraph
                    runs = self._get_runs(para)
                    for run in runs:
                        run_text = self._get_run_text(run)
                        if run_text and pattern in run_text:
                            self._set_run_text(run, run_text.replace(pattern, ""))
                    
                    # If paragraph is empty, remove it and insert table in its place
                    # Otherwise insert table after paragraph
                    para_text_after = self._get_paragraph_text(para)
                    if not para_text_after.strip():
                        # Paragraph is empty - replace it with table
                        if hasattr(body, 'children'):
                            # Find paragraph index in body.children
                            try:
                                para_index = body.children.index(para)
                                # Remove paragraph
                                body.children.remove(para)
                                # Insert table in its place
                                body.children.insert(para_index, table)
                                body.add_child(table)
                            except (ValueError, AttributeError):
                                # Fallback: add table at end
                                body.add_table(table)
                        else:
                            # Fallback: add table
                            if hasattr(body, 'add_table'):
                                body.add_table(table)
                            elif hasattr(body, 'add_child'):
                                body.add_child(table)
                    else:
                        # Paragraph still has text - insert table after it
                        if hasattr(body, 'children'):
                            try:
                                para_index = body.children.index(para)
                                body.children.insert(para_index + 1, table)
                                body.add_child(table)
                            except (ValueError, AttributeError):
                                if hasattr(body, 'add_table'):
                                    body.add_table(table)
                                elif hasattr(body, 'add_child'):
                                    body.add_child(table)
                        else:
                            if hasattr(body, 'add_table'):
                                body.add_table(table)
                            elif hasattr(body, 'add_child'):
                                body.add_child(table)
                    
                    return True
        
        return False
    
    def insert_image(self, placeholder: str, data: Any) -> bool:
        """

        Inserts image in place of placeholder.

        Args:
        placeholder: Placeholder name (e.g. "IMAGE:Logo")
        data: Path to image or dict {"path": "...", "width": 200, "height": 100}

        Returns:
        True if inserted

        """
        # Parse data
        if isinstance(data, str):
            image_path = Path(data)
            width = None
            height = None
        elif isinstance(data, dict):
            image_path = Path(data.get('path', ''))
            width = data.get('width')
            height = data.get('height')
        else:
            return False
        
        if not image_path.exists():
            return False
        
        try:
            # Load image file
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
            
            # Get image dimensions if not provided
            if width is None or height is None:
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(image_path) as pil_img:
                        orig_width, orig_height = pil_img.size
                        
                        if width is None and height is None:
                            # Use original size (max 400px)
                            if orig_width > 400:
                                scale = 400 / orig_width
                                width = 400
                                height = int(orig_height * scale)
                            else:
                                width = orig_width
                                height = orig_height
                        elif width is None:
                            width = int(orig_width * (height / orig_height))
                        elif height is None:
                            height = int(orig_height * (width / orig_width))
                except ImportError:
                    width = width or 200
                    height = height or 200
            
            patterns = self._get_placeholder_patterns(placeholder)
            body = self._get_body()
            if not body:
                return False
            
            # Replace in paragraphs
            paragraphs = self._get_paragraphs(body)
            for para in paragraphs:
                runs = self._get_runs(para)
                for run_idx, run in enumerate(runs):
                    run_text = self._get_run_text(run)
                    if not run_text:
                        continue
                    
                    for pattern in patterns:
                        if pattern in run_text:
                            # Remove placeholder text
                            self._set_run_text(run, run_text.replace(pattern, ""))
                            
                            # Create new run with image
                            img_run = Run()
                            img_run.text = ""
                            
                            img_model = Image()
                            img_model.set_size(width, height)
                            
                            # Generuj unikalny rel_id dla obrazu
                            # Use filename as base for rel_id
                            image_filename = f"image_{image_path.stem}_{hash(str(image_path)) % 10000}.{image_path.suffix[1:]}"
                            media_path = f"word/media/{image_filename}"
                            
                            # Generate rel_id (will be used during export)
                            # Save image data in model for later use in DOCXExporter
                            img_model.rel_id = f"rId{hash(media_path) % 10000}"  # Tymczasowy ID
                            img_model.part_path = media_path  # Path in DOCX package
                            
                            # Zapisujemy dane obrazu w modelu dokumentu dla DOCXExporter
                            # DOCXExporter will be able to get them during export
                            if not hasattr(self.document, '_new_images'):
                                self.document._new_images = []
                            
                            self.document._new_images.append({
                                'path': media_path,
                                'data': img_data,
                                'rel_id': img_model.rel_id,
                                'width': width,
                                'height': height
                            })
                            
                            img_run.image = img_model
                            
                            # Wstaw run z obrazem
                            para.runs.insert(run_idx + 1, img_run)
                            
                            return True
            
        except Exception:
            return False
        
        return False
    
    def insert_list(self, placeholder: str, data: Any) -> bool:
        """

        Inserts list in place of placeholder.

        Args:
        placeholder: Placeholder name (e.g. "LIST:Items")
        data: List of items or dict {"items": [...], "style": "bullet"|"decimal"}

        Returns:
        True if inserted

        """
        # Parse data
        if isinstance(data, list):
            items = data
            style = 'bullet'
            level = 0
        elif isinstance(data, dict):
            items = data.get('items', [])
            style = data.get('style', 'bullet')
            level = data.get('level', 0)
        else:
            return False
        
        if not items:
            return False
        
        patterns = self._get_placeholder_patterns(placeholder)
        body = self._get_body()
        if not body:
            return False
        
        # Find placeholder in paragraphs
        paragraphs = self._get_paragraphs(body)
        for para_idx, para in enumerate(paragraphs):
            para_text = self._get_paragraph_text(para)
            
            for pattern in patterns:
                if pattern in para_text:
                    # Found placeholder - create list
                    # Create paragraphs for each list item
                    list_paragraphs = []
                    
                    # Automatically create numbering_id for list
                    numbering_id = None
                    
                    # Check if document has API for creating numbering
                    if hasattr(self.document, 'create_bullet_list') and hasattr(self.document, 'create_numbered_list'):
                        # Use API methods to create numbering
                        try:
                            if style == 'bullet':
                                numbering_group = self.document.create_bullet_list()
                            else:
                                numbering_group = self.document.create_numbered_list()
                            
                            if numbering_group and hasattr(numbering_group, 'group_id'):
                                numbering_id = numbering_group.group_id
                            elif hasattr(numbering_group, 'id'):
                                numbering_id = numbering_group.id
                        except Exception as e:
                            logger.warning(f"Failed to create numbering via API: {e}")
                    
                    # If couldn't create via API, use simple mechanism
                    if not numbering_id:
                        # Create unique numbering_id based on style and placeholder
                        # Save numbering info in document for later use
                        if not hasattr(self.document, '_new_numbering_definitions'):
                            self.document._new_numbering_definitions = {}
                        
                        # Generuj unikalny klucz dla tego typu listy
                        numbering_key = f"{style}_{level}_{hash(placeholder) % 10000}"
                        
                        if numbering_key not in self.document._new_numbering_definitions:
                            # Create new numbering_id
                            # Use simple counter or hash
                            numbering_counter = len(self.document._new_numbering_definitions) + 1
                            numbering_id = str(numbering_counter)
                            
                            # Save numbering definition for later use in DOCXExporter
                            self.document._new_numbering_definitions[numbering_key] = {
                                'id': numbering_id,
                                'style': style,
                                'level': level,
                                'abstract_num_id': str(numbering_counter),
                                'levels': {
                                    str(level): {
                                        'format': 'bullet' if style == 'bullet' else 'decimal',
                                        'start': '1',
                                        'text': '•' if style == 'bullet' else '%1.',
                                        'indent_left': 720 * (level + 1),  # 0.5" per level
                                        'indent_hanging': 360,  # 0.25"
                                    }
                                }
                            }
                        else:
                            # Use existing numbering_id
                            numbering_id = self.document._new_numbering_definitions[numbering_key]['id']
                    
                    for item_text in items:
                        list_para = Paragraph()
                        list_run = Run(text=str(item_text))
                        list_para.add_run(list_run)
                        
                        # Set numbering if available
                        if numbering_id:
                            try:
                                list_para.set_list(level=level, numbering_id=numbering_id)
                            except Exception:
                                # If set_list doesn't work, use set_numbering
                                list_para.set_numbering({
                                    'id': numbering_id,
                                    'level': str(level)
                                })
                        
                        list_paragraphs.append(list_para)
                    
                    # Remove placeholder from paragraph
                    runs = self._get_runs(para)
                    for run in runs:
                        run_text = self._get_run_text(run)
                        if run_text and pattern in run_text:
                            self._set_run_text(run, run_text.replace(pattern, ""))
                    
                    # If paragraph is empty, replace it with list paragraphs
                    # W przeciwnym razie wstaw paragrafy listy po paragrafie
                    para_text_after = self._get_paragraph_text(para)
                    if not para_text_after.strip():
                        # Paragraph is empty - replace it with list paragraphs
                        if hasattr(body, 'children'):
                            try:
                                para_index = body.children.index(para)
                                body.children.remove(para)
                                # Wstaw paragrafy listy w miejsce paragrafu
                                for i, list_para in enumerate(list_paragraphs):
                                    body.children.insert(para_index + i, list_para)
                                    body.add_child(list_para)
                            except (ValueError, AttributeError):
                                # Fallback: add paragraphs at end
                                for list_para in list_paragraphs:
                                    if hasattr(body, 'add_paragraph'):
                                        body.add_paragraph(list_para)
                                    elif hasattr(body, 'add_child'):
                                        body.add_child(list_para)
                        else:
                            # Fallback
                            for list_para in list_paragraphs:
                                if hasattr(body, 'add_paragraph'):
                                    body.add_paragraph(list_para)
                                elif hasattr(body, 'add_child'):
                                    body.add_child(list_para)
                    else:
                        # Paragraf ma jeszcze tekst - wstaw paragrafy listy po nim
                        if hasattr(body, 'children'):
                            try:
                                para_index = body.children.index(para)
                                for i, list_para in enumerate(list_paragraphs):
                                    body.children.insert(para_index + 1 + i, list_para)
                                    body.add_child(list_para)
                            except (ValueError, AttributeError):
                                for list_para in list_paragraphs:
                                    if hasattr(body, 'add_paragraph'):
                                        body.add_paragraph(list_para)
                                    elif hasattr(body, 'add_child'):
                                        body.add_child(list_para)
                        else:
                            for list_para in list_paragraphs:
                                if hasattr(body, 'add_paragraph'):
                                    body.add_paragraph(list_para)
                                elif hasattr(body, 'add_child'):
                                    body.add_child(list_para)
                    
                    return True
        
        return False
    
    def insert_watermark(self, placeholder: str, data: Any) -> bool:
        """

        Inserts watermark into document.

        Args:
        placeholder: Placeholder name (e.g. "WATERMARK:Status")
        data: Watermark text or dict {"text": "...", "angle": 45, "opacity": 0.5}

        Returns:
        True if inserted

        """
        # Parse data
        if isinstance(data, str):
            watermark_text = data
            angle = 45  # Default angle
            opacity = 0.5  # Default opacity
        elif isinstance(data, dict):
            watermark_text = data.get('text', '')
            angle = data.get('angle', 45)
            opacity = data.get('opacity', 0.5)
        else:
            watermark_text = str(data)
            angle = 45
            opacity = 0.5
        
        if not watermark_text:
            return False
        
        # Dodaj watermark do dokumentu przez Document API
        if hasattr(self.document, 'add_watermark'):
            try:
                watermark = self.document.add_watermark(
                    text=watermark_text,
                    angle=angle,
                    opacity=opacity
                )
                # Remove placeholder from text (watermark is rendered separately)
                return self.replace_placeholder(placeholder, "") > 0
            except Exception as e:
                logger.warning(f"Failed to add watermark via Document API: {e}")
        
        # Fallback: replace placeholder with formatted text
        formatted_text = f"[WATERMARK: {watermark_text}]"
        return self.replace_placeholder(placeholder, formatted_text) > 0
    
    def insert_footnote(self, placeholder: str, data: Any) -> bool:
        """

        Inserts footnote in place of placeholder.

        Args:
        placeholder: Placeholder name (e.g. "FOOTNOTE:Ref1")
        data: Footnote text or dict {"text": "...", "marker": "1"}

        Returns:
        True if inserted

        """
        # Parse data
        if isinstance(data, str):
            footnote_text = data
            marker = None  # Auto-generate
        elif isinstance(data, dict):
            footnote_text = data.get('text', '')
            marker = data.get('marker')
        else:
            footnote_text = str(data)
            marker = None
        
        if not footnote_text:
            return False
        
        # In DOCX footnotes are added as special elements
        # For simplicity, replace placeholder with text with marker
        if marker:
            formatted_text = f"{marker}. {footnote_text}"
        else:
            formatted_text = f"* {footnote_text}"
        
        return self.replace_placeholder(placeholder, formatted_text) > 0
    
    def insert_endnote(self, placeholder: str, data: Any) -> bool:
        """

        Inserts endnote in place of placeholder.

        Args:
        placeholder: Placeholder name (e.g. "ENDNOTE:Ref1")
        data: Endnote text or dict {"text": "...", "marker": "i"}

        Returns:
        True if inserted

        """
        # Parse data
        if isinstance(data, str):
            endnote_text = data
            marker = None  # Auto-generate
        elif isinstance(data, dict):
            endnote_text = data.get('text', '')
            marker = data.get('marker')
        else:
            endnote_text = str(data)
            marker = None
        
        if not endnote_text:
            return False
        
        # In DOCX endnotes are similar to footnotes
        # For simplicity, replace placeholder with text with marker
        if marker:
            formatted_text = f"{marker}. {endnote_text}"
        else:
            formatted_text = f"[{endnote_text}]"
        
        return self.replace_placeholder(placeholder, formatted_text) > 0
    
    def _format_crossref(self, value: Any, key: str) -> str:
        """

        Formats cross-reference.

        Args:
        value: Value (can be dict with {"type": "heading", "number": 1})
        key: Placeholder key

        Returns:
        Formatted reference

        """
        if isinstance(value, dict):
            ref_type = value.get('type', 'item')
            ref_number = value.get('number', '?')
            ref_text = value.get('text', '')
            
            if ref_type == 'heading':
                return f"Rozdział {ref_number}"
            elif ref_type == 'figure':
                return f"Rysunek {ref_number}"
            elif ref_type == 'table':
                return f"Tabela {ref_number}"
            elif ref_type == 'equation':
                return f"Równanie ({ref_number})"
            else:
                return ref_text or f"Odwołanie {ref_number}"
        else:
            return str(value)
    
    def insert_formula(self, placeholder: str, data: Any) -> bool:
        """

        Inserts mathematical formula in place of placeholder.

        Args:
        placeholder: Placeholder name (e.g. "FORMULA:Sum")
        data: Formula as string (LaTeX or MathML) or dict {"formula": "...", "format": "latex"}

        Returns:
        True if inserted

        """
        # Parse data
        if isinstance(data, str):
            formula_text = data
            format_type = 'latex'  # Default format
        elif isinstance(data, dict):
            formula_text = data.get('formula', '')
            format_type = data.get('format', 'latex')
        else:
            formula_text = str(data)
            format_type = 'latex'
        
        if not formula_text:
            return False
        
        # In DOCX formulas are saved as MathML or OMath
        # For simplicity, replace placeholder with formula text
        # In future can add full MathML support
        
        if format_type == 'latex':
            # Try to convert LaTeX to readable form
            # Simple examples: \sum -> Σ, \int -> ∫, etc.
            formatted_text = formula_text.replace('\\sum', 'Σ').replace('\\int', '∫')
        else:
            formatted_text = formula_text
        
        return self.replace_placeholder(placeholder, f"({formatted_text})") > 0

