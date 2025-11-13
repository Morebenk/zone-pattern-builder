"""
Interactive Zone Builder - Restructured Version
===============================================

Optimized workflow for zone and pattern-based extraction configuration.
"""

import streamlit as st
import re
from pathlib import Path
from PIL import Image
from typing import List
from collections import defaultdict, Counter
import io
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modular components
from zone_builder.field_formats import (
    FIELD_FORMATS, DATE_FORMATS, HEIGHT_FORMATS, WEIGHT_FORMATS,
    get_date_pattern, get_height_pattern, get_weight_pattern,
    auto_detect_format
)
from zone_builder.exporters import (
    export_to_json, export_to_python, preview_zone_status
)
from zone_builder.zone_operations import (
    calculate_aggregate_zone, extract_from_zone, extract_from_zone_multimodel,
)
from zone_builder.ocr_utils import (
    call_ocr_api, extract_words, draw_visualization
)
from zone_builder.field_normalizers import (
    normalize_field
)
from zone_builder.session_manager import (
    save_session, load_session, load_template_file
)
from zone_builder.settings_manager import (
    init_settings, get_setting, set_setting, render_settings_panel
)

# Page configuration
st.set_page_config(
    page_title="Zone Builder Pro",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize settings
init_settings()

# Field definitions
USA_FIELDS = [
    "document_number", "license_class", "date_of_birth", "expiration_date",
    "issue_date", "first_name", "last_name", "address", "endorsement",
    "restriction", "sex", "hair", "eyes", "height", "weight", "dd_code"
]
FRANCE_FIELDS = [
    "document_number", "nationality", "last_name", "alternate_name",
    "first_name", "sex", "date_of_birth", "birth_place", "height",
    "address", "expiration_date", "issue_date", "issuing_authority"
]

# Session state initialization with robust error handling
def init_session_state():
    """Initialize session state with proper type checking and error recovery"""
    defaults = {
        'images': [],
        'zones': {},
        'selections': defaultdict(set),
        'current_field': None,
        'current_image_idx': 0,
        'field_filter': 'All',
        'view_mode': 'build',
        'config_expanded': True
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
        else:
            # Validate existing values and fix if corrupted
            if key == 'images' and not isinstance(st.session_state[key], list):
                st.session_state[key] = []
            elif key == 'zones' and not isinstance(st.session_state[key], dict):
                st.session_state[key] = {}
            elif key == 'selections':
                # Ensure selections is always a defaultdict
                if not isinstance(st.session_state[key], defaultdict):
                    if isinstance(st.session_state[key], dict):
                        st.session_state[key] = defaultdict(set, st.session_state[key])
                    else:
                        st.session_state[key] = defaultdict(set)
            elif key == 'current_image_idx' and not isinstance(st.session_state[key], int):
                st.session_state[key] = 0

init_session_state()

# Minimal CSS with proper header spacing
st.markdown("""
<style>
    .block-container {
        padding-top: 4rem;
        max-width: 100%;
    }
    .stButton > button {
        white-space: nowrap;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def get_filtered_fields(filter_type: str) -> List[str]:
    """Get field list based on filter"""
    if filter_type == "USA":
        return USA_FIELDS
    elif filter_type == "France":
        return FRANCE_FIELDS
    return list(dict.fromkeys(USA_FIELDS + FRANCE_FIELDS))  # All, remove duplicates


def process_extraction_result(consensus_text: str, zone_config: dict, field_name: str = None) -> tuple:
    """
    Process extraction result: normalize, validate

    NOTE: Cleanup pattern is NOT applied here - it's already applied in extract_from_zone_multimodel.
    Applying it twice would cause incorrect results (production only applies it once).
    """
    # Normalize
    field_format = zone_config.get('format', 'string')
    format_options = {}
    if field_format == 'date':
        format_options['date_format'] = zone_config.get('date_format', 'MM.DD.YYYY')
    elif field_format == 'height':
        format_options['height_format'] = zone_config.get('height_format', 'auto')
    elif field_format == 'weight':
        format_options['weight_format'] = zone_config.get('weight_format', 'auto')

    # Pass field_name for field-specific cleaning (name/address fields)
    normalized_text = normalize_field(consensus_text, field_format, field_name, **format_options) if consensus_text else None

    # Validate
    pattern = zone_config.get('pattern', '')
    is_valid = bool(re.match(pattern, normalized_text)) if pattern and normalized_text else bool(normalized_text)

    return consensus_text, normalized_text, is_valid, field_format, format_options


def render_model_outputs(model_results: dict, field_format: str, format_options: dict, pattern: str, field_name: str = None):
    """Render per-model outputs with colorful styling"""
    if not model_results:
        return

    st.markdown("**📊 Model Outputs:**")
    model_colors = {
        'parseq': '#4CAF50', 'crnn': '#2196F3', 'vitstr': '#FF9800',
        'sar': '#9C27B0', 'viptr': '#F44336'
    }

    for model_name, model_text in sorted(model_results.items()):
        # Display empty strings as "(no match)" for clarity
        display_text = model_text if model_text else "(no match)"

        # Model outputs get field_name for proper cleaning
        model_normalized = normalize_field(model_text, field_format, field_name, **format_options) if model_text else None
        model_valid = bool(re.match(pattern, model_normalized)) if pattern and model_normalized else bool(model_normalized)

        status = "✅" if model_valid else "❌"
        color = model_colors.get(model_name, '#666666')

        # Create styled HTML output
        if model_text and model_text != model_normalized and model_normalized:
            output_html = f"""
            <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {color}15, transparent); border-left: 3px solid {color}; border-radius: 4px;">
                <span style="color: {color}; font-weight: bold; font-size: 14px;">
                    {status} {model_name.upper()}:
                </span>
                <span style="color: #666; margin-left: 10px; font-family: monospace;">
                    {display_text}
                </span>
                <span style="color: #999; margin: 0 5px;">→</span>
                <span style="color: #333; font-weight: 500; font-family: monospace;">
                    {model_normalized}
                </span>
            </div>
            """
        else:
            output_html = f"""
            <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {color}15, transparent); border-left: 3px solid {color}; border-radius: 4px;">
                <span style="color: {color}; font-weight: bold; font-size: 14px;">
                    {status} {model_name.upper()}:
                </span>
                <span style="color: #333; margin-left: 10px; font-family: monospace;">
                    {display_text}
                </span>
            </div>
            """
        st.markdown(output_html, unsafe_allow_html=True)


def render_per_image_expandable(img_idx: int, img_data: dict, consensus_text: str, normalized_text: str,
                                is_valid: bool, vote_count: int, total_models: int, model_results: dict,
                                field_format: str, format_options: dict, pattern: str, field_name: str = None,
                                empty_msg: str = "(empty)"):
    """Render expandable section for a single image"""
    status_icon = "✅" if is_valid else "❌"
    display_text = normalized_text or consensus_text or empty_msg

    with st.expander(f"{status_icon} {img_data['name'][:30]}: {display_text[:30]}", expanded=(img_idx == 0)):
        st.markdown(f"**🏆 Consensus** ({vote_count}/{total_models} models agree):")

        col1, col2 = st.columns([3, 1])
        with col1:
            if consensus_text != normalized_text and normalized_text:
                st.text("Raw extracted:")
                st.code(consensus_text or empty_msg)
                st.text("After normalization:")
                st.code(normalized_text)
            else:
                st.code(consensus_text or empty_msg)

        with col2:
            st.metric("Status", "Valid" if is_valid else "Invalid")

        render_model_outputs(model_results, field_format, format_options, pattern, field_name)


def render_header():
    """Simplified header with mode tabs"""
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔨 **Build Mode**",
                    type="primary" if st.session_state.view_mode == 'build' else "secondary",
                    width='stretch'):
            st.session_state.view_mode = 'build'
            st.rerun()

    with col2:
        if st.button("🧪 **Test Mode**",
                    type="primary" if st.session_state.view_mode == 'test' else "secondary",
                    width='stretch'):
            st.session_state.view_mode = 'test'
            st.rerun()

    with col3:
        if st.button("📤 **Export Mode**",
                    type="primary" if st.session_state.view_mode == 'export' else "secondary",
                    width='stretch'):
            st.session_state.view_mode = 'export'
            st.rerun()


def render_sidebar():
    """Sidebar with image management and settings"""
    with st.sidebar:
        st.markdown("### 📁 Project Controls")

        # Image management tab
        with st.expander("📷 Image Management", expanded=True):
            # API configuration
            api_url = st.text_input(
                "API URL",
                value=get_setting('ocr', 'api_url', 'http://localhost:8080/ocr'),
                key="ocr_api_url"
            )
            set_setting('ocr', 'api_url', api_url)

            # File upload
            uploaded_files = st.file_uploader(
                "Upload images",
                type=['jpg', 'jpeg', 'png'],
                accept_multiple_files=True,
                key="file_uploader"
            )

            if uploaded_files:
                if st.button("🔍 Process", type="primary", use_container_width=True):
                    process_images(uploaded_files, api_url)

                if st.session_state.images:
                    if st.button("🗑️ Clear", type="secondary", use_container_width=True):
                        st.session_state.images = []
                        st.session_state.zones = {}
                        st.session_state.selections = defaultdict(set)
                        st.rerun()

        # Template Metadata
        with st.expander("📄 Template Metadata", expanded=False):
            render_template_metadata()

        # Session management
        with st.expander("💾 Session", expanded=False):
            render_session_management()

        # Settings
        with st.expander("⚙️ Settings", expanded=False):
            render_settings_panel()


def process_images(uploaded_files, api_url):
    """Process images with OCR"""
    st.session_state.images = []
    st.session_state.selections = defaultdict(set)

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, file in enumerate(uploaded_files):
        status_text.text(f"Processing {file.name} ({idx + 1}/{len(uploaded_files)})...")

        try:
            img_bytes = file.getvalue()
            img = Image.open(io.BytesIO(img_bytes))
            ocr_result = call_ocr_api(img_bytes, file.name, api_url)

            if ocr_result:
                words = extract_words(ocr_result)
                st.session_state.images.append({
                    'name': file.name,
                    'image': img,
                    'ocr_result': ocr_result,
                    'words': words
                })

        except Exception as e:
            st.error(f"Error processing {file.name}: {str(e)}")

        progress_bar.progress((idx + 1) / len(uploaded_files))

    status_text.empty()
    progress_bar.empty()

    if st.session_state.images:
        st.success(f"✅ Processed {len(st.session_state.images)} images")
        st.rerun()


def render_template_metadata():
    """Render template metadata configuration - simplified to essential fields only"""
    # Initialize metadata in session state if not present
    if 'metadata' not in st.session_state:
        st.session_state.metadata = {
            'template_name': 'my_template',
            'class_name': 'MyTemplate',
            'version': '1.0'
        }

    # Use value parameter to show loaded metadata, but allow editing
    template_name = st.text_input(
        "Template Name",
        value=st.session_state.metadata.get('template_name', 'my_template'),
        help="Used for file naming (e.g., 'texas_dl_front')",
        placeholder="e.g., texas_dl_front",
        key="metadata_template_name"
    )
    st.session_state.metadata['template_name'] = template_name

    class_name = st.text_input(
        "Class Name",
        value=st.session_state.metadata.get('class_name', 'MyTemplate'),
        help="Python class name for code generation (e.g., 'TexasDLFront')",
        placeholder="e.g., TexasDLFront",
        key="metadata_class_name"
    )
    st.session_state.metadata['class_name'] = class_name

    version = st.text_input(
        "Version",
        value=st.session_state.metadata.get('version', '1.0'),
        help="Template version for tracking changes",
        placeholder="e.g., 1.0",
        key="metadata_version"
    )
    st.session_state.metadata['version'] = version


def render_session_management():
    """Compact session management"""
    if st.session_state.images or st.session_state.zones:
        # Create session bytes
        session_bytes = save_session(st.session_state)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Get template name from metadata
        template_name = st.session_state.metadata.get('template_name', 'template') if hasattr(st.session_state, 'metadata') else 'template'

        st.download_button(
            "💾 Download Session",
            data=session_bytes,
            file_name=f"{template_name}_{timestamp}.json.gz",
            mime="application/octet-stream",
            use_container_width=True,
            help="Download session with all images, OCR results, and zone configurations"
        )

    uploaded_session = st.file_uploader(
        "Load session or template",
        type=['json', 'gz', 'py'],
        key="session_loader",
        help="Load .json.gz session (with images) or .py template (zones only)"
    )

    if uploaded_session:
        if st.button("📥 Load", type="primary", width='stretch'):
            try:
                file_name = uploaded_session.name
                file_content = uploaded_session.getvalue()
                
                # Check if it's a Python template file
                if file_name.endswith('.py'):
                    # Parse template file
                    file_text = file_content.decode('utf-8')
                    template_data = load_template_file(file_text)

                    if template_data:
                        # Load zones and ensure they have required fields
                        loaded_zones = template_data['zones']

                        # Add default y_range and x_range if missing
                        for field_name, zone_config in loaded_zones.items():
                            if 'y_range' not in zone_config:
                                zone_config['y_range'] = (0, 1)
                            if 'x_range' not in zone_config:
                                zone_config['x_range'] = (0, 1)

                        st.session_state.zones = loaded_zones

                        # Load metadata
                        if 'metadata' in template_data:
                            st.session_state.metadata = template_data['metadata']

                        st.success(f"✅ Template loaded: {len(template_data['zones'])} zones")
                        st.info("💡 Upload images to start building/testing")
                        st.rerun()
                    else:
                        st.error("❌ Could not parse template file")
                else:
                    # Load session file (.json or .gz)
                    session_data = load_session(file_content)
                    if session_data:
                        st.session_state.update(session_data)
                        # Metadata widget syncing happens automatically in render_template_metadata()
                        st.success("✅ Session loaded")
                        st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")


def render_build_mode():
    """Main build interface with improved organization"""
    if not st.session_state.images:
        render_welcome_screen()
        return

    # Step 1: Field and Image Selection (collapsible)
    with st.expander("📋 **Step 1: Field & Image Selection**",
                     expanded=st.session_state.config_expanded):
        render_field_and_image_selector()

    # Only show zone configuration if a field is selected
    if st.session_state.current_field:
        # Step 2: Zone Configuration
        st.markdown("### 🎯 Zone Configuration")

        # Get or create zone config
        if st.session_state.current_field in st.session_state.zones:
            zone_config = st.session_state.zones[st.session_state.current_field].copy()
            editing_mode = True
            st.info(f"📝 Editing: **{st.session_state.current_field}**")
        else:
            zone_config = calculate_aggregate_zone(
                st.session_state.images,
                st.session_state.selections
            )
            editing_mode = False

            # Auto-detect format based on field name
            auto_format = auto_detect_format(st.session_state.current_field)
            if not zone_config:
                zone_config = {'y_range': (0, 1), 'x_range': (0, 1)}
            zone_config['format'] = auto_format

            # Set format-specific defaults
            if auto_format == 'date':
                zone_config['date_format'] = 'MM.DD.YYYY'
            elif auto_format == 'height':
                zone_config['height_format'] = 'us'
            elif auto_format == 'weight':
                zone_config['weight_format'] = 'us'

            if zone_config.get('y_range') != (0, 1):
                st.success(f"✨ Auto-calculated zone from selections (format: {auto_format})")
            else:
                st.warning("Select words on the image to create a zone")

        # Format configuration
        col1, col2 = st.columns(2)
        with col1:
            field_format = st.selectbox(
                "Data Format",
                FIELD_FORMATS,
                index=FIELD_FORMATS.index(zone_config.get('format', 'string')),
                key=f"format_selector_{st.session_state.current_field}"
            )
            zone_config['format'] = field_format

        with col2:
            # Format-specific options
            if field_format == 'date':
                date_format = st.selectbox(
                    "Date Format",
                    DATE_FORMATS,
                    index=DATE_FORMATS.index(zone_config.get('date_format', 'MM.DD.YYYY')),
                    key=f"date_format_selector_{st.session_state.current_field}"
                )
                zone_config['date_format'] = date_format
                zone_config['pattern'] = get_date_pattern(date_format)

            elif field_format == 'height':
                height_format = st.selectbox(
                    "Height Format",
                    HEIGHT_FORMATS,
                    index=HEIGHT_FORMATS.index(zone_config.get('height_format', 'us')),
                    key=f"height_format_selector_{st.session_state.current_field}"
                )
                zone_config['height_format'] = height_format
                zone_config['pattern'] = get_height_pattern(height_format)

            elif field_format == 'weight':
                weight_format = st.selectbox(
                    "Weight Format",
                    WEIGHT_FORMATS,
                    index=WEIGHT_FORMATS.index(zone_config.get('weight_format', 'us')),
                    key=f"weight_format_selector_{st.session_state.current_field}"
                )
                zone_config['weight_format'] = weight_format
                zone_config['pattern'] = get_weight_pattern(weight_format)

            elif field_format == 'sex':
                zone_config['pattern'] = r'^[MF]$'
                st.info("Pattern: ^[MF]$")

            elif field_format == 'eyes':
                zone_config['pattern'] = r'^[A-Z]{2,6}$'
                st.info("Pattern: ^[A-Z]{2,6}$ (extracts as-is)")

            elif field_format == 'hair':
                zone_config['pattern'] = r'^[A-Z]{2,6}$'
                st.info("Pattern: ^[A-Z]{2,6}$ (extracts as-is)")

        # Common patterns (shared by both extraction methods)
        st.divider()
        st.markdown("### 🔧 Common Extraction Patterns")
        st.caption("Configure cleanup, validation, and pattern-based extraction patterns")

        col1, col2, col3 = st.columns(3)
        with col1:
            consensus_pattern = st.text_input(
                "Consensus Extract",
                value=zone_config.get('consensus_extract', ''),
                placeholder="e.g., (?:ID|1D)[:\\s]*(\\d{8})",
                help="Pattern for pattern-based extraction (searches expanded zone +5% only)"
            )
            zone_config['consensus_extract'] = consensus_pattern

        with col2:
            cleanup_pattern = st.text_input(
                "Cleanup Pattern",
                value=zone_config.get('cleanup_pattern', ''),
                placeholder="e.g., ^.*?:\\s*",
                help="Removes unwanted text (labels, prefixes)"
            )
            zone_config['cleanup_pattern'] = cleanup_pattern

        with col3:
            if field_format in ['string', 'number']:
                validation_pattern = st.text_input(
                    "Validation Pattern",
                    value=zone_config.get('pattern', ''),
                    placeholder="e.g., ^\\d{8}$",
                    help="Validates the final extracted value"
                )
                zone_config['pattern'] = validation_pattern

        # Custom Pattern Tester
        st.divider()
        render_custom_pattern_tester(zone_config, st.session_state.current_field)

        # Zone-based extraction section
        st.divider()
        st.markdown("### 📦 Zone-Based Extraction")
        render_zone_extraction_section(zone_config, st.session_state.current_field)

        # Pattern-based extraction section (separate from zone-based)
        st.divider()
        st.markdown("### 🔄 Pattern-Based Extraction")
        st.caption("Alternative extraction method using regex patterns (searches expanded zone +5% only)")
        render_pattern_extraction_section(zone_config, st.session_state.current_field)

        # Save/Delete buttons
        st.divider()
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("💾 Save Configuration", type="primary", width='stretch'):
                st.session_state.zones[st.session_state.current_field] = zone_config
                st.success(f"✅ Saved: {st.session_state.current_field}")
                st.session_state.selections = defaultdict(set)
                st.rerun()

        with col2:
            if editing_mode:
                if st.button("🔄 Reset", type="secondary", width='stretch'):
                    st.session_state.selections = defaultdict(set)
                    st.rerun()

        with col3:
            if editing_mode:
                if st.button("🗑️ Delete", type="secondary", width='stretch'):
                    del st.session_state.zones[st.session_state.current_field]
                    st.session_state.current_field = None
                    st.warning(f"Deleted configuration")
                    st.rerun()


def render_field_and_image_selector():
    """Combined field and image selection interface"""
    col1, col2 = st.columns([2, 1])  # Swapped: image on left (2), field on right (1)

    with col2:  # Field selection now on the right
        # Field selection
        st.markdown("#### Select Field")

        # Region filter
        region = st.selectbox(
            "Region",
            ["All", "USA", "France"],
            index=["All", "USA", "France"].index(st.session_state.field_filter)
        )
        if region != st.session_state.field_filter:
            st.session_state.field_filter = region
            st.rerun()

        # Field dropdown
        fields = get_filtered_fields(st.session_state.field_filter)
        created_fields = [f for f in fields if f in st.session_state.zones]
        available_fields = [f for f in fields if f not in st.session_state.zones]

        options = []
        if created_fields:
            options.append("── Configured ──")
            options.extend([f"✅ {f}" for f in created_fields])
        if available_fields:
            if created_fields:
                options.append("── Available ──")
            options.extend(available_fields)

        if options:
            field_selection = st.selectbox(
                "Field",
                options,
                key="field_dropdown"
            )

            if field_selection and not field_selection.startswith("──"):
                field_name = field_selection.replace("✅ ", "") if field_selection.startswith("✅") else field_selection
                if field_name != st.session_state.current_field:
                    st.session_state.current_field = field_name
                    if field_name not in st.session_state.zones:
                        st.session_state.selections = defaultdict(set)
                    st.session_state.config_expanded = False
                    st.rerun()

        # Zone coordinates editor (if field is selected and zone exists)
        if st.session_state.current_field and st.session_state.current_field in st.session_state.zones:
            st.markdown("---")
            st.markdown("#### Zone Coordinates")

            zone_config = st.session_state.zones[st.session_state.current_field]

            # Store auto-calculated zone if not already stored
            auto_zones_key = f"_auto_zone_{st.session_state.current_field}"
            if auto_zones_key not in st.session_state:
                # Calculate and store the auto zone
                auto_zone = calculate_aggregate_zone(
                    st.session_state.images,
                    st.session_state.selections
                )
                if auto_zone:
                    st.session_state[auto_zones_key] = auto_zone.copy()

            # Y Range
            y_min = st.number_input(
                "Y Min",
                min_value=0.0,
                max_value=1.0,
                value=float(zone_config['y_range'][0]),
                step=0.01,
                format="%.3f",
                key=f"y_min_{st.session_state.current_field}"
            )
            y_max = st.number_input(
                "Y Max",
                min_value=0.0,
                max_value=1.0,
                value=float(zone_config['y_range'][1]),
                step=0.01,
                format="%.3f",
                key=f"y_max_{st.session_state.current_field}"
            )

            # X Range
            x_min = st.number_input(
                "X Min",
                min_value=0.0,
                max_value=1.0,
                value=float(zone_config.get('x_range', (0, 1))[0]),
                step=0.01,
                format="%.3f",
                key=f"x_min_{st.session_state.current_field}"
            )
            x_max = st.number_input(
                "X Max",
                min_value=0.0,
                max_value=1.0,
                value=float(zone_config.get('x_range', (0, 1))[1]),
                step=0.01,
                format="%.3f",
                key=f"x_max_{st.session_state.current_field}"
            )

            # Update zone config if values changed
            if (y_min, y_max) != zone_config['y_range'] or (x_min, x_max) != zone_config.get('x_range', (0, 1)):
                zone_config['y_range'] = (y_min, y_max)
                zone_config['x_range'] = (x_min, x_max)
                st.session_state.zones[st.session_state.current_field] = zone_config
                st.rerun()

            # Reset to auto-calculated button
            if st.button("🔄 Reset to Auto", use_container_width=True, help="Recalculate zone from current selections"):
                # Recalculate zone from current selections
                auto_zone = calculate_aggregate_zone(
                    st.session_state.images,
                    st.session_state.selections
                )
                if auto_zone and auto_zone.get('y_range') != (0, 1):
                    # Update the zone in session state
                    zone_config['y_range'] = auto_zone['y_range']
                    zone_config['x_range'] = auto_zone.get('x_range', (0, 1))
                    st.session_state.zones[st.session_state.current_field] = zone_config
                    
                    # Clear the widget keys so they refresh with new values
                    field = st.session_state.current_field
                    for key in [f"y_min_{field}", f"y_max_{field}", f"x_min_{field}", f"x_max_{field}"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    st.rerun()
                else:
                    st.warning("⚠️ No words selected. Select words to calculate zone.")

        st.markdown("---")
        # Progress
        st.metric("Progress", f"{len(st.session_state.zones)}/{len(fields)} fields")

    with col1:  # Image section now on the left
        # Image viewer and word selection
        st.markdown("#### Image & Word Selection")

        # Image navigation
        image_options = [f"{i+1}. {img['name'][:30]}" for i, img in enumerate(st.session_state.images)]

        col_nav1, col_nav2 = st.columns([3, 1])
        with col_nav1:
            selected = st.selectbox(
                "Current Image",
                options=range(len(image_options)),
                format_func=lambda x: image_options[x],
                index=st.session_state.current_image_idx
            )
            if selected != st.session_state.current_image_idx:
                st.session_state.current_image_idx = selected
                st.rerun()

        with col_nav2:
            st.metric("Image", f"{st.session_state.current_image_idx + 1}/{len(st.session_state.images)}", label_visibility="collapsed")

        # Display image
        current_img = st.session_state.images[st.session_state.current_image_idx]
        current_selections = st.session_state.selections[st.session_state.current_image_idx]

        vis_img = draw_visualization(
            current_img['image'],
            current_img['words'],
            current_selections,
            st.session_state.zones,
            st.session_state.current_field
        )

        # Image display with scale
        image_scale = get_setting('display', 'image_scale', 1.0)
        if image_scale < 1.0:
            col_width = int(12 * image_scale)
            col1, col2 = st.columns([col_width, 12 - col_width])
            with col1:
                st.image(vis_img, width='stretch')
        else:
            st.image(vis_img, width='stretch')

        # Word selection tools
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Select All"):
                current_selections.update(range(len(current_img['words'])))
                st.rerun()
        with col2:
            if st.button("Clear"):
                current_selections.clear()
                st.rerun()
        with col3:
            if st.button("Invert"):
                all_indices = set(range(len(current_img['words'])))
                current_selections.symmetric_difference_update(all_indices)
                st.rerun()
        with col4:
            st.info(f"Selected: {len(current_selections)}")

        # Word buttons
        words = current_img['words']
        cols_per_row = 10  # 10 numbers per line as requested
        for row_start in range(0, len(words), cols_per_row):
            row_end = min(row_start + cols_per_row, len(words))
            cols = st.columns(cols_per_row)

            for i in range(row_start, row_end):
                col_idx = i - row_start
                word = words[i]
                is_selected = i in current_selections

                with cols[col_idx]:
                    if st.button(
                        str(i+1),
                        key=f"word_{st.session_state.current_image_idx}_{i}",
                        type="primary" if is_selected else "secondary",
                        help=f"'{word['text']}'"
                    ):
                        if is_selected:
                            current_selections.remove(i)
                        else:
                            current_selections.add(i)
                        st.rerun()


def render_custom_pattern_tester(zone_config: dict, field_name: str = None):
    """
    Interactive pattern testing sandbox - test patterns on custom text
    without relying on OCR output
    """
    with st.expander("🧪 **Pattern Testing Sandbox**", expanded=False):
        st.caption("Test your patterns on custom text - updates automatically as you type")

        # Custom text input - use text_input for instant updates
        custom_text = st.text_input(
            "Input Text",
            value="",
            placeholder="e.g., DD: 12345678",
            help="Enter any text to test your patterns",
            key=f"custom_text_input_{field_name}"
        )

        if not custom_text.strip():
            st.info("💡 Enter some text above to start testing patterns")
            return

        # Get patterns from config
        cleanup_pattern = zone_config.get('cleanup_pattern', '')
        validation_pattern = zone_config.get('pattern', '')
        consensus_pattern = zone_config.get('consensus_extract', '')

        # Pattern selection checkboxes - BEFORE application
        st.markdown("**Select patterns to apply:**")
        col1, col2, col3 = st.columns(3)

        with col1:
            apply_consensus = st.checkbox(
                "Consensus Extract",
                value=False,
                key=f"test_apply_consensus_{field_name}",
                disabled=not consensus_pattern.strip()
            )
            if consensus_pattern.strip():
                st.caption(f"`{consensus_pattern[:40]}...`" if len(consensus_pattern) > 40 else f"`{consensus_pattern}`")

        with col2:
            apply_cleanup = st.checkbox(
                "Cleanup",
                value=False,
                key=f"test_apply_cleanup_{field_name}",
                disabled=not cleanup_pattern.strip()
            )
            if cleanup_pattern.strip():
                st.caption(f"`{cleanup_pattern[:40]}...`" if len(cleanup_pattern) > 40 else f"`{cleanup_pattern}`")

        with col3:
            apply_validation = st.checkbox(
                "Validation",
                value=True,
                key=f"test_apply_validation_{field_name}",
                disabled=not validation_pattern.strip()
            )
            if validation_pattern.strip():
                st.caption(f"`{validation_pattern[:40]}...`" if len(validation_pattern) > 40 else f"`{validation_pattern}`")

        st.divider()

        # Process the text step by step
        current_text = custom_text
        model_colors = {'input': '#6c757d', 'consensus': '#9C27B0', 'cleanup': '#2196F3', 'normalize': '#FF9800', 'valid': '#4CAF50', 'invalid': '#F44336'}

        # Show original input
        st.markdown(f"""
        <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {model_colors['input']}15, transparent); border-left: 3px solid {model_colors['input']}; border-radius: 4px;">
            <span style="color: {model_colors['input']}; font-weight: bold; font-size: 14px;">📥 INPUT:</span>
            <span style="color: #333; margin-left: 10px; font-family: monospace;">{custom_text}</span>
        </div>
        """, unsafe_allow_html=True)

        # Step 1: Consensus Extract
        if apply_consensus and consensus_pattern.strip():
            try:
                match = re.search(consensus_pattern, current_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    prev_text = current_text
                    current_text = match.group(1).strip() if (match.lastindex and match.lastindex >= 1) else match.group(0).strip()

                    st.markdown(f"""
                    <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {model_colors['consensus']}15, transparent); border-left: 3px solid {model_colors['consensus']}; border-radius: 4px;">
                        <span style="color: {model_colors['consensus']}; font-weight: bold; font-size: 14px;">✅ CONSENSUS EXTRACT:</span>
                        <span style="color: #666; margin-left: 10px; font-family: monospace;">{prev_text}</span>
                        <span style="color: #999; margin: 0 5px;">→</span>
                        <span style="color: #333; font-weight: 500; font-family: monospace;">{current_text}</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {model_colors['invalid']}15, transparent); border-left: 3px solid {model_colors['invalid']}; border-radius: 4px;">
                        <span style="color: {model_colors['invalid']}; font-weight: bold; font-size: 14px;">❌ CONSENSUS EXTRACT:</span>
                        <span style="color: #333; margin-left: 10px; font-family: monospace;">No match</span>
                    </div>
                    """, unsafe_allow_html=True)
                    current_text = ""
            except re.error as e:
                st.error(f"❌ Consensus pattern error: {e}")
                current_text = ""

        # Step 2: Cleanup
        if apply_cleanup and cleanup_pattern.strip() and current_text:
            try:
                prev_text = current_text
                current_text = re.sub(cleanup_pattern, '', current_text, flags=re.IGNORECASE).strip()

                if prev_text != current_text:
                    st.markdown(f"""
                    <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {model_colors['cleanup']}15, transparent); border-left: 3px solid {model_colors['cleanup']}; border-radius: 4px;">
                        <span style="color: {model_colors['cleanup']}; font-weight: bold; font-size: 14px;">✅ CLEANUP:</span>
                        <span style="color: #666; margin-left: 10px; font-family: monospace;">{prev_text}</span>
                        <span style="color: #999; margin: 0 5px;">→</span>
                        <span style="color: #333; font-weight: 500; font-family: monospace;">{current_text if current_text else '(empty)'}</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {model_colors['cleanup']}15, transparent); border-left: 3px solid {model_colors['cleanup']}; border-radius: 4px;">
                        <span style="color: {model_colors['cleanup']}; font-weight: bold; font-size: 14px;">ℹ️ CLEANUP:</span>
                        <span style="color: #333; margin-left: 10px; font-family: monospace;">No changes</span>
                    </div>
                    """, unsafe_allow_html=True)
            except re.error as e:
                st.error(f"❌ Cleanup pattern error: {e}")

        # Step 3: Normalization (always apply if we have text)
        if current_text:
            field_format = zone_config.get('format', 'string')
            format_options = {}

            if field_format == 'date':
                format_options['date_format'] = zone_config.get('date_format', 'MM.DD.YYYY')
            elif field_format == 'height':
                format_options['height_format'] = zone_config.get('height_format', 'auto')
            elif field_format == 'weight':
                format_options['weight_format'] = zone_config.get('weight_format', 'auto')

            prev_text = current_text
            normalized = normalize_field(current_text, field_format, field_name, **format_options)

            if normalized and normalized != current_text:
                current_text = normalized
                st.markdown(f"""
                <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {model_colors['normalize']}15, transparent); border-left: 3px solid {model_colors['normalize']}; border-radius: 4px;">
                    <span style="color: {model_colors['normalize']}; font-weight: bold; font-size: 14px;">✅ NORMALIZE ({field_format}):</span>
                    <span style="color: #666; margin-left: 10px; font-family: monospace;">{prev_text}</span>
                    <span style="color: #999; margin: 0 5px;">→</span>
                    <span style="color: #333; font-weight: 500; font-family: monospace;">{current_text}</span>
                </div>
                """, unsafe_allow_html=True)

        # Step 4: Validation
        if current_text:
            if apply_validation and validation_pattern.strip():
                try:
                    is_valid = bool(re.match(validation_pattern, current_text))
                    color = model_colors['valid'] if is_valid else model_colors['invalid']
                    status = "✅ VALID" if is_valid else "❌ INVALID"

                    st.markdown(f"""
                    <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {color}15, transparent); border-left: 3px solid {color}; border-radius: 4px;">
                        <span style="color: {color}; font-weight: bold; font-size: 14px;">{status}:</span>
                        <span style="color: #333; margin-left: 10px; font-family: monospace; font-weight: 600;">{current_text}</span>
                    </div>
                    """, unsafe_allow_html=True)
                except re.error as e:
                    st.error(f"❌ Validation pattern error: {e}")
            else:
                # No validation or not enabled - show final result
                st.markdown(f"""
                <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {model_colors['valid']}15, transparent); border-left: 3px solid {model_colors['valid']}; border-radius: 4px;">
                    <span style="color: {model_colors['valid']}; font-weight: bold; font-size: 14px;">✅ RESULT:</span>
                    <span style="color: #333; margin-left: 10px; font-family: monospace; font-weight: 600;">{current_text}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Empty result - no output from extraction pipeline")


def render_zone_extraction_section(zone_config, field_name: str = None):
    """Zone-based extraction preview with detailed expandables"""

    # Copy all raw outputs button
    all_raw_outputs = []
    for img_data in st.session_state.images:
        model_results = extract_from_zone_multimodel(
            img_data.get('ocr_result', {}),
            zone_config,
            img_data.get('words', [])
        )
        if model_results:
            all_raw_outputs.extend(model_results.values())

    if all_raw_outputs:
        with st.expander(f"📋 Copy All Zone Outputs ({len(all_raw_outputs)} samples)", expanded=False):
            st.code('\n'.join(all_raw_outputs), language="text")

    # Preview for each image with expandable details
    for img_idx, img_data in enumerate(st.session_state.images):
        model_results_raw = extract_from_zone_multimodel(
            img_data.get('ocr_result', {}), zone_config, img_data.get('words', [])
        )

        # Prepare normalization settings
        field_format = zone_config.get('format', 'string')
        format_options = {}
        if field_format == 'date':
            format_options['date_format'] = zone_config.get('date_format', 'MM.DD.YYYY')
        elif field_format == 'height':
            format_options['height_format'] = zone_config.get('height_format', 'auto')
        elif field_format == 'weight':
            format_options['weight_format'] = zone_config.get('weight_format', 'auto')

        pattern = zone_config.get('pattern', '')

        # Normalize and validate each model's result BEFORE voting
        if model_results_raw:
            model_results_normalized = {}
            for model_name, raw_text in model_results_raw.items():
                if raw_text:
                    normalized = normalize_field(raw_text, field_format, field_name, **format_options)
                    # Only include valid normalized results in voting
                    if normalized and (not pattern or re.match(pattern, normalized)):
                        model_results_normalized[model_name] = normalized

            # Vote on NORMALIZED values
            if model_results_normalized:
                vote_counts = Counter(model_results_normalized.values())
                normalized_text = vote_counts.most_common(1)[0][0]
                vote_count = vote_counts[normalized_text]
                total_models = len(model_results_normalized)
                # Find a raw text that normalized to the consensus (for display)
                consensus_text = next((raw for model, raw in model_results_raw.items()
                                      if model in model_results_normalized
                                      and model_results_normalized[model] == normalized_text), normalized_text)
                is_valid = True  # Already validated during normalization
            else:
                # No valid normalized results
                normalized_text = None
                consensus_text = ""
                vote_count = 0
                total_models = len(model_results_raw)
                is_valid = False
        else:
            # Fallback to single model
            consensus_text = extract_from_zone(img_data['words'], zone_config)
            _, normalized_text, is_valid, _, _ = process_extraction_result(
                consensus_text, zone_config, field_name
            )
            vote_count, total_models = 1, 1

        # Render expandable for this image
        render_per_image_expandable(
            img_idx, img_data, consensus_text, normalized_text, is_valid,
            vote_count, total_models, model_results_raw, field_format, format_options,
            pattern, field_name
        )


def render_pattern_extraction_section(zone_config, field_name: str = None):
    """Pattern-based extraction configuration and preview"""

    # Get expanded zone bounds
    y_range = zone_config.get('y_range', (0, 1))
    x_range = zone_config.get('x_range', (0, 1))

    expand_factor = 0.05
    expanded_y = (max(0, y_range[0] - expand_factor), min(1, y_range[1] + expand_factor))
    expanded_x = (max(0, x_range[0] - expand_factor), min(1, x_range[1] + expand_factor))

    # Get consensus pattern from zone_config (set in Common Patterns section above)
    consensus_pattern = zone_config.get('consensus_extract', '')

    # Validate consensus pattern and show info
    if consensus_pattern:
        from zone_operations import validate_consensus_pattern
        is_valid, error_msg = validate_consensus_pattern(consensus_pattern)
        if not is_valid:
            st.error(f"⚠️ **Invalid Pattern:** {error_msg}")
        else:
            # Check if pattern has capturing group
            compiled = re.compile(consensus_pattern)
            if compiled.groups >= 1:
                st.success("✓ Pattern with capturing group - extracts group(1)")
            else:
                st.info("ℹ️ Pattern without capturing group - extracts full match + cleanup_pattern")

    # Cleanup toggle
    apply_cleanup = st.checkbox(
        "Apply cleanup pattern to extracted value",
        value=True,  # Default ON to match Test Mode behavior
        key=f"apply_cleanup_{field_name}",
        help="Apply cleanup pattern to the value extracted by consensus pattern (e.g., remove remaining labels)"
    )

    # Prepare expanded zone config WITHOUT cleanup
    # (Consensus patterns search raw text, cleanup is applied to extracted value)
    expanded_zone_config = zone_config.copy()
    expanded_zone_config['y_range'] = expanded_y
    expanded_zone_config['x_range'] = expanded_x
    expanded_zone_config['cleanup_pattern'] = ''  # Never apply cleanup to zone text for consensus extraction

    # Decide what to show based on whether pattern is entered
    if not consensus_pattern:
        # NO PATTERN: Show expanded zone outputs for pattern development
        st.info("💡 Enter a 'Consensus Extract' pattern in the Common Patterns section above to test extraction. The outputs below show the expanded zone (+5%) text from each model to help you develop your pattern.")

        all_expanded_outputs = []
        for img_data in st.session_state.images:
            model_results = extract_from_zone_multimodel(
                img_data.get('ocr_result', {}),
                expanded_zone_config,
                img_data.get('words', [])
            )
            if model_results:
                all_expanded_outputs.extend(model_results.values())

        if all_expanded_outputs:
            with st.expander(f"📋 Copy All Expanded Zone Outputs ({len(all_expanded_outputs)} samples)", expanded=False):
                st.code('\n'.join(all_expanded_outputs), language="text")

        # Per-image expandables showing expanded zone content
        for img_idx, img_data in enumerate(st.session_state.images):
            model_results_raw = extract_from_zone_multimodel(
                img_data.get('ocr_result', {}), expanded_zone_config, img_data.get('words', [])
            )

            # Prepare normalization settings
            field_format = zone_config.get('format', 'string')
            format_options = {}
            if field_format == 'date':
                format_options['date_format'] = zone_config.get('date_format', 'MM.DD.YYYY')
            elif field_format == 'height':
                format_options['height_format'] = zone_config.get('height_format', 'auto')
            elif field_format == 'weight':
                format_options['weight_format'] = zone_config.get('weight_format', 'auto')

            pattern = zone_config.get('pattern', '')

            # Normalize and validate each model's result BEFORE voting
            if model_results_raw:
                model_results_normalized = {}
                for model_name, raw_text in model_results_raw.items():
                    if raw_text:
                        normalized = normalize_field(raw_text, field_format, field_name, **format_options)
                        # Only include valid normalized results in voting
                        if normalized and (not pattern or re.match(pattern, normalized)):
                            model_results_normalized[model_name] = normalized

                # Vote on NORMALIZED values
                if model_results_normalized:
                    vote_counts = Counter(model_results_normalized.values())
                    normalized_text = vote_counts.most_common(1)[0][0]
                    vote_count = vote_counts[normalized_text]
                    total_models = len(model_results_normalized)
                    # Find a raw text that normalized to the consensus (for display)
                    consensus_text = next((raw for model, raw in model_results_raw.items()
                                          if model in model_results_normalized
                                          and model_results_normalized[model] == normalized_text), normalized_text)
                    is_valid = True  # Already validated during normalization
                else:
                    # No valid normalized results
                    normalized_text = None
                    consensus_text = ""
                    vote_count = 0
                    total_models = len(model_results_raw)
                    is_valid = False
            else:
                # Fallback to single model
                consensus_text = extract_from_zone(img_data['words'], expanded_zone_config)
                _, normalized_text, is_valid, _, _ = process_extraction_result(
                    consensus_text, zone_config, field_name
                )
                vote_count, total_models = 1, 1

            # Render expandable for this image
            render_per_image_expandable(
                img_idx, img_data, consensus_text, normalized_text, is_valid,
                vote_count, total_models, model_results_raw, field_format, format_options,
                pattern, field_name
            )
    else:
        # PATTERN ENTERED: Test pattern and show results
        try:
            compiled_pattern = re.compile(consensus_pattern, re.IGNORECASE | re.MULTILINE)
        except re.error as e:
            st.error(f"❌ Invalid regex: {e}")
            return

        st.success(f"✅ Testing pattern on each model's expanded zone (+5%) and full document")

        # Get cleanup pattern if toggle is enabled
        cleanup_pattern = zone_config.get('cleanup_pattern', '') if apply_cleanup else ''

        # Helper function to test pattern on text and apply cleanup to result
        def test_pattern_on_text(zone_text, full_text):
            """Test pattern on zone text only (NO FALLBACK to full text)"""
            extracted_value = None

            # Try expanded zone text only (no fallback)
            if zone_text:
                match = compiled_pattern.search(zone_text)
                if match:
                    extracted_value = match.group(1) if match.groups() else match.group(0)

            # Apply cleanup pattern to the extracted value (if enabled and pattern exists)
            if extracted_value and cleanup_pattern:
                try:
                    extracted_value = re.sub(cleanup_pattern, '', extracted_value, flags=re.IGNORECASE).strip()
                except re.error:
                    pass  # If cleanup pattern is invalid, skip it

            return extracted_value

        # Process all images once and cache results
        all_image_results = []

        for img_idx, img_data in enumerate(st.session_state.images):
            ocr_result = img_data.get('ocr_result', {})
            per_model_outputs = ocr_result.get('model_comparison', {}).get('per_model_outputs', {})

            # Get expanded zone text for pattern testing (only once per image)
            model_expanded_zone_results = extract_from_zone_multimodel(
                ocr_result, expanded_zone_config, img_data.get('words', [])
            )

            # Test pattern on each model - Get model names dynamically from the data
            model_results = {}

            # Get actual model names from per_model_outputs (don't hardcode!)
            available_models = list(per_model_outputs.keys()) if per_model_outputs else []

            for model_name in available_models:
                zone_text = model_expanded_zone_results.get(model_name, '')
                model_data = per_model_outputs.get(model_name, {})

                # Get full document text by joining all words
                model_words = model_data.get('words', []) if model_data else []
                full_text = ' '.join(model_words) if model_words else ''

                model_match = test_pattern_on_text(zone_text, full_text)
                model_results[model_name] = model_match if model_match else ''

            # Normalize and validate each model's result BEFORE voting
            field_format = zone_config.get('format', 'string')
            format_options = {}
            if field_format == 'date':
                format_options['date_format'] = zone_config.get('date_format', 'MM.DD.YYYY')
            elif field_format == 'height':
                format_options['height_format'] = zone_config.get('height_format', 'auto')
            elif field_format == 'weight':
                format_options['weight_format'] = zone_config.get('weight_format', 'auto')

            pattern = zone_config.get('pattern', '')

            model_results_normalized = {}
            for model_name, raw_value in model_results.items():
                if raw_value:
                    normalized = normalize_field(raw_value, field_format, field_name, **format_options)
                    # Only include valid normalized results in voting
                    if normalized and (not pattern or re.match(pattern, normalized)):
                        model_results_normalized[model_name] = normalized

            # Vote on NORMALIZED values
            if model_results_normalized:
                vote_counts = Counter(model_results_normalized.values())
                consensus_match = vote_counts.most_common(1)[0][0]
                vote_count = vote_counts[consensus_match]
                total_models = len(model_results_normalized)
            else:
                consensus_match, vote_count, total_models = None, 0, len(model_results)

            # Store results for this image
            all_image_results.append({
                'img_idx': img_idx,
                'img_data': img_data,
                'model_results': model_results,
                'consensus_match': consensus_match,
                'vote_count': vote_count,
                'total_models': total_models
            })

        # Copy all pattern outputs button
        all_pattern_outputs = []
        for img_result in all_image_results:
            for model_name in sorted(img_result['model_results'].keys()):
                match_value = img_result['model_results'].get(model_name, '')
                all_pattern_outputs.append(match_value if match_value else '(no match)')

        with st.expander(f"📋 Copy All Pattern Outputs ({len(all_pattern_outputs)} samples)", expanded=False):
            st.code('\n'.join(all_pattern_outputs), language="text")

        # Per-image expandables using cached results
        for img_result in all_image_results:
            # Process result: normalize, validate
            cleaned, normalized, is_valid, field_format, format_options = process_extraction_result(
                img_result['consensus_match'] or '', zone_config, field_name
            )

            # Render expandable for this image
            render_per_image_expandable(
                img_result['img_idx'], img_result['img_data'], cleaned, normalized, is_valid,
                img_result['vote_count'], img_result['total_models'], img_result['model_results'],
                field_format, format_options, zone_config.get('pattern', ''), field_name, empty_msg='(no match)'
            )


def render_test_mode():
    """Test mode for validation"""
    st.markdown("### 🧪 Zone Testing & Validation")

    if not st.session_state.zones:
        st.info("No zones created yet. Switch to Build mode to create zones.")
        return

    # Test all zones
    for field_name, zone_config in st.session_state.zones.items():
        success_count = 0
        total_count = len(st.session_state.images)

        for img_data in st.session_state.images:
            # Test zone extraction
            extracted = extract_from_zone(img_data['words'], zone_config)
            if extracted:
                success_count += 1

        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        status = "🟢" if success_rate >= 90 else "🟡" if success_rate >= 70 else "🔴"

        st.text(f"{status} {field_name}: {success_rate:.0f}% success ({success_count}/{total_count})")


def render_welcome_screen():
    """Welcome screen"""
    st.markdown("""
    ### 👋 Welcome to Zone Builder Pro

    **Getting Started:**
    1. Upload document images in the sidebar
    2. Process with OCR
    3. Select field and create zones
    4. Configure extraction patterns
    5. Export your template

    **Upload images in the sidebar to begin →**
    """)


def render_test_mode():
    """Test mode - comprehensive field extraction testing"""
    st.markdown("### 🧪 Test Mode - Field Extraction Validation")
    
    if not st.session_state.zones:
        st.warning("⚠️ No zones configured yet. Switch to Build Mode to create zones first.")
        if st.button("🔨 Go to Build Mode"):
            st.session_state.view_mode = 'build'
            st.rerun()
        return

    # Test images upload section
    st.markdown("#### 📷 Upload Test Images")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        test_files = st.file_uploader(
            "Upload test images to validate your template",
            type=['jpg', 'jpeg', 'png'],
            accept_multiple_files=True,
            key="test_file_uploader"
        )
    
    with col2:
        # API URL for testing
        test_api_url = st.text_input(
            "OCR API URL",
            value=get_setting('ocr', 'api_url', 'http://localhost:8080/ocr'),
            key="test_api_url"
        )

    if test_files:
        if st.button("🔍 Process Test Images & Extract Fields", type="primary"):
            process_test_images_and_extract(test_files, test_api_url)
    
    # Display test results if available
    if hasattr(st.session_state, 'test_results') and st.session_state.test_results:
        render_test_results()


def render_export_mode():
    """Export mode - template export interface"""
    st.markdown("### 📤 Export Template")
    
    if not st.session_state.zones:
        st.warning("⚠️ No zones configured yet. Switch to Build Mode to create zones first.")
        if st.button("🔨 Go to Build Mode"):
            st.session_state.view_mode = 'build'
            st.rerun()
        return

    # Export preview
    st.markdown("#### 📋 Zone Configuration Preview")
    
    preview_data = preview_zone_status(st.session_state.zones)
    
    if preview_data:
        # Summary stats
        total_zones = len(preview_data)
        configured_zones = len([p for p in preview_data if p['status'] == '✅'])
        partial_zones = len([p for p in preview_data if p['status'] == '⚠️'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Zones", total_zones)
        with col2:
            st.metric("Fully Configured", configured_zones)
        with col3:
            st.metric("Partially Configured", partial_zones)
        
        # Zone status table
        for preview in preview_data:
            with st.expander(f"{preview['status']} {preview['field_name']} - {preview['message']}", expanded=False):
                st.markdown(f"**Zone:** y_range: {preview['y_range']}, x_range: {preview['x_range']}")
                if preview.get('patterns'):
                    st.markdown("**Patterns configured:**")
                    for pattern_type, pattern in preview['patterns'].items():
                        st.code(f"{pattern_type}: {pattern}")

    # Get metadata from session state (configured in sidebar)
    metadata = st.session_state.get('metadata', {
        'template_name': 'my_template',
        'class_name': 'MyTemplate',
        'version': '1.0'
    })

    # Auto-set document_type to equal template_name (required for export)
    metadata['document_type'] = metadata.get('template_name', 'my_template')

    # Show current metadata (simplified to essential fields only)
    st.markdown("#### 📄 Template Metadata")
    st.info(f"**Using metadata from sidebar:**\n\n"
            f"Template: `{metadata.get('template_name', 'N/A')}`\n\n"
            f"Class: `{metadata.get('class_name', 'N/A')}`\n\n"
            f"Version: `{metadata.get('version', 'N/A')}`\n\n"
            f"Document Type: `{metadata.get('document_type', 'N/A')}`")

    # Export section
    st.markdown("#### 💾 Export Options")
    
    export_format = st.radio(
        "Export Format",
        ["JSON", "Python Template"],
        horizontal=True
    )
    
    if export_format == "JSON":
        zones_json = export_to_json(st.session_state.zones)
        st.code(zones_json, language="json", line_numbers=True)
        
        st.download_button(
            "📥 Download JSON",
            data=zones_json,
            file_name=f"{metadata['template_name']}.json",
            mime="application/json",
            use_container_width=True
        )
    
    else:  # Python Template
        python_code = export_to_python(st.session_state.zones, metadata)
        st.code(python_code, language="python", line_numbers=True)
        
        st.download_button(
            "📥 Download Python Template",
            data=python_code,
            file_name=f"{metadata['template_name']}.py",
            mime="text/plain",
            use_container_width=True
        )


def process_test_images_and_extract(test_files, api_url):
    """Process test images and extract all fields using configured zones"""
    st.session_state.test_results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, file in enumerate(test_files):
        status_text.text(f"Processing {file.name} ({idx + 1}/{len(test_files)})...")
        
        try:
            img_bytes = file.getvalue()
            img = Image.open(io.BytesIO(img_bytes))
            
            # Get OCR result
            ocr_result = call_ocr_api(img_bytes, file.name, api_url)
            
            if ocr_result:
                words = extract_words(ocr_result)
                
                # Extract all configured fields
                field_results = {}
                overall_valid = True
                
                for field_name, zone_config in st.session_state.zones.items():
                    # Apply exporter logic to ensure normalized fields have consensus_extract
                    # (this matches what the exporter does automatically)
                    working_zone_config = zone_config.copy()
                    if not working_zone_config.get('consensus_extract'):
                        field_format = working_zone_config.get('format')
                        if field_format in ['height', 'sex', 'eyes', 'hair', 'weight']:
                            working_zone_config['consensus_extract'] = r".*"  # Match any text, let normalizer handle extraction
                    
                    # TEST BOTH EXTRACTION METHODS SEPARATELY
                    
                    # 1. ZONE-BASED EXTRACTION (pure zone, no pattern fallback)
                    zone_config_pure = working_zone_config.copy()
                    zone_config_pure.pop('consensus_extract', None)  # Remove pattern fallback
                    
                    zone_model_results = extract_from_zone_multimodel(
                        ocr_result,
                        zone_config_pure,
                        words
                    )
                    
                    # Normalize and validate EACH model's zone result BEFORE voting (like Build Mode & Production)
                    field_format = working_zone_config.get('format', 'string')
                    format_options = {}
                    if field_format == 'date':
                        format_options['date_format'] = working_zone_config.get('date_format', 'MM.DD.YYYY')
                    elif field_format == 'height':
                        format_options['height_format'] = working_zone_config.get('height_format', 'auto')
                    elif field_format == 'weight':
                        format_options['weight_format'] = working_zone_config.get('weight_format', 'auto')

                    validation_pattern = working_zone_config.get('pattern', '')

                    if zone_model_results:
                        # Normalize each model's zone text
                        zone_model_results_normalized = {}
                        for model_name, raw_zone_text in zone_model_results.items():
                            if raw_zone_text:
                                normalized = normalize_field(raw_zone_text, field_format, field_name, **format_options)
                                # Only include valid normalized results in voting
                                if normalized and (not validation_pattern or re.match(validation_pattern, normalized)):
                                    zone_model_results_normalized[model_name] = normalized

                        # Vote on NORMALIZED values (like Build Mode & Production)
                        if zone_model_results_normalized:
                            zone_vote_counts = Counter(zone_model_results_normalized.values())
                            zone_consensus_text = zone_vote_counts.most_common(1)[0][0] if zone_vote_counts else ""
                            zone_vote_count = zone_vote_counts[zone_consensus_text] if zone_consensus_text else 0
                            zone_total_models = len(zone_model_results_normalized)

                            # Winner is already normalized!
                            zone_normalized_text = zone_consensus_text
                            zone_is_valid = bool(zone_normalized_text)
                        else:
                            # No valid normalized results
                            zone_consensus_text = ""
                            zone_normalized_text = ""
                            zone_is_valid = False
                            zone_vote_count = 0
                            zone_total_models = len(zone_model_results)
                    else:
                        # Single model fallback
                        zone_consensus_text = extract_from_zone(words, zone_config_pure)
                        zone_normalized_text = normalize_field(zone_consensus_text, field_format, field_name, **format_options) if zone_consensus_text else ""
                        zone_is_valid = bool(zone_normalized_text) and (not validation_pattern or bool(re.match(validation_pattern, zone_normalized_text)))
                        zone_vote_count, zone_total_models = 1, 1
                        zone_model_results = {"single": zone_consensus_text}
                    
                    # 2. PATTERN-BASED EXTRACTION (pure pattern, if consensus_extract exists)
                    pattern_results = {}
                    pattern_consensus_text = ""
                    pattern_normalized_text = ""
                    pattern_is_valid = False
                    pattern_vote_count = 0
                    pattern_total_models = 0
                    pattern_model_results = {}
                    
                    consensus_extract_pattern = working_zone_config.get('consensus_extract', '')
                    if consensus_extract_pattern and consensus_extract_pattern.strip():
                        consensus_pattern = consensus_extract_pattern
                        cleanup_pattern = working_zone_config.get('cleanup_pattern', '')
                        
                        # Test pattern like Build Mode: expanded zone (+5%) first, then full document fallback
                        model_comparison = ocr_result.get('model_comparison', {})
                        per_model_outputs = model_comparison.get('per_model_outputs', {})
                        
                        if per_model_outputs:
                            # Create expanded zone config (like Build Mode)
                            y_min, y_max = working_zone_config['y_range']
                            x_min, x_max = working_zone_config['x_range']
                            expand_factor = 0.05  # 5% expansion like Build Mode

                            expanded_y = (max(0, y_min - expand_factor), min(1, y_max + expand_factor))
                            expanded_x = (max(0, x_min - expand_factor), min(1, x_max + expand_factor))

                            expanded_zone_config = working_zone_config.copy()
                            expanded_zone_config['y_range'] = expanded_y
                            expanded_zone_config['x_range'] = expanded_x
                            expanded_zone_config['cleanup_pattern'] = ''  # Don't apply cleanup to zone text

                            # Use extract_from_zone_multimodel like Build Mode (correct approach!)
                            model_expanded_zone_results = extract_from_zone_multimodel(
                                ocr_result, expanded_zone_config, words
                            )

                            for model_name, model_data in per_model_outputs.items():
                                # Get expanded zone text for this model
                                expanded_zone_text = model_expanded_zone_results.get(model_name, '')

                                # Test pattern on expanded zone ONLY (NO fallback to full document)
                                extracted_value = ""
                                if expanded_zone_text:
                                    try:
                                        match = re.search(consensus_pattern, expanded_zone_text, re.IGNORECASE | re.MULTILINE)
                                        if match:
                                            if match.lastindex and match.lastindex >= 1:
                                                # Has capturing group
                                                extracted_value = match.group(1).strip()
                                            else:
                                                # No capturing group, use full match
                                                extracted_value = match.group(0).strip()

                                            # Apply cleanup to extracted value (not search text)
                                            if cleanup_pattern and extracted_value:
                                                try:
                                                    extracted_value = re.sub(cleanup_pattern, '', extracted_value, flags=re.IGNORECASE).strip()
                                                except:
                                                    pass
                                    except:
                                        pass
                                
                                pattern_model_results[model_name] = extracted_value

                            # Normalize and validate EACH model's result BEFORE voting (like Build Mode & Production)
                            field_format = working_zone_config.get('format', 'string')
                            format_options = {}
                            if field_format == 'date':
                                format_options['date_format'] = working_zone_config.get('date_format', 'MM.DD.YYYY')
                            elif field_format == 'height':
                                format_options['height_format'] = working_zone_config.get('height_format', 'auto')
                            elif field_format == 'weight':
                                format_options['weight_format'] = working_zone_config.get('weight_format', 'auto')

                            validation_pattern = working_zone_config.get('pattern', '')

                            pattern_model_results_normalized = {}
                            for model_name, raw_value in pattern_model_results.items():
                                if raw_value:
                                    # Normalize each model's value
                                    normalized = normalize_field(raw_value, field_format, field_name, **format_options)
                                    # Only include valid normalized results in voting
                                    if normalized and (not validation_pattern or re.match(validation_pattern, normalized)):
                                        pattern_model_results_normalized[model_name] = normalized

                            # Vote on NORMALIZED values (like Build Mode & Production)
                            if pattern_model_results_normalized:
                                pattern_vote_counts = Counter(pattern_model_results_normalized.values())
                                pattern_consensus_text = pattern_vote_counts.most_common(1)[0][0] if pattern_vote_counts else ""
                                pattern_vote_count = pattern_vote_counts[pattern_consensus_text] if pattern_consensus_text else 0
                                pattern_total_models = len(pattern_model_results_normalized)

                                # Winner is already normalized!
                                pattern_normalized_text = pattern_consensus_text
                                pattern_is_valid = bool(pattern_normalized_text)
                            else:
                                # No valid normalized results
                                pattern_consensus_text = ""
                                pattern_normalized_text = ""
                                pattern_is_valid = False
                                pattern_vote_count = 0
                                pattern_total_models = len(pattern_model_results)
                    
                    # Store results for BOTH methods
                    field_results[field_name] = {
                        # Zone-based results
                        'zone_raw_consensus': zone_consensus_text,
                        'zone_normalized': zone_normalized_text,
                        'zone_is_valid': zone_is_valid,
                        'zone_vote_count': zone_vote_count,
                        'zone_total_models': zone_total_models,
                        'zone_model_results': zone_model_results,
                        
                        # Pattern-based results
                        'pattern_raw_consensus': pattern_consensus_text,
                        'pattern_normalized': pattern_normalized_text,
                        'pattern_is_valid': pattern_is_valid,
                        'pattern_vote_count': pattern_vote_count,
                        'pattern_total_models': pattern_total_models,
                        'pattern_model_results': pattern_model_results,
                        'has_pattern': bool(consensus_extract_pattern and consensus_extract_pattern.strip()),
                        
                        # Common info
                        'field_format': field_format,
                        'format_options': format_options,
                        'zone_config': working_zone_config
                    }
                    
                    # Overall validity: either method should work
                    if not (zone_is_valid or pattern_is_valid):
                        overall_valid = False
                
                # Store test result
                st.session_state.test_results.append({
                    'image_name': file.name,
                    'image': img,
                    'overall_valid': overall_valid,
                    'field_results': field_results,
                    'total_fields': len(field_results),
                    'valid_fields': sum(1 for r in field_results.values() if (r['zone_is_valid'] or r['pattern_is_valid']))
                })
                
        except Exception as e:
            st.error(f"Error processing {file.name}: {str(e)}")
        
        progress_bar.progress((idx + 1) / len(test_files))
    
    status_text.empty()
    progress_bar.empty()
    
    if st.session_state.test_results:
        st.success(f"✅ Processed {len(st.session_state.test_results)} test images")
        st.rerun()


def render_test_results():
    """Display comprehensive test results"""
    st.markdown("#### 📊 Test Results")
    
    # Overall summary with zone vs pattern breakdown
    total_images = len(st.session_state.test_results)
    fully_valid_images = sum(1 for result in st.session_state.test_results if result['overall_valid'])
    
    # Calculate zone vs pattern success rates
    zone_successes = 0
    pattern_successes = 0
    total_zone_fields = 0
    total_pattern_fields = 0
    
    for result in st.session_state.test_results:
        for field_result in result['field_results'].values():
            total_zone_fields += 1
            if field_result['zone_is_valid']:
                zone_successes += 1
            
            if field_result['has_pattern']:
                total_pattern_fields += 1
                if field_result['pattern_is_valid']:
                    pattern_successes += 1
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Images", total_images)
    with col2:
        st.metric("Fully Valid", fully_valid_images)
    with col3:
        zone_rate = (zone_successes / total_zone_fields * 100) if total_zone_fields > 0 else 0
        st.metric("Zone Success", f"{zone_rate:.1f}%")
    with col4:
        pattern_rate = (pattern_successes / total_pattern_fields * 100) if total_pattern_fields > 0 else 0
        st.metric("Pattern Success", f"{pattern_rate:.1f}%" if total_pattern_fields > 0 else "N/A")
    
    # Per-image results
    for result in st.session_state.test_results:
        status_icon = "✅" if result['overall_valid'] else "❌"
        
        with st.expander(
            f"{status_icon} {result['image_name']} - {result['valid_fields']}/{result['total_fields']} fields valid",
            expanded=not result['overall_valid']  # Expand failed images by default
        ):
            # Show image thumbnail
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.image(result['image'], caption=result['image_name'], width=200)
            
            with col2:
                st.markdown("**Field Extraction Results:**")
                
                # Field results table - show both zone-based and pattern-based
                for field_name, field_result in result['field_results'].items():
                    zone_status = "✅" if field_result['zone_is_valid'] else "❌"
                    pattern_status = "✅" if field_result['pattern_is_valid'] else "❌"
                    has_pattern = field_result['has_pattern']
                    
                    # Field summary line
                    zone_text = field_result['zone_normalized'] or field_result['zone_raw_consensus'] or "(empty)"
                    pattern_text = field_result['pattern_normalized'] or field_result['pattern_raw_consensus'] or "(empty)"
                    
                    if has_pattern:
                        summary = f"Zone: {zone_text[:25]} | Pattern: {pattern_text[:25]}"
                        overall_status = "✅" if (field_result['zone_is_valid'] or field_result['pattern_is_valid']) else "❌"
                    else:
                        summary = f"Zone only: {zone_text[:35]}"
                        overall_status = zone_status
                    
                    with st.expander(f"{overall_status} {field_name}: {summary}", expanded=False):
                        # Show both extraction methods side by side
                        if has_pattern:
                            col1, col2 = st.columns(2)
                            
                            # Zone-based extraction column
                            with col1:
                                st.markdown(f"**🎯 Zone-Based Extraction** {zone_status}")

                                # Display with arrow notation like Build Mode
                                if field_result['zone_normalized'] != field_result['zone_raw_consensus'] and field_result['zone_normalized']:
                                    consensus_display = f"{field_result['zone_raw_consensus'] or '(empty)'} → {field_result['zone_normalized']}"
                                    st.code(consensus_display)
                                else:
                                    st.code(field_result['zone_raw_consensus'] or "(empty)")
                                
                                st.metric("Agreement", f"{field_result['zone_vote_count']}/{field_result['zone_total_models']}")
                                
                                # Zone model results
                                if len(field_result['zone_model_results']) > 1:
                                    st.markdown("**Per-model zone results:**")
                                    for model_name, model_text in field_result['zone_model_results'].items():
                                        # Normalize like Build Mode does (use normalize_field imported at top)
                                        model_normalized = normalize_field(
                                            model_text,
                                            field_result['field_format'],
                                            field_name,
                                            **field_result['format_options']
                                        ) if model_text else None

                                        color = "#28a745" if model_text == field_result['zone_raw_consensus'] else "#6c757d"
                                        status = "🏆" if model_text == field_result['zone_raw_consensus'] else "📝"

                                        # Show arrow notation if normalized differs from raw (like Build Mode)
                                        if model_text and model_text != model_normalized and model_normalized:
                                            display = f"{model_text} → {model_normalized}"
                                        else:
                                            display = model_text or '(empty)'

                                        st.markdown(f"""
                                        <div style="margin: 2px 0; padding: 2px 6px; background: {color}15; border-left: 2px solid {color}; border-radius: 3px;">
                                            <span style="color: {color}; font-weight: bold; font-size: 12px;">
                                                {status} {model_name.upper()}:
                                            </span>
                                            <span style="color: #333; margin-left: 4px; font-family: monospace; font-size: 12px;">
                                                {display}
                                            </span>
                                        </div>
                                        """, unsafe_allow_html=True)
                            
                            # Pattern-based extraction column
                            with col2:
                                st.markdown(f"**🔍 Pattern-Based Extraction** {pattern_status}")

                                # Display with arrow notation like Build Mode
                                if field_result['pattern_normalized'] != field_result['pattern_raw_consensus'] and field_result['pattern_normalized']:
                                    consensus_display = f"{field_result['pattern_raw_consensus'] or '(empty)'} → {field_result['pattern_normalized']}"
                                    st.code(consensus_display)
                                else:
                                    st.code(field_result['pattern_raw_consensus'] or "(empty)")
                                
                                if field_result['pattern_total_models'] > 0:
                                    st.metric("Agreement", f"{field_result['pattern_vote_count']}/{field_result['pattern_total_models']}")
                                else:
                                    st.metric("Pattern", "Not configured")
                                
                                # Pattern model results
                                if len(field_result['pattern_model_results']) > 1:
                                    st.markdown("**Per-model pattern results:**")
                                    for model_name, model_text in field_result['pattern_model_results'].items():
                                        # Normalize like Build Mode does (use normalize_field imported at top)
                                        model_normalized = normalize_field(
                                            model_text,
                                            field_result['field_format'],
                                            field_name,
                                            **field_result['format_options']
                                        ) if model_text else None

                                        color = "#28a745" if model_text == field_result['pattern_raw_consensus'] else "#6c757d"
                                        status = "🏆" if model_text == field_result['pattern_raw_consensus'] else "📝"

                                        # Show arrow notation if normalized differs from raw (like Build Mode)
                                        if model_text and model_text != model_normalized and model_normalized:
                                            display = f"{model_text} → {model_normalized}"
                                        else:
                                            display = model_text or '(empty)'

                                        st.markdown(f"""
                                        <div style="margin: 2px 0; padding: 2px 6px; background: {color}15; border-left: 2px solid {color}; border-radius: 3px;">
                                            <span style="color: {color}; font-weight: bold; font-size: 12px;">
                                                {status} {model_name.upper()}:
                                            </span>
                                            <span style="color: #333; margin-left: 4px; font-family: monospace; font-size: 12px;">
                                                {display}
                                            </span>
                                        </div>
                                        """, unsafe_allow_html=True)
                                
                                # Show the pattern being used
                                if field_result['zone_config'].get('consensus_extract'):
                                    st.markdown("**Pattern used:**")
                                    st.code(field_result['zone_config']['consensus_extract'])
                        
                        else:
                            # Zone-only field
                            st.markdown(f"**🎯 Zone-Based Extraction Only** {zone_status}")
                            st.info("💡 No pattern configured - add `consensus_extract` pattern for fallback extraction")

                            # Display with arrow notation like Build Mode
                            if field_result['zone_normalized'] != field_result['zone_raw_consensus'] and field_result['zone_normalized']:
                                consensus_display = f"{field_result['zone_raw_consensus'] or '(empty)'} → {field_result['zone_normalized']}"
                                st.code(consensus_display)
                            else:
                                st.code(field_result['zone_raw_consensus'] or "(empty)")
                            
                            st.metric("Agreement", f"{field_result['zone_vote_count']}/{field_result['zone_total_models']}")
                            
                            # Zone model results
                            if len(field_result['zone_model_results']) > 1:
                                st.markdown("**Per-model zone results:**")
                                for model_name, model_text in field_result['zone_model_results'].items():
                                    # Normalize like Build Mode does (use normalize_field imported at top)
                                    model_normalized = normalize_field(
                                        model_text,
                                        field_result['field_format'],
                                        field_name,
                                        **field_result['format_options']
                                    ) if model_text else None

                                    color = "#28a745" if model_text == field_result['zone_raw_consensus'] else "#6c757d"
                                    status = "🏆" if model_text == field_result['zone_raw_consensus'] else "📝"

                                    # Show arrow notation if normalized differs from raw (like Build Mode)
                                    if model_text and model_text != model_normalized and model_normalized:
                                        display = f"{model_text} → {model_normalized}"
                                    else:
                                        display = model_text or '(empty)'

                                    st.markdown(f"""
                                    <div style="margin: 2px 0; padding: 2px 6px; background: {color}15; border-left: 2px solid {color}; border-radius: 3px;">
                                        <span style="color: {color}; font-weight: bold; font-size: 12px;">
                                            {status} {model_name.upper()}:
                                        </span>
                                        <span style="color: #333; margin-left: 4px; font-family: monospace; font-size: 12px;">
                                            {display}
                                        </span>
                                    </div>
                                    """, unsafe_allow_html=True)


def main():
    """Main application"""
    render_header()
    render_sidebar()

    if st.session_state.view_mode == 'build':
        render_build_mode()
    elif st.session_state.view_mode == 'test':
        render_test_mode()
    elif st.session_state.view_mode == 'export':
        render_export_mode()


if __name__ == "__main__":
    main()