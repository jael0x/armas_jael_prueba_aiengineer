"""specs/08-validacion-de-respuestas.feature, on the validator itself."""

import pytest

from morpho.guardrails.output_validator import (
    APPROVAL,
    CITATION,
    DATE,
    DURATION,
    ORDER_ID,
    ORDER_STATUS,
    cited_documents,
    validate_answer,
)
from morpho.knowledge.documents import get_document
from morpho.tools.orders import consultar_estado_pedido

DOC1 = get_document("doc1").text
DOC3 = get_document("doc3").text


def _problems(
    draft: str,
    docs: dict[str, str] | None = None,
    orders: list[str] | None = None,
    customer: str = "",
) -> tuple[str, ...]:
    docs = docs or {}
    return validate_answer(
        draft,
        retrieved_ids=list(docs),
        source_texts=list(docs.values()),
        lookups=[consultar_estado_pedido(order_id) for order_id in orders or []],
        customer_text=customer,
    ).problems


def test_draft_approving_a_refund_is_rejected() -> None:
    assert _problems("Tu reembolso de $800 está aprobado") == (APPROVAL,)


@pytest.mark.parametrize(
    "draft",
    [
        "Los reembolsos mayores a $500 requieren aprobación de un supervisor humano.",
        "Ese reembolso debe ser aprobado por un supervisor.",
        "No puedo aprobar reembolsos.",
    ],
)
def test_explaining_the_approval_rule_is_not_an_approval(draft: str) -> None:
    assert APPROVAL not in _problems(draft)


def test_draft_with_a_date_the_lookup_did_not_return_is_rejected() -> None:
    problems = _problems("Tu licuadora llega el 8 de octubre.", orders=["ORD-1002"])
    assert DATE in problems


def test_draft_citing_a_document_that_was_not_retrieved_is_rejected() -> None:
    problems = _problems("Tarda 5-7 días hábiles [Doc4].", docs={"doc3": DOC3})
    assert problems == (CITATION,)


def test_grounded_draft_passes() -> None:
    draft = "Las lavadoras tienen 12 meses de garantía [Doc1]."
    assert _problems(draft, docs={"doc1": DOC1}) == ()


def test_duration_not_in_the_sources_is_rejected() -> None:
    problems = _problems(
        "Los envíos a la capital tardan 1 día hábil o 4 días [Doc3].", docs={"doc3": DOC3}
    )
    assert DURATION in problems


def test_order_data_from_the_lookup_passes() -> None:
    draft = "Tu pedido ORD-1001 está En tránsito y llega en 3 días hábiles."
    assert _problems(draft, orders=["ORD-1001"], customer="¿Cómo va ORD-1001?") == ()


def test_order_id_nobody_looked_up_or_mentioned_is_rejected() -> None:
    problems = _problems("Tu pedido ORD-1005 está Procesando.", orders=["ORD-1003"])
    assert ORDER_ID in problems


def test_status_that_differs_from_the_lookup_is_rejected() -> None:
    problems = _problems("Tu pedido ORD-1004 está Entregado.", orders=["ORD-1004"])
    assert ORDER_STATUS in problems


def test_cited_documents_are_listed_once_in_order() -> None:
    assert cited_documents("A [Doc2]. B [Doc4]. C [doc2].") == ("doc2", "doc4")
