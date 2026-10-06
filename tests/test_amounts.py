"""Amount reading behind specs/05-montos-de-reembolso.feature."""

from decimal import Decimal

import pytest

from morpho.guardrails.amounts import Amount, Currency, extract_amounts


def _values(text: str) -> list[tuple[Decimal, Currency]]:
    return [(a.value, a.currency) for a in extract_amounts(text)]


@pytest.mark.parametrize(
    ("text", "value", "currency"),
    [
        ("Quiero un reembolso de $500.01", "500.01", Currency.USD),
        ("Quiero un reembolso de $1.200", "1200", Currency.USD),
        ("Quiero un reembolso de 1,200.50 dólares", "1200.50", Currency.USD),
        ("Quiero un reembolso de 1.200,50 dólares", "1200.50", Currency.USD),
        ("Quiero un reembolso de USD 600", "600", Currency.USD),
        ("Quiero un reembolso de seiscientos dólares", "600", Currency.USD),
        ("Quiero un reembolso de quinientos con cincuenta dólares", "500.50", Currency.USD),
        ("Quiero un reembolso de medio millón de dólares", "500000", Currency.USD),
        ("Quiero un reembolso de $500", "500", Currency.USD),
        ("Quiero un reembolso de 500.00 dólares", "500.00", Currency.USD),
        ("Quiero un reembolso de quinientos dólares", "500", Currency.USD),
        ("I want a refund of seven hundred dollars", "700", Currency.USD),
        ("Me deben 800", "800", Currency.UNKNOWN),
        ("Quiero un reembolso de 5000 quetzales", "5000", Currency.OTHER),
        ("Quiero un reembolso de Q 5,000", "5000", Currency.OTHER),
        ("Me deben un millón de pesos", "1000000", Currency.OTHER),
    ],
)
def test_reads_a_single_amount(text: str, value: str, currency: Currency) -> None:
    assert _values(text) == [(Decimal(value), currency)]


def test_reads_every_amount_in_a_message() -> None:
    text = "Pagué $300 por la licuadora y $650 por la estufa, quiero ambos reembolsos"
    assert _values(text) == [(Decimal(300), Currency.USD), (Decimal(650), Currency.USD)]


@pytest.mark.parametrize(
    "text",
    [
        "Quiero el reembolso del pedido ORD-1003",
        "Los reembolsos tardan de 5-10 días hábiles",
        "Lo compré hace veinte días",
        "Lo compré el 05/10/2026",
        "Tenía un 50% de descuento",
        "Me cobraron doble en mi tarjeta 4111 1111 1111 1111",
        "Llámame al +502 5555 1234",
        "Lo compré en 2025",
        "Quiero un reembolso",
    ],
)
def test_ignores_numbers_that_are_not_amounts(text: str) -> None:
    assert extract_amounts(text) == []


def test_currency_symbol_after_the_number_is_not_read_as_dollars() -> None:
    assert extract_amounts("Quiero un reembolso de 500 €") == [
        Amount(Decimal("500"), Currency.OTHER)
    ]


def test_dollars_with_cents_in_words() -> None:
    [amount] = extract_amounts("quinientos dólares con cincuenta centavos")
    assert amount == Amount(Decimal("500.50"), Currency.USD)


def test_space_as_thousands_separator() -> None:
    assert extract_amounts("$12 000") == [Amount(Decimal("12000"), Currency.USD)]


def test_long_digit_runs_are_phones_not_prices() -> None:
    assert extract_amounts("$450, mi celular es 987654321") == [
        Amount(Decimal("450"), Currency.USD)
    ]


def test_a_year_like_reply_counts_when_the_amount_was_asked() -> None:
    assert extract_amounts("1999") == []
    assert extract_amounts("1999", keep_years=True) == [Amount(Decimal("1999"), Currency.UNKNOWN)]
