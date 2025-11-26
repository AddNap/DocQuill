"""Custom exceptions for DOCX Interpreter."""

from typing import Optional


class DocxInterpreterError(Exception):
    """Base exception for DOCX Interpreter errors."""

    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ParsingError(DocxInterpreterError):
    """Exception raised during document parsing."""

    pass


class LayoutError(DocxInterpreterError):
    """Exception raised during layout calculation."""

    pass


class RenderingError(DocxInterpreterError):
    """Exception raised during document rendering."""

    pass


class FontError(DocxInterpreterError):
    """Exception raised during font resolution."""

    pass


class StyleError(DocxInterpreterError):
    """Exception raised during style resolution."""

    pass


class NumberingError(DocxInterpreterError):
    """Exception raised during numbering formatting."""

    pass


class GeometryError(DocxInterpreterError):
    """Exception raised during geometry calculations."""

    pass


class MediaError(DocxInterpreterError):
    """Exception raised during media processing."""

    pass


class CompilationError(DocxInterpreterError):
    """Exception raised during PDF compilation."""

    pass

