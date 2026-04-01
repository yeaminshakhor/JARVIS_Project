"""Advanced long-term memory with key-value, vector, and short context tracking."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class _SimpleEmbedder:
    """Deterministic hash embedding fallback when sentence-transformers is unavailable."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def encode(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in str(text or "").lower().split():
                idx = abs(hash(token)) % self.dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class AdvancedMemorySystem:
    def __init__(self, memory_file: Optional[Path] = None):
        self.file = memory_file or Path("long_memory.json")
        self.file.parent.mkdir(parents=True, exist_ok=True)
        if not self.file.exists():
            self.file.write_text("{}", encoding="utf-8")

        self.data = self._load_json()
        self.context: List[str] = []

        self.model, self._embedding_size = self._build_embedder()
        self.index, self._use_faiss = self._build_index(self._embedding_size)
        self.texts: List[str] = []
        self._vectors: List[List[float]] = []

        # Rehydrate vector store from persisted key-value memory.
        for key, payload in self.data.items():
            value = ""
            if isinstance(payload, dict):
                value = str(payload.get("value", ""))
            elif payload is not None:
                value = str(payload)
            if value.strip():
                self._store_vector(f"{key}: {value}")

    def remember(self, key: str, value: str) -> str:
        clean_key = str(key or "").strip().lower()
        clean_value = str(value or "").strip()
        if not clean_key:
            return "Memory key is empty"
        if not clean_value:
            return "Memory value is empty"

        self.data[clean_key] = {
            "value": clean_value,
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        self._save()
        self._store_vector(f"{clean_key}: {clean_value}")
        return f"Remembered {clean_key}"

    def recall(self, key: str) -> str:
        clean_key = str(key or "").strip().lower()
        if not clean_key:
            return "Usage: recall <key>"

        item = self.data.get(clean_key)
        if isinstance(item, dict) and "value" in item:
            return str(item["value"])
        if isinstance(item, str):
            return item

        return self.semantic_search(clean_key)

    def semantic_search(self, query: str) -> str:
        if not self.texts:
            return "No memory found"

        q_vec = self.model.encode([str(query or "")])[0]

        if self._use_faiss and self.index is not None:
            try:
                import numpy as np

                q_np = np.array([q_vec], dtype="float32")
                _distances, indices = self.index.search(q_np, 1)
                best = int(indices[0][0])
                if 0 <= best < len(self.texts):
                    return self.texts[best]
            except Exception:
                pass

        best_idx = self._nearest_vector_index(q_vec)
        if best_idx is None:
            return "No memory found"
        return self.texts[best_idx]

    def add_context(self, text: str):
        clean = str(text or "").strip()
        if not clean:
            return
        self.context.append(clean)
        if len(self.context) > 10:
            self.context.pop(0)

    def get_context(self) -> List[str]:
        return list(self.context)

    def _store_vector(self, text: str):
        vec = self.model.encode([text])[0]
        self.texts.append(text)
        self._vectors.append(vec)

        if self._use_faiss and self.index is not None:
            try:
                import numpy as np

                arr = np.array([vec], dtype="float32")
                self.index.add(arr)
            except Exception:
                self._use_faiss = False

    def _save(self):
        self.file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def _load_json(self) -> Dict[str, Any]:
        try:
            payload = json.loads(self.file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _build_embedder(self) -> Tuple[Any, int]:
        model_name = os.getenv("JARVIS_MEMORY_EMBED_MODEL", "all-MiniLM-L6-v2")
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

            model = SentenceTransformer(model_name)
            sample = model.encode(["jarvis"])
            dim = int(len(sample[0]))
            return model, dim
        except Exception:
            fallback = _SimpleEmbedder(dim=384)
            return fallback, 384

    def _build_index(self, dim: int):
        try:
            import faiss  # type: ignore[import-not-found]

            return faiss.IndexFlatL2(dim), True
        except Exception:
            return None, False

    def _nearest_vector_index(self, query_vec: List[float]) -> Optional[int]:
        if not self._vectors:
            return None

        best_idx = None
        best_dist = float("inf")
        for idx, vec in enumerate(self._vectors):
            dist = 0.0
            for a, b in zip(vec, query_vec):
                d = a - b
                dist += d * d
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx
