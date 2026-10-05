# language: es
Característica: Respuestas basadas en las políticas
  Como cliente de TiendaHogar
  Quiero respuestas tomadas solo de las políticas de la tienda
  Para confiar en lo que Morpho me dice

  Escenario: Una respuesta de garantía da la regla y cita su documento
    Dado que un cliente escribe "¿Cuánto dura la garantía de una lavadora?"
    Cuando Morpho responde
    Entonces la respuesta dice que los electrodomésticos grandes tienen 12 meses de garantía desde la compra
    Y la respuesta cita "Doc 1"

  Escenario: El daño por mal uso no está cubierto por la garantía
    Dado que un cliente escribe "Se me cayó la plancha y se rompió, ¿la cubre la garantía?"
    Cuando Morpho responde
    Entonces la respuesta dice que la garantía cubre defectos de fábrica y no daños por mal uso
    Y la respuesta cita "Doc 1"

  Escenario: Los envíos internacionales se informan como no disponibles
    Dado que un cliente escribe "¿Hacen envíos a Miami?"
    Cuando Morpho responde
    Entonces la respuesta dice que los envíos internacionales no están disponibles
    Y la respuesta cita "Doc 3"

  Escenario: Un electrodoméstico fuera de las listas de garantía no se clasifica
    Dado que un cliente escribe "¿Cuánto dura la garantía de un microondas?"
    Cuando Morpho responde
    Entonces la respuesta da la regla de 12 meses para grandes y la de 6 meses para pequeños
    Y la respuesta dice que el microondas no está en ninguna de las dos listas
    Y la respuesta ofrece un asesor humano en "soporte@tiendahogar.example"

  Escenario: Una pregunta ajena a las políticas recibe una respuesta fija sin el modelo de lenguaje
    Dado que un cliente escribe "¿Quién ganó el mundial de 2022?"
    Cuando Morpho responde
    Entonces la respuesta dice que Morpho no tiene esa información
    Y la respuesta ofrece un asesor humano en "soporte@tiendahogar.example"
    Y no se consulta al modelo de lenguaje

  Escenario: Un dato que las políticas no cubren no se responde adivinando
    Dado que un cliente escribe "¿Cuánto cuesta el envío a la capital?"
    Cuando Morpho responde
    Entonces la respuesta dice que el costo de envío no está en las políticas de TiendaHogar
    Y la respuesta no da ningún precio
