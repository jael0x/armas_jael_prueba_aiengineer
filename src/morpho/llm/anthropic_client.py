"""Claude adapter: the Messages API with a manual tool-use loop.

The loop is written by hand instead of using the SDK's beta tool runner so this module owns the
round cap and hands each call to the agent's `run_tool`. The same code reaches Claude on
Microsoft Foundry when the client is `anthropic.AnthropicFoundry(api_key=..., resource=...)`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from morpho.llm.base import Completion, Message, ToolCall, ToolRunner, ToolSpec, Usage

MAX_TOKENS = 16_000


class AnthropicClient:
    def __init__(self, client: Any, model: str, effort: str | None = None) -> None:
        self._client = client
        self.model = model
        self.effort = effort

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
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
                "strict": True,
            }
            for tool in tools
        ]
        history: list[dict[str, Any]] = [{"role": m.role, "content": m.text} for m in messages]
        options: dict[str, Any] = {"output_config": {"effort": self.effort}} if self.effort else {}
        usage, made = Usage(), []
        for round_number in range(max_tool_rounds + 1):
            response = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=instructions,
                messages=history,
                tools=tool_params,
                **options,
            )
            usage += usage_from(response.usage)
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            wants_tools = response.stop_reason == "tool_use" and bool(tool_uses)
            if not wants_tools or round_number == max_tool_rounds:
                return Completion(
                    text="".join(b.text for b in response.content if b.type == "text"),
                    tool_calls=tuple(made),
                    usage=usage,
                    requests=round_number + 1,
                    hit_tool_limit=wants_tools,
                    stop_reason=response.stop_reason or "",
                )
            history.append({"role": "assistant", "content": response.content})
            results = []
            for block in tool_uses:
                call = ToolCall(block.name, block.input if isinstance(block.input, dict) else {})
                made.append(call)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(run_tool(call), ensure_ascii=False),
                    }
                )
            history.append({"role": "user", "content": results})  # every result in one message
        raise AssertionError("unreachable: the loop always returns on its last round")


def usage_from(raw: Any) -> Usage:
    """Claude usage as a `Usage`: input counts uncached tokens plus cache reads and writes."""
    if raw is None:
        return Usage()
    cache_read = getattr(raw, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(raw, "cache_creation_input_tokens", 0) or 0
    return Usage(
        input_tokens=raw.input_tokens + cache_read + cache_write,
        output_tokens=raw.output_tokens,
        cached_tokens=cache_read,
    )
