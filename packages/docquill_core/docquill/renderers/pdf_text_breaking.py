"""
Text breaking and line wrapping for PDF renderer.

Handles word wrapping, justification, and proper line breaking with formatting preservation.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TextLine:
    """Represents a single line of text with runs."""
    runs: List[Tuple[Any, str, Dict[str, Any]]] = field(default_factory=list)  # (run, text, font_info)
    width: float = 0.0
    height: float = 0.0
    words: List[str] = field(default_factory=list)  # Words for justification


class PDFTextBreaker:
    """
    Handles text breaking and line wrapping for PDF rendering.
    
    Similar to the old direct_pdf_renderer's _break_paragraph_into_lines functionality.
    """
    
    def __init__(self, pdf_canvas, get_font_info_func, line_spacing_multiplier: float = 1.2, 
                 default_font_size: float = 12.0, debug: bool = False):
        """
        Initialize text breaker.
        
        Args:
            pdf_canvas: ReportLab canvas for width calculations
            get_font_info_func: Function to get font info for a run
            line_spacing_multiplier: Line spacing multiplier
            default_font_size: Default font size in points
            debug: Enable debug logging
        """
        self.pdf = pdf_canvas
        self._get_font_info = get_font_info_func
        self.line_spacing_multiplier = line_spacing_multiplier
        self.default_font_size = default_font_size
        self.debug = debug
        self._justify_para_count = 0
    
    def break_paragraph_into_lines(self, paragraph: Any, available_width: float, 
                                   first_line_indent: float = 0.0, alignment: str = 'left') -> List[TextLine]:
        """
        Break paragraph into lines with proper word wrapping.
        
        HYBRID APPROACH:
        - For justify/both: use ReportLab Paragraph for line breaking
        - Map words back to runs using char_to_run_map
        - Preserves formatting per-run + Word-quality line breaking
        
        Args:
            paragraph: Paragraph object
            available_width: Available width for text
            first_line_indent: First line indent
            alignment: Paragraph alignment (left, right, center, justify, both)
            
        Returns:
            List of TextLine objects
        """
        lines = []
        
        # Step 1: Get clean text from paragraph.text (DOCX already has spaces!)
        full_text = ""
        if hasattr(paragraph, 'text'):
            full_text = paragraph.text or ''
            # Clean placeholders from paragraph.text
            import re
            full_text = re.sub(r'\{\{([^}]+)\}\}', r'\1', full_text)
            full_text = re.sub(r'\{TEXT:([^}]+)\}', r'\1', full_text)
            full_text = re.sub(r'\{[A-Z]+:[^}]+\}', '', full_text)
        elif hasattr(paragraph, 'get_text'):
            full_text = paragraph.get_text() or ''
            # Clean placeholders
            import re
            full_text = re.sub(r'\{\{([^}]+)\}\}', r'\1', full_text)
            full_text = re.sub(r'\{TEXT:([^}]+)\}', r'\1', full_text)
            full_text = re.sub(r'\{[A-Z]+:[^}]+\}', '', full_text)
        elif hasattr(paragraph, 'runs'):
            # Fallback: concatenate run texts and clean placeholders
            text_parts = []
            for run in paragraph.runs:
                if hasattr(run, 'text') and run.text:
                    run_text = run.text
                    # Clean DOCX field codes
                    import re
                    run_text = re.sub(r'\{\{([^}]+)\}\}', r'\1', run_text)
                    run_text = re.sub(r'\{TEXT:([^}]+)\}', r'\1', run_text)
                    run_text = re.sub(r'\{[A-Z]+:[^}]+\}', '', run_text)
                    text_parts.append(run_text)
            full_text = ''.join(text_parts)
        
        if not full_text.strip():
            # Empty paragraph - return single empty line
            line = TextLine()
            line.height = self.default_font_size * self.line_spacing_multiplier
            return [line]
        
        # Step 2: Build mapping: {char_position: run} by enumerating runs
        char_to_run_map = {}
        current_char_position = 0
        
        if hasattr(paragraph, 'runs') and paragraph.runs:
            for run in paragraph.runs:
                # Skip special items (handled later)
                if hasattr(run, 'line_break') and run.line_break:
                    continue
                if hasattr(run, 'image') and run.image:
                    continue
                
                # Map each character of this run (including spaces!)
                if hasattr(run, 'text') and run.text is not None:
                    # Clean placeholders from run text for breaking
                    run_text = run.text
                    import re
                    run_text = re.sub(r'\{\{([^}]+)\}\}', r'\1', run_text)
                    run_text = re.sub(r'\{TEXT:([^}]+)\}', r'\1', run_text)
                    run_text = re.sub(r'\{[A-Z]+:[^}]+\}', '', run_text)
                    run_text_length = len(run_text)
                    for offset in range(run_text_length):
                        char_to_run_map[current_char_position + offset] = run
                    current_char_position += run_text_length
        
        # Fallback: if mapping shorter than text, use last run
        if char_to_run_map:
            last_run = char_to_run_map[max(char_to_run_map.keys())]
            for pos in range(current_char_position, len(full_text)):
                char_to_run_map[pos] = last_run
        
        # HYBRID APPROACH: For justify/both use ReportLab Paragraph for line breaking
        if alignment in ('justify', 'both') and full_text.strip():
            try:
                from reportlab.platypus import Paragraph as RLParagraph
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.lib.enums import TA_JUSTIFY
                
                # Get font from first run
                first_run = paragraph.runs[0] if (hasattr(paragraph, 'runs') and paragraph.runs) else None
                if first_run:
                    font_info = self._get_font_info(first_run)
                    font_name = font_info.get('name', 'Helvetica')
                    font_size = font_info.get('size', self.default_font_size)
                else:
                    font_name = 'Helvetica'
                    font_size = self.default_font_size
                
                # Create style with justification
                rl_style = ParagraphStyle(
                    name='JustifyStyle',
                    alignment=TA_JUSTIFY,
                    fontName=font_name,
                    fontSize=font_size,
                    leading=font_size * self.line_spacing_multiplier,
                )
                
                # Use ReportLab to calculate line breaking
                rl_para = RLParagraph(full_text, rl_style)
                _, _ = rl_para.wrap(available_width, 10000)  # Large height
                
                # Extract line breaking info from blPara.lines
                if hasattr(rl_para, 'blPara') and hasattr(rl_para.blPara, 'lines'):
                    rl_lines = rl_para.blPara.lines
                    
                    if self.debug:
                        logger.debug(f"ReportLab returned {len(rl_lines)} lines for paragraph")
                    
                    # Each line is tuple: (extra_space, [word_list])
                    for line_idx, (extra_space, words) in enumerate(rl_lines):
                        if not words:
                            continue
                        
                        # Find these words in full_text and map to runs
                        line = TextLine()
                        line_text = ' '.join(words)  # Reconstruct line text
                        
                        # Find position of this text in full_text
                        search_start = 0
                        for prev_line in lines:
                            # Skip previous lines
                            prev_text = ''.join(text for _, text, _ in prev_line.runs if text)
                            search_start += len(prev_text)
                        
                        # Map words to runs using char_to_run_map
                        char_idx = search_start
                        words_found = 0
                        for word_idx, word in enumerate(words):
                            # Find word in full_text starting from char_idx
                            word_pos = full_text.find(word, char_idx)
                            if word_pos == -1:
                                if self.debug:
                                    logger.warning(f"Word '{word}' not found at position {char_idx}")
                                break
                            words_found += 1
                            
                            # Map word characters to runs
                            for i in range(len(word)):
                                pos = word_pos + i
                                run = char_to_run_map.get(pos)
                                if run and i == 0:  # First character of word
                                    font_info = self._get_font_info(run)
                                    # Add word as run
                                    word_width = self.pdf.stringWidth(word, font_info['name'], font_info['size'])
                                    line.runs.append((run, word, font_info))
                                    line.width += word_width
                                    line.words.append(word)
                            
                            # Add space after word (if not last)
                            if word_idx < len(words) - 1:
                                # Space after word
                                space_pos = word_pos + len(word)
                                space_run = char_to_run_map.get(space_pos)
                                if space_run:
                                    font_info = self._get_font_info(space_run)
                                    space_width = self.pdf.stringWidth(' ', font_info['name'], font_info['size'])
                                    line.runs.append((space_run, ' ', font_info))
                                    line.width += space_width
                                
                            char_idx = word_pos + len(word) + 1  # +1 for space
                        
                        # Calculate line height
                        max_line_height = 0
                        for run, text, font_info in line.runs:
                            if text:
                                item_height = font_info['size'] * self.line_spacing_multiplier
                                max_line_height = max(max_line_height, item_height)
                        line.height = max_line_height if max_line_height > 0 else self.default_font_size
                        
                        if len(line.runs) > 0:
                            lines.append(line)
                    
                    # Return lines from ReportLab
                    return lines
            except Exception as e:
                # Fallback to normal breaking if ReportLab fails
                if self.debug:
                    logger.warning(f"ReportLab breaking failed, using fallback: {e}")
                pass
        
        # Step 3: Process full_text into words, using mapping for formatting
        run_data = []
        current_word = ""
        word_start_idx = 0
        
        for char_idx, char in enumerate(full_text):
            # Get run for this character from mapping dictionary
            current_run = char_to_run_map.get(char_idx)
            
            if char == ' ':
                # End current word (if exists)
                if current_word:
                    word_run = char_to_run_map.get(word_start_idx, current_run)
                    font_info = self._get_font_info(word_run) if word_run else {
                        'name': 'Helvetica', 'size': self.default_font_size, 'color': (0, 0, 0),
                        'bold': False, 'italic': False, 'underline': False
                    }
                    word_width = self.pdf.stringWidth(current_word, font_info['name'], font_info['size'])
                    run_data.append({
                        'type': 'text',
                        'run': word_run,
                        'text': current_word,
                        'width': word_width,
                        'font_info': font_info
                    })
                    current_word = ""
                
                # Add space
                if current_run:
                    font_info = self._get_font_info(current_run)
                    space_width = self.pdf.stringWidth(' ', font_info['name'], font_info['size'])
                    run_data.append({
                        'type': 'space',
                        'run': current_run,
                        'text': ' ',
                        'width': space_width,
                        'font_info': font_info
                    })
            elif char == '\n':
                # Line break - end word and add break
                if current_word:
                    word_run = char_to_run_map.get(word_start_idx, current_run)
                    font_info = self._get_font_info(word_run) if word_run else {
                        'name': 'Helvetica', 'size': self.default_font_size, 'color': (0, 0, 0),
                        'bold': False, 'italic': False, 'underline': False
                    }
                    word_width = self.pdf.stringWidth(current_word, font_info['name'], font_info['size'])
                    run_data.append({
                        'type': 'text',
                        'run': word_run,
                        'text': current_word,
                        'width': word_width,
                        'font_info': font_info
                    })
                    current_word = ""
                
                run_data.append({
                    'type': 'line_break',
                    'run': current_run,
                    'text': '\n',
                    'width': 0,
                    'font_info': font_info if current_run else None
                })
                word_start_idx = char_idx + 1
            else:
                # Regular character - add to current word
                if not current_word:
                    word_start_idx = char_idx
                current_word += char
        
        # Add remaining word
        if current_word:
            word_run = char_to_run_map.get(word_start_idx) if word_start_idx < len(full_text) else None
            font_info = self._get_font_info(word_run) if word_run else {
                'name': 'Helvetica', 'size': self.default_font_size, 'color': (0, 0, 0),
                'bold': False, 'italic': False, 'underline': False
            }
            word_width = self.pdf.stringWidth(current_word, font_info['name'], font_info['size'])
            run_data.append({
                'type': 'text',
                'run': word_run,
                'text': current_word,
                'width': word_width,
                'font_info': font_info
            })
        
        # Step 4: Break into lines based on available width
        current_line = TextLine()
        current_line_width = 0
        
        for item in run_data:
            if item['type'] == 'line_break':
                # Force line break
                if current_line.runs:
                    # Calculate line height
                    max_height = 0
                    for run, text, font_info in current_line.runs:
                        if text:
                            item_height = font_info['size'] * self.line_spacing_multiplier
                            max_height = max(max_height, item_height)
                    current_line.height = max_height if max_height > 0 else self.default_font_size
                    lines.append(current_line)
                
                current_line = TextLine()
                current_line_width = 0
            elif item['type'] == 'text':
                # Try to add word to current line
                word_width = item['width']
                
                # Check if word fits (consider first line indent)
                line_available_width = available_width
                if len(lines) == 0:  # First line
                    line_available_width -= first_line_indent
                
                if current_line_width + word_width <= line_available_width:
                    # Word fits - add to current line
                    current_line.runs.append((item['run'], item['text'], item['font_info']))
                    current_line.width += word_width
                    current_line.words.append(item['text'])
                    current_line_width += word_width
                else:
                    # Word doesn't fit - start new line
                    if current_line.runs:
                        # Calculate line height
                        max_height = 0
                        for run, text, font_info in current_line.runs:
                            if text:
                                item_height = font_info['size'] * self.line_spacing_multiplier
                                max_height = max(max_height, item_height)
                        current_line.height = max_height if max_height > 0 else self.default_font_size
                        lines.append(current_line)
                    
                    # Start new line with this word
                    current_line = TextLine()
                    current_line.runs.append((item['run'], item['text'], item['font_info']))
                    current_line.width = word_width
                    current_line.words.append(item['text'])
                    current_line_width = word_width
            elif item['type'] == 'space':
                # Add space if there's room
                space_width = item['width']
                line_available_width = available_width
                if len(lines) == 0:  # First line
                    line_available_width -= first_line_indent
                
                if current_line_width + space_width <= line_available_width:
                    current_line.runs.append((item['run'], item['text'], item['font_info']))
                    current_line.width += space_width
                    current_line_width += space_width
        
        # Add last line
        if current_line.runs:
            max_height = 0
            for run, text, font_info in current_line.runs:
                if text:
                    item_height = font_info['size'] * self.line_spacing_multiplier
                    max_height = max(max_height, item_height)
            current_line.height = max_height if max_height > 0 else self.default_font_size
            lines.append(current_line)
        
        # If no lines created, return empty line
        if not lines:
            line = TextLine()
            line.height = self.default_font_size * self.line_spacing_multiplier
            lines.append(line)
        
        return lines

