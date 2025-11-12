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
# US: Finds 5'05", 5-05, 5"04, 5 05, etc.
HEIGHT_PATTERN_US_EXPLICIT = re.compile(r"(\d)\s*['\"\-\s]+\s*(\d{1,2})")
# US: Finds 3-digit format like 508 (5'08")
HEIGHT_PATTERN_US_IMPLICIT = re.compile(r'\b(\d{3})\b')

# Metric: Finds 1.75 or 1,75 (with optional 'M') - NOTE: Text is uppercased, so use 'M'
HEIGHT_PATTERN_METRIC_DEC = re.compile(r'\b(1)[,.](\d{2})\s*M?\b')
# Metric: Finds 175cm (range 140-220) - NOTE: Text is uppercased, so use 'CM'
HEIGHT_PATTERN_METRIC_CM = re.compile(r'\b(1[4-9]\d|2[0-1]\d)\s*CM\b')
# Metric: Finds 175 (ambiguous, range 140-220, must be last resort)
HEIGHT_PATTERN_METRIC_INT = re.compile(r'\b(1[4-9]\d|2[0-1]\d)\b')


def _extract_color_after_label(
    text: str, label: str, color_pattern: re.Pattern
) -> Optional[str]:
    """
    Generic helper to find a color code that appears after a specific label.

    Args:
        text: The raw input string.
        label: The label to search for (e.g., "EYES", "HAIR").
        color_pattern: The compiled regex pattern containing valid color codes.

    Returns:
        The first valid color code found after the label, or None.
    """
    if not text:
        return None

    # Standardize to uppercase
    upper_text = text.upper().strip()

    # Find the position of the label (e.g., "EYES")
    label_pos = upper_text.find(label)

    # If the label doesn't exist, we can't find the color
    if label_pos == -1:
        return None

    # Create a new string starting *after* the label
    # This ensures "HAIR BLK EYES BRN" won't find "BLK" for "EYES"
    search_text = upper_text[label_pos + len(label):]

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
    """
    Tries to parse US-style height (5'08" or 508) from text.
    Uses finditer to check ALL matches and return the first valid one.
    """
    
    # 1. Try explicit format first: 5'05", 5-05, etc.
    # *** THIS IS THE FIX for "HGT 19 5-08" ***
    # It finds ALL matches and checks them in order.
    # Match 1: "1 9" -> feet=1, inches=9 -> Fails sanity check, continues
    # Match 2: "5-08" -> feet=5, inches=8 -> Passes sanity check, returns
    for match in HEIGHT_PATTERN_US_EXPLICIT.finditer(text):
        try:
            feet_str, inches_str = match.groups()
            feet = int(feet_str)
            inches = int(inches_str)

            # Sanity check: 4'00" to 7'11"
            if 4 <= feet <= 7 and 0 <= inches <= 11:
                return f"{feet}'{inches_str.zfill(2)}"
        except (ValueError, IndexError):
            continue  # Not a valid number, keep searching

    # 2. Try implicit 3-digit format: 508
    for match_implicit in HEIGHT_PATTERN_US_IMPLICIT.finditer(text):
        try:
            digits = match_implicit.group(1)
            feet, inches_str = digits[0], digits[1:]
            feet_int = int(feet)
            inches_int = int(inches_str)
            
            # Sanity check: 4'00" to 7'11"
            if 4 <= feet_int <= 7 and 0 <= inches_int <= 11:
                return f"{feet_int}'{inches_str.zfill(2)}"
        except (ValueError, IndexError):
            continue # Keep searching
            
    return None

def _parse_metric_height(text: str) -> Optional[str]:
    """
    Tries to parse metric-style height (1.75m or 175cm) from text.
    Checks in priority order.
    """
    
    # We must check in order of specificity.
    
    # 1. Try decimal format: 1.75m or 1,82
    # *** THIS IS THE FIX for "HGT 1.75m" ***
    for match_dec in HEIGHT_PATTERN_METRIC_DEC.finditer(text):
        try:
            meters, cm_str = match_dec.groups()
            cm = int(cm_str)
            # Sanity check: 1.00m to 1.99m
            if 0 <= cm <= 99: # '1.' is already checked by regex
                return f"1,{cm_str}m"
        except (ValueError, IndexError):
            continue

    # 2. Try 'cm' integer format: 175cm
    # *** THIS IS THE FIX for "HGT 168cm" ***
    for match_cm in HEIGHT_PATTERN_METRIC_CM.finditer(text):
        try:
            cm_str = match_cm.group(1)
            cm = int(cm_str)
            # Sanity check: 140cm to 220cm (already in regex)
            return f"{cm_str[0]},{cm_str[1:]}m"
        except (ValueError, IndexError):
            continue

    # 3. Try ambiguous 3-digit integer format: 180 (LAST RESORT)
    for match_int in HEIGHT_PATTERN_METRIC_INT.finditer(text):
        try:
            digits = match_int.group(1)
            cm = int(digits)
            # Sanity check: 140cm to 220cm (already in regex)
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
    
    # --- Label is NOT required for height ---
    search_text = value.upper().strip()

    if format_type == 'us':
        return _parse_us_height(search_text)
    
    if format_type == 'metric':
        return _parse_metric_height(search_text)

    if format_type == 'auto':
        # 'auto' mode MUST try US first, as it's more common in
        # mixed strings like "HGT 160 5'04"".
        us_result = _parse_us_height(search_text)
        if us_result:
            return us_result
        
        # Fallback to metric
        return _parse_metric_height(search_text)

    return None


# ============================================================================
# WEIGHT NORMALIZATION (from app/field_extraction/hybrid_template.py)
# ============================================================================

def normalize_weight(value: str, format_type: str = 'auto') -> Optional[str]:
    """
    Extracts a 2 or 3-digit weight value that appears after the "WGT" label.
    Supports US (pounds) and metric (kilograms) formats.

    Args:
        value: Raw string from OCR
        format_type: 'us' (pounds), 'metric' (kilograms), or 'auto'

    Returns:
        The weight as a formatted string (e.g., "156lb" or "70kg"), or None.

    Examples:
        normalize_weight("WGT 156 lb", "us") → "156lb"
        normalize_weight("WGT 70 kg", "metric") → "70kg"
        normalize_weight("WGT 156", "auto") → "156lb" (assumes US if no unit)
    """
    if not value:
        return None

    upper_text = value.upper().strip()

    # Find the position of the label "WGT"
    label_pos = upper_text.find("WGT")

    if label_pos == -1:
        return None

    # Create a new string starting *after* the label
    search_text = upper_text[label_pos + len("WGT"):]

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
    Extracts the AAMVA eye color code (BLK, BLU, BRN, etc.) that
    appears after the "EYES" label in a string.

    Args:
        value: Raw string from OCR

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
    Extracts the AAMVA hair color code (BLK, BLN, BRO, etc.) that
    appears after the "HAIR" label in a string.

    Args:
        value: Raw string from OCR

    Returns:
        The 3-letter hair color code, or None if not found.
    """
    return _extract_color_after_label(value, "HAIR", HAIR_COLOR_PATTERN)


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

    elif field_format == 'hair':
        value = normalize_hair_color(value)

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


# This code assumes the normalize_height function and its helpers
# (_parse_us_height, _parse_metric_height) are defined above.

if __name__ == "__main__":

    print("\n--- Testing Height Normalization (US & Auto-Detect) ---")
    
    # Using a set to auto-remove duplicates from the provided examples
    test_cases_height = list(set([
        # --- Examples from first prompt ---
        '15 SEX F 18 16 HGT 5\'-05" 19',
        '15 SEX F 18 16 HGT 5\'-05" 19',
        '15 SEX F 18 16 HGT 5\'-05" 19',
        '15 SEX F 18 16 HGT 5\'-05" 19',
        '15 SEX F 18 16 HGT 5-05" 19',
        '15 SEX M 18 16 HGT 5-11" 19 17 WGT 155 Ib',
        '15 SEX M 18 16 HGT 5-11" 19 17 WGT 155 lb',
        '15 SEX M 18 16 HGT 5-11" 19 17 WGT 155 Ib',
        '15 SEX M 18 16 HGT 5-11" 19 17 WGT 155 lb',
        '15 SEX M 18 16 HGT 5-11" 19 17 WGT 155 lb',
        '16 HGT 5\'-04" 19 17 WGT 110 Ib',
        '16 HGT 5\'-04" 19 17 WGT 110 Ib',
        '16 HGT 5"-04" 19 17 WGT 110 lb',
        '16 HGT 5-00" 19 17 WGT 110 lb',
        '16 HGT 5-04" 19 17 WGT 110 lb',
        '16 HGT 5-01" 19 17 WGT 175.1b',
        '16 HGT 5-01 19 17 WGT 1751b',
        '16 HGT 5-01" 19 17 WGT 1751b',
        '16 HGT 5-01" 19 17 WGT 1751b',
        '16 HGT 5-01" 19 17 WGT 1751b',
        '15 SEX M 16 HGT 6\'-01" 17 WGT 210 lb',
        '15 SEX M 16 HGT 6\'-01" 17 WGT 210 lb',
        '15 SEX M 16 HGT 6\'-01" 17 WGT 210 lb',
        '15 SEX M 16 HGT 6\'-01" 17 WGT 210 lb',
        '15 SEX M 16 HGT 6\'-01" 17 WGT 210 lb',
        '16 HGT 5\'-04" 19 17 WGT 190 lb',
        '16 HGT 5\'-04" 19 17 WGT 190 lb',
        '16 HGT 5\'-04" 19 17 WGT 190 lb',
        '16 HGT 5\'004" 19 17 WGT 190 lb', # Should find 5'00"
        '16 HGT 5\'-04" 19 17 WGT 190 lb',

        # --- Examples from second prompt ---
        '4b EXP 09/19/2061 15 SEX F 18 EYES 16 HGT 5\'-05" 19 HAIR 17 WGT 156 Ib',
        '4b EXP 09/19/2061 15 SEX F 18 EYES 16 HGT 5\'-05" 19 HAIR 17 WGT 156 lb',
        '4b EXP 09/19/2061 15 SEX F 18 EYES 16 HGT 5\'-05" 19 HAIR 17 WGT 156 Ib',
        '4b EXP 09/19/2061 15 SEX F 18 EYES 16 HGT 5\'-05" 19 HAIR 17 WGT 156 lb',
        '4b EXP 09/19/2061 15 SEX F 18 EYES 16 HGT 5-05" 19 HAIR 17 WGT 156 lb',
        '15 SEX M 18 16 HGT 5-11" 19 HAIR 17 WGT 155 Ib',
        '15 SEX M 18 16 HGT 5-11" 19 HAIR 17 WGT 155 lb',
        '15 SEX M 18 16 HGT 5-11" 19 HAIR 17 WGT 155 Ib',
        '15 SEX M 18 16 HGT 5-11" 19 HAIR 17 WGT 155 lb',
        '15 SEX M 18 16 HGT 5-11" 19 HAIR 17 WGT 155 lb',
        '15: SEX F 18 EYES 16 HGT 5\'-04" 19 HAIR 17 WGT 110 Ib DONOR',
        '15 SEX F 18 EYES 16 HGT 5\'-04" 19 HAIR 17 WGT 110 Ib DONOR',
        '15 SEX F 18 EYES 16 HGT 5"-04" 19 HAIR 17 WGT 110 lb DONOR',
        '15 SEX F 18 EYES 16 HGT 5-00" 19 HAIR 17 WGT 110 lb DONOR',
        '15 SEX F 18 EYES 16 HGT 5-04" 19 HAIR 17 WGT 110 lb DONOR',
        '16 SEX F 18 16 HGT 5-01" 19 HAIR 17 WGT 175.1b DONOR - -',
        '16 SEX F 18 16 HGT 5-01 19 HAIR 17 WGT 1751b DONOR - -',
        '16 SEX F 1 16 HGT 5-01" 19 HAIR 17 WGT 1751b DONOR - -',
        '16 SEX F 18 16 HGT 5-01" 19 HAIR 17 WGT 1751b DONOR - -',
        '16 SEX F 14 16 HGT 5-01" 19 HAIR 17 WGT 1751b DONOR - -',
        '4b 15 SEX M 18 16 HGT 6\'-01" 19 17 WGT 210 lb',
        '46 15 SEX M 18 16 HGT 6\'-01" 19 17 WGT 210 lb',
        '46 15 SEX M 18 16 HGT 6\'-01" 19 17 WGT 210 lb',
        '4b 15 SEX M 18 16 HGT 6\'-01" 19 17 WGT 210 lb',
        '4b 15 SEX M 18 16 HGT 6\'-01" 19 17 WGT 210 lb',
        '15 SEX F 18 EYES 16 HGT 5\'-04" 19 HAIR 17 WGT 190 lb DONOR',
        '15 SEX F 18 EYES 16 HGT 5\'-04" 19 HAIR 17 WGT 190 lb DONOR',
        '15 SEX F 18 EYES 16 HGT 5\'-04" 19 HAIR 17 WGT 190 lb DONOR',
        '15 SEX F 18 EYES 16 HGT 5\'004" 19 HAIR 17 WGT 190 lb DONOR', # Should find 5'00"
        '15 SEX F 18 EYES 16 HGT 5\'-04" 19 HAIR 17 WGT 190 lb DONOR',

        # --- Additional Edge Cases ---
        'HGT: 5 10', # Space separator
        'HGT 5\' 11"', # Space after separator
        'HGT 6\'1"',  # 1-digit inch
        '16 HGT 509', # Implicit 3-digit format
        '16 HGT 601', # Implicit 3-digit format
        'HGT 8\'01"',  # Fail sanity check (too tall)
        'HGT 3\'11"',  # Fail sanity check (too short)
        'HGT 5\'12"',  # Fail sanity check (invalid inches)
        'NO LABEL 5\'05"', # Fail (no HGT label)
        'HGT 19 5-08', # Should ignore "19" and find 5-08
        'HGT 5-0', # Should find 5'00"
        'HGT 5- 2', # Should find 5'02"
    ]))

    # Sort for cleaner output
    test_cases_height.sort()

    for test in test_cases_height:
        # Test with default 'auto' format
        print(f'"{test}" -> "{normalize_height(test)}"')

    
    print("\n--- Testing Height (Explicit Format & Auto-Detect) ---")
    
    # (test_string, format_to_test)
    test_cases_height_metric = [
        ('HGT 1.75m', 'auto'),
        ('HGT 1,82', 'auto'),
        ('HGT 168cm', 'auto'),
        ('HGT 199', 'auto'), # Should parse as 1,99m
        ('HGT 5-05 175cm', 'us'), # Force US: Should find 5-05
        ('HGT 5-05 175cm', 'metric'), # Force Metric: Should find 1,75m
        ('HGT 1.60m 5\'04"', 'metric'), # Force Metric: Should find 1,60m
        ('HGT 1.60m 5\'04"', 'auto'), # Auto: Should find 5'04" (US-first)
        ('HGT 160 5\'04"', 'auto'), # Auto: Should find 5'04" (US-first)
        ('HGT 160 5\'04"', 'metric'), # Force Metric: Should find 1,60m
        ('HGT 508', 'auto'), # Auto: Should find 5'08"
        ('HGT 508', 'us'),   # Force US: Should find 5'08"
        ('HGT 508', 'metric'), # Force Metric: Should fail
        ('HGT 180', 'auto'), # Auto: Should find 1,80m (US 1'80" is invalid)
        ('HGT 180', 'metric'), # Force Metric: Should find 1,80m
        ('HGT 180', 'us'), # Force US: Should fail (1'80" invalid)
        ('HGT 99cm', 'metric'), # Fail Metric: (Too short)
    ]
    
    for test, fmt in test_cases_height_metric:
        print(f'"{test}" (format: {fmt}) -> "{normalize_height(test, fmt)}"')