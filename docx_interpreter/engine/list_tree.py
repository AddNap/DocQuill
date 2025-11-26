"""
Helper structures for representing numbering lists as trees.

The goal is to mimic Word's hierarchical list model, so that paragraphs can
resolve their effective indents by walking the tree instead of relying on
ad-hoc calculations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

from .geometry import twips_to_points


@dataclass
class IndentSpec:
    """Simple container describing paragraph indents in points."""

    left: float = 0.0
    right: float = 0.0
    first_line: float = 0.0
    hanging: float = 0.0

    def copy(self) -> "IndentSpec":
        return IndentSpec(self.left, self.right, self.first_line, self.hanging)

    def add(self, other: "IndentSpec") -> None:
        self.left += other.left
        self.right += other.right
        self.first_line += other.first_line
        self.hanging += other.hanging

    def ensure_word_rules(self) -> None:
        if self.hanging and self.first_line:
            # Word prioritises hanging over firstLine
            self.first_line = 0.0


@dataclass
class NumberingLevel:
    level: int
    indent: IndentSpec
    format: str = ""
    text: str = ""
    start: int = 1
    overridden: bool = False


@dataclass
class ParagraphEntry:
    block_ref: Dict[str, Any]
    style_name: str
    paragraph_indent: IndentSpec
    style_indent: IndentSpec
    num_id: Optional[str]
    level: Optional[int]
    marker_text: str
    marker_visible: bool
    style_is_list: bool
    has_border: bool
    number_override: bool = False
    auto_correction: bool = True
    explicit_indent: bool = False
    inline_indent: Optional[IndentSpec] = None


@dataclass
class LevelEntryInfo:
    entry_id: int
    marker_text: str
    marker_visible: bool


@dataclass
class ListLevelNode:
    num_id: str
    level: int
    definition: NumberingLevel
    parent: Optional["ListLevelNode"] = None
    children: List[LevelEntryInfo] = field(default_factory=list)
    unified_left: Optional[float] = None
    last_resolved_indent: Optional["IndentSpec"] = None

    def append(self, paragraph: ParagraphEntry) -> None:
        self.children.append(
            LevelEntryInfo(
                entry_id=id(paragraph.block_ref),
                marker_text=paragraph.marker_text,
                marker_visible=paragraph.marker_visible,
            )
        )

    def record_left(self, left_value: float, threshold: float) -> float:
        values = getattr(self, "_left_values", None)
        if values is None:
            values = []
            setattr(self, "_left_values", values)
        values.append(left_value)
        if len(values) >= 2:
            max_v = max(values)
            min_v = min(values)
            if (max_v - min_v) <= threshold:
                unified = float(median(values))
                self.unified_left = unified
                setattr(self, "_left_values", [unified])
                return unified
        if len(values) > 6:
            setattr(self, "_left_values", values[-3:])
        return left_value

    def resolved_indent(self) -> IndentSpec:
        """Resolve indent by walking parents."""
        parts: List[IndentSpec] = []
        node: Optional[ListLevelNode] = self
        while node:
            parts.append(node.definition.indent)
            node = node.parent
        resolved = IndentSpec()
        for part in reversed(parts):
            resolved.add(part)
        return resolved


class ListTreeBuilder:
    """
    Builds tree structures for numbering lists and resolves paragraph indents.
    """

    UNIFY_THRESHOLD_PT = 9.0  # ~180 twips
    MIN_MARKER_WIDTH_PT = 6.0
    MARKER_BUFFER_PT = 3.0

    def __init__(self, numbering_data: Optional[Dict[str, Any]] = None):
        numbering_data = numbering_data or {}
        self.level_registry: Dict[str, List[NumberingLevel]] = {}
        self._parse_numbering_data(numbering_data)
        self.active_stacks: Dict[str, List[ListLevelNode]] = {}
        self.last_active_level: Optional[ListLevelNode] = None
        self.marker_registry: Dict[Tuple[str, int], ListLevelNode] = {}
        self.marker_indent_registry: Dict[Tuple[str, int], IndentSpec] = {}
        self.scope_counters: Dict[Tuple[str, int, Optional[int]], int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self.active_stacks.clear()
        self.last_active_level = None
        self.marker_registry.clear()
        self.marker_indent_registry.clear()
        self.scope_counters.clear()

    def print_tree_structure(self) -> None:
        """Print the current list tree structure for debugging."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("=" * 80)
        logger.info("LIST TREE STRUCTURE")
        logger.info("=" * 80)
        
        if not self.active_stacks:
            logger.info("No active list stacks")
            return
        
        for num_id, stack in self.active_stacks.items():
            logger.info(f"\nNumbering ID: {num_id}")
            logger.info(f"  Stack depth: {len(stack)}")
            for idx, node in enumerate(stack):
                indent = node.definition.indent
                resolved = node.resolved_indent()
                logger.info(f"  Level {node.level} (stack index {idx}):")
                logger.info(f"    Definition indent: left={indent.left:.2f}pt, right={indent.right:.2f}pt, first_line={indent.first_line:.2f}pt, hanging={indent.hanging:.2f}pt")
                logger.info(f"    Resolved indent: left={resolved.left:.2f}pt, right={resolved.right:.2f}pt, first_line={resolved.first_line:.2f}pt, hanging={resolved.hanging:.2f}pt")
                logger.info(f"    Format: {node.definition.format}, Text: {node.definition.text}")
                logger.info(f"    Children count: {len(node.children)}")
                if node.unified_left is not None:
                    logger.info(f"    Unified left: {node.unified_left:.2f}pt")
                if node.last_resolved_indent:
                    last = node.last_resolved_indent
                    logger.info(f"    Last resolved: left={last.left:.2f}pt, right={last.right:.2f}pt, first_line={last.first_line:.2f}pt, hanging={last.hanging:.2f}pt")
        
        if self.marker_registry:
            logger.info(f"\nMarker Registry ({len(self.marker_registry)} entries):")
            for (marker_token, level, scope_id), node in self.marker_registry.items():
                logger.info(f"  Marker '{marker_token}' (level {level}, scope {scope_id}): num_id={node.num_id}, level={node.level}")
        
        if self.marker_indent_registry:
            logger.info(f"\nMarker Indent Registry ({len(self.marker_indent_registry)} entries):")
            for (marker_token, level, scope_id), indent_spec in self.marker_indent_registry.items():
                logger.info(f"  Marker '{marker_token}' (level {level}, scope {scope_id}): left={indent_spec.left:.2f}pt, hanging={indent_spec.hanging:.2f}pt")
        
        logger.info("=" * 80)

    def process_paragraph(self, entry: ParagraphEntry) -> Tuple[IndentSpec, float, float, Optional[str], Optional[int], Dict[str, Any]]:
        """
        Process a paragraph and return effective indent specification.

        Returns:
            indent, text_start, number_start, effective_num_id, effective_level, meta_updates
        """
        if entry.has_border:
            base = entry.inline_indent or entry.paragraph_indent or entry.style_indent
            resolved = base.copy()
            resolved.ensure_word_rules()
            text_start = self._text_start(resolved)
            number_start = self._number_start(resolved)
            meta = {"list_indent_mode": "none", "auto_correction": False}
            return resolved, text_start, number_start, entry.num_id, entry.level, meta

        if entry.num_id is not None:
            resolved_indent, text_start, number_start, meta = self._handle_numbered(entry)
        elif (
            entry.style_is_list
            or (
                self.last_active_level
                and self.last_active_level.definition.format
                and self._marker_tokens_match(entry.marker_text, self.last_active_level.definition.text)
                and self.last_active_level.level == (entry.level or self.last_active_level.level)
            )
        ):
            resolved_indent, text_start, number_start, meta = self._handle_list_style(entry)
        else:
            # Paragraphs without numbering: first we use style from list_tree (style_indent + paragraph_indent)
            resolved_indent = self._combine_indents(entry.style_indent, None, entry.paragraph_indent)
            resolved_indent.ensure_word_rules()
            # Inline indents override style indents ONLY if explicit (explicit_indent=True)
            # Otherwise we use style indents (style has priority)
            if entry.explicit_indent and entry.inline_indent is not None:
                resolved_indent.left = entry.inline_indent.left
                resolved_indent.right = entry.inline_indent.right
                resolved_indent.first_line = entry.inline_indent.first_line
                resolved_indent.hanging = entry.inline_indent.hanging
                resolved_indent.ensure_word_rules()
            text_start = self._text_start(resolved_indent)
            number_start = self._number_start(resolved_indent)
            meta = {"list_indent_mode": "none", "auto_correction": entry.auto_correction}

        return resolved_indent, text_start, number_start, meta.get("num_id"), meta.get("level"), meta

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_numbered(self, entry: ParagraphEntry):
        num_id = entry.num_id or ""
        level = entry.level or 0
        previous_level = self.last_active_level
        level_def = self._get_level_definition(num_id, level)
        candidate_marker = entry.marker_text or level_def.text
        marker_token = self._normalize_marker_token(candidate_marker)
        stack = self.active_stacks.setdefault(num_id, [])
        current_parent = stack[-1] if stack else None
        scope_id: Optional[int] = id(current_parent) if current_parent else None
        marker_key: Optional[Tuple[str, int, Optional[int]]] = None
        if marker_token:
            marker_key = (marker_token, entry.level or 0, scope_id)
        registry_level: Optional[ListLevelNode] = None
        if marker_key:
            registry_level = self.marker_registry.get(marker_key)
            if registry_level and registry_level is previous_level:
                registry_level = None

        # Pop levels deeper or equal to current to maintain hierarchy
        while stack and stack[-1].level >= level:
            stack.pop()

        parent = stack[-1] if stack else None
        scope_id = id(parent) if parent else None
        if marker_token:
            marker_key = (marker_token, entry.level or 0, scope_id)
            if registry_level and registry_level is previous_level and registry_level.parent is not parent:
                registry_level = None
        node = ListLevelNode(num_id=num_id, level=level, definition=level_def, parent=parent)
        stack.append(node)
        self.last_active_level = node

        # First check marker_indent_registry for unification between different num_id
        matched_previous_chain = False
        unified_base_indent: Optional[IndentSpec] = None
        if marker_key:
            # First check exact marker_key (with scope_id)
            baseline = self.marker_indent_registry.get(marker_key)
            if baseline is None:
                # If no exact match, check marker with same token and level,
                # but without scope_id (for unification between different num_id)
                marker_token, marker_level, _ = marker_key
                alternative_key = None
                # Check all entries with same marker_token and level
                for key, indent_spec in self.marker_indent_registry.items():
                    key_token, key_level, _ = key
                    if key_token == marker_token and key_level == marker_level:
                        baseline = indent_spec
                        alternative_key = key
                        break
                
                if baseline is not None:
                    # Use found baseline as unified_base_indent
                    unified_base_indent = baseline.copy()
                    matched_previous_chain = True
            else:
                # Exact match - use baseline
                unified_base_indent = baseline.copy()
                matched_previous_chain = True

        # Use unified_base_indent if found, otherwise use base_indent from node
        if unified_base_indent is not None:
            base_indent = unified_base_indent
        else:
            base_indent = node.resolved_indent()
        
        resolved_indent = self._combine_indents(
            entry.style_indent,
            base_indent,
            entry.paragraph_indent,
            allow_paragraph_override=entry.explicit_indent,
        )
        resolved_indent.ensure_word_rules()
        # Inline indents override list_tree indents ONLY if explicit (explicit_indent=True)
        # Otherwise we use list_tree indents (list_tree has priority)
        if entry.explicit_indent and entry.inline_indent is not None:
            resolved_indent.left = entry.inline_indent.left
            resolved_indent.right = entry.inline_indent.right
            resolved_indent.first_line = entry.inline_indent.first_line
            resolved_indent.hanging = entry.inline_indent.hanging
            resolved_indent.ensure_word_rules()
        # If we have unified indent from marker_indent_registry, don't modify it further
        # (unification has priority over parent_indent_for_alignment and reference_level)
        if not matched_previous_chain:
            parent_indent_for_alignment: Optional[IndentSpec] = None
            if parent:
                parent_indent_for_alignment = parent.last_resolved_indent or parent.resolved_indent()
            if (
                parent_indent_for_alignment
                and entry.inline_indent is None
                and not entry.explicit_indent
            ):
                parent_text_start = self._text_start(parent_indent_for_alignment)
                hanging = level_def.indent.hanging or resolved_indent.hanging
                if hanging or parent_text_start:
                    resolved_indent.hanging = hanging
                    resolved_indent.first_line = 0.0
                    resolved_indent.left = max(parent_text_start, 0.0) + hanging
                    resolved_indent.ensure_word_rules()
            
            # Save resolved_indent to marker_indent_registry if no match
            if marker_key:
                # Check again if match appeared
                existing = self.marker_indent_registry.get(marker_key)
                if existing is None:
                    # Check all entries with same marker_token and level (ignoring num_id)
                    marker_token, marker_level, _ = marker_key
                    for key, indent_spec in self.marker_indent_registry.items():
                        key_token, key_level, _ = key
                        if key_token == marker_token and key_level == marker_level:
                            # Use existing indent as baseline
                            if resolved_indent.left + 1e-3 >= indent_spec.left:
                                resolved_indent = indent_spec.copy()
                                resolved_indent.ensure_word_rules()
                                matched_previous_chain = True
                            break
                    # Zapisz resolved_indent jako nowy baseline
                    if not matched_previous_chain:
                        self.marker_indent_registry[marker_key] = resolved_indent.copy()
                    else:
                        self.marker_indent_registry[marker_key] = resolved_indent.copy()
                else:
                    # Use existing baseline
                    if resolved_indent.left + 1e-3 >= existing.left:
                        resolved_indent = existing.copy()
                        resolved_indent.ensure_word_rules()
                        matched_previous_chain = True
                    else:
                        # Update baseline if resolved_indent is smaller
                        self.marker_indent_registry[marker_key] = resolved_indent.copy()

        effective_auto = entry.auto_correction and not entry.number_override and not node.definition.overridden

        # Unification based on reference_level - check marker and level, not num_id
        reference_level: Optional[ListLevelNode] = None
        if previous_level and previous_level.level == level:
            # Check if marker matches (don't check num_id - unification between different num_id)
            previous_marker_text = ""
            if previous_level.children:
                previous_marker_text = previous_level.children[-1].marker_text or ""
            if not previous_marker_text:
                previous_marker_text = previous_level.definition.text
            if not previous_marker_text:
                registry = self.level_registry.get(previous_level.num_id) or []
                if 0 <= previous_level.level < len(registry):
                    previous_marker_text = registry[previous_level.level].text
            marker_match = self._marker_tokens_match(candidate_marker, previous_marker_text)
            if marker_match or (
                not previous_marker_text
                and not candidate_marker
                and previous_level.definition.format
                and previous_level.definition.format == level_def.format
            ):
                reference_level = previous_level
        elif registry_level and registry_level.level == level:
            reference_level = registry_level

        if reference_level and not matched_previous_chain:
            previous_indent = reference_level.last_resolved_indent or reference_level.resolved_indent()
            if previous_indent:
                # Use previous_indent as baseline for unification
                resolved_indent = previous_indent.copy()
                resolved_indent.ensure_word_rules()
                matched_previous_chain = True
                # Zapisz do marker_indent_registry
                if marker_key:
                    self.marker_indent_registry[marker_key] = resolved_indent.copy()
                effective_auto = True

        if matched_previous_chain:
            effective_auto = True

        if effective_auto and not entry.explicit_indent:
            unified_left = node.record_left(resolved_indent.left, self.UNIFY_THRESHOLD_PT)
            if node.unified_left is not None:
                resolved_indent.left = node.unified_left
            self._ensure_marker_width(resolved_indent, entry.marker_text or level_def.text)

        node.append(entry)
        node.last_resolved_indent = resolved_indent.copy()
        if marker_key and marker_key not in self.marker_registry:
            self.marker_registry[marker_key] = node
        text_start = self._text_start(resolved_indent)
        number_start = self._number_start(resolved_indent)

        meta = {
            "list_indent_mode": "auto" if effective_auto else "manual",
            "num_id": num_id,
            "level": level,
            "auto_correction": effective_auto,
        }
        if matched_previous_chain:
            meta["list_indent_mode"] = "auto-match"
            meta["matched_previous_chain"] = True

        marker_override = None
        restart_marker = False
        scope_key = (num_id, level, scope_id)
        fmt_lower = level_def.format.lower()
        if fmt_lower not in ("bullet", "none", "nothing"):
            start_value = level_def.start or 1
            if scope_key not in self.scope_counters:
                current_counter = start_value
                restart_marker = True
            else:
                current_counter = self.scope_counters[scope_key] + 1
            self.scope_counters[scope_key] = current_counter
            marker_override = self._format_marker(level_def, current_counter)
            meta["marker_override_counter"] = current_counter
            meta["marker_override_text"] = marker_override
            if restart_marker:
                meta["marker_restart"] = True

        return resolved_indent, text_start, number_start, meta

    def _handle_list_style(self, entry: ParagraphEntry):
        node = None
        if self.last_active_level:
            if entry.style_is_list or self.last_active_level.num_id == entry.num_id:
                node = self.last_active_level
        base_level_indent = node.resolved_indent() if node else None
        effective_auto = entry.auto_correction
        if node and effective_auto and not entry.explicit_indent and base_level_indent is not None:
            resolved_indent = base_level_indent.copy()
        else:
            resolved_indent = self._combine_indents(
                entry.style_indent,
                base_level_indent,
                entry.paragraph_indent,
                allow_paragraph_override=entry.explicit_indent,
            )
        resolved_indent.ensure_word_rules()
        # Inline indents override list_tree indents ONLY if explicit (explicit_indent=True)
        # Otherwise we use list_tree indents (list_tree has priority)
        if entry.explicit_indent and entry.inline_indent is not None:
            resolved_indent.left = entry.inline_indent.left
            resolved_indent.right = entry.inline_indent.right
            resolved_indent.first_line = entry.inline_indent.first_line
            resolved_indent.hanging = entry.inline_indent.hanging
            resolved_indent.ensure_word_rules()
        if entry.style_is_list and not entry.marker_visible:
            if entry.inline_indent is None:
                resolved_indent.left = 0.0
            resolved_indent.hanging = 0.0
            resolved_indent.first_line = 0.0
            resolved_indent.ensure_word_rules()
        if node:
            node.append(entry)
            if effective_auto and not entry.explicit_indent:
                node.record_left(resolved_indent.left, self.UNIFY_THRESHOLD_PT)
            node.last_resolved_indent = resolved_indent.copy()
        if effective_auto:
            self._ensure_marker_width(resolved_indent, entry.marker_text or "")
        text_start = self._text_start(resolved_indent)
        number_start = self._number_start(resolved_indent)
        meta = {
            "list_indent_mode": "continuation" if node else "manual",
            "auto_correction": effective_auto,
        }
        if node:
            meta["num_id"] = node.num_id
            meta["level"] = node.level
        return resolved_indent, text_start, number_start, meta

    def _format_marker(self, level_def: NumberingLevel, counter: int) -> str:
        template = level_def.text or ""
        fmt = (level_def.format or "").lower()
        formatted_counter = self._format_counter(counter, fmt)
        if not template:
            return formatted_counter

        text = template
        if "%" in text:
            level_idx = level_def.level + 1

            def replace_placeholder(idx: int) -> None:
                nonlocal text
                placeholder = f"%{idx}"
                if placeholder in text:
                    text = text.replace(placeholder, formatted_counter)

            replace_placeholder(level_idx)
            for idx in range(1, 10):
                replace_placeholder(idx)
        else:
            text = formatted_counter or text
        return text

    @staticmethod
    def _format_counter(counter: int, fmt: str) -> str:
        fmt_lower = (fmt or "").lower()
        if fmt_lower in ("", "decimal"):
            return str(counter)
        if fmt_lower == "lowerletter":
            return ListTreeBuilder._number_to_letters(counter, lower=True)
        if fmt_lower == "upperletter":
            return ListTreeBuilder._number_to_letters(counter, lower=False)
        if fmt_lower == "lowerroman":
            return ListTreeBuilder._number_to_roman(counter, upper=False)
        if fmt_lower == "upperroman":
            return ListTreeBuilder._number_to_roman(counter, upper=True)
        if fmt_lower in ("ordinal", "ordinaltext"):
            return ListTreeBuilder._number_to_ordinal(counter)
        if fmt_lower == "cardinaltext":
            return str(counter)
        return str(counter)

    @staticmethod
    def _number_to_letters(num: int, lower: bool = True) -> str:
        if num <= 0:
            return ""
        num -= 1
        result = ""
        base = ord("a" if lower else "A")
        while num >= 0:
            result = chr(base + (num % 26)) + result
            num = num // 26 - 1
        return result

    @staticmethod
    def _number_to_roman(num: int, upper: bool = True) -> str:
        if num <= 0:
            return ""
        if num > 3999:
            return str(num)
        val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
        roman_num = ""
        i = 0
        while num > 0:
            count = num // val[i]
            roman_num += syb[i] * count
            num -= val[i] * count
            i += 1
        return roman_num.upper() if upper else roman_num.lower()

    @staticmethod
    def _number_to_ordinal(num: int) -> str:
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

    def _combine_indents(
        self,
        style_indent: IndentSpec,
        level_indent: Optional[IndentSpec],
        paragraph_indent: IndentSpec,
        allow_paragraph_override: bool = True,
    ) -> IndentSpec:
        result = style_indent.copy()
        if level_indent:
            result = level_indent.copy()
        if allow_paragraph_override and any(
            (
                paragraph_indent.left,
                paragraph_indent.right,
                paragraph_indent.first_line,
                paragraph_indent.hanging,
            )
        ):
            if paragraph_indent.left:
                result.left = paragraph_indent.left
            if paragraph_indent.right:
                result.right = paragraph_indent.right
            if paragraph_indent.first_line:
                result.first_line = paragraph_indent.first_line
            if paragraph_indent.hanging:
                result.hanging = paragraph_indent.hanging
        elif allow_paragraph_override:
            result.add(paragraph_indent)
        return result

    def _ensure_marker_width(self, indent: IndentSpec, marker_text: str) -> None:
        width = self._estimate_marker_width(marker_text)
        minimum = width + self.MARKER_BUFFER_PT
        if indent.hanging < minimum:
            diff = minimum - indent.hanging
            indent.hanging += diff
            indent.left += diff

    def _get_level_definition(self, num_id: str, level: int) -> NumberingLevel:
        levels = self.level_registry.get(num_id)
        if not levels:
            return NumberingLevel(level=level, indent=IndentSpec())
        level = max(level, 0)
        if level >= len(levels):
            return levels[-1]
        return levels[level]

    def _parse_numbering_data(self, numbering_data: Dict[str, Any]) -> None:
        abstract_defs = numbering_data.get("abstract_numberings") or {}
        numbering_instances = numbering_data.get("numbering_instances") or {}

        for num_id, instance in numbering_instances.items():
            abstract_id = str(instance.get("abstractNumId") or "")
            abstract = abstract_defs.get(abstract_id) or {}
            abstract_levels = abstract.get("levels") or {}
            overrides = instance.get("levels") or {}
            compiled_levels: List[NumberingLevel] = []
            for level_key in sorted(abstract_levels.keys(), key=lambda x: int(x)):
                base_def = dict(abstract_levels[level_key] or {})
                if level_key in overrides:
                    override = overrides[level_key] or {}
                    for k, v in override.items():
                        if v is not None:
                            base_def[k] = v
                indent = self._indent_from_definition(base_def)
                compiled_levels.append(
                    NumberingLevel(
                        level=int(level_key),
                        indent=indent,
                        format=base_def.get("format") or "",
                        text=base_def.get("text") or "",
                        start=_parse_int(base_def.get("start"), 1),
                        overridden=level_key in overrides,
                    )
                )
            self.level_registry[str(num_id)] = compiled_levels

    @staticmethod
    def _indent_from_definition(definition: Dict[str, Any]) -> IndentSpec:
        return IndentSpec(
            left=_convert_to_points(definition.get("indent_left")),
            right=_convert_to_points(definition.get("indent_right")),
            first_line=_convert_to_points(definition.get("indent_first_line")),
            hanging=_convert_to_points(definition.get("indent_hanging")),
        )

    @staticmethod
    def _text_start(indent: IndentSpec) -> float:
        if indent.first_line:
            return indent.left + indent.first_line
        return max(indent.left, 0.0)

    @staticmethod
    def _number_start(indent: IndentSpec) -> float:
        if indent.hanging:
            return max(indent.left - indent.hanging, 0.0)
        return max(indent.left, 0.0)

    def _estimate_marker_width(self, marker_text: str) -> float:
        text = marker_text.strip()
        if not text:
            return self.MIN_MARKER_WIDTH_PT
        return max(len(text) * self.MIN_MARKER_WIDTH_PT, self.MIN_MARKER_WIDTH_PT)

    @staticmethod
    @staticmethod
    def _normalize_marker_token(text: str) -> str:
        cleaned = re.sub(r"%(\d+)", r"\1", text or "").strip()
        if not cleaned:
            return ""
        token = []
        for ch in cleaned:
            if ch.isspace():
                break
            token.append(ch)
        value = "".join(token).strip()
        return value.rstrip(").,:;")

    @classmethod
    def _marker_tokens_match(cls, candidate: str, reference: str) -> bool:
        if not candidate or not reference:
            return False
        return cls._normalize_marker_token(candidate) == cls._normalize_marker_token(reference)


def _convert_to_points(value: Any) -> float:
    if value in (None, "", False):
        return 0.0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if abs(numeric) > 144.0:
        return twips_to_points(numeric)
    return numeric


def _parse_int(value: Any, default: int = 0) -> int:
    if value in (None, "", False):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


