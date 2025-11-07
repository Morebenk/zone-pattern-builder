# Field Extraction Pipeline Architecture

## Overview
This document explains how field extraction works in our OCR system. Understanding this pipeline is critical for designing robust regex patterns.

## Pipeline Flow

```
1. OCR Zone Extraction
   ↓ (Raw text from zone)
2. Cleanup Pattern Applied
   ↓ (Labels/noise removed)
3. Validation Pattern Check
   ↓ (Format verified)
4. Normalization Applied
   ↓ (Final formatted output)
5. Final Output
```

## Step-by-Step Breakdown

### Step 1: OCR Zone Extraction
- Multi-model OCR runs (5 models: parseq, crnn, vitstr, sar, viptr)
- Text extracted from normalized coordinate zones (y_range, x_range)
- Words sorted by reading order (Y-coordinate rounded to 0.1, then X)
- Raw text may include labels, numbers, noise

**Example raw output:**
```
"3. DOB: 10/22/1993"
```

### Step 2: Cleanup Pattern Applied
**Purpose:** Remove unwanted prefixes, labels, and noise

**Input:** Raw extracted text
**Pattern:** `cleanup_pattern` (regex)
**Operation:** `re.sub(cleanup_pattern, '', text, flags=re.IGNORECASE).strip()`
**Output:** Text with labels removed

**Example:**
```
Input:  "3. DOB: 10/22/1993"
Pattern: r'^.*?:\s*'
Output: "10/22/1993"
```

**YOUR JOB:** Design this pattern to be robust against OCR variations

### Step 3: Validation Pattern Check
**Purpose:** Verify the cleaned text matches expected format

**Input:** Cleaned text (after cleanup)
**Pattern:** `pattern` (regex)
**Operation:** `re.match(pattern, text)`
**Output:** Boolean (valid or not)

**Example:**
```
Input:  "10/22/1993"
Pattern: r'^\d{2}/\d{2}/\d{4}$'
Result: ✅ Valid
```

**YOUR JOB:** Design this pattern to match the expected format BEFORE normalization

### Step 4: Normalization Applied
**Purpose:** Convert to standard format (happens AFTER validation)

**This is NOT your responsibility** - The system handles this automatically based on format type.

**Examples:**
- Date: `10/22/1993` → `10.22.1993` (if format is MM.DD.YYYY)
- Height: `508` → `5'08` (if format is US)
- Weight: `150` → `150lb` (if format is US)
- Sex: `MALE` → `M`

### Step 5: Final Output
The normalized, validated field value ready for use.

## Field Formats

### Format: `date`
- **Cleanup goal:** Remove label text, keep date digits and separators
- **Validation goal:** Match date format BEFORE normalization (with /, -, or .)
- **Normalization:** Converts to specified format (DD.MM.YYYY, MM.DD.YYYY, etc.)
- **Final pattern check:** System validates normalized format

### Format: `height`
- **Cleanup goal:** Remove label text, keep measurement
- **Validation goal:** Match height format BEFORE normalization
- **Normalization:** Converts to US (5'08) or metric (1,75m)

### Format: `weight`
- **Cleanup goal:** Remove label text, keep weight value
- **Validation goal:** Match weight format BEFORE normalization
- **Normalization:** Converts to US (150lb) or metric (68kg)

### Format: `sex`
- **Cleanup goal:** Remove label text, keep M or F
- **Validation goal:** Match single letter M or F
- **Normalization:** Extracts M or F from text

### Format: `string` / `number`
- **Cleanup goal:** Remove label text, keep data
- **Validation goal:** Match expected format (custom per field)
- **Normalization:** Basic uppercase/trim

## Key Insights for Pattern Design

### 1. Validation Happens BEFORE Normalization
Your validation pattern checks the format AFTER cleanup but BEFORE normalization.

Example for dates:
```
Raw:        "3. DOB: 10/22/1993"
↓ Cleanup
Cleaned:    "10/22/1993"           ← Validation pattern checks THIS
↓ Validation (your pattern)
Valid: ✅
↓ Normalization (system)
Final:      "10.22.1993"
```

### 2. Multiple OCR Models = Multiple Variations
Same field may produce different raw outputs:
```
parseq:  "3. DOB: 10/22/1993"
crnn:    "3 DOB: 10/22/1993"   (missing dot)
sar:     "3.D0B: 10/22/1993"   (0 instead of O)
viptr:   "3.DOB:10/22/1993"    (no space after colon)
vitstr:  "3 DOB 10/22/1993"    (missing colon)
```

Your patterns must handle ALL variations using structural patterns, not literal text matching.

### 3. Consensus Voting
System uses majority vote across models. Your patterns should work for the majority of outputs.

## Pattern Design Requirements

### Cleanup Patterns Must:
- Remove labels/prefixes generically (not matching specific text)
- Handle missing separators (colon, dot, space)
- Use structural features (lookaheads, boundaries)
- Be simple and maintainable

### Validation Patterns Must:
- Match expected format strictly
- Check format BEFORE normalization
- Be format-specific (dates, heights, weights)
- Reject invalid data

### Both Patterns Should:
- NOT match specific OCR errors (DOB, D0B, 008)
- NOT rely on exact label text
- Work across multiple samples
- Be explainable and maintainable
