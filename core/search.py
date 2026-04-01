#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import datetime
import json
import os
from collections import Counter, deque
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

try:
    from googlesearch import search as google_search
except Exception:
    google_search = None

try:
    from groq import Groq
except Exception:
    Groq = None

from .config import ConfigManager
from .utils import env_get, load_env_map, EnhancedCache, CommandHistory
from .chatbot import load_chat as load_shared_chat, save_chat as save_shared_chat
from .paths import DATA_DIR


ENV = load_env_map(".env")
VERBOSE = ConfigManager.get_bool("JARVIS_VERBOSE_STARTUP", default=False)
USERNAME = env_get("Username", "USERNAME", default="User", env_map=ENV)
ASSISTANT_NAME = env_get("Assistantname", "AssistantName", "ASSISTANT_NAME", default="Jarvis", env_map=ENV)
GROQ_API_KEY = env_get("GROQ_API_KEY", "GroqAPIKey", "GROQAPIKEY", env_map=ENV)
TAVILY_API_KEY = env_get("TAVILY_API_KEY", "Tavily_API_KEY", default="", env_map=ENV)
SERPER_API_KEY = env_get("SERPER_API_KEY", default="", env_map=ENV)
NEWS_API_KEY = env_get("NEWS_API_KEY", default="", env_map=ENV)
BRAVE_API_KEY = env_get("BRAVE_API_KEY", default="", env_map=ENV)

_cache = None
_command_history = None


def _get_cache() -> EnhancedCache:
    global _cache
    if _cache is None:
        _cache = EnhancedCache(DATA_DIR / "search_cache", ttl_seconds=1800)
    return _cache


def _get_command_history() -> CommandHistory:
    global _command_history
    if _command_history is None:
        _command_history = CommandHistory()
    return _command_history

SEARCH_METRICS_FILE = DATA_DIR / "search_metrics.json"
SEARCH_METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)


class SearchAnalytics:
    def __init__(self):
        self.popular = Counter()
        self.trending = deque(maxlen=100)

    def log_search(self, query: str, results_count: int):
        clean = (query or "").strip().lower()
        if not clean:
            return
        self.popular[clean] += 1
        self.trending.append(
            {
                "query": clean,
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "count": int(results_count),
            }
        )


search_analytics = SearchAnalytics()


@dataclass
class SearchItem:
    title: str
    url: str
    snippet: str
    source: str


class SearchProvider:
    name = "provider"

    def supports(self, search_type: str) -> bool:
        return search_type in {"web", "news", "social"}

    async def async_search(self, query: str, search_type: str = "web", limit: int = 6) -> List[SearchItem]:
        raise NotImplementedError


class TavilySearch(SearchProvider):
    name = "tavily"

    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()

    def supports(self, search_type: str) -> bool:
        return search_type in {"web", "news"}

    async def async_search(self, query: str, search_type: str = "web", limit: int = 6) -> List[SearchItem]:
        if not self.api_key:
            return []
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max(1, limit),
            "topic": "news" if search_type == "news" else "general",
        }

        def _call():
            response = requests.post("https://api.tavily.com/search", json=payload, timeout=20)
            response.raise_for_status()
            return response.json()

        try:
            data = await asyncio.to_thread(_call)
            items = []
            for row in data.get("results", [])[:limit]:
                url = str(row.get("url") or "").strip()
                if not url:
                    continue
                items.append(
                    SearchItem(
                        title=str(row.get("title") or query),
                        url=url,
                        snippet=str(row.get("content") or "").strip(),
                        source=self.name,
                    )
                )
            return items
        except Exception:
            return []


class SerperSearch(SearchProvider):
    name = "serper"

    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()

    def supports(self, search_type: str) -> bool:
        return search_type in {"web", "news"}

    async def async_search(self, query: str, search_type: str = "web", limit: int = 6) -> List[SearchItem]:
        if not self.api_key:
            return []
        endpoint = "https://google.serper.dev/news" if search_type == "news" else "https://google.serper.dev/search"

        def _call():
            response = requests.post(
                endpoint,
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json={"q": query, "num": max(1, limit)},
                timeout=20,
            )
            response.raise_for_status()
            return response.json()

        try:
            data = await asyncio.to_thread(_call)
            rows = data.get("organic") or data.get("news") or []
            items = []
            for row in rows[:limit]:
                link = str(row.get("link") or "").strip()
                if not link:
                    continue
                items.append(
                    SearchItem(
                        title=str(row.get("title") or query),
                        url=link,
                        snippet=str(row.get("snippet") or "").strip(),
                        source=self.name,
                    )
                )
            return items
        except Exception:
            return []


class NewsAPISearch(SearchProvider):
    name = "newsapi"

    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()

    def supports(self, search_type: str) -> bool:
        return search_type == "news"

    async def async_search(self, query: str, search_type: str = "news", limit: int = 6) -> List[SearchItem]:
        if not self.api_key:
            return []

        def _call():
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params={"q": query, "pageSize": max(1, limit), "sortBy": "publishedAt", "apiKey": self.api_key},
                timeout=20,
            )
            response.raise_for_status()
            return response.json()

        try:
            data = await asyncio.to_thread(_call)
            items = []
            for row in data.get("articles", [])[:limit]:
                link = str(row.get("url") or "").strip()
                if not link:
                    continue
                items.append(
                    SearchItem(
                        title=str(row.get("title") or query),
                        url=link,
                        snippet=str(row.get("description") or "").strip(),
                        source=self.name,
                    )
                )
            return items
        except Exception:
            return []


class TwitterSearch(SearchProvider):
    name = "twitter"

    def supports(self, search_type: str) -> bool:
        return search_type == "social"

    async def async_search(self, query: str, search_type: str = "social", limit: int = 6) -> List[SearchItem]:
        url = f"https://x.com/search?q={requests.utils.quote(query)}&src=typed_query"
        return [SearchItem(title=f"X search: {query}", url=url, snippet="Open X search results", source=self.name)]


class BraveSearch(SearchProvider):
    name = "brave"

    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()

    def supports(self, search_type: str) -> bool:
        return search_type in {"web", "news"}

    async def async_search(self, query: str, search_type: str = "web", limit: int = 6) -> List[SearchItem]:
        if not self.api_key:
            return []

        def _call():
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                params={"q": query, "count": max(1, limit)},
                timeout=20,
            )
            response.raise_for_status()
            return response.json()

        try:
            data = await asyncio.to_thread(_call)
            rows = ((data.get("web") or {}).get("results") or [])
            items = []
            for row in rows[:limit]:
                link = str(row.get("url") or "").strip()
                if not link:
                    continue
                items.append(
                    SearchItem(
                        title=str(row.get("title") or query),
                        url=link,
                        snippet=str(row.get("description") or "").strip(),
                        source=self.name,
                    )
                )
            return items
        except Exception:
            return []


class FallbackGoogleScraper(SearchProvider):
    name = "google-scrape"

    def supports(self, search_type: str) -> bool:
        return search_type in {"web", "news"}

    async def async_search(self, query: str, search_type: str = "web", limit: int = 6) -> List[SearchItem]:
        if google_search is None:
            return []

        def _call():
            urls = []
            for url in google_search(query, num_results=max(1, limit)):
                urls.append(url)
            return urls

        try:
            urls = await asyncio.to_thread(_call)
            return [
                SearchItem(title=f"Result {idx+1}", url=url, snippet="", source=self.name)
                for idx, url in enumerate(urls[:limit])
            ]
        except Exception:
            return []


class UnifiedSearchEngine:
    def __init__(self):
        self.engines: List[SearchProvider] = [
            TavilySearch(TAVILY_API_KEY),
            SerperSearch(SERPER_API_KEY),
            NewsAPISearch(NEWS_API_KEY),
            TwitterSearch(),
            BraveSearch(BRAVE_API_KEY),
            FallbackGoogleScraper(),
        ]

    async def search(self, query: str, search_type: str = "web", limit: int = 8) -> List[SearchItem]:
        tasks = []
        for engine in self.engines:
            if engine.supports(search_type):
                tasks.append(engine.async_search(query, search_type=search_type, limit=limit))

        if not tasks:
            return []

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        merged: List[SearchItem] = []
        for result in responses:
            if isinstance(result, Exception):
                continue
            merged.extend(result)
        return self.merge_results(merged, limit=limit)

    def merge_results(self, items: List[SearchItem], limit: int = 8) -> List[SearchItem]:
        seen = set()
        out = []
        for item in items:
            key = (item.url or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= limit:
                break
        return out


class EnhancedSearchEngine(UnifiedSearchEngine):
    pass


def _format_results(query: str, results: List[SearchItem], search_type: str = "web") -> str:
    if not results:
        return " No search results found."
    lines = [
        f"** Search Results for: '{query}'**",
        f"**Type:** {search_type} | **Sources Found:** {len(results)}",
        "",
    ]
    for idx, item in enumerate(results, 1):
        suffix = f" ({item.source})" if item.source else ""
        snippet = f"\n   {item.snippet}" if item.snippet else ""
        lines.append(f"{idx}. {item.title}{suffix}\n   {item.url}{snippet}")
    return "\n".join(lines)


def _track_search_metrics(query: str, response_time: float, results_count: int):
    try:
        if SEARCH_METRICS_FILE.exists():
            payload = json.loads(SEARCH_METRICS_FILE.read_text(encoding="utf-8") or "[]")
        else:
            payload = []
        payload.append(
            {
                "query": query,
                "response_time": round(float(response_time), 3),
                "results_count": int(results_count),
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        )
        payload = payload[-200:]
        SEARCH_METRICS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    search_analytics.log_search(query, results_count)


def quick_multi_search(query: str) -> List[Dict[str, str]]:
    engine = UnifiedSearchEngine()
    results = asyncio.run(engine.search(query, search_type="web", limit=8))
    return [{"title": item.title, "url": item.url, "snippet": item.snippet, "source": item.source} for item in results]


def EnhancedGoogleSearch(query: str):
    clean = (query or "").strip()
    if not clean:
        return " Empty search query"

    cached = _get_cache().get_cached_result(f"search:{clean}")
    if cached:
        return cached

    start = datetime.datetime.now().timestamp()
    engine = UnifiedSearchEngine()
    results = asyncio.run(engine.search(clean, search_type="web", limit=8))
    answer = _format_results(clean, results, search_type="web")

    elapsed = datetime.datetime.now().timestamp() - start
    _track_search_metrics(clean, elapsed, len(results))
    _get_cache().set_cached_result(f"search:{clean}", answer)
    return answer


def search_with_progress(query: str, search_type: str = "web") -> Dict[str, object]:
    clean = (query or "").strip()
    if not clean:
        return {"ok": False, "message": "Empty query", "progress": 0, "results": []}

    engine = UnifiedSearchEngine()
    results = asyncio.run(engine.search(clean, search_type=search_type, limit=8))
    payload_results = [
        {"title": item.title, "url": item.url, "snippet": item.snippet, "source": item.source}
        for item in results
    ]
    return {
        "ok": True,
        "message": "Search completed",
        "progress": 100,
        "search_type": search_type,
        "results": payload_results,
    }


def EnhancedProcessQuery(prompt: str):
    query = (prompt or "").strip()
    if not query:
        return "Please provide a query."

    if any(word in query.lower() for word in ["introduce yourself", "who are you", "what are you"]):
        return (
            f"I am {ASSISTANT_NAME}, your realtime assistant. "
            "I can combine multiple search providers and summarize current web results."
        )

    search_block = EnhancedGoogleSearch(query)
    messages = load_shared_chat()
    messages.append({"role": "user", "content": query})

    system_prompt = (
        f"You are {ASSISTANT_NAME}. Use the search results to answer clearly and concisely.\n"
        f"Context user: {USERNAME}\n\n{search_block}"
    )

    if Groq is None or not GROQ_API_KEY:
        response = f"Here are the latest web results for '{query}':\n\n{search_block}"
        messages.append({"role": "assistant", "content": response})
        save_shared_chat(messages)
        _get_command_history().add_command(query, "search-only response", success=True)
        return response

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_prompt}] + messages[-8:],
            max_tokens=700,
            temperature=0.4,
        )
        answer = str(completion.choices[0].message.content or "").strip()
        if not answer:
            answer = f"I found these search results:\n\n{search_block}"
        messages.append({"role": "assistant", "content": answer})
        save_shared_chat(messages)
        _get_command_history().add_command(query, answer[:120], success=True)
        return answer
    except Exception:
        fallback = f"I found these search results:\n\n{search_block}"
        messages.append({"role": "assistant", "content": fallback})
        save_shared_chat(messages)
        _get_command_history().add_command(query, "fallback response", success=True)
        return fallback


if __name__ == "__main__":
    while True:
        q = input("\n Search query> ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        print(EnhancedProcessQuery(q))
