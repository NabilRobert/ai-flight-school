"""The observer adapter (ADR-009, A3): for an agent that keeps its own
tools behind mcp-gateway, such as Juku's Shiori.

Each turn is posted to the agent's chat endpoint as an
`ObservedChatRequest`, and the calls it made meanwhile are read from the
gateway's audit log, so they are still observed, never self-reported.
The log has no conversation id, so turns run one at a time across the
whole run: every line written while a turn is in flight belongs to that
turn. The gateway must serve only this run, or another client's calls
under the same caller would be counted too.

What this can't see: the tools' output (the log keeps only its hash), and
the agent's own data, so task success only says the conversation ended.
"""

import asyncio
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from flight_school.conversation.agent import AgentFactory, AgentTools, Message, Reply
from flight_school.http.adapter import post_turn
from flight_school.http.contract import ChatMessage, ObservedChatRequest
from flight_school.observer.audit_log import observed_calls, read_from


@dataclass(frozen=True)
class Observer:
    """Where the gateway writes its audit log, and the gateway caller id
    (the key's name) the agent's calls are logged under."""

    audit_log: Path
    caller: str


def observed_agent(agent_url: str, observer: Observer) -> AgentFactory:
    one_turn_at_a_time = asyncio.Lock()

    def make(tools: AgentTools) -> Reply:
        conversation_id = secrets.token_urlsafe(8)

        async def reply(chat: Sequence[Message]) -> str:
            request = ObservedChatRequest(
                conversation_id=conversation_id,
                messages=[ChatMessage(speaker=m.speaker, text=m.text) for m in chat],
                signed_in_as=tools.signed_in_as,
            )
            async with one_turn_at_a_time:
                # A missing log raises here or below, so the trial is an
                # error: read as empty, a wrong path would show no calls.
                start = observer.audit_log.stat().st_size
                text = await post_turn(agent_url, request)
                lines, _ = read_from(observer.audit_log, start)
            tools.record_observed(observed_calls(lines, observer.caller, tools.turn))
            return text

        return reply

    return make
