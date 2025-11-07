"""
Session Management - Complete Save/Load with OCR Results
=========================================================

This module handles saving and loading complete sessions including:
- Images (as base64)
- OCR results (complete API responses)
- Word detections
- Zones configurations
- Selections (word indices)
- All session state
"""

import json
import base64
import io
import gzip
from typing import Dict, List, Any, Optional
from PIL import Image
from datetime import datetime
from pathlib import Path


def image_to_base64(image: Image.Image, format: str = "JPEG") -> str:
    """Convert PIL Image to base64 string"""
    buffer = io.BytesIO()
    # Convert RGBA to RGB if necessary
    if image.mode == 'RGBA' and format == "JPEG":
        rgb_image = Image.new('RGB', image.size, (255, 255, 255))
        rgb_image.paste(image, mask=image.split()[3] if len(image.split()) == 4 else None)
        image = rgb_image
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def base64_to_image(base64_str: str) -> Image.Image:
    """Convert base64 string back to PIL Image"""
    image_data = base64.b64decode(base64_str)
    return Image.open(io.BytesIO(image_data))


def save_session(session_state: Dict[str, Any],
                 include_ocr: bool = True,
                 include_images: bool = True,
                 compress: bool = True) -> bytes:
    """
    Save complete session data including images and OCR results

    Args:
        session_state: Streamlit session state object
        include_ocr: Whether to include OCR results (saves re-processing)
        include_images: Whether to include image data
        compress: Whether to compress the output

    Returns:
        Bytes data ready for download
    """

    # Prepare session data with metadata
    session_data = {
        'version': '2.0',  # Version for backwards compatibility
        'timestamp': datetime.now().isoformat(),
        'metadata': {
            'num_images': len(session_state.get('images', [])),
            'num_zones': len(session_state.get('zones', {})),
            'include_ocr': include_ocr,
            'include_images': include_images,
        }
    }

    # Save images with OCR results
    images_data = []
    for img_data in session_state.get('images', []):
        image_entry = {
            'name': img_data['name'],
        }

        # Include image as base64 if requested
        if include_images and 'image' in img_data:
            try:
                image_entry['image_base64'] = image_to_base64(img_data['image'])
                image_entry['image_size'] = img_data['image'].size
            except Exception as e:
                print(f"Warning: Could not save image {img_data['name']}: {e}")

        # Include OCR results if requested
        if include_ocr:
            if 'ocr_result' in img_data:
                image_entry['ocr_result'] = img_data['ocr_result']
            if 'words' in img_data:
                image_entry['words'] = img_data['words']

        images_data.append(image_entry)

    session_data['images'] = images_data

    # Save zones with all configurations
    session_data['zones'] = session_state.get('zones', {})

    # Save selections (convert sets to lists for JSON)
    selections = session_state.get('selections', {})
    session_data['selections'] = {
        str(k): list(v) for k, v in selections.items()
    }

    # Save current state
    session_data['current_field'] = session_state.get('current_field')
    session_data['current_image_idx'] = session_state.get('current_image_idx', 0)
    session_data['field_filter'] = session_state.get('field_filter', 'All')

    # Save draft configurations if any
    session_data['zone_config_draft'] = session_state.get('zone_config_draft', {})

    # Save template metadata
    session_data['metadata'] = session_state.get('metadata', {
        'template_name': 'my_template',
        'class_name': 'MyTemplate',
        'document_type': 'Driver License',
        'region': 'USA',
        'version': '1.0',
    })

    # Convert to JSON
    json_str = json.dumps(session_data, indent=2)

    # Compress if requested
    if compress:
        return gzip.compress(json_str.encode('utf-8'))
    else:
        return json_str.encode('utf-8')


def load_session(file_data: bytes,
                  validate: bool = True) -> Optional[Dict[str, Any]]:
    """
    Load complete session data from file

    Args:
        file_data: Bytes data from uploaded file
        validate: Whether to validate the data structure

    Returns:
        Dictionary with session data or None if error
    """

    try:
        # Try to decompress first (handle both compressed and uncompressed)
        try:
            json_str = gzip.decompress(file_data).decode('utf-8')
        except:
            json_str = file_data.decode('utf-8')

        # Parse JSON
        session_data = json.loads(json_str)

        # Validate if requested
        if validate:
            if not validate_session_data(session_data):
                return None

        # Process loaded data
        processed_data = {
            'version': session_data.get('version', '1.0'),
            'metadata': session_data.get('metadata', {}),
        }

        # Process images
        images = []
        for img_entry in session_data.get('images', []):
            img_data = {
                'name': img_entry['name']
            }

            # Restore image from base64
            if 'image_base64' in img_entry:
                try:
                    img_data['image'] = base64_to_image(img_entry['image_base64'])
                except Exception as e:
                    print(f"Warning: Could not restore image {img_entry['name']}: {e}")
                    # Create placeholder image
                    img_data['image'] = create_placeholder_image(img_entry.get('image_size', (800, 600)))

            # Restore OCR results
            if 'ocr_result' in img_entry:
                img_data['ocr_result'] = img_entry['ocr_result']

            if 'words' in img_entry:
                img_data['words'] = img_entry['words']

            images.append(img_data)

        processed_data['images'] = images

        # Process zones
        processed_data['zones'] = session_data.get('zones', {})

        # Process selections (convert back to sets and use defaultdict)
        from collections import defaultdict
        selections_dict = session_data.get('selections', {})
        processed_data['selections'] = defaultdict(set, {
            int(k): set(v) for k, v in selections_dict.items()
        })

        # Process other state
        processed_data['current_field'] = session_data.get('current_field')
        processed_data['current_image_idx'] = session_data.get('current_image_idx', 0)
        processed_data['field_filter'] = session_data.get('field_filter', 'All')
        processed_data['zone_config_draft'] = session_data.get('zone_config_draft', {})

        # Process metadata
        processed_data['metadata'] = session_data.get('metadata', {
            'template_name': 'my_template',
            'class_name': 'MyTemplate',
            'document_type': 'Driver License',
            'region': 'USA',
            'version': '1.0',
        })

        return processed_data

    except Exception as e:
        print(f"Error loading session: {e}")
        return None


def validate_session_data(session_data: Dict[str, Any]) -> bool:
    """Validate session data structure"""

    # Check version compatibility
    version = session_data.get('version', '1.0')
    if not version.startswith(('1.', '2.')):
        print(f"Incompatible session version: {version}")
        return False

    # Check required fields
    if 'images' not in session_data:
        print("Missing 'images' in session data")
        return False

    # Validate images structure
    for idx, img in enumerate(session_data.get('images', [])):
        if 'name' not in img:
            print(f"Image {idx} missing 'name'")
            return False

    # Validate zones structure
    zones = session_data.get('zones', {})
    for field_name, zone_config in zones.items():
        if 'x_range' not in zone_config or 'y_range' not in zone_config:
            print(f"Zone {field_name} missing coordinate ranges")
            return False

    return True


def create_placeholder_image(size: tuple = (800, 600)) -> Image.Image:
    """Create a placeholder image when original can't be restored"""
    from PIL import ImageDraw, ImageFont

    img = Image.new('RGB', size, color=(240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Add text
    text = "Image Not Available\n(OCR data preserved)"
    try:
        # Try to use a better font if available
        font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = ImageFont.load_default()

    # Center the text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2

    draw.text((x, y), text, fill=(128, 128, 128), font=font)

    # Add border
    draw.rectangle([(0, 0), (size[0]-1, size[1]-1)], outline=(200, 200, 200), width=2)

    return img


def get_session_summary(session_data: Dict[str, Any]) -> str:
    """Get a human-readable summary of session contents"""

    metadata = session_data.get('metadata', {})

    summary = []
    summary.append(f"📅 Saved: {session_data.get('timestamp', 'Unknown')}")
    summary.append(f"🔢 Version: {session_data.get('version', 'Unknown')}")
    summary.append(f"🖼️ Images: {metadata.get('num_images', 0)}")
    summary.append(f"📦 Zones: {metadata.get('num_zones', 0)}")

    if metadata.get('include_ocr'):
        summary.append("✅ OCR results included")
    else:
        summary.append("❌ OCR results not included")

    if metadata.get('include_images'):
        summary.append("✅ Image data included")
    else:
        summary.append("❌ Image data not included")

    # Add file size info if available
    if 'file_size' in metadata:
        size_mb = metadata['file_size'] / (1024 * 1024)
        summary.append(f"📊 Size: {size_mb:.2f} MB")

    return "\n".join(summary)


def migrate_old_session(old_session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate old session format to new format"""

    # Check if this is old format (no version field)
    if 'version' not in old_session_data:
        print("Migrating old session format to v2.0")

        # Old format only had: zones, selections, current_field, field_filter
        new_session = {
            'version': '2.0',
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'num_zones': len(old_session_data.get('zones', {})),
                'num_images': 0,
                'include_ocr': False,
                'include_images': False,
            },
            'images': [],  # No images in old format
            'zones': old_session_data.get('zones', {}),
            'selections': old_session_data.get('selections', {}),
            'current_field': old_session_data.get('current_field'),
            'current_image_idx': 0,
            'field_filter': old_session_data.get('field_filter', 'All'),
            'zone_config_draft': {}
        }

        return new_session

    return old_session_data


def auto_save_session(session_state: Dict[str, Any],
                       save_dir: str = "zone_builder_sessions") -> Optional[str]:
    """
    Auto-save session to local directory

    Returns:
        Path to saved file or None if error
    """

    try:
        # Create directory if not exists
        save_path = Path(save_dir)
        save_path.mkdir(exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{timestamp}.json.gz"
        file_path = save_path / filename

        # Save session
        session_data = save_session(session_state, compress=True)

        with open(file_path, 'wb') as f:
            f.write(session_data)

        # Clean up old auto-saves (keep last 10)
        cleanup_old_autosaves(save_path, keep_last=10)

        return str(file_path)

    except Exception as e:
        print(f"Auto-save failed: {e}")
        return None


def cleanup_old_autosaves(save_dir: Path, keep_last: int = 10):
    """Remove old auto-save files, keeping only the most recent ones"""

    try:
        # Get all session files
        session_files = sorted(save_dir.glob("session_*.json.gz"),
                             key=lambda x: x.stat().st_mtime,
                             reverse=True)

        # Delete older files
        for file_path in session_files[keep_last:]:
            file_path.unlink()

    except Exception as e:
        print(f"Cleanup failed: {e}")


def list_saved_sessions(save_dir: str = "zone_builder_sessions") -> List[Dict[str, Any]]:
    """List all saved sessions with metadata"""

    sessions = []
    save_path = Path(save_dir)

    if not save_path.exists():
        return sessions

    for file_path in save_path.glob("session_*.json.gz"):
        try:
            # Get file info
            stat = file_path.stat()

            # Try to load metadata without loading entire file
            with open(file_path, 'rb') as f:
                file_data = f.read()
                session_data = load_session(file_data, validate=False)

                if session_data:
                    sessions.append({
                        'filename': file_path.name,
                        'path': str(file_path),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'metadata': session_data.get('metadata', {}),
                        'timestamp': session_data.get('timestamp'),
                    })

        except Exception as e:
            print(f"Could not read session {file_path}: {e}")

    return sorted(sessions, key=lambda x: x['modified'], reverse=True)