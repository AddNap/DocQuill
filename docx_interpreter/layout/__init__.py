"""
Layout module for DOCX document layout and pagination.

This module contains all components responsible for document layout,
page management, section handling, and pagination logic.
"""

from .body import Body
from .header import Header
from .footer import Footer
from .page import Page
from .section import Section
from .pagination_manager import PaginationManager
from .numbering_resolver import NumberingResolver

__all__ = [
    "Body",
    "Header",
    "Footer",
    "Page",
    "Section",
    "PaginationManager",
    "NumberingResolver",
]
