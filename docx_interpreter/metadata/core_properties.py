"""
Core properties for DOCX documents.

Handles core properties functionality, core properties parsing, core properties validation, core properties access, and core properties serialization.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CoreProperties:
    """
    Represents core document properties.
    
    Handles core properties functionality, core properties parsing, core properties validation, and core properties access.
    """
    
    def __init__(self, title: str = "Untitled Document", author: str = "Unknown", 
                 created: Optional[datetime] = None, modified: Optional[datetime] = None,
                 subject: str = "", keywords: str = "", category: str = "", 
                 version: str = "1.0", language: str = "en-US"):
        """
        Initialize core properties.
        
        Args:
            title: Document title
            author: Document author
            created: Creation date
            modified: Modified date
            subject: Document subject
            keywords: Document keywords
            category: Document category
            version: Document version
            language: Document language
        """
        self.title = title
        self.author = author
        self.created = created or datetime.now()
        self.modified = modified or datetime.now()
        self.subject = subject
        self.keywords = keywords
        self.category = category
        self.version = version
        self.language = language
        self.validation_errors = []
        self.core_properties_stats = {
            'total_properties': 9,
            'required_properties': 4,
            'optional_properties': 5
        }
        
        logger.debug("Core properties initialized")
    
    def set_title(self, title: str) -> None:
        """
        Set document title.
        
        Args:
            title: Document title
        """
        if not isinstance(title, str):
            raise ValueError("Title must be a string")
        
        self.title = title
        logger.debug(f"Title set: {title}")
    
    def set_author(self, author: str) -> None:
        """
        Set document author.
        
        Args:
            author: Document author
        """
        if not isinstance(author, str):
            raise ValueError("Author must be a string")
        
        self.author = author
        logger.debug(f"Author set: {author}")
    
    def set_subject(self, subject: str) -> None:
        """
        Set document subject.
        
        Args:
            subject: Document subject
        """
        if not isinstance(subject, str):
            raise ValueError("Subject must be a string")
        
        self.subject = subject
        logger.debug(f"Subject set: {subject}")
    
    def set_keywords(self, keywords: str) -> None:
        """
        Set document keywords.
        
        Args:
            keywords: Document keywords
        """
        if not isinstance(keywords, str):
            raise ValueError("Keywords must be a string")
        
        self.keywords = keywords
        logger.debug(f"Keywords set: {keywords}")
    
    def set_created_date(self, date: datetime) -> None:
        """
        Set creation date.
        
        Args:
            date: Creation date
        """
        if not isinstance(date, datetime):
            raise ValueError("Created date must be a datetime object")
        
        self.created = date
        logger.debug(f"Created date set: {date}")
    
    def set_modified_date(self, date: datetime) -> None:
        """
        Set modification date.
        
        Args:
            date: Modified date
        """
        if not isinstance(date, datetime):
            raise ValueError("Modified date must be a datetime object")
        
        self.modified = date
        logger.debug(f"Modified date set: {date}")
    
    def get_title(self) -> str:
        """
        Get document title.
        
        Returns:
            Document title
        """
        return self.title
    
    def get_author(self) -> str:
        """
        Get document author.
        
        Returns:
            Document author
        """
        return self.author
    
    def get_created_date(self) -> datetime:
        """
        Get creation date.
        
        Returns:
            Creation date
        """
        return self.created
    
    def get_modified_date(self) -> datetime:
        """
        Get modified date.
        
        Returns:
            Modified date
        """
        return self.modified
    
    def get_subject(self) -> str:
        """
        Get document subject.
        
        Returns:
            Document subject
        """
        return self.subject
    
    def get_keywords(self) -> str:
        """
        Get document keywords.
        
        Returns:
            Document keywords
        """
        return self.keywords
    
    def get_category(self) -> str:
        """
        Get document category.
        
        Returns:
            Document category
        """
        return self.category
    
    def get_version(self) -> str:
        """
        Get document version.
        
        Returns:
            Document version
        """
        return self.version
    
    def get_language(self) -> str:
        """
        Get document language.
        
        Returns:
            Document language
        """
        return self.language
    
    def get_all_properties(self) -> Dict[str, Any]:
        """
        Get all core properties.
        
        Returns:
            Dictionary with all core properties
        """
        return {
            'title': self.title,
            'author': self.author,
            'created': self.created,
            'modified': self.modified,
            'subject': self.subject,
            'keywords': self.keywords,
            'category': self.category,
            'version': self.version,
            'language': self.language
        }
    
    def validate(self) -> bool:
        """
        Validate core properties.
        
        Returns:
            True if core properties are valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate required fields
        if not self.title or not isinstance(self.title, str):
            self.validation_errors.append("Title is required and must be a string")
        
        if not self.author or not isinstance(self.author, str):
            self.validation_errors.append("Author is required and must be a string")
        
        if not isinstance(self.created, datetime):
            self.validation_errors.append("Created date must be a datetime object")
        
        if not isinstance(self.modified, datetime):
            self.validation_errors.append("Modified date must be a datetime object")
        
        # Validate optional fields
        if not isinstance(self.subject, str):
            self.validation_errors.append("Subject must be a string")
        
        if not isinstance(self.keywords, str):
            self.validation_errors.append("Keywords must be a string")
        
        if not isinstance(self.category, str):
            self.validation_errors.append("Category must be a string")
        
        if not isinstance(self.version, str):
            self.validation_errors.append("Version must be a string")
        
        if not isinstance(self.language, str):
            self.validation_errors.append("Language must be a string")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Core properties validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def get_core_properties_stats(self) -> Dict[str, int]:
        """
        Get core properties statistics.
        
        Returns:
            Dictionary with core properties statistics
        """
        return self.core_properties_stats.copy()
    
    def get_core_properties_info(self) -> Dict[str, Any]:
        """
        Get core properties information.
        
        Returns:
            Dictionary with core properties information
        """
        return {
            'title': self.title,
            'author': self.author,
            'created': self.created.isoformat() if self.created else None,
            'modified': self.modified.isoformat() if self.modified else None,
            'subject': self.subject,
            'keywords': self.keywords,
            'category': self.category,
            'version': self.version,
            'language': self.language,
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.core_properties_stats.copy()
        }
    
    def clear_core_properties(self) -> None:
        """Clear all core properties."""
        self.title = "Untitled Document"
        self.author = "Unknown"
        self.created = datetime.now()
        self.modified = datetime.now()
        self.subject = ""
        self.keywords = ""
        self.category = ""
        self.version = "1.0"
        self.language = "en-US"
        self.validation_errors.clear()
        logger.debug("Core properties cleared")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert core properties to dictionary.
        
        Returns:
            Dictionary with all core properties
        """
        return {
            'title': self.title,
            'author': self.author,
            'created': self.created.isoformat() if self.created else None,
            'modified': self.modified.isoformat() if self.modified else None,
            'subject': self.subject,
            'keywords': self.keywords,
            'category': self.category,
            'version': self.version,
            'language': self.language,
            'validation_errors': self.validation_errors.copy(),
            'core_properties_stats': self.core_properties_stats.copy()
        }
    
    def get_core_properties_summary(self) -> Dict[str, Any]:
        """
        Get core properties summary.
        
        Returns:
            Dictionary with core properties summary
        """
        return {
            'total_properties': self.core_properties_stats['total_properties'],
            'required_properties': self.core_properties_stats['required_properties'],
            'optional_properties': self.core_properties_stats['optional_properties'],
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.core_properties_stats.copy()
        }
