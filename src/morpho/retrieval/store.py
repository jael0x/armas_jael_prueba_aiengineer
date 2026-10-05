"""Vector store: an exact in-memory search, enough for five documents.

`VectorStore` marks where Azure AI Search or Databricks AI Search would plug in.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np

from morpho.retrieval.embedder import Vectors


class VectorStore(Protocol):
    def search(self, query: Vectors, k: int) -> list[tuple[str, float]]:
        """The `k` closest ids with their cosine similarity, best first."""
        ...


class NumpyStore:
    def __init__(self, ids: Sequence[str], vectors: Vectors) -> None:
        if len(ids) != len(vectors):
            raise ValueError(f"{len(ids)} ids for {len(vectors)} vectors")
        self._ids = list(ids)
        self._matrix = _unit_rows(np.asarray(vectors, dtype=np.float32))

    def search(self, query: Vectors, k: int) -> list[tuple[str, float]]:
        scores = self._matrix @ _unit_rows(np.asarray(query, dtype=np.float32).reshape(1, -1))[0]
        order = np.argsort(-scores, kind="stable")[:k]
        return [(self._ids[i], float(scores[i])) for i in order]


def _unit_rows(matrix: Vectors) -> Vectors:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return (matrix / np.where(norms == 0, 1, norms)).astype(np.float32)
