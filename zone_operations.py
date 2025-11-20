"""
Zone Operations - Zone Builder Specific UI Functions
=====================================================

REFACTORED: Minimal zone-builder-specific functions only.
All extraction logic now lives in shared app.field_extraction module.

Functions kept here:
- validate_consensus_pattern: UI regex validation
- calculate_aggregate_zone: UI aggregate zone calculation
- extract_from_zone_multimodel_with_words: Zone builder multi-model display
"""

import re
from typing import Dict, List, Optional, Tuple, Set, Any

# Import from shared modules (single source of truth)
try:
    # Try importing when run from main app
    from app.field_extraction.core import ZoneExtractionPipeline
    from app.field_extraction.processing import (
        is_in_zone,
        get_consensus_from_models,
        match_boxes_to_model_words
    )
except ImportError:
    # Fallback when run standalone (add parent dir to path)
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.field_extraction.core import ZoneExtractionPipeline
    from app.field_extraction.processing import (
        is_in_zone,
        get_consensus_from_models,
        match_boxes_to_model_words
    )


def validate_consensus_pattern(pattern: str) -> Tuple[bool, str]:
    """
    Validate consensus_extract pattern syntax (UI validation)

    Returns:
        (is_valid, error_message)
    """
    if not pattern:
        return True, ""

    try:
        re.compile(pattern)
        return True, ""
    except re.error as e:
        return False, f"Invalid regex: {e}"


def apply_clustering(zone_words: List[Dict], zone_config: Dict) -> List[Dict]:
    """
    Apply clustering to zone words (Zone Builder UI wrapper).

    Delegates to the shared ZoneExtractionPipeline clustering logic.

    Args:
        zone_words: Words in the zone
        zone_config: Zone config with clustering parameters

    Returns:
        Filtered list of words (the selected cluster)
    """
    # Use the shared pipeline's clustering
    pipeline = ZoneExtractionPipeline()
    return pipeline._apply_clustering(zone_words, zone_config)


def calculate_aggregate_zone(
    images: List[Dict],
    selections: Dict[int, Set[int]],
    margin: float = 0.01
) -> Optional[Dict]:
    """
    Calculate aggregate zone from selected words across images (UI-specific)

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
        'sample_texts': selected_texts[:10]
    }


def extract_from_zone(words: List[Dict], zone_config: Dict) -> str:
    """
    Extract text from zone with clustering and cleanup (Zone Builder UI wrapper).

    This is a simple wrapper for the Zone Builder UI that uses the shared pipeline.

    Args:
        words: List of word dictionaries with geometry
        zone_config: Zone configuration dict

    Returns:
        Extracted text string
    """
    x_range = zone_config['x_range']
    y_range = zone_config['y_range']

    # Filter words to zone (skip noise-flagged detections)
    zone_words = [
        w for w in words
        if is_in_zone(w, x_range, y_range) and not w.get('is_noise', False)
    ]

    # Use shared pipeline for extraction
    pipeline = ZoneExtractionPipeline()
    return pipeline.extract_from_zone(zone_words, zone_config) or ""


def extract_from_zone_multimodel(
    ocr_result: Dict,
    zone_config: Dict,
    consensus_words: List[Dict]
) -> Dict[str, str]:
    """
    Extract text from zone for ALL OCR models (Zone Builder UI wrapper).

    Returns:
        Dict mapping model name to extracted text
    """
    results_with_words = extract_from_zone_multimodel_with_words(
        ocr_result, zone_config, consensus_words
    )
    # Extract just the text from (text, words) tuples
    return {model: text for model, (text, words) in results_with_words.items()}


def extract_from_zone_multimodel_with_words(
    ocr_result: Dict,
    zone_config: Dict,
    consensus_words: List[Dict]
) -> Dict[str, Tuple[str, List[Dict]]]:
    """
    Extract text AND word objects from zone for ALL OCR models (Zone Builder UI)

    This is zone-builder specific - shows per-model outputs in the UI.

    Returns:
        Dict mapping model name to (text, word_objects_list) tuple
    """
    results = {}
    x_range = zone_config['x_range']
    y_range = zone_config['y_range']

    # Find which consensus words are in the zone
    zone_word_boxes = []
    for word in consensus_words:
        if is_in_zone(word, x_range, y_range) and not word.get('is_noise', False):
            zone_word_boxes.append({
                'center_x': word.get('center_x'),
                'center_y': word.get('center_y'),
                'x1': word.get('x1'),
                'y1': word.get('y1'),
                'x2': word.get('x2'),
                'y2': word.get('y2'),
            })

    if not zone_word_boxes:
        return {}

    # Check if we have per-model outputs
    model_comparison = ocr_result.get('model_comparison', {})
    per_model_outputs = model_comparison.get('per_model_outputs', {})

    if not per_model_outputs:
        return {}

    # Get all words with geometry from OCR result
    all_words_with_geom = []
    if 'items' in ocr_result and ocr_result['items']:
        page = ocr_result['items'][0]
        for block in page.get('blocks', []):
            for line in block.get('lines', []):
                for word_obj in line.get('words', []):
                    geom = word_obj.get('geometry', [])
                    if len(geom) == 4:
                        x1, y1, x2, y2 = geom
                        all_words_with_geom.append({
                            'value': word_obj.get('value', ''),
                            'center_x': (x1 + x2) / 2,
                            'center_y': (y1 + y2) / 2,
                            'x1': x1,
                            'y1': y1,
                            'x2': x2,
                            'y2': y2,
                        })

    # Use shared zone extraction pipeline
    pipeline = ZoneExtractionPipeline()

    # Extract text AND words from each model using GEOMETRY matching
    for model_name, model_data in per_model_outputs.items():
        model_words = model_data.get('words', [])

        if not model_words or len(model_words) != len(all_words_with_geom):
            results[model_name] = ("", [])
            continue

        # Match zone boxes to model words by geometry (shared utility)
        zone_word_objects = match_boxes_to_model_words(
            zone_word_boxes,
            all_words_with_geom,
            model_words
        )

        # Use shared pipeline extraction
        text = pipeline.extract_from_zone(zone_word_objects, zone_config)
        results[model_name] = (text, zone_word_objects if text else [])

    return results
