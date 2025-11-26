"""
Entry point for running docx_interpreter as a module.

Usage:
    python -m docx_interpreter input.docx --output output.html --format html
"""

from .cli import main

if __name__ == "__main__":
    main()
