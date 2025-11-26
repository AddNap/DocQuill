"""Validation helpers for semantic DOCX models."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ..models.base import Models


class DocumentValidators:
    """Run a suite of lightweight checks over document models."""

    def __init__(self) -> None:
        self._errors: Dict[str, List[Dict[str, Any]]] = {
            "structure": [],
            "content": [],
            "format": [],
            "relationships": [],
        }

    # ------------------------------------------------------------------
    def _add_error(self, section: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        entry = {"message": message}
        if context:
            entry["context"] = context
        self._errors.setdefault(section, []).append(entry)

    def _reset_section(self, section: str) -> None:
        self._errors.setdefault(section, []).clear()

    # ------------------------------------------------------------------
    def validate_document_structure(self, document: Any) -> bool:
        """Ensure the high-level document hierarchy is coherent."""

        self._reset_section("structure")

        if document is None:
            self._add_error("structure", "Document instance is missing")
            return False

        body = getattr(document, "body", None) or getattr(document, "document_body", None)
        if body is None:
            self._add_error("structure", "Document has no body element")
            return False

        if not isinstance(body, Models):
            self._add_error(
                "structure",
                "Body element must inherit from Models",
                {"type": type(body).__name__},
            )
            return False

        for child in getattr(body, "children", []):
            if not isinstance(child, Models):
                self._add_error(
                    "structure",
                    "Child does not inherit from Models",
                    {"parent": type(body).__name__, "child": type(child).__name__},
                )
        return not self._errors["structure"]

    # ------------------------------------------------------------------
    def validate_content_integrity(self, content: Any) -> bool:
        """Check that content elements carry meaningful information."""

        self._reset_section("content")

        elements: Iterable[Any]
        if isinstance(content, Models):
            elements = content.children
        elif isinstance(content, Iterable) and not isinstance(content, (str, bytes)):
            elements = content
        else:
            self._add_error("content", "Unsupported content container", {"type": type(content).__name__})
            return False

        for idx, element in enumerate(elements):
            if element is None:
                self._add_error("content", "Encountered None element", {"index": idx})
                continue
            if hasattr(element, "get_text"):
                text_value = element.get_text()
                if text_value is None:
                    self._add_error("content", "Element get_text returned None", {"index": idx})
            elif isinstance(element, str):
                if not element.strip():
                    self._add_error("content", "Empty text fragment", {"index": idx})
            else:
                self._add_error(
                    "content",
                    "Unsupported element type",
                    {"index": idx, "type": type(element).__name__},
                )

        return not self._errors["content"]

    # ------------------------------------------------------------------
    def validate_format_compliance(self, document: Any) -> bool:
        """Validate that styles and numbering metadata are consistent."""

        self._reset_section("format")

        body = getattr(document, "body", None)
        paragraphs = getattr(body, "get_paragraphs_recursive", None)
        if callable(paragraphs):
            candidates = paragraphs()
        else:
            candidates = getattr(body, "children", []) if body else []

        for para in candidates:
            style = getattr(para, "style", None)
            if style is not None and not isinstance(style, dict):
                self._add_error(
                    "format",
                    "Paragraph style must be a dictionary",
                    {"paragraph": getattr(para, "id", None)},
                )
            numbering = getattr(para, "numbering", None)
            if numbering is not None and not isinstance(numbering, dict):
                self._add_error(
                    "format",
                    "Numbering metadata must be a dictionary",
                    {"paragraph": getattr(para, "id", None)},
                )

        return not self._errors["format"]

    # ------------------------------------------------------------------
    def validate_relationships(self, relationships: Any) -> bool:
        """Ensure relationship definitions are well-formed dictionaries."""

        self._reset_section("relationships")

        if relationships is None:
            self._add_error("relationships", "Relationships payload is missing")
            return False

        if not isinstance(relationships, dict):
            self._add_error("relationships", "Relationships must be a dictionary", {"type": type(relationships).__name__})
            return False

        for rel_id, rel_data in relationships.items():
            if not rel_id:
                self._add_error("relationships", "Empty relationship id detected")
            if not isinstance(rel_data, dict):
                self._add_error(
                    "relationships",
                    "Relationship entry must be a dictionary",
                    {"id": rel_id, "type": type(rel_data).__name__},
                )
                continue
            if "target" not in rel_data:
                self._add_error("relationships", "Relationship missing target", {"id": rel_id})
            if "type" not in rel_data:
                self._add_error("relationships", "Relationship missing type", {"id": rel_id})

        return not self._errors["relationships"]

    # ------------------------------------------------------------------
    def get_validation_errors(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return a deep copy of collected validation errors."""

        return {
            section: [entry.copy() for entry in errors]
            for section, errors in self._errors.items()
        }
