"""Calibrates the retrieval threshold τ from the cached vectors (the model never runs).

τ is the midpoint between the lowest best-score of an in-domain question and the highest
best-score of an out-of-domain one. Questions the escalation rules already send to a person
are left out: they never reach retrieval, so they should not move τ.

    uv run python -m morpho.evals.calibrate            # writes retrieval/thresholds.json
    uv run python -m morpho.evals.calibrate --dry-run  # only prints the report
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from morpho.config import load_settings
from morpho.evals.questions import QuestionSet, load_questions
from morpho.guardrails.normalize import normalize
from morpho.guardrails.rules import evaluate
from morpho.retrieval.embedder import CachedEmbedder, EmbeddingCache, MissingEmbeddingError
from morpho.retrieval.retriever import THRESHOLDS_PATH, Retriever, Thresholds

DEFAULT_DELTA = 0.1


@dataclass(frozen=True)
class Calibration:
    tau: float
    separation: float
    """Lowest in-domain best score minus highest out-of-domain one; > 0 means a τ splits them."""
    min_in_domain: float
    max_out_of_domain: float
    top1_correct: int
    top1_total: int


def threshold_between(in_scores: list[float], out_scores: list[float]) -> tuple[float, float]:
    """Return (τ, separation) for the best in-domain and out-of-domain scores."""
    low_in, high_out = min(in_scores), max(out_scores)
    return (low_in + high_out) / 2, low_in - high_out


def calibrate(retriever: Retriever, questions: QuestionSet) -> tuple[Calibration, list[str]]:
    lines, in_scores, out_scores, correct = [], [], [], 0
    for item in questions.in_domain:
        ranked = retriever.rank(item.question)
        top_ids = {hit.doc_id for hit in ranked[: len(item.expected)]}
        ok = top_ids == set(item.expected)
        correct += ok
        escalates = evaluate(normalize(item.question)).escalate
        if not escalates:
            in_scores.append(ranked[0].score)
        note = "escala por regla, no cuenta" if escalates else ""
        mark = "ok " if ok else "MAL"
        lines.append(f"{mark} {ranked[0].score:.3f} {ranked[0].doc_id} {item.question[:60]} {note}")
    for question in questions.out_of_domain:
        best = retriever.rank(question)[0]
        out_scores.append(best.score)
        lines.append(f"out {best.score:.3f} {best.doc_id} {question[:60]}")
    tau, separation = threshold_between(in_scores, out_scores)
    result = Calibration(
        tau=round(tau, 4),
        separation=round(separation, 4),
        min_in_domain=round(min(in_scores), 4),
        max_out_of_domain=round(max(out_scores), 4),
        top1_correct=correct,
        top1_total=len(questions.in_domain),
    )
    return result, lines


def write_thresholds(model: str, result: Calibration, path: Path = THRESHOLDS_PATH) -> None:
    entries = json.loads(path.read_text()) if path.exists() else {}
    entries[model] = {
        "tau": result.tau,
        "delta": DEFAULT_DELTA,
        "separation": result.separation,
        "min_in_domain": result.min_in_domain,
        "max_out_of_domain": result.max_out_of_domain,
        "top1": f"{result.top1_correct}/{result.top1_total}",
        "calibrated_on": date.today().isoformat(),
    }
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate the retrieval threshold τ.")
    parser.add_argument("--dry-run", action="store_true", help="print the report without writing")
    args = parser.parse_args(argv)
    model = load_settings().embedding_model
    embedder = CachedEmbedder(EmbeddingCache(), model)  # cache only: never runs the model
    try:
        retriever = Retriever.over_documents(embedder, Thresholds(tau=0.0))
        result, lines = calibrate(retriever, load_questions())
    except MissingEmbeddingError as exc:
        print(f"No se puede calibrar: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    print(
        f"\n{model}: top-1 {result.top1_correct}/{result.top1_total}, "
        f"mínimo dentro {result.min_in_domain}, máximo fuera {result.max_out_of_domain}, "
        f"separación {result.separation:+}, τ = {result.tau}"
    )
    if result.separation <= 0:
        print("Atención: separación no positiva; ningún τ separa todas las preguntas.")
    if not args.dry_run:
        write_thresholds(model, result)
        print(f"Guardado en {THRESHOLDS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
