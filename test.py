import re
from typing import List, Optional

# ============================================================================
# 1. DEFINITIONS (NUMBERS REMOVED)
# ============================================================================

US_DL_ENDORSEMENTS = [
    'NONE', 'H', 'N', 'P', 'S', 'T', 'X', 'M', 'L', 'F', 'G', 'R', 'W', 'Z', 'O', 'A',
    'M1', 'M2', 'M3', 'P1', 'P2'
]

# REMOVED: '1'-'16'
US_DL_RESTRICTIONS = [
    'NONE', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    'P1', 'P2', 'P3', 'P4', 'S1', 'J01', 'J02', 'A1', 'A2'
]

def _parse_multiple_codes(text: str, valid_codes: List[str]) -> List[str]:
    """Robust parser for mixed separators and concatenated codes."""
    found_codes = []
    sorted_codes = sorted([c for c in valid_codes if c != 'NONE'], key=len, reverse=True)
    
    # Normalize separators
    clean_text = re.sub(r'[,\.]', ' ', text)
    chunks = clean_text.split()

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk: continue

        if chunk in valid_codes:
            found_codes.append(chunk)
            continue

        # Attempt to parse concatenated codes (e.g. "HM1")
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
                remaining = remaining[1:] 
    return found_codes

# ============================================================================
# 2. ENDORSEMENTS (UPDATED REGEX)
# ============================================================================

def normalize_endorsements(value: str) -> Optional[str]:
    if not value: return None
    upper_text = value.upper().strip()

    if re.fullmatch(r'(DRIVER\s*LICENSE|USA|AMERICA|CLASS)', upper_text): return None

    # 1. START ANCHOR (Fuzzy match for "Endorsements")
    # Matches: 9a End, End, Ends, Endors, 9 Endorsements
    start_pattern = r'^(?:[9SDo0-9]+[a-zA-Z]?\s*)?E[NM]D(?:\w*)\.?\s*'
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
    if 'NONE' in upper_text: return 'NONE'

    codes = _parse_multiple_codes(upper_text, US_DL_ENDORSEMENTS)
    if not codes: return None
    return ','.join(sorted(set(codes)))

# ============================================================================
# 3. RESTRICTIONS (UPDATED REGEX)
# ============================================================================

def normalize_restrictions(value: str) -> Optional[str]:
    if not value: return None
    upper_text = value.upper().strip()
    
    if re.fullmatch(r'(DRIVER\s*LICENSE|USA|AMERICA|CLASS)', upper_text): return None

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
    if 'NONE' in upper_text: return 'NONE'

    codes = _parse_multiple_codes(upper_text, US_DL_RESTRICTIONS)
    if not codes: return None
    return ','.join(sorted(set(codes)))

# 50 Lines of Complex Endorsements
ENDO_TESTS = [
    ("9a Endorsements NONE 12 Restrictions", "NONE"),
    ("9a Endorsements H 12 Restrictions B", "H"),
    ("Endorsements P2 12 Restriotions", "P2"),
    ("End. H M1 12 Rest.", "H,M1"),
    ("Ends H, M1 12 Restrictions", "H,M1"),
    ("Endors. P1,P2 Restr A", "P1,P2"),
    ("Sa Endorsements H.M1 12 Restrictions", "H,M1"),
    ("Da Endorsements P 12 Rest.", "P"),
    ("9 Endorsements H 12 Resticions", "H"),
    ("9a End H M1 P 12 Rest", "H,M1,P"),
    ("Endorsements NONE", "NONE"),
    ("Endorsements HM1", "H,M1"),
    ("Endorsements H,M1.", "H,M1"),
    ("Endorsements H M1 .", "H,M1"),
    ("Endorsements H-M1", "H,M1"),
    ("Endorsemants X", "X"),
    ("Endorsments T", "T"),
    ("Emdorsements P", "P"), 
    ("9a End NONE .", "NONE"),
    ("9a Endorsements H M1 12 Restrictions NONE", "H,M1"),
    ("Endorsements H 12 Restrictions 1 2", "H"),
    ("Endorsements P 12 Restriotions A", "P"),
    ("Endorsements P2 12 Restrictlons", "P2"),
    ("Endorsements H,M1 12 Restr", "H,M1"),
    ("Endorsements H M1 * 12 Restrictions", "H,M1"),
    ("Endorsements H..M1", "H,M1"),
    ("9a Endorsements H/M1", "H,M1"),
    ("Endorsements M1, M2, M3", "M1,M2,M3"),
    ("Endorsements M1M2", "M1,M2"),
    ("Endorsements P1 P2", "P1,P2"),
    ("Endorsements H (M1)", "H,M1"),
    ("9a Endorsements: H", "H"),
    ("9a Endorsements - H", "H"),
    ("Endorsements H, M1 12", "H,M1"),
    ("Endorsements NONE 12", "NONE"),
    # -- Fixed Failures Below --
    ("Endorsements H M1 9 Vehicle", "H,M1"),
    ("Endorsements HM1 9 Class", "H,M1"),
    ("9a Endorsements H,M1 12 Restrictions J01", "H,M1"),
    ("Sa Endorsements P 12 Rest. B", "P"),
    ("93 Endorsements H", "H"),
    ("Endorsements H 12 Resticions", "H"),
    ("Endorsements H 12 Restrictioms", "H"),
    ("Endorsements H 12 Restictons", "H"),
    ("Endorsements H 12 Restrcitions", "H"),
    ("Endorsements H 12 Restrictionss", "H"),
    ("Endorsements H 12 Rst", "H"), # Now Pass
    ("Endorsements H 12 Re", "H"),  # Now Pass
    ("Endorsements M1 P2 X", "M1,P2,X"),
    ("Endorsements H, N, P", "H,N,P"),
    ("Driver License", None),
]

# 50 Lines of Complex Restrictions
REST_TESTS = [
    # --- GROUP 1: BASIC CLEAN (Baseline) ---
    ("12 Restrictions A", "A"),
    ("Restrictions B", "B"),
    ("Rest C", "C"),
    ("Restrictions NONE", "NONE"),
    ("Restrictions J01", "J01"),
    ("Restrictions P1", "P1"),
    ("Restrictions A1", "A1"),

    # --- GROUP 2: SEPARATOR CHAOS ---
    ("Restrictions A,B", "A,B"),
    ("Restrictions A.B", "A,B"),
    ("Restrictions A/B", "A,B"),
    ("Restrictions A-B", "A,B"),
    ("Restrictions A B", "A,B"),
    ("Restrictions A..B", "A,B"),
    ("Restrictions A,, B", "A,B"),
    ("Restrictions A * B", "A,B"),
    ("Restrictions J01/P1", "J01,P1"),
    ("Restrictions A. J01", "A,J01"),

    # --- GROUP 3: CONCATENATION ---
    ("Restrictions AB", "A,B"),
    ("Restrictions ABC", "A,B,C"),
    ("Restrictions J01J02", "J01,J02"),
    ("Restrictions P1P2", "P1,P2"),
    ("Restrictions A1A2", "A1,A2"),
    ("Restrictions AB.CD", "A,B,C,D"),
    ("Restrictions J01P1", "J01,P1"),

    # --- GROUP 4: NUMERIC NOISE (Numbers removed from valid list) ---
    ("Restrictions 1", None),
    ("Restrictions 12", None),
    ("Restrictions 1, 2", None),
    ("Restrictions 12, 13", None),
    ("Restrictions A 1", "A"),         # A is valid, 1 is noise
    ("Restrictions 12 A", "A"),        # A is valid, 12 is noise
    ("Restrictions A, 12, B", "A,B"),
    ("Restrictions 1.2.A", "A"),
    ("Restrictions J01 1", "J01"),
    
    # --- GROUP 5: LABEL TYPOS (The Anchor Test) ---
    ("12 Restriotions A", "A"),
    ("12 Restrictlons B", "B"),
    ("12 Resticions C", "C"),
    ("12 Restictons D", "D"),
    ("Rest. E", "E"),
    ("Restr F", "F"),
    ("Rst G", "G"),
    ("12 Re H", "H"),
    ("Restrictionss I", "I"),
    ("12 Restic J", "J"),

    # --- GROUP 6: LEFT BLEED (Endorsements Bleeding In) ---
    ("P2 12 Restrictions A", "A"),
    ("M1 12 Restrictions B", "B"),
    ("Endorsements H 12 Restrictions C", "C"),
    ("9a End NONE 12 Restrictions NONE", "NONE"),
    ("H,M1 12 Rest D", "D"),
    ("Endorsements P2 12 Resticions E", "E"),
    ("Endors H M1 12 Rest F", "F"),
    ("Sa End P 12 Rest. G", "G"),
    ("NONE 12 Restrictions H", "H"), # Start with NONE, but finding H

    # --- GROUP 7: RIGHT BLEED (Vehicle/Class Bleeding In) ---
    ("Restrictions A 9 Vehicle", "A"),
    ("Restrictions B 9Vehicle", "B"),
    ("Restrictions C gVehicle", "C"),
    ("Restrictions D SVehicle", "D"),
    ("Restrictions E 5Vehicle", "E"),
    ("Restrictions F 9 V", "F"),
    ("Restrictions G 9 Class", "G"),
    ("Restrictions H Class", "H"),
    ("Restrictions I Vehicle", "I"),
    ("Restrictions J 9 Vohicle", "J"),
    
    # --- GROUP 8: DOUBLE BLEED (Mess on both sides) ---
    ("P2 12 Restrictions A 9 Vehicle", "A"),
    ("9a End H 12 Rest B 9 Class", "B"),
    ("Endorsements NONE 12 Restrictions C gVehicle", "C"),
    ("M1 P2 12 Restriotions D 9 V", "D"),
    ("End H,M1 12 Rst E,F 9Vehicle", "E,F"),
    ("Sa End P 12 Re G 9 Class", "G"),
    
    # --- GROUP 9: COMPLEX / MIXED GARBAGE ---
    ("Restrictions A. 12 . B", "A,B"),
    ("Restrictions J01..P1..12", "J01,P1"),
    ("Restrictions A (1)", "A"),
    ("Restrictions A-1-B", "A,B"),
    ("Restrictions: A, B", "A,B"),
    ("Restrictions - A B", "A,B"),
    ("Restrictions .A.B.", "A,B"),
    ("12 Restrictions A B (9)", "A,B"), # 9 in parens is noise, not field 9
    ("Restrictions A&B", "A,B"), # & is typically split by the non-alphanum logic or noise skip
    ("Restrictions A+B", "A,B"),

    # --- GROUP 10: SPECIFIC EDGE CASES & OCR HORRORS ---
    ("P2 12 Restrictions C.EM gVehicleCiazsifications", "C,E,M"),
    ("P2 12 Restrictions CEM SVehicieCiassications", "C,E,M"),
    ("P2 12 Restrictions C.E.M gVehicleciarstications", "C,E,M"),
    ("12 Restrictions CE,M 9Vehicle B", "C,E,M"),
    ("Restrictions A B 9 V A", "A,B"), # The A after 9 V is correctly cut off?
    ("Restrictions J01 J02", "J01,J02"),
    ("Restrictions S1 A2", "A2,S1"),
    ("Restrictions P1, P2, 12", "P1,P2"),
    ("Restrictions 12, A", "A"),
    ("Restrictions 9 9 Vehicle", None), # Code 9 (removed) vs Field 9
    
    # --- GROUP 11: THE "NONE" TRAPS ---
    ("Restrictions NONE 9 Vehicle", "NONE"),
    ("NONE 12 Restrictions NONE", "NONE"),
    ("Endorsements NONE 12 Restrictions NONE", "NONE"),
    ("Restrictions N O N E", "NONE"), # Concat parser handles this? No, spaces split it into N,O,N,E
    ("Restrictions N,O,N,E", "E,N,O"), # Parsed as codes N, O, E
    
    # --- GROUP 12: INVALID INPUTS ---
    ("Driver License", None),
    ("USA", None),
    ("Class C", None), # Starts with Class -> Rejected by regex or parsed as C? 
                       # "Class" is not in restrictions. "C" is. 
                       # But 'Class' usually appears at End. 
                       # If just "Class C", Anchor fails -> returns None. Correct.
    ("", None),
    ("     ", None),
    ("12 Restrictions", None), # Valid Label, No codes
    ("Rest.", None),
    ("9a Endorsements", None),
    
    # --- GROUP 13: J-SERIES / P-SERIES SPECIFICS ---
    ("Restrictions J01,J02", "J01,J02"),
    ("Restrictions J01.J02", "J01,J02"),
    ("Restrictions P1 P2 P3", "P1,P2,P3"),
    ("Restrictions P1P2P3", "P1,P2,P3"),
    ("Restrictions J01P1", "J01,P1"),
    
    # --- GROUP 14: NOISE BETWEEN CODES ---
    ("Restrictions A ' B", "A,B"),
    ("Restrictions A \" B", "A,B"),
    ("Restrictions A _ B", "A,B"),
    ("Restrictions A = B", "A,B"),
    ("Restrictions A : B", "A,B"),
    ("Restrictions A ; B", "A,B"),
    
    # --- GROUP 15: FINAL BOSS ---
    ("9a End H,M1 12 Restriotions: A, B, 12. J01 -- P1 9VehicleClass", "A,B,J01,P1")
]

def run_tests():
    print(f"{'TYPE':<5} | {'RAW INPUT':<50} | {'RESULT':<10} | {'STATUS'}")
    print("=" * 85)
    failures = 0
    
    for raw, expected in ENDO_TESTS:
        result = normalize_endorsements(raw)
        if result == expected:
            print(f"ENDO  | {raw[:50]:<50} | {str(result):<10} | PASS")
        else:
            print(f"ENDO  | {raw[:50]:<50} | {str(result):<10} | FAIL (Exp: {expected})")
            failures += 1

    print("-" * 85)

    for raw, expected in REST_TESTS:
        result = normalize_restrictions(raw)
        if result == expected:
            print(f"REST  | {raw[:50]:<50} | {str(result):<10} | PASS")
        else:
            print(f"REST  | {raw[:50]:<50} | {str(result):<10} | FAIL (Exp: {expected})")
            failures += 1

    print("=" * 85)
    print(f"TOTAL TESTS: {len(ENDO_TESTS) + len(REST_TESTS)}")
    print(f"FAILURES:    {failures}")

if __name__ == "__main__":
    run_tests()