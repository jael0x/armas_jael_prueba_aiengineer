"""Checks every model draft before the customer sees it.

A draft is rejected when it approves a refund, cites a document that was not retrieved,
mentions an order ID or status nobody looked up, or states a duration or calendar date that
does not come from the documents, the order lookup or the customer's own message. The agent then
sends a fixed reply.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from text_to_num import alpha2digit

from morpho.guardrails.normalize import fold
from morpho.tools.orders import ORDER_ID_EXAMPLE, normalize_order_id

APPROVAL = "approval"
CITATION = "citation"
ORDER_ID = "order_id"
ORDER_STATUS = "order_status"
DURATION = "duration"
DATE = "date"

_APPROVAL = re.compile(
    "|".join(
        [
            r"\b(?:esta|fue|ha\s+sido|queda|quedo|quedara)\s+(?:aprobad|autorizad)\w*",
            r"\b(?:aprobe|autorice|apruebo|autorizo)\s+(?:tu|el|su)\s+reembolso",
            r"\b(?:he|hemos|ha|han)\s+(?:aprobado|autorizado)\b",
            r"\bte\s+(?:reembolso|reembolsare|reembolsamos|reembolsaremos|devolvere|devolvemos"
            r"|devolveremos)\b",
            r"\b(?:procedemos|procederemos)\s+(?:con|a)\s+(?:el\s+|tu\s+)?reembols",
            r"\b(?:is|has\s+been|was)\s+(?:approved|authorized)\b",
            r"\bwe(?:'ll|\s+will)\s+refund\b",
            r"\bi(?:'ve|\s+have)?\s+(?:approved|authorized)\b",
            r"\b(?:approved|authorized)\s+(?:your|the)\s+refund\b",
        ]
    )
)
_CITATION = re.compile(r"\[\s*doc\s*(\d+)\s*\]", re.IGNORECASE)
_ORDER_ID = re.compile(r"\bORD[\s-]?\d{4}\b", re.IGNORECASE)
# Each status the tool returns, with the ways an answer can say it in Spanish or English.
_STATUSES = {
    "en transito": ("en transito", "in transit"),
    "entregado": ("entregado", "delivered"),
    "procesando": ("procesando", "processing"),
    "cancelado": ("cancelado", "cancelled", "canceled"),
}
_DURATION = re.compile(
    r"(\d+)(?:\s*(?:-|a|to|y|and)\s*(\d+))?\s*"
    r"(?:dias?|semanas?|meses|mes|anos?|horas?|days?|weeks?|months?|years?|hours?|business\s+days)\b"
)
_MONTHS = (
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre"
    "|diciembre|january|february|march|april|may|june|july|august|september|october|november"
    "|december"
)
_DATE = re.compile(
    rf"\b\d{{1,2}}\s+de\s+(?:{_MONTHS})\b"
    rf"|\b(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\b"
    r"|\b\d{1,2}/\d{1,2}\b"
    r"|\b\d{4}-\d{1,2}-\d{1,2}\b"
)
_NUMBER = re.compile(r"\d+")


@dataclass(frozen=True)
class Validation:
    problems: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.problems


def validate_answer(
    draft: str,
    *,
    retrieved_ids: Iterable[str],
    source_texts: Iterable[str],
    lookups: Iterable[Mapping[str, Any]],
    customer_text: str,
) -> Validation:
    """`source_texts` are the retrieved documents; `lookups` the order results of this turn."""
    folded = fold(draft)
    lookups = list(lookups)
    problems: list[str] = []

    if _APPROVAL.search(folded):
        problems.append(APPROVAL)

    allowed_docs = {doc_id.lower() for doc_id in retrieved_ids}
    if any(f"doc{n}" not in allowed_docs for n in _CITATION.findall(draft)):
        problems.append(CITATION)

    known_ids = {normalize_order_id(m) for m in _ORDER_ID.findall(customer_text)}
    known_ids |= {str(result.get("order_id")) for result in lookups}
    known_ids.add(ORDER_ID_EXAMPLE)
    if any(normalize_order_id(m) not in known_ids for m in _ORDER_ID.findall(draft)):
        problems.append(ORDER_ID)

    looked_up_statuses = {
        fold(str(result.get("estado"))) for result in lookups if result.get("encontrado")
    }
    mentions_order = bool(lookups) or bool(_ORDER_ID.search(draft))
    if mentions_order and any(
        status not in looked_up_statuses and any(word in folded for word in words)
        for status, words in _STATUSES.items()
    ):
        problems.append(ORDER_STATUS)

    sources = list(source_texts) + [str(result.get("entrega_estimada") or "") for result in lookups]
    source_numbers = set(_NUMBER.findall(" ".join(fold(text) for text in sources)))
    # A duration the customer stated ("la compré hace 45 días") can be repeated back.
    for match in _DURATION.finditer(_digits(fold(customer_text))):
        source_numbers.update(n for n in match.groups() if n)
    for match in _DURATION.finditer(_digits(folded)):
        if any(n and n not in source_numbers for n in match.groups()):
            problems.append(DURATION)
            break

    customer_dates = set(_DATE.findall(fold(customer_text)))
    if any(date not in customer_dates for date in _DATE.findall(folded)):
        problems.append(DATE)
    return Validation(tuple(problems))


def cited_documents(answer: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(f"doc{n}" for n in _CITATION.findall(answer)))


def _digits(folded: str) -> str:
    """Numbers written in words become digits, so "treinta días" is checked like "30 días"."""
    return alpha2digit(alpha2digit(folded, "es"), "en")
