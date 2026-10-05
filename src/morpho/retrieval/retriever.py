"""Retrieval over the five policy documents, with a calibrated relevance threshold.

No chunking: each document is 20 to 55 words on a single topic, so one document is one
vector. A document is used when its cosine score reaches τ and is within δ of the best one;
when nothing reaches τ the list is empty and Morpho abstains without calling the model.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from morpho.knowledge.documents import DOCUMENTS, PolicyDocument
from morpho.retrieval.embedder import Embedder
from morpho.retrieval.store import NumpyStore, VectorStore

THRESHOLDS_PATH = Path(__file__).with_name("thresholds.json")
CALIBRATE_COMMAND = "uv run python -m morpho.evals.calibrate"
TOP_K = 2


@dataclass(frozen=True)
class Hit:
    doc_id: str
    score: float


@dataclass(frozen=True)
class Thresholds:
    tau: float
    """Minimum cosine score for a document to be used."""
    delta: float = 0.1
    """A second document is kept only if it is within this distance of the best score."""


class NotCalibratedError(LookupError):
    pass


def load_thresholds(model: str, path: Path = THRESHOLDS_PATH) -> Thresholds:
    # Scores are not comparable across embedding models, so τ is stored per model.
    entries = json.loads(path.read_text()) if path.exists() else {}
    entry = entries.get(model)
    if entry is None:
        raise NotCalibratedError(f"No retrieval threshold for {model!r}. Run: {CALIBRATE_COMMAND}")
    return Thresholds(tau=entry["tau"], delta=entry["delta"])


def document_text(doc: PolicyDocument) -> str:
    """The text that gets embedded for a document: its title, then its body."""
    return f"{doc.title}. {doc.text}"


class Retriever:
    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        thresholds: Thresholds,
        *,
        size: int,
        top_k: int = TOP_K,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._size = size
        self.thresholds = thresholds
        self.top_k = top_k

    @classmethod
    def over_documents(
        cls,
        embedder: Embedder,
        thresholds: Thresholds,
        documents: Sequence[PolicyDocument] = DOCUMENTS,
    ) -> Retriever:
        vectors = embedder.embed([document_text(doc) for doc in documents])
        store = NumpyStore([doc.doc_id for doc in documents], vectors)
        return cls(embedder, store, thresholds, size=len(documents))

    def rank(self, question: str) -> list[Hit]:
        """Every document with its score, best first. Used for traces and calibration."""
        query = self._embedder.embed([question])[0]
        return [Hit(doc_id, score) for doc_id, score in self._store.search(query, self._size)]

    def retrieve(self, question: str) -> list[Hit]:
        ranked = self.rank(question)
        if not ranked or ranked[0].score < self.thresholds.tau:
            return []
        best = ranked[0].score
        return [
            hit
            for hit in ranked[: self.top_k]
            if hit.score >= self.thresholds.tau and best - hit.score <= self.thresholds.delta
        ]
