"""The golden set: cases for every scenario of RESEARCH.md §7.2, checked in code.

Each case is a fresh conversation. The expectations apply to its last turn and look for facts
(path, escalation reasons, order lookups, citations, phrases), never for exact wording.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from morpho.agent import TurnResult
from morpho.guardrails.normalize import fold
from morpho.language import detect_language

GOLDEN_PATH = Path(__file__).with_name("golden.jsonl")
PATHS = frozenset(
    {
        "escalated",
        "asked_refund_amount",
        "asked_order_id",
        "answered",
        "replaced",
        "abstained",
        "refused",
        "empty",
    }
)


@dataclass(frozen=True)
class Expectation:
    path: tuple[str, ...]
    """Any of these paths passes."""
    reasons: tuple[str, ...] = ()
    """Exact set of escalation rule ids."""
    orders: tuple[str, ...] | None = None
    """Order IDs the tool must look up, in any order. None skips the check."""
    cites: tuple[str, ...] = ()
    """Documents the answer must cite, among others."""
    contains: tuple[tuple[str, ...], ...] = ()
    """Each group needs at least one of its phrases in the answer (case and accents ignored)."""
    forbidden: tuple[str, ...] = ()
    language: str = "es"
    model: bool | None = None
    """Whether the model must be called (True) or must not be (False). None skips the check."""


@dataclass(frozen=True)
class GoldenCase:
    id: str
    scenario: int
    category: str
    turns: tuple[str, ...]
    expect: Expectation


def load_golden(path: Path = GOLDEN_PATH) -> list[GoldenCase]:
    cases = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        expect = raw["expect"]
        orders = expect["orders"]
        cases.append(
            GoldenCase(
                id=raw["id"],
                scenario=raw["scenario"],
                category=raw["category"],
                turns=tuple(raw["turns"]),
                expect=Expectation(
                    path=tuple(expect["path"]),
                    reasons=tuple(expect["reasons"]),
                    orders=None if orders is None else tuple(orders),
                    cites=tuple(expect["cites"]),
                    contains=tuple(tuple(group) for group in expect["contains"]),
                    forbidden=tuple(expect["forbidden"]),
                    language=expect["language"],
                    model=expect["model"],
                ),
            )
        )
    return cases


def check(expect: Expectation, result: TurnResult) -> list[str]:
    """What the turn got wrong, in Spanish for the report. An empty list means it passes."""
    problems = []
    answer = fold(result.answer)
    if result.path not in expect.path:
        problems.append(f"camino {result.path}; se esperaba {' o '.join(expect.path)}")
    reasons = sorted(reason.value for reason in result.reasons)
    if reasons != sorted(expect.reasons):
        problems.append(f"motivos {_listed(reasons)}; se esperaba {_listed(expect.reasons)}")
    if expect.orders is not None:
        looked_up = sorted(str(lookup.get("order_id")) for lookup in result.lookups)
        if looked_up != sorted(expect.orders):
            problems.append(f"consultó {_listed(looked_up)}; se esperaba {_listed(expect.orders)}")
    missing = [doc for doc in expect.cites if doc not in result.citations]
    if missing:
        problems.append(f"no cita {_listed(missing)}")
    for group in expect.contains:
        if not any(fold(phrase) in answer for phrase in group):
            problems.append(f"no dice {' / '.join(repr(p) for p in group)}")
    problems.extend(f"dice {p!r}" for p in expect.forbidden if fold(p) in answer)
    language = detect_language(result.answer)
    if language != expect.language:
        problems.append(f"idioma {language}; se esperaba {expect.language}")
    if expect.model is not None and (result.llm_requests > 0) != expect.model:
        called = "llamó" if result.llm_requests else "no llamó"
        problems.append(f"{called} al modelo")
    return problems


def _listed(items: tuple[str, ...] | list[str]) -> str:
    return ", ".join(items) if items else "ninguno"
