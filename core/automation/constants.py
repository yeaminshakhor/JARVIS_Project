"""Constants shared across automation modules."""

from __future__ import annotations

SUPPORTED_WEBSITES = {
    "youtube": "https://youtube.com",
    "facebook": "https://facebook.com",
    "google": "https://google.com",
    "gmail": "https://gmail.com",
    "github": "https://github.com",
    "twitter": "https://twitter.com",
    "instagram": "https://instagram.com",
    "whatsapp": "https://web.whatsapp.com",
    "reddit": "https://reddit.com",
    "linkedin": "https://linkedin.com",
    "netflix": "https://netflix.com",
    "amazon": "https://amazon.com",
    "spotify": "https://spotify.com",
}

BASE_APP_MAP = {
    "calculator": {"linux": "gnome-calculator", "windows": "calc"},
    "terminal": {"linux": "gnome-terminal", "windows": "cmd"},
    "files": {"linux": "nautilus", "windows": "explorer"},
    "text editor": {"linux": "gedit", "windows": "notepad"},
    "browser": {"linux": "firefox", "windows": "firefox"},
    "firefox": {"linux": "firefox", "windows": "firefox"},
    "chrome": {"linux": "google-chrome", "windows": "chrome"},
    "settings": {"linux": "gnome-control-center", "windows": "control"},
    "notepad": {"linux": "gedit", "windows": "notepad"},
    "file manager": {"linux": "nautilus", "windows": "explorer"},
    "vlc": {"linux": "vlc", "windows": "vlc"},
    "gimp": {"linux": "gimp", "windows": "gimp"},
    "thunderbird": {"linux": "thunderbird", "windows": "thunderbird"},
    "spotify": {"linux": "spotify", "windows": "spotify"},
    "discord": {"linux": "discord", "windows": "discord"},
    "bluetooth": {"linux": "bluetoothctl", "windows": "fsquirt"},
}

KEY_COMBINATIONS = {
    "ctrl c": ["ctrl", "c"],
    "ctrl v": ["ctrl", "v"],
    "ctrl a": ["ctrl", "a"],
    "ctrl s": ["ctrl", "s"],
    "alt tab": ["alt", "tab"],
    "enter": ["enter"],
    "escape": ["esc"],
    "tab": ["tab"],
    "space": ["space"],
}
