"""Visualization theme and styling."""

from typing import Dict, Any

# Color palette
COLORS = {
    'primary': '#1f77b4',      # Blue
    'secondary': '#ff7f0e',    # Orange
    'success': '#2ca02c',      # Green
    'warning': '#d62728',      # Red
    'info': '#9467bd',         # Purple
    'light': '#f0f0f0',        # Light gray
    'dark': '#333333',         # Dark gray
    'text': '#2c3e50',         # Dark blue-gray
    'muted': '#7f8c8d',        # Muted gray
}

# Chart styling
CHART_STYLE = {
    'font_family': 'Arial, sans-serif',
    'font_size': 12,
    'title_font_size': 16,
    'axis_font_size': 10,
    'legend_font_size': 11,
    'margin': {'l': 60, 'r': 60, 't': 80, 'b': 60},
    'background_color': 'white',
    'grid_color': '#e0e0e0',
    'grid_width': 1,
}

# Table styling
TABLE_STYLE = {
    'font_family': 'Arial, sans-serif',
    'font_size': 12,
    'title_font_size': 16,
    'header_font_size': 12,
    'cell_font_size': 10,
    'header_color': COLORS['primary'],
    'header_text_color': 'white',
    'cell_color': 'white',
    'cell_text_color': COLORS['text'],
    'border_color': COLORS['light'],
    'border_width': 1,
}

# Export settings
EXPORT_SETTINGS = {
    'width': 800,      # Default width in pixels
    'height': 600,     # Default height in pixels
    'scale': 2,        # High DPI scaling
    'format': 'png',   # Default format
}

def get_chart_colors(n_colors: int) -> list:
    """Get a list of colors for charts."""
    color_list = [
        COLORS['primary'],
        COLORS['secondary'],
        COLORS['success'],
        COLORS['warning'],
        COLORS['info'],
    ]
    
    # Extend with additional colors if needed
    while len(color_list) < n_colors:
        color_list.append(f"hsl({len(color_list) * 137.5 % 360}, 70%, 50%)")
    
    return color_list[:n_colors]

def format_currency(value: float) -> str:
    """Format currency values."""
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M SEK"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.1f}K SEK"
    else:
        return f"{value:.0f} SEK"

def format_percentage(value: float) -> str:
    """Format percentage values."""
    return f"{value:.1f}%"

def format_number(value: float) -> str:
    """Format large numbers."""
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.1f}K"
    else:
        return f"{value:.0f}"
