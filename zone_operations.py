"""
Zone Operations
================

Zone calculation, manipulation, and extraction logic
"""

import re
from typing import Dict, List, Optional, Tuple, Set, Any
from collections import defaultdict, Counter

# Import clustering functions from production
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.field_extraction.processing.geometry import (
    cluster_words_by_position,
    select_value_cluster
)
from app.field_extraction.processing.cleaners import filter_labels


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


def apply_clustering(zone_words: List[Dict], zone_config: Dict) -> List[Dict]:
    """
    Apply clustering to separate labels from values (simulates production ExtractionPipeline)

    Args:
        zone_words: Words in the zone (with 'parsed' geometry or direct coords)
        zone_config: Zone config with clustering parameters:
            - cluster_by: 'y' (horizontal lines) or 'x' (vertical columns)
            - cluster_select: 'lowest', 'highest', 'rightmost', 'leftmost', 'largest'
            - cluster_tolerance: float (default 0.02)
            - pattern: Optional validation pattern
            - label_patterns: Optional list of regex patterns for template-specific labels
            - format: Optional field type for quality scoring (name, date, etc.)

    Returns:
        Filtered list of words (the selected cluster), or original words if clustering fails
    """
    if not zone_words:
        return zone_words

    cluster_by = zone_config.get('cluster_by')
    if not cluster_by:
        return zone_words

    cluster_select = zone_config.get('cluster_select', 'lowest')
    cluster_tolerance = zone_config.get('cluster_tolerance', 0.02)
    pattern = zone_config.get('pattern')
    label_patterns = zone_config.get('label_patterns')  # Get template-specific label patterns
    field_type = zone_config.get('format')  # Get field type for quality scoring

    # Convert zone_builder word format to production format (needs 'parsed' dict)
    words_for_clustering = []
    for word in zone_words:
        # Check if already has 'parsed' dict, otherwise create it
        if 'parsed' not in word:
            word_copy = word.copy()
            word_copy['parsed'] = {
                'center_x': word.get('center_x'),
                'center_y': word.get('center_y'),
                'x1': word.get('x1'),
                'y1': word.get('y1'),
                'x2': word.get('x2'),
                'y2': word.get('y2'),
            }
            words_for_clustering.append(word_copy)
        else:
            words_for_clustering.append(word)

    # Step 1: Cluster words by position
    clusters = cluster_words_by_position(
        words_for_clustering,
        axis=cluster_by,
        tolerance=cluster_tolerance
    )

    if not clusters:
        return zone_words

    # Step 2: Rank clusters and filter labels
    ranked_clusters = select_value_cluster(
        clusters,
        strategy=cluster_select,
        label_patterns=label_patterns,
        field_type=field_type
    )

    if not ranked_clusters:
        return zone_words

    # Step 3: Try each ranked cluster, return first valid one
    for candidate_cluster in ranked_clusters:
        # Validate if pattern is provided
        if pattern:
            combined_text = ' '.join(w.get('text', '') for w in candidate_cluster).strip()
            if not re.match(pattern, combined_text):
                continue  # Try next cluster

        # Sort selected cluster by X position for left-to-right reading
        selected = sorted(candidate_cluster, key=lambda w: w.get('parsed', {}).get('center_x', 0))
        return selected

    # If no valid cluster found, return original words
    return zone_words


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
    Extract text from zone with clustering and cleanup (matches production pipeline.py)

    Zone-based extraction flow:
    1. Extract from zone only (skip noise-flagged detections)
    2. Apply clustering if configured (separates labels from values)
    3. Sort and build text
    4. Apply cleanup pattern
    5. Return result (empty if no words in zone)
    """
    x_range = zone_config['x_range']
    y_range = zone_config['y_range']
    # Skip noise-flagged detections
    zone_words = [w for w in words if is_in_zone(w, x_range, y_range) and not w.get('is_noise', False)]

    # Apply clustering if configured (matches production pipeline.py)
    if zone_config.get('cluster_by'):
        zone_words = apply_clustering(zone_words, zone_config)

    text = ""
    if zone_words:
        # Sort by reading order: group words on same line (Y), then left-to-right (X)
        # Round Y to 0.1 precision to group words on same horizontal line (coarser grouping)
        # Handle both direct coords and parsed dict (after clustering, words have parsed dict)
        def get_center(w, coord):
            if 'parsed' in w:
                return w['parsed'].get(f'center_{coord}', 0)
            return w.get(f'center_{coord}', 0)

        zone_words.sort(key=lambda w: (round(get_center(w, 'y'), 1), get_center(w, 'x')))
        text = ' '.join(w.get('text', '') for w in zone_words)

        # Apply cleanup pattern
        cleanup = zone_config.get('cleanup_pattern', '')
        if cleanup:
            try:
                text = re.sub(cleanup, '', text, flags=re.IGNORECASE).strip()
            except:
                pass

    # NO FALLBACK to consensus_extract - zone extraction is independent from pattern extraction
    return text


def extract_from_zone_multimodel_with_words(
    ocr_result: Dict,
    zone_config: Dict,
    consensus_words: List[Dict]
) -> Dict[str, Tuple[str, List[Dict]]]:
    """
    Extract text AND word objects from zone showing ALL OCR model outputs

    NOTE: This is used by BOTH zone-based AND pattern-based extraction.
    - For zone-based: clustering is applied if configured
    - For pattern-based: clustering should NOT be in zone_config (removed in interactive_zone_builder_v2.py)

    Returns:
        Dict mapping model name to (text, word_objects_list) tuple
    """
    results = {}
    x_range = zone_config['x_range']
    y_range = zone_config['y_range']

    # Find which consensus words are in the zone (store their geometry, skip noise)
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

    # Get all words with geometry from OCR result (to match against)
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

    # Extract text AND words from each model using GEOMETRY matching
    for model_name, model_data in per_model_outputs.items():
        model_words = model_data.get('words', [])

        if not model_words or len(model_words) != len(all_words_with_geom):
            # Fallback: if word count doesn't match, skip this model
            results[model_name] = ("", [])
            continue

        # Match zone boxes to model words by geometry - build word objects
        zone_word_objects = []
        for zone_box in zone_word_boxes:
            # Find the word in all_words_with_geom that matches this box
            best_match_idx = None
            min_distance = float('inf')

            for idx, geom_word in enumerate(all_words_with_geom):
                # Calculate distance between centers
                dx = geom_word['center_x'] - zone_box['center_x']
                dy = geom_word['center_y'] - zone_box['center_y']
                distance = dx*dx + dy*dy

                if distance < min_distance and distance < 0.001:  # Very close match (1mm tolerance)
                    min_distance = distance
                    best_match_idx = idx

            # If found a matching box, get the text from that index in model_words
            if best_match_idx is not None and best_match_idx < len(model_words):
                zone_word_objects.append({
                    'text': model_words[best_match_idx],
                    'center_x': zone_box['center_x'],
                    'center_y': zone_box['center_y'],
                    'x1': zone_box['x1'],
                    'y1': zone_box['y1'],
                    'x2': zone_box['x2'],
                    'y2': zone_box['y2'],
                })

        # Apply clustering if configured
        # NOTE: For pattern-based extraction, cluster_by should NOT be in zone_config
        if zone_word_objects and zone_config.get('cluster_by'):
            zone_word_objects = apply_clustering(zone_word_objects, zone_config)
            # Clustering already sorts selected cluster by X position, no need to sort again

        # Build text from zone words (preserves order from zone_word_boxes or clustering)
        if zone_word_objects:
            text = ' '.join(w.get('text', '') for w in zone_word_objects)

            # Apply cleanup pattern
            cleanup = zone_config.get('cleanup_pattern', '')
            if cleanup:
                try:
                    text = re.sub(cleanup, '', text, flags=re.IGNORECASE).strip()
                except:
                    pass

            results[model_name] = (text, zone_word_objects)
        else:
            results[model_name] = ("", [])

    return results


def extract_from_zone_multimodel(
    ocr_result: Dict,
    zone_config: Dict,
    consensus_words: List[Dict]
) -> Dict[str, str]:
    """
    Extract text from zone showing ALL OCR model outputs

    Returns:
        Dict mapping model name to extracted text
    """
    results_with_words = extract_from_zone_multimodel_with_words(ocr_result, zone_config, consensus_words)
    # Extract just the text from (text, words) tuples
    return {model: text for model, (text, words) in results_with_words.items()}


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
