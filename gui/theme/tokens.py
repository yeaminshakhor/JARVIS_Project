"""Semantic design tokens shared by GUI renderers."""

THEME = {
    "color": {
        "bg_primary": "#0A0F1A",
        "bg_secondary": "#141C2C",
        "bg_tertiary": "#1E2A3A",
        "accent_info": "#00E5FF",
        "accent_success": "#00FF9D",
        "accent_warning": "#FFB74D",
        "accent_error": "#FF5252",
        "text_primary": "#FFFFFF",
        "text_secondary": "#B0C4DE",
        "text_tertiary": "#708090",
        "border_light": "rgba(255,255,255,0.10)",
        "border_medium": "rgba(255,255,255,0.20)",
        "panel_overlay": "rgba(8, 14, 22, 150)",
        "input_bg": "#061019",
        "input_border": "#325067",
    },
    "font": {
        "display": "Orbitron",
        "title": "Rajdhani",
        "body": "Inter",
        "mono": "Share Tech Mono",
    },
}


def color(name: str, default: str = "#FFFFFF") -> str:
    """Fetch a semantic color token by name with fallback."""
    return THEME.get("color", {}).get(name, default)
