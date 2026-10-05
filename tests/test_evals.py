"""The golden set, its code checks, the Claude judge and the report, all offline."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from morpho.agent import Agent, TurnResult
from morpho.config import Settings
from morpho.evals.golden import PATHS, Expectation, GoldenCase, check, load_golden
from morpho.evals.judge import METRICS, VERDICT_SCHEMA, ClaudeJudge, JudgeError
from morpho.evals.run_eval import CaseRun, Report, records_have_cards, render_markdown, run_case
from morpho.guardrails.rules import Reason
from morpho.llm.base import Usage
from morpho.llm.fake import FakeLLM
from morpho.records import HandoffLog, TraceLog
from morpho.retrieval.retriever import Hit

# --- the golden set file


def test_golden_set_covers_every_research_scenario() -> None:
    cases = load_golden()
    assert sorted({case.scenario for case in cases}) == list(range(1, 32))
    assert len({case.id for case in cases}) == len(cases)


def test_golden_expectations_use_known_paths_and_reasons() -> None:
    reasons = {reason.value for reason in Reason}
    for case in load_golden():
        assert set(case.expect.path) <= PATHS, case.id
        assert set(case.expect.reasons) <= reasons, case.id
        assert case.expect.language in {"es", "en"}, case.id
        assert case.turns, case.id


# --- code checks


def _result(**overrides: Any) -> TurnResult:
    values: dict[str, Any] = {
        "answer": "Tu pedido ORD-1001 está En tránsito [Doc3].",
        "path": "answered",
        "language": "es",
        "citations": ("doc3",),
        "lookups": ({"order_id": "ORD-1001", "encontrado": True},),
        "llm_requests": 2,
    }
    return TurnResult(**{**values, **overrides})


EXPECT = Expectation(
    path=("answered",),
    orders=("ORD-1001",),
    cites=("doc3",),
    contains=(("en transito", "en camino"),),
    forbidden=("reembolso",),
    model=True,
)


def test_matching_turn_has_no_problems() -> None:
    assert check(EXPECT, _result()) == []


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"path": "replaced"}, "camino replaced"),
        ({"reasons": (Reason.LEGAL,)}, "motivos LEGAL"),
        ({"lookups": ()}, "consultó ninguno"),
        ({"citations": ()}, "no cita doc3"),
        ({"answer": "Tu pedido ORD-1001 está Entregado [Doc3]."}, "no dice 'en transito'"),
        ({"answer": "En tránsito; tu reembolso llega pronto."}, "dice 'reembolso'"),
        ({"answer": "Your order ORD-1001 is in transit and arrives soon."}, "idioma en"),
        ({"llm_requests": 0}, "no llamó al modelo"),
    ],
)
def test_each_kind_of_mismatch_is_reported(overrides: dict[str, Any], problem: str) -> None:
    problems = check(EXPECT, _result(**overrides))
    assert any(p.startswith(problem) for p in problems), problems


def test_a_multi_turn_case_is_checked_on_its_last_turn() -> None:
    llm = FakeLLM()
    agent = Agent(llm=llm, retriever=_NoDocs(), handoffs=HandoffLog(None), traces=TraceLog(None))
    case = GoldenCase(
        "multiturno",
        31,
        "montos",
        ("Quiero un reembolso", "800"),
        Expectation(path=("escalated",), reasons=("REFUND_OVER_LIMIT",), model=False),
    )
    run = run_case(agent, case)
    assert run.passed, run.problems
    assert llm.calls == []


class _NoDocs:
    def retrieve(self, question: str) -> list[Hit]:
        return []


# --- the judge


class _FakeMessages:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.text, self.stop_reason = text, stop_reason
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        usage = SimpleNamespace(
            input_tokens=900,
            output_tokens=150,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
        content = [SimpleNamespace(type="text", text=self.text)]
        return SimpleNamespace(content=content, stop_reason=self.stop_reason, usage=usage)


def _verdict_json(score: int) -> str:
    return json.dumps({m: {"razonamiento": "ok", "puntaje": score} for m in METRICS})


def test_judge_sends_the_rubric_schema_and_what_the_agent_saw() -> None:
    fake = _FakeMessages(_verdict_json(5))
    judge = ClaudeJudge(SimpleNamespace(messages=fake), "claude-sonnet-5-5")
    result = _result(retrieved=(Hit("doc3", 0.5),))
    verdict = judge.grade(["¿Cómo va ORD-1001?"], result)

    request = fake.requests[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["output_config"]["format"] == {"type": "json_schema", "schema": VERDICT_SCHEMA}
    prompt = request["messages"][0]["content"]
    assert "Cliente: ¿Cómo va ORD-1001?" in prompt
    assert 'id="Doc3"' in prompt  # the retrieved document, as the agent saw it
    assert '"order_id": "ORD-1001"' in prompt
    assert verdict.passed
    assert verdict.usage == Usage(900, 150, 0)


def test_judge_also_sees_documents_cited_by_fixed_replies() -> None:
    fake = _FakeMessages(_verdict_json(5))
    result = _result(path="escalated", citations=("doc5",), lookups=())
    ClaudeJudge(SimpleNamespace(messages=fake), "m").grade(["Me cobraron doble"], result)
    assert 'id="Doc5"' in fake.requests[0]["messages"][0]["content"]


def test_low_score_fails_the_verdict() -> None:
    judge = ClaudeJudge(SimpleNamespace(messages=_FakeMessages(_verdict_json(2))), "m")
    assert judge.grade(["x"], _result()).passed is False


def test_judge_refusal_is_an_error_not_a_score() -> None:
    judge = ClaudeJudge(SimpleNamespace(messages=_FakeMessages("", "refusal")), "m")
    with pytest.raises(JudgeError, match="refusal"):
        judge.grade(["x"], _result())


# --- report


def test_report_has_the_category_table_and_lists_failures() -> None:
    case = GoldenCase("caso-a", 1, "politicas", ("x",), Expectation(path=("answered",)))
    runs = [
        CaseRun(case, _result(), [], Usage(1000, 100), 1500.0),
        CaseRun(case, _result(path="replaced"), ["camino replaced"], Usage(1000, 100), 900.0),
    ]
    report = Report(runs, Settings.from_env({}), records_have_cards=False, judge_model=None)
    markdown = render_markdown(report)
    assert "| Respuestas con políticas | 2 | 1 | 50% |" in markdown
    assert "- `caso-a`: camino replaced." in markdown
    assert "sin juez" in markdown


def test_card_numbers_in_the_records_are_detected(tmp_path: Path) -> None:
    (tmp_path / "handoffs.jsonl").write_text('{"summary": "[tarjeta]"}\n')
    assert records_have_cards(tmp_path) is False
    (tmp_path / "traces.jsonl").write_text('{"x": "4111 1111 1111 1111"}\n')
    assert records_have_cards(tmp_path) is True
