"""Deterministic escalation rules, evaluated before retrieval and before the language model.

Doc 4 and Doc 5 reserve some cases for people: refunds over $500, complaints about an
employee's treatment, billing disputes and legal matters. A customer can also ask for a human
at any time. These rules are plain code so they are predictable and testable, and so the
decision never depends on what the model happens to write. When in doubt they escalate:
sending a simple case to a person costs less than keeping a case a supervisor must see.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from morpho.guardrails.amounts import Currency, extract_amounts
from morpho.guardrails.normalize import NormalizedMessage

REFUND_LIMIT_USD = Decimal(500)


class Reason(StrEnum):
    HUMAN_REQUEST = "HUMAN_REQUEST"
    REFUND_OVER_LIMIT = "REFUND_OVER_LIMIT"
    STAFF_COMPLAINT = "STAFF_COMPLAINT"
    BILLING_DISPUTE = "BILLING_DISPUTE"
    LEGAL = "LEGAL"

    @property
    def label(self) -> str:
        """Label shown to the customer and stored in the handoff record."""
        return _LABELS[self]


_LABELS = {
    Reason.HUMAN_REQUEST: "solicitud de asesor",
    Reason.REFUND_OVER_LIMIT: "reembolso mayor a $500",
    Reason.STAFF_COMPLAINT: "queja de trato",
    Reason.BILLING_DISPUTE: "disputa de facturación",
    Reason.LEGAL: "tema legal",
}


@dataclass(frozen=True)
class RuleResult:
    reasons: tuple[Reason, ...] = ()
    """Why the message must go to a person, in the order the rules are listed below."""
    refund_intent: bool = False
    refund_amount_usd: Decimal | None = None
    """Largest dollar amount in a refund request, when there is one."""
    ask_refund_amount: bool = False
    """A refund request with no dollar amount: Morpho explains the process and asks for it."""
    prompt_injection: bool = False

    @property
    def escalate(self) -> bool:
        return bool(self.reasons)


_NEW_QUESTION = re.compile(r"\?|\bORD[\s-]?\d{4}\b", re.IGNORECASE)


def _any(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns))


# Patterns run on the folded text: lowercase and without accents ("reembolsó" -> "reembolso").
_HUMAN_REQUEST = _any(
    r"\b(?:hablar|comunicarme|contactar|chatear|atender\w*)\s+(?:con\s+)?(?:un|una|algun|alguna|el|la)?\s*"
    r"(?:asesor|asesora|agente|persona|humano|representante|ejecutivo|ejecutiva|supervisor|operador)",
    r"\b(?:pasame|pasenme|comunicame|transfiereme|transfiereme)\s+con\b",
    r"\bquiero\s+(?:un|una)\s+(?:asesor|asesora|persona|humano|agente humano)\b",
    r"\b(?:asesor|agente|persona)\s+(?:humano|humana|real)\b",
    r"\b(?:talk|speak|chat)\s+(?:to|with)\s+(?:a\s+)?(?:human|person|agent|representative|someone)\b",
    r"\b(?:real|live)\s+(?:person|human|agent)\b",
)
_REFUND = _any(
    r"\breembols\w*",
    r"\breintegr\w*",
    r"\bdevolucion\s+del\s+dinero\b",
    r"\bdevuelv\w*\s+(?:el|mi|mis|nuestro)?\s*dinero\b",
    r"\bdevolver(?:me|nos)?\s+(?:el|mi)\s+dinero\b",
    r"\bmi\s+dinero\s+de\s+vuelta\b",
    r"\brefund\w*",
    r"\bmoney\s+back\b",
    r"\breimburs\w*",
)
# A return or an approval request that names an amount is a refund request too:
# "devolver mi refrigeradora de $900", "apruébame $800".
_RETURN_OR_APPROVAL = _any(
    r"\bdevol\w*",
    r"\bdevuelv\w*",
    r"\bregres\w*",
    r"\breturn\w*",
    r"\baprueb\w*",
    r"\baprob\w*",
    r"\bautoriz\w*",
    r"\bapprov\w*",
    r"\bauthori[sz]\w*",
)
_STAFF = _any(
    r"\b(?:emplead|vendedor|cajer|repartidor|tecnic|dependient|encargad|gerente|instalador"
    r"|mensajer|chofer|transportista|guardia|asesor)\w*",
    r"\bpersonal\b",
    r"\b(?:employee|staff|cashier|clerk|salesperson|driver|technician|manager|courier)s?\b",
    r"\bdelivery\s+(?:guy|man|person)\b",
)
_MISTREATMENT = _any(
    r"\bgroser\w*",
    r"\bgrit\w*",
    r"\bmaltrat\w*",
    r"\bmal\s+trato\b",
    r"\binsult\w*",
    r"\bdiscrimin\w*",
    r"\bacos\w*",
    r"\bmala\s+actitud\b",
    r"\bfalta\s+de\s+respeto\b",
    r"\bfalt\w*\s+(?:el\s+)?respeto\b",
    r"\bmal\s*educad\w*",
    r"\bdescortes\w*",
    r"\birrespetu\w*",
    r"\bprepoten\w*",
    r"\bhumill\w*",
    r"\bofend\w*",
    r"\bagresiv\w*",
    r"\bamenaz\w*",
    r"\bburl\w*",
    r"\bqueja\w*",
    r"\bquejarme\b",
    r"\breclamo\w*",
    r"\b(?:rude|yell\w*|shout\w*|insult\w*|disrespect\w*|harass\w*|mistreat\w*|complain\w*)\b",
    r"\btreated\s+me\s+(?:badly|poorly|terribly)\b",
)
# Complaints about being served badly imply an employee even when none is named.
_BAD_SERVICE = _any(
    r"\b(?:me|nos)\s+(?:trato|trataron)\s+(?:muy\s+)?mal\b",
    r"\b(?:me|nos)\s+(?:grito|gritaron|insulto|insultaron|humillo|humillaron|discrimino"
    r"|discriminaron|maltrato|maltrataron|ofendio|ofendieron|amenazo|amenazaron)\b",
    r"\bme\s+(?:atendio|atendieron)\s+(?:muy\s+)?mal\b",
    r"\b(?:pesima|horrible|terrible)\s+atencion\b",
)
_BILLING = _any(
    r"\bcobr\w*\s+(?:doble|(?:dos|2)\s+veces|de\s+mas|demas|mal)\b",
    r"\bdoble\s+cobro\b",
    r"\b(?:cobro|cargo)\s+(?:duplicado|doble|indebido|no\s+reconocido|que\s+no\s+reconozco)\b",
    r"\bno\s+reconozco\s+(?:el|este|ese|un)\s+(?:cargo|cobro)\b",
    r"\bno\s+autorice\s+(?:el|este|ese|un)\s+(?:cargo|cobro)\b",
    r"\b(?:factura|boleta)\s+(?:incorrecta|equivocada|mal\s+hecha)\b",
    r"\berror\s+en\s+(?:la|mi)\s+(?:factura|boleta|cuenta)\b",
    r"\bme\s+facturaron\s+mal\b",
    r"\bcontracargo\b",
    r"\bdisputa\w*\s+(?:de|del|un|el)\s+(?:cargo|cobro|factura)\b",
    r"\b(?:double\s+charged|(?:charged|billed)\s+(?:me\s+)?twice|overcharg\w*|chargeback)\b",
    r"\b(?:billing|invoice)\s+(?:error|dispute|issue|problem|mistake)\b",
    r"\bunauthori[sz]ed\s+charge\b",
)
_LEGAL = _any(
    r"\bdemand(?:a|ar|are|aremos|o|amos)\b",
    r"\bdemanda\s+legal\b",
    r"\babogad\w*",
    r"\bjuicio\b",
    r"\bjuzgado\b",
    r"\btribunal\w*",
    r"\bdenunci\w*",
    r"\baccion(?:es)?\s+legal(?:es)?\b",
    r"\b(?:proceso|via|tema|asunto)\s+legal\b",
    r"\blegalmente\b",
    r"\bprofeco\b",
    r"\bdiaco\b",
    r"\bindecopi\b",
    r"\bsernac\b",
    r"\b(?:defensoria|proteccion)\s+(?:del|al)\s+consumidor\b",
    r"\b(?:sue|suing|lawsuit|lawyer|attorney|legal\s+action|court)\b",
)
_INJECTION = _any(
    r"\b(?:ignora|olvida|omite|desobedece|salta(?:te)?)\s+(?:todas\s+)?(?:tus|las|sus|estas)?\s*"
    r"(?:instrucciones|reglas|indicaciones|restricciones|politicas)\b",
    r"\b(?:ignore|forget|disregard)\s+(?:all\s+)?(?:your|the|previous|prior|above)?\s*"
    r"(?:instructions|rules|prompts?)\b",
    r"\bsystem\s+prompt\b",
    r"\bprompt\s+del\s+sistema\b",
    r"\binstrucciones\s+(?:del\s+sistema|internas|ocultas)\b",
    r"\b(?:muestra|revela|dime|imprime|repite)\s+(?:tus|las)\s+instrucciones\b",
    r"\b(?:a\s+partir\s+de\s+ahora|desde\s+ahora)\s+(?:eres|seras|actua)\b",
    r"\bactua\s+como\b",
    r"\bfinge\s+(?:que|ser)\b",
    r"\b(?:act\s+as|pretend\s+(?:to\s+be|you\s+are)|you\s+are\s+now)\b",
    r"\bmodo\s+(?:desarrollador|dan|dios)\b",
    r"\b(?:developer|dan|god)\s+mode\b",
    r"\bdo\s+anything\s+now\b",
    r"\bjailbreak\w*",
    r"<\|?\s*(?:system|im_start)",
)
_BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


def evaluate(message: NormalizedMessage, *, awaiting_refund_amount: bool = False) -> RuleResult:
    """Apply the escalation rules to one customer message.

    `awaiting_refund_amount` is True when Morpho asked for the refund amount in the previous
    turn, so a reply like "800" is read as the amount of that refund request.
    """
    text = message.folded
    reasons: list[Reason] = []

    if _HUMAN_REQUEST.search(text):
        reasons.append(Reason.HUMAN_REQUEST)

    amounts = extract_amounts(message.text, keep_years=awaiting_refund_amount)
    # Bare numbers count as dollars, since Doc 4 states the limit in dollars. Bare numbers
    # under 10 are quantities ("devolver 2 licuadoras"), not prices.
    dollar_values = [
        a.value
        for a in amounts
        if a.currency is Currency.USD or (a.currency is Currency.UNKNOWN and a.value >= 10)
    ]
    refund_intent = bool(
        _REFUND.search(text)
        or (_RETURN_OR_APPROVAL.search(text) and dollar_values)
        or (awaiting_refund_amount and amounts)
    )
    # Waiting for the amount ends when the customer moves on ("¿Cómo va ORD-1001?"); a reply
    # like "no estoy seguro" keeps the request open.
    still_waiting = (
        awaiting_refund_amount and not refund_intent and not _NEW_QUESTION.search(message.text)
    )
    refund_amount = max(dollar_values) if refund_intent and dollar_values else None
    if refund_amount is not None and refund_amount > REFUND_LIMIT_USD:
        reasons.append(Reason.REFUND_OVER_LIMIT)

    if (_STAFF.search(text) and _MISTREATMENT.search(text)) or _BAD_SERVICE.search(text):
        reasons.append(Reason.STAFF_COMPLAINT)
    if _BILLING.search(text):
        reasons.append(Reason.BILLING_DISPUTE)
    if _LEGAL.search(text):
        reasons.append(Reason.LEGAL)

    injection = bool(
        message.had_hidden_characters
        or _INJECTION.search(text)
        or _BASE64_BLOB.search(message.text)
    )
    return RuleResult(
        reasons=tuple(reasons),
        refund_intent=refund_intent or still_waiting,
        refund_amount_usd=refund_amount,
        ask_refund_amount=(refund_intent or still_waiting) and refund_amount is None,
        prompt_injection=injection,
    )
