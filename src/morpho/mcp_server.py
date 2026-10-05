"""MCP server that exposes the order status lookup over stdio.

Run it with `uv run morpho-mcp`. It offers one read-only tool, `consultar_estado_pedido`,
backed by the same function the agent calls.
"""

from typing import cast

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from morpho.tools.orders import OrderStatus, consultar_estado_pedido

TOOL_NAME = "consultar_estado_pedido"


def _lookup(order_id: str) -> OrderStatus:
    # The challenge fixes the function's return type as a bare `dict`, which MCP cannot turn
    # into an output schema. This wrapper only adds the typed shape; the logic is the same.
    return cast(OrderStatus, consultar_estado_pedido(order_id))


def build_server() -> MCPServer:
    server = MCPServer(
        name="morpho",
        instructions="Consulta el estado de pedidos de TiendaHogar por su ID (formato ORD-1234).",
    )
    server.add_tool(
        _lookup,
        name=TOOL_NAME,
        description=consultar_estado_pedido.__doc__,
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    return server


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
