"""The Responses API adapter, against a fake client that records every request."""

import json
from types import SimpleNamespace
from typing import Any

from morpho.llm.base import Message, ToolCall
from morpho.llm.openai_client import OpenAIClient
from morpho.prompts import ORDER_TOOL
from morpho.tools.orders import consultar_estado_pedido


class _Reasoning:
    type = "reasoning"

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {"type": "reasoning", "id": "rs_1", "encrypted_content": "opaque"}


def _function_call(call_id: str, order_id: str) -> SimpleNamespace:
    arguments = json.dumps({"order_id": order_id})
    return SimpleNamespace(
        type="function_call", call_id=call_id, name=ORDER_TOOL.name, arguments=arguments
    )


def _response(output: list[Any], text: str = "", cached: int = 0) -> SimpleNamespace:
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=20,
        input_tokens_details=SimpleNamespace(cached_tokens=cached),
    )
    return SimpleNamespace(output=output, output_text=text, usage=usage)


class _FakeResponses:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        return self.responses.pop(0)


def _client(responses: list[SimpleNamespace]) -> tuple[OpenAIClient, _FakeResponses]:
    fake = _FakeResponses(responses)
    return OpenAIClient(SimpleNamespace(responses=fake), "gpt-6-luna", "low"), fake


def _complete(client: OpenAIClient, calls: list[ToolCall], max_rounds: int = 3) -> Any:
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


def test_tool_result_is_sent_back_with_its_call_id() -> None:
    client, fake = _client(
        [
            _response([_Reasoning(), _function_call("call_1", "ORD-1001")], cached=40),
            _response([], text="Tu pedido ORD-1001 está En tránsito."),
        ]
    )
    calls: list[ToolCall] = []
    completion = _complete(client, calls)

    assert completion.text == "Tu pedido ORD-1001 está En tránsito."
    assert calls == [ToolCall(ORDER_TOOL.name, {"order_id": "ORD-1001"})]
    assert completion.requests == 2
    assert (completion.usage.input_tokens, completion.usage.cached_tokens) == (200, 40)

    second_input = fake.requests[1]["input"]
    assert second_input[1] == {"type": "reasoning", "id": "rs_1", "encrypted_content": "opaque"}
    assert second_input[2]["type"] == "function_call"
    output = second_input[3]
    assert output["type"] == "function_call_output"
    assert output["call_id"] == "call_1"
    assert json.loads(output["output"])["estado"] == "En tránsito"


def test_request_uses_strict_tools_no_storage_and_the_configured_effort() -> None:
    client, fake = _client([_response([], text="Hola")])
    _complete(client, [])
    request = fake.requests[0]
    assert request["model"] == "gpt-6-luna"
    assert request["store"] is False
    assert request["reasoning"] == {"effort": "low"}
    assert request["tools"][0]["strict"] is True
    assert request["tools"][0]["name"] == "consultar_estado_pedido"


def test_tool_rounds_stop_at_the_limit() -> None:
    always_calls = [_response([_function_call(f"call_{i}", "ORD-1001")]) for i in range(5)]
    client, fake = _client(always_calls)
    calls: list[ToolCall] = []
    completion = _complete(client, calls, max_rounds=2)
    assert len(calls) == 2
    assert len(fake.requests) == 3
    assert completion.hit_tool_limit is True


def test_malformed_tool_arguments_become_an_empty_call() -> None:
    bad = SimpleNamespace(
        type="function_call", call_id="c", name=ORDER_TOOL.name, arguments="{oops"
    )
    client, _ = _client([_response([bad]), _response([], text="¿Me das el ID?")])
    seen: list[ToolCall] = []

    def run_tool(call: ToolCall) -> dict[str, Any]:
        seen.append(call)
        return consultar_estado_pedido(str(call.arguments.get("order_id", "")))

    client.complete(
        instructions="Reglas",
        messages=[Message("user", "x")],
        tools=[ORDER_TOOL],
        run_tool=run_tool,
        max_tool_rounds=3,
    )
    assert seen == [ToolCall(ORDER_TOOL.name, {})]
