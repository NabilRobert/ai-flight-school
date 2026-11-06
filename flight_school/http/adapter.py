"""The HTTP adapter (ADR-009, A2): an agent factory that talks to a
team's agent over its chat endpoint, with its tools on the MCP server.

To the loop it looks like any in-process agent, so the same scorer and
gate run. The agent's URL comes only from the command line (X4): no
rule or scenario file can point it anywhere else. A key for the agent's
endpoint comes only from the environment (X1) and goes only in the
request header, never in a record.
"""

import os
import secrets
from collections.abc import Sequence

import httpx

from flight_school.conversation.agent import AgentFactory, AgentTools, Message, Reply
from flight_school.http.contract import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ObservedChatRequest,
)
from flight_school.http.tool_server import ToolServer

# Sent as `Authorization: Bearer <key>` when set, for an endpoint that
# needs one.
AGENT_KEY_VARIABLE = "FLIGHTSCHOOL_AGENT_KEY"
# A model-backed agent takes about 10 s a turn (plan.py); a reply slower
# than this is an error, and the trial is inconclusive, never a pass.
REPLY_TIMEOUT_SECONDS = 60.0


def http_agent(agent_url: str, tool_server: ToolServer) -> AgentFactory:
    def make(tools: AgentTools) -> Reply:
        conversation_id = secrets.token_urlsafe(8)
        tools_url = tool_server.register(tools)

        async def reply(chat: Sequence[Message]) -> str:
            request = ChatRequest(
                conversation_id=conversation_id,
                messages=[ChatMessage(speaker=m.speaker, text=m.text) for m in chat],
                tools_url=tools_url,
            )
            return await post_turn(agent_url, request)

        return reply

    return make


async def post_turn(agent_url: str, request: ChatRequest | ObservedChatRequest) -> str:
    """One turn. A refused request, a non-2xx answer or a reply that isn't
    a `ChatResponse` raises, so the trial is an error."""
    async with httpx.AsyncClient(timeout=REPLY_TIMEOUT_SECONDS) as client:
        response = await client.post(agent_url, json=request.model_dump(), headers=auth_headers())
    response.raise_for_status()
    return ChatResponse.model_validate_json(response.content).reply


def auth_headers() -> dict[str, str]:
    key = os.environ.get(AGENT_KEY_VARIABLE)
    return {"Authorization": f"Bearer {key}"} if key else {}
