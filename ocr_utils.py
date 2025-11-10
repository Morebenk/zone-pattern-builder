"""
OCR Utilities
==============

OCR API interaction and word extraction
"""

import requests
from typing import Dict, List, Optional
from PIL import Image, ImageDraw


def call_ocr_api(image_bytes: bytes, filename: str, api_url: str) -> Optional[Dict]:
    """Call OCR API"""
    try:
        files = {'files': (filename, image_bytes, 'image/jpeg')}
        params = {'include_details': True, 'enable_field_extraction': False}
        response = requests.post(api_url, files=files, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
    except Exception as e:
        return None
    return None


def extract_words(ocr_result: Dict) -> List[Dict]:
    """Extract words with geometry"""
    words = []
    if 'items' in ocr_result and ocr_result['items']:
        page = ocr_result['items'][0]
        for block in page.get('blocks', []):
            for line in block.get('lines', []):
                for word in line.get('words', []):
                    geom = word.get('geometry', [])
                    text = word.get('value', '')
                    if len(geom) == 4 and text.strip():
                        x1, y1, x2, y2 = geom
                        words.append({
                            'text': text,
                            'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                            'center_x': (x1 + x2) / 2,
                            'center_y': (y1 + y2) / 2,
                        })
    return words


def draw_visualization(
    image: Image.Image,
    words: List[Dict],
    selected_indices: set,
    zones: Dict,
    current_field: str,
    show_numbers: bool = True,
    show_expanded: bool = False
) -> Image.Image:
    """Draw word boxes, selections, zones, and clickable numbers on image with improved visibility"""
    # Import settings functions
    try:
        from zone_builder.settings_manager import get_number_style, get_box_style, get_setting

        # Check if user wants to show overlay elements at all
        show_elements = get_setting('display', 'show_elements', True)

        number_style = get_number_style()
        box_style = get_box_style()
        show_zones = get_setting('display', 'show_zones', True) and show_elements
        show_boxes = get_setting('display', 'show_word_boxes', True) and show_elements
        show_numbers = get_setting('display', 'show_word_numbers', True) and show_numbers and show_elements

        # Hide numbers if opacity is 0
        if number_style.get('opacity', 1.0) == 0:
            show_numbers = False
    except:
        # Fallback if settings not available
        number_style = {'size': 10, 'color': '#FF0000', 'bg_color': '#FFFFFF', 'opacity': 0.9}
        box_style = {'color': '#00FF00', 'width': 2, 'zone_color': '#FFA500', 'zone_opacity': 0.3}
        show_zones = True
        show_boxes = True

    img = image.copy()
    draw = ImageDraw.Draw(img, 'RGBA')
    w, h = img.size

    try:
        from PIL import ImageFont
        # Use setting-based font size
        font_size = number_style['size'] + 4
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = None

    # Helper function to convert hex to RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    # Draw zones first (behind everything)
    if show_zones:
        for fname, zconf in zones.items():
            yr, xr = zconf['y_range'], zconf['x_range']
            x1_norm, x2_norm = min(xr[0], xr[1]), max(xr[0], xr[1])
            y1_norm, y2_norm = min(yr[0], yr[1]), max(yr[0], yr[1])
            x1, y1 = int(x1_norm * w), int(y1_norm * h)
            x2, y2 = int(x2_norm * w), int(y2_norm * h)

            is_current = (fname == current_field)

            # Draw expanded zone if requested
            if show_expanded and is_current:
                # Calculate 10% expansion in all directions
                expand_factor = 0.10
                x1_exp = max(0, x1_norm - expand_factor)
                x2_exp = min(1, x2_norm + expand_factor)
                y1_exp = max(0, y1_norm - expand_factor)
                y2_exp = min(1, y2_norm + expand_factor)

                x1_exp_px = int(x1_exp * w)
                y1_exp_px = int(y1_exp * h)
                x2_exp_px = int(x2_exp * w)
                y2_exp_px = int(y2_exp * h)

                # Draw expanded zone with dotted line
                for i in range(x1_exp_px, x2_exp_px, 10):
                    draw.line([(i, y1_exp_px), (i+5, y1_exp_px)], fill=(255, 0, 255, 150), width=2)
                    draw.line([(i, y2_exp_px), (i+5, y2_exp_px)], fill=(255, 0, 255, 150), width=2)
                for i in range(y1_exp_px, y2_exp_px, 10):
                    draw.line([(x1_exp_px, i), (x1_exp_px, i+5)], fill=(255, 0, 255, 150), width=2)
                    draw.line([(x2_exp_px, i), (x2_exp_px, i+5)], fill=(255, 0, 255, 150), width=2)

                # Add label for expanded zone
                draw.text((x1_exp_px + 5, y1_exp_px - 20), "Expanded Zone (Pattern Search Area)", fill=(255, 0, 255, 255))
            if is_current:
                zone_rgb = hex_to_rgb(box_style['zone_color'])
                opacity = int(box_style['zone_opacity'] * 255)
                color = zone_rgb + (opacity,)
                outline_color = zone_rgb
            else:
                color = (128, 128, 128, 50)
                outline_color = (128, 128, 128)

            draw.rectangle([x1, y1, x2, y2], fill=color, outline=outline_color + (255,), width=3 if is_current else 1)

            # Draw field name with background for visibility
            label_bg = (0, 0, 0, 200)
            if font:
                bbox = draw.textbbox((0, 0), fname, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                draw.rectangle([x1, y1, x1 + text_width + 10, y1 + text_height + 10], fill=label_bg)
                draw.text((x1 + 5, y1 + 5), fname, fill=(255, 255, 255), font=font)
            else:
                draw.rectangle([x1, y1, x1 + 80, y1 + 20], fill=label_bg)
                draw.text((x1 + 5, y1 + 5), fname, fill=(255, 255, 255))

    # Draw word boxes with improved visibility
    if show_boxes:
        for idx, word in enumerate(words):
            x1, y1 = int(word['x1'] * w), int(word['y1'] * h)
            x2, y2 = int(word['x2'] * w), int(word['y2'] * h)

            if idx in selected_indices:
                box_rgb = hex_to_rgb(box_style['color'])
                draw.rectangle([x1, y1, x2, y2], fill=box_rgb + (100,), outline=box_rgb + (255,), width=box_style['width'] + 1)
            else:
                draw.rectangle([x1, y1, x2, y2], outline=(200, 200, 200, 180), width=1)

    # Draw numbers with better visibility
    if show_numbers:
        for idx, word in enumerate(words):
            x1, y1 = int(word['x1'] * w), int(word['y1'] * h)

            number_text = str(idx + 1)

            # Calculate circle size based on number of digits
            num_digits = len(number_text)
            circle_radius = (number_style['size'] + 3) * (1 + num_digits * 0.2)

            # Position number above the word box
            number_x = x1 + circle_radius
            number_y = y1 - circle_radius - 5

            # Keep within bounds
            if number_y - circle_radius < 0:
                number_y = y1 + circle_radius + 5
            if number_x - circle_radius < 0:
                number_x = circle_radius
            if number_x + circle_radius > w:
                number_x = w - circle_radius

            # Draw shadow for better visibility
            shadow_offset = 2
            draw.ellipse(
                [number_x - circle_radius + shadow_offset, number_y - circle_radius + shadow_offset,
                 number_x + circle_radius + shadow_offset, number_y + circle_radius + shadow_offset],
                fill=(0, 0, 0, 100)
            )

            # Draw white background circle
            bg_rgb = hex_to_rgb(number_style['bg_color'])
            opacity = int(number_style['opacity'] * 255)
            draw.ellipse(
                [number_x - circle_radius, number_y - circle_radius,
                 number_x + circle_radius, number_y + circle_radius],
                fill=bg_rgb + (opacity,),
                outline=(0, 0, 0, 255),
                width=2
            )

            # Draw number with better centering
            num_rgb = hex_to_rgb(number_style['color'])
            if font:
                draw.text((number_x, number_y), number_text, fill=num_rgb + (255,), font=font, anchor='mm')
            else:
                draw.text((number_x, number_y), number_text, fill=num_rgb + (255,), anchor='mm')

    return img
