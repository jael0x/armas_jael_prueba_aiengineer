# language: es
Característica: Estado de pedidos
  Como cliente de TiendaHogar
  Quiero saber dónde está mi pedido
  Para saber cuándo llega sin llamar a la tienda

  Escenario: Un pedido en tránsito informa producto, estado y entrega estimada
    Cuando se consulta el estado del pedido "ORD-1001"
    Entonces el resultado indica que el pedido existe
    Y el producto es "Refrigeradora"
    Y el estado es "En tránsito"
    Y la entrega estimada es "3 días hábiles"

  Escenario: Un pedido entregado no tiene entrega estimada
    Cuando se consulta el estado del pedido "ORD-1002"
    Entonces el estado es "Entregado"
    Y la entrega estimada está vacía

  Escenario: Un pedido inexistente se informa como no encontrado sin inventar datos
    Cuando se consulta el estado del pedido "ORD-9999"
    Entonces el resultado indica que el pedido no existe
    Y el resultado no trae producto, estado ni entrega estimada

  Esquema del escenario: Las formas comunes de escribir un ID llevan al ID canónico
    Cuando se consulta el estado del pedido "<escrito-como>"
    Entonces el resultado indica que el pedido "ORD-1001" existe

    Ejemplos:
      | escrito-como |
      | ord-1001     |
      | ORD 1001     |
      | ORD1001      |

  Esquema del escenario: Un ID mal formado se rechaza sin buscar pedidos
    Cuando se consulta el estado del pedido "<entrada>"
    Entonces el resultado indica un formato de ID de pedido inválido
    Y no se busca ningún pedido

    Ejemplos:
      | entrada               |
      | ORD-10011             |
      | ORD-1001'; DROP TABLE |
      | ../                   |

  Escenario: Morpho pide el ID cuando el cliente no lo da
    Dado que un cliente escribe "¿Dónde está mi pedido?"
    Cuando Morpho responde
    Entonces Morpho pide el ID del pedido
    Y no se busca ningún pedido

  Escenario: Un pedido cancelado se informa sin inventar motivo ni reembolso
    Dado que un cliente escribe "¿Qué pasó con mi pedido ORD-1004?"
    Cuando Morpho responde
    Entonces la respuesta dice que el pedido "ORD-1004" está "Cancelado"
    Y la respuesta no da un motivo de cancelación
    Y la respuesta no promete un reembolso
