# Quick Reference Guide

## TL;DR

**Your job:** Design TWO regex patterns for each field:
1. **Cleanup Pattern** - Removes labels/prefixes (structural, not literal)
2. **Validation Pattern** - Validates format BEFORE normalization

**Golden Rules:**
- ✅ Use structural patterns (lookaheads, character classes, boundaries)
- ✅ Handle missing separators (colon, dot, space)
- ❌ NEVER match specific OCR errors (DOB, D0B, 008)
- ❌ NEVER rely on exact label text

---

## Quick Pattern Templates

### Cleanup Patterns (Choose Best for Your Case)

```regex
# Lookahead to data pattern (most robust)
r'^.*?(?=\d{2}/\d{2}/\d{4})'   # For dates
r'^.*?(?=\d{8})'                # For 8-digit numbers
r'^.*?(?=\d[\''\-]?\d{2})'      # For US heights

# Remove non-data characters
r'^[^/\d]*'                     # Until slash or digit
r'^[^\d]*'                      # Until first digit
r'^[^A-Z]*'                     # Until uppercase letter

# Remove up to separator
r'^.*?[:.\s]\s*'                # Until colon/dot/space + optional space
```

### Validation Patterns (Format-Specific)

```regex
# Dates (pre-normalization)
r'^\d{2}[/\-\.]\d{2}[/\-\.]\d{4}$'

# Heights US
r'^\d[\''\-\s]?\d{2}$'

# Heights Metric
r'^\d{2,3}(?:[.,]\d{2})?(?:cm|m)?$'

# Weight
r'^\d{2,3}(?:lb|kg)?$'

# Sex
r'^[MF]$'

# 8-digit number
r'^\d{8}$'

# Name
r'^[A-Z][A-Z\s\-\']+$'
```

---

## Common Mistakes Cheatsheet

| ❌ Wrong Approach                  | ✅ Right Approach                    |
|------------------------------------|--------------------------------------|
| `(?:DOB\|D0B\|008)`                | `^.*?(?=\d{2}/\d{2}/\d{4})`          |
| `^\d+\.\s*ID:\s*`                  | `^.*?(?=\d{8})`                      |
| `(?:HGT\|HEIGHT\|H6T):`            | `^.*?(?=\d[\''\-]?\d{2})`            |
| Requires colon                     | Makes colon optional or ignores it   |
| Matches label variations           | Matches data structure               |
| Complex multi-alternative          | Simple structural pattern            |

---

## OCR Error Patterns

**What varies (don't match these):**
- Label text: DOB, D0B, 008, D08, OOB
- Separators: `:`, `.`, ` ` presence
- Spacing: variable whitespace
- Prefixes: 3., 43, 4d., etc.

**What stays consistent (match these):**
- Data format: ##/##/#### for dates
- Data position: after label
- Character types: digits for numbers
- Structure: feet'inches, ###lb, etc.

---

## Decision Tree

### Designing Cleanup Pattern

```
Is the data format predictable?
├─ YES → Use lookahead to data pattern
│         r'^.*?(?=\d{2}/\d{2}/\d{4})'
│
└─ NO → Remove non-data characters
          r'^[^/\d]*' or r'^.*?[:.\s]\s*'
```

### Designing Validation Pattern

```
What format type?
├─ date → r'^\d{2}[/\-\.]\d{2}[/\-\.]\d{4}$'
├─ height US → r'^\d[\''\-\s]?\d{2}$'
├─ height metric → r'^\d{2,3}(?:[.,]\d{2})?(?:cm|m)?$'
├─ weight → r'^\d{2,3}(?:lb|kg)?$'
├─ sex → r'^[MF]$'
├─ number → r'^\d{8}$' (adjust digit count)
└─ string → Custom per field
```

---

## Testing Checklist

Before submitting patterns, verify:

- [ ] Works on all provided samples
- [ ] Works with missing colon
- [ ] Works with missing dot/space
- [ ] Works with OCR letter-digit confusion
- [ ] Works with different prefix formats
- [ ] Doesn't match specific label text
- [ ] Simple and explainable

---

## Example Workflow

### Given Samples:
```
3. DOB: 10/22/1993
3.008: 09/06/1988
3 DOB 01/26/1979
```

### Step 1: Identify Data Pattern
- Data is always: `##/##/####`
- Data position: after labels/prefixes
- Prefixes vary, data format consistent

### Step 2: Design Cleanup
**Approach:** Lookahead to date pattern
```regex
r'^.*?(?=\d{2}/\d{2}/\d{4})'
```

**Why:** Removes everything until date appears, ignores label variations

### Step 3: Design Validation
**Format:** Date with slashes (pre-normalization)
```regex
r'^\d{2}/\d{2}/\d{4}$'
```

**Why:** Validates exact date format before system normalizes `/` to `.`

### Step 4: Test
```
"3. DOB: 10/22/1993" → cleanup → "10/22/1993" → validate → ✅
"3.008: 09/06/1988" → cleanup → "09/06/1988" → validate → ✅
"3 DOB 01/26/1979" → cleanup → "01/26/1979" → validate → ✅
```

---

## Remember

1. **Cleanup = Remove noise** (be generous, structural)
2. **Validation = Check format** (be strict, specific)
3. **Normalization = System handles** (not your concern)
4. **Think structure, not labels** (data format, not text content)
5. **Handle variations gracefully** (optional separators, flexible matching)

---

## Common Questions

**Q: Should I match "DOB" or "D0B"?**
A: Neither. Match the date pattern itself: `(?=\d{2}/\d{2}/\d{4})`

**Q: What if colon is missing?**
A: Use patterns that don't require it: `^.*?(?=\d{2}/\d{2}/\d{4})`

**Q: Should validation accept both `/` and `.`?**
A: Depends on format. For dates, accept common separators: `[/\-\.]`

**Q: What if future samples have different prefixes?**
A: That's the point! Use structural patterns that work regardless.

**Q: How permissive should cleanup be?**
A: Very permissive. Remove everything until data pattern.

**Q: How strict should validation be?**
A: Strict on format, flexible on separators (within reason).

---

## Output Format Reminder

```
Field: field_name

Cleanup Pattern: r'pattern'
Why robust: Explanation focusing on structural approach

Validation Pattern: r'pattern'
What it matches: Expected format (pre-normalization)

Handles:
✓ Missing colon/spaces
✓ OCR substitutions (how structurally)
✓ Label variations (how ignored)

May fail on:
- Acceptable edge case if any
```
