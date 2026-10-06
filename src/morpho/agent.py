"""One customer turn, from the raw message to the answer, the handoff and the trace.

Order of a turn:
1. Normalize the message and pick the reply language.
2. Apply the escalation rules. A message that only needs a person never reaches the model.
3. A refund request with no dollar amount gets the refund process and a question for the amount.
4. "¿Dónde está mi pedido?" without an ID gets a question for the ID.
5. Retrieve policy documents. Nothing relevant and no order ID: a fixed reply offering a human.
6. Otherwise ask the model, with the documents and the order tool.
7. Validate the draft; a rejected draft is replaced by a fixed reply.
8. Record the trace.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from morpho.guardrails.normalize import normalize
from morpho.guardrails.output_validator import APPROVAL, cited_documents, validate_answer
from morpho.guardrails.pii import contains_card_number
from morpho.guardrails.rules import Reason, evaluate
from morpho.knowledge.documents import get_document
from morpho.language import Language, detect_language
from morpho.llm.base import Completion, LLMClient, Message, ToolCall, Usage
from morpho.prompts import ORDER_TOOL, TEMPLATES, build_instructions
from morpho.records import Handoff, HandoffLog, TraceLog
from morpho.retrieval.retriever import Hit
from morpho.tools.orders import consultar_estado_pedido, normalize_order_id

MAX_TOOL_ROUNDS = 3
HISTORY_TURNS = 3

_ORDER_ID = re.compile(r"\bORD[\s-]?\d{4}\b", re.IGNORECASE)
_MY_ORDER = re.compile(r"\b(?:mi|my)\s+(?:pedido|orden|compra|paquete|order|package)\b")
_STATUS_QUESTION = re.compile(
    r"\b(?:donde\s+esta|estado|como\s+va|ya\s+(?:salio|llego|lo\s+enviaron)|rastre\w*"
    r"|seguimiento|where\s+is|status|track\w*)\b"
)
_SENTENCE_BREAK = re.compile(r"(?<=[.?!])\s+|\n+")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)  # the chat is plain text; the model sometimes bolds
# A draft cut by the token limit or stopped by the model's safety classifier is never sent.
_UNFINISHED_STOPS = frozenset({"max_tokens", "refusal"})


class DocumentRetriever(Protocol):
    def retrieve(self, question: str) -> list[Hit]: ...


@dataclass
class ConversationState:
    conversation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    turns: int = 0
    awaiting_refund_amount: bool = False
    history: list[Message] = field(default_factory=list)


@dataclass(frozen=True)
class TurnResult:
    answer: str
    path: str
    """One of: escalated, asked_refund_amount, asked_order_id, answered, replaced,
    abstained, refused, empty."""
    language: Language
    reasons: tuple[Reason, ...] = ()
    handoff: Handoff | None = None
    retrieved: tuple[Hit, ...] = ()
    citations: tuple[str, ...] = ()
    lookups: tuple[dict[str, Any], ...] = ()
    llm_requests: int = 0
    usage: Usage = field(default_factory=Usage)
    validation_problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Draft:
    text: str
    hits: list[Hit]
    lookups: list[dict[str, Any]]
    completion: Completion
    problems: tuple[str, ...]


class Agent:
    def __init__(
        self,
        *,
        llm: LLMClient,
        retriever: DocumentRetriever,
        handoffs: HandoffLog,
        traces: TraceLog,
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.handoffs = handoffs
        self.traces = traces
        self.max_tool_rounds = max_tool_rounds

    def run_turn(self, raw_message: str, state: ConversationState) -> TurnResult:
        started = time.perf_counter()
        state.turns += 1
        message = normalize(raw_message)
        language = detect_language(message.text)
        templates = TEMPLATES[language]
        rules = evaluate(message, awaiting_refund_amount=state.awaiting_refund_amount)
        parts: list[str] = []
        draft: _Draft | None = None
        handoff: Handoff | None = None

        if message.is_empty:
            path = "empty"
            parts.append(templates.empty)
        elif rules.escalate:
            path = "escalated"
            handoff = self.handoffs.record(state.conversation_id, rules.reasons, message.text)
            residual = _residual_question(message.text)
            if residual:
                draft = self._draft(
                    residual,
                    language,
                    state,
                    escalated_elsewhere=True,
                    injection=rules.prompt_injection,
                )
                if draft:
                    parts.append(draft.text)
            if rules.prompt_injection:
                parts.append(templates.injection_refusal)
            parts.append(templates.escalation(rules.reasons, handoff.reference))
            state.awaiting_refund_amount = False
        elif rules.ask_refund_amount:
            path = "asked_refund_amount"
            if rules.prompt_injection:
                parts.append(templates.injection_refusal)
            parts.append(templates.ask_refund_amount)
            state.awaiting_refund_amount = True
        else:
            state.awaiting_refund_amount = False
            if not _order_ids(message.text) and _asks_for_own_order(message.folded):
                path = "asked_order_id"
                parts.append(templates.ask_order_id)
            else:
                question = (
                    _without_injection(message.text) if rules.prompt_injection else message.text
                )
                draft = (
                    self._draft(
                        question,
                        language,
                        state,
                        injection=rules.prompt_injection,
                        refund_amount_usd=rules.refund_amount_usd,
                    )
                    if question
                    else None
                )
                if draft:
                    path = "replaced" if draft.problems else "answered"
                    parts.append(draft.text)
                elif rules.prompt_injection:
                    path = "refused"
                    parts.extend([templates.injection_refusal, templates.offer_help])
                else:
                    path = "abstained"
                    parts.append(templates.abstain)

        if contains_card_number(message.text):
            parts.append(templates.card_advice)
        answer = "\n\n".join(parts)
        self._remember(state, message.text, answer)

        result = TurnResult(
            answer=answer,
            path=path,
            language=language,
            reasons=rules.reasons,
            handoff=handoff,
            retrieved=tuple(draft.hits) if draft else (),
            citations=cited_documents(answer),
            lookups=tuple(draft.lookups) if draft else (),
            llm_requests=draft.completion.requests if draft else 0,
            usage=draft.completion.usage if draft else Usage(),
            validation_problems=draft.problems if draft else (),
        )
        self.traces.record(
            conversation_id=state.conversation_id,
            turn=state.turns,
            model=self.llm.model,
            path=path,
            language=language,
            usage=result.usage,
            llm_requests=result.llm_requests,
            rule_ids=tuple(reason.value for reason in rules.reasons),
            handoff_reference=handoff.reference if handoff else None,
            retrieved=[(hit.doc_id, hit.score) for hit in result.retrieved],
            order_ids=sorted(
                {*_order_ids(message.text), *(str(r["order_id"]) for r in result.lookups)}
            ),
            tool_calls=len(result.lookups),
            validation_problems=result.validation_problems,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        return result

    def _draft(
        self,
        question: str,
        language: Language,
        state: ConversationState,
        *,
        escalated_elsewhere: bool = False,
        injection: bool = False,
        refund_amount_usd: Decimal | None = None,
    ) -> _Draft | None:
        """Ask the model about `question`, or return None when there is nothing to answer from."""
        hits = self.retriever.retrieve(question)
        if not hits and not _order_ids(question):
            return None
        documents = [get_document(hit.doc_id) for hit in hits]
        lookups: list[dict[str, Any]] = []

        def run_tool(call: ToolCall) -> dict[str, Any]:
            if call.name == ORDER_TOOL.name:
                result = consultar_estado_pedido(str(call.arguments.get("order_id", "")))
            else:
                result = {"error": "herramienta_desconocida", "mensaje": f"No existe {call.name}."}
            lookups.append(result)
            return result

        completion = self.llm.complete(
            instructions=build_instructions(
                language,
                documents,
                escalated_elsewhere=escalated_elsewhere,
                injection=injection,
                refund_amount_usd=refund_amount_usd,
            ),
            messages=[*state.history, Message("user", _with_canonical_order_ids(question))],
            tools=[ORDER_TOOL],
            run_tool=run_tool,
            max_tool_rounds=self.max_tool_rounds,
        )
        problems = validate_answer(
            completion.text,
            retrieved_ids=[hit.doc_id for hit in hits],
            source_texts=[doc.text for doc in documents],
            lookups=[r for r in lookups if "order_id" in r],
            customer_text=question,
        ).problems
        if not completion.text.strip():
            problems = (*problems, "empty_answer")
        if completion.stop_reason in _UNFINISHED_STOPS:
            problems = (*problems, f"stop_{completion.stop_reason}")
        text = _BOLD.sub(r"\1", completion.text).strip()
        if problems:
            templates = TEMPLATES[language]
            text = (
                templates.refund_process_fallback
                if APPROVAL in problems
                else templates.safe_fallback
            )
        return _Draft(text, hits, lookups, completion, problems)

    def _remember(self, state: ConversationState, message: str, answer: str) -> None:
        state.history.extend([Message("user", message), Message("assistant", answer)])
        del state.history[: -2 * HISTORY_TURNS]


def _order_ids(text: str) -> list[str]:
    ids = (normalize_order_id(match) for match in _ORDER_ID.findall(text))
    return sorted({order_id for order_id in ids if order_id})


def _with_canonical_order_ids(text: str) -> str:
    """ "ord 1001" becomes "ORD-1001": the model then passes the ID as the tool expects it."""
    return _ORDER_ID.sub(lambda match: normalize_order_id(match.group()) or match.group(), text)


def _asks_for_own_order(folded: str) -> bool:
    return bool(_MY_ORDER.search(folded) and _STATUS_QUESTION.search(folded))


def _without_injection(text: str) -> str | None:
    """The sentences of a message that do not try to change Morpho's rules, or None."""
    keep = [
        sentence.strip()
        for sentence in _SENTENCE_BREAK.split(text)
        if sentence.strip() and not evaluate(normalize(sentence)).prompt_injection
    ]
    return " ".join(keep) or None


def _residual_question(text: str) -> str | None:
    """Parts of an escalated message that are questions Morpho can still answer."""
    keep = []
    for sentence in _SENTENCE_BREAK.split(text):
        result = evaluate(normalize(sentence))
        if result.escalate or result.refund_intent or result.prompt_injection:
            continue
        if "?" in sentence or _order_ids(sentence):
            keep.append(sentence.strip())
    return " ".join(keep) or None
