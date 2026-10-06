"""The Claude Messages API adapter, against a fake client that records every request."""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import pytest

from morpho.llm.anthropic_client import MAX_TOKENS, AnthropicClient
from morpho.llm.base import Completion, LLMUnavailableError, Message, ToolCall
from morpho.prompts import ORDER_TOOL
from morpho.tools.orders import consultar_estado_pedido


def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use(block_id: str, order_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="tool_use", id=block_id, name=ORDER_TOOL.name, input={"order_id": order_id}
    )


def _response(
    content: list[SimpleNamespace], stop_reason: str = "end_turn", cache_read: int = 0
) -> SimpleNamespace:
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=20,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=None,
    )
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage)


def _wants_tool(*order_ids: str) -> SimpleNamespace:
    blocks = [_tool_use(f"toolu_{i}", order_id) for i, order_id in enumerate(order_ids)]
    return _response(blocks, stop_reason="tool_use")


class _FakeMessages:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        # The adapter keeps appending to the same history list, so keep a copy per request.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def _client(
    responses: list[SimpleNamespace], effort: str | None = None
) -> tuple[AnthropicClient, _FakeMessages]:
    fake = _FakeMessages(responses)
    return AnthropicClient(SimpleNamespace(messages=fake), "claude-haiku-4-5", effort), fake


def _complete(client: AnthropicClient, calls: list[ToolCall], max_rounds: int = 3) -> Completion:
    def run_tool(call: ToolCall) -> dict[str, Any]:
        calls.append(call)
        return consultar_estado_pedido(call.arguments["order_id"])

    return client.complete(
        instructions="Reglas",
        messages=[Message("user", "¿Cómo va ORD-1001?")],
        tools=[ORDER_TOOL],
        run_tool=run_tool,
        max_tool_rounds=max_rounds,
    )


def test_tool_result_is_sent_back_with_its_tool_use_id() -> None:
    client, fake = _client(
        [
            _response([_text("Lo reviso."), _tool_use("toolu_1", "ORD-1001")], "tool_use", 40),
            _response([_text("Tu pedido ORD-1001 está En tránsito.")]),
        ]
    )
    calls: list[ToolCall] = []
    completion = _complete(client, calls)

    assert completion.text == "Tu pedido ORD-1001 está En tránsito."
    assert completion.stop_reason == "end_turn"
    assert calls == [ToolCall(ORDER_TOOL.name, {"order_id": "ORD-1001"})]
    assert completion.requests == 2
    assert (completion.usage.input_tokens, completion.usage.cached_tokens) == (240, 40)

    _, assistant, results = fake.requests[1]["messages"]
    assert assistant["role"] == "assistant"
    assert assistant["content"][1].id == "toolu_1"
    assert results["role"] == "user"
    (result,) = results["content"]
    assert (result["type"], result["tool_use_id"]) == ("tool_result", "toolu_1")
    assert json.loads(result["content"])["estado"] == "En tránsito"


def test_parallel_tool_calls_are_answered_in_one_message() -> None:
    client, fake = _client([_wants_tool("ORD-1001", "ORD-1004"), _response([_text("Listo.")])])
    calls: list[ToolCall] = []
    _complete(client, calls)
    results = fake.requests[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_0", "toolu_1"]
    assert len(calls) == 2


def test_request_uses_strict_tools_and_the_system_prompt() -> None:
    client, fake = _client([_response([_text("Hola")])])
    _complete(client, [])
    request = fake.requests[0]
    assert request["model"] == "claude-haiku-4-5"
    assert request["system"] == "Reglas"
    assert request["max_tokens"] == MAX_TOKENS
    assert request["messages"] == [{"role": "user", "content": "¿Cómo va ORD-1001?"}]
    tool = request["tools"][0]
    assert (tool["name"], tool["strict"]) == ("consultar_estado_pedido", True)
    assert tool["input_schema"] == ORDER_TOOL.parameters
    assert "output_config" not in request  # Claude Haiku 4.5 rejects the effort parameter


def test_effort_is_sent_only_when_configured() -> None:
    client, fake = _client([_response([_text("Hola")])], effort="low")
    _complete(client, [])
    assert fake.requests[0]["output_config"] == {"effort": "low"}


def test_tool_rounds_stop_at_the_limit() -> None:
    client, fake = _client([_wants_tool("ORD-1001") for _ in range(5)])
    calls: list[ToolCall] = []
    completion = _complete(client, calls, max_rounds=2)
    assert len(calls) == 2
    assert len(fake.requests) == 3
    assert completion.hit_tool_limit is True
    assert completion.stop_reason == "tool_use"


def test_refusal_is_reported_with_its_stop_reason() -> None:
    client, _ = _client([_response([], stop_reason="refusal")])
    completion = _complete(client, [])
    assert (completion.text, completion.stop_reason) == ("", "refusal")
    assert completion.hit_tool_limit is False


def test_api_errors_become_a_provider_neutral_error() -> None:
    class _Failing:
        def create(self, **_: Any) -> SimpleNamespace:
            raise anthropic.AnthropicError("overloaded")

    client = AnthropicClient(SimpleNamespace(messages=_Failing()), "claude-haiku-4-5")
    with pytest.raises(LLMUnavailableError, match="overloaded"):
        _complete(client, [])
