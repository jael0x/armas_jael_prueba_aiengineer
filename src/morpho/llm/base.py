"""Provider-neutral port to the language model.

The adapter runs the tool loop itself and calls back `run_tool`, so the agent never sees
provider objects. Swapping Claude for Claude on Foundry or another provider touches only
`llm/`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    """JSON Schema of the arguments; adapters send it with strict validation."""


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cached_tokens + other.cached_tokens,
        )


@dataclass(frozen=True)
class Completion:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = Usage()
    requests: int = 1
    """API requests made, one per tool round plus the final answer."""
    hit_tool_limit: bool = False
    stop_reason: str = "end_turn"
    """Why the last request stopped: `end_turn`, `tool_use`, `max_tokens`, `refusal`, ..."""


ToolRunner = Callable[[ToolCall], dict[str, Any]]


class LLMClient(Protocol):
    model: str

    def complete(
        self,
        *,
        instructions: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        run_tool: ToolRunner,
        max_tool_rounds: int,
    ) -> Completion:
        """Answer the last user message, calling tools for at most `max_tool_rounds` rounds."""
        ...
