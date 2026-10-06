"""specs/07-conversacion-por-chat.feature: the chat command."""

import pytest

from morpho import cli
from morpho.agent import ConversationState, TurnResult
from morpho.llm.base import LLMUnavailableError


def test_missing_api_key_is_explained_without_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main() == 2
    captured = capsys.readouterr()
    assert "Falta ANTHROPIC_API_KEY" in captured.err
    assert "Traceback" not in captured.err + captured.out


class _EchoAgent:
    def __init__(self, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.states: list[ConversationState] = []

    def run_turn(self, raw_message: str, state: ConversationState) -> TurnResult:
        self.states.append(state)
        if self.fail_first:
            self.fail_first = False
            raise LLMUnavailableError("APIConnectionError: connection reset")
        return TurnResult(answer=f"eco: {raw_message}", path="answered", language="es")


def _run(agent: _EchoAgent, inputs: list[str]) -> list[str]:
    pending, output = list(inputs), []

    def read(_prompt: str) -> str:
        if not pending:
            raise EOFError
        return pending.pop(0)

    assert cli.chat(agent, read=read, write=output.append) == 0
    return output


def test_chat_keeps_one_conversation_until_the_customer_leaves() -> None:
    agent = _EchoAgent()
    output = _run(agent, ["hola", "¿y los envíos?", "salir"])
    assert output[1:] == ["Morpho: eco: hola", "Morpho: eco: ¿y los envíos?"]
    assert agent.states[0] is agent.states[1]


def test_chat_ends_quietly_on_end_of_input() -> None:
    assert _run(_EchoAgent(), [])[-1] == ""


def test_model_errors_are_reported_and_the_chat_continues() -> None:
    output = _run(_EchoAgent(fail_first=True), ["hola", "hola otra vez"])
    assert "No pude contactar al modelo." in output[1]
    assert output[2] == "Morpho: eco: hola otra vez"
