import re

from morpho.guardrails.rules import Reason
from morpho.llm.base import Usage
from morpho.records import HandoffLog, cost_usd


def test_handoff_reference_has_the_expected_shape() -> None:
    handoff = HandoffLog(None).record("c1", (Reason.LEGAL,), "Los voy a demandar")
    assert re.fullmatch(r"ESC-\d{8}-[0-9A-F]{4}", handoff.reference)
    assert handoff.rule_ids == ("LEGAL",)
    assert handoff.reasons == ("tema legal",)


def test_handoff_summary_is_redacted_and_short() -> None:
    message = "Me cobraron doble, mi correo es ana.perez@correo.example " + "x" * 500
    handoff = HandoffLog(None).record("c1", (Reason.BILLING_DISPUTE,), message)
    assert "ana.perez" not in handoff.summary
    assert len(handoff.summary) == 280


def test_in_memory_log_keeps_records_without_a_file() -> None:
    log = HandoffLog(None)
    log.record("c1", (Reason.HUMAN_REQUEST,), "Quiero hablar con un asesor")
    assert len(log.records) == 1


def test_cost_uses_cached_and_output_prices() -> None:
    usage = Usage(input_tokens=2_000, output_tokens=500, cached_tokens=1_000)
    # claude-haiku-4-5: $1 input, $0.10 cache read, $5 output per 1M tokens
    expected = (1_000 * 1.00 + 1_000 * 0.10 + 500 * 5.00) / 1_000_000
    assert cost_usd("claude-haiku-4-5", usage) == round(expected, 8)


def test_unknown_model_costs_zero() -> None:
    assert cost_usd("fake-llm", Usage(1_000, 100)) == 0.0
