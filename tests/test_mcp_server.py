"""specs/10-consulta-de-pedidos-por-mcp.feature, through an in-process MCP client."""

import asyncio
from typing import Any

from mcp import Client
from mcp.types import Tool

from morpho.mcp_server import TOOL_NAME, build_server
from morpho.tools.orders import consultar_estado_pedido


def _list_tools() -> list[Tool]:
    async def run() -> list[Tool]:
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    return asyncio.run(run())


def _call(order_id: str) -> dict[str, Any] | None:
    async def run() -> dict[str, Any] | None:
        async with Client(build_server()) as client:
            result = await client.call_tool(TOOL_NAME, {"order_id": order_id})
            assert result.is_error is False
            return result.structured_content

    return asyncio.run(run())


def test_server_offers_only_the_order_status_lookup() -> None:
    tools = _list_tools()
    assert [tool.name for tool in tools] == ["consultar_estado_pedido"]
    assert tools[0].annotations is not None
    assert tools[0].annotations.read_only_hint is True


def test_mcp_tool_returns_the_same_result_as_the_lookup() -> None:
    assert _call("ORD-1003") == {
        "encontrado": True,
        "order_id": "ORD-1003",
        "producto": "Lavadora",
        "estado": "Procesando",
        "entrega_estimada": "6 días hábiles",
    }


def test_mcp_tool_returns_the_same_errors_as_the_lookup() -> None:
    for order_id in ("ORD-9999", "1001"):
        assert _call(order_id) == consultar_estado_pedido(order_id)
