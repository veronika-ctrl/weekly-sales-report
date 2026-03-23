# Weekly Report Pipeline

A deterministic Python CLI pipeline that generates weekly PDF reports from CSV data sources.

## Quick Start

```bash
make install
make run WEEK=2025-42
```

## Requirements

- Python 3.11+
- CSV files placed in `data/raw/{WEEK}/{source}/` directories
- PDF template in `templates/pdf_layout.yaml`

## Data Structure

Place your CSV files in the following structure:
```
data/raw/{WEEK}/
  qlik/*.csv
  dema/*.csv
  shopify/*.csv
  other/*.csv
```

## Outputs

The pipeline generates:
- `data/curated/{WEEK}/` - validated and transformed CSV files
- `charts/{WEEK}/` - rendered charts and tables as PNG/SVG
- `reports/{WEEK}/general.pdf` - general report (A4 landscape)
- `reports/{WEEK}/market.pdf` - market report (A4 landscape)
- `reports/{WEEK}/manifest.json` - metadata and checksums

## Commands

- `make install` - Install dependencies
- `make run WEEK=2025-42` - Generate reports for week 2025-42
- `make test` - Run tests
- `make clean` - Clean generated files

## Configuration

Copy `.env.example` to `.env` and adjust settings:
- `DEFAULT_WEEK` - Default week to process
- `DATA_ROOT` - Root data directory
- `TEMPLATE_PATH` - PDF layout template
- `STRICT_MODE` - Stop on validation errors (default: true)

