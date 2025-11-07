# Field Format Specifications

## Purpose
This document defines what each field format expects for cleanup and validation patterns.

---

## Format: `date`

### Purpose
Extracts and validates date values from OCR text.

### Pipeline
```
Raw OCR → Cleanup → Validation → Normalization → Final
"3. DOB: 10/22/1993" → "10/22/1993" → ✅ Valid → "10.22.1993" → "10.22.1993"
```

### Cleanup Pattern Goal
Remove label text and prefixes, keep the date with its separators.

**Expected input:** `"3. DOB: 10/22/1993"`, `"3.008: 09/06/1988"`, `"DOB 01/26/1979"`
**Expected output:** `"10/22/1993"`, `"09/06/1988"`, `"01/26/1979"`

### Validation Pattern Goal
Match date format BEFORE normalization (validates separators like `/`, `-`, `.`).

**Expected format:** `##/##/####` or `##-##-####` or `##.##.####`
**Pattern example:** `r'^\d{2}[/\-\.]\d{2}[/\-\.]\d{4}$'`

### Normalization (Automatic)
System converts to specified format:
- `date_format: "MM.DD.YYYY"` → `10.22.1993`
- `date_format: "DD.MM.YYYY"` → `22.10.1993`
- `date_format: "YYYY-MM-DD"` → `1993-10-22`

### Common Issues
- OCR may produce: `10/22/1993`, `10-22-1993`, `10.22.1993`
- All are valid PRE-normalization formats
- Validation should accept common separators: `/`, `-`, `.`

---

## Format: `height`

### Purpose
Extracts and validates height measurements.

### Pipeline
```
Raw OCR → Cleanup → Validation → Normalization → Final
"8. HGT: 508" → "508" → ✅ Valid → "5'08" → "5'08"
```

### Cleanup Pattern Goal
Remove label text, keep height digits and any separators.

**Expected input:** `"8. HGT: 5-08"`, `"HEIGHT: 508"`, `"HGT 5'08"`
**Expected output:** `"5-08"`, `"508"`, `"5'08"`

### Validation Pattern Goal
Match height format BEFORE normalization.

**US Format expected:** `#'##` or `#-##` or `###` (e.g., `5'08`, `5-08`, `508`)
**Pattern example:** `r'^\d[\''\-]?\d{2}$'`

**Metric Format expected:** `###` or `#.##m` or `#,##m` (e.g., `175`, `1.75m`, `1,75m`)
**Pattern example:** `r'^\d{2,3}(?:[.,]\d{2})?(?:cm|m)?$'`

### Normalization (Automatic)
System converts based on format:
- `height_format: "us"` → `5'08` (feet'inches)
- `height_format: "metric"` → `1,75m` (meters)
- `height_format: "auto"` → Detects format automatically

### Common Issues
- US heights may appear as: `508`, `5'08`, `5-08`, `5 08`
- Metric heights may appear as: `175`, `1.75`, `1,75`, `175cm`, `1.75m`
- Validation should be flexible with separators

---

## Format: `weight`

### Purpose
Extracts and validates weight measurements.

### Pipeline
```
Raw OCR → Cleanup → Validation → Normalization → Final
"9. WGT: 150" → "150" → ✅ Valid → "150lb" → "150lb"
```

### Cleanup Pattern Goal
Remove label text, keep weight digits and optional units.

**Expected input:** `"9. WGT: 150"`, `"WEIGHT: 150lb"`, `"WGT 68kg"`
**Expected output:** `"150"`, `"150lb"`, `"68kg"`

### Validation Pattern Goal
Match weight format BEFORE normalization.

**Expected format:** `###` or `###lb` or `##kg` (e.g., `150`, `150lb`, `68kg`)
**Pattern example:** `r'^\d{2,3}(?:lb|kg)?$'`

### Normalization (Automatic)
System converts based on format:
- `weight_format: "us"` → `150lb` (pounds)
- `weight_format: "metric"` → `68kg` (kilograms)
- `weight_format: "auto"` → Detects based on unit or range

### Common Issues
- Weight may appear with or without units: `150`, `150lb`, `68kg`
- Units may be lowercase/uppercase: `LB`, `lb`, `KG`, `kg`
- Validation should accept optional units

---

## Format: `sex`

### Purpose
Extracts and validates sex/gender field (M or F).

### Pipeline
```
Raw OCR → Cleanup → Validation → Normalization → Final
"4. SEX: M" → "M" → ✅ Valid → "M" → "M"
```

### Cleanup Pattern Goal
Remove label text, keep M or F.

**Expected input:** `"4. SEX: M"`, `"SEX: MALE"`, `"S: F"`
**Expected output:** `"M"`, `"MALE"`, `"F"`

### Validation Pattern Goal
Match single letter M or F (before normalization extracts from MALE/FEMALE).

**Expected format:** `M` or `F` or `MALE` or `FEMALE`
**Pattern example:** `r'^[MF](?:ALE)?$'` or strict `r'^[MF]$'`

### Normalization (Automatic)
System extracts M or F:
- `"M"` → `"M"`
- `"MALE"` → `"M"`
- `"F"` → `"F"`
- `"FEMALE"` → `"F"`

### Common Issues
- May appear as: `M`, `F`, `MALE`, `FEMALE`, `Male`, `Female`
- Validation can be strict (MF only) or permissive (MALE/FEMALE)
- System handles extraction from full words

---

## Format: `number`

### Purpose
Extracts document numbers, ID numbers, codes (alphanumeric).

### Pipeline
```
Raw OCR → Cleanup → Validation → Normalization → Final
"43. ID: 33677153" → "33677153" → ✅ Valid → "33677153" → "33677153"
```

### Cleanup Pattern Goal
Remove label text and prefixes, keep the ID/code.

**Expected input:** `"43. ID: 33677153"`, `"ID 33677153"`, `"DL#: WA12345"`
**Expected output:** `"33677153"`, `"33677153"`, `"WA12345"`

### Validation Pattern Goal
Match expected number format (varies by field).

**Common formats:**
- 8 digits: `r'^\d{8}$'` (e.g., `33677153`)
- Alphanumeric: `r'^[A-Z]{2}\d{6}$'` (e.g., `WA123456`)
- Variable length: `r'^\d{7,9}$'` (e.g., 7-9 digits)

### Normalization (Automatic)
Basic uppercase and trim:
- `"wa12345"` → `"WA12345"`
- `" 33677153 "` → `"33677153"`

### Common Issues
- May include prefixes: `DL#`, `ID:`, etc.
- May have spaces: `336 771 53`
- Validation format depends on document type

---

## Format: `string`

### Purpose
Extracts text fields (names, addresses, etc.).

### Pipeline
```
Raw OCR → Cleanup → Validation → Normalization → Final
"5. NAME: SMITH" → "SMITH" → ✅ Valid → "SMITH" → "SMITH"
```

### Cleanup Pattern Goal
Remove label text, keep the actual data.

**Expected input:** `"5. NAME: SMITH"`, `"NAME JOHN"`, `"FN: JANE"`
**Expected output:** `"SMITH"`, `"JOHN"`, `"JANE"`

### Validation Pattern Goal
Match expected text format (varies by field).

**Common patterns:**
- Names: `r'^[A-Z][A-Z\s\-\']+$'` (uppercase letters, spaces, hyphens, apostrophes)
- Addresses: `r'^[A-Z0-9\s,\.]+$'` (alphanumeric with common punctuation)
- Codes: Custom per field

### Normalization (Automatic)
Basic text cleanup:
- Trim whitespace
- May capitalize first letters
- Remove excessive punctuation

---

## Validation Pattern Examples by Format

### Date (Pre-normalization)
```regex
r'^\d{2}[/\-\.]\d{2}[/\-\.]\d{4}$'
```
Matches: `10/22/1993`, `10-22-1993`, `10.22.1993`

### Height US (Pre-normalization)
```regex
r'^\d[\''\-\s]?\d{2}$'
```
Matches: `508`, `5'08`, `5-08`, `5 08`

### Height Metric (Pre-normalization)
```regex
r'^\d{2,3}(?:[.,]\d{2})?(?:cm|m)?$'
```
Matches: `175`, `1.75`, `1,75`, `175cm`, `1.75m`

### Weight (Pre-normalization)
```regex
r'^\d{2,3}(?:lb|kg)?$'
```
Matches: `150`, `150lb`, `68kg`

### Sex (Pre-normalization)
```regex
r'^[MF]$'
```
Matches: `M`, `F`

### Document Number (8 digits)
```regex
r'^\d{8}$'
```
Matches: `33677153`

### Name (Uppercase letters)
```regex
r'^[A-Z][A-Z\s\-\']+$'
```
Matches: `SMITH`, `O'BRIEN`, `JEAN-PAUL`

---

## Summary Table

| Format   | Cleanup Goal           | Validation Checks        | Normalization Does      |
|----------|------------------------|--------------------------|-------------------------|
| date     | Remove labels          | Date format with sep     | Convert separator/order |
| height   | Remove labels          | Height format with sep   | Convert to US/metric    |
| weight   | Remove labels          | Weight with optional unit| Add unit (lb/kg)        |
| sex      | Remove labels          | M or F                   | Extract from MALE/FEMALE|
| number   | Remove labels/prefixes | Digit/alphanum format    | Uppercase, trim         |
| string   | Remove labels          | Text format              | Basic cleanup           |

---

## Key Takeaways

1. **Cleanup removes labels** - Focus on removing prefixes/labels generically
2. **Validation checks format** - Before normalization, validate structure
3. **Normalization standardizes** - System handles conversion automatically
4. **Patterns must be structural** - Don't match specific OCR errors
5. **Separators vary** - Handle optional/missing separators gracefully
