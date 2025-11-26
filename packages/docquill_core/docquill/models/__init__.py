"""
Models module for DOCX semantic models.

This module contains all semantic model classes that represent
document elements as Python objects.
"""

from .base import Models
from .body import Body
from .paragraph import Paragraph
from .run import Run
from .inline_fragment import InlineFragment
from .table import Table, TableRow, TableCell
from .image import Image
from .textbox import TextBox
from .field import Field
from .hyperlink import Hyperlink
from .document_part import DocumentPart
from .shape import Shape
from .numbering import NumberingGroup, NumberingLevel
# from .section import Section
from .style_ref import StyleReference
from .comment import Comment
from .footnote import Footnote, Endnote
from .controlbox import ControlBox
from .bookmark import Bookmark
from .smartart import SmartArt
from .chart import Chart
from .metadata_ref import MetadataReference
from .relation_ref import RelationReference

__all__ = [
    "Models",
    "Body",
    "Paragraph",
    "Run",
    "InlineFragment",
    "Table",
    "TableRow",
    "TableCell",
    "Image",
    "TextBox",
    "Field",
    "Hyperlink",
    "DocumentPart",
    "Shape",
    "NumberingGroup",
    "NumberingLevel",
    # "Section",
    "StyleReference",
    "Comment",
    "Footnote",
    "Endnote",
    "ControlBox",
    "Bookmark",
    "SmartArt",
    "Chart",
    "MetadataReference",
    "RelationReference",
]
