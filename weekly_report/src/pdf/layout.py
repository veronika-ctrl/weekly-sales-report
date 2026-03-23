"""PDF layout configuration and loading."""

from pathlib import Path
from typing import Dict, Any, List

import yaml
from loguru import logger


class PDFLayout:
    """PDF layout configuration."""
    
    def __init__(self, layout_data: Dict[str, Any]):
        self.layout_data = layout_data
        self.pages = layout_data.get('pages', {})
        self.global_settings = layout_data.get('global', {})
    
    def get_page_layout(self, page_name: str) -> Dict[str, Any]:
        """Get layout for a specific page."""
        return self.pages.get(page_name, {})
    
    def get_placeholder(self, page_name: str, placeholder_name: str) -> Dict[str, Any]:
        """Get placeholder configuration."""
        page_layout = self.get_page_layout(page_name)
        placeholders = page_layout.get('placeholders', {})
        return placeholders.get(placeholder_name, {})
    
    def get_page_size(self) -> tuple:
        """Get page size in points."""
        width = self.global_settings.get('width', 842)
        height = self.global_settings.get('height', 595)
        return (width, height)
    
    def get_font_settings(self) -> Dict[str, Any]:
        """Get font settings."""
        return self.global_settings.get('fonts', {})
    
    def get_color_settings(self) -> Dict[str, Any]:
        """Get color settings."""
        return self.global_settings.get('colors', {})


def load_pdf_layout(template_path: Path) -> PDFLayout:
    """Load PDF layout configuration from YAML file."""
    
    if not template_path.exists():
        logger.warning(f"PDF layout template not found: {template_path}")
        return create_default_layout()
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            layout_data = yaml.safe_load(f)
        
        logger.info(f"Loaded PDF layout from {template_path}")
        return PDFLayout(layout_data)
        
    except Exception as e:
        logger.error(f"Failed to load PDF layout: {e}")
        return create_default_layout()


def create_default_layout() -> PDFLayout:
    """Create default PDF layout configuration."""
    
    default_layout = {
        'global': {
            'width': 842,
            'height': 595,
            'fonts': {
                'title': {'name': 'Helvetica-Bold', 'size': 24},
                'subtitle': {'name': 'Helvetica-Bold', 'size': 18},
                'body': {'name': 'Helvetica', 'size': 12},
                'small': {'name': 'Helvetica', 'size': 10}
            },
            'colors': {
                'primary': '#1f77b4',
                'secondary': '#ff7f0e',
                'text': '#333333',
                'muted': '#666666'
            }
        },
        'pages': {
            'general': {
                'placeholders': {
                    'title': {'x': 50, 'y': 550, 'width': 400, 'height': 30},
                    'kpi_grid': {'x': 50, 'y': 500, 'width': 400, 'height': 200},
                    'chart_left': {'x': 50, 'y': 300, 'width': 350, 'height': 200},
                    'chart_right': {'x': 450, 'y': 300, 'width': 350, 'height': 200},
                    'table_bottom': {'x': 50, 'y': 50, 'width': 750, 'height': 200}
                }
            },
            'market': {
                'placeholders': {
                    'title': {'x': 50, 'y': 550, 'width': 400, 'height': 30},
                    'kpi_grid': {'x': 50, 'y': 500, 'width': 400, 'height': 200},
                    'chart_left': {'x': 50, 'y': 300, 'width': 350, 'height': 200},
                    'chart_right': {'x': 450, 'y': 300, 'width': 350, 'height': 200},
                    'table_bottom': {'x': 50, 'y': 50, 'width': 750, 'height': 200}
                }
            }
        }
    }
    
    logger.info("Created default PDF layout")
    return PDFLayout(default_layout)

