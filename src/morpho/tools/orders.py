"""Order status lookup over TiendaHogar's mock orders table."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal, NotRequired, TypedDict


class OrderStatus(TypedDict):
    """Shape of every result of `consultar_estado_pedido`, found or not."""

    encontrado: bool
    order_id: str
    producto: NotRequired[str]
    estado: NotRequired[str]
    entrega_estimada: NotRequired[str | None]
    error: NotRequired[Literal["no_encontrado", "formato_invalido"]]
    mensaje: NotRequired[str]


# The mock table from the challenge. Where the challenge shows "—" there is no estimate,
# so the value is None: a client must not print a placeholder as if it were a date.
ORDERS: Mapping[str, Mapping[str, str | None]] = {
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

# Accepts the common spellings "ORD-1001", "ord-1001", "ORD 1001" and "ORD1001".
# A bare "1001" is rejected on purpose: guessing the prefix could return someone else's order.
_ORDER_ID = re.compile(r"ORD[\s-]?(\d{4})", re.IGNORECASE)
_MAX_ECHO = 64


def normalize_order_id(raw: str) -> str | None:
    """Return the canonical `ORD-####` form of an order ID, or None if it is malformed."""
    match = _ORDER_ID.fullmatch(raw.strip())
    return f"ORD-{match.group(1)}" if match else None


def consultar_estado_pedido(order_id: str) -> dict:
    """Look up a TiendaHogar order by its ID, in the format ORD-1234.

    Returns `encontrado: true` with `producto`, `estado` and `entrega_estimada` (null when the
    order has no estimate). Otherwise returns `encontrado: false` with `error` set to
    `no_encontrado` or `formato_invalido`, and no order data. It never invents data.
    """
    canonical = normalize_order_id(order_id)
    if canonical is None:
        return _error(
            order_id[:_MAX_ECHO],
            "formato_invalido",
            "El ID de pedido debe tener el formato ORD-1234.",
        )
    order = ORDERS.get(canonical)
    if order is None:
        return _error(canonical, "no_encontrado", f"No existe un pedido con el ID {canonical}.")
    return {"encontrado": True, "order_id": canonical, **order}


def _error(order_id: str, code: str, message: str) -> dict[str, Any]:
    return {"encontrado": False, "order_id": order_id, "error": code, "mensaje": message}
