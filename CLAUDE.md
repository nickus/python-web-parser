# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

This is a Python 3.13 project with a virtual environment (.venv) already configured. It's a complete material matching system that finds similarities between materials and price lists using Elasticsearch and advanced similarity algorithms.

## Development Environment

- **Python Version**: 3.13.7
- **Virtual Environment**: Located at `.venv/` (Windows: `.venv\Scripts\activate`)
- **Dependencies**: Listed in `requirements.txt` (elasticsearch==8.15.1, pandas, fuzzywuzzy, customtkinter, etc.)
- **Configuration**: `config.json` for basic settings, `config_optimized.json` for performance tuning

## Project Overview

Material matching system that finds similarities between materials and price lists using Elasticsearch and advanced similarity algorithms.

### Key Features
- Material and price list loading from CSV, Excel (.xlsx), JSON
- Elasticsearch-powered full-text search with Russian language support
- Multi-criteria similarity percentage calculation (weighted scoring algorithm)
- Batch processing with configurable threading
- Interactive GUI with variant selection and double-click functionality
- Results export in JSON/CSV/Excel (.xlsx) formats with selected variants only

## Common Commands

```bash
# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Elasticsearch (required for all operations)
docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" elasticsearch:8.15.1

# Primary interfaces
python main.py --gui                    # RECOMMENDED: Full GUI interface
python main.py --init                   # Interactive CLI setup for first-time use

# Core operations
python main.py --setup                  # Create/recreate Elasticsearch indices
python main.py --check-connection       # Verify Elasticsearch connectivity

# Complete workflow
python main.py --setup --materials data/materials.csv --price-list data/price_list.csv --output results.json

# Search operations
python main.py --search-material "Кабель ВВГНГ" --top-n 5
python main.py --materials data/materials.csv --price-list data/price_list.csv --threshold 30 --format xlsx --output results.xlsx

# Testing
python test_app.py                      # Main application test
python test_performance_optimizations.py # Performance testing
```

### Development Workflow
1. Ensure Elasticsearch is running: `docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" elasticsearch:8.15.1`
2. Use `python main.py --gui` for main development interface (recommended)
3. For CLI setup use `python main.py --init` for guided configuration
4. Run `python test_app.py` to verify system functionality
5. Use `config_optimized.json` for performance-critical environments

## Architecture

The system follows a layered architecture with clear separation of concerns:

### Core Service Layer
- **ElasticsearchService** (`src/services/elasticsearch_service.py`): Index management, search operations, bulk operations with Russian language analysis
- **SimilarityService** (`src/services/similarity_service.py`): Multi-criteria similarity calculation with weighted scoring
- **MatchingService** (`src/services/matching_service.py`): Orchestrates the complete matching workflow
- **MaterialMatcherApp** (`src/material_matcher_app.py`): Main application facade

### Data Layer
- **Models** (`src/models/material.py`): Material, PriceListItem, SearchResult data classes
- **DataLoader** (`src/utils/data_loader.py`): File I/O operations for CSV/Excel/JSON formats

### Presentation Layer
- **GUI Application** (`gui_app.py`): Full-featured tkinter interface with variant selection
- **CLI Interface** (`main.py`): Command-line interface with interactive setup mode

### Similarity Algorithm Architecture
Multi-criteria weighted approach:
- Name similarity (40% weight) - Primary matching criterion
- Description similarity (20% weight) - Contextual matching
- Category similarity (15% weight) - Classification matching
- Brand similarity (15% weight) - Manufacturer matching
- Specifications similarity (10% weight) - Technical parameter matching

Uses fuzzywuzzy for string similarity, tokenization for partial matching, and semantic analysis for contextual understanding.

### GUI Variant Selection System
- **Double-click selection**: Click any variant in "Вариант из прайс-листа" column
- **State management**: Selected variants stored in `self.selected_variants` dict
- **Visual feedback**: Green highlighting for selected variants, material name prefix "➤ Selected Variant"
- **Export filtering**: "✅ Экспорт выбранных (Excel)" exports only selected variants
- **State reset**: "🔄 Сбросить выборы" clears selections and restores full view

## Important Development Notes

- **Entry Points**: `main.py --gui` (primary), `main.py --init` (setup), `test_app.py` (testing)
- **Elasticsearch Dependency**: All core functionality requires Elasticsearch running on localhost:9200
- **Configuration**: Use `config_optimized.json` for production environments (higher bulk_size, more workers)
- **Logging**: Application logs to `material_matcher.log` with UTF-8 encoding
- **Threading**: Configurable via `max_workers` in config (recommended: 4-6 for optimal performance)
- **Testing**: Multiple test files exist (`test_*.py`) for different functionality areas
- **Russian Language Support**: Built-in Russian analyzer for improved text matching

## Code Style Rules

- **IMPORTANT**: All code comments MUST be written in Russian language
- **Comment Language**: Use Russian for all inline comments, docstrings, and code documentation
- **Variable Names**: Use English for variable and function names, but document them in Russian
- **Error Messages**: User-facing error messages should be in Russian
- **Documentation**: Internal code documentation should be in Russian to match the project's language context