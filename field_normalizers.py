"""
Field Normalization - Single Source of Truth
==============================================

REFACTORED: Now imports from shared app.field_extraction.processing module
instead of replicating logic.

This ensures the zone builder shows the exact same output as the main OCR system.
"""

from typing import Optional

# Import from shared modules (single source of truth)
from app.field_extraction.processing import (
    normalize_date,
    normalize_height,
    normalize_weight,
    normalize_sex,
    normalize_eye_color,
    normalize_hair_color,
    normalize_endorsements,
    normalize_restrictions,
    clean_name_field,
    clean_address_field
)


def normalize_field(value: str, field_format: str, field_name: Optional[str] = None, **format_options) -> Optional[str]:
    """
    Normalize field value based on format type

    This matches the logic in HybridTemplate._normalize_field()

    Args:
        value: Raw extracted text
        field_format: Format type (date, height, weight, sex, eyes, hair, endorsements, restrictions, etc.)
        field_name: Optional field name for context
        **format_options: Format-specific options (e.g., date_format='MM.DD.YYYY', height_format='us')

    Returns:
        Normalized value or None if invalid
    """
    if not value:
        return None

    # Format-specific normalization
    if field_format == 'date':
        date_format = format_options.get('date_format', 'DD.MM.YYYY')
        return normalize_date(value, date_format)
    elif field_format == 'height':
        height_format = format_options.get('height_format', 'auto')
        return normalize_height(value, height_format)
    elif field_format == 'weight':
        weight_format = format_options.get('weight_format', 'auto')
        return normalize_weight(value, weight_format)
    elif field_format == 'sex':
        return normalize_sex(value)
    elif field_format == 'eyes':
        return normalize_eye_color(value)
    elif field_format == 'hair':
        return normalize_hair_color(value)
    elif field_format == 'endorsements':
        return normalize_endorsements(value)
    elif field_format == 'restrictions':
        return normalize_restrictions(value)

    # Field-specific cleaning (ALWAYS apply, regardless of format)
    # This matches HybridTemplate._apply_format logic
    if field_name and any(name_field in field_name for name_field in ['first_name', 'last_name', 'middle_name']):
        return clean_name_field(value)

    if field_name and 'address' in field_name:
        return clean_address_field(value)

    # No normalization for other formats (string, number, etc.)
    return value
