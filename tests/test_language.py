import pytest

from morpho.language import detect_language


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("¿Cuánto dura la garantía?", "es"),
        ("quiero devolver mi licuadora", "es"),
        ("How long is the warranty on a washing machine?", "en"),
        ("I want a refund of $700", "en"),
        ("ORD-1001", "es"),
        ("ok", "es"),
    ],
)
def test_detects_spanish_or_english(text: str, language: str) -> None:
    assert detect_language(text) == language
