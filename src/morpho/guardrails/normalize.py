"""Message normalization shared by the rules and the retriever."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MAX_CHARS = 2000

# Zero-width and bidi control characters: invisible to a reader, often used to hide instructions.
_HIDDEN = re.compile("[​-‏‪-‮⁠-⁤﻿]")
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class NormalizedMessage:
    text: str
    """What the customer wrote: NFKC, without hidden or control characters, capped in length."""
    folded: str
    """Lowercase copy without accents and with single spaces, used only for rule matching."""
    truncated: bool
    had_hidden_characters: bool
    is_empty: bool
    """True when the message has no letters or digits (empty, only emojis or punctuation)."""


def normalize(raw: str) -> NormalizedMessage:
    text = unicodedata.normalize("NFKC", raw)
    had_hidden = bool(_HIDDEN.search(text))
    text = _HIDDEN.sub("", text)
    text = "".join(ch if ch in "\n\t" or unicodedata.category(ch) != "Cc" else " " for ch in text)
    text = text.strip()
    truncated = len(text) > MAX_CHARS
    text = text[:MAX_CHARS]
    return NormalizedMessage(
        text=text,
        folded=fold(text),
        truncated=truncated,
        had_hidden_characters=had_hidden,
        is_empty=not any(ch.isalnum() for ch in text),
    )


def fold(text: str) -> str:
    """Lowercase, strip accents and collapse whitespace: "¿Envío?" -> "¿envio?"."""
    decomposed = unicodedata.normalize("NFD", text.casefold().replace("\u2019", "'"))
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return _SPACES.sub(" ", without_accents).strip()
