"""The five TiendaHogar policy documents, copied verbatim from the challenge.

The challenge says to use them as they are, so the texts must not be edited.
`tests/test_documents.py` pins each one with a SHA-256 hash.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDocument:
    doc_id: str
    title: str
    text: str


DOCUMENTS: tuple[PolicyDocument, ...] = (
    PolicyDocument(
        doc_id="doc1",
        title="Política de garantía",
        text=(
            "Todos los electrodomésticos grandes (refrigeradoras, lavadoras, estufas) tienen "
            "garantía de 12 meses desde la fecha de compra. Electrodomésticos pequeños "
            "(licuadoras, planchas, tostadoras) tienen garantía de 6 meses. La garantía cubre "
            "defectos de fábrica, no daños por mal uso."
        ),
    ),
    PolicyDocument(
        doc_id="doc2",
        title="Política de devoluciones",
        text=(
            "Los productos pueden devolverse dentro de 30 días de la compra si están sin usar y "
            "en su empaque original. Devoluciones después de 30 días solo se aceptan si el "
            "producto tiene un defecto cubierto por garantía. No se aceptan devoluciones de "
            "productos personalizados o en oferta final (“liquidación”)."
        ),
    ),
    PolicyDocument(
        doc_id="doc3",
        title="Tiempos de envío",
        text=(
            "Envíos a la capital: 2-3 días hábiles. Envíos a otras ciudades: 5-7 días hábiles. "
            "Envíos internacionales no están disponibles actualmente."
        ),
    ),
    PolicyDocument(
        doc_id="doc4",
        title="Reembolsos",
        text=(
            "Los reembolsos se procesan en 5-10 días hábiles después de recibir el producto "
            "devuelto. Se reembolsa al mismo método de pago original. Reembolsos mayores a $500 "
            "requieren aprobación de un supervisor humano — el agente no debe aprobarlos "
            "automáticamente."
        ),
    ),
    PolicyDocument(
        doc_id="doc5",
        title="Canales de contacto",
        text=(
            "Para quejas sobre el trato de un empleado, disputas de facturación, o cualquier tema "
            "legal, el cliente debe ser referido a un agente humano en "
            "soporte@tiendahogar.example — el asistente de IA no debe intentar resolver estos "
            "casos."
        ),
    ),
)

_BY_ID = {doc.doc_id: doc for doc in DOCUMENTS}


def get_document(doc_id: str) -> PolicyDocument:
    """Return the document with this id; raises `KeyError` for an unknown id."""
    return _BY_ID[doc_id]
