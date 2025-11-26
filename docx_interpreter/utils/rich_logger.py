"""
Rich logging for DOCX documents.

Provides modern, colorful logging using the rich library.
"""

import logging
import sys
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.traceback import install
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: rich library not available. Falling back to standard logging.")

# Install rich traceback handler
if RICH_AVAILABLE:
    install()


class RichLogger:
    """
    Modern logging with rich formatting and colors.
    """
    
    def __init__(self, name: str = "docx_interpreter", level: str = "INFO"):
        """
        Initialize rich logger.
        
        Args:
            name: Logger name
            level: Log level
        """
        self.name = name
        self.level = level
        self.console = Console() if RICH_AVAILABLE else None
        
        # Setup logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        if RICH_AVAILABLE:
            self._setup_rich_handler()
        else:
            self._setup_standard_handler()
    
    def _setup_rich_handler(self):
        """Setup rich handler."""
        # Create rich handler
        rich_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_path=True,
            markup=True,
            rich_tracebacks=True
        )
        
        # Create formatter
        formatter = logging.Formatter(
            fmt="%(message)s",
            datefmt="[%X]"
        )
        
        rich_handler.setFormatter(formatter)
        self.logger.addHandler(rich_handler)
    
    def _setup_standard_handler(self):
        """Setup standard handler as fallback."""
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.logger.critical(message, **kwargs)
    
    def success(self, message: str):
        """Log success message with rich formatting."""
        if RICH_AVAILABLE:
            self.console.print(f"[green]✓ {message}[/green]")
        else:
            self.logger.info(f"✓ {message}")
    
    def failure(self, message: str):
        """Log failure message with rich formatting."""
        if RICH_AVAILABLE:
            self.console.print(f"[red]✗ {message}[/red]")
        else:
            self.logger.error(f"✗ {message}")
    
    def progress(self, message: str, total: Optional[int] = None):
        """Create progress indicator."""
        if RICH_AVAILABLE:
            if total:
                return Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console
                )
            else:
                self.console.print(f"[yellow]⏳ {message}[/yellow]")
        else:
            self.logger.info(f"⏳ {message}")
    
    def panel(self, title: str, content: str, style: str = "blue"):
        """Display content in a rich panel."""
        if RICH_AVAILABLE:
            panel = Panel(content, title=title, style=style)
            self.console.print(panel)
        else:
            self.logger.info(f"{title}: {content}")
    
    def table(self, title: str, data: Dict[str, Any]):
        """Display data in a rich table."""
        if RICH_AVAILABLE:
            table = Table(title=title)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="magenta")
            
            for key, value in data.items():
                table.add_row(str(key), str(value))
            
            self.console.print(table)
        else:
            self.logger.info(f"{title}:")
            for key, value in data.items():
                self.logger.info(f"  {key}: {value}")
    
    def traceback(self, exc_info):
        """Display rich traceback."""
        if RICH_AVAILABLE:
            self.console.print_exception()
        else:
            import traceback
            traceback.print_exception(*exc_info)


def get_rich_logger(name: str = "docx_interpreter", level: str = "INFO") -> RichLogger:
    """
    Get rich logger instance.
    
    Args:
        name: Logger name
        level: Log level
        
    Returns:
        RichLogger instance
    """
    return RichLogger(name, level)


def setup_logging(level: str = "INFO", use_rich: bool = True):
    """
    Setup logging for the application.
    
    Args:
        level: Log level
        use_rich: Whether to use rich logging
    """
    if use_rich and RICH_AVAILABLE:
        # Setup rich logging
        console = Console()
        
        # Create rich handler
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            markup=True,
            rich_tracebacks=True
        )
        
        # Create formatter
        formatter = logging.Formatter(
            fmt="%(message)s",
            datefmt="[%X]"
        )
        
        rich_handler.setFormatter(formatter)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        root_logger.handlers.clear()
        root_logger.addHandler(rich_handler)
        
        # Log startup message
        console.print(f"[green]✓ Rich logging initialized at {level} level[/green]")
        
    else:
        # Setup standard logging
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        logger = logging.getLogger(__name__)
        logger.info(f"Standard logging initialized at {level} level")


def create_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Create a logger with rich formatting.
    
    Args:
        name: Logger name
        level: Log level
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if RICH_AVAILABLE:
        # Create rich handler
        console = Console()
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            markup=True,
            rich_tracebacks=True
        )
        
        # Create formatter
        formatter = logging.Formatter(
            fmt="%(message)s",
            datefmt="[%X]"
        )
        
        rich_handler.setFormatter(formatter)
        logger.addHandler(rich_handler)
    
    return logger


# Global rich logger instance
rich_logger = get_rich_logger() if RICH_AVAILABLE else None
