# OCR Variations - Real Examples

## Purpose
This file shows REAL OCR outputs from our multi-model system. Use these to understand variation patterns, but DO NOT overfit your regex to these specific examples.

## Date of Birth (DOB) Field

### Sample Set 1 (Washington DL)
```
3. DOB: 10/22/1993
3 DOB: 10/22/1993
3. DOB: 10/22/1993
3 DOB: 10/22/1993
3. DOB: 10/22/1993
```
**Variation:** Missing dot after "3"

### Sample Set 2 (Washington DL)
```
3.DOB: 03/24/1985
3.DOB: 03/24/1985
3.DOB: 03/24/1985
3.DOB: 03/24/1985
3.DOB: 03/24/1985
```
**Variation:** No space between "3." and "DOB"

### Sample Set 3 (Washington DL)
```
3.008: 09/06/1988
3.006: 09/06/1988
3.008: 09/06/1988
3.D0B: 09/06/1988
3.008: 09/06/1988
```
**Variation:** OCR misreading "DOB" as "008", "006", "D0B" (letter-digit confusion)

### Sample Set 4 (Washington DL)
```
3. DOB: 01/26/1979
3. DOB: 01/26/1979
3. DOB: 01/26/1979
3. DOB: 01/26/1979
3. DOB: 01/26/1979
```
**Variation:** Consistent (but don't rely on this!)

### Sample Set 5 (Hypothetical future samples)
```
3 DOB 05/15/1990        ← Missing both dot and colon
3,DOB: 07/20/1985       ← Comma instead of dot
DOB: 12/31/2000         ← Missing number prefix entirely
3.D08: 03/14/1995       ← "0" and "8" misread
```

## Document Number Field

### Sample Set 1 (8-digit ID)
```
43. ID: 33677153
43 ID: 33677153
43. ID: 33677153
43 ID 33677153          ← Missing colon
43.ID:33677153          ← No spaces
```

### Sample Set 2 (License number)
```
4d.1D: 42482120
4d.10: 42482120         ← "1D" misread as "10"
4d.1D: 42482120
4d.10: 42482120
4d.1D: 42482120
```
**Variation:** Letter-digit confusion (D ↔ 0)

## Height Field

### Sample Set 1 (US Format)
```
8. HGT: 5-08
8. HGT: 5'08
8 HGT: 5-08
8. HGT: 508             ← Missing separator
8.HGT:5-08              ← No spaces
```

### Sample Set 2 (Metric)
```
HEIGHT: 175cm
HEIGHT: 1,75m
HEIGHT: 175             ← Missing unit
HEIGHT 1.75m            ← Missing colon
HEIGHT:175cm            ← No space
```

## Weight Field

### Sample Set 1
```
9. WGT: 150
9 WGT: 150
9. WGT: 150lb
9.WGT:150
9 WGT 150               ← Missing colon
```

## Sex Field

### Sample Set 1
```
4. SEX: M
4 SEX: M
4. SEX M                ← Missing colon
4.SEX:M                 ← No spaces
SEX: M                  ← Missing number
```

### Sample Set 2 (With more text)
```
4. SEX: M HAIR: BRO
SEX: MALE
S: M                    ← Label abbreviated
```

## Common OCR Error Patterns

### Missing Separators
- Colon missing: `DOB 10/22/1993` instead of `DOB: 10/22/1993`
- Dot missing: `3 DOB:` instead of `3. DOB:`
- Space missing: `DOB:10/22/1993` instead of `DOB: 10/22/1993`
- All missing: `DOB10221993`

### Letter-Digit Confusion
- `O` ↔ `0`: DOB → D0B, 008, D08
- `I` ↔ `1`: ID → 1D, I0
- `S` ↔ `5`: SEX → 5EX
- `B` ↔ `8`: DOB → DO8, D08

### Extra/Missing Spaces
- Extra: `3.  DOB:  10/22/1993`
- Missing: `3.DOB:10/22/1993`
- Inconsistent: `3 .DOB: 10/22/1993`

### Punctuation Variations
- Comma instead of dot: `3,DOB:`
- Dash instead of colon: `3. DOB- 10/22/1993`
- Multiple separators: `3.. DOB:: 10/22/1993`

## Key Insights

### What Stays Consistent
✓ **Data format:** Date always appears as `##/##/####` or similar
✓ **Data position:** After label text
✓ **Digit patterns:** Document numbers maintain digit count
✓ **Character types:** Heights use digits + separators

### What Varies
✗ **Label text:** DOB, D0B, 008, D08, etc.
✗ **Separators:** Colon, dot, space presence
✗ **Spacing:** Variable whitespace
✗ **Number prefixes:** 3., 3, 43., 4d., etc.

## Pattern Design Strategy

### ❌ BAD: Match label variations
```regex
(?:DOB|D0B|008|D08|D00)[:.\s]*
```
This is overfitted to seen examples. Future samples might have "D68", "OOB", "DDB", etc.

### ✅ GOOD: Match structural position
```regex
^.*?(?=\d{2}/\d{2}/\d{4})
```
This removes everything until the date pattern appears, regardless of label text.

### ❌ BAD: Require specific separators
```regex
^\d+\.\s*\w+:\s*
```
Fails if dot or colon is missing.

### ✅ GOOD: Optional separators with lookahead
```regex
^[^/]*(?=\d{2}/\d{2}/\d{4})
```
Removes any non-date characters until date pattern appears.

## Testing Your Patterns

Your patterns should work on:
1. All samples shown above
2. Variations not shown (new OCR errors)
3. Future documents with different layouts
4. Edge cases (missing separators, misread labels)

Focus on **what the data IS** (format, structure) not **what the label SAYS**.
