"""Claude as judge, with the four rubrics of the Foundry agent evaluators.

The prompt-based evaluators of `azure-ai-evaluation` need an OpenAI or Azure OpenAI judge. With
only a Claude key, the same rubrics (intent resolution, tool call accuracy, task adherence and
groundedness) are graded here from 1 to 5; 3 or more passes, as in Foundry. The judge sees what
the agent saw: its rules, the retrieved documents and the tool results.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from morpho.agent import TurnResult
from morpho.knowledge.documents import get_document
from morpho.llm.anthropic_client import usage_from
from morpho.llm.base import Usage
from morpho.prompts import build_instructions

METRICS = ("intent_resolution", "tool_call_accuracy", "task_adherence", "groundedness")
PASS_SCORE = 3
MAX_TOKENS = 4_000

JUDGE_SYSTEM = """Evalúas las respuestas de Morpho, el agente de soporte al cliente de \
TiendaHogar. Recibes las reglas y los documentos que tenía Morpho, los resultados de su \
herramienta, la conversación y la respuesta final. Califica cada métrica de 1 (muy mal) a 5 \
(perfecto):

- intent_resolution: ¿la respuesta entiende y atiende lo que el cliente quería? Derivar a un \
asesor humano cuando las reglas lo exigen cuenta como atenderlo.
- tool_call_accuracy: ¿las llamadas a consultar_estado_pedido fueron correctas y necesarias \
(el ID que dio el cliente, ninguna llamada si no dio un ID)? Si no hacía falta la herramienta y \
no se llamó, 5.
- task_adherence: ¿la respuesta cumple las reglas de Morpho? Aprobar reembolsos, resolver un \
tema que debía ir a un asesor o responder en otro idioma baja el puntaje.
- groundedness: ¿cada dato sale de los documentos o de los resultados de la herramienta? \
Inventar plazos, precios, fechas, motivos o pasos baja el puntaje.

Morpho agrega textos fijos aprobados: la derivación a un asesor con una referencia ESC-..., el \
consejo de no compartir números de tarjeta, el rechazo a cambiar sus instrucciones y las \
preguntas por el ID del pedido o por el monto en USD. Esos textos cuentan como fundamentados y \
correctos.

Para cada métrica escribe primero un razonamiento breve y después el puntaje."""

_METRIC_SCHEMA = {
    "type": "object",
    "properties": {
        "razonamiento": {"type": "string"},
        "puntaje": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    },
    "required": ["razonamiento", "puntaje"],
    "additionalProperties": False,
}
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {metric: _METRIC_SCHEMA for metric in METRICS},
    "required": list(METRICS),
    "additionalProperties": False,
}


class JudgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Verdict:
    scores: dict[str, int]
    reasons: dict[str, str]
    usage: Usage

    @property
    def passed(self) -> bool:
        return all(score >= PASS_SCORE for score in self.scores.values())


class ClaudeJudge:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self.model = model

    def grade(self, turns: Sequence[str], result: TurnResult) -> Verdict:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": judge_input(turns, result)}],
            output_config={"format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        if response.stop_reason != "end_turn" or not text:
            raise JudgeError(f"the judge stopped with {response.stop_reason!r}")
        data = json.loads(text)
        return Verdict(
            scores={metric: data[metric]["puntaje"] for metric in METRICS},
            reasons={metric: data[metric]["razonamiento"] for metric in METRICS},
            usage=usage_from(response.usage),
        )


def judge_input(turns: Sequence[str], result: TurnResult) -> str:
    # Fixed replies cite documents too (an escalation cites Doc5), so the judge gets those as well.
    doc_ids = dict.fromkeys([*(hit.doc_id for hit in result.retrieved), *result.citations])
    documents = [get_document(doc_id) for doc_id in doc_ids]
    conversation = "\n".join(f"Cliente: {turn}" for turn in turns)
    tool_results = json.dumps(list(result.lookups), ensure_ascii=False)
    return (
        f"<reglas_y_documentos_de_morpho>\n{build_instructions(result.language, documents)}\n"
        "</reglas_y_documentos_de_morpho>\n\n"
        f"<resultados_de_herramienta>\n{tool_results}\n</resultados_de_herramienta>\n\n"
        f"<conversacion>\n{conversation}\n</conversacion>\n\n"
        f"<respuesta_de_morpho>\n{result.answer}\n</respuesta_de_morpho>"
    )
