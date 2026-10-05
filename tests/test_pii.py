"""Redaction behind specs/09-registro-de-handoffs-y-turnos.feature."""

import pytest

from morpho.guardrails.pii import contains_card_number, redact


def test_card_number_never_reaches_the_records() -> None:
    redacted = redact("Me cobraron doble en mi tarjeta 4111 1111 1111 1111")
    assert "4111 1111 1111 1111" not in redacted
    assert redacted == "Me cobraron doble en mi tarjeta [tarjeta]"


def test_order_ids_are_kept() -> None:
    assert redact("¿Cómo va mi pedido ORD-1003?") == "¿Cómo va mi pedido ORD-1003?"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Escríbeme a maria.lopez@correo.example", "Escríbeme a [email]"),
        ("Mi teléfono es +502 5555 1234", "Mi teléfono es [número]"),
        ("Mi DPI es 2589123450101", "Mi DPI es [número]"),
        ("Quiero un reembolso de $1,200.50", "Quiero un reembolso de $1,200.50"),
    ],
)
def test_other_personal_data_is_redacted_but_amounts_stay(text: str, expected: str) -> None:
    assert redact(text) == expected


def test_detects_a_valid_card_number() -> None:
    assert contains_card_number("tarjeta 4111-1111-1111-1111") is True


def test_number_failing_luhn_is_not_a_card() -> None:
    assert contains_card_number("1234 5678 9012 3456") is False
