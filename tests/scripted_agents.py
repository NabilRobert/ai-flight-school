"""Agents for the loop's tests: each makes fixed calls on fixed turns.

Slice 3 builds the real reference agents; these only drive the loop.
"""

from collections.abc import Mapping, Sequence

from flight_school.conversation.agent import AgentFactory, AgentTools, Message, Reply

CallsByTurn = Mapping[int, Sequence[tuple[str, Mapping[str, object]]]]


def scripted_agent(calls_by_turn: CallsByTurn, says: str = "Done.") -> AgentFactory:
    """On customer turn N, make `calls_by_turn[N]`; always answer `says`."""

    def make(tools: AgentTools) -> Reply:
        async def reply(chat: Sequence[Message]) -> str:
            turn = sum(1 for message in chat if message.speaker == "customer")
            for tool, arguments in calls_by_turn.get(turn, []):
                tools.call(tool, dict(arguments))
            return says

        return reply

    return make


def crashing_agent(tools: AgentTools) -> Reply:  # noqa: ARG001
    async def reply(chat: Sequence[Message]) -> str:  # noqa: ARG001
        raise RuntimeError("the agent fell over")

    return reply


REFUNDS_O1_AFTER_VERIFYING: CallsByTurn = {
    2: [
        ("verify_identity", {"customer_id": "c1", "email": "aiko@example.com"}),
        ("issue_refund", {"order_id": "o1", "amount_cents": 4500}),
    ]
}
