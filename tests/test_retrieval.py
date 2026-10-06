"""Retrieval. The first block is specs/02-recuperacion-de-politicas.feature with the real
cached vectors of the configured embedding model; the rest checks the logic offline."""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from morpho.config import Settings
from morpho.evals.calibrate import calibrate, threshold_between
from morpho.evals.questions import LabeledQuestion, QuestionSet, load_questions
from morpho.guardrails.normalize import normalize
from morpho.guardrails.rules import evaluate
from morpho.knowledge.documents import get_document
from morpho.retrieval.embedder import (
    CachedEmbedder,
    EmbedderUnavailableError,
    EmbeddingCache,
    FastEmbedEmbedder,
    Kind,
    MissingEmbeddingError,
    Vectors,
)
from morpho.retrieval.retriever import (
    Hit,
    NotCalibratedError,
    Retriever,
    Thresholds,
    document_text,
    load_thresholds,
)
from morpho.retrieval.store import NumpyStore

# --- specs/02-recuperacion-de-politicas.feature (real cached vectors, the model never runs)


@pytest.fixture(scope="module")
def policy_retriever() -> Retriever:
    # The cache and thresholds are committed: a missing vector or τ is a failure, not a skip.
    model = Settings.from_env({}).embedding_model
    return Retriever.over_documents(CachedEmbedder(EmbeddingCache(), model), load_thresholds(model))


@pytest.mark.parametrize(
    ("question", "document"),
    [
        ("¿Cuánto dura la garantía de una lavadora?", "doc1"),
        ("¿Puedo devolver un producto que compré en liquidación?", "doc2"),
        ("¿Cuánto tarda un envío a otra ciudad?", "doc3"),
        ("¿Cuándo me devuelven mi dinero?", "doc4"),
        ("¿A dónde escribo para poner una queja?", "doc5"),
        ("How long is the warranty on a fridge?", "doc1"),
    ],
)
@pytest.mark.challenge
def test_clear_question_retrieves_its_document_first(
    policy_retriever: Retriever, question: str, document: str
) -> None:
    hits = policy_retriever.retrieve(question)
    assert hits, f"nothing passed τ={policy_retriever.thresholds.tau} for {question!r}"
    assert hits[0].doc_id == document


def test_question_spanning_two_policies_retrieves_both(policy_retriever: Retriever) -> None:
    hits = policy_retriever.retrieve("Si devuelvo la licuadora, ¿cuándo me reembolsan?")
    assert {hit.doc_id for hit in hits} == {"doc2", "doc4"}


def test_question_outside_the_policies_retrieves_nothing(policy_retriever: Retriever) -> None:
    assert policy_retriever.retrieve("Dame una receta de paella") == []


def test_calibrated_threshold_separates_the_labeled_questions(policy_retriever: Retriever) -> None:
    questions = load_questions()
    for item in questions.in_domain:
        if evaluate(normalize(item.question)).escalate:
            continue  # rules handle these before retrieval
        hits = policy_retriever.retrieve(item.question)
        assert hits and hits[0].doc_id in item.expected, item.question
    for question in questions.out_of_domain:
        assert policy_retriever.retrieve(question) == [], question


# --- retriever logic with fixed vectors


class FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]], model: str = "fake-model") -> None:
        self.vectors = vectors
        self.model = model
        self.calls: list[tuple[Kind, list[str]]] = []

    def embed(self, texts: Sequence[str], kind: Kind) -> Vectors:
        self.calls.append((kind, list(texts)))
        return np.asarray([self.vectors[t] for t in texts], dtype=np.float32)


def _retriever(query: list[float], tau: float, delta: float = 0.1) -> Retriever:
    docs = {"doc1": [1.0, 0.0, 0.0], "doc2": [0.0, 1.0, 0.0], "doc3": [0.0, 0.0, 1.0]}
    store = NumpyStore(list(docs), np.asarray(list(docs.values()), dtype=np.float32))
    return Retriever(FakeEmbedder({"q": query}), store, Thresholds(tau, delta), size=3)


def test_nothing_is_retrieved_when_the_best_score_is_below_tau() -> None:
    assert _retriever([0.5, 0.4, 0.3], tau=0.9).retrieve("q") == []


def test_second_document_within_delta_is_kept() -> None:
    hits = _retriever([0.8, 0.75, 0.1], tau=0.5).retrieve("q")
    assert [hit.doc_id for hit in hits] == ["doc1", "doc2"]


def test_second_document_beyond_delta_is_dropped() -> None:
    hits = _retriever([0.9, 0.5, 0.1], tau=0.3).retrieve("q")
    assert [hit.doc_id for hit in hits] == ["doc1"]


def test_second_document_below_tau_is_dropped_even_within_delta() -> None:
    hits = _retriever([0.62, 0.55, 0.0], tau=0.7, delta=0.3).retrieve("q")
    assert [hit.doc_id for hit in hits] == ["doc1"]


def test_at_most_top_k_documents_are_returned() -> None:
    hits = _retriever([1.0, 1.0, 1.0], tau=0.1, delta=1.0).retrieve("q")
    assert len(hits) == 2


def test_rank_returns_every_document_best_first() -> None:
    ranked = _retriever([0.1, 0.9, 0.5], tau=0.9).rank("q")
    assert [hit.doc_id for hit in ranked] == ["doc2", "doc3", "doc1"]
    assert ranked[0].score == pytest.approx(0.9 / np.linalg.norm([0.1, 0.9, 0.5]))


def test_store_rejects_mismatched_ids_and_vectors() -> None:
    with pytest.raises(ValueError, match="2 ids for 1 vectors"):
        NumpyStore(["doc1", "doc2"], np.ones((1, 3), dtype=np.float32))


def test_document_text_is_title_then_body() -> None:
    assert document_text(get_document("doc3")).startswith("Tiempos de envío. Envíos a la capital")


# --- embeddings cache


def test_cache_round_trips_vectors_exactly(tmp_path: Path) -> None:
    vector = np.asarray([0.1, -0.25, 3.5], dtype=np.float32)
    cache = EmbeddingCache(tmp_path / "cache.json")
    cache.put("google/embeddinggemma-300m", "¿Hacen envíos a Miami?", "query", vector)
    cache.save()
    reloaded = EmbeddingCache(tmp_path / "cache.json")
    stored = reloaded.get("google/embeddinggemma-300m", "¿Hacen envíos a Miami?", "query")
    assert stored is not None
    np.testing.assert_array_equal(stored, vector)
    assert reloaded.get("another-model", "¿Hacen envíos a Miami?", "query") is None


def test_cache_keeps_query_and_document_vectors_apart(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path / "cache.json")
    cache.put("m", "Garantía", "document", np.asarray([1.0, 0.0], dtype=np.float32))
    assert cache.get("m", "Garantía", "query") is None


def test_cache_only_embedder_explains_how_to_record_a_missing_vector(tmp_path: Path) -> None:
    embedder = CachedEmbedder(EmbeddingCache(tmp_path / "empty.json"), "google/embeddinggemma-300m")
    with pytest.raises(MissingEmbeddingError, match=r"morpho\.evals\.record_embeddings"):
        embedder.embed(["¿Cuánto tarda un reembolso?"], "query")


def test_only_missing_texts_go_to_the_fallback(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path / "cache.json")
    cache.put("fake-model", "cached", "query", np.asarray([1.0, 0.0], dtype=np.float32))
    fallback = FakeEmbedder({"new": [0.0, 1.0]})
    vectors = CachedEmbedder(cache, "fake-model", fallback).embed(["cached", "new", "new"], "query")
    assert fallback.calls == [("query", ["new"])]
    np.testing.assert_array_equal(vectors, [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])


def test_fallback_must_use_the_cache_model(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fallback embeds with"):
        CachedEmbedder(EmbeddingCache(tmp_path / "c.json"), "model-a", FakeEmbedder({}, "model-b"))


class _RecordingBackend:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.seen.extend(texts)
        return [[float(i), 1.0] for i in range(len(texts))]


def test_local_embedder_adds_the_embeddinggemma_prompts_and_loads_once(tmp_path: Path) -> None:
    backend, loads = _RecordingBackend(), []

    def load(model: str, cache_dir: str | None) -> _RecordingBackend:
        loads.append((model, cache_dir))
        return backend

    embedder = FastEmbedEmbedder("google/embeddinggemma-300m", tmp_path, load=load)
    vectors = embedder.embed(["Garantía. Texto"], "document")
    embedder.embed(["¿Cuánto dura?"], "query")
    assert backend.seen == [
        "title: none | text: Garantía. Texto",
        "task: search result | query: ¿Cuánto dura?",
    ]
    assert loads == [("google/embeddinggemma-300m", str(tmp_path))]
    assert vectors.dtype == np.float32
    np.testing.assert_array_equal(vectors, [[0.0, 1.0]])


def test_local_embedder_can_load_ahead_of_the_first_question() -> None:
    loads: list[str] = []

    def load(model: str, _cache_dir: str | None) -> _RecordingBackend:
        loads.append(model)
        return _RecordingBackend()

    embedder = FastEmbedEmbedder("m", load=load)
    assert embedder.loaded is False
    embedder.load()
    embedder.embed(["hola"], "query")
    assert embedder.loaded is True
    assert loads == ["m"]


def test_local_embedder_sends_plain_text_for_models_without_prompts() -> None:
    backend = _RecordingBackend()
    FastEmbedEmbedder("other/model", load=lambda *_: backend).embed(["hola"], "query")
    assert backend.seen == ["hola"]


# --- thresholds and calibration


def test_missing_threshold_explains_how_to_calibrate(tmp_path: Path) -> None:
    with pytest.raises(NotCalibratedError, match=r"morpho\.evals\.calibrate"):
        load_thresholds("google/embeddinggemma-300m", tmp_path / "thresholds.json")


def test_threshold_is_the_midpoint_between_in_and_out_of_domain() -> None:
    tau, separation = threshold_between([0.62, 0.55, 0.70], [0.31, 0.40])
    assert tau == pytest.approx(0.475)
    assert separation == pytest.approx(0.15)


def test_calibration_leaves_out_questions_the_rules_escalate() -> None:
    vectors = {
        document_text(get_document("doc1")): [1.0, 0.0],
        document_text(get_document("doc5")): [0.0, 1.0],
        "¿Cuánto dura la garantía?": [0.9, 0.1],
        "Me cobraron doble": [0.1, 0.2],
        "Dame una receta de paella": [0.3, 0.3],
    }
    retriever = Retriever.over_documents(
        FakeEmbedder(vectors), Thresholds(0.0), [get_document("doc1"), get_document("doc5")]
    )
    questions = QuestionSet(
        in_domain=(
            LabeledQuestion("¿Cuánto dura la garantía?", ("doc1",)),
            LabeledQuestion("Me cobraron doble", ("doc5",)),
        ),
        out_of_domain=("Dame una receta de paella",),
    )
    result, _ = calibrate(retriever, questions)
    assert result.min_in_domain == pytest.approx(0.9939, abs=1e-4)  # the escalating one is ignored
    assert result.top1_correct == 2
    assert result.separation > 0


def test_hit_is_a_plain_value() -> None:
    assert Hit("doc1", 0.5) == Hit("doc1", 0.5)


def test_a_failed_model_load_is_reported_and_not_retried() -> None:
    attempts: list[str] = []

    def load(model: str, _cache_dir: str | None) -> _RecordingBackend:
        attempts.append(model)
        raise ValueError("Could not load model from any source")

    embedder = FastEmbedEmbedder("m", load=load)
    for _ in range(2):
        with pytest.raises(EmbedderUnavailableError, match="Could not load"):
            embedder.embed(["hola"], "query")
    assert attempts == ["m"]
