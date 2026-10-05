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
    # gpt-6-luna: $0.10 input, $0.01 cached input, $0.50 output per 1M tokens
    expected = (1_000 * 0.10 + 1_000 * 0.01 + 500 * 0.50) / 1_000_000
    assert cost_usd("gpt-6-luna", usage) == round(expected, 8)


def test_unknown_model_costs_zero() -> None:
    assert cost_usd("fake-llm", Usage(1_000, 100)) == 0.0
