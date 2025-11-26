"""Image model for DOCX documents."""

from typing import Dict, Any, Optional, Tuple
from .base import Models

class Image(Models):
    """Represents an image drawing stored in the document package."""
    
    def __init__(self):
        """Initialize image."""
        super().__init__()
        self.rel_id: str = ""
        self.relationship_source: Optional[str] = None
        self.part_path: Optional[str] = None
        self.width: int = 0
        self.height: int = 0
        self.position: Tuple[int, int] = (0, 0)
        self.anchor_type: str = "inline"  # "inline" or "anchor"
        self.z_order: str = "front"  # "front" or "behind" - render order relative to text
        self.raw_xml: Optional[str] = None
    
    def set_rel_id(self, rel_id: str):
        """Set relationship ID for image."""
        self.rel_id = rel_id
    
    def set_relationship_source(self, source: Optional[str]):
        """Set the relationship file path this image originates from."""
        self.relationship_source = source

    def set_part_path(self, part_path: Optional[str]):
        """Set the part XML path the image is defined in."""
        self.part_path = part_path

    def set_size(self, width: int, height: int):
        """Set image size."""
        self.width = width
        self.height = height
    
    def set_dimensions(self, width: int, height: int):
        """Set image dimensions (alias for set_size)."""
        self.set_size(width, height)
    
    def set_position(self, x: int, y: int = None):
        """Set image position."""
        if y is None:
            # If only one argument, assume it's a tuple or dict
            if isinstance(x, (tuple, list)):
                self.position = tuple(x)
            elif isinstance(x, dict):
                self.position = x  # Keep as dict if input is dict
            else:
                self.position = (x, 0)
        else:
            self.position = (x, y)
    
    def set_anchor_type(self, anchor_type: str):
        """Set anchor type (inline or anchor)."""
        self.anchor_type = anchor_type

    def set_raw_xml(self, raw_xml: Optional[str]):
        """Store raw XML representation of the drawing anchor."""
        self.raw_xml = raw_xml
    
    def get_rel_id(self):
        """Get relationship ID for image."""
        return self.rel_id
    
    def get_size(self):
        """Get image size."""
        return (self.width, self.height)
    
    def get_position(self):
        """Get image position."""
        return self.position
    
    def is_inline(self):
        """Check if image is inline."""
        return self.anchor_type == "inline"
    
    def is_anchored(self):
        """Check if image is anchored."""
        return self.anchor_type == "anchor"
    
    def get_src(self):
        """Get image source path."""
        if hasattr(self, 'parent') and self.parent:
            return self.parent.get_relationship_target(self.rel_id)
        return ""
    
    def get_alt(self):
        """Get image alt text."""
        return getattr(self, 'alt_text', '')
    
    def get_width(self):
        """Get image width."""
        return self.width
    
    def get_height(self):
        """Get image height."""
        return self.height
