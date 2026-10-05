"""Records the embeddings cache for the five documents and the labeled questions.

Needs OPENAI_API_KEY. Only texts missing from the cache are sent to the API.

    uv run python -m morpho.evals.record_embeddings
"""

from __future__ import annotations

import sys

from openai import OpenAI

from morpho.config import PRICES_PER_MTOK, load_settings
from morpho.evals.questions import load_questions
from morpho.knowledge.documents import DOCUMENTS
from morpho.retrieval.embedder import CachedEmbedder, EmbeddingCache, OpenAIEmbedder
from morpho.retrieval.retriever import document_text


def texts_to_record() -> list[str]:
    return [document_text(doc) for doc in DOCUMENTS] + load_questions().all_questions()


def main() -> int:
    settings = load_settings()
    if not settings.has_api_key:
        print("Falta OPENAI_API_KEY: agrégala a .env (ver .env.example).", file=sys.stderr)
        return 2
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    api = OpenAIEmbedder(client, settings.embedding_model)
    cache = EmbeddingCache()
    CachedEmbedder(cache, settings.embedding_model, fallback=api).embed(texts_to_record())
    cache.save()
    price = PRICES_PER_MTOK.get(settings.embedding_model, {}).get("input", 0.0)
    cost = api.tokens_used / 1_000_000 * price
    print(
        f"{len(texts_to_record())} textos con vector de {settings.embedding_model} "
        f"en {cache.path}. Tokens nuevos: {api.tokens_used} (USD {cost:.6f})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
