"""
Settings Manager for Zone Builder
==================================

Centralized settings management for the zone builder application.
"""

import streamlit as st
from typing import Dict, Any


# Default settings
DEFAULT_SETTINGS = {
    'display': {
        'number_size': 4,  # Changed default from 6 to 4 (2-8 range)
        'number_color': '#FF0000',  # Red
        'number_bg_color': '#FFFFFF',  # White
        'number_opacity': 0.8,  # Changed default from 0.9 to 0.8 (0-1 range)
        'box_color': '#00FF00',  # Green for selected
        'box_width': 2,
        'zone_color': '#FFA500',  # Orange for zones
        'zone_opacity': 0.3,
        'show_word_numbers': True,
        'show_word_boxes': True,
        'show_zones': True,
        'show_elements': True,  # Master toggle for all overlay elements
        'image_scale': 1.0,
    },
    'behavior': {
        'auto_save_enabled': False,
        'auto_save_interval': 5,  # minutes
        'multi_select_mode': 'ctrl',  # ctrl, shift, or always
        'confirm_before_delete': True,
        'auto_calculate_zone': True,  # Auto-calculate zone from selections
        'show_debug_info': False,
    },
    'ocr': {
        'api_url': 'http://localhost:8080/ocr',
        'include_details': True,
        'enable_field_extraction': False,
    },
    'ui': {
        'theme': 'light',  # light, dark, auto
        'compact_mode': False,
        'show_tips': True,
        'sidebar_width': 'normal',  # narrow, normal, wide
        'images_per_row': 6,
    }
}


def init_settings():
    """Initialize settings in session state if not present"""
    if 'settings' not in st.session_state:
        st.session_state.settings = DEFAULT_SETTINGS.copy()


def get_setting(category: str, key: str, default=None):
    """Get a specific setting value"""
    init_settings()
    return st.session_state.settings.get(category, {}).get(key, default)


def set_setting(category: str, key: str, value: Any):
    """Set a specific setting value"""
    init_settings()
    if category not in st.session_state.settings:
        st.session_state.settings[category] = {}
    st.session_state.settings[category][key] = value


def render_settings_panel():
    """Render simplified settings panel with only essential options"""

    # Custom CSS for very compact color pickers
    st.markdown("""
    <style>
    /* Make color picker inputs very small */
    div[data-testid="stColorPicker"] > div > div {
        width: 32px !important;
        height: 32px !important;
    }

    div[data-testid="stColorPicker"] > div > div > div {
        border-radius: 50% !important;
        border: 1px solid #ddd !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
    }

    div[data-testid="stColorPicker"] > label {
        font-size: 0.75rem !important;
        margin-bottom: 2px !important;
    }

    div[data-testid="stColorPicker"] input[type="color"] {
        width: 32px !important;
        height: 32px !important;
        border-radius: 50% !important;
        cursor: pointer !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("⚙️ Visual Settings")

    # Visibility toggle
    with st.expander("👁️ **Display Elements**", expanded=True):
        show_elements = st.checkbox(
            "Show all overlay elements (numbers, boxes, zones)",
            value=get_setting('display', 'show_elements', True),
            help="Toggle to show or hide all overlays on the image"
        )
        set_setting('display', 'show_elements', show_elements)

    # Number settings section
    with st.expander("📏 **Number Display**", expanded=True):
        # Handle old string format and convert to int
        current_size = get_setting('display', 'number_size', 4)
        if isinstance(current_size, str):
            size_map = {'small': 4, 'medium': 6, 'large': 8}
            current_size = size_map.get(current_size, 4)

        number_size = st.slider(
            "Size",
            min_value=2,
            max_value=8,
            value=current_size,
            help="Adjust the size of word numbers (2-8)"
        )
        set_setting('display', 'number_size', number_size)

        number_opacity = st.slider(
            "Opacity",
            0.0, 1.0,
            value=get_setting('display', 'number_opacity', 0.8),
            step=0.05,
            help="Number transparency (0 = hidden, 1 = fully visible)"
        )
        set_setting('display', 'number_opacity', number_opacity)

    # Colors section
    with st.expander("🎨 **Colors**", expanded=False):
        number_color = st.color_picker(
            "Number Text Color",
            value=get_setting('display', 'number_color', '#FF0000'),
            key="num_text_color",
            help="Color of the number text"
        )
        set_setting('display', 'number_color', number_color)

        number_bg_color = st.color_picker(
            "Number Background Color",
            value=get_setting('display', 'number_bg_color', '#FFFFFF'),
            key="num_bg_color",
            help="Background color behind numbers"
        )
        set_setting('display', 'number_bg_color', number_bg_color)

        box_color = st.color_picker(
            "Selected Words Color",
            value=get_setting('display', 'box_color', '#00FF00'),
            help="Color of selected word boxes",
            key="box_color_picker"
        )
        set_setting('display', 'box_color', box_color)

        zone_color = st.color_picker(
            "Zone Areas Color",
            value=get_setting('display', 'zone_color', '#FFA500'),
            help="Color of extraction zones",
            key="zone_color_picker"
        )
        set_setting('display', 'zone_color', zone_color)

    # Image display size
    with st.expander("🖼️ **Image Display**", expanded=False):
        image_scale = st.slider(
            "Image Size",
            0.5, 1.5,
            value=get_setting('display', 'image_scale', 1.0),
            step=0.1,
            help="Scale the displayed image size"
        )
        set_setting('display', 'image_scale', image_scale)

    # Reset button
    st.divider()
    if st.button("🔄 Reset Settings", use_container_width=True):
        st.session_state.settings = DEFAULT_SETTINGS.copy()
        st.success("Settings reset!")
        st.rerun()


def get_number_style() -> Dict[str, Any]:
    """Get style configuration for word numbers"""
    # Support both old string format and new numeric format
    number_size = get_setting('display', 'number_size', 6)
    if isinstance(number_size, str):
        # Legacy support
        size_map = {'small': 4, 'medium': 6, 'large': 8}
        number_size = size_map.get(number_size, 6)

    return {
        'size': number_size,
        'color': get_setting('display', 'number_color', '#FF0000'),
        'bg_color': get_setting('display', 'number_bg_color', '#FFFFFF'),
        'opacity': get_setting('display', 'number_opacity', 0.9),
    }


def get_box_style() -> Dict[str, Any]:
    """Get style configuration for selection boxes"""
    return {
        'color': get_setting('display', 'box_color', '#00FF00'),
        'width': get_setting('display', 'box_width', 2),
        'zone_color': get_setting('display', 'zone_color', '#FFA500'),
        'zone_opacity': get_setting('display', 'zone_opacity', 0.3),
    }