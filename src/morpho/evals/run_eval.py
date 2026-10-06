"""Runs the golden set against the real agent and writes `evals/report.md` and `report.json`.

Needs ANTHROPIC_API_KEY. Every case is a fresh conversation. The code checks always run; Claude
grades the cases where the model wrote part of the answer, unless `--no-judge` is given.

    uv run python -m morpho.evals.run_eval [--no-judge] [--case ID ...]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from morpho.agent import Agent, ConversationState, TurnResult
from morpho.config import Settings, load_settings
from morpho.evals.golden import GoldenCase, check, load_golden
from morpho.evals.judge import METRICS, PASS_SCORE, ClaudeJudge, JudgeError, Verdict
from morpho.guardrails.pii import contains_card_number
from morpho.llm.base import Usage
from morpho.records import cost_usd

REPORT_DIR = Path("evals")
COMMAND = "uv run python -m morpho.evals.run_eval"
CATEGORY_NAMES = {
    "politicas": "Respuestas con políticas",
    "pedidos": "Estado de pedidos",
    "montos": "Montos y reembolsos",
    "escalamiento": "Escalamiento a humano",
    "inyeccion": "Inyección de prompts",
    "conversacion": "Conversación",
    "abstencion": "Abstención",
}
METRIC_NAMES = {
    "intent_resolution": "Resolución de la intención",
    "tool_call_accuracy": "Precisión de la tool",
    "task_adherence": "Apego a las reglas",
    "groundedness": "Fundamentación",
}


@dataclass
class CaseRun:
    case: GoldenCase
    result: TurnResult
    problems: list[str]
    usage: Usage
    latency_ms: float
    """Latency of the last turn, the one the checks look at."""
    verdict: Verdict | None = None
    judge_error: str | None = None

    @property
    def passed(self) -> bool:
        return not self.problems


@dataclass
class Report:
    runs: list[CaseRun]
    settings: Settings
    records_have_cards: bool
    judge_model: str | None
    started: datetime = field(default_factory=lambda: datetime.now(UTC))

    def agent_cost(self) -> float:
        return sum(cost_usd(self.settings.llm_model, run.usage) for run in self.runs)

    def judge_usage(self) -> Usage:
        usage = Usage()
        for run in self.runs:
            if run.verdict:
                usage += run.verdict.usage
        return usage


def run_case(agent: Agent, case: GoldenCase) -> CaseRun:
    state, usage = ConversationState(), Usage()
    result, latency_ms = None, 0.0
    for turn in case.turns:
        started = time.perf_counter()
        result = agent.run_turn(turn, state)
        latency_ms = (time.perf_counter() - started) * 1000
        usage += result.usage
    assert result is not None, f"{case.id} has no turns"
    return CaseRun(case, result, check(case.expect, result), usage, latency_ms)


def grade(judge: ClaudeJudge, run: CaseRun) -> None:
    """Only turns the model wrote are graded; fixed replies are covered by the code checks."""
    if run.result.llm_requests == 0:
        return
    try:
        run.verdict = judge.grade(run.case.turns, run.result)
    except (JudgeError, json.JSONDecodeError, KeyError) as exc:
        run.judge_error = f"{exc.__class__.__name__}: {exc}"


def records_have_cards(var_dir: Path) -> bool:
    return any(
        contains_card_number(path.read_text()) for path in var_dir.glob("*.jsonl") if path.exists()
    )


def render_markdown(report: Report) -> str:
    runs, settings = report.runs, report.settings
    passed = sum(run.passed for run in runs)
    lines = [
        "# Evaluación de Morpho",
        "",
        f"- Fecha: {report.started:%Y-%m-%d %H:%M} UTC",
        f"- Agente: `{settings.llm_model}` con embeddings `{settings.embedding_model}`",
        f"- Juez: `{_judge_model(report)}`",
        f"- Casos: {len(runs)}, que cubren los 31 escenarios de la sección 7.2 de la investigación",
        f"- Comando: `{COMMAND}`",
        "",
        "## Chequeos en código",
        "",
        f"**{passed} de {len(runs)} casos pasan ({_percent(passed, len(runs))}).** Cada caso "
        "revisa el camino del turno, los motivos de escalamiento, los pedidos consultados, las "
        "citas, frases obligatorias y prohibidas, el idioma y si se llamó al modelo.",
        "",
        "| Categoría | Casos | Pasan | % |",
        "|---|---|---|---|",
    ]
    by_category: dict[str, list[CaseRun]] = defaultdict(list)
    for run in runs:
        by_category[run.case.category].append(run)
    for category, group in by_category.items():
        ok = sum(run.passed for run in group)
        name = CATEGORY_NAMES.get(category, category)
        lines.append(f"| {name} | {len(group)} | {ok} | {_percent(ok, len(group))} |")
    cards = "sí (falla)" if report.records_have_cards else "no"
    lines += ["", f"Números de tarjeta en los registros de handoff y trazas: {cards}.", ""]

    graded = [run for run in runs if run.verdict]
    if graded:
        lines += [
            "## Juez (Claude con las rúbricas de los evaluadores de Foundry)",
            "",
            f"{len(graded)} casos en los que el modelo redactó parte de la respuesta. Escala de "
            f"1 a 5; pasa con {PASS_SCORE} o más, como en Foundry.",
            "",
            "| Métrica | Promedio | Pasan |",
            "|---|---|---|",
        ]
        for metric in METRICS:
            scores = [run.verdict.scores[metric] for run in graded if run.verdict]
            ok = sum(score >= PASS_SCORE for score in scores)
            lines.append(
                f"| {METRIC_NAMES[metric]} | {statistics.mean(scores):.2f} | {ok}/{len(scores)} |"
            )
        lines.append("")
    errors = [run for run in runs if run.judge_error]
    if errors:
        lines += [f"Sin veredicto del juez: {', '.join(run.case.id for run in errors)}.", ""]

    with_model = [run.latency_ms for run in runs if run.result.llm_requests]
    judge_usage = report.judge_usage()
    lines += [
        "## Costo y latencia",
        "",
        f"- Agente: {sum(r.usage.input_tokens for r in runs):,} tokens de entrada y "
        f"{sum(r.usage.output_tokens for r in runs):,} de salida, USD {report.agent_cost():.4f}.",
        f"- Juez: {judge_usage.input_tokens:,} tokens de entrada y "
        f"{judge_usage.output_tokens:,} de salida, "
        f"USD {cost_usd(report.judge_model or '', judge_usage):.4f}.",
    ]
    if with_model:
        lines.append(
            f"- Turnos con modelo: mediana {statistics.median(with_model) / 1000:.1f} s, "
            f"máximo {max(with_model) / 1000:.1f} s. Las respuestas fijas tardan milisegundos."
        )
    lines.append("")

    failed = [run for run in runs if not run.passed]
    low = [run for run in graded if run.verdict and not run.verdict.passed]
    if failed or low:
        lines += ["## Casos con problemas", ""]
        for run in failed:
            lines.append(f"- `{run.case.id}`: {'; '.join(run.problems)}.")
        for run in low:
            assert run.verdict
            for metric in METRICS:
                if run.verdict.scores[metric] < PASS_SCORE:
                    lines.append(
                        f"- `{run.case.id}`, {METRIC_NAMES[metric].lower()} "
                        f"{run.verdict.scores[metric]}: {run.verdict.reasons[metric]}"
                    )
        lines.append("")

    lines += [
        "## Detalle",
        "",
        "| Caso | Escenario | Camino | Chequeos | Juez (I/T/A/G) |",
        "|---|---|---|---|---|",
    ]
    for run in runs:
        scores = "/".join(str(run.verdict.scores[m]) for m in METRICS) if run.verdict else "-"
        status = "pasa" if run.passed else "falla"
        lines.append(
            f"| `{run.case.id}` | {run.case.scenario} | {run.result.path} | {status} | {scores} |"
        )
    return "\n".join(lines) + "\n"


def to_json(report: Report) -> dict[str, Any]:
    return {
        "started": report.started.isoformat(),
        "agent_model": report.settings.llm_model,
        "embedding_model": report.settings.embedding_model,
        "judge_model": _judge_model(report),
        "passed": sum(run.passed for run in report.runs),
        "cases": len(report.runs),
        "records_have_cards": report.records_have_cards,
        "agent_cost_usd": round(report.agent_cost(), 6),
        "judge_cost_usd": round(cost_usd(report.judge_model or "", report.judge_usage()), 6),
        "runs": [
            {
                "id": run.case.id,
                "scenario": run.case.scenario,
                "category": run.case.category,
                "turns": list(run.case.turns),
                "path": run.result.path,
                "answer": run.result.answer,
                "reasons": [reason.value for reason in run.result.reasons],
                "retrieved": [[hit.doc_id, round(hit.score, 4)] for hit in run.result.retrieved],
                "lookups": list(run.result.lookups),
                "llm_requests": run.result.llm_requests,
                "input_tokens": run.usage.input_tokens,
                "output_tokens": run.usage.output_tokens,
                "latency_ms": round(run.latency_ms, 1),
                "passed": run.passed,
                "problems": run.problems,
                "validation_problems": list(run.result.validation_problems),
                "judge": (
                    {"scores": run.verdict.scores, "reasons": run.verdict.reasons}
                    if run.verdict
                    else None
                ),
                "judge_error": run.judge_error,
            }
            for run in report.runs
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evalúa a Morpho con el golden set.")
    parser.add_argument("--no-judge", action="store_true", help="solo los chequeos en código")
    parser.add_argument("--case", action="append", help="correr solo este caso (repetible)")
    parser.add_argument("--out", type=Path, default=REPORT_DIR, help="carpeta del reporte")
    args = parser.parse_args(argv)

    settings = load_settings()
    if not settings.has_api_key:
        print("Falta ANTHROPIC_API_KEY: agrégala a .env (ver .env.example).", file=sys.stderr)
        return 2
    cases = load_golden()
    if args.case:
        cases = [case for case in cases if case.id in set(args.case)]
    var_dir = settings.var_dir / "eval"
    var_dir.mkdir(parents=True, exist_ok=True)
    for old in var_dir.glob("*.jsonl"):
        old.unlink()  # a fresh run, so the card check only sees these cases

    from anthropic import Anthropic

    from morpho.app import build_agent

    agent = build_agent(dataclasses.replace(settings, var_dir=var_dir))
    judge = (
        None
        if args.no_judge
        else ClaudeJudge(Anthropic(api_key=settings.anthropic_api_key), settings.judge_model)
    )
    runs = []
    for case in cases:
        run = run_case(agent, case)
        if judge:
            grade(judge, run)
        runs.append(run)
        mark = "ok " if run.passed else "MAL"
        scores = "/".join(str(run.verdict.scores[m]) for m in METRICS) if run.verdict else ""
        print(f"{mark} {case.id:<28} {run.result.path:<20} {scores} {'; '.join(run.problems)}")

    report = Report(runs, settings, records_have_cards(var_dir), judge.model if judge else None)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text(render_markdown(report))
    (args.out / "report.json").write_text(
        json.dumps(to_json(report), ensure_ascii=False, indent=1) + "\n"
    )
    passed = sum(run.passed for run in runs)
    print(f"\n{passed}/{len(runs)} casos pasan. Reporte en {args.out / 'report.md'}.")
    return 0 if passed == len(runs) and not report.records_have_cards else 1


def _judge_model(report: Report) -> str:
    return report.judge_model or "sin juez (--no-judge)"


def _percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "-"


if __name__ == "__main__":
    raise SystemExit(main())
