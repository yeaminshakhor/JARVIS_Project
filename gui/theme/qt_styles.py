"""Qt style helpers backed by semantic theme tokens."""

from .tokens import THEME, color

_FONTS = {
    "display": THEME["font"]["display"],
    "title": THEME["font"]["title"],
    "body": THEME["font"]["body"],
    "mono": THEME["font"]["mono"],
}


def font_name(kind: str = "body") -> str:
    return _FONTS.get(kind, _FONTS["body"])


def label_style(size: int, role: str = "text_primary", kind: str = "body", weight: int = 400) -> str:
    return (
        f"font-size:{int(size)}px; "
        f"color:{color(role)}; "
        f"font-family:'{font_name(kind)}'; "
        f"font-weight:{int(weight)};"
    )


def reactor_level_color(percent: float) -> str:
    value = float(percent)
    if value < 50.0:
        return color("accent_success")
    if value < 80.0:
        return color("accent_warning")
    return color("accent_error")


def severity_color(severity: str) -> str:
    key = str(severity or "info").strip().lower()
    if key == "critical":
        return color("accent_error")
    if key == "important":
        return color("accent_warning")
    if key == "success":
        return color("accent_success")
    return color("accent_info")
