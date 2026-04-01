import hashlib
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional

QdrantClient = None
models = None
try:
    from qdrant_client import QdrantClient  # type: ignore
    from qdrant_client.http import models  # type: ignore
except Exception:
    pass

from .utils import env_get
from .config import ConfigManager


def _normalize_tokens(text: str) -> List[str]:
    return [token for token in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if token]


def _hashed_embedding(text: str, dim: int = 128) -> List[float]:
    # Deterministic fallback only: this is not semantic embedding quality.
    vector = [0.0] * dim
    tokens = _normalize_tokens(text)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dim
        sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
        weight = 1.0 + (int(digest[10:12], 16) / 255.0)
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class QdrantMemoryBridge:
    def __init__(self, client: Any, collection_name: str = "jarvis_memory", vector_size: int = 128, max_documents: int = 1000):
        self.client = client
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.max_documents = max(100, int(max_documents))
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            collections = self.client.get_collections().collections
            names = {item.name for item in collections}
            if self.collection_name in names:
                return
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=self.vector_size, distance=models.Distance.COSINE),
            )
        except Exception as exc:
            logging.warning("Qdrant collection setup failed: %s", exc)

    def _point_id(self, username: str, memory_type: str, value: str) -> int:
        digest = hashlib.sha1(f"{username}|{memory_type}|{value}".encode("utf-8")).hexdigest()[:15]
        return int(digest, 16)

    def remember(self, username: str, memory_type: str, value: str) -> bool:
        if not value:
            return False
        try:
            embedding = _hashed_embedding(f"{memory_type} {value}", dim=self.vector_size)
            payload = {
                "username": username,
                "memory_type": memory_type,
                "memory_value": value,
                "created_at": int(time.time()),
            }
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=self._point_id(username, memory_type, value),
                        vector=embedding,
                        payload=payload,
                    )
                ],
                wait=False,
            )
            self.prune(username=username, memory_type=memory_type)
            return True
        except Exception as exc:
            logging.warning("Qdrant remember failed: %s", exc)
            return False

    def prune(self, username: Optional[str] = None, memory_type: Optional[str] = None):
        try:
            conditions = []
            if username:
                conditions.append(models.FieldCondition(key="username", match=models.MatchValue(value=username)))
            if memory_type:
                conditions.append(models.FieldCondition(key="memory_type", match=models.MatchValue(value=memory_type)))

            query_filter = models.Filter(must=conditions) if conditions else None
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=max(self.max_documents * 3, 300),
                with_payload=True,
                with_vectors=False,
                scroll_filter=query_filter,
            )

            if len(points) <= self.max_documents:
                return 0

            ordered = sorted(
                points,
                key=lambda p: int((p.payload or {}).get("created_at") or 0),
            )
            removable = ordered[: len(points) - self.max_documents]
            ids = [item.id for item in removable if getattr(item, "id", None) is not None]
            if not ids:
                return 0

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=ids),
                wait=False,
            )
            return len(ids)
        except Exception as exc:
            logging.warning("Qdrant prune failed: %s", exc)
            return 0

    def recall(self, username: str, memory_type: str, query_text: str = "") -> Optional[str]:
        try:
            allow_hash_semantic = ConfigManager.get_bool("JARVIS_VECTOR_ALLOW_HASH_SEMANTIC", default=False)
            if not allow_hash_semantic:
                points, _ = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=min(self.max_documents, 200),
                    with_payload=True,
                    with_vectors=False,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(key="username", match=models.MatchValue(value=username)),
                            models.FieldCondition(key="memory_type", match=models.MatchValue(value=memory_type)),
                        ]
                    ),
                )
                if not points:
                    return None
                latest = max(points, key=lambda p: int((p.payload or {}).get("created_at") or 0))
                payload = latest.payload or {}
                return payload.get("memory_value")

            query = _hashed_embedding(query_text or memory_type, dim=self.vector_size)
            hits = self.client.search(
                collection_name=self.collection_name,
                query_vector=query,
                limit=1,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(key="username", match=models.MatchValue(value=username)),
                        models.FieldCondition(key="memory_type", match=models.MatchValue(value=memory_type)),
                    ]
                ),
            )
            if not hits:
                return None
            payload = hits[0].payload or {}
            return payload.get("memory_value")
        except Exception as exc:
            logging.warning("Qdrant recall failed: %s", exc)
            return None


def _resolve_qdrant_config(env_vars: Dict[str, str]):
    qdrant_url = env_get("QDRANT_URL", "Quadrant_URL", default="", env_map=env_vars)
    qdrant_key = env_get("QDRANT_API_KEY", "Quadrant_API_KEY", default="", env_map=env_vars)

    if qdrant_key and "|" in qdrant_key and not qdrant_url:
        first, second = qdrant_key.split("|", 1)
        if first.startswith("http://") or first.startswith("https://"):
            qdrant_url = first.strip()
        elif "." in first:
            qdrant_url = f"https://{first.strip()}"
        else:
            qdrant_url = f"https://{first.strip()}.cloud.qdrant.io"
        qdrant_key = second.strip()

    return qdrant_url.strip(), qdrant_key.strip()


def build_qdrant_memory_bridge(env_vars: Dict[str, str]):
    if not QdrantClient or not models:
        return None

    qdrant_url, qdrant_key = _resolve_qdrant_config(env_vars)
    if not qdrant_url or not qdrant_key:
        return None

    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=10.0)
        max_docs = ConfigManager.get_int("JARVIS_VECTOR_MAX_DOCUMENTS", default=1000)
        return QdrantMemoryBridge(client, max_documents=max_docs)
    except Exception as exc:
        logging.warning("Qdrant bridge setup failed: %s", exc)
        return None
