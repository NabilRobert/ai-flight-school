"""The record of one conversation: what the agent called and what it said.

The shop writes the tool calls (the agent never reports its own); the
rule checker reads this record and nothing else.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    """One call, as the agent sent it, and whether the shop carried it out."""

    turn: int
    tool: str
    arguments: dict[str, object]
    succeeded: bool
    result: dict[str, object] | None = None
    error: str | None = None


@dataclass(frozen=True)
class AgentReply:
    turn: int
    text: str


@dataclass
class ConversationLog:
    """`customer_id` is who the simulated person really is, whatever they claim."""

    customer_id: str
    calls: list[ToolCall] = field(default_factory=list[ToolCall])
    replies: list[AgentReply] = field(default_factory=list[AgentReply])
