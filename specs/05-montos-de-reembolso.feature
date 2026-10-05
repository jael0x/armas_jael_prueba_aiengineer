# language: es
Característica: Montos de reembolso
  Como TiendaHogar
  Quiero que Morpho lea los montos de reembolso como los escriben los clientes
  Para que todo reembolso mayor a $500 llegue a un supervisor y ninguno menor

  Esquema del escenario: Un monto mayor a $500 escala sin importar cómo se escriba
    Dado que un cliente escribe "Quiero un reembolso de <monto>"
    Cuando Morpho responde
    Entonces Morpho escala con el motivo "reembolso mayor a $500"

    Ejemplos:
      | monto                            |
      | $500.01                          |
      | $1.200                           |
      | 1,200.50 dólares                 |
      | USD 600                          |
      | seiscientos dólares              |
      | quinientos con cincuenta dólares |
      | medio millón de dólares          |

  Esquema del escenario: Un monto de $500 o menos no escala
    Dado que un cliente escribe "Quiero un reembolso de <monto>"
    Cuando Morpho responde
    Entonces Morpho no escala
    Y la respuesta explica que el reembolso tarda de 5 a 10 días hábiles y va al mismo método de pago

    Ejemplos:
      | monto              |
      | $500               |
      | 500.00 dólares     |
      | quinientos dólares |
      | $120               |

  Escenario: Un mensaje escala si alguno de sus montos supera $500
    Dado que un cliente escribe "Pagué $300 por la licuadora y $650 por la estufa, quiero ambos reembolsos"
    Cuando Morpho responde
    Entonces Morpho escala con el motivo "reembolso mayor a $500"

  Escenario: Un ID de pedido no se lee como monto
    Dado que un cliente escribe "Quiero el reembolso del pedido ORD-1003"
    Cuando Morpho responde
    Entonces Morpho no escala
    Y Morpho pide el monto del reembolso en dólares

  Escenario: Un reembolso en otra moneda pide el monto en dólares
    Dado que un cliente escribe "Quiero un reembolso de 5000 quetzales"
    Cuando Morpho responde
    Entonces Morpho no escala
    Y Morpho pide el monto del reembolso en dólares
    Y la respuesta no da el equivalente en dólares de 5000 quetzales

  Escenario: Una solicitud de reembolso sin monto explica la regla del supervisor
    Dado que un cliente escribe "Quiero un reembolso"
    Cuando Morpho responde
    Entonces la respuesta dice que los reembolsos mayores a $500 necesitan aprobación de un supervisor humano
    Y Morpho pide el monto del reembolso en dólares

  Escenario: Un monto dado en el mensaje siguiente completa la solicitud de reembolso
    Dado que Morpho pidió a un cliente el monto del reembolso en dólares
    Cuando el cliente escribe "800"
    Entonces Morpho escala con el motivo "reembolso mayor a $500"
