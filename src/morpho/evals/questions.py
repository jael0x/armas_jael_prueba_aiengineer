"""Labeled questions used to record the embeddings cache and to calibrate the threshold."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

QUESTIONS_PATH = Path(__file__).with_name("retrieval_questions.json")


@dataclass(frozen=True)
class LabeledQuestion:
    question: str
    expected: tuple[str, ...]
    """Documents that should come first; two ids when the question spans two policies."""


@dataclass(frozen=True)
class QuestionSet:
    in_domain: tuple[LabeledQuestion, ...]
    out_of_domain: tuple[str, ...]

    def all_questions(self) -> list[str]:
        return [q.question for q in self.in_domain] + list(self.out_of_domain)


def load_questions(path: Path = QUESTIONS_PATH) -> QuestionSet:
    data = json.loads(path.read_text())
    return QuestionSet(
        in_domain=tuple(
            LabeledQuestion(item["question"], tuple(item["expected"])) for item in data["in_domain"]
        ),
        out_of_domain=tuple(data["out_of_domain"]),
    )
