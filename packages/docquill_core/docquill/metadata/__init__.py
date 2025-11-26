"""
Metadata module for DOCX document properties.

This module contains all components responsible for extracting
and managing document metadata and properties.
"""

from .metadata import Metadata
from .core_properties import CoreProperties
from .app_properties import AppProperties
from .custom_properties import CustomProperties
from .revision import Revision, TrackChanges

__all__ = [
    "Metadata",
    "CoreProperties",
    "AppProperties",
    "CustomProperties",
    "Revision",
    "TrackChanges",
]
