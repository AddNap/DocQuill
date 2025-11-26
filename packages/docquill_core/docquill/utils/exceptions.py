"""
Exceptions for DOCX documents.

Handles exception classes, custom exception hierarchy, exception handling, error messages, and exception chaining.
"""

from typing import Optional, Any, Dict, List
import traceback
import sys

class DocumentError(Exception):
    """
    Base exception for document-related errors.
    
    Handles document error functionality, error handling, and error messages.
    """
    
    def __init__(self, message: str, cause: Optional[Exception] = None, 
                 error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize document error.
        
        Args:
            message: Error message
            cause: Causing exception
            error_code: Error code
            details: Additional details
        """
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.error_code = error_code
        self.details = details or {}
        self.traceback = traceback.format_exc()
    
    def get_error_info(self) -> Dict[str, Any]:
        """
        Get error information.
        
        Returns:
            Dictionary with error information
        """
        return {
            'message': self.message,
            'cause': str(self.cause) if self.cause else None,
            'error_code': self.error_code,
            'details': self.details,
            'traceback': self.traceback
        }
    
    def __str__(self) -> str:
        """String representation of exception."""
        return f"{self.__class__.__name__}: {self.message}"

class ParsingError(DocumentError):
    """
    Exception for parsing-related errors.
    
    Handles parsing error functionality, parsing error handling, and parsing error messages.
    """
    
    def __init__(self, message: str, file_path: Optional[str] = None, 
                 line_number: Optional[int] = None, column_number: Optional[int] = None,
                 cause: Optional[Exception] = None, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize parsing error.
        
        Args:
            message: Error message
            file_path: File path where error occurred
            line_number: Line number where error occurred
            column_number: Column number where error occurred
            cause: Causing exception
            error_code: Error code
            details: Additional details
        """
        super().__init__(message, cause, error_code, details)
        self.file_path = file_path
        self.line_number = line_number
        self.column_number = column_number
    
    def get_error_info(self) -> Dict[str, Any]:
        """
        Get error information.
        
        Returns:
            Dictionary with error information
        """
        info = super().get_error_info()
        info.update({
            'file_path': self.file_path,
            'line_number': self.line_number,
            'column_number': self.column_number
        })
        return info

class PackageError(DocumentError):
    """
    Exception for package-related errors.
    
    Handles package error functionality, package error handling, and package error messages.
    """
    
    def __init__(self, message: str, package_path: Optional[str] = None,
                 package_size: Optional[int] = None, package_format: Optional[str] = None,
                 cause: Optional[Exception] = None, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize package error.
        
        Args:
            message: Error message
            package_path: Path of package causing error
            package_size: Size of package causing error
            package_format: Format of package causing error
            cause: Causing exception
            error_code: Error code
            details: Additional details
        """
        super().__init__(message, cause, error_code, details)
        self.package_path = package_path
        self.package_size = package_size
        self.package_format = package_format
    
    def get_error_info(self) -> Dict[str, Any]:
        """
        Get error information.
        
        Returns:
            Dictionary with error information
        """
        info = super().get_error_info()
        info.update({
            'package_path': self.package_path,
            'package_size': self.package_size,
            'package_format': self.package_format
        })
        return info

class RelationshipError(DocumentError):
    """
    Exception for relationship-related errors.
    
    Handles relationship error functionality, relationship error handling, and relationship error messages.
    """
    
    def __init__(self, message: str, relationship_id: Optional[str] = None,
                 relationship_type: Optional[str] = None, target_path: Optional[str] = None,
                 cause: Optional[Exception] = None, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize relationship error.
        
        Args:
            message: Error message
            relationship_id: ID of relationship causing error
            relationship_type: Type of relationship causing error
            target_path: Target path of relationship causing error
            cause: Causing exception
            error_code: Error code
            details: Additional details
        """
        super().__init__(message, cause, error_code, details)
        self.relationship_id = relationship_id
        self.relationship_type = relationship_type
        self.target_path = target_path
    
    def get_error_info(self) -> Dict[str, Any]:
        """
        Get error information.
        
        Returns:
            Dictionary with error information
        """
        info = super().get_error_info()
        info.update({
            'relationship_id': self.relationship_id,
            'relationship_type': self.relationship_type,
            'target_path': self.target_path
        })
        return info

class SectionParsingError(ParsingError):
    """
    Exception for section parsing errors.
    
    Handles section parsing error functionality, section parsing error handling, and section parsing error messages.
    """
    
    def __init__(self, message: str, section_number: Optional[int] = None,
                 section_type: Optional[str] = None, section_properties: Optional[Dict[str, Any]] = None,
                 file_path: Optional[str] = None, line_number: Optional[int] = None, 
                 column_number: Optional[int] = None, cause: Optional[Exception] = None, 
                 error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize section parsing error.
        
        Args:
            message: Error message
            section_number: Number of section causing error
            section_type: Type of section causing error
            section_properties: Properties of section causing error
            file_path: File path where error occurred
            line_number: Line number where error occurred
            column_number: Column number where error occurred
            cause: Causing exception
            error_code: Error code
            details: Additional details
        """
        super().__init__(message, file_path, line_number, column_number, cause, error_code, details)
        self.section_number = section_number
        self.section_type = section_type
        self.section_properties = section_properties or {}
    
    def get_error_info(self) -> Dict[str, Any]:
        """
        Get error information.
        
        Returns:
            Dictionary with error information
        """
        info = super().get_error_info()
        info.update({
            'section_number': self.section_number,
            'section_type': self.section_type,
            'section_properties': self.section_properties
        })
        return info

class ValidationError(DocumentError):
    """
    Exception for validation errors.
    
    Handles validation error functionality, validation error handling, and validation error messages.
    """
    
    def __init__(self, message: str, field_name: Optional[str] = None,
                 field_value: Optional[Any] = None, validation_rule: Optional[str] = None,
                 cause: Optional[Exception] = None, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            field_name: Name of field causing error
            field_value: Value of field causing error
            validation_rule: Validation rule that failed
            cause: Causing exception
            error_code: Error code
            details: Additional details
        """
        super().__init__(message, cause, error_code, details)
        self.field_name = field_name
        self.field_value = field_value
        self.validation_rule = validation_rule
    
    def get_error_info(self) -> Dict[str, Any]:
        """
        Get error information.
        
        Returns:
            Dictionary with error information
        """
        info = super().get_error_info()
        info.update({
            'field_name': self.field_name,
            'field_value': self.field_value,
            'validation_rule': self.validation_rule
        })
        return info

class LayoutError(DocumentError):
    """
    Exception for layout errors.
    
    Handles layout error functionality, layout error handling, and layout error messages.
    """
    
    def __init__(self, message: str, element_type: Optional[str] = None,
                 element_id: Optional[str] = None, page_number: Optional[int] = None,
                 cause: Optional[Exception] = None, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize layout error.
        
        Args:
            message: Error message
            element_type: Type of element causing error
            element_id: ID of element causing error
            page_number: Page number where error occurred
            cause: Causing exception
            error_code: Error code
            details: Additional details
        """
        super().__init__(message, cause, error_code, details)
        self.element_type = element_type
        self.element_id = element_id
        self.page_number = page_number
    
    def get_error_info(self) -> Dict[str, Any]:
        """
        Get error information.
        
        Returns:
            Dictionary with error information
        """
        info = super().get_error_info()
        info.update({
            'element_type': self.element_type,
            'element_id': self.element_id,
            'page_number': self.page_number
        })
        return info

class RenderError(DocumentError):
    """
    Exception for rendering errors.
    
    Handles render error functionality, render error handling, and render error messages.
    """
    
    def __init__(self, message: str, render_type: Optional[str] = None,
                 output_path: Optional[str] = None, render_engine: Optional[str] = None,
                 cause: Optional[Exception] = None, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize render error.
        
        Args:
            message: Error message
            render_type: Type of rendering causing error
            output_path: Output path where error occurred
            render_engine: Rendering engine causing error
            cause: Causing exception
            error_code: Error code
            details: Additional details
        """
        super().__init__(message, cause, error_code, details)
        self.render_type = render_type
        self.output_path = output_path
        self.render_engine = render_engine
    
    def get_error_info(self) -> Dict[str, Any]:
        """
        Get error information.
        
        Returns:
            Dictionary with error information
        """
        info = super().get_error_info()
        info.update({
            'render_type': self.render_type,
            'output_path': self.output_path,
            'render_engine': self.render_engine
        })
        return info

def handle_exception(exception: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Handle exception and return error information.
    
    Args:
        exception: Exception to handle
        context: Additional context
        
    Returns:
        Dictionary with error information
    """
    if isinstance(exception, DocumentError):
        error_info = exception.get_error_info()
    else:
        error_info = {
            'message': str(exception),
            'error_code': None,
            'details': {},
            'cause': None,
            'traceback': traceback.format_exc()
        }
    
    if context:
        error_info['context'] = context
    
    return error_info

def create_exception(exception_type: str, message: str, **kwargs) -> DocumentError:
    """
    Create exception of specified type.
    
    Args:
        exception_type: Type of exception to create
        message: Exception message
        **kwargs: Additional arguments
        
    Returns:
        Exception instance
    """
    exception_classes = {
        'DocumentError': DocumentError,
        'ParsingError': ParsingError,
        'PackageError': PackageError,
        'RelationshipError': RelationshipError,
        'SectionParsingError': SectionParsingError,
        'ValidationError': ValidationError,
        'LayoutError': LayoutError,
        'RenderError': RenderError
    }
    
    if exception_type not in exception_classes:
        raise ValueError(f"Unknown exception type: {exception_type}")
    
    exception_class = exception_classes[exception_type]
    return exception_class(message, **kwargs)

def get_exception_hierarchy() -> Dict[str, List[str]]:
    """
    Get exception hierarchy.
    
    Returns:
        Dictionary with exception hierarchy
    """
    return {
        'DocumentError': ['ParsingError', 'PackageError', 'RelationshipError', 'ValidationError', 'LayoutError', 'RenderError'],
        'ParsingError': ['SectionParsingError'],
        'PackageError': [],
        'RelationshipError': [],
        'SectionParsingError': [],
        'ValidationError': [],
        'LayoutError': [],
        'RenderError': []
    }
