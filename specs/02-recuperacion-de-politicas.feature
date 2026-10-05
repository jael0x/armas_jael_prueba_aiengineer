# language: es
Característica: Recuperación de políticas
  Como Morpho
  Quiero encontrar los documentos de política que responden una pregunta
  Para que cada respuesta salga de las políticas de TiendaHogar

  Antecedentes:
    Dado que la base de conocimiento tiene estos documentos de política:
      | documento | tema                     |
      | Doc 1     | política de garantía     |
      | Doc 2     | política de devoluciones |
      | Doc 3     | tiempos de envío         |
      | Doc 4     | reembolsos               |
      | Doc 5     | canales de contacto      |

  Esquema del escenario: Una pregunta clara recupera primero el documento que la responde
    Cuando Morpho recupera documentos para "<pregunta>"
    Entonces el primer documento recuperado es "<documento>"

    Ejemplos:
      | pregunta                                               | documento |
      | ¿Cuánto dura la garantía de una lavadora?              | Doc 1     |
      | ¿Puedo devolver un producto que compré en liquidación? | Doc 2     |
      | ¿Cuánto tarda un envío a otra ciudad?                  | Doc 3     |
      | ¿Cuándo me devuelven mi dinero?                        | Doc 4     |
      | ¿A dónde escribo para poner una queja?                 | Doc 5     |
      | How long is the warranty on a fridge?                  | Doc 1     |

  Escenario: Una pregunta que cruza dos políticas recupera ambos documentos
    Cuando Morpho recupera documentos para "Si devuelvo la licuadora, ¿cuándo me reembolsan?"
    Entonces los documentos recuperados son "Doc 2" y "Doc 4"

  Escenario: Una pregunta ajena a las políticas no recupera ningún documento
    Cuando Morpho recupera documentos para "Dame una receta de paella"
    Entonces no se recupera ningún documento
