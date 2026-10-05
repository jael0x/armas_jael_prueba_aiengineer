"""Records the embeddings cache for the five documents and the labeled questions.

Runs the embedding model locally: no API key. The first run downloads the model (about 1.2 GB
for EmbeddingGemma). Only texts missing from the cache are embedded.

    uv run python -m morpho.evals.record_embeddings
"""

from __future__ import annotations

from morpho.config import load_settings
from morpho.evals.questions import load_questions
from morpho.knowledge.documents import DOCUMENTS
from morpho.retrieval.embedder import CachedEmbedder, EmbeddingCache, FastEmbedEmbedder
from morpho.retrieval.retriever import document_text


def documents_to_record() -> list[str]:
    return [document_text(doc) for doc in DOCUMENTS]


def queries_to_record() -> list[str]:
    return load_questions().all_questions()


def main() -> int:
    settings = load_settings()
    local = FastEmbedEmbedder(settings.embedding_model, settings.models_dir)
    cache = EmbeddingCache()
    embedder = CachedEmbedder(cache, settings.embedding_model, fallback=local)
    documents, queries = documents_to_record(), queries_to_record()
    embedder.embed(documents, "document")
    embedder.embed(queries, "query")
    cache.save()
    print(
        f"{len(documents)} documentos y {len(queries)} preguntas con vector de "
        f"{settings.embedding_model} en {cache.path}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
