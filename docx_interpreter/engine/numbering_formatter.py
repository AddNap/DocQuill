"""Helpers for formatting numbering markers during layout."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, Optional, Tuple

from .font_resolver import resolve_font_path
from .geometry import twips_to_points

logger = logging.getLogger(__name__)


class NumberingFormatter:
    """Formats list markers based on numbering definitions."""

    def __init__(self, numbering_data: Optional[Dict[str, Any]] = None) -> None:
        data = numbering_data or {}
        self.abstract_numberings: Dict[str, Dict[str, Any]] = {
            str(k): v for k, v in (data.get("abstract_numberings") or {}).items()
        }
        self.numbering_instances: Dict[str, Dict[str, Any]] = {
            str(k): v for k, v in (data.get("numbering_instances") or {}).items()
        }
        self._counters: Dict[Tuple[str, str], int] = defaultdict(int)

    def format(self, num_id: Optional[str], level: Optional[str]) -> Optional[Dict[str, Any]]:
        if not num_id:
            return None

        num_id = str(num_id)
        level = str(level or "0")

        definition = self._level_definition(num_id, level)
        if not definition:
            return None

        counter_key = (num_id, level)
        start_value = self._parse_int(definition.get("start"), fallback=1)
        if counter_key not in self._counters or self._counters[counter_key] < start_value - 1:
            self._counters[counter_key] = start_value - 1
        self._counters[counter_key] += 1
        counter = self._counters[counter_key]

        marker_text = self._format_marker_text(definition, level, counter)
        font_style = self._font_style(definition)

        metrics = self._build_level_metrics(definition)

        return {
            "text": marker_text,
            "style": font_style,
            "counter": counter,
            "format": definition.get("format", "decimal"),
            "indent_left": metrics.get("indent_left", 0.0),
            "indent_right": metrics.get("indent_right", 0.0),
            "indent_hanging": metrics.get("indent_hanging", 0.0),
            "indent_first_line": metrics.get("indent_first_line", 0.0),
            "suffix": metrics.get("suffix"),
            "alignment": metrics.get("alignment"),
            "tab_position": metrics.get("tab_position"),
            "number_position": metrics.get("number_position"),
            "text_position": metrics.get("text_position"),
        }

    def reset(self) -> None:
        self._counters.clear()
    
    def rewind(self, num_id: Optional[str], level: Optional[str]) -> None:
        """Undo the last counter increment for a numbering level."""
        if not num_id:
            return

        num_id = str(num_id)
        level = str(level or "0")
        counter_key = (num_id, level)
        if counter_key not in self._counters:
            return

        definition = self._level_definition(num_id, level)
        start_value = self._parse_int(definition.get("start") if definition else None, fallback=1)
        min_value = start_value - 1
        current = self._counters[counter_key]

        if current > min_value:
            self._counters[counter_key] = current - 1

        if self._counters[counter_key] <= min_value:
            # Keep baseline value for future increments
            self._counters[counter_key] = min_value

    def get_level_metrics(self, num_id: Optional[str], level: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get level metrics (indents, etc.) for a numbering level.
        
        Args:
            num_id: Numbering ID
            level: Level number (as string or int)
            
        Returns:
            Dictionary with level metrics (indent_left, indent_hanging, etc.) or None
        """
        if not num_id:
            return None
        
        num_id = str(num_id)
        level = str(level or "0")
        
        definition = self._level_definition(num_id, level)
        if not definition:
            return None
        
        return self._build_level_metrics(definition)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _level_definition(self, num_id: str, level: str) -> Optional[Dict[str, Any]]:
        num_instance = self.numbering_instances.get(num_id)
        if not num_instance:
            return None

        abstract_id = str(num_instance.get("abstractNumId", ""))
        abstract = self.abstract_numberings.get(abstract_id)
        if not abstract:
            return None

        levels = abstract.get("levels", {})
        level_def = dict(levels.get(level) or {})

        overrides = num_instance.get("levels", {})
        if level in overrides:
            override = overrides[level]
            for key in ("format", "text", "start"):
                if override.get(key):
                    level_def[key] = override[key]

        return level_def or None

    def _build_level_metrics(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        indent_left = self._to_points(definition.get("indent_left"))
        indent_right = self._to_points(definition.get("indent_right"))
        indent_hanging = self._to_points(definition.get("indent_hanging"))
        indent_first_line = self._to_points(definition.get("indent_first_line"))

        suffix = definition.get("suffix") or "tab"
        alignment = definition.get("alignment") or "left"
        tab_position = self._resolve_tab_position(definition.get("tabs"))
        effective_tab_position = tab_position
        if (
            suffix == "tab"
            and effective_tab_position is not None
            and abs(effective_tab_position) < 0.05
            and indent_left
        ):
            effective_tab_position = indent_left

        # Determine text and marker positions
        number_position = indent_left - indent_hanging
        text_position = indent_left

        if suffix == "tab":
            if effective_tab_position is None and indent_left:
                tab_position = indent_left
            if effective_tab_position is None and tab_position is not None:
                effective_tab_position = tab_position
            if effective_tab_position is not None:
                text_position = effective_tab_position
        elif suffix == "nothing":
            text_position = indent_left
        elif suffix == "space":
            text_position = indent_left

        if indent_first_line == 0.0:
            if suffix == "tab" and effective_tab_position is not None:
                indent_first_line = effective_tab_position
            elif indent_hanging:
                indent_first_line = indent_left - indent_hanging
            else:
                indent_first_line = indent_left

        return {
            "indent_left": indent_left,
            "indent_right": indent_right,
            "indent_hanging": indent_hanging,
            "indent_first_line": indent_first_line,
            "suffix": suffix,
            "alignment": alignment,
            "tab_position": effective_tab_position,
            "number_position": number_position,
            "text_position": text_position,
        }

    def _resolve_tab_position(self, tabs: Optional[Any]) -> Optional[float]:
        if not tabs:
            return None

        for tab in tabs:
            if not isinstance(tab, dict):
                continue
            if tab.get("val") == "num" and tab.get("pos") is not None:
                return self._to_points(tab.get("pos"))

        for tab in tabs:
            if not isinstance(tab, dict):
                continue
            if tab.get("pos") is not None:
                return self._to_points(tab.get("pos"))

        return None

    @staticmethod
    def _parse_int(value: Any, fallback: int = 0) -> int:
        if value is None:
            return fallback
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return fallback

    def _format_marker_text(self, definition: Dict[str, Any], level: str, counter: int) -> str:
        fmt = definition.get("format", "decimal")
        template = definition.get("text") or ("•" if fmt == "bullet" else "%1.")

        text = template

        if isinstance(text, str) and "\\u" in text:
            try:
                text = text.encode("utf-8").decode("unicode_escape")
            except Exception as e:
                logger.debug(f"Failed to decode unicode escape in numbering template '{template}': {e}")
                # Continue with original text if decode fails

        # Handle bullet format
        if fmt == "bullet":
            mapping = {
                "\uf0b7": "•",
                "\uf0d8": "◘",
                "\uf0a7": "►",
                "\uf0fc": "▪",
            }
            return mapping.get(text, text or "•")

        # Handle none/nothing format
        if fmt in ("none", "nothing"):
            return ""

        # Format the counter value based on format type
        formatted_counter = self._format_counter(counter, fmt)

        # Replace placeholders in template
        def replace_placeholder(match_index: int, value: str) -> None:
            placeholder = f"%{match_index}"
            nonlocal text
            if placeholder in text:
                text = text.replace(placeholder, value)

        # Replace level-specific placeholder (e.g., %1 for level 0, %2 for level 1)
        level_idx = int(level) + 1
        replace_placeholder(level_idx, formatted_counter)

        # Replace all other placeholders with the same formatted counter
        if "%" in text:
            for idx in range(1, 10):
                replace_placeholder(idx, formatted_counter)

        return text

    def _format_counter(self, counter: int, fmt: str) -> str:
        """Format counter value based on format type.
        
        Args:
            counter: Counter value (1-based)
            fmt: Format type (decimal, lowerLetter, upperLetter, lowerRoman, upperRoman, etc.)
            
        Returns:
            Formatted counter string
        """
        fmt_lower = fmt.lower()
        
        if fmt_lower == "decimal":
            return str(counter)
        
        elif fmt_lower == "lowerletter":
            # a, b, c, ..., z, aa, ab, ...
            return self._number_to_letters(counter, lower=True)
        
        elif fmt_lower == "upperletter":
            # A, B, C, ..., Z, AA, AB, ...
            return self._number_to_letters(counter, lower=False)
        
        elif fmt_lower == "lowerroman":
            # i, ii, iii, iv, v, ...
            return self._number_to_roman(counter, upper=False)
        
        elif fmt_lower == "upperroman":
            # I, II, III, IV, V, ...
            return self._number_to_roman(counter, upper=True)
        
        elif fmt_lower in ("korean", "koreanlegal"):
            # Korean numbering
            return self._number_to_korean(counter)
        
        elif fmt_lower in ("chinesenum", "chinesetraditional", "chinesesimplified"):
            # Chinese numbering
            return self._number_to_chinese(counter, fmt_lower)
        
        elif fmt_lower in ("ordinal", "ordinaltext"):
            # Ordinal numbers (1st, 2nd, 3rd, ...)
            return self._number_to_ordinal(counter)
        
        elif fmt_lower == "cardinaltext":
            # Cardinal text (one, two, three, ...)
            return self._number_to_cardinal_text(counter)
        
        elif fmt_lower == "hex":
            # Hexadecimal
            return hex(counter)[2:]
        
        elif fmt_lower == "binary":
            # Binary
            return bin(counter)[2:]
        
        else:
            # Default to decimal for unknown formats
            logger.debug(f"Unknown numbering format: {fmt}, using decimal")
            return str(counter)

    def _number_to_letters(self, num: int, lower: bool = True) -> str:
        """Convert number to letters (a-z, aa-zz, etc.).
        
        Args:
            num: Number (1-based)
            lower: Use lowercase letters
            
        Returns:
            Letter string (a, b, ..., z, aa, ab, ...)
        """
        if num <= 0:
            return ""
        
        # Excel-style numbering: a-z, aa-az, ba-bz, ... (no zero)
        num -= 1  # Convert to 0-based
        result = ""
        
        while num >= 0:
            result = chr(ord('a' if lower else 'A') + (num % 26)) + result
            num = num // 26 - 1
        
        return result

    def _number_to_roman(self, num: int, upper: bool = True) -> str:
        """Convert number to Roman numerals.
        
        Args:
            num: Number (1-based)
            upper: Use uppercase letters
            
        Returns:
            Roman numeral string (I, II, III, IV, V, ...)
        """
        if num <= 0:
            return ""
        
        if num > 3999:
            # Roman numerals don't go beyond 3999 traditionally
            return str(num)
        
        val = [
            1000, 900, 500, 400,
            100, 90, 50, 40,
            10, 9, 5, 4,
            1
        ]
        syb = [
            "M", "CM", "D", "CD",
            "C", "XC", "L", "XL",
            "X", "IX", "V", "IV",
            "I"
        ]
        
        roman_num = ""
        i = 0
        while num > 0:
            for _ in range(num // val[i]):
                roman_num += syb[i]
                num -= val[i]
            i += 1
        
        return roman_num.upper() if upper else roman_num.lower()

    def _number_to_korean(self, num: int) -> str:
        """Convert number to Korean numbering.
        
        Args:
            num: Number (1-based)
            
        Returns:
            Korean number string
        """
        # Korean numbering uses specific characters
        korean_digits = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
        korean_units = ["", "십", "백", "천", "만"]
        
        if num <= 0:
            return ""
        
        if num < 10:
            return korean_digits[num]
        
        # Simplified Korean numbering for 1-99
        if num < 100:
            tens = num // 10
            ones = num % 10
            result = ""
            if tens > 1:
                result += korean_digits[tens]
            if tens > 0:
                result += korean_units[1]
            if ones > 0:
                result += korean_digits[ones]
            return result
        
        # For larger numbers, use decimal representation
        return str(num)

    def _number_to_chinese(self, num: int, fmt: str) -> str:
        """Convert number to Chinese numbering.
        
        Args:
            num: Number (1-based)
            fmt: Format type (chinesenum, chinesetraditional, chinesesimplified)
            
        Returns:
            Chinese number string
        """
        # Simplified Chinese numbering
        chinese_digits = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
        
        if num <= 0:
            return ""
        
        if num < 10:
            return chinese_digits[num]
        
        # For larger numbers, use decimal representation
        return str(num)

    def _number_to_ordinal(self, num: int) -> str:
        """Convert number to ordinal text (1st, 2nd, 3rd, etc.).
        
        Args:
            num: Number (1-based)
            
        Returns:
            Ordinal string (1st, 2nd, 3rd, ...)
        """
        if num <= 0:
            return ""
        
        suffix = "th"
        if 10 <= num % 100 <= 20:
            suffix = "th"
        else:
            last_digit = num % 10
            if last_digit == 1:
                suffix = "st"
            elif last_digit == 2:
                suffix = "nd"
            elif last_digit == 3:
                suffix = "rd"
        
        return f"{num}{suffix}"

    def _number_to_cardinal_text(self, num: int) -> str:
        """Convert number to cardinal text (one, two, three, etc.).
        
        Args:
            num: Number (1-based)
            
        Returns:
            Cardinal text string (one, two, three, ...)
        """
        if num <= 0:
            return ""
        
        # Basic cardinal numbers
        cardinals = {
            0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
            5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
            10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
            14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
            18: "eighteen", 19: "nineteen", 20: "twenty", 30: "thirty",
            40: "forty", 50: "fifty", 60: "sixty", 70: "seventy",
            80: "eighty", 90: "ninety"
        }
        
        if num in cardinals:
            return cardinals[num]
        
        # For larger numbers, use decimal representation
        return str(num)

    def _font_style(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        font = definition.get("font") or {}
        style: Dict[str, Any] = {}
        if font.get("name"):
            style["font_name"] = font["name"]
        if font.get("size"):
            try:
                style["font_size"] = float(font["size"]) / 2.0
            except (TypeError, ValueError):
                pass
        if font.get("bold"):
            style["bold"] = True
        if font.get("italic"):
            style["italic"] = True

        font_name = style.get("font_name")
        if font_name:
            bold = bool(style.get("bold"))
            italic = bool(style.get("italic"))
            resolved = resolve_font_path(font_name, bold=bold, italic=italic)
            if resolved:
                variant_name, font_path = resolved
                style["font_pdf_name"] = variant_name
                style["font_path"] = font_path
        return style

    def _to_points(self, value: Any) -> float:
        if value is None:
            return 0.0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if numeric > 144:
            return twips_to_points(numeric)
        return numeric

    def _normalize_font_size(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.endswith("pt"):
                stripped = stripped[:-2]
            try:
                numeric = float(stripped)
            except (TypeError, ValueError):
                return None
            return numeric / 2.0
        if isinstance(value, (int, float)):
            return float(value)
        return None

