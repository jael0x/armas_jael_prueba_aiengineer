"""Embeddings: a local EmbeddingGemma embedder and a cache keyed by (model, kind, text).

The cache is committed to the repo, so the retrieval tests run with the real vectors of the
chosen model without downloading it. At runtime, questions that are not in the cache go to the
local model and stay cached in memory for the rest of the process.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
from numpy.typing import NDArray

DEFAULT_CACHE_PATH = Path(__file__).with_name("embeddings_cache.json")
RECORD_COMMAND = "uv run python -m morpho.evals.record_embeddings"

Vectors = NDArray[np.float32]
Kind = Literal["query", "document"]
"""Questions and documents are embedded with different prompts, so they get different vectors."""

# Prompts from the EmbeddingGemma model card. fastembed does not add them on its own.
PROMPTS: dict[str, dict[Kind, str]] = {
    "google/embeddinggemma-300m": {
        "query": "task: search result | query: {}",
        "document": "title: none | text: {}",
    },
}


class Embedder(Protocol):
    model: str

    def embed(self, texts: Sequence[str], kind: Kind) -> Vectors:
        """One row per text, in the same order."""
        ...


class MissingEmbeddingError(LookupError):
    pass


class FastEmbedEmbedder:
    """Runs the model on this machine with ONNX Runtime. No API key, no per-token cost.

    The first use downloads the model into `cache_dir` (about 1.2 GB for EmbeddingGemma).
    """

    def __init__(
        self,
        model: str,
        cache_dir: Path | None = None,
        *,
        load: Callable[[str, str | None], Any] | None = None,
    ) -> None:
        self.model = model
        self._cache_dir = str(cache_dir) if cache_dir else None
        self._load = load or _load_fastembed
        self._backend: Any = None

    def embed(self, texts: Sequence[str], kind: Kind) -> Vectors:
        if self._backend is None:
            self._backend = self._load(self.model, self._cache_dir)
        template = PROMPTS.get(self.model, {}).get(kind, "{}")
        rows = self._backend.embed([template.format(text) for text in texts])
        return np.asarray(list(rows), dtype=np.float32)


def _load_fastembed(model: str, cache_dir: str | None) -> Any:
    from fastembed import TextEmbedding  # slow import; only paid when a vector is missing

    return TextEmbedding(model_name=model, cache_dir=cache_dir)


class EmbeddingCache:
    """Vectors stored as base64 float32 per model, in a JSON file small enough to commit."""

    def __init__(self, path: Path = DEFAULT_CACHE_PATH) -> None:
        self.path = path
        self._models: dict[str, dict[str, str]] = {}
        if path.exists():
            self._models = json.loads(path.read_text())["models"]

    @staticmethod
    def key(text: str, kind: Kind) -> str:
        return hashlib.sha256(f"{kind}:{text}".encode()).hexdigest()

    def get(self, model: str, text: str, kind: Kind) -> Vectors | None:
        encoded = self._models.get(model, {}).get(self.key(text, kind))
        if encoded is None:
            return None
        return np.frombuffer(base64.b64decode(encoded), dtype="<f4").astype(np.float32)

    def put(self, model: str, text: str, kind: Kind, vector: Vectors) -> None:
        raw = np.asarray(vector, dtype="<f4").tobytes()
        self._models.setdefault(model, {})[self.key(text, kind)] = base64.b64encode(raw).decode()

    def save(self) -> None:
        models = {
            model: dict(sorted(vectors.items())) for model, vectors in sorted(self._models.items())
        }
        self.path.write_text(json.dumps({"version": 2, "models": models}, indent=1) + "\n")


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

    def embed(self, texts: Sequence[str], kind: Kind) -> Vectors:
        missing = [t for t in dict.fromkeys(texts) if self._cache.get(self.model, t, kind) is None]
        if missing:
            if self._fallback is None:
                raise MissingEmbeddingError(
                    f"{len(missing)} {kind} text(s) have no cached {self.model} vector, "
                    f"for example {missing[0][:60]!r}. Record them with: {RECORD_COMMAND}"
                )
            for text, vector in zip(missing, self._fallback.embed(missing, kind), strict=True):
                self._cache.put(self.model, text, kind, vector)
        vectors = [self._cache.get(self.model, t, kind) for t in texts]
        return np.asarray(vectors, dtype=np.float32)
