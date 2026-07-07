"""exact: a linter that recognizes magic float constants and suggests exact forms.

Scans Python source for float literals like 0.017453292519943295, recognizes
them (that one is pi/180) via a curated table, a rational check, and a PSLQ
integer-relation search, and suggests readable exact replacements.
"""

from .extract import FloatLiteral, extract_file, extract_source
from .recognize import Match, recognize
from .report import Finding

__version__ = "0.2.0"

__all__ = [
    "FloatLiteral",
    "Match",
    "Finding",
    "extract_file",
    "extract_source",
    "recognize",
    "__version__",
]
