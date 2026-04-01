"""Browser-related automation handlers."""

from __future__ import annotations

import webbrowser
from urllib.parse import quote_plus

from ..constants import SUPPORTED_WEBSITES


class BrowserHandler:
    def open_browser(self, url: str = "") -> str:
        try:
            target = (url or "").strip() or "https://google.com"
            webbrowser.open(target)
            return f" Browser opened with URL: {target}" if url else " Browser opened to Google"
        except Exception as exc:
            return f" Browser error: {exc}"

    def open_website(self, website: str = "") -> str:
        try:
            key = (website or "").strip().lower()
            if key in SUPPORTED_WEBSITES:
                webbrowser.open(SUPPORTED_WEBSITES[key])
                return f" Opened {key.capitalize()}"
            if key.startswith(("http://", "https://")):
                webbrowser.open(key)
                return " Opened website"
            if key:
                webbrowser.open(f"https://{key}")
                return f" Opened: https://{key}"
            return " Please provide a website"
        except Exception as exc:
            return f" Website error: {exc}"

    def search_web(self, query: str = "") -> str:
        try:
            clean = (query or "").strip()
            if not clean:
                return " Please provide a search query"
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(clean)}")
            return f" Searching for: {clean}"
        except Exception as exc:
            return f" Search error: {exc}"
