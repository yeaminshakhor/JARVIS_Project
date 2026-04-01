#!/usr/bin/env python3
from __future__ import annotations

import re
import os
from dataclasses import dataclass
from typing import List, Optional, Dict

try:
    import cohere
except Exception:
    cohere = None

from .config import ConfigManager
from .utils import env_get, load_env_map, EnhancedCache
from .paths import DATA_DIR


ENV = load_env_map(".env")
VERBOSE = ConfigManager.get_bool("JARVIS_VERBOSE_STARTUP", default=False)


def _cohere_api_key() -> str:
    return env_get("COHERE_API_KEY", "CohereAPIKeys", "COHEREAPIKEY", env_map=load_env_map(".env"))


@dataclass
class ClassificationResult:
    intent: str
    query: str
    confidence: float
    source: str

    def as_route(self) -> str:
        return f"{self.intent} {self.query}".strip()


class ClassificationCache:
    def __init__(self):
        self.cache = EnhancedCache(DATA_DIR / "model_cache", ttl_seconds=3600 * 24)

    def get(self, text: str) -> Optional[ClassificationResult]:
        payload = self.cache.get_cached_result((text or "").strip().lower())
        if not isinstance(payload, dict):
            return None
        try:
            return ClassificationResult(
                intent=str(payload.get("intent") or "general"),
                query=str(payload.get("query") or text or "").strip(),
                confidence=float(payload.get("confidence") or 0.0),
                source=str(payload.get("source") or "cache"),
            )
        except Exception:
            return None

    def set(self, text: str, result: ClassificationResult) -> None:
        self.cache.set_cached_result(
            (text or "").strip().lower(),
            {
                "intent": result.intent,
                "query": result.query,
                "confidence": result.confidence,
                "source": result.source,
            },
        )


class QuickLocalClassifier:
    def __init__(self):
        self.exit_words = {"exit", "quit", "bye", "goodbye"}

    def _clean(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip())

    def predict(self, text: str) -> ClassificationResult:
        clean = self._clean(text)
        low = clean.lower()

        if low in self.exit_words:
            return ClassificationResult("exit", "", 0.99, "local-rules")

        patterns = [
            (r"^(open|launch|start)\s+(.+)$", "open", 0.95),
            (r"^(close|stop)\s+(.+)$", "close", 0.94),
            (r"^play\s+(.+)$", "play", 0.93),
            (r"^(google\s+search|search\s+for|search|look\s+up|find)\s+(.+)$", "google search", 0.92),
            (r"^(youtube\s+search)\s+(.+)$", "youtube search", 0.92),
            (r"^(generate\s+image|create\s+image|create\s+picture|make\s+image)\s+(.+)$", "generate image", 0.93),
            (r"^(system)\s+(.+)$", "system", 0.9),
            (r"^(content|write)\s+(.+)$", "content", 0.88),
            (r"^(realtime)\s+(.+)$", "realtime", 0.97),
        ]

        for pattern, intent, confidence in patterns:
            match = re.match(pattern, low)
            if not match:
                continue
            groups = [g for g in match.groups() if g]
            payload = groups[-1].strip() if groups else clean
            return ClassificationResult(intent, payload, confidence, "local-rules")

        realtime_hints = [
            "today", "latest", "recent", "news", "headline", "current", "price", "stock", "weather",
            "who is", "what is happening", "trending",
        ]
        if any(hint in low for hint in realtime_hints):
            return ClassificationResult("realtime", clean, 0.86, "local-rules")

        return ClassificationResult("general", clean, 0.7, "local-rules")


class HybridClassifier:
    def __init__(self):
        self.local_model = QuickLocalClassifier()
        self.cache = ClassificationCache()
        self.local_conf_threshold = 0.85
        self.cohere_client = None
        key = _cohere_api_key()
        if cohere is not None and key:
            try:
                self.cohere_client = cohere.Client(api_key=key)
            except Exception:
                self.cohere_client = None

    def _cohere_classify(self, text: str) -> Optional[ClassificationResult]:
        if self.cohere_client is None:
            return None

        prompt = (
            "Classify the user query into exactly one intent from: "
            "general, realtime, open, close, play, generate image, system, content, google search, youtube search, reminder, exit. "
            "Return only JSON with keys intent and query.\n"
            f"User query: {text}"
        )
        try:
            for model in ["command-a", "command", "command-nightly"]:
                try:
                    response = self.cohere_client.chat(model=model, message=prompt, temperature=0.1)
                    raw = str(getattr(response, "text", "") or "").strip()
                    intent_match = re.search(r'"intent"\s*:\s*"([^"]+)"', raw)
                    query_match = re.search(r'"query"\s*:\s*"([^"]*)"', raw)
                    if not intent_match:
                        # loose fallback
                        intent_guess = raw.lower().split()[0] if raw else "general"
                        intent = self._normalize_intent(intent_guess)
                        return ClassificationResult(intent, text, 0.78, "cohere")
                    intent = self._normalize_intent(intent_match.group(1))
                    query = (query_match.group(1).strip() if query_match else text)
                    return ClassificationResult(intent, query or text, 0.82, "cohere")
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _normalize_intent(self, intent: str) -> str:
        low = (intent or "").strip().lower()
        allowed = {
            "general", "realtime", "open", "close", "play", "generate image",
            "system", "content", "google search", "youtube search", "reminder", "exit",
        }
        if low in allowed:
            return low
        if low.startswith("generate"):
            return "generate image"
        if low.startswith("google"):
            return "google search"
        if low.startswith("youtube"):
            return "youtube search"
        return "general"

    def classify(self, text: str) -> ClassificationResult:
        clean = (text or "").strip()
        if not clean:
            return ClassificationResult("general", "", 1.0, "local-rules")

        cached = self.cache.get(clean)
        if cached:
            return cached

        local_result = self.local_model.predict(clean)
        if local_result.confidence >= self.local_conf_threshold:
            self.cache.set(clean, local_result)
            return local_result

        remote = self._cohere_classify(clean)
        if remote:
            self.cache.set(clean, remote)
            return remote

        self.cache.set(clean, local_result)
        return local_result


_classifier = None


def _get_classifier() -> HybridClassifier:
    global _classifier
    if _classifier is None:
        _classifier = HybridClassifier()
    return _classifier


def classify_with_confidence(prompt: str) -> Dict[str, object]:
    result = _get_classifier().classify(prompt)
    return {
        "intent": result.intent,
        "query": result.query,
        "confidence": round(float(result.confidence), 3),
        "source": result.source,
        "route": result.as_route(),
    }


def EnhancedFirstLayerDMM(prompt: str = "test") -> List[str]:
    result = _get_classifier().classify(prompt)
    if result.intent == "exit":
        return ["exit"]
    return [result.as_route()]


if __name__ == "__main__":
    while True:
        text = input("\n >>> ").strip()
        if text.lower() in {"exit", "quit", "bye"}:
            break
        print(classify_with_confidence(text))
