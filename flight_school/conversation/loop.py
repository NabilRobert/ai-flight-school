"""The conversation loop: an Inspect solver where the customer and the
agent take turns until the customer says a stop marker or the turn limit
is reached (ADR-007, following τ²-bench's user-simulator loop).

The loop owns the shop: the agent only sees `AgentTools`, and every call
it makes is recorded by the shop, never reported by the agent. Errors are
never caught here: an agent or customer that raises makes the trial an
error, so a broken run can't pass (spike 4's worry about τ²'s loop).
"""

from dataclasses import asdict
from typing import Any

from inspect_ai.model import ChatMessageAssistant, ChatMessageUser
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import LimitExceededError, StoreModel
from pydantic import Field

from flight_school.conversation.agent import AgentFactory, AgentTools, Message
from flight_school.conversation.scenario import Row, Scenario, stop_marker_in, world_rows
from flight_school.log import AgentReply, ConversationLog, ToolCall
from flight_school.world.schema import World
from flight_school.world.shop import FakeShop

# The most replies the agent gets in one conversation. The cost model
# assumes about 8 turns; 10 leaves room for a customer who repeats
# themselves, and a scenario that needs more says so.
DEFAULT_TURN_LIMIT = 10


class ConversationRecord(StoreModel):
    """What the loop hands the scorer, kept in the sample's store so it
    is also in the Inspect log."""

    customer_id: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    replies: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    stop_marker: str | None = None
    final_rows: list[Row] = Field(default_factory=list[Row])

    def to_log(self) -> ConversationLog:
        return ConversationLog(
            customer_id=self.customer_id,
            calls=[ToolCall(**call) for call in self.tool_calls],
            replies=[AgentReply(**reply) for reply in self.replies],
        )


def scenario_of(state: TaskState) -> Scenario:
    return Scenario.model_validate(state.metadata["scenario"])


@solver
def conversation(
    agent_factory: AgentFactory, world: World, turn_limit: int = DEFAULT_TURN_LIMIT
) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:  # noqa: ARG001
        scenario = scenario_of(state)
        shop = FakeShop(world)
        record = state.store_as(ConversationRecord)
        record.customer_id = scenario.customer_id
        # The sample's input is only a label; the loop builds the chat.
        state.messages = []
        try:
            await take_turns(state, scenario, shop, agent_factory, turn_limit)
        finally:
            # Also on the turn limit, so the scorer sees the calls made.
            record.tool_calls = [asdict(call) for call in shop.calls]
            record.final_rows = world_rows(shop.world)
        return state

    return solve


async def take_turns(
    state: TaskState,
    scenario: Scenario,
    shop: FakeShop,
    agent_factory: AgentFactory,
    turn_limit: int,
) -> None:
    tools = AgentTools(shop)
    reply = agent_factory(tools)
    record = state.store_as(ConversationRecord)
    chat: list[Message] = []
    for line in scenario.script:
        # Only the customer can end the conversation: an agent that types
        # a stop marker is just saying words (ADR-015, X5).
        marker = stop_marker_in(line)
        if marker is not None:
            record.stop_marker = marker
            return
        if tools.turn >= turn_limit:
            break
        tools.turn += 1
        chat.append(Message("customer", line))
        state.messages.append(ChatMessageUser(content=line))
        text = await reply(list(chat))
        chat.append(Message("agent", text))
        state.messages.append(ChatMessageAssistant(content=text))
        record.replies = [*record.replies, asdict(AgentReply(tools.turn, text))]
    # Reached on the turn limit, and on a script that ran out without a
    # marker: either way the conversation never ended, so it can't pass.
    # Inspect records the limit and still scores the sample; the harness
    # then counts it as a fail (its `stop_reason` rule).
    raise LimitExceededError(
        "turn",
        value=tools.turn,
        limit=turn_limit,
        message=f"the customer hadn't ended the conversation after {tools.turn} turns",
    )
