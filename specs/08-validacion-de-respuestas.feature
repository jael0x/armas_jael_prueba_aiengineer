# language: es
Característica: Validación de respuestas
  Como TiendaHogar
  Quiero revisar cada borrador de respuesta antes de que lo vea el cliente
  Para que ninguna aprobación, dato de pedido inventado o cita falsa llegue a un cliente

  Escenario: Un borrador que aprueba un reembolso se reemplaza
    Dado que el modelo de lenguaje redacta "Tu reembolso de $800 está aprobado"
    Cuando Morpho valida el borrador
    Entonces el cliente no recibe el borrador
    Y el cliente recibe en su lugar el proceso de reembolso y el canal de soporte

  Escenario: Un borrador con una fecha de entrega que la consulta no devolvió se reemplaza
    Dado que la consulta del estado del pedido "ORD-1002" no devolvió entrega estimada
    Y el modelo de lenguaje redacta "Tu licuadora llega el 8 de octubre"
    Cuando Morpho valida el borrador
    Entonces el cliente no recibe el borrador

  Escenario: Un borrador que cita un documento no recuperado se reemplaza
    Dado que para la pregunta solo se recuperó "Doc 3"
    Y el modelo de lenguaje redacta una respuesta que cita "Doc 4"
    Cuando Morpho valida el borrador
    Entonces el cliente no recibe el borrador

  Escenario: Un borrador basado en los documentos recuperados se entrega sin cambios
    Dado que para la pregunta solo se recuperó "Doc 1"
    Y el modelo de lenguaje redacta "Las lavadoras tienen 12 meses de garantía [Doc1]"
    Cuando Morpho valida el borrador
    Entonces el cliente recibe el borrador sin cambios
