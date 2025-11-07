# Pattern Examples: Good vs Bad

## Purpose
This file demonstrates the difference between robust, structural patterns and brittle, overfitted patterns.

---

## Example 1: Date of Birth (DOB)

### Input Samples
```
3. DOB: 10/22/1993
3.008: 09/06/1988      ← OCR error
3 DOB 01/26/1979       ← Missing separators
```

### ❌ BAD Cleanup Pattern
```regex
r'^\d+\.?\s*(?:DOB|D0B|008|D08)[:.\s]*'
```

**Why it's bad:**
- Hardcoded label variations (DOB, D0B, 008, D08)
- What about future: D68, OOB, D00, 00B, DDB?
- Requires optional dot `\.?` and colon `:`
- Overfitted to current samples
- Will break on unseen variations

**Fails on:**
- `"4. D68: 03/15/1990"` (new OCR error)
- `"DOB 05/20/1985"` (no number prefix)
- `"3-DOB- 07/10/1992"` (dashes instead)

### ✅ GOOD Cleanup Pattern
```regex
r'^.*?(?=\d{2}/\d{2}/\d{4})'
```

**Why it's good:**
- Uses lookahead to find data pattern
- Removes EVERYTHING before date appears
- Doesn't care about label text
- Works regardless of separators
- Structural approach (finds the date format)

**Works on:**
- `"3. DOB: 10/22/1993"` → `"10/22/1993"`
- `"3.008: 09/06/1988"` → `"09/06/1988"`
- `"3 DOB 01/26/1979"` → `"01/26/1979"`
- `"X5.ZZZ- 03/15/1990"` → `"03/15/1990"`
- `"DOB05/20/1985"` → `"05/20/1985"`

### ✅ ALTERNATIVE Good Cleanup Pattern
```regex
r'^[^/\d]*'
```

**Why it's good:**
- Removes all non-date characters from start
- Simple and fast
- Doesn't match specific labels
- Stops at first slash or digit sequence

**Trade-off:**
- Less precise than lookahead
- Might leave some noise if format varies

---

## Example 2: Document Number

### Input Samples
```
43. ID: 33677153
4d.1D: 42482120        ← Mixed letters/digits
43 ID 33677153         ← Missing separators
```

### ❌ BAD Cleanup Pattern
```regex
r'^\d+[a-z]*\.?\s*(?:ID|1D|I0)[:.\s]*'
```

**Why it's bad:**
- Hardcoded "ID" variations
- Assumes number prefix format
- Won't handle future label variations
- Brittle to format changes

### ✅ GOOD Cleanup Pattern
```regex
r'^.*?(?=\d{8})'
```

**Why it's good:**
- Removes everything until 8-digit number
- Works regardless of label text
- Handles any prefix format
- Structural (looks for the data pattern)

**Alternative if document number format varies:**
```regex
r'^[^\d]*'
```
Removes all non-digits from start, stops at first digit.

---

## Example 3: Height Field

### Input Samples
```
8. HGT: 5-08
8. HGT: 508            ← Missing separator
HEIGHT 175cm           ← Different format
```

### ❌ BAD Cleanup Pattern
```regex
r'^\d+\.\s*(?:HGT|HEIGHT):\s*'
```

**Why it's bad:**
- Requires colon (fails on `"HEIGHT 175cm"`)
- Requires number prefix (fails on `"HEIGHT: 175cm"`)
- Hardcoded label text
- Too specific

### ✅ GOOD Cleanup Pattern (US Format)
```regex
r'^.*?(?=\d[\''\-]?\d{2})'
```

**Why it's good:**
- Finds height pattern (digit + separator + 2 digits)
- Works with ' or - or missing separator
- Doesn't care about label
- Handles `"508"`, `"5'08"`, `"5-08"`

### ✅ GOOD Cleanup Pattern (Metric Format)
```regex
r'^.*?(?=\d{2,3}(?:cm|kg|m)?)'
```

**Why it's good:**
- Finds 2-3 digit number
- Optional unit suffix
- Label-agnostic

---

## Example 4: Sex Field

### Input Samples
```
4. SEX: M
4 SEX M                ← Missing separators
SEX: MALE              ← Full word
```

### ❌ BAD Cleanup Pattern
```regex
r'^\d+\.?\s*SEX[:.\s]*'
```

**Why it's bad:**
- Hardcoded "SEX" label
- Won't work if OCR reads "5EX", "SFX", etc.
- Requires optional prefix number
- Fails on variations

### ✅ GOOD Cleanup Pattern
```regex
r'^[^MF]*'
```

**Why it's good:**
- Removes everything until M or F appears
- Super simple
- Works regardless of label
- Handles `"4. SEX: M"`, `"S: M"`, `"MALE"`, etc.

**Trade-off:**
- Might fail if M or F appears in label text
- But statistically unlikely, so acceptable

### ✅ ALTERNATIVE Good Cleanup Pattern
```regex
r'^.*?(?=[MF])'
```

**Why it's good:**
- Lookahead for M or F
- More explicit
- Slightly slower but safer

---

## Validation Pattern Examples

### Date Validation (BEFORE normalization)

**Input after cleanup:** `"10/22/1993"`

### ✅ GOOD Validation Pattern
```regex
r'^\d{2}/\d{2}/\d{4}$'
```

**Why it's good:**
- Matches exact format with slashes
- Strict digit count
- Validates format before normalization converts `/` to `.`

**Note:** Normalization will convert this to `10.22.1993` later. Validation checks pre-normalization format.

### Height Validation (US Format, BEFORE normalization)

**Input after cleanup:** `"5-08"` or `"508"` or `"5'08"`

### ✅ GOOD Validation Pattern
```regex
r'^\d[\''\-]?\d{2}$'
```

**Why it's good:**
- Accepts separator or no separator
- Validates structure
- Normalization will convert to `5'08` later

---

## Key Principles Summary

### Cleanup Patterns Should:
1. ✅ Use lookaheads to find data patterns
2. ✅ Remove based on structure, not labels
3. ✅ Handle missing separators
4. ✅ Be simple and maintainable
5. ❌ NOT match specific OCR errors
6. ❌ NOT rely on exact label text

### Validation Patterns Should:
1. ✅ Match expected format strictly
2. ✅ Validate BEFORE normalization
3. ✅ Use anchors (^ and $)
4. ✅ Be format-specific
5. ❌ NOT be too permissive
6. ❌ NOT validate normalized output

---

## Pattern Testing Checklist

Before submitting a pattern, verify:

- [ ] Works on all provided samples
- [ ] Works with missing separators (colon, dot, space)
- [ ] Works with OCR letter-digit confusion
- [ ] Works with different prefix formats
- [ ] Works with unseen label variations
- [ ] Doesn't rely on specific label text
- [ ] Is simple and explainable
- [ ] Handles edge cases gracefully

---

## Common Mistakes to Avoid

### 1. Matching Specific OCR Errors
```regex
❌ (?:DOB|D0B|008|D08)
✅ ^.*?(?=\d{2}/\d{2}/\d{4})
```

### 2. Requiring Specific Separators
```regex
❌ ^\d+\.\s*\w+:\s*
✅ ^.*?(?=\d{2}/\d{2}/\d{4})
```

### 3. Overly Complex Patterns
```regex
❌ ^\d{1,2}[a-z]*[.,;:\-\s]*(?:DOB|D0B|D08|008|OOB)[.,;:\-\s]*
✅ ^[^/\d]*
```

### 4. Validating Normalized Output
```regex
❌ ^\d{2}\.\d{2}\.\d{4}$  (for validation pattern)
✅ ^\d{2}/\d{2}/\d{4}$    (validate PRE-normalization format)
```

Note: Normalization converts `/` to `.`, so validate the format BEFORE this conversion.
