"""Picks the reply language: Spanish unless the message reads as English."""

from __future__ import annotations

import re
from typing import Literal

from morpho.guardrails.normalize import fold

Language = Literal["es", "en"]

_SPANISH_MARKS = re.compile(r"[¿¡ñáéíóú]")
_WORD = re.compile(r"[a-z']+")
_ES = frozenset(
    [
        "de",
        "la",
        "el",
        "que",
        "en",
        "y",
        "los",
        "las",
        "un",
        "una",
        "mi",
        "por",
        "para",
        "con",
        "es",
        "se",
        "no",
        "me",
        "lo",
        "cuanto",
        "donde",
        "cuando",
        "como",
        "quiero",
        "puedo",
        "tengo",
        "hola",
        "gracias",
        "pedido",
        "garantia",
        "envio",
        "reembolso",
        "devolver",
    ]
)
_EN = frozenset(
    [
        "the",
        "is",
        "my",
        "what",
        "how",
        "when",
        "where",
        "to",
        "a",
        "of",
        "for",
        "i",
        "you",
        "your",
        "can",
        "do",
        "does",
        "it",
        "this",
        "an",
        "and",
        "want",
        "with",
        "order",
        "refund",
        "return",
        "shipping",
        "warranty",
        "hello",
        "thanks",
        "please",
    ]
)


def detect_language(text: str) -> Language:
    if _SPANISH_MARKS.search(text.casefold()):
        return "es"
    words = _WORD.findall(fold(text))
    spanish = sum(word in _ES for word in words)
    english = sum(word in _EN for word in words)
    return "en" if english > spanish else "es"
