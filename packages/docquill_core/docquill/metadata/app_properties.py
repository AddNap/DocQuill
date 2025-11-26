"""
Application properties for DOCX documents.

Handles app properties functionality, app properties parsing, app properties validation, app properties access, and app properties serialization.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class AppProperties:
    """
    Represents application-specific document properties.
    
    Handles app properties functionality, app properties parsing, app properties validation, and app properties access.
    """
    
    def __init__(self, application: str = "Microsoft Word", app_version: str = "16.0",
                 company: str = "", manager: str = "", security: str = "0",
                 template: str = "Normal.dotm", total_time: str = "0",
                 pages: str = "1", words: str = "0", characters: str = "0",
                 characters_with_spaces: str = "0", lines: str = "0", paragraphs: str = "0"):
        """
        Initialize app properties.
        
        Args:
            application: Application name
            app_version: Application version
            company: Company name
            manager: Manager name
            security: Security level
            template: Template name
            total_time: Total editing time
            pages: Page count
            words: Word count
            characters: Character count
            characters_with_spaces: Character count with spaces
            lines: Line count
            paragraphs: Paragraph count
        """
        self.application = application
        self.app_version = app_version
        self.company = company
        self.manager = manager
        self.security = security
        self.template = template
        self.total_time = total_time
        self.pages = pages
        self.words = words
        self.characters = characters
        self.characters_with_spaces = characters_with_spaces
        self.lines = lines
        self.paragraphs = paragraphs
        self.validation_errors = []
        self.app_properties_stats = {
            'total_properties': 12,
            'required_properties': 2,
            'optional_properties': 10
        }
        
        logger.debug("App properties initialized")
    
    def set_application(self, application: str) -> None:
        """
        Set application name.
        
        Args:
            application: Application name
        """
        if not isinstance(application, str):
            raise ValueError("Application must be a string")
        
        self.application = application
        logger.debug(f"Application set: {application}")
    
    def set_app_version(self, version: str) -> None:
        """
        Set application version.
        
        Args:
            version: Application version
        """
        if not isinstance(version, str):
            raise ValueError("Version must be a string")
        
        self.app_version = version
        logger.debug(f"Version set: {version}")
    
    def set_document_stats(self, stats: Dict[str, str]) -> None:
        """
        Set document statistics.
        
        Args:
            stats: Document statistics dictionary
        """
        if not isinstance(stats, dict):
            raise ValueError("Stats must be a dictionary")
        
        # Update individual stats
        if 'pages' in stats:
            self.pages = str(stats['pages'])
        if 'words' in stats:
            self.words = str(stats['words'])
        if 'characters' in stats:
            self.characters = str(stats['characters'])
        if 'characters_with_spaces' in stats:
            self.characters_with_spaces = str(stats['characters_with_spaces'])
        if 'lines' in stats:
            self.lines = str(stats['lines'])
        if 'paragraphs' in stats:
            self.paragraphs = str(stats['paragraphs'])
        
        logger.debug(f"Document stats set: {stats}")
    
    def set_security(self, security: str) -> None:
        """
        Set security properties.
        
        Args:
            security: Security level
        """
        if not isinstance(security, str):
            raise ValueError("Security must be a string")
        
        self.security = security
        logger.debug(f"Security set: {security}")
    
    def set_company(self, company: str) -> None:
        """
        Set company name.
        
        Args:
            company: Company name
        """
        if not isinstance(company, str):
            raise ValueError("Company must be a string")
        
        self.company = company
        logger.debug(f"Company set: {company}")
    
    def set_manager(self, manager: str) -> None:
        """
        Set manager name.
        
        Args:
            manager: Manager name
        """
        if not isinstance(manager, str):
            raise ValueError("Manager must be a string")
        
        self.manager = manager
        logger.debug(f"Manager set: {manager}")
    
    def set_template(self, template: str) -> None:
        """
        Set template name.
        
        Args:
            template: Template name
        """
        if not isinstance(template, str):
            raise ValueError("Template must be a string")
        
        self.template = template
        logger.debug(f"Template set: {template}")
    
    def set_total_time(self, total_time: str) -> None:
        """
        Set total editing time.
        
        Args:
            total_time: Total editing time
        """
        if not isinstance(total_time, str):
            raise ValueError("Total time must be a string")
        
        self.total_time = total_time
        logger.debug(f"Total time set: {total_time}")
    
    def get_application(self) -> str:
        """
        Get application name.
        
        Returns:
            Application name
        """
        return self.application
    
    def get_app_version(self) -> str:
        """
        Get application version.
        
        Returns:
            Application version
        """
        return self.app_version
    
    def get_company(self) -> str:
        """
        Get company name.
        
        Returns:
            Company name
        """
        return self.company
    
    def get_manager(self) -> str:
        """
        Get manager name.
        
        Returns:
            Manager name
        """
        return self.manager
    
    def get_security(self) -> str:
        """
        Get security level.
        
        Returns:
            Security level
        """
        return self.security
    
    def get_template(self) -> str:
        """
        Get template name.
        
        Returns:
            Template name
        """
        return self.template
    
    def get_total_time(self) -> str:
        """
        Get total editing time.
        
        Returns:
            Total editing time
        """
        return self.total_time
    
    def get_pages(self) -> str:
        """
        Get page count.
        
        Returns:
            Page count
        """
        return self.pages
    
    def get_words(self) -> str:
        """
        Get word count.
        
        Returns:
            Word count
        """
        return self.words
    
    def get_characters(self) -> str:
        """
        Get character count.
        
        Returns:
            Character count
        """
        return self.characters
    
    def get_characters_with_spaces(self) -> str:
        """
        Get character count with spaces.
        
        Returns:
            Character count with spaces
        """
        return self.characters_with_spaces
    
    def get_lines(self) -> str:
        """
        Get line count.
        
        Returns:
            Line count
        """
        return self.lines
    
    def get_paragraphs(self) -> str:
        """
        Get paragraph count.
        
        Returns:
            Paragraph count
        """
        return self.paragraphs
    
    def get_document_stats(self) -> Dict[str, str]:
        """
        Get document statistics.
        
        Returns:
            Dictionary with document statistics
        """
        return {
            'pages': self.pages,
            'words': self.words,
            'characters': self.characters,
            'characters_with_spaces': self.characters_with_spaces,
            'lines': self.lines,
            'paragraphs': self.paragraphs
        }
    
    def get_all_properties(self) -> Dict[str, str]:
        """
        Get all app properties.
        
        Returns:
            Dictionary with all app properties
        """
        return {
            'application': self.application,
            'app_version': self.app_version,
            'company': self.company,
            'manager': self.manager,
            'security': self.security,
            'template': self.template,
            'total_time': self.total_time,
            'pages': self.pages,
            'words': self.words,
            'characters': self.characters,
            'characters_with_spaces': self.characters_with_spaces,
            'lines': self.lines,
            'paragraphs': self.paragraphs
        }
    
    def validate(self) -> bool:
        """
        Validate app properties.
        
        Returns:
            True if app properties are valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate required fields
        if not self.application or not isinstance(self.application, str):
            self.validation_errors.append("Application is required and must be a string")
        
        if not self.app_version or not isinstance(self.app_version, str):
            self.validation_errors.append("App version is required and must be a string")
        
        # Validate optional fields
        if not isinstance(self.company, str):
            self.validation_errors.append("Company must be a string")
        
        if not isinstance(self.manager, str):
            self.validation_errors.append("Manager must be a string")
        
        if not isinstance(self.security, str):
            self.validation_errors.append("Security must be a string")
        
        if not isinstance(self.template, str):
            self.validation_errors.append("Template must be a string")
        
        if not isinstance(self.total_time, str):
            self.validation_errors.append("Total time must be a string")
        
        if not isinstance(self.pages, str):
            self.validation_errors.append("Pages must be a string")
        
        if not isinstance(self.words, str):
            self.validation_errors.append("Words must be a string")
        
        if not isinstance(self.characters, str):
            self.validation_errors.append("Characters must be a string")
        
        if not isinstance(self.characters_with_spaces, str):
            self.validation_errors.append("Characters with spaces must be a string")
        
        if not isinstance(self.lines, str):
            self.validation_errors.append("Lines must be a string")
        
        if not isinstance(self.paragraphs, str):
            self.validation_errors.append("Paragraphs must be a string")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"App properties validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def get_app_properties_stats(self) -> Dict[str, int]:
        """
        Get app properties statistics.
        
        Returns:
            Dictionary with app properties statistics
        """
        return self.app_properties_stats.copy()
    
    def get_app_properties_info(self) -> Dict[str, Any]:
        """
        Get app properties information.
        
        Returns:
            Dictionary with app properties information
        """
        return {
            'application': self.application,
            'app_version': self.app_version,
            'company': self.company,
            'manager': self.manager,
            'security': self.security,
            'template': self.template,
            'total_time': self.total_time,
            'pages': self.pages,
            'words': self.words,
            'characters': self.characters,
            'characters_with_spaces': self.characters_with_spaces,
            'lines': self.lines,
            'paragraphs': self.paragraphs,
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.app_properties_stats.copy()
        }
    
    def clear_app_properties(self) -> None:
        """Clear all app properties."""
        self.application = "Microsoft Word"
        self.app_version = "16.0"
        self.company = ""
        self.manager = ""
        self.security = "0"
        self.template = "Normal.dotm"
        self.total_time = "0"
        self.pages = "1"
        self.words = "0"
        self.characters = "0"
        self.characters_with_spaces = "0"
        self.lines = "0"
        self.paragraphs = "0"
        self.validation_errors.clear()
        logger.debug("App properties cleared")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert app properties to dictionary.
        
        Returns:
            Dictionary with all app properties
        """
        return {
            'application': self.application,
            'app_version': self.app_version,
            'company': self.company,
            'manager': self.manager,
            'security': self.security,
            'template': self.template,
            'total_time': self.total_time,
            'pages': self.pages,
            'words': self.words,
            'characters': self.characters,
            'characters_with_spaces': self.characters_with_spaces,
            'lines': self.lines,
            'paragraphs': self.paragraphs,
            'validation_errors': self.validation_errors.copy(),
            'app_properties_stats': self.app_properties_stats.copy()
        }
    
    def get_app_properties_summary(self) -> Dict[str, Any]:
        """
        Get app properties summary.
        
        Returns:
            Dictionary with app properties summary
        """
        return {
            'total_properties': self.app_properties_stats['total_properties'],
            'required_properties': self.app_properties_stats['required_properties'],
            'optional_properties': self.app_properties_stats['optional_properties'],
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.app_properties_stats.copy()
        }
