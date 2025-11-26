"""
Document Merger module - zaawansowane scalanie dokumentów DOCX z obsługą relacji OPC.
"""

# DocumentMerger i MergeOptions są w pliku docx_interpreter/merger.py
# Importujemy je bezpośrednio z pliku, omijając konflikt z katalogiem
import sys
import importlib.util
from pathlib import Path

# Znajdź plik merger.py w parent directory
merger_file = Path(__file__).parent.parent / 'merger.py'
if merger_file.exists():
    spec = importlib.util.spec_from_file_location("docx_interpreter.merger_module", merger_file)
    merger_module = importlib.util.module_from_spec(spec)
    # Ustaw parent package dla relative imports
    merger_module.__package__ = 'docx_interpreter'
    sys.modules['docx_interpreter.merger_module'] = merger_module
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

