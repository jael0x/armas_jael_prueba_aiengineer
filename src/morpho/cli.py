"""Chat with Morpho in the terminal: `uv run morpho`. Type `salir` to leave."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Protocol

import anthropic

from morpho.agent import ConversationState, TurnResult
from morpho.config import load_settings
from morpho.guardrails.normalize import fold
from morpho.prompts import SUPPORT_EMAIL
from morpho.retrieval.embedder import MissingEmbeddingError
from morpho.retrieval.retriever import NotCalibratedError

MISSING_KEY = (
    "Falta ANTHROPIC_API_KEY. Copia .env.example a .env, agrega tu key y vuelve a correr "
    "`uv run morpho`. Los tests no la necesitan: `uv run pytest tests/`."
)
_EXIT_WORDS = {"salir", "exit", "quit"}


class TurnRunner(Protocol):
    def run_turn(self, raw_message: str, state: ConversationState) -> TurnResult: ...


def main() -> int:
    settings = load_settings()
    if not settings.has_api_key:
        print(MISSING_KEY, file=sys.stderr)
        return 2
    from morpho.app import build_agent  # imported here so a missing key never loads the SDKs

    try:
        agent = build_agent(settings)
    except (NotCalibratedError, MissingEmbeddingError) as exc:
        print(f"No se puede iniciar Morpho: {exc}", file=sys.stderr)
        return 2
    except anthropic.AnthropicError as exc:
        print(f"No se pudo conectar con Claude ({exc.__class__.__name__}).", file=sys.stderr)
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
        except anthropic.AnthropicError as exc:
            write(
                f"Morpho: No pude contactar al modelo ({exc.__class__.__name__}). Intenta de "
                f"nuevo o escribe a {SUPPORT_EMAIL}."
            )
            continue
        write(f"Morpho: {result.answer}")


if __name__ == "__main__":
    raise SystemExit(main())
