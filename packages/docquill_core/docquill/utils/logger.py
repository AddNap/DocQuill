"""
Logger for DOCX documents.

Handles logger functionality, logging configuration, log levels, log formatting, and log output.
"""

import logging
from typing import Optional, Dict, Any
import sys
import os
from datetime import datetime

def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance for module.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    if not name or not isinstance(name, str):
        raise ValueError("Logger name must be a non-empty string")
    
    logger = logging.getLogger(name)
    
    # Set default level if not configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger

def configure_logging(level: str = "INFO", format_string: Optional[str] = None, 
                     log_file: Optional[str] = None, max_file_size: int = 10 * 1024 * 1024,
                     backup_count: int = 5) -> None:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string
        log_file: Log file path
        max_file_size: Maximum log file size in bytes
        backup_count: Number of backup files to keep
    """
    if level.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        raise ValueError(f"Invalid log level: {level}")
    
    # Set root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    if format_string:
        formatter = logging.Formatter(format_string)
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        add_file_handler(root_logger, log_file, level, formatter, max_file_size, backup_count)

def set_log_level(level: str) -> None:
    """
    Set log level.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if level.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        raise ValueError(f"Invalid log level: {level}")
    
    # Set root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Update all handlers
    for handler in root_logger.handlers:
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))

def add_file_handler(logger: logging.Logger, file_path: str, level: str = "INFO",
                    formatter: Optional[logging.Formatter] = None,
                    max_file_size: int = 10 * 1024 * 1024, backup_count: int = 5) -> None:
    """
    Add file handler to logger.
    
    Args:
        logger: Logger instance
        file_path: Log file path
        level: Log level for this handler
        formatter: Log formatter
        max_file_size: Maximum log file size in bytes
        backup_count: Number of backup files to keep
    """
    if not isinstance(logger, logging.Logger):
        raise ValueError("Logger must be a logging.Logger instance")
    
    if not file_path or not isinstance(file_path, str):
        raise ValueError("File path must be a non-empty string")
    
    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Use RotatingFileHandler for log rotation
    from logging.handlers import RotatingFileHandler
    
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=max_file_size,
        backupCount=backup_count
    )
    file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Set formatter
    if formatter:
        file_handler.setFormatter(formatter)
    else:
        default_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(default_formatter)
    
    logger.addHandler(file_handler)

def remove_file_handler(logger: logging.Logger, file_path: str) -> bool:
    """
    Remove file handler from logger.
    
    Args:
        logger: Logger instance
        file_path: Log file path to remove
        
    Returns:
        True if handler was removed, False if not found
    """
    if not isinstance(logger, logging.Logger):
        raise ValueError("Logger must be a logging.Logger instance")
    
    if not file_path or not isinstance(file_path, str):
        raise ValueError("File path must be a non-empty string")
    
    # Find and remove file handler
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == file_path:
            logger.removeHandler(handler)
            return True
    
    return False

def get_logger_info(logger: logging.Logger) -> Dict[str, Any]:
    """
    Get logger information.
    
    Args:
        logger: Logger instance
        
    Returns:
        Dictionary with logger information
    """
    if not isinstance(logger, logging.Logger):
        raise ValueError("Logger must be a logging.Logger instance")
    
    return {
        'name': logger.name,
        'level': logging.getLevelName(logger.getEffectiveLevel()),
        'effective_level': logger.getEffectiveLevel(),
        'handlers_count': len(logger.handlers),
        'handlers': [type(h).__name__ for h in logger.handlers],
        'propagate': logger.propagate
    }

def create_child_logger(parent_logger: logging.Logger, name: str) -> logging.Logger:
    """
    Create child logger.
    
    Args:
        parent_logger: Parent logger instance
        name: Child logger name
        
    Returns:
        Child logger instance
    """
    if not isinstance(parent_logger, logging.Logger):
        raise ValueError("Parent logger must be a logging.Logger instance")
    
    if not name or not isinstance(name, str):
        raise ValueError("Child logger name must be a non-empty string")
    
    child_name = f"{parent_logger.name}.{name}"
    child_logger = logging.getLogger(child_name)
    
    # Set level to parent's level
    child_logger.setLevel(parent_logger.getEffectiveLevel())
    
    return child_logger

def clear_handlers(logger: logging.Logger) -> None:
    """
    Clear all handlers from logger.
    
    Args:
        logger: Logger instance
    """
    if not isinstance(logger, logging.Logger):
        raise ValueError("Logger must be a logging.Logger instance")
    
    for handler in logger.handlers:
        logger.removeHandler(handler)

def set_formatter(logger: logging.Logger, formatter: logging.Formatter) -> None:
    """
    Set formatter for all handlers.
    
    Args:
        logger: Logger instance
        formatter: Log formatter
    """
    if not isinstance(logger, logging.Logger):
        raise ValueError("Logger must be a logging.Logger instance")
    
    if not isinstance(formatter, logging.Formatter):
        raise ValueError("Formatter must be a logging.Formatter instance")
    
    for handler in logger.handlers:
        handler.setFormatter(formatter)

def get_effective_level(logger: logging.Logger) -> int:
    """
    Get effective log level.
    
    Args:
        logger: Logger instance
        
    Returns:
        Effective log level
    """
    if not isinstance(logger, logging.Logger):
        raise ValueError("Logger must be a logging.Logger instance")
    
    return logger.getEffectiveLevel()

def is_enabled_for(logger: logging.Logger, level: str) -> bool:
    """
    Check if logger is enabled for level.
    
    Args:
        logger: Logger instance
        level: Log level to check
        
    Returns:
        True if enabled, False otherwise
    """
    if not isinstance(logger, logging.Logger):
        raise ValueError("Logger must be a logging.Logger instance")
    
    if level.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        raise ValueError(f"Invalid log level: {level}")
    
    return logger.isEnabledFor(getattr(logging, level.upper(), logging.INFO))

def create_formatter(format_string: str, date_format: str = '%Y-%m-%d %H:%M:%S') -> logging.Formatter:
    """
    Create log formatter.
    
    Args:
        format_string: Format string
        date_format: Date format string
        
    Returns:
        Log formatter
    """
    if not format_string or not isinstance(format_string, str):
        raise ValueError("Format string must be a non-empty string")
    
    if not date_format or not isinstance(date_format, str):
        raise ValueError("Date format must be a non-empty string")
    
    return logging.Formatter(format_string, date_format)

def get_default_formatter() -> logging.Formatter:
    """
    Get default formatter.
    
    Returns:
        Default log formatter
    """
    return logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
