"""The conversation loop: an Inspect solver where the customer and the
agent take turns until the customer says a stop marker or the turn limit
is reached (ADR-007, following τ²-bench's user-simulator loop).

The customer is scripted or a model (`customer.py`); either way, its
lines are recorded and checked for breaking character (`character.py`).
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
from flight_school.conversation.character import character_breaks
from flight_school.conversation.customer import (
    Customer,
    customer_seed,
    model_customer,
    scripted_customer,
)
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
    customer_seed: int | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    replies: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    customer_lines: list[str] = Field(default_factory=list[str])
    character_breaks: list[str] = Field(default_factory=list[str])
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
    agent_factory: AgentFactory,
    world: World,
    turn_limit: int = DEFAULT_TURN_LIMIT,
    has_model_customer: bool = False,
) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:  # noqa: ARG001
        scenario = scenario_of(state)
        record = state.store_as(ConversationRecord)
        record.customer_id = scenario.customer_id
        customer = scripted_customer(scenario)
        if has_model_customer:
            record.customer_seed = customer_seed(scenario.id, state.epoch)
            customer = model_customer(scenario, record.customer_seed)
        shop = FakeShop(world)
        # The sample's input is only a label; the loop builds the chat.
        state.messages = []
        tools = AgentTools(shop, signed_in_as=scenario.customer_id)
        try:
            await take_turns(state, customer, tools, agent_factory, turn_limit)
        finally:
            # Also on the turn limit, so the scorer sees the calls made.
            record.tool_calls = [asdict(call) for call in shop.calls]
            record.final_rows = world_rows(shop.world)
            record.character_breaks = character_breaks(scenario, record.customer_lines)
        return state

    return solve


async def take_turns(
    state: TaskState,
    customer: Customer,
    tools: AgentTools,
    agent_factory: AgentFactory,
    turn_limit: int,
) -> None:
    reply = agent_factory(tools)
    record = state.store_as(ConversationRecord)
    chat: list[Message] = []
    while True:
        line = await customer(chat)
        record.customer_lines = [*record.customer_lines, line]
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
    # The customer hadn't ended the conversation, so it can't pass.
    # Inspect records the limit and still scores the sample; the harness
    # then counts it as a fail (its `stop_reason` rule).
    raise LimitExceededError(
        "turn",
        value=tools.turn,
        limit=turn_limit,
        message=f"the customer hadn't ended the conversation after {tools.turn} turns",
    )
