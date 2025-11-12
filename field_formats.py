"""
Field Format Definitions and UI Helpers
=========================================

Defines all supported field formats and their configuration options,
matching the template system exactly.
"""

from typing import Dict, List, Optional, Tuple


# ============================================================================
# FORMAT DEFINITIONS (matching app/field_extraction/hybrid_template.py)
# ============================================================================

FIELD_FORMATS = [
    'string',     # Default - no special processing
    'date',       # Date values with format specification
    'height',     # Height values (US/metric)
    'weight',     # Weight values (US/metric)
    'sex',        # Gender/sex values (M/F)
    'eyes',       # Eye color values (extracts as-is: BRO, BRN, BLU, BLUE, etc.)
    'hair',       # Hair color values (extracts as-is: BLK, BRO, BRN, BLN, etc.)
    'number',     # Numeric/code fields
]

# Date format options (matching app/field_extraction/processing/normalizers.py)
DATE_FORMATS = [
    'DD.MM.YYYY',   # European format with dots
    'MM.DD.YYYY',   # US format with dots
    'DD/MM/YYYY',   # European format with slashes
    'MM/DD/YYYY',   # US format with slashes
    'YYYY.MM.DD',   # ISO format with dots
    'YYYY-MM-DD',   # ISO format with hyphens
]

# Height format options
HEIGHT_FORMATS = [
    'us',       # US format: 5'08 (feet'inches)
    'metric',   # Metric format: 1,75m
    'auto',     # Auto-detect based on content
]

# Weight format options
WEIGHT_FORMATS = [
    'us',       # US format: 150lb
    'metric',   # Metric format: 68kg
    'auto',     # Auto-detect based on content
]


# ============================================================================
# FORMAT-SPECIFIC DEFAULTS
# ============================================================================

def get_format_defaults(field_format: str, field_name: str = "") -> Dict:
    """
    Get default configuration for a specific format type

    Returns dict with format-specific keys only (no pattern suggestions)
    """
    defaults = {}

    if field_format == 'date':
        defaults['date_format'] = 'MM.DD.YYYY'  # US default

    elif field_format == 'height':
        defaults['height_format'] = 'us'

    elif field_format == 'weight':
        defaults['weight_format'] = 'us'

    return defaults


def get_format_help_text(field_format: str) -> str:
    """Get help text explaining the format type"""
    help_texts = {
        'string': 'Default text format - no special processing',
        'date': 'Date values - automatically normalized to specified format',
        'height': 'Height values - normalized to US (5\'08) or metric (1,75m) format',
        'weight': 'Weight values - normalized to US (150lb) or metric (68kg) format',
        'sex': 'Gender/sex values - normalized to M or F',
        'eyes': 'Eye color values - extracts code as-is from document (BRO, BRN, BLU, etc.)',
        'hair': 'Hair color values - extracts code as-is from document (BLK, BRO, BRN, BLN, etc.)',
        'number': 'Numeric/code fields - uppercase alphanumeric',
    }
    return help_texts.get(field_format, '')


# ============================================================================
# VALIDATION PATTERN GENERATORS
# ============================================================================

def get_date_pattern(date_format: str) -> str:
    """Generate validation pattern for a specific date format"""
    if date_format.startswith('YYYY'):
        return r'^\d{4}[\.\/\-]\d{2}[\.\/\-]\d{2}$'
    else:  # DD or MM first
        return r'^\d{2}[\.\/\-]\d{2}[\.\/\-]\d{4}$'


def get_height_pattern(height_format: str) -> str:
    """Generate validation pattern for a specific height format"""
    if height_format == 'us':
        return r"^\d[']\d{2}\"?$"  # 5'08
    elif height_format == 'metric':
        return r'^\d[.,]\d{2}m?$'  # 1,75m
    else:  # auto
        return r"^(?:\d[']\d{2}|\d[.,]\d{2}m?)$"  # Both formats


def get_weight_pattern(weight_format: str) -> str:
    """Generate validation pattern for a specific weight format"""
    if weight_format == 'us':
        return r'^\d{2,3}lb$'  # 150lb
    elif weight_format == 'metric':
        return r'^\d{2,3}kg$'  # 68kg
    else:  # auto
        return r'^\d{2,3}(?:lb|kg)$'  # Both formats


# ============================================================================
# AUTO-FORMAT DETECTION
# ============================================================================

def auto_detect_format(field_name: str) -> str:
    """
    Auto-detect format based on field name patterns

    Args:
        field_name: The name of the field

    Returns:
        Detected format type (date, height, weight, sex, eyes, hair, or string as default)

    Examples:
        auto_detect_format("date_of_birth") → "date"
        auto_detect_format("expiration_date") → "date"
        auto_detect_format("height") → "height"
        auto_detect_format("sex") → "sex"
        auto_detect_format("eyes") → "eyes"
        auto_detect_format("hair") → "hair"
        auto_detect_format("first_name") → "string"
    """
    field_lower = field_name.lower()

    # Date fields
    if 'date' in field_lower:
        return 'date'

    # Height fields
    if 'height' in field_lower or field_lower in ['hgt', 'ht']:
        return 'height'

    # Weight fields
    if 'weight' in field_lower or field_lower in ['wgt', 'wt']:
        return 'weight'

    # Sex/gender fields
    if field_lower in ['sex', 'gender']:
        return 'sex'

    # Eye color fields
    if 'eye' in field_lower or field_lower in ['eyes', 'eye_color', 'eye_colour']:
        return 'eyes'

    # Hair color fields
    if 'hair' in field_lower or field_lower in ['hair', 'hair_color', 'hair_colour']:
        return 'hair'

    # Number/code fields
    if any(keyword in field_lower for keyword in ['number', 'code', 'dl', 'license']):
        return 'number'

    # Default to string
    return 'string'


