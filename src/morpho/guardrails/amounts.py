"""Reads money amounts the way customers write them.

Handles "$1.200", "1,200.50 dólares", "USD 600", "seiscientos dólares", "medio millón" and
"quinientos con cincuenta". Order IDs, day counts, dates, percentages and card numbers are
removed first so they are never read as amounts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from text_to_num import alpha2digit

from morpho.guardrails.normalize import fold


class Currency(StrEnum):
    USD = "USD"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"
    """A bare number. TiendaHogar's policies are in dollars, so callers treat it as USD."""


@dataclass(frozen=True)
class Amount:
    value: Decimal
    currency: Currency


_DURATION = re.compile(
    r"\b\d+(?:\s*(?:-|a|to)\s*\d+)?\s*"
    r"(?:dias?|semanas?|meses|mes|anos?|horas?|days?|weeks?|months?|years?|hours?)\b"
)
_NOT_AMOUNTS = [
    re.compile(r"\bord[\s-]?\d{4}\b"),  # order IDs
    re.compile(r"\b\d{4}(?:[ -]?\d{4}){3}\b"),  # card numbers
    re.compile(r"\+\d[\d\s-]{6,}\d"),  # phone numbers with a country code
    re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b"),  # dates like 05/10/2026
    re.compile(r"\b\d+(?:[.,]\d+)?\s*%"),  # percentages
    _DURATION,  # "30 días", "5-10 días hábiles"
]
_HALF = re.compile(r"\bmedio (\d+)\b")  # "medio millón" becomes "medio 1000000"
_WITH_CENTS = re.compile(r"\b(\d+) con (\d{1,2})\b")  # "quinientos con cincuenta" -> "500 con 50"
_NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])")
_YEAR = re.compile(r"(?:19|20)\d\d")

_USD_BEFORE = re.compile(r"(?:\$|us\$|usd|u\$s)\s*$")
_USD_AFTER = re.compile(r"^\s*(?:de\s+)?(?:usd|us\$|dolares|dolar|dollars?|bucks)\b")
_OTHER_BEFORE = re.compile(r"(?:\bq|€|£|\bs/|\bmxn|\bcop|\beur|\bgtq)\s*$")
_OTHER_AFTER = re.compile(
    r"^\s*(?:de\s+)?(?:quetzales|quetzal|pesos?|euros?|soles?|colones|colon|lempiras?|bolivares"
    r"|cordobas?|mxn|cop|gtq|eur)\b"
)


def extract_amounts(text: str) -> list[Amount]:
    prepared = _prepare(text)
    amounts = []
    for match in _NUMBER.finditer(prepared):
        raw = match.group()
        before, after = prepared[: match.start()], prepared[match.end() :]
        currency = _currency(before, after)
        if currency is Currency.UNKNOWN and _YEAR.fullmatch(raw):
            continue  # "compré en 2025" is a year, not an amount
        amounts.append(Amount(_parse_number(raw), currency))
    return amounts


def _prepare(text: str) -> str:
    folded = fold(text)
    for pattern in _NOT_AMOUNTS:
        folded = pattern.sub(" ", folded)
    folded = alpha2digit(folded, "es")
    folded = alpha2digit(folded, "en")
    folded = _HALF.sub(lambda m: str(int(m.group(1)) // 2), folded)
    folded = _WITH_CENTS.sub(lambda m: f"{m.group(1)}.{int(m.group(2)):02d}", folded)
    # Day counts written in words ("hace veinte días") only become digits after alpha2digit.
    return _DURATION.sub(" ", folded)


def _currency(before: str, after: str) -> Currency:
    if _OTHER_AFTER.match(after) or _OTHER_BEFORE.search(before):
        return Currency.OTHER
    if _USD_BEFORE.search(before) or _USD_AFTER.match(after):
        return Currency.USD
    return Currency.UNKNOWN


def _parse_number(raw: str) -> Decimal:
    """The last "." or "," is a decimal point unless exactly 3 digits follow it."""
    separators = [i for i, ch in enumerate(raw) if ch in ".,"]
    if not separators:
        return Decimal(raw)
    last = separators[-1]
    digits_after = len(raw) - last - 1
    if digits_after == 3:
        return Decimal(re.sub(r"[.,]", "", raw))
    whole = re.sub(r"[.,]", "", raw[:last])
    return Decimal(f"{whole}.{raw[last + 1 :]}")
