"""Handoff records and per-turn traces, written as JSON lines.

Both pass through PII redaction. Traces never store the customer's message, only what the
turn did; attribute names follow the OpenTelemetry GenAI conventions so they map to
Application Insights or any OTel backend. In production the handoff becomes an event on
`support.escalation.requested`.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from morpho.config import PRICES_PER_MTOK
from morpho.guardrails.pii import redact
from morpho.guardrails.rules import Reason
from morpho.llm.base import Usage

SUMMARY_CHARS = 280


@dataclass(frozen=True)
class Handoff:
    reference: str
    conversation_id: str
    rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    summary: str
    created_at: str


class JsonLines:
    """Appends one JSON object per line; with no path it only keeps records in memory."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.records: list[dict[str, Any]] = []

    def append(self, record: dict[str, Any]) -> None:
        self.records.append(record)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")


class HandoffLog(JsonLines):
    def record(self, conversation_id: str, reasons: tuple[Reason, ...], message: str) -> Handoff:
        now = datetime.now(UTC)
        handoff = Handoff(
            reference=f"ESC-{now:%Y%m%d}-{secrets.token_hex(2).upper()}",
            conversation_id=conversation_id,
            rule_ids=tuple(reason.value for reason in reasons),
            reasons=tuple(reason.label for reason in reasons),
            summary=redact(message)[:SUMMARY_CHARS],
            created_at=now.isoformat(timespec="seconds"),
        )
        self.append(asdict(handoff))
        return handoff


def cost_usd(model: str, usage: Usage) -> float:
    prices = PRICES_PER_MTOK.get(model, {})
    fresh = usage.input_tokens - usage.cached_tokens
    total = (
        fresh * prices.get("input", 0.0)
        + usage.cached_tokens * prices.get("cached_input", prices.get("input", 0.0))
        + usage.output_tokens * prices.get("output", 0.0)
    )
    return round(total / 1_000_000, 8)


class TraceLog(JsonLines):
    def record(
        self,
        *,
        conversation_id: str,
        turn: int,
        model: str,
        path: str,
        language: str,
        usage: Usage,
        llm_requests: int,
        rule_ids: tuple[str, ...],
        handoff_reference: str | None,
        retrieved: list[tuple[str, float]],
        order_ids: list[str],
        tool_calls: int,
        validation_problems: tuple[str, ...],
        latency_ms: float,
    ) -> dict[str, Any]:
        trace = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "morpho",
            "gen_ai.conversation.id": conversation_id,
            "gen_ai.request.model": model,
            "gen_ai.usage.input_tokens": usage.input_tokens,
            "gen_ai.usage.output_tokens": usage.output_tokens,
            "gen_ai.usage.cache_read.input_tokens": usage.cached_tokens,
            "morpho.turn": turn,
            "morpho.path": path,
            "morpho.language": language,
            "morpho.llm_requests": llm_requests,
            "morpho.rules": list(rule_ids),
            "morpho.handoff_reference": handoff_reference,
            "morpho.retrieval": [
                {"doc": doc, "score": round(score, 4)} for doc, score in retrieved
            ],
            "morpho.order_ids": order_ids,
            "morpho.tool_calls": tool_calls,
            "morpho.validation_problems": list(validation_problems),
            "morpho.latency_ms": round(latency_ms, 1),
            "morpho.cost_usd": cost_usd(model, usage),
        }
        self.append(json.loads(redact(json.dumps(trace, ensure_ascii=False))))
        return trace
