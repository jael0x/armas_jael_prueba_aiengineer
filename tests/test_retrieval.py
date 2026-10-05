"""Retrieval. The first block is specs/02-recuperacion-de-politicas.feature with the real
cached vectors of the configured embedding model; the rest checks the logic offline."""

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

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
    EmbeddingCache,
    MissingEmbeddingError,
    OpenAIEmbedder,
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

# --- specs/02-recuperacion-de-politicas.feature (real vectors, no API calls)


@pytest.fixture(scope="module")
def policy_retriever() -> Retriever:
    model = Settings.from_env({}).embedding_model
    try:
        thresholds = load_thresholds(model)
        return Retriever.over_documents(CachedEmbedder(EmbeddingCache(), model), thresholds)
    except (MissingEmbeddingError, NotCalibratedError) as exc:
        pytest.skip(f"Falta el caché de vectores o la calibración de {model}: {exc}")


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
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> Vectors:
        self.calls.append(list(texts))
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
    cache.put("text-embedding-3-small", "¿Hacen envíos a Miami?", vector)
    cache.save()
    reloaded = EmbeddingCache(tmp_path / "cache.json")
    stored = reloaded.get("text-embedding-3-small", "¿Hacen envíos a Miami?")
    assert stored is not None
    np.testing.assert_array_equal(stored, vector)
    assert reloaded.get("another-model", "¿Hacen envíos a Miami?") is None


def test_cache_only_embedder_explains_how_to_record_a_missing_vector(tmp_path: Path) -> None:
    embedder = CachedEmbedder(EmbeddingCache(tmp_path / "empty.json"), "text-embedding-3-small")
    with pytest.raises(MissingEmbeddingError, match=r"morpho\.evals\.record_embeddings"):
        embedder.embed(["¿Cuánto tarda un reembolso?"])


def test_only_missing_texts_go_to_the_fallback(tmp_path: Path) -> None:
    cache = EmbeddingCache(tmp_path / "cache.json")
    cache.put("fake-model", "cached", np.asarray([1.0, 0.0], dtype=np.float32))
    fallback = FakeEmbedder({"new": [0.0, 1.0]})
    vectors = CachedEmbedder(cache, "fake-model", fallback).embed(["cached", "new", "new"])
    assert fallback.calls == [["new"]]
    np.testing.assert_array_equal(vectors, [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])


def test_fallback_must_use_the_cache_model(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fallback embeds with"):
        CachedEmbedder(EmbeddingCache(tmp_path / "c.json"), "model-a", FakeEmbedder({}, "model-b"))


def test_openai_embedder_keeps_input_order_and_counts_tokens() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=[0.0, 1.0]),
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
        ],
        usage=SimpleNamespace(total_tokens=12),
    )
    client = SimpleNamespace(embeddings=SimpleNamespace(create=lambda **_: response))
    embedder = OpenAIEmbedder(client, "text-embedding-3-small")
    np.testing.assert_array_equal(embedder.embed(["a", "b"]), [[1.0, 0.0], [0.0, 1.0]])
    assert embedder.tokens_used == 12


# --- thresholds and calibration


def test_missing_threshold_explains_how_to_calibrate(tmp_path: Path) -> None:
    with pytest.raises(NotCalibratedError, match=r"morpho\.evals\.calibrate"):
        load_thresholds("text-embedding-3-small", tmp_path / "thresholds.json")


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
