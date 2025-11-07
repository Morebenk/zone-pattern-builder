# GitHub Copilot Context Files

## Purpose
These files provide context to GitHub Copilot for designing robust OCR field extraction patterns.

## Files Overview

### 1. `field_extraction_pipeline.md`
**What it contains:** Complete explanation of the extraction pipeline (OCR → Cleanup → Validation → Normalization).

**Why upload it:** Helps Copilot understand where patterns fit in the system and what happens before/after pattern application.

**Key concepts:**
- 4-step pipeline flow
- Cleanup vs validation roles
- Normalization happens AFTER validation
- Multi-model OCR voting

---

### 2. `ocr_variations_examples.md`
**What it contains:** Real OCR output samples showing common variations and errors.

**Why upload it:** Shows Copilot what kind of variations exist, but emphasizes NOT to overfit to these specific examples.

**Key concepts:**
- Real multi-model OCR outputs
- Common OCR errors (letter-digit confusion, missing separators)
- What varies vs what stays consistent
- Anti-patterns (what NOT to do)

---

### 3. `pattern_examples_good_vs_bad.md`
**What it contains:** Side-by-side comparison of overfitted vs robust patterns with explanations.

**Why upload it:** Teaches Copilot the philosophy of structural pattern design through concrete examples.

**Key concepts:**
- Good vs bad pattern comparisons
- Why patterns are good/bad
- Trade-offs and edge cases
- Testing checklist

---

### 4. `field_format_specifications.md`
**What it contains:** Detailed specifications for each field format (date, height, weight, sex, number, string).

**Why upload it:** Provides format-specific requirements for cleanup and validation patterns.

**Key concepts:**
- Per-format expectations
- Pre-normalization vs post-normalization
- Validation pattern examples
- Common issues per format

---

### 5. `quick_reference.md`
**What it contains:** Condensed cheatsheet with templates, decision trees, and common mistakes.

**Why upload it:** Quick lookup for pattern templates and design decisions.

**Key concepts:**
- Pattern templates
- Decision tree
- Common mistakes table
- Testing checklist

---

## How to Use with GitHub Copilot

### Option 1: Copilot Chat (Recommended)
1. Open GitHub Copilot chat
2. Upload all 5 context files
3. Paste the main instruction (3800-4000 characters)
4. Paste your OCR sample outputs
5. Ask: "Design cleanup and validation patterns for this field"

### Option 2: Copilot in Editor
1. Open all 5 context files in your editor
2. Create a new file for your pattern work
3. Add comment with field name and samples
4. Let Copilot suggest patterns based on open files

### Option 3: Copilot Workspace
1. Create a GitHub Copilot workspace
2. Add these files as workspace context
3. Configure workspace with the main instruction
4. Use throughout your pattern design session

---

## Usage Example

### Step 1: Upload Context Files
Upload these 5 files to GitHub Copilot chat:
- field_extraction_pipeline.md
- ocr_variations_examples.md
- pattern_examples_good_vs_bad.md
- field_format_specifications.md
- quick_reference.md

### Step 2: Provide Main Instruction
Paste the main instruction (the 3800-4000 character prompt about being an OCR Pattern Designer).

### Step 3: Provide Your OCR Samples
```
Field: date_of_birth
Format: date (MM.DD.YYYY)

OCR Samples:
3. DOB: 10/22/1993
3.008: 09/06/1988
3 DOB 01/26/1979
3.DOB: 03/24/1985
DOB: 12/31/2000
```

### Step 4: Ask for Patterns
```
Design cleanup and validation patterns for this field.
```

### Step 5: Review Output
Copilot should provide:
```
Field: date_of_birth

Cleanup Pattern: r'^.*?(?=\d{2}/\d{2}/\d{4})'
Why robust: Uses lookahead to find date pattern, removes everything before it regardless of label text...

Validation Pattern: r'^\d{2}/\d{2}/\d{4}$'
What it matches: Date format with slashes before normalization converts to dots...

Handles:
✓ Missing colon/spaces: Works regardless of separator presence
✓ OCR substitutions: Doesn't match label text, only date structure
✓ Label variations: Ignores all label text, finds date pattern directly

May fail on:
- Dates without separators (10221993) - acceptable as these are rare
```

---

## Tips for Best Results

### DO:
✅ Upload all 5 files for complete context
✅ Provide real OCR samples (copy from zone builder)
✅ Specify the format type (date, height, weight, etc.)
✅ Ask for explanations of why patterns are robust
✅ Request edge case analysis

### DON'T:
❌ Upload only 1-2 files (incomplete context)
❌ Ask for patterns without providing samples
❌ Accept patterns that match specific OCR errors
❌ Skip validation of suggested patterns
❌ Forget to specify pre-normalization format

---

## Validating Copilot's Suggestions

After Copilot provides patterns, verify:

1. **Cleanup Pattern:**
   - [ ] Uses structural approach (lookaheads, character classes)
   - [ ] Doesn't match specific label text (DOB, D0B, 008)
   - [ ] Handles missing separators
   - [ ] Works on all your samples

2. **Validation Pattern:**
   - [ ] Matches expected pre-normalization format
   - [ ] Uses anchors (^ and $)
   - [ ] Handles separator variations if needed
   - [ ] Strict enough to reject invalid data

3. **Explanation:**
   - [ ] Explains WHY pattern is robust
   - [ ] Mentions structural approach
   - [ ] Acknowledges edge cases
   - [ ] References avoiding label matching

---

## Iterating on Patterns

If patterns don't work well:

1. **Show Copilot the failures:**
   ```
   This pattern failed on: "DOB10/22/1993" (no separator after label)
   Suggest a more robust pattern that handles this.
   ```

2. **Ask for alternatives:**
   ```
   Provide 3 alternative cleanup patterns with different approaches.
   ```

3. **Request simplification:**
   ```
   Can this pattern be simplified while maintaining robustness?
   ```

4. **Ask for trade-off analysis:**
   ```
   What are the trade-offs between these two patterns?
   ```

---

## File Maintenance

### When to Update These Files:

**Update `ocr_variations_examples.md`:**
- When you encounter new OCR error patterns
- When adding samples from new document types
- When discovering edge cases

**Update `pattern_examples_good_vs_bad.md`:**
- When you find better pattern approaches
- When discovering new anti-patterns
- When learning from mistakes

**Update `field_format_specifications.md`:**
- When adding new field formats
- When normalization logic changes
- When validation requirements change

**Keep `quick_reference.md` and `field_extraction_pipeline.md` stable** - Only update for major architectural changes.

---

## Additional Resources

### Testing Your Patterns
Use the zone builder's live preview to test patterns:
1. Apply cleanup pattern
2. Check validation pattern
3. See normalized output
4. Verify across all images and models

### Pattern Debugging
If patterns fail:
1. Copy all OCR outputs using "📋 Copy All" button
2. Paste into Copilot with context files
3. Show which samples fail
4. Ask for improved pattern

### Learning from Production
After deploying patterns:
1. Monitor extraction success rates
2. Collect failure samples
3. Add to `ocr_variations_examples.md`
4. Redesign patterns if needed

---

## Summary

These 5 context files teach GitHub Copilot:
1. **How** the system works (pipeline)
2. **What** variations exist (examples)
3. **Why** patterns should be structural (good vs bad)
4. **When** to use specific patterns (format specs)
5. **Quick** reference for common cases (cheatsheet)

Together, they provide comprehensive context for designing robust, maintainable OCR extraction patterns.
