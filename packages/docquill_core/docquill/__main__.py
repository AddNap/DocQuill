"""
Entry point for running DocQuill as a module.

Usage:
    python -m docquill input.docx --output output.html --format html
    docquill input.docx --output output.pdf --format pdf
"""

from .cli import main

if __name__ == "__main__":
    main()
