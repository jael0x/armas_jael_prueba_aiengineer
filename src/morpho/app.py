"""Wires the real agent from settings: Claude, the cached local embedder, the retriever and logs."""

from __future__ import annotations

from anthropic import Anthropic

from morpho.agent import Agent
from morpho.config import Settings
from morpho.llm.anthropic_client import AnthropicClient
from morpho.records import HandoffLog, TraceLog
from morpho.retrieval.embedder import CachedEmbedder, EmbeddingCache, FastEmbedEmbedder
from morpho.retrieval.retriever import Retriever, load_thresholds


def build_agent(settings: Settings, *, local_embedder: FastEmbedEmbedder | None = None) -> Agent:
    """`local_embedder` lets a caller share a model it already loaded (the web UI warms it up)."""
    local = local_embedder or FastEmbedEmbedder(settings.embedding_model, settings.models_dir)
    embedder = CachedEmbedder(EmbeddingCache(), settings.embedding_model, fallback=local)
    client = Anthropic(api_key=settings.anthropic_api_key)
    return Agent(
        llm=AnthropicClient(client, settings.llm_model, settings.effort),
        retriever=Retriever.over_documents(embedder, load_thresholds(settings.embedding_model)),
        handoffs=HandoffLog(settings.var_dir / "handoffs.jsonl"),
        traces=TraceLog(settings.var_dir / "traces.jsonl"),
    )
