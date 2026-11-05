"""The fake shop's tools as an MCP server (ADR-009, adapter A2), built on
the official MCP SDK's low-level server.

One server runs for the whole run. Each conversation registers its
`AgentTools` and gets its own URL, `.../mcp?conversation=<token>`; a call
on that URL acts on that conversation's shop only, and is recorded by the
shop like an in-process call. The token is random, so one conversation
can't reach another's shop by guessing. Stateless JSON mode: every call is
a single HTTP request, with no MCP session to keep alive.
"""

import json
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import mcp.types as types
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server

from flight_school.conversation.agent import AgentTools
from flight_school.http.serving import serve_in_thread
from flight_school.world.shop import SHOP_TOOLS

MCP_PATH = "/mcp"
CONVERSATION_PARAMETER = "conversation"


class ToolServer:
    """The registry of live conversations, and the MCP server over it."""

    def __init__(self) -> None:
        self.base_url = ""
        self._tools_by_token: dict[str, AgentTools] = {}
        self.server = Server("flight-school-shop", on_list_tools=list_tools, on_call_tool=self.call)

    def register(self, tools: AgentTools) -> str:
        """The URL this conversation's agent calls its tools on."""
        token = secrets.token_urlsafe(16)
        self._tools_by_token[token] = tools
        return f"{self.base_url}{MCP_PATH}?{CONVERSATION_PARAMETER}={token}"

    async def call(
        self, context: ServerRequestContext[Any, Any], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        request = context.request
        token = request.query_params.get(CONVERSATION_PARAMETER) if request is not None else None
        tools = self._tools_by_token.get(token or "")
        if tools is None:
            return error_result("unknown conversation: call the tools_url you were given")
        call = tools.call(params.name, dict(params.arguments or {}))
        if not call.succeeded:
            return error_result(call.error or "the call failed")
        result = call.result or {}
        return types.CallToolResult(
            content=[types.TextContent(text=json.dumps(result))], structured_content=result
        )


async def list_tools(
    context: ServerRequestContext[Any, Any],  # noqa: ARG001
    params: types.PaginatedRequestParams | None,  # noqa: ARG001
) -> types.ListToolsResult:
    tools = [
        types.Tool(name=spec.name, input_schema=spec.arguments.model_json_schema())
        for spec in SHOP_TOOLS.values()
    ]
    return types.ListToolsResult(tools=tools)


def error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(text=message)], is_error=True)


@contextmanager
def running_tool_server() -> Iterator[ToolServer]:
    """A tool server, listening on a free local port while the block runs."""
    tool_server = ToolServer()
    app = tool_server.server.streamable_http_app(stateless_http=True, json_response=True)
    with serve_in_thread(app) as base_url:
        tool_server.base_url = base_url
        yield tool_server
