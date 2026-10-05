# language: es
Característica: Consulta de pedidos por MCP
  Como aplicación conectada por MCP, por ejemplo MCP Inspector
  Quiero consultar el estado de un pedido sin pasar por el chat
  Para que otros agentes reutilicen la misma herramienta

  Escenario: El servidor MCP ofrece solo la consulta del estado de pedidos
    Cuando una aplicación MCP lista las herramientas disponibles
    Entonces la única herramienta es "consultar_estado_pedido"

  Escenario: La herramienta MCP devuelve el mismo resultado que la consulta del estado
    Cuando una aplicación MCP llama a "consultar_estado_pedido" para "ORD-1003"
    Entonces el resultado indica que el pedido existe
    Y el producto es "Lavadora"
    Y el estado es "Procesando"
    Y la entrega estimada es "6 días hábiles"
