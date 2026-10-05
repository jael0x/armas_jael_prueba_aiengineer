# language: es
Característica: Registro de handoffs y turnos
  Como responsable de soporte de TiendaHogar
  Quiero que cada escalamiento y cada turno queden registrados
  Para que los asesores retomen los casos y el equipo audite costo y comportamiento

  Escenario: Un escalamiento escribe un registro de handoff con la referencia que vio el cliente
    Dado que un cliente escribe "Quiero un reembolso de $800"
    Cuando Morpho escala el caso
    Entonces un registro de handoff guarda la misma referencia que recibió el cliente
    Y el registro de handoff guarda el motivo "reembolso mayor a $500" y un resumen corto

  Escenario: Cada turno escribe una traza con uso y costo
    Dado que un cliente escribe "¿Cuánto tarda un envío a otra ciudad?"
    Cuando Morpho responde
    Entonces la traza del turno guarda los tokens de entrada, los tokens de salida y la latencia
    Y la traza guarda los documentos recuperados con sus scores y el costo estimado

  Escenario: Los números de tarjeta nunca llegan a los registros
    Dado que un cliente escribe "Me cobraron doble en mi tarjeta 4111 1111 1111 1111"
    Cuando Morpho registra el turno
    Entonces ningún registro contiene "4111 1111 1111 1111"

  Escenario: Los IDs de pedido se conservan en los registros
    Dado que un cliente escribe "¿Cómo va mi pedido ORD-1003?"
    Cuando Morpho registra el turno
    Entonces la traza contiene "ORD-1003"
