"""
Zone Operations
================

Zone calculation, manipulation, and extraction logic
"""

import re
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, Counter


def validate_consensus_pattern(pattern: str) -> Tuple[bool, str]:
    """
    Validate consensus_extract pattern syntax

    Returns:
        (is_valid, error_message)
    """
    if not pattern:
        return True, ""

    try:
        # Just check for syntax errors - both approaches are valid:
        # 1. With capturing group: extracts group(1)
        # 2. Without capturing group: extracts group(0) + cleanup_pattern
        re.compile(pattern)
        return True, ""
    except re.error as e:
        return False, f"Invalid regex: {e}"


def is_in_zone(word: Dict, x_range: Tuple, y_range: Tuple) -> bool:
    """Check if word is in zone"""
    return (x_range[0] <= word['center_x'] <= x_range[1] and
            y_range[0] <= word['center_y'] <= y_range[1])


def calculate_aggregate_zone(
    images: List[Dict],
    selections: Dict[int, Set[int]],
    margin: float = 0.01
) -> Optional[Dict]:
    """
    Calculate aggregate zone from selected words across all images using min/max approach

    Args:
        images: List of image data dictionaries
        selections: Dict mapping image indices to sets of selected word indices
        margin: Safety margin to add around the zone (normalized 0-1)

    Returns:
        Zone configuration dict with x_range, y_range, and metadata
    """
    all_x_coords = []
    all_y_coords = []
    selected_texts = []

    for img_idx, word_indices in selections.items():
        if img_idx >= len(images):
            continue

        words = images[img_idx]['words']
        for word_idx in word_indices:
            if word_idx < len(words):
                word = words[word_idx]
                all_x_coords.extend([word['x1'], word['x2']])
                all_y_coords.extend([word['y1'], word['y2']])
                selected_texts.append(word['text'])

    if not all_x_coords:
        return None

    # Calculate min/max with margin
    x_min = max(0.0, min(all_x_coords) - margin)
    x_max = min(1.0, max(all_x_coords) + margin)
    y_min = max(0.0, min(all_y_coords) - margin)
    y_max = min(1.0, max(all_y_coords) + margin)

    return {
        'x_range': (round(x_min, 3), round(x_max, 3)),
        'y_range': (round(y_min, 3), round(y_max, 3)),
        'cleanup_pattern': '',
        'pattern': '',
        'format': 'string',
        'samples': len(selections),
        'total_words': sum(len(indices) for indices in selections.values()),
        'sample_texts': selected_texts[:10]  # Keep first 10 for reference
    }


def extract_from_zone(words: List[Dict], zone_config: Dict) -> str:
    """
    Extract text from zone with cleanup (NO fallback to consensus_extract)

    Pure zone-based extraction:
    1. Extract from zone only
    2. Apply cleanup pattern
    3. Return result (empty if no words in zone)
    """
    x_range = zone_config['x_range']
    y_range = zone_config['y_range']
    zone_words = [w for w in words if is_in_zone(w, x_range, y_range)]

    text = ""
    if zone_words:
        # Sort by reading order: group words on same line (Y), then left-to-right (X)
        # Round Y to 0.1 precision to group words on same horizontal line (coarser grouping)
        zone_words.sort(key=lambda w: (round(w['center_y'], 1), w['center_x']))
        text = ' '.join(w['text'] for w in zone_words)

        # Apply cleanup pattern
        cleanup = zone_config.get('cleanup_pattern', '')
        if cleanup:
            try:
                text = re.sub(cleanup, '', text, flags=re.IGNORECASE).strip()
            except:
                pass

    # NO FALLBACK to consensus_extract - zone extraction is independent from pattern extraction
    return text


def extract_from_zone_multimodel(
    ocr_result: Dict,
    zone_config: Dict,
    consensus_words: List[Dict]
) -> Dict[str, str]:
    """
    Extract text from zone showing ALL OCR model outputs

    Strategy:
    1. Find which consensus words (with geometry) are in the zone
    2. Get their indices in the full word list
    3. Extract corresponding words from each model using those indices

    Args:
        ocr_result: Full OCR API response
        zone_config: Zone configuration with x_range, y_range, etc.
        consensus_words: List of consensus words WITH geometry

    Returns:
        Dict mapping model name to extracted text
    """
    results = {}
    x_range = zone_config['x_range']
    y_range = zone_config['y_range']
    cleanup = zone_config.get('cleanup_pattern', '')

    # Find which consensus words are in the zone
    zone_word_indices = []
    for idx, word in enumerate(consensus_words):
        if is_in_zone(word, x_range, y_range):
            zone_word_indices.append(idx)

    if not zone_word_indices:
        return {}

    # Check if we have per-model outputs
    model_comparison = ocr_result.get('model_comparison', {})
    per_model_outputs = model_comparison.get('per_model_outputs', {})

    if not per_model_outputs:
        return {}

    # Extract text from each model using the same word indices
    for model_name, model_data in per_model_outputs.items():
        model_words = model_data.get('words', [])

        if not model_words:
            results[model_name] = ""
            continue

        # Extract words at the same indices as zone_word_indices
        zone_text_words = []
        for idx in zone_word_indices:
            if idx < len(model_words):
                zone_text_words.append(model_words[idx])

        if zone_text_words:
            text = ' '.join(zone_text_words)

            # Apply cleanup pattern
            if cleanup:
                try:
                    text = re.sub(cleanup, '', text, flags=re.IGNORECASE).strip()
                except:
                    pass

            results[model_name] = text
        else:
            results[model_name] = ""

    return results


def get_consensus_from_models(model_results: Dict[str, str]) -> Tuple[str, int, int]:
    """
    Calculate true consensus by voting across all models

    Returns:
        (consensus_text, vote_count, total_models)
    """
    if not model_results:
        return "", 0, 0

    vote_counts = Counter(model_results.values())
    consensus_text = vote_counts.most_common(1)[0][0] if vote_counts else ""
    vote_count = vote_counts[consensus_text] if consensus_text else 0
    total_models = len(model_results)

    return consensus_text, vote_count, total_models
