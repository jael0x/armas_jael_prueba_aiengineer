"""Embeddings: an OpenAI embedder and a cache keyed by (model, sha256(text)).

The cache is committed to the repo, so the retrieval tests run with the real vectors of the
chosen model and without an API key. At runtime, questions that are not in the cache go to
the API and stay cached in memory for the rest of the process.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

DEFAULT_CACHE_PATH = Path(__file__).with_name("embeddings_cache.json")
RECORD_COMMAND = "uv run python -m morpho.evals.record_embeddings"

Vectors = NDArray[np.float32]


class Embedder(Protocol):
    model: str

    def embed(self, texts: Sequence[str]) -> Vectors:
        """One row per text, in the same order."""
        ...


class MissingEmbeddingError(LookupError):
    pass


class OpenAIEmbedder:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self.model = model
        self.tokens_used = 0

    def embed(self, texts: Sequence[str]) -> Vectors:
        response = self._client.embeddings.create(model=self.model, input=list(texts))
        self.tokens_used += response.usage.total_tokens
        rows = sorted(response.data, key=lambda item: item.index)
        return np.asarray([row.embedding for row in rows], dtype=np.float32)


class EmbeddingCache:
    """Vectors stored as base64 float32 per model, in a JSON file small enough to commit."""

    def __init__(self, path: Path = DEFAULT_CACHE_PATH) -> None:
        self.path = path
        self._models: dict[str, dict[str, str]] = {}
        if path.exists():
            self._models = json.loads(path.read_text())["models"]

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def get(self, model: str, text: str) -> Vectors | None:
        encoded = self._models.get(model, {}).get(self.key(text))
        if encoded is None:
            return None
        return np.frombuffer(base64.b64decode(encoded), dtype="<f4").astype(np.float32)

    def put(self, model: str, text: str, vector: Vectors) -> None:
        raw = np.asarray(vector, dtype="<f4").tobytes()
        self._models.setdefault(model, {})[self.key(text)] = base64.b64encode(raw).decode()

    def save(self) -> None:
        models = {
            model: dict(sorted(vectors.items())) for model, vectors in sorted(self._models.items())
        }
        self.path.write_text(json.dumps({"version": 1, "models": models}, indent=1) + "\n")


class CachedEmbedder:
    """Serves vectors from the cache and sends only the misses to `fallback`.

    Without a fallback (tests, offline runs) a miss raises `MissingEmbeddingError`.
    """

    def __init__(self, cache: EmbeddingCache, model: str, fallback: Embedder | None = None) -> None:
        if fallback is not None and fallback.model != model:
            raise ValueError(f"fallback embeds with {fallback.model!r}, cache model is {model!r}")
        self._cache = cache
        self._fallback = fallback
        self.model = model

    def embed(self, texts: Sequence[str]) -> Vectors:
        missing = [t for t in dict.fromkeys(texts) if self._cache.get(self.model, t) is None]
        if missing:
            if self._fallback is None:
                raise MissingEmbeddingError(
                    f"{len(missing)} text(s) have no cached {self.model} vector, "
                    f"for example {missing[0][:60]!r}. Record them with: {RECORD_COMMAND}"
                )
            for text, vector in zip(missing, self._fallback.embed(missing), strict=True):
                self._cache.put(self.model, text, vector)
        vectors = [self._cache.get(self.model, t) for t in texts]
        return np.asarray(vectors, dtype=np.float32)
