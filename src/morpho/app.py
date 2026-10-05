"""Wires the real agent from settings: OpenAI, the cached embedder, the retriever and the logs."""

from __future__ import annotations

from openai import OpenAI

from morpho.agent import Agent
from morpho.config import Settings
from morpho.llm.openai_client import OpenAIClient
from morpho.records import HandoffLog, TraceLog
from morpho.retrieval.embedder import CachedEmbedder, EmbeddingCache, OpenAIEmbedder
from morpho.retrieval.retriever import Retriever, load_thresholds


def build_agent(settings: Settings) -> Agent:
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    embedder = CachedEmbedder(
        EmbeddingCache(),
        settings.embedding_model,
        fallback=OpenAIEmbedder(client, settings.embedding_model),
    )
    return Agent(
        llm=OpenAIClient(client, settings.llm_model, settings.reasoning_effort),
        retriever=Retriever.over_documents(embedder, load_thresholds(settings.embedding_model)),
        handoffs=HandoffLog(settings.var_dir / "handoffs.jsonl"),
        traces=TraceLog(settings.var_dir / "traces.jsonl"),
    )
