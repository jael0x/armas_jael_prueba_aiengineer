"""specs/01-estado-de-pedidos.feature, scenarios on the lookup itself (1 to 5)."""

from collections.abc import Iterator, Mapping

import pytest

import morpho.tools.orders as orders
from morpho.tools.orders import ORDERS, consultar_estado_pedido, normalize_order_id


def test_mock_table_matches_the_challenge() -> None:
    assert ORDERS == {
        "ORD-1001": {
            "producto": "Refrigeradora",
            "estado": "En tránsito",
            "entrega_estimada": "3 días hábiles",
        },
        "ORD-1002": {"producto": "Licuadora", "estado": "Entregado", "entrega_estimada": None},
        "ORD-1003": {
            "producto": "Lavadora",
            "estado": "Procesando",
            "entrega_estimada": "6 días hábiles",
        },
        "ORD-1004": {"producto": "Tostadora", "estado": "Cancelado", "entrega_estimada": None},
    }


@pytest.mark.challenge
def test_order_in_transit_reports_product_status_and_estimated_delivery() -> None:
    assert consultar_estado_pedido("ORD-1001") == {
        "encontrado": True,
        "order_id": "ORD-1001",
        "producto": "Refrigeradora",
        "estado": "En tránsito",
        "entrega_estimada": "3 días hábiles",
    }


def test_delivered_order_has_no_estimated_delivery() -> None:
    result = consultar_estado_pedido("ORD-1002")
    assert result["estado"] == "Entregado"
    assert result["entrega_estimada"] is None


@pytest.mark.challenge
def test_unknown_order_is_not_found_without_invented_data() -> None:
    result = consultar_estado_pedido("ORD-9999")
    assert result == {
        "encontrado": False,
        "order_id": "ORD-9999",
        "error": "no_encontrado",
        "mensaje": "No existe un pedido con el ID ORD-9999.",
    }
    assert not {"producto", "estado", "entrega_estimada"} & result.keys()


@pytest.mark.parametrize("written_as", ["ord-1001", "ORD 1001", "ORD1001", "  ORD-1001\n"])
def test_common_spellings_resolve_to_the_canonical_id(written_as: str) -> None:
    result = consultar_estado_pedido(written_as)
    assert result["encontrado"] is True
    assert result["order_id"] == "ORD-1001"


class _ForbiddenTable(Mapping[str, Mapping[str, str | None]]):
    """Fails the test if anything reads the orders table."""

    def __getitem__(self, key: str) -> Mapping[str, str | None]:
        raise AssertionError(f"orders table read for {key!r}")

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("orders table iterated")

    def __len__(self) -> int:
        raise AssertionError("orders table sized")


@pytest.mark.parametrize(
    "malformed",
    ["ORD-10011", "ORD-1001'; DROP TABLE", "../", "1001", "pedido 1001", "", "ORD-12A4"],
)
@pytest.mark.challenge
def test_malformed_id_is_rejected_without_reading_the_orders(
    malformed: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orders, "ORDERS", _ForbiddenTable())
    result = consultar_estado_pedido(malformed)
    assert result["encontrado"] is False
    assert result["error"] == "formato_invalido"
    assert not {"producto", "estado", "entrega_estimada"} & result.keys()


def test_rejected_id_echo_is_truncated() -> None:
    result = consultar_estado_pedido("ORD-" + "9" * 500)
    assert len(result["order_id"]) == 64


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("ORD-1004", "ORD-1004"),
        ("ord1004", "ORD-1004"),
        ("ORD\u20131004", None),  # en dash instead of a hyphen
        ("ORD-1004 ", "ORD-1004"),
    ],
)
def test_normalize_order_id(raw: str, canonical: str | None) -> None:
    assert normalize_order_id(raw) == canonical
