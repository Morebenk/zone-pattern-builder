"""
Field Normalization - Simulating Field Extraction Logic
========================================================

This module replicates the exact normalization logic from the field extraction
system so the zone builder can show the actual final output that will be produced.
"""

import re
from enum import Enum
from typing import Optional, List


# --- Enums Provided by User ---

class EyeColor(Enum):
    """Eye color categories as defined in AAMVA standard."""
    BLACK = "BLK"
    BLUE = "BLU"
    BROWN = "BRO" # Note: AAMVA standard is BRO, but data often has BRN.
    GRAY = "GRY"
    GREEN = "GRN"
    HAZEL = "HAZ"
    MAROON = "MAR"
    PINK = "PNK"
    DICHROMATIC = "DIC"
    UNKNOWN = "UNK"
    # Adding BRN as it's extremely common in your examples
    BROWN_ALT = "BRN"


class HairColor(Enum):
    """Hair color categories as defined in AAMVA standard."""
    BALD = "BAL"
    BLACK = "BLK"
    BLOND = "BLN"
    BROWN = "BRO"
    GRAY = "GRY"
    RED = "RED"
    SANDY = "SDY"
    WHITE = "WHI"
    UNKNOWN = "UNK"
    # Adding BRN as it's common
    BROWN_ALT = "BRN"


# --- Pre-compiled Regex Patterns for Performance ---

# Create lists of valid color codes directly from the Enums
VALID_EYE_COLORS: List[str] = [e.value for e in EyeColor]
VALID_HAIR_COLORS: List[str] = [h.value for h in HairColor]

# Create regex patterns to find *only* these valid codes
# We use \b (word boundary) to avoid matching "BRO" inside "BROWN" (if "BROWN" wasn't a code)
# We join all valid codes with an OR | operator
EYE_COLOR_PATTERN = re.compile(r'\b(' + '|'.join(VALID_EYE_COLORS) + r')\b')
HAIR_COLOR_PATTERN = re.compile(r'\b(' + '|'.join(VALID_HAIR_COLORS) + r')\b')

# Pattern to find the first 2 or 3-digit number.
# This is less strict than \b\d{2,3}\b and will find "175" in "1751b"
WEIGHT_PATTERN = re.compile(r'(\d{2,3})')

# --- Height Patterns ---
# Allow word boundary before feet, accept various quote/hyphen variants,
# require feet to be a single digit 4-7 and inches 0-99 (we sanity-check later).
HEIGHT_PATTERN_US_EXPLICIT = re.compile(
    r"([4-7])\s*(?:'|’|`|\u2019|\-|\s)+\s*([0-9]{1,2})\b"
)

# Implicit 3-digit like 507 or 508. (Removed leading \b)
HEIGHT_PATTERN_US_IMPLICIT = re.compile(r'([4-7])([0-9]{2})\b')

# Metric patterns (from previous logic, removed leading \b)
HEIGHT_PATTERN_METRIC_DEC = re.compile(r'(1)[,.](\d{2})\s*M?\b')
HEIGHT_PATTERN_METRIC_CM = re.compile(r'(1[4-9]\d|2[0-1]\d)\s*CM\b')
HEIGHT_PATTERN_METRIC_INT = re.compile(r'(1[4-9]\d|2[0-1]\d)\b')
# ============================================================================

def _extract_color_after_label(
    text: str, label: str, color_pattern: re.Pattern
) -> Optional[str]:
    """
    Generic helper to find a color code. Works with or without label.

    Args:
        text: The raw input string (with or without label).
        label: The label to search for (e.g., "EYES", "HAIR"), optional.
        color_pattern: The compiled regex pattern containing valid color codes.

    Returns:
        The first valid color code found (after the label if present), or None.
    """
    if not text:
        return None

    # Standardize to uppercase
    upper_text = text.upper().strip()

    # Find the position of the label (e.g., "EYES") - optional, zone may have removed it
    label_pos = upper_text.find(label)

    if label_pos != -1:
        # Label found - search after it
        # This ensures "HAIR BLK EYES BRN" won't find "BLK" for "EYES"
        search_text = upper_text[label_pos + len(label):]
    else:
        # No label found - search entire string (zone may have removed label already)
        search_text = upper_text

    # Find the *first* match for a valid color in the new string
    match = color_pattern.search(search_text)

    if match:
        # Return the matched group (e.g., "BLK", "BRN")
        return match.group(1)

    return None


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


# ---------------------------------------------------------------------------
#  Height Normalization (Label is Optional)
# ---------------------------------------------------------------------------

def _parse_us_height(text: str) -> Optional[str]:
    """Tries to parse US-style height (5'08" or 508) from text."""
    
    # 1) Explicit formats like 5'07", 5-07, 5 07
    # Uses finditer to get the *first* valid match
    for match in HEIGHT_PATTERN_US_EXPLICIT.finditer(text):
        try:
            feet_str, inches_str = match.groups()
            feet = int(feet_str)
            inches = int(inches_str)
            # Sanity check inches 0-11
            if 0 <= inches <= 11:
                return f"{feet}'{str(inches).zfill(2)}"
        except (ValueError, IndexError):
            continue

    # 2) Implicit 3-digit formats like 507
    for match in HEIGHT_PATTERN_US_IMPLICIT.finditer(text):
        try:
            feet = int(match.group(1))
            inches = int(match.group(2))
            # Sanity check inches 0-11
            if 0 <= inches <= 11:
                return f"{feet}'{str(inches).zfill(2)}"
        except (ValueError, IndexError):
            continue

    return None

def _parse_metric_height(text: str) -> Optional[str]:
    """Tries to parse metric-style height (1.75m or 175cm) from text."""
    
    # Priority 1: Decimal format (1.75m, 1,82)
    for match_dec in HEIGHT_PATTERN_METRIC_DEC.finditer(text):
        try:
            meters, cm_str = match_dec.groups()
            if 0 <= int(cm_str) <= 99:
                return f"1,{cm_str}m"
        except (ValueError, IndexError):
            continue

    # Priority 2: Explicit CM format (168cm)
    for match_cm in HEIGHT_PATTERN_METRIC_CM.finditer(text):
        try:
            cm_str = match_cm.group(1)
            # Sanity check 140-219cm is already in regex
            return f"{cm_str[0]},{cm_str[1:]}m"
        except (ValueError, IndexError):
            continue

    # Priority 3: Ambiguous integer format (180)
    for match_int in HEIGHT_PATTERN_METRIC_INT.finditer(text):
        try:
            digits = match_int.group(1)
            # Sanity check 140-219cm is already in regex
            return f"{digits[0]},{digits[1:]}m"
        except (ValueError, IndexError):
            continue

    return None


def normalize_height(value: str, format_type: str = 'auto') -> Optional[str]:
    """
    Normalize height to US (5'08") or metric (1,75m) format.
    A label (HGT) is NOT required, as height formats are unique.
    
    Args:
        value: Raw height string from OCR
        format_type: 'us', 'metric', or 'auto'

    Returns:
        Normalized height string, or None if invalid
    """
    if not value:
        return None
    # Convert to upper for regex consistency (e.g., 'cm' vs 'CM')
    search_text = value.upper().strip()

    if format_type == 'us':
        return _parse_us_height(search_text)
    
    if format_type == 'metric':
        return _parse_metric_height(search_text)
    
    # 'auto' mode: Try US first, then metric
    us_result = _parse_us_height(search_text)
    if us_result:
        return us_result
    
    return _parse_metric_height(search_text)


# ============================================================================
# WEIGHT NORMALIZATION (from app/field_extraction/hybrid_template.py)
# ============================================================================

def normalize_weight(value: str, format_type: str = 'auto') -> Optional[str]:
    """
    Extracts a 2 or 3-digit weight value. Works with or without "WGT" label.
    Supports US (pounds) and metric (kilograms) formats.

    Args:
        value: Raw string from OCR (with or without "WGT" label)
        format_type: 'us' (pounds), 'metric' (kilograms), or 'auto'

    Returns:
        The weight as a formatted string (e.g., "156lb" or "70kg"), or None.

    Examples:
        normalize_weight("WGT 156 lb", "us") → "156lb"
        normalize_weight("155lb", "us") → "155lb"
        normalize_weight("WGT 70 kg", "metric") → "70kg"
        normalize_weight("156", "auto") → "156lb" (assumes US if no unit)
    """
    if not value:
        return None

    upper_text = value.upper().strip()

    # Find the position of the label "WGT" (optional - zone extraction may have already removed it)
    label_pos = upper_text.find("WGT")

    if label_pos != -1:
        # Label found - search after it
        search_text = upper_text[label_pos + len("WGT"):]
    else:
        # No label found - search entire string (zone may have removed label already)
        search_text = upper_text

    # Auto-detect format based on presence of 'KG' or 'LB'
    if format_type == 'auto':
        if 'KG' in search_text:
            format_type = 'metric'
        else:
            format_type = 'us'  # Default to US/pounds

    # Find all 2 or 3-digit numbers in the remaining string
    matches = WEIGHT_PATTERN.findall(search_text)

    if not matches:
        return None

    # Find the first number that passes the sanity check
    for weight_str in matches:
        try:
            weight_int = int(weight_str)

            if format_type == 'us':
                # Sanity check: plausible weight in lbs (e.g., 50-400 lbs)
                if 50 <= weight_int <= 400:
                    return f"{weight_int}lb"
            elif format_type == 'metric':
                # Sanity check: plausible weight in kg (e.g., 30-200 kg)
                if 30 <= weight_int <= 200:
                    return f"{weight_int}kg"

        except ValueError:
            # This should not happen with the regex, but good to continue
            continue

    return None


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
    Extracts the AAMVA eye color code (BLK, BLU, BRN, etc.). Works with or without "EYES" label.

    Args:
        value: Raw string from OCR (with or without "EYES" label)

    Returns:
        The 3-letter eye color code, or None if not found.
    """
    # I added "BRN" to your EyeColor Enum as it was in all your examples
    return _extract_color_after_label(value, "EYES", EYE_COLOR_PATTERN)


# ============================================================================
# HAIR COLOR NORMALIZATION (from app/field_extraction/hybrid_template.py)
# ============================================================================

def normalize_hair_color(value: str) -> Optional[str]:
    """
    Extracts the AAMVA hair color code (BLK, BLN, BRO, etc.). Works with or without "HAIR" label.

    Args:
        value: Raw string from OCR (with or without "HAIR" label)

    Returns:
        The 3-letter hair color code, or None if not found.
    """
    return _extract_color_after_label(value, "HAIR", HAIR_COLOR_PATTERN)


# ============================================================================
# US DRIVER LICENSE ENDORSEMENTS & RESTRICTIONS
# ============================================================================

def _parse_multiple_codes(text: str, valid_codes: List[str]) -> List[str]:
    """
    Robust parser that handles mixed separators (dots, commas, spaces) AND 
    concatenated codes within those separators.
    """
    found_codes = []
    # Sort valid codes by length (longest first) to prioritize M1/M2 over M
    sorted_codes = sorted([c for c in valid_codes if c != 'NONE'], key=len, reverse=True)

    # 1. Normalize all separators to spaces
    # Replace commas and dots with space
    clean_text = re.sub(r'[,\.]', ' ', text)
    
    # 2. Split into chunks
    chunks = clean_text.split()

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        # Case A: Exact match (e.g., "M1" or "P")
        if chunk in valid_codes:
            found_codes.append(chunk)
            continue

        # Case B: Concatenated codes inside a chunk (e.g., "HM1")
        remaining = chunk
        while remaining:
            matched = False
            for code in sorted_codes:
                if remaining.startswith(code):
                    found_codes.append(code)
                    remaining = remaining[len(code):]
                    matched = True
                    break
            
            if not matched:
                # If we can't match the start, it's noise. Skip one char.
                remaining = remaining[1:]

    return found_codes

# Valid endorsement codes from AAMVA standard
US_DL_ENDORSEMENTS = [
    'NONE',
    # Single-character codes
    'H', 'N', 'P', 'S', 'T', 'X', 'M', 'L', 'F', 'G', 'R', 'W', 'Z', 'O', 'A',
    # Multi-character codes
    'M1', 'M2', 'M3', 'P1', 'P2'
]

def normalize_endorsements(value: str) -> Optional[str]:
    """
    Normalize US driver license endorsements.
    
    Handles:
    - Left Bleed: "9a Endorsements", "Sa Endorsemants", "Da End"
    - Right Bleed: "12 Restrictions", "Restriotions", "Vehicle", "Class"
    - OCR Noise: Dots, missing spaces, concatenated codes.
    """
    if not value:
        return None

    upper_text = value.upper().strip()

    # Reject full label matches that are not field values
    if re.fullmatch(r'(DRIVER\s*LICENSE|USA|AMERICA|CLASS)', upper_text):
        return None

    # 1. START ANCHOR (Fuzzy match for "Endorsements")
    # Matches: 9a End, End, Ends, Endors, 9 Endorsements
    start_pattern = r'^(?:[9SDo0-9]+[a-zA-Z]?\s*)?E[NM]D(?:\w*)?\.?\s*'
    match_start = re.search(start_pattern, upper_text)
    if match_start:
        upper_text = upper_text[match_start.end():]

    # 2. END ANCHOR (Cut "Restrictions", "Vehicle", "Class")
    # Updates:
    # - R[EO]?ST matches "REST" and "RST" (no vowel)
    # - RE\b matches "12 Re"
    # - V[EHICO] matches "Vehicle" bleed if Rest label is missing
    end_pattern = r'(?:12\s*)?(?:R[EO]?ST\w*|RE\b|V[EHICO]\w*|CLASS).*$'
    upper_text = re.sub(end_pattern, '', upper_text)

    upper_text = upper_text.strip()

    # 3. Explicit NONE check
    if 'NONE' in upper_text:
        return 'NONE'

    # 4. Parse Codes
    codes = _parse_multiple_codes(upper_text, US_DL_ENDORSEMENTS)

    if not codes:
        return None

    # Sort and return comma-separated
    codes_sorted = sorted(set(codes))
    return ','.join(codes_sorted)

# Valid restriction codes from AAMVA standard
US_DL_RESTRICTIONS = [
    'NONE',
    # Single-character codes (A-Z)
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
    'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    # Numeric codes (1-16)
    # '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16',
    # P-series (P1-P40)
    'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9', 'P10',
    'P11', 'P12', 'P13', 'P14', 'P15', 'P16', 'P17', 'P18', 'P19', 'P20',
    'P21', 'P22', 'P23', 'P24', 'P25', 'P26', 'P27', 'P28', 'P29', 'P30',
    'P31', 'P32', 'P33', 'P34', 'P35', 'P36', 'P37', 'P38', 'P39', 'P40',
    # J-series (J01-J11, J99)
    'J01', 'J02', 'J03', 'J04', 'J05', 'J06', 'J07', 'J08', 'J09', 'J10', 'J11', 'J99',
    # Special codes
    'S1', 'A1', 'A2'
]

def normalize_restrictions(value: str) -> Optional[str]:
    """
    Normalize US driver license restrictions with aggressive noise removal
    for bleed-in text from 'Endorsements' (left) and 'Vehicle Class' (right).
    """
    if not value:
        return None

    # Standardize to uppercase
    upper_text = value.upper().strip()

    # Reject full label matches that are not field values
    if re.fullmatch(r'(DRIVER\s*LICENSE|USA|AMERICA|CLASS)', upper_text):
        return None

    # 1. START ANCHOR (Fuzzy match for "Restrictions")
    # Matches: 12 Restrictions, Rest, Rst, Resticions
    match_start = re.search(r'(?:12\s*)?(?:R[EO]?ST\w*|RE\b)\.?\s*', upper_text)
    if match_start:
        upper_text = upper_text[match_start.end():]

    # 2. END ANCHOR (Cut "Vehicle", "Class")
    # Matches: 9 Vehicle, gVehicle, Class, 9 V
    end_pattern = r'(?<=[\s\.,A-Z0-9])(?:(?:[9GS5]\s*)?V[EHICO]|CLASS|9\s*V\b).*$'
    upper_text = re.sub(end_pattern, '', upper_text)

    upper_text = upper_text.strip()

    # 3. Explicit NONE check
    if 'NONE' in upper_text:
        return 'NONE'

    # 4. Parse Codes
    codes = _parse_multiple_codes(upper_text, US_DL_RESTRICTIONS)

    if not codes:
        return None

    # Sort and return comma-separated
    codes_sorted = sorted(set(codes))
    return ','.join(codes_sorted)

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
        field_format: Field format type (date, height, weight, sex, eyes, hair, endorsements, restrictions, string, number)
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

    elif field_format == 'hair':
        value = normalize_hair_color(value)

    elif field_format == 'height':
        height_format = format_options.get('height_format', 'auto')
        value = normalize_height(value, height_format)

    elif field_format == 'weight':
        weight_format = format_options.get('weight_format', 'auto')
        value = normalize_weight(value, weight_format)

    elif field_format == 'endorsements':
        value = normalize_endorsements(value)

    elif field_format == 'restrictions':
        value = normalize_restrictions(value)

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


# This code assumes the normalize_height function and its helpers
# (_parse_us_height, _parse_metric_height) are defined above.

if __name__ == "__main__":

    print("\n--- Testing Height Normalization (US only) ---")

    test_cases_us = [
        # old tests
        "HGT 5'05\"",
        "HGT 5-05",
        "HGT 508",
        "HGT 5 08",
        "HGT 507",
        "HGT 19 5-08",
        "HGT 6-00",
        "HGT 4-11",
        "HGT 6 11",
        "HGT 705",
        "HGT 6'11\"",
        "HGT 4'00\"",
        "HGT 7'00\"",
        "HGT 3'11\"",
        "HGT 8'02\"",
        "HGT 11 5 09",
        "HGT 18 5 10",
        "HGT 165 5'09",
        "5-07",
        "5'07",
        "507",
        "5'00",
        "6'00",
        "411",
        "611",
        "705",
        # your new test cases
        "16 HGT 5'-00 NONE",
        "16 HGT 5-00 NONE",
        "16 HGT 5'-00 NONE",
        "16 HGT 5'-00 NONE",
        "16 HGT 5-00 NONE",
        "16 HGT 18 5'-07\" NONE",
        "16 HGT 18 5'-07\" NONE",
        "16 HGT 18 5'-07\" NONE",
        "16 HGT 18 5'-07\" NONE",
        "16 HGT 18 5'-07\" NONE",
        "16 HGT 18 5'-09\" NONE",
        "16 HGT 18 5'-09\" NONE",
        "16 HGT 18 5'-09\" NONE",
        "16 HGT 18 5'-09\" NONE",
        "16 HGT 18 5'-09\" NONE",
        "16 HGT 5-07 NONE",
        "16 HGT 5-07 NONE",
        "16 HGT 507 NONE",
        "16 HGT 5-07 NONE",
        "16 HGT 5-07 NONE",
        "16 HGT 18 6'-07\" NONE",
        "16 HGT 18 6'-07\" NONE",
        "16 HGT 18 6'-07\" NONE",
        "16 HGT 18 6'-07\" NONE",
        "16 HGT 18 6'-07\" NONE",
    ]

    for test in test_cases_us:
        print(f'"{test}" -> "{normalize_height(test, "us")}"')

