"""OpenAI Responses API adapter with function calling.

The same SDK reaches Azure OpenAI / Microsoft Foundry by setting `OPENAI_BASE_URL` to the v1
endpoint. Requests are not stored on OpenAI's side (`store=False`); reasoning items come back
encrypted and are returned on the next tool round, as the API expects for reasoning models.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from morpho.llm.base import Completion, Message, ToolCall, ToolRunner, ToolSpec, Usage


class OpenAIClient:
    def __init__(self, client: Any, model: str, reasoning_effort: str = "low") -> None:
        self._client = client
        self.model = model
        self.reasoning_effort = reasoning_effort

    def complete(
        self,
        *,
        instructions: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        run_tool: ToolRunner,
        max_tool_rounds: int,
    ) -> Completion:
        tool_params = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "strict": True,
            }
            for tool in tools
        ]
        items: list[dict[str, Any]] = [{"role": m.role, "content": m.text} for m in messages]
        usage, made = Usage(), []
        for round_number in range(max_tool_rounds + 1):
            response = self._client.responses.create(
                model=self.model,
                instructions=instructions,
                input=items,
                tools=tool_params,
                reasoning={"effort": self.reasoning_effort},
                store=False,
                include=["reasoning.encrypted_content"],
            )
            usage += _usage(response.usage)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls or round_number == max_tool_rounds:
                return Completion(
                    text=response.output_text or "",
                    tool_calls=tuple(made),
                    usage=usage,
                    requests=round_number + 1,
                    hit_tool_limit=bool(calls),
                )
            for item in response.output:
                if item.type == "reasoning":
                    items.append(item.model_dump(by_alias=True, exclude_none=True))
            for call in calls:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                )
                tool_call = ToolCall(call.name, _arguments(call.arguments))
                made.append(tool_call)
                result = run_tool(tool_call)
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )
        raise AssertionError("unreachable: the loop always returns on its last round")


def _arguments(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _usage(raw: Any) -> Usage:
    if raw is None:
        return Usage()
    details = getattr(raw, "input_tokens_details", None)
    return Usage(
        input_tokens=raw.input_tokens,
        output_tokens=raw.output_tokens,
        cached_tokens=getattr(details, "cached_tokens", 0) or 0,
    )
