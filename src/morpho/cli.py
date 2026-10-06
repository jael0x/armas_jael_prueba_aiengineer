"""Chat with Morpho in the terminal: `uv run morpho`. Type `salir` to leave."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Protocol

from morpho.agent import ConversationState, TurnResult
from morpho.config import load_settings
from morpho.guardrails.normalize import fold
from morpho.llm.base import LLMUnavailableError
from morpho.prompts import SUPPORT_EMAIL
from morpho.retrieval.embedder import EmbedderUnavailableError, MissingEmbeddingError
from morpho.retrieval.retriever import NotCalibratedError

MISSING_KEY = (
    "Falta ANTHROPIC_API_KEY. Copia .env.example a .env, agrega tu key y vuelve a correr "
    "`uv run morpho`. Los tests no la necesitan: `uv run pytest tests/`."
)
_EXIT_WORDS = {"salir", "exit", "quit"}
_UNAVAILABLE = {
    LLMUnavailableError: "No pude contactar al modelo.",
    EmbedderUnavailableError: "No pude cargar el modelo de embeddings.",
}


class TurnRunner(Protocol):
    def run_turn(self, raw_message: str, state: ConversationState) -> TurnResult: ...


def main() -> int:
    settings = load_settings()
    if not settings.has_api_key:
        print(MISSING_KEY, file=sys.stderr)
        return 2
    from morpho.app import build_agent  # imported here so a missing key never loads the SDKs
    from morpho.retrieval.embedder import FastEmbedEmbedder

    local = FastEmbedEmbedder(settings.embedding_model, settings.models_dir)
    print("Preparando el modelo de embeddings (la primera vez se descarga, ~1.2 GB)...")
    try:
        local.load()
        agent = build_agent(settings, local_embedder=local)
    except (NotCalibratedError, MissingEmbeddingError, EmbedderUnavailableError) as exc:
        print(f"No se puede iniciar Morpho: {exc}", file=sys.stderr)
        return 2
    return chat(agent)


def chat(
    agent: TurnRunner,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
) -> int:
    write("Morpho, soporte de TiendaHogar. Escribe tu consulta, o 'salir' para terminar.")
    state = ConversationState()
    while True:
        try:
            raw = read("Tú: ")
        except (EOFError, KeyboardInterrupt):
            write("")
            return 0
        if fold(raw) in _EXIT_WORDS:
            return 0
        try:
            result = agent.run_turn(raw, state)
        except (LLMUnavailableError, EmbedderUnavailableError) as exc:
            write(
                f"Morpho: {_UNAVAILABLE[type(exc)]} Intenta de nuevo o escribe a {SUPPORT_EMAIL}."
            )
            print(f"[detalle] {exc}", file=sys.stderr)
            continue
        write(f"Morpho: {result.answer}")


if __name__ == "__main__":
    raise SystemExit(main())
