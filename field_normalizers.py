"""
Field Normalization - Simulating Field Extraction Logic
========================================================

This module replicates the exact normalization logic from the field extraction
system so the zone builder can show the actual final output that will be produced.
"""

import re
from typing import Optional


# ============================================================================
# DATE NORMALIZATION (from app/field_extraction/processing/normalizers.py)
# ============================================================================

def normalize_date(date_str: str, format: str = "DD.MM.YYYY") -> Optional[str]:
    """
    Normalize date to specified format - handles OCR errors

    Args:
        date_str: Raw date string from OCR
        format: Target format (DD.MM.YYYY, MM.DD.YYYY, YYYY.MM.DD, etc.)

    Returns:
        Normalized date in specified format, or None if invalid

    Examples:
        normalize_date("08/01/1988") → "08.01.1988"
        normalize_date("05/07/2025", "MM.DD.YYYY") → "05.07.2025"
    """
    if not date_str:
        return None

    # Fix common letter-digit confusions
    cleaned = date_str.replace('O', '0').replace('l', '1').replace('I', '1')

    # Extract ALL digits
    digits = ''.join(re.findall(r'\d', cleaned))

    # Must have exactly 8 digits for a valid date
    if len(digits) != 8:
        return None

    # Parse format to determine component order
    format_upper = format.upper()

    if format_upper.startswith("DD"):
        first, second, year = digits[0:2], digits[2:4], digits[4:8]
    elif format_upper.startswith("MM"):
        first, second, year = digits[0:2], digits[2:4], digits[4:8]
    elif format_upper.startswith("YYYY"):
        year, first, second = digits[0:4], digits[4:6], digits[6:8]
    else:
        return None

    # Determine separator
    sep = '.' if '.' in format else ('/' if '/' in format else ('-' if '-' in format else '.'))

    # Rebuild
    if format_upper.startswith("YYYY"):
        return f"{year}{sep}{first}{sep}{second}"
    else:
        return f"{first}{sep}{second}{sep}{year}"


# ============================================================================
# HEIGHT NORMALIZATION (from app/field_extraction/hybrid_template.py)
# ============================================================================

def normalize_height(value: str, format_type: str = 'auto') -> Optional[str]:
    """
    Normalize height to US (5'08) or metric (1,75m) format

    Args:
        value: Raw height string from OCR
        format_type: 'us', 'metric', or 'auto'

    Returns:
        Normalized height string, or None if invalid

    Examples:
        normalize_height("508", "us") → "5'08"
        normalize_height("175", "metric") → "1,75m"
    """
    if not value:
        return None

    # Auto-detect format
    if format_type == 'auto':
        us_result = normalize_height(value, 'us')
        metric_result = normalize_height(value, 'metric')
        return us_result or metric_result

    if format_type == 'us':
        # Try to parse existing format like "5'08" or "5-08" or "5"08"
        match = re.search(r"(\d)['\"\-\s]+(\d{1,2})\"?", value)
        if match:
            feet, inches = match.group(1), match.group(2).zfill(2)
            if 4 <= int(feet) <= 7 and 0 <= int(inches) <= 11:
                return f"{feet}'{inches}"

        # Extract digits and parse as feet-inches
        digits = ''.join(re.findall(r'\d', value))
        if 2 <= len(digits) <= 3:
            feet, inches = digits[0], digits[1:].zfill(2)
            if 4 <= int(feet) <= 7 and 0 <= int(inches) <= 11:
                return f"{feet}'{inches}"

    elif format_type == 'metric':
        # Extract digits for metric format
        digits = re.findall(r'\d', value)
        if len(digits) >= 3:
            return f"{digits[0]},{digits[1]}{digits[2]}m"
        elif len(digits) == 2:
            return f"1,{digits[0]}{digits[1]}m"

    return value.strip() or None


# ============================================================================
# WEIGHT NORMALIZATION (from app/field_extraction/hybrid_template.py)
# ============================================================================

def normalize_weight(value: str, format_type: str = 'auto') -> Optional[str]:
    """
    Normalize weight to US (150lb) or metric (68kg) format

    Args:
        value: Raw weight string from OCR
        format_type: 'us', 'metric', or 'auto'

    Returns:
        Normalized weight string, or None if invalid

    Examples:
        normalize_weight("150", "us") → "150lb"
        normalize_weight("68", "metric") → "68kg"
    """
    if not value:
        return None

    # Auto-detect format
    if format_type == 'auto':
        if 'kg' in value.lower():
            format_type = 'metric'
        elif 'lb' in value.lower():
            format_type = 'us'
        else:
            format_type = 'us'

    # Extract digits
    digits = ''.join(re.findall(r'\d', value))

    if format_type == 'us':
        if len(digits) >= 2:
            # Try 3-digit weight first (100-400 lb)
            if len(digits) >= 3:
                for i in range(len(digits) - 2):
                    weight = int(digits[i:i+3])
                    if 80 <= weight <= 400:
                        return f"{weight}lb"
            # Try 2-digit weight (80-99 lb)
            for i in range(len(digits) - 1):
                weight = int(digits[i:i+2])
                if 80 <= weight <= 99:
                    return f"{weight}lb"

    elif format_type == 'metric':
        if len(digits) >= 2:
            weight = int(digits[:2]) if len(digits) == 2 else int(digits[:3])
            if 40 <= weight <= 200:
                return f"{weight}kg"

    return value.strip() or None


# ============================================================================
# SEX NORMALIZATION (from app/field_extraction/hybrid_template.py)
# ============================================================================

def normalize_sex(value: str) -> Optional[str]:
    """
    Extract M or F from text

    Args:
        value: Raw sex string from OCR

    Returns:
        'M' or 'F', or None if invalid

    Examples:
        normalize_sex("M") → "M"
        normalize_sex("MALE") → "M"
        normalize_sex("4. SEX: F") → "F"
    """
    if not value:
        return None

    text = value.upper().strip()

    # Direct match
    if text in ['M', 'F']:
        return text

    # Word boundary match
    match = re.search(r'\b[MF]\b', text)
    if match:
        return match.group(0)

    # Fallback: check presence
    if 'F' in text and 'M' not in text:
        return 'F'
    if 'M' in text and 'F' not in text:
        return 'M'

    return None


# ============================================================================
# EYE COLOR NORMALIZATION (from app/field_extraction/hybrid_template.py)
# ============================================================================

def normalize_eye_color(value: str) -> Optional[str]:
    """
    Extract eye color from text using regex pattern (no normalization)

    Just extracts the eye color code exactly as it appears on the document.
    Works like height extraction: "18. Eyes: BRO" → "BRO"

    Args:
        value: Raw eye color string from OCR

    Returns:
        Eye color code as found in document, or None if not found

    Examples:
        normalize_eye_color("BRO") → "BRO"
        normalize_eye_color("18. Eyes: BRN") → "BRN"
        normalize_eye_color("EYES: BLUE") → "BLUE"
    """
    if not value:
        return None

    text = value.upper().strip()

    # Extract 2-3 letter eye color codes (most common on IDs)
    # Pattern: word boundary + 2-3 uppercase letters + word boundary
    match = re.search(r'\b([A-Z]{2,3})\b', text)
    if match:
        code = match.group(1)
        # Only return if it looks like an eye color code (2-3 letters, all caps)
        if 2 <= len(code) <= 3:
            return code

    # Fallback: extract full words like BLUE, BROWN, GREEN, etc.
    match = re.search(r'\b([A-Z]{4,6})\b', text)
    if match:
        return match.group(1)

    return None


# ============================================================================
# FIELD-SPECIFIC CLEANING (from app/field_extraction/processing/cleaners.py)
# ============================================================================

def clean_name_field(value: str) -> Optional[str]:
    """
    Clean name fields by removing OCR noise while preserving valid name components.

    Rules:
    - Keep only UPPERCASE letters, spaces, apostrophes (O'BRIEN), and hyphens (JEAN-PAUL)
    - Remove lowercase letters (OCR noise: "GEORGE a" -> "GEORGE")
    - Remove trailing/leading punctuation
    - Remove standalone punctuation between words
    - Normalize multiple spaces to single space

    Args:
        value: Raw name string from OCR

    Returns:
        Cleaned name string with only uppercase letters and valid punctuation, or None if empty

    Examples:
        clean_name_field("GEORGE a NICHOLAS") -> "GEORGE NICHOLAS"
        clean_name_field("SMITH - -") -> "SMITH"
        clean_name_field("O'BRIEN") -> "O'BRIEN"
        clean_name_field("JEAN-PAUL") -> "JEAN-PAUL"
    """
    if not value:
        return None

    # Step 1: Convert separators that are not part of names to spaces
    # Keep apostrophes and hyphens that might be part of names
    value = re.sub(r"[._:;,]", ' ', value)

    # Step 2: Keep only uppercase letters, spaces, apostrophes, and hyphens
    # This removes lowercase letters (OCR noise) and other invalid characters
    cleaned = re.sub(r"[^A-Z\s'\-]", '', value)

    # Step 3: Remove standalone punctuation (not part of a name)
    # " - " -> " ", " ' " -> " "
    cleaned = re.sub(r'\s+[\'\-]+\s+', ' ', cleaned)

    # Step 4: Remove leading/trailing punctuation
    cleaned = re.sub(r'^\s*[\'\-]+\s*|\s*[\'\-]+\s*$', '', cleaned)

    # Step 5: Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)

    return cleaned.strip() if cleaned.strip() else None


def clean_address_field(value: str) -> Optional[str]:
    """
    Clean address fields by removing OCR noise while preserving valid address components.

    Rules:
    - Keep UPPERCASE letters, numbers, spaces, and common address punctuation (-, #, /, ,)
    - Remove lowercase letters (OCR noise: "2502 BROOKLINE de" -> "2502 BROOKLINE")
    - Remove trailing/leading invalid characters
    - Preserve abbreviations (APT, CT, ST, TX, etc.)
    - Normalize multiple spaces to single space

    Args:
        value: Raw address string from OCR

    Returns:
        Cleaned address string, or None if empty

    Examples:
        clean_address_field("2502 BROOKLINECTAPT de 516") -> "2502 BROOKLINECTAPT 516"
        clean_address_field("ARLINGTON, TX:76006 a") -> "ARLINGTON, TX 76006"
        clean_address_field("123 MAIN ST apt 4B") -> "123 MAIN ST 4B"
    """
    if not value:
        return None

    # Step 1: Keep only uppercase letters, digits, spaces, and valid address punctuation
    # Remove lowercase letters (OCR noise) and other invalid characters
    # Valid: A-Z, 0-9, space, comma, hyphen, #, /
    cleaned = re.sub(r"[^A-Z0-9\s,\-#/]", '', value)

    # Step 2: Clean up excessive punctuation
    # Remove standalone commas/hyphens between spaces
    cleaned = re.sub(r'\s+[,\-]+\s+', ' ', cleaned)

    # Step 3: Normalize spacing around commas
    cleaned = re.sub(r'\s*,\s*', ', ', cleaned)

    # Step 4: Remove leading/trailing punctuation
    cleaned = re.sub(r'^\s*[,\-#/]+\s*|\s*[,\-#/]+\s*$', '', cleaned)

    # Step 5: Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)

    return cleaned.strip() if cleaned.strip() else None


# ============================================================================
# MASTER NORMALIZATION FUNCTION
# ============================================================================

def normalize_field(value: str, field_format: str, field_name: Optional[str] = None, **format_options) -> Optional[str]:
    """
    Apply format-specific normalization AND field-specific cleaning to a field value

    This replicates the exact logic from HybridTemplate._apply_format()

    Args:
        value: Raw extracted text
        field_format: Field format type (date, height, weight, sex, string, number)
        field_name: Field name for field-specific cleaning (e.g., "first_name", "address")
        **format_options: Format-specific options:
            - date_format: Date format string (DD.MM.YYYY, etc.)
            - height_format: Height format (us, metric, auto)
            - weight_format: Weight format (us, metric, auto)

    Returns:
        Normalized value, or None if normalization fails
    """
    if not value:
        return None

    # Step 1: Format-specific normalization
    if field_format == 'date':
        date_format = format_options.get('date_format', 'DD.MM.YYYY')
        value = normalize_date(value, date_format)

    elif field_format == 'sex':
        value = normalize_sex(value)

    elif field_format == 'eyes':
        value = normalize_eye_color(value)

    elif field_format == 'height':
        height_format = format_options.get('height_format', 'auto')
        value = normalize_height(value, height_format)

    elif field_format == 'weight':
        weight_format = format_options.get('weight_format', 'auto')
        value = normalize_weight(value, weight_format)

    elif field_format == 'number':
        # Number format: uppercase alphanumeric
        value = value.strip().upper() if value.strip() else None

    else:  # string
        value = value.strip() if value.strip() else None

    # Step 2: Field-specific cleaning (ALWAYS apply for name/address fields)
    # This matches production behavior in HybridTemplate._apply_format
    if value and field_name:
        # Clean name fields (first_name, last_name, middle_name)
        if any(name_field in field_name for name_field in ['first_name', 'last_name', 'middle_name']):
            value = clean_name_field(value)

        # Clean address fields
        if 'address' in field_name:
            value = clean_address_field(value)

    return value
