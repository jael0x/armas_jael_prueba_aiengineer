"""Removes personal data before anything is written to a log, trace or handoff record.

Card numbers (checked with Luhn), email addresses and long digit sequences such as phone or ID
numbers are replaced. Order IDs (ORD-1234) are kept: advisors need them to find the case.
"""

from __future__ import annotations

import re

_CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_LONG_NUMBER = re.compile(r"(?<![\w-])\+?\d(?:[\d\s().-]*\d){7,}(?![\w])")


def redact(text: str) -> str:
    text = _CARD_CANDIDATE.sub(lambda m: "[tarjeta]" if _is_card(m.group()) else m.group(), text)
    text = _EMAIL.sub("[email]", text)
    return _LONG_NUMBER.sub(_redact_long_number, text)


def contains_card_number(text: str) -> bool:
    return any(_is_card(m.group()) for m in _CARD_CANDIDATE.finditer(text))


def _redact_long_number(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    return "[número]" if len(digits) >= 8 else match.group()


def _is_card(candidate: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", candidate)]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
