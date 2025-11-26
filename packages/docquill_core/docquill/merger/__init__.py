"""
Document Merger module - advanced merging of DOCX documents.
"""

# DocumentMerger and MergeOptions are in file docquill/merger.py
# We import them directly from file, bypassing conflict with directory
import sys
import importlib.util
from pathlib import Path

# Find merger.py file in parent directory
merger_file = Path(__file__).parent.parent / 'merger.py'
if merger_file.exists():
    spec = importlib.util.spec_from_file_location("docquill.merger_module", merger_file)
    merger_module = importlib.util.module_from_spec(spec)
    # Set parent package for relative imports
    merger_module.__package__ = 'docquill'
    sys.modules['docquill.merger_module'] = merger_module
    spec.loader.exec_module(merger_module)
    DocumentMerger = getattr(merger_module, 'DocumentMerger', None)
    MergeOptions = getattr(merger_module, 'MergeOptions', None)
else:
    DocumentMerger = None
    MergeOptions = None

try:
    from .relationship_merger import RelationshipMerger
except ImportError:
    RelationshipMerger = None

__all__ = [
    "RelationshipMerger",
]

if DocumentMerger is not None:
    __all__.append("DocumentMerger")
if MergeOptions is not None:
    __all__.append("MergeOptions")
