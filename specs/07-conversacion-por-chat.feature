# language: es
Característica: Conversación por chat
  Como cliente de TiendaHogar
  Quiero conversar con Morpho con mis palabras y en mi idioma
  Para recibir una respuesta clara aunque pregunte varias cosas a la vez

  Escenario: Un mensaje que mezcla un pedido y una disputa de facturación se atiende completo
    Dado que un cliente escribe "¿Cómo va mi pedido ORD-1001? Además me cobraron doble"
    Cuando Morpho responde
    Entonces la respuesta dice que el pedido "ORD-1001" está "En tránsito" con entrega en "3 días hábiles"
    Y Morpho escala con el motivo "disputa de facturación"
    Y la respuesta incluye una referencia de handoff

  Escenario: Morpho responde en el idioma del cliente
    Dado que un cliente escribe "How long is the warranty on a washing machine?"
    Cuando Morpho responde
    Entonces la respuesta está escrita en inglés

  Escenario: Un cliente que comparte un número de tarjeta recibe el consejo de no hacerlo
    Dado que un cliente escribe "Me cobraron doble en mi tarjeta 4111 1111 1111 1111"
    Cuando Morpho responde
    Entonces la respuesta aconseja al cliente no compartir números de tarjeta

  Escenario: Un mensaje vacío recibe una invitación a escribir la consulta
    Dado que un cliente envía un mensaje vacío
    Cuando Morpho responde
    Entonces Morpho pide al cliente que escriba su consulta
    Y no se consulta al modelo de lenguaje

  Escenario: El chat explica que falta la API key en vez de fallar
    Dado que no hay una API key de Anthropic configurada
    Cuando el cliente abre el chat
    Entonces el chat dice que falta la API key de Anthropic
    Y el chat termina sin mostrar un error de Python
