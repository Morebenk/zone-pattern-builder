"""
Standalone clustering and label filtering utilities
====================================================

Copied from app/field_extraction/processing/ to make zone_builder independent.
This prevents triggering template registration when zone_builder loads.

Functions:
- cluster_words_by_position: Group words spatially by position
- filter_labels: Remove label words from value words
"""

import re
from typing import Any, Dict, List, Optional

# Pre-compiled regex patterns for performance
_PATTERN_PUNCTUATION = re.compile(r'[:.-]')
_PATTERN_PUNCTUATION_END = re.compile(r'[:.-]$')
_PATTERN_ALPHANUMERIC = re.compile(r'[a-zA-Z0-9]')
_PATTERN_DATE = re.compile(r'\d+[/-]\d+[/-]\d+')
_PATTERN_LEADING_TRAILING_PUNCT = re.compile(r'^[\s:,\-\(\)]+|[\s:,\-\)]+$')


def cluster_words_by_position(
    words: List[Dict[str, Any]],
    axis: str = 'y',
    tolerance: float = 0.02
) -> List[List[Dict[str, Any]]]:
    """
    Cluster words by spatial proximity along X or Y axis.

    Args:
        words: List of word dictionaries with geometry
        axis: 'y' for horizontal clustering (same line), 'x' for vertical clustering (same column)
        tolerance: Maximum distance between words in same cluster (normalized 0-1)
                  Can be 'auto' to calculate adaptive tolerance based on word sizes

    Returns:
        List of word clusters, sorted by position (top-to-bottom for Y, left-to-right for X)
    """
    if not words:
        return []

    # Extract positions and calculate adaptive tolerance if needed
    positions = []
    for word in words:
        geom = word.get('parsed', {})
        pos = geom.get(f'center_{axis}', 0)
        positions.append((word, pos))

    # Calculate adaptive tolerance if set to 'auto'
    if tolerance == 'auto':
        # Calculate median word size along the clustering axis
        sizes = []
        for word in words:
            geom = word.get('parsed', {})
            if axis == 'y':
                size = geom.get('y2', 0) - geom.get('y1', 0)
            else:
                size = geom.get('x2', 0) - geom.get('x1', 0)
            if size > 0:
                sizes.append(size)

        if sizes:
            sizes.sort()
            median_size = sizes[len(sizes) // 2]
            # Tolerance = 1.5x median word size (accounts for spacing between lines/columns)
            tolerance = median_size * 1.5
        else:
            tolerance = 0.02  # Fallback to default

    positions.sort(key=lambda x: x[1])

    clusters = []
    current_cluster = [positions[0][0]]
    prev_pos = positions[0][1]  # Track previous word position, not first

    for i in range(1, len(positions)):
        word, pos = positions[i]
        # FIX: Compare to PREVIOUS word position, not first word in cluster
        if abs(pos - prev_pos) <= tolerance:
            current_cluster.append(word)
        else:
            # Start new cluster
            clusters.append(current_cluster)
            current_cluster = [word]

        # Update previous position for next iteration
        prev_pos = pos

    if current_cluster:
        clusters.append(current_cluster)

    return clusters


def is_label_by_case(text: str) -> bool:
    """
    Determine if text is a label based on case pattern (French ID specific).
    Labels: lowercase or Title Case (e.g., "nom", "Taille")
    Values: UPPERCASE (e.g., "PETE", "PARIS")

    NOTE: Only works for French IDs where labels are lowercase/Title case
    """
    if not text or not text.isalpha() or len(text) <= 3:
        return False

    if text.islower():
        return True

    if text[0].isupper():
        rest = text[1:]
        return rest and any(c.islower() for c in rest) and not any(c.isupper() for c in rest)

    return False


def detect_label_universal(text: str, field_type: str = None) -> int:
    """
    Universal label detection using ONLY generic heuristics (no template-specific keywords).
    Template-specific label patterns should be passed via label_patterns parameter.

    Generic heuristics:
    - Case patterns (lowercase/Title case = label for French-style documents)
    - Punctuation patterns (colons, short codes with punctuation)
    - Non-alphanumeric separators
    - Field type context (reduce score if looks like a value)

    Args:
        text: Word text to analyze
        field_type: Optional hint about expected field type (name, date, etc.)

    Returns:
        Label score (0-10). Threshold: >= 5 = label, < 5 = value
    """
    if not text:
        return 10  # Empty = label

    score = 0

    # 1. French-style case detection (lowercase/Title = label, UPPERCASE = value)
    if is_label_by_case(text):
        score += 3  # Moderate confidence for French-style labels

    # 2. Short text with punctuation (e.g., "SEX:", "DOB:", "LN:")
    if len(text) <= 5 and _PATTERN_PUNCTUATION.search(text):
        score += 3

    # 3. Punctuation at end (common in labels)
    if _PATTERN_PUNCTUATION_END.search(text):
        score += 2

    # 4. Contains only non-alphanumeric (e.g., ":", "-", "/")
    if not _PATTERN_ALPHANUMERIC.search(text):
        score += 5  # Definitely a label separator

    # 5. Very short alphabetic text (1-3 letters) without context
    # Could be abbreviations like "LN", "FN", "DD" - weak indicator
    if len(text) <= 3 and text.isalpha() and not field_type:
        score += 1

    # 6. Field type specific checks (reduce score if looks like a value for this field)
    if field_type == 'name' and text.isupper() and len(text) > 3 and text.isalpha():
        # Long uppercase alphabetic = likely a name value, not a label
        score -= 2
    elif field_type == 'date' and _PATTERN_DATE.search(text):
        # Date pattern = definitely a value
        score -= 5

    return max(0, score)  # Clamp to 0 minimum


def filter_labels(words: List[Dict[str, Any]], label_patterns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Universal label filtering using multiple detection strategies.
    Works for French IDs (lowercase labels), US licenses (keyword-based), and more.

    Args:
        words: List of word dictionaries with 'text' key
        label_patterns: Optional regex patterns to identify labels (e.g., [r'^(sex|dob|ln)'])

    Returns:
        Filtered list with label words removed
    """
    if not words:
        return []

    # Handle None label_patterns gracefully
    if label_patterns is None:
        label_patterns = []

    filtered = []

    for word in words:
        text = word.get('text', '').strip()

        # Skip empty or punctuation-only
        if not text or (len(text) == 1 and text in ':,-.()/'):
            continue

        # Check against provided label patterns
        if label_patterns and any(re.match(pattern, text, re.IGNORECASE) for pattern in label_patterns):
            continue  # Skip this word (it's a label)

        # Universal label detection
        label_score = detect_label_universal(text)
        if label_score >= 5:  # Threshold: >= 5 = label
            continue  # Skip this word (it's a label)

        # Clean any remaining label prefixes (generic cleanup)
        # Remove common label patterns like "Label:" or "Label :"
        cleaned = text
        if ':' in text:
            # If text has colon, try to extract the part after it
            # E.g., "LN: SMITH" -> "SMITH", "SEX: M" -> "M"
            parts = text.split(':', 1)
            if len(parts) == 2 and parts[1].strip():
                cleaned = parts[1].strip()
            else:
                cleaned = text

        # Remove leading/trailing punctuation
        cleaned = _PATTERN_LEADING_TRAILING_PUNCT.sub('', cleaned)

        # Only keep if has alphanumeric content
        if cleaned and _PATTERN_ALPHANUMERIC.search(cleaned):
            word_copy = word.copy()
            word_copy['text'] = cleaned
            filtered.append(word_copy)

    return filtered
