"""A scripted stand-in for the language model, used by the offline tests."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from morpho.llm.base import Completion, Message, ToolCall, ToolRunner, ToolSpec, Usage


@dataclass(frozen=True)
class FakeReply:
    text: str | Callable[[list[dict[str, Any]]], str]
    """Final answer, or a function that builds it from the tool results."""
    tool_calls: tuple[ToolCall, ...] = ()
    stop_reason: str = "end_turn"


@dataclass(frozen=True)
class FakeCall:
    instructions: str
    messages: list[Message]
    tools: list[str]


@dataclass
class FakeLLM:
    replies: list[FakeReply | str] = field(default_factory=list)
    model: str = "fake-llm"
    calls: list[FakeCall] = field(default_factory=list)

    def complete(
        self,
        *,
        instructions: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        run_tool: ToolRunner,
        max_tool_rounds: int,
    ) -> Completion:
        self.calls.append(FakeCall(instructions, list(messages), [tool.name for tool in tools]))
        reply = self.replies.pop(0) if self.replies else FakeReply("Respuesta de prueba.")
        if isinstance(reply, str):
            reply = FakeReply(reply)
        made = reply.tool_calls[:max_tool_rounds]
        results = [run_tool(call) for call in made]
        text = reply.text(results) if callable(reply.text) else reply.text
        return Completion(
            text=text,
            tool_calls=made,
            usage=Usage(input_tokens=1000, output_tokens=100),
            requests=len(made) + 1,
            hit_tool_limit=len(reply.tool_calls) > max_tool_rounds,
            stop_reason=reply.stop_reason,
        )
