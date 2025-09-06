# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

This is a Python 3.13 project with a virtual environment (.venv) already configured. This is a complete material matching system that finds similarities between materials and price lists using Elasticsearch and advanced similarity algorithms.

## Development Environment

- **Python Version**: 3.13.7
- **Virtual Environment**: Located at `.venv/`
- **IDE**: PyCharm (configuration in `.idea/`)
- **Dependencies**: Listed in `requirements.txt` (elasticsearch, pandas, fuzzywuzzy, etc.)

## Project Overview

This is a full-featured material matching system that finds similarities between materials and price lists using Elasticsearch and advanced similarity algorithms.

### Key Features
- Material and price list loading from CSV, Excel (.xlsx), JSON
- Elasticsearch-powered full-text search
- Multi-criteria similarity percentage calculation (100% for identical core fields)
- Batch processing with threading
- Interactive variant selection in GUI with double-click
- Results export in JSON/CSV/Excel (.xlsx) formats
- Export of selected variants only

## Common Commands

```bash
# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Elasticsearch (required for the application)
docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" elasticsearch:8.15.1

# RECOMMENDED: GUI interface
python main.py --gui

# Interactive setup for first-time use
python main.py --init

# Run the main application with sample data
python main.py --setup --materials data/sample/materials.csv --price-list data/sample/price_list.csv --output results.json

# Test the application
python test_app.py

# Run with custom parameters  
python main.py --materials data/materials.csv --price-list data/price_list.csv --threshold 30 --format csv --output results.csv

# Setup indices only
python main.py --setup

# Check Elasticsearch connection
python main.py --check-connection

# Search specific material
python main.py --search-material "Кабель ВВГНГ" --top-n 5
```

### Development Workflow
1. **GUI Interface**: Use `python main.py --gui` for graphical interface (recommended)
2. **First Time Setup**: Use `python main.py --init` for interactive CLI setup
3. Ensure Elasticsearch is running before testing or running the application
4. Run `python test_app.py` to verify system functionality
5. Sample data is available in `data/sample/` for testing
6. Configuration can be modified in `config.json`

### GUI Variant Selection Feature
- **Double-click selection**: Double-click any variant in "Вариант из прайс-листа" column
- **Auto-hide others**: All other variants for that material are automatically hidden
- **Visual feedback**: Selected variant highlighted in green, material name updated with "➤ Selected Variant"
- **Export selected**: Use "✅ Экспорт выбранных (Excel)" to export only chosen variants
- **Reset selections**: Use "🔄 Сбросить выборы" to clear all selections and restore full view

## Architecture

### Core Components
- `src/models/material.py` - Data models (Material, PriceListItem, SearchResult)
- `src/services/elasticsearch_service.py` - Elasticsearch operations
- `src/services/similarity_service.py` - Similarity calculation algorithms  
- `src/services/matching_service.py` - Material matching logic
- `src/utils/data_loader.py` - File loading and export utilities
- `src/material_matcher_app.py` - Main application class

### Similarity Algorithm
Multi-criteria approach with weighted scoring:
- Name similarity (40% weight)
- Description similarity (20% weight)  
- Category similarity (15% weight)
- Brand similarity (15% weight)
- Specifications similarity (10% weight)

Uses fuzzy string matching, tokenization, and semantic analysis.

## Important Development Notes

- **Entry Points**: Use `main.py --gui` for GUI, `main.py` for CLI, `test_app.py` for testing
- **GUI Interface**: `gui_app.py` provides full-featured graphical interface with tkinter
- **First Time Setup**: Use `python main.py --init` for guided CLI setup process
- **Logging**: Application logs to `material_matcher.log` - check this for debugging
- **Prerequisites**: Elasticsearch must be running before any operations
- **Test Data**: Sample materials and price lists in `data/sample/` for testing
- **Threading**: Uses configurable multi-threading (max_workers in config.json)
- **Performance**: System handles batch processing with progress tracking
- **Interactive Modes**: GUI (`--gui`) and CLI interactive setup (`--init`)