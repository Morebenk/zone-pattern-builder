"""
Interactive Zone Builder - Professional Version
===============================================

Complete OCR field zone creation tool with professional UI and full functionality.
"""

import streamlit as st
import requests
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, Counter
import io
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modular components
from zone_builder.field_formats import (
    FIELD_FORMATS, DATE_FORMATS, HEIGHT_FORMATS, WEIGHT_FORMATS,
    get_format_defaults, get_format_help_text,
    get_date_pattern, get_height_pattern, get_weight_pattern
)
from zone_builder.exporters import (
    export_to_json, export_to_python, preview_zone_status
)
from zone_builder.zone_operations import (
    calculate_aggregate_zone, extract_from_zone, extract_from_zone_multimodel,
    get_consensus_from_models, is_in_zone
)
from zone_builder.ocr_utils import (
    call_ocr_api, extract_words, draw_visualization
)
from zone_builder.field_normalizers import (
    normalize_field
)
from zone_builder.session_manager import (
    save_session, load_session, get_session_summary,
    migrate_old_session, auto_save_session
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
    "restrictions", "sex", "hair", "eyes", "height", "weight", "dd_code"
]
FRANCE_FIELDS = [
    "document_number", "nationality", "last_name", "alternate_name",
    "first_name", "sex", "date_of_birth", "birth_place", "height",
    "address", "expiration_date", "issue_date", "issuing_authority"
]

# Session state initialization
if 'images' not in st.session_state:
    st.session_state.images = []
if 'zones' not in st.session_state:
    st.session_state.zones = {}
if 'selections' not in st.session_state:
    st.session_state.selections = defaultdict(set)
if 'current_field' not in st.session_state:
    st.session_state.current_field = None
if 'current_image_idx' not in st.session_state:
    st.session_state.current_image_idx = 0
if 'field_filter' not in st.session_state:
    st.session_state.field_filter = 'All'
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'build'

# Minimal CSS styling
st.markdown("""
<style>
    /* Reduce excessive padding */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }

    /* Fix button text wrapping - keep numbers on same line */
    .stButton > button {
        white-space: nowrap;
        min-width: fit-content;
    }

    /* Info boxes */
    .stAlert {
        padding: 0.75rem;
        border-radius: 4px;
    }

    /* Make expanders more compact */
    .streamlit-expanderHeader {
        font-size: 1rem;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Field definitions
USA_FIELDS = [
    "document_number", "license_class", "date_of_birth", "expiration_date",
    "issue_date", "first_name", "last_name", "address", "endorsement",
    "restrictions", "sex", "hair", "eyes", "height", "weight", "dd_code"
]

FRANCE_FIELDS = [
    "document_number", "nationality", "last_name", "alternate_name",
    "first_name", "sex", "date_of_birth", "birth_place", "height",
    "address", "expiration_date", "issue_date", "issuing_authority"
]

# Session state initialization
if 'images' not in st.session_state:
    st.session_state.images = []
if 'zones' not in st.session_state:
    st.session_state.zones = {}
if 'selections' not in st.session_state:
    st.session_state.selections = defaultdict(set)
if 'current_field' not in st.session_state:
    st.session_state.current_field = None
if 'current_image_idx' not in st.session_state:
    st.session_state.current_image_idx = 0
if 'field_filter' not in st.session_state:
    st.session_state.field_filter = "All"
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'build'


def get_filtered_fields(filter_type: str) -> List[str]:
    """Get field list based on filter"""
    if filter_type == "USA":
        return USA_FIELDS
    elif filter_type == "France":
        return FRANCE_FIELDS
    else:  # "All"
        all_fields = []
        for field in USA_FIELDS + FRANCE_FIELDS:
            if field not in all_fields:
                all_fields.append(field)
        return all_fields


def render_header():
    """Professional header with horizontal mode tabs"""
    st.markdown("## 🎯 Zone Builder Pro")

    # Horizontal mode selector tabs
    tab_col1, tab_col2, tab_col3 = st.columns(3)

    with tab_col1:
        if st.button("🔨 **Build Mode**",
                    type="primary" if st.session_state.view_mode == 'build' else "secondary",
                    use_container_width=True,
                    help="Create and edit zones"):
            st.session_state.view_mode = 'build'
            st.rerun()

    with tab_col2:
        if st.button("🧪 **Test Mode**",
                    type="primary" if st.session_state.view_mode == 'test' else "secondary",
                    use_container_width=True,
                    help="Validate zones across images"):
            st.session_state.view_mode = 'test'
            st.rerun()

    with tab_col3:
        if st.button("📤 **Export Mode**",
                    type="primary" if st.session_state.view_mode == 'export' else "secondary",
                    use_container_width=True,
                    help="Download zone configurations"):
            st.session_state.view_mode = 'export'
            st.rerun()

    # Statistics bar
    if st.session_state.images:
        st.divider()
        stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)

        with stats_col1:
            st.metric("📷 Images", len(st.session_state.images))

        with stats_col2:
            st.metric("🎯 Zones", len(st.session_state.zones))

        with stats_col3:
            # Progress metric
            total_fields = len(get_filtered_fields(st.session_state.field_filter))
            completed = len(st.session_state.zones)
            progress_pct = (completed / total_fields * 100) if total_fields > 0 else 0
            st.metric("✅ Progress", f"{progress_pct:.0f}%",
                     delta=f"{completed}/{total_fields} fields")

        with stats_col4:
            if st.session_state.current_field:
                st.info(f"📝 Working on: **{st.session_state.current_field}**")

    st.divider()


def render_sidebar():
    """Professional sidebar"""
    with st.sidebar:
        st.markdown("### 📁 Project Controls")

        # Tabs for organization
        tab_images, tab_session, tab_settings = st.tabs(["Images", "Session", "Settings"])

        with tab_images:
            # API configuration
            with st.expander("⚙️ OCR Settings", expanded=False):
                api_url = st.text_input(
                    "API URL",
                    value=get_setting('ocr', 'api_url', 'http://localhost:8080/ocr'),
                    key="ocr_api_url"
                )
                set_setting('ocr', 'api_url', api_url)

            # File upload
            st.markdown("#### Upload Documents")
            uploaded_files = st.file_uploader(
                "Select images",
                type=['jpg', 'jpeg', 'png'],
                accept_multiple_files=True,
                key="file_uploader"
            )

            if uploaded_files:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 Process", type="primary", use_container_width=True):
                        process_images(uploaded_files, api_url)
                with col2:
                    if st.session_state.images:
                        if st.button("🗑️ Clear", type="secondary", use_container_width=True):
                            st.session_state.images = []
                            st.session_state.zones = {}
                            st.session_state.selections = defaultdict(set)
                            st.rerun()

        with tab_session:
            render_session_management()

        with tab_settings:
            render_settings_panel()


def process_images(uploaded_files, api_url):
    """Process images with OCR"""
    st.session_state.images = []
    st.session_state.selections = defaultdict(set)

    progress_bar = st.progress(0)
    status_text = st.empty()
    failed_files = []

    for idx, file in enumerate(uploaded_files):
        status_text.text(f"Processing {file.name} ({idx + 1}/{len(uploaded_files)})...")

        try:
            img_bytes = file.getvalue()
            img = Image.open(io.BytesIO(img_bytes))

            # Call OCR with better error handling
            ocr_result = call_ocr_api(img_bytes, file.name, api_url)

            if ocr_result:
                words = extract_words(ocr_result)
                st.session_state.images.append({
                    'name': file.name,
                    'image': img,
                    'ocr_result': ocr_result,
                    'words': words
                })
                # Show success for each image
                st.success(f"✅ {file.name}: {len(words)} words detected")
            else:
                failed_files.append(file.name)
                st.error(f"❌ Failed to process: {file.name}")

        except Exception as e:
            failed_files.append(file.name)
            st.error(f"❌ Error processing {file.name}: {str(e)}")

        progress_bar.progress((idx + 1) / len(uploaded_files))

    status_text.empty()
    progress_bar.empty()

    # Final summary
    if len(st.session_state.images) == len(uploaded_files):
        st.success(f"✅ All {len(st.session_state.images)} images processed successfully!")
    elif len(st.session_state.images) > 0:
        st.warning(f"⚠️ Processed {len(st.session_state.images)}/{len(uploaded_files)} images. Failed: {', '.join(failed_files)}")
    else:
        st.error(f"❌ Failed to process any images. Check if OCR API is running at {api_url}")

    if len(st.session_state.images) > 0:
        st.rerun()


def render_session_management():
    """Session save/load interface"""
    st.markdown("#### 💾 Session Management")

    # Save section
    if st.session_state.images or st.session_state.zones:
        with st.expander("Save Session", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                include_ocr = st.checkbox("Include OCR", value=True)
                include_images = st.checkbox("Include Images", value=True)
            with col2:
                compress = st.checkbox("Compress", value=True)

            if st.button("💾 Generate File", type="primary", use_container_width=True):
                session_bytes = save_session(
                    st.session_state,
                    include_ocr=include_ocr,
                    include_images=include_images,
                    compress=compress
                )
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                extension = ".json.gz" if compress else ".json"

                st.download_button(
                    "⬇️ Download Session",
                    data=session_bytes,
                    file_name=f"session_{timestamp}{extension}",
                    mime="application/octet-stream",
                    use_container_width=True
                )

    # Load section
    st.markdown("#### 📂 Load Session")
    uploaded_session = st.file_uploader(
        "Choose session file",
        type=['json', 'gz'],
        key="session_loader"
    )

    if uploaded_session:
        if st.button("📥 Load", type="primary", use_container_width=True):
            try:
                session_data = load_session(uploaded_session.getvalue())
                if session_data:
                    # Restore state
                    st.session_state.images = session_data.get('images', [])
                    st.session_state.zones = session_data.get('zones', {})
                    st.session_state.selections = defaultdict(set, session_data.get('selections', {}))
                    st.session_state.current_field = session_data.get('current_field')
                    st.session_state.current_image_idx = session_data.get('current_image_idx', 0)
                    st.session_state.field_filter = session_data.get('field_filter', 'All')

                    st.success("✅ Session loaded successfully")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")


def render_build_mode():
    """Professional build interface"""
    if not st.session_state.images:
        render_welcome_screen()
        return

    # Two-column layout
    col_main, col_config = st.columns([3, 2])

    with col_main:
        # Image viewer section
        st.markdown("### 📷 Document Viewer")

        # Image navigation
        render_image_navigation_bar()

        # Display current image
        current_img = st.session_state.images[st.session_state.current_image_idx]
        current_selections = st.session_state.selections[st.session_state.current_image_idx]

        # Draw and display image
        vis_img = draw_visualization(
            current_img['image'],
            current_img['words'],
            current_selections,
            st.session_state.zones,
            st.session_state.current_field
        )

        # Apply image scale setting to control display size
        try:
            from zone_builder.settings_manager import get_setting
            image_scale = get_setting('display', 'image_scale', 1.0)
            # Use column to control image width
            if image_scale < 1.0:
                # Create a column with reduced width
                col_width = int(12 * image_scale)  # Streamlit uses 12-column grid
                col1, col2 = st.columns([col_width, 12 - col_width])
                with col1:
                    st.image(vis_img, width='stretch')
            else:
                st.image(vis_img, width='stretch')
        except:
            st.image(vis_img, width='stretch')

        # Word selection interface
        render_word_selection_interface(current_img['words'], current_selections)

    with col_config:
        render_zone_configuration()


def render_image_navigation_bar():
    """Image navigation with dropdown"""

    # Image selector dropdown
    image_options = [f"{i+1}. {img['name'][:30]}" for i, img in enumerate(st.session_state.images)]

    col1, col2, col3 = st.columns([3, 6, 3])

    with col2:
        selected = st.selectbox(
            "📷 Current Image",
            options=range(len(image_options)),
            format_func=lambda x: image_options[x],
            index=st.session_state.current_image_idx,
            key="image_dropdown"
        )
        if selected != st.session_state.current_image_idx:
            st.session_state.current_image_idx = selected
            st.rerun()

    with col3:
        st.metric("Progress", f"{st.session_state.current_image_idx + 1}/{len(st.session_state.images)}")


def render_word_selection_interface(words, current_selections):
    """Improved word selection interface"""
    st.markdown("#### 🔢 Word Selection")

    # Selection tools
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📝 All", help="Select all words"):
            current_selections.update(range(len(words)))
            st.rerun()
    with col2:
        if st.button("🗑️ Clear", help="Clear selection"):
            current_selections.clear()
            st.rerun()
    with col3:
        if st.button("🔄 Invert", help="Invert selection"):
            all_indices = set(range(len(words)))
            current_selections.symmetric_difference_update(all_indices)
            st.rerun()
    with col4:
        st.info(f"Selected: {len(current_selections)}/{len(words)}")

    # Word buttons grid
    st.markdown("---")
    cols_per_row = 12
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
                    help=f"'{word['text']}'",
                    use_container_width=True
                ):
                    if is_selected:
                        current_selections.remove(i)
                    else:
                        current_selections.add(i)
                    st.rerun()


def render_zone_configuration():
    """Professional zone configuration panel"""
    st.markdown("### ⚙️ Zone Configuration")

    # Field selection section
    st.markdown("#### 📋 Field Selection")

    col1, col2 = st.columns([2, 3])

    with col1:
        region = st.selectbox(
            "Region Filter",
            ["All", "USA", "France"],
            index=["All", "USA", "France"].index(st.session_state.field_filter),
            key="region_selector"
        )
        if region != st.session_state.field_filter:
            st.session_state.field_filter = region
            st.rerun()

    with col2:
        fields = get_filtered_fields(st.session_state.field_filter)

        # Separate created and available fields
        created_fields = [f for f in fields if f in st.session_state.zones]
        available_fields = [f for f in fields if f not in st.session_state.zones]

        # Build options list
        options = []
        if created_fields:
            options.append("── Created Zones ──")
            options.extend([f"✅ {f}" for f in created_fields])
        if available_fields:
            if created_fields:
                options.append("── Available Fields ──")
            options.extend(available_fields)

        if not options:
            options = ["(No fields available)"]

        # Field selector
        field_selection = st.selectbox(
            "Select Field",
            options,
            key="field_dropdown"
        )

        # Process selection
        if field_selection and not field_selection.startswith("──"):
            # Remove checkmark if present
            field_name = field_selection.replace("✅ ", "") if field_selection.startswith("✅") else field_selection

            if field_name != st.session_state.current_field and field_name != "(No fields available)":
                st.session_state.current_field = field_name
                # Clear selections when switching to new field
                if field_name not in st.session_state.zones:
                    st.session_state.selections = defaultdict(set)
                st.rerun()

    # Zone editing section
    if st.session_state.current_field and st.session_state.current_field != "(No fields available)":
        st.divider()
        render_zone_editor()


def render_zone_editor():
    """Zone editing interface"""
    field_name = st.session_state.current_field

    # Get or create zone config
    if field_name in st.session_state.zones:
        zone_config = st.session_state.zones[field_name].copy()
        editing_mode = True
        st.info(f"📝 Editing existing zone: **{field_name}**")
    else:
        zone_config = calculate_aggregate_zone(
            st.session_state.images,
            st.session_state.selections
        )
        editing_mode = False
        if zone_config:
            st.success(f"✨ Auto-calculated zone from {zone_config.get('total_words', 0)} selected words")
        else:
            st.warning("Select words to create a zone")
            return

    # Format configuration
    st.markdown("#### 📐 Format Settings")

    col1, col2 = st.columns(2)

    with col1:
        field_format = st.selectbox(
            "Data Format",
            FIELD_FORMATS,
            index=FIELD_FORMATS.index(zone_config.get('format', 'string')),
            key="format_selector",
            help=get_format_help_text(zone_config.get('format', 'string'))
        )
        zone_config['format'] = field_format

    with col2:
        # Format-specific options
        if field_format == 'date':
            date_format = st.selectbox(
                "Date Format",
                DATE_FORMATS,
                index=DATE_FORMATS.index(zone_config.get('date_format', 'MM.DD.YYYY')),
                key="date_format_selector"
            )
            zone_config['date_format'] = date_format
            zone_config['pattern'] = get_date_pattern(date_format)

        elif field_format == 'height':
            height_format = st.selectbox(
                "Height Format",
                HEIGHT_FORMATS,
                index=HEIGHT_FORMATS.index(zone_config.get('height_format', 'us')),
                key="height_format_selector"
            )
            zone_config['height_format'] = height_format
            zone_config['pattern'] = get_height_pattern(height_format)

        elif field_format == 'weight':
            weight_format = st.selectbox(
                "Weight Format",
                WEIGHT_FORMATS,
                index=WEIGHT_FORMATS.index(zone_config.get('weight_format', 'us')),
                key="weight_format_selector"
            )
            zone_config['weight_format'] = weight_format
            zone_config['pattern'] = get_weight_pattern(weight_format)

        elif field_format == 'sex':
            zone_config['pattern'] = r'^[MF]$'
            st.info("Pattern: ^[MF]$")

    # Live preview FIRST (Zone-Based)
    st.markdown("#### 👁️ Live Preview - Zone Extraction")
    render_live_preview_professional(zone_config)

    # Zone extraction patterns
    st.markdown("#### 🎯 Extraction Patterns")

    # Cleanup pattern
    cleanup_pattern = st.text_input(
        "Cleanup Pattern (removes text)",
        value=zone_config.get('cleanup_pattern', ''),
        placeholder="e.g., ^.*?:\\s* to remove label before colon",
        key="cleanup_pattern_input",
        help="Regex to remove unwanted text before the data"
    )
    zone_config['cleanup_pattern'] = cleanup_pattern

    # Validation pattern (for manual formats)
    if field_format in ['string', 'number']:
        validation_pattern = st.text_input(
            "Validation Pattern",
            value=zone_config.get('pattern', ''),
            placeholder="e.g., ^\\d{8}$ for 8-digit number",
            key="validation_pattern_input",
            help="Regex to validate the extracted data"
        )
        zone_config['pattern'] = validation_pattern

    # Pattern-Based Extraction (Fallback) - AFTER zone config
    st.divider()
    st.markdown("#### 🔄 Fallback: Pattern-Based Extraction")
    st.caption("When zone extraction fails, pattern matching searches the expanded zone (+10% in all directions)")

    # Toggle to show zone text
    col1, col2 = st.columns([3, 1])
    with col1:
        show_zone_text = st.checkbox(
            "Show Expanded Zone Text",
            value=st.session_state.get('show_zone_text', False),
            help="Display text extracted from original and expanded zones"
        )
        st.session_state['show_zone_text'] = show_zone_text

    with col2:
        if st.button("🔬 Test Pattern", help="Test consensus pattern on all images"):
            st.session_state['test_pattern'] = True

    # Consensus pattern input
    consensus_pattern = st.text_area(
        "Consensus Extract Pattern",
        value=zone_config.get('consensus_extract', ''),
        placeholder="e.g., (?:ID|DL)\\s*:?\\s*(\\d{8})",
        height=80,
        key="consensus_pattern_input",
        help="Regex pattern for pattern-based extraction. This searches the expanded zone (10% larger) first, then full text if needed."
    )
    zone_config['consensus_extract'] = consensus_pattern

    # Show zone text if enabled
    if show_zone_text:
        render_zone_text_preview(zone_config)

    # Pattern testing interface
    if st.session_state.get('test_pattern', False) and consensus_pattern:
        render_pattern_testing(zone_config, consensus_pattern)
        st.session_state['test_pattern'] = False

    # Action buttons
    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💾 Save Zone", type="primary", use_container_width=True):
            st.session_state.zones[field_name] = zone_config
            st.success(f"✅ Zone saved for {field_name}")
            # Clear field and selections after save
            st.session_state.current_field = None
            st.session_state.selections = defaultdict(set)
            st.rerun()

    with col2:
        if editing_mode:
            if st.button("🔄 Reset", type="secondary", use_container_width=True):
                st.session_state.current_field = None
                st.session_state.selections = defaultdict(set)
                st.rerun()

    with col3:
        if editing_mode:
            if st.button("🗑️ Delete", type="secondary", use_container_width=True):
                del st.session_state.zones[field_name]
                st.session_state.current_field = None
                st.warning(f"Zone deleted for {field_name}")
                st.rerun()


def render_zone_text_preview(zone_config):
    """Show text extracted from original and expanded zones"""
    st.markdown("**📄 Zone Text Extraction**")

    # Get zone bounds
    y_range = zone_config.get('y_range', (0, 1))
    x_range = zone_config.get('x_range', (0, 1))

    # Calculate expanded bounds (10% expansion)
    expand_factor = 0.10
    y_min, y_max = y_range
    x_min, x_max = x_range

    expanded_y = (max(0, y_min - expand_factor), min(1, y_max + expand_factor))
    expanded_x = (max(0, x_min - expand_factor), min(1, x_max + expand_factor))

    # Collect all expanded zone texts for copying
    all_expanded_texts = []

    # Extract text from zones for each image
    for img_idx, img_data in enumerate(st.session_state.images):
        words = img_data.get('words', [])

        # Extract from original zone
        original_words = [w for w in words if is_in_zone(w, x_range, y_range)]
        original_text = ' '.join(w.get('text', '') for w in original_words)

        # Extract from expanded zone
        expanded_words = [w for w in words if is_in_zone(w, expanded_x, expanded_y)]
        expanded_text = ' '.join(w.get('text', '') for w in expanded_words)

        # Collect for copying
        if expanded_text:
            all_expanded_texts.append(expanded_text)

        with st.expander(f"📄 {img_data['name'][:30]}", expanded=(img_idx == 0)):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Original Zone:**")
                st.text_area(
                    "Text in zone",
                    value=original_text or "(empty)",
                    height=100,
                    disabled=True,
                    key=f"orig_text_{img_idx}"
                )

            with col2:
                st.markdown("**Expanded Zone (+10%):**")
                st.text_area(
                    "Text in expanded zone",
                    value=expanded_text or "(empty)",
                    height=100,
                    disabled=True,
                    key=f"exp_text_{img_idx}"
                )

            # Highlight the difference
            added_text = expanded_text.replace(original_text, "").strip() if original_text else expanded_text
            if added_text:
                st.info(f"**Added by expansion:** {added_text[:100]}...")

    # Add copy button for all expanded zone texts with multi-model outputs
    if st.session_state.images:
        with st.expander("📋 **Copy All Expanded Zone Outputs** (for pattern development)", expanded=False):
            all_model_outputs = []

            for img_data in st.session_state.images:
                # Get multi-model results from expanded zone using the zone operations
                model_results = extract_from_zone_multimodel(
                    img_data.get('ocr_result', {}),
                    {
                        'y_range': expanded_y,
                        'x_range': expanded_x,
                        'cleanup_pattern': zone_config.get('cleanup_pattern', ''),
                        'pattern': zone_config.get('pattern', '')
                    },
                    img_data.get('words', [])
                )

                # Collect all model outputs
                if model_results:
                    for model_name, model_text in model_results.items():
                        if model_text:
                            all_model_outputs.append(model_text)

            # Display all outputs
            if all_model_outputs:
                combined_text = '\n'.join(all_model_outputs)
                st.code(combined_text, language="text")
                st.caption(f"✨ {len(all_model_outputs)} samples from all models in expanded zones - perfect for pattern development!")
            else:
                st.warning("No text found in expanded zones. Make sure OCR has been run on the images.")


def render_pattern_testing(zone_config, pattern):
    """Test consensus pattern on all images with proper workflow"""
    st.markdown("**🔬 Pattern Testing Results**")

    if not pattern:
        st.warning("Please enter a consensus extract pattern to test")
        return

    try:
        compiled_pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as e:
        st.error(f"Invalid regex pattern: {e}")
        return

    # Get patterns for full workflow
    cleanup_pattern = zone_config.get('cleanup_pattern', '')
    validation_pattern = zone_config.get('pattern', '')

    # Get zone bounds
    y_range = zone_config.get('y_range', (0, 1))
    x_range = zone_config.get('x_range', (0, 1))

    # Calculate expanded bounds
    expand_factor = 0.10
    y_min, y_max = y_range
    x_min, x_max = x_range

    expanded_y = (max(0, y_min - expand_factor), min(1, y_max + expand_factor))
    expanded_x = (max(0, x_min - expand_factor), min(1, x_max + expand_factor))

    results = []

    for img_data in st.session_state.images:
        words = img_data.get('words', [])
        ocr_result = img_data.get('ocr_result', {})

        # Extract from expanded zone
        expanded_words = [w for w in words if is_in_zone(w, expanded_x, expanded_y)]
        zone_text = ' '.join(w.get('text', '') for w in expanded_words)

        # Test pattern on zone text
        zone_match = None
        if zone_text:
            match = compiled_pattern.search(zone_text)
            if match:
                zone_match = match.group(1) if match.groups() else match.group(0)

        # Test on all models
        model_results = {}
        for model_name in ['parseq', 'crnn', 'vitstr', 'sar', 'viptr']:
            model_data = ocr_result.get(model_name, {})
            if model_data:
                # Get full text
                full_text = model_data.get('raw_text', '')
                # Try zone text first
                model_match = None
                if zone_text:
                    match = compiled_pattern.search(zone_text)
                    if match:
                        model_match = match.group(1) if match.groups() else match.group(0)
                # Fallback to full text
                if not model_match and full_text:
                    match = compiled_pattern.search(full_text)
                    if match:
                        model_match = match.group(1) if match.groups() else match.group(0)
                if model_match:
                    model_results[model_name] = model_match

        # Get consensus
        if model_results:
            vote_counts = Counter(model_results.values())
            consensus = vote_counts.most_common(1)[0][0] if vote_counts else None
            confidence = vote_counts[consensus] / len(model_results) if consensus else 0
        else:
            consensus = zone_match
            confidence = 1.0 if zone_match else 0

        # Apply cleanup pattern
        cleaned_consensus = consensus
        if consensus and cleanup_pattern:
            try:
                cleaned_consensus = re.sub(cleanup_pattern, '', consensus)
            except:
                cleaned_consensus = consensus

        # Apply validation pattern
        is_valid = True
        if cleaned_consensus and validation_pattern:
            try:
                is_valid = bool(re.match(validation_pattern, cleaned_consensus))
            except:
                is_valid = True

        # Normalize
        field_format = zone_config.get('format', 'string')
        format_options = {}
        if field_format == 'date':
            format_options['date_format'] = zone_config.get('date_format', 'MM.DD.YYYY')
        elif field_format == 'height':
            format_options['height_format'] = zone_config.get('height_format', 'auto')
        elif field_format == 'weight':
            format_options['weight_format'] = zone_config.get('weight_format', 'auto')

        normalized = normalize_field(cleaned_consensus, field_format, **format_options) if cleaned_consensus else None

        results.append({
            'image': img_data['name'],
            'zone_match': zone_match,
            'consensus': consensus,
            'cleaned': cleaned_consensus,
            'normalized': normalized,
            'is_valid': is_valid,
            'confidence': confidence,
            'model_results': model_results
        })

    # Display results
    valid_count = sum(1 for r in results if r['is_valid'])
    st.metric("Validation Success", f"{valid_count}/{len(results)} images",
             delta=f"{valid_count/len(results)*100:.0f}% pass validation")

    for result in results:
        # Status based on validation, not just extraction
        status = "✅" if result['is_valid'] else "❌"
        display_value = result['normalized'] or result['cleaned'] or result['consensus'] or '(no match)'

        with st.expander(f"{status} {result['image'][:30]}: {display_value[:30]}"):
            # Show extraction workflow
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**1️⃣ Extracted:**")
                st.code(result['consensus'] or "(no match)")
                if result['confidence'] < 1.0:
                    st.caption(f"Confidence: {result['confidence']:.0%}")

            with col2:
                st.markdown("**2️⃣ After Cleanup:**")
                st.code(result['cleaned'] or "(no change)")

            with col3:
                st.markdown("**3️⃣ Final Result:**")
                st.code(result['normalized'] or result['cleaned'] or "(empty)")
                if result['is_valid']:
                    st.success("✅ Valid")
                else:
                    st.error("❌ Invalid")

            # Show model results
            if result['model_results']:
                st.markdown("**📊 Model Outputs:**")
                model_text = " | ".join([f"{model}: {value}" for model, value in result['model_results'].items()])
                st.caption(model_text)


def render_live_preview_professional(zone_config):
    """Professional live preview with full details"""

    # Get ALL raw outputs from ALL images for copying
    all_raw_outputs = []
    for img_data in st.session_state.images:
        model_results = extract_from_zone_multimodel(
            img_data.get('ocr_result', {}),
            zone_config,
            img_data.get('words', [])
        )
        if model_results:
            all_raw_outputs.extend(model_results.values())

    # Master copy button
    if all_raw_outputs:
        with st.expander(f"📋 Copy All Raw Outputs ({len(all_raw_outputs)} samples)", expanded=False):
            st.code('\n'.join(all_raw_outputs), language="text")

    # Preview for each image
    for img_idx, img_data in enumerate(st.session_state.images):
        # Get multi-model results
        model_results = extract_from_zone_multimodel(
            img_data.get('ocr_result', {}),
            zone_config,
            img_data.get('words', [])
        )

        # Calculate consensus
        if model_results:
            vote_counts = Counter(model_results.values())
            consensus_text = vote_counts.most_common(1)[0][0] if vote_counts else ""
            vote_count = vote_counts[consensus_text] if consensus_text else 0
            total_models = len(model_results)
        else:
            consensus_text = extract_from_zone(img_data['words'], zone_config)
            vote_count = 1
            total_models = 1

        # Normalize
        field_format = zone_config.get('format', 'string')
        format_options = {}
        if field_format == 'date':
            format_options['date_format'] = zone_config.get('date_format', 'MM.DD.YYYY')
        elif field_format == 'height':
            format_options['height_format'] = zone_config.get('height_format', 'auto')
        elif field_format == 'weight':
            format_options['weight_format'] = zone_config.get('weight_format', 'auto')

        normalized_text = normalize_field(consensus_text, field_format, **format_options) if consensus_text else None

        # Validate
        pattern = zone_config.get('pattern', '')
        is_valid = bool(re.match(pattern, normalized_text)) if pattern and normalized_text else bool(normalized_text)

        # Display
        status_icon = "✅" if is_valid else "❌"
        with st.expander(f"{status_icon} {img_data['name'][:30]}: {(normalized_text or consensus_text or '(empty)')[:30]}",
                        expanded=(img_idx == 0)):

            # Consensus result
            st.markdown(f"**🏆 Consensus** ({vote_count}/{total_models} models agree):")

            col1, col2 = st.columns([3, 1])
            with col1:
                if consensus_text != normalized_text and normalized_text:
                    st.text("Raw extracted:")
                    st.code(consensus_text or "(empty)")
                    st.text("After normalization:")
                    st.code(normalized_text)
                else:
                    st.code(consensus_text or "(empty)")

            with col2:
                st.metric("Status", "Valid" if is_valid else "Invalid",
                         delta=None,
                         delta_color="normal" if is_valid else "inverse")

            # Per-model outputs with colorful styling
            if model_results:
                st.markdown("**📊 Model Outputs:**")

                # Define colors for each model
                model_colors = {
                    'parseq': '#4CAF50',      # Green
                    'crnn': '#2196F3',        # Blue
                    'vitstr': '#FF9800',      # Orange
                    'sar': '#9C27B0',         # Purple
                    'viptr': '#F44336'        # Red
                }

                # Display each model output with colors
                for model_name, model_text in sorted(model_results.items()):
                    model_normalized = normalize_field(model_text, field_format, **format_options) if model_text else None
                    model_valid = bool(re.match(pattern, model_normalized)) if pattern and model_normalized else bool(model_normalized)

                    status = "✅" if model_valid else "❌"
                    color = model_colors.get(model_name, '#666666')

                    # Create styled HTML output
                    if model_text != model_normalized and model_normalized:
                        output_html = f"""
                        <div style="margin: 8px 0; padding: 8px; background: linear-gradient(90deg, {color}15, transparent); border-left: 3px solid {color}; border-radius: 4px;">
                            <span style="color: {color}; font-weight: bold; font-size: 14px;">
                                {status} {model_name.upper()}:
                            </span>
                            <span style="color: #666; margin-left: 10px; font-family: monospace;">
                                {model_text}
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
                            <span style="color: #333; margin-left: 10px; font-family: monospace; font-size: 15px;">
                                {model_text or '(empty)'}
                            </span>
                        </div>
                        """

                    st.markdown(output_html, unsafe_allow_html=True)


def render_test_mode():
    """Test mode with comprehensive validation"""
    st.markdown("### 🧪 Zone Testing & Validation")

    if not st.session_state.zones:
        st.info("No zones created yet. Switch to Build mode to create zones.")
        return

    if not st.session_state.images:
        st.warning("No images loaded. Upload images to test zones.")
        return

    # Test controls
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        test_filter = st.selectbox(
            "Filter zones to test",
            ["All"] + list(st.session_state.zones.keys()),
            key="test_filter"
        )

    with col2:
        show_failures = st.checkbox("Show only failures", key="show_failures")

    with col3:
        if st.button("🔄 Re-test", type="primary"):
            st.rerun()

    st.divider()

    # Run tests
    zones_to_test = st.session_state.zones if test_filter == "All" else {test_filter: st.session_state.zones[test_filter]}

    for field_name, zone_config in zones_to_test.items():
        results = []
        for img_data in st.session_state.images:
            extracted = extract_from_zone(img_data['words'], zone_config)

            # Normalize
            field_format = zone_config.get('format', 'string')
            format_options = {}
            if field_format == 'date':
                format_options['date_format'] = zone_config.get('date_format', 'MM.DD.YYYY')
            elif field_format == 'height':
                format_options['height_format'] = zone_config.get('height_format', 'auto')
            elif field_format == 'weight':
                format_options['weight_format'] = zone_config.get('weight_format', 'auto')

            normalized = normalize_field(extracted, field_format, **format_options) if extracted else None

            # Validate
            pattern = zone_config.get('pattern', '')
            is_valid = bool(re.match(pattern, normalized)) if pattern and normalized else bool(normalized)

            results.append({
                'image': img_data['name'],
                'extracted': extracted,
                'normalized': normalized,
                'valid': is_valid
            })

        # Calculate success rate
        success_rate = sum(1 for r in results if r['valid']) / len(results) * 100 if results else 0

        # Determine status color
        if success_rate >= 90:
            status = "🟢"
            color = "success"
        elif success_rate >= 70:
            status = "🟡"
            color = "warning"
        else:
            status = "🔴"
            color = "error"

        # Skip if showing only failures and this is successful
        if show_failures and success_rate == 100:
            continue

        # Display results
        with st.expander(f"{status} **{field_name}** - {success_rate:.0f}% success rate", expanded=(success_rate < 100)):
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Success Rate", f"{success_rate:.0f}%")
            with col2:
                st.metric("Passed", sum(1 for r in results if r['valid']))
            with col3:
                st.metric("Failed", sum(1 for r in results if not r['valid']))

            # Detailed results
            if success_rate < 100:
                st.markdown("**Failed Extractions:**")
                for result in results:
                    if not result['valid']:
                        st.error(f"❌ {result['image']}: {result['extracted'] or '(empty)'}")

            # Show all results
            with st.expander("View all results", expanded=False):
                for result in results:
                    icon = "✅" if result['valid'] else "❌"
                    if result['normalized'] and result['normalized'] != result['extracted']:
                        st.text(f"{icon} {result['image'][:30]}: {result['extracted']} → {result['normalized']}")
                    else:
                        st.text(f"{icon} {result['image'][:30]}: {result['extracted'] or '(empty)'}")


def render_export_mode():
    """Export mode with options"""
    st.markdown("### 📤 Export Zones")

    if not st.session_state.zones:
        st.info("No zones to export. Create zones in Build mode first.")
        return

    # Export summary
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Zones", len(st.session_state.zones))

        # Zone list
        st.markdown("**Configured Zones:**")
        for field_name, zone_config in st.session_state.zones.items():
            format_type = zone_config.get('format', 'string')
            st.text(f"• {field_name} ({format_type})")

    with col2:
        st.markdown("**Export Options:**")

        # Template name for Python export
        template_name = st.text_input(
            "Template Class Name",
            value="CustomTemplate",
            key="template_name",
            help="Name for the Python template class"
        )

        # Export format selection
        export_format = st.radio(
            "Export Format",
            ["JSON", "Python"],
            horizontal=True,
            key="export_format"
        )

        st.divider()

        # Export buttons
        if export_format == "JSON":
            zones_json = export_to_json(st.session_state.zones)
            st.download_button(
                "📥 Download JSON",
                data=zones_json,
                file_name="zones.json",
                mime="application/json",
                use_container_width=True
            )
        else:
            python_code = export_to_python(st.session_state.zones, template_name)
            st.download_button(
                "📥 Download Python Template",
                data=python_code,
                file_name=f"{template_name.lower()}.py",
                mime="text/plain",
                use_container_width=True
            )

        # Preview
        with st.expander("Preview Export", expanded=False):
            if export_format == "JSON":
                st.json(json.loads(zones_json))
            else:
                st.code(python_code, language="python")


def render_welcome_screen():
    """Welcome screen with animated entrance"""
    # Animated welcome message
    st.markdown("""
    <div style="animation: fadeIn 0.8s ease-in;">
        <h1 style="text-align: center; font-size: 3em; margin-bottom: 0.5em;">
            🎯 Zone Builder Pro
        </h1>
        <p style="text-align: center; color: #666; font-size: 1.2em;">
            Professional OCR Field Extraction Zone Creator
        </p>
    </div>

    <style>
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### 🚀 Quick Start
        1. **Upload** document images
        2. **Process** with OCR
        3. **Select** word numbers
        4. **Save** zones
        5. **Export** configuration
        """)

    with col2:
        st.markdown("""
        ### ✨ Features
        - 5-model consensus OCR
        - Visual zone editing
        - Pattern validation
        - Session persistence
        - Production templates
        """)

    with col3:
        st.markdown("""
        ### 💡 Pro Tips
        - Adjust number size in Settings
        - Save sessions regularly
        - Test zones before export
        - Use Copy All for patterns
        """)

    st.divider()

    # Animated call-to-action
    st.markdown("""
    <div style="text-align: center; animation: pulse 2s infinite;">
        <h3 style="color: #1E88E5;">
            📁 Upload images in the sidebar to begin →
        </h3>
    </div>

    <style>
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
    </style>
    """, unsafe_allow_html=True)


def main():
    """Main application entry point"""
    render_header()
    render_sidebar()

    # Render based on current mode
    if st.session_state.view_mode == 'build':
        render_build_mode()
    elif st.session_state.view_mode == 'test':
        render_test_mode()
    elif st.session_state.view_mode == 'export':
        render_export_mode()
    else:
        render_build_mode()


if __name__ == "__main__":
    main()