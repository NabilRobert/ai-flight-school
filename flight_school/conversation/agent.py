"""The in-process way to plug in an agent (ADR-009, adapter A1).

A team writes a factory: it takes the fake shop's tools and returns the
agent's `reply` function for one conversation. The factory is called
afresh for every conversation, so an agent can keep memory in it without
one conversation leaking into the next. Nothing here imports Inspect: an
agent only needs this module.
"""

import copy
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from flight_school.log import ToolCall
from flight_school.world.shop import FakeShop


@dataclass(frozen=True)
class Message:
    speaker: Literal["customer", "agent"]
    text: str


class AgentTools:
    """What the agent gets: the shop's tools. The loop, not the agent,
    stamps each call with the turn it happened in."""

    def __init__(self, shop: FakeShop) -> None:
        self._shop = shop
        self.turn = 0

    def call(self, tool: str, arguments: dict[str, object]) -> ToolCall:
        """Run one tool. A refused call comes back with `succeeded` False
        and an `error`, as a real backend's error would; it never raises.

        The agent gets a copy: the record's dicts are mutable, and an agent
        that edits what it sent or got back must not rewrite the shop's log."""
        return copy.deepcopy(self._shop.call(self.turn, tool, copy.deepcopy(arguments)))


# The conversation so far, oldest first, ending with the customer's latest
# message; returns what the agent says back.
Reply = Callable[[Sequence[Message]], Awaitable[str]]
AgentFactory = Callable[[AgentTools], Reply]
