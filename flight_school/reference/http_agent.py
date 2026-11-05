"""The reference agent served over HTTP (A2): the same `ReferenceAgent`,
behind the chat endpoint contract, calling its tools through an MCP
client on the `tools_url` each request names.

It is what `flightschool run --agent-url` is tested against: the same
variant must get the same verdict over HTTP as in process. Run one with
`flightschool serve-reference --variant correct`.
"""

import json

import mcp.types as types
from fastapi import FastAPI
from mcp import Client

from flight_school.http.contract import ChatRequest, ChatResponse
from flight_school.log import ToolCall
from flight_school.reference.agent import Bug, ReferenceAgent, ToolCaller
from flight_school.conversation.agent import Message

CHAT_PATH = "/chat"


def over_mcp(tools_url: str) -> ToolCaller:
    """Each call opens its own MCP client: the tool server is stateless."""

    async def call(tool: str, arguments: dict[str, object]) -> ToolCall:
        async with Client(tools_url) as client:
            result = await client.call_tool(tool, arguments)
        return as_tool_call(tool, arguments, result)

    return call


def as_tool_call(tool: str, arguments: dict[str, object], result: types.CallToolResult) -> ToolCall:
    """What the agent learns from a call. The turn is the server's
    business; the shop's own record has it."""
    text = " ".join(part.text for part in result.content if isinstance(part, types.TextContent))
    if result.is_error:
        return ToolCall(0, tool, arguments, succeeded=False, error=text)
    structured = result.structured_content
    return ToolCall(0, tool, arguments, succeeded=True, result=structured or json.loads(text))


def reference_app(bug: Bug | None = None) -> FastAPI:
    """One agent per conversation id, so it remembers the conversation the
    way the in-process factory's agent does."""
    app = FastAPI(title="Flight School reference agent")
    agents: dict[str, ReferenceAgent] = {}

    async def chat(request: ChatRequest) -> ChatResponse:
        agent = agents.get(request.conversation_id)
        if agent is None:
            agent = ReferenceAgent(over_mcp(request.tools_url), bug)
            agents[request.conversation_id] = agent
        messages = [Message(m.speaker, m.text) for m in request.messages]
        return ChatResponse(reply=await agent.reply(messages))

    app.add_api_route(CHAT_PATH, chat, methods=["POST"])
    return app
