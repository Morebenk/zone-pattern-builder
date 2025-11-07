# Interactive Zone Builder

A clean, modern tool for creating OCR field extraction zones with visual feedback.

## 🚀 Features

- 📷 **Multi-image OCR processing** - Process multiple documents at once
- 🎯 **Click-based word selection** - Simply click word numbers to select
- 💾 **Complete session save/load** - Including images and OCR results
- ⚙️ **Customizable settings** - Adjust colors, sizes, and behavior
- 🎨 **Improved visibility** - Numbers with shadows and configurable appearance
- 📤 **Export formats** - JSON or Python template code
- 🧪 **Test mode** - Validate zones across all images
- 🔄 **Auto-save** - Never lose your work

## Quick Start

```bash
# 1. Install requirements (if not already installed)
pip install -r zone_builder/requirements.txt

# 2. Start OCR API
python -m uvicorn app.main:app --port 8080

# 3. Launch Zone Builder
streamlit run zone_builder/interactive_zone_builder.py
```

## Usage Workflow

### 1. **Setup Phase**
- Open sidebar and upload document images
- Click "Process Images" to run OCR
- Configure settings if needed (Settings tab)

### 2. **Build Mode**
- Select region filter (USA/France/All)
- Choose a field from dropdown
- Click numbered buttons to select words
- Zone auto-calculates from selections
- Adjust patterns if needed
- Save zone

### 3. **Test Mode**
- Switch to Test mode
- Review extraction success rates
- Identify problematic zones
- Return to Build mode to fix

### 4. **Export Mode**
- Switch to Export mode
- Download as JSON or Python template
- Use in your extraction system

## Settings Panel

Access via sidebar Settings tab:

- **Display Settings**
  - Number size/color/opacity
  - Selection box appearance
  - Zone visualization

- **Behavior Settings**
  - Auto-save intervals
  - Multi-select modes
  - Confirmation dialogs

## Session Management

### Save Session
- Preserves everything: images, OCR, zones, selections
- Compressed .json.gz format
- Includes all work progress

### Load Session
- Restore complete workspace
- No need to re-run OCR
- Continue exactly where you left off

## Tips & Tricks

- 🔢 **Numbers** correspond to detected words
- 🟢 **Green boxes** indicate selected words
- 🟠 **Orange zones** show current field area
- 🔍 **Live preview** shows extraction results
- 📋 **Copy All** button for pattern development with AI

## File Structure

```
zone_builder/
├── interactive_zone_builder.py  # Main application
├── session_manager.py           # Save/load functionality
├── settings_manager.py          # Settings configuration
├── field_normalizers.py         # Field normalization
├── field_formats.py             # Format definitions
├── zone_operations.py           # Zone calculations
├── ocr_utils.py                 # OCR and visualization
├── exporters.py                 # Export functionality
└── copilot_context/            # AI pattern assistance
```
