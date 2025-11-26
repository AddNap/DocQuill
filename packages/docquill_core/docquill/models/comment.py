"""
Comment model for DOCX documents.

Handles comment functionality, content, author information, date information, and range information.
"""

from typing import Dict, Any, Optional, List
from .base import Models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Comment(Models):
    """
    Represents a comment in the document.
    
    Handles comment functionality, content, author information, and date information.
    """
    
    def __init__(self, content: str = "", author: str = "", date: datetime = None, 
                 start_pos: int = 0, end_pos: int = 0):
        """
        Initialize comment.
        
        Args:
            content: Comment content
            author: Comment author
            date: Comment date
            start_pos: Start position in document
            end_pos: End position in document
        """
        super().__init__()
        self.content = content
        self.author = author
        self.date = date or datetime.now()
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.properties = {}
        self.validation_errors = []
        
        logger.debug(f"Comment initialized by {author}")
    
    def set_content(self, content: str) -> None:
        """
        Set comment content.
        
        Args:
            content: Comment content
        """
        if not isinstance(content, str):
            raise ValueError("Comment content must be a string")
        
        self.content = content
        logger.debug(f"Comment content set: {len(content)} characters")
    
    def set_author(self, author: str) -> None:
        """
        Set comment author.
        
        Args:
            author: Comment author
        """
        if not isinstance(author, str):
            raise ValueError("Comment author must be a string")
        
        self.author = author
        logger.debug(f"Comment author set to: {author}")
    
    def set_date(self, date: datetime) -> None:
        """
        Set comment date.
        
        Args:
            date: Comment date
        """
        if not isinstance(date, datetime):
            raise ValueError("Comment date must be a datetime object")
        
        self.date = date
        logger.debug(f"Comment date set to: {date}")
    
    def set_range(self, start_pos: int, end_pos: int) -> None:
        """
        Set comment range.
        
        Args:
            start_pos: Start position in document
            end_pos: End position in document
        """
        if not isinstance(start_pos, int) or not isinstance(end_pos, int):
            raise ValueError("Comment range positions must be integers")
        
        if start_pos < 0 or end_pos < 0:
            raise ValueError("Comment range positions must be non-negative")
        
        if start_pos > end_pos:
            raise ValueError("Start position must be less than or equal to end position")
        
        self.start_pos = start_pos
        self.end_pos = end_pos
        logger.debug(f"Comment range set: {start_pos}-{end_pos}")
    
    def get_text(self) -> str:
        """
        Get comment text.
        
        Returns:
            Comment text content
        """
        return self.content
    
    def get_author(self) -> str:
        """
        Get comment author.
        
        Returns:
            Comment author
        """
        return self.author
    
    def get_date(self) -> datetime:
        """
        Get comment date.
        
        Returns:
            Comment date
        """
        return self.date
    
    def get_range(self) -> tuple:
        """
        Get comment range.
        
        Returns:
            Tuple of (start_pos, end_pos)
        """
        return (self.start_pos, self.end_pos)
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set comment property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Comment property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get comment property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate comment.
        
        Returns:
            True if comment is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate content
        if not self.content:
            self.validation_errors.append("Comment content is required")
        
        # Validate author
        if not self.author:
            self.validation_errors.append("Comment author is required")
        
        # Validate date
        if not isinstance(self.date, datetime):
            self.validation_errors.append("Comment date must be a datetime object")
        
        # Validate range
        if self.start_pos < 0 or self.end_pos < 0:
            self.validation_errors.append("Comment range positions must be non-negative")
        
        if self.start_pos > self.end_pos:
            self.validation_errors.append("Start position must be less than or equal to end position")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Comment validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert comment to dictionary.
        
        Returns:
            Dictionary representation of comment
        """
        return {
            'type': 'comment',
            'content': self.content,
            'author': self.author,
            'date': self.date.isoformat() if self.date else None,
            'start_pos': self.start_pos,
            'end_pos': self.end_pos,
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load comment from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.content = data.get('content', '')
        self.author = data.get('author', '')
        date_str = data.get('date')
        if date_str:
            self.date = datetime.fromisoformat(date_str)
        else:
            self.date = datetime.now()
        self.start_pos = data.get('start_pos', 0)
        self.end_pos = data.get('end_pos', 0)
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"Comment loaded from dictionary by {self.author}")
    
    def get_comment_info(self) -> Dict[str, Any]:
        """
        Get comment information.
        
        Returns:
            Dictionary with comment information
        """
        return {
            'content_length': len(self.content),
            'author': self.author,
            'date': self.date.isoformat() if self.date else None,
            'range': f"{self.start_pos}-{self.end_pos}",
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_content(self) -> None:
        """Clear comment content."""
        self.content = ""
        logger.debug("Comment content cleared")
    
    def clear_properties(self) -> None:
        """Clear all comment properties."""
        self.properties.clear()
        logger.debug("Comment properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if comment has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove comment property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Comment property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if comment is empty.
        
        Returns:
            True if comment has no content, False otherwise
        """
        return not self.content.strip()
    
    def get_length(self) -> int:
        """
        Get comment content length.
        
        Returns:
            Length of comment content
        """
        return len(self.content)
