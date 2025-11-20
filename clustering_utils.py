"""
Clustering and Label Filtering - Single Source of Truth
========================================================

REFACTORED: Now imports from shared app.field_extraction.processing module
instead of copying code.

Functions:
- cluster_words_by_position: Group words spatially by position
- filter_labels: Remove label words from value words
"""

# Import from shared modules (single source of truth)
from app.field_extraction.processing import cluster_words_by_position
from app.field_extraction.processing.cleaners import filter_labels

# Re-export for backward compatibility with zone builder imports
__all__ = ['cluster_words_by_position', 'filter_labels']
