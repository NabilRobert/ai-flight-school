"""The chat endpoint contract (ADR-009, adapter A2): what Flight School
sends a team's agent each turn over HTTP, and what it expects back.

Each turn is one `POST` to the agent's URL with a `ChatRequest` as JSON.
The agent answers with a `ChatResponse`. For its tools, the agent calls
the MCP server at `tools_url` (Streamable HTTP), which serves the fake
shop for this conversation only; the agent must not keep its own tools.
Any language works: this is plain JSON, and MCP has clients for most.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    speaker: Literal["customer", "agent"]
    text: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The same for every turn of one conversation, and different for every
    # conversation, so an agent can keep memory per conversation.
    conversation_id: str = Field(min_length=1)
    # The whole chat so far, oldest first, ending with the customer's line.
    messages: list[ChatMessage] = Field(min_length=1)
    # This conversation's tools, as an MCP server.
    tools_url: str


class ObservedChatRequest(BaseModel):
    """A turn for an observed agent (A3), which keeps its own tools: no
    `tools_url`, but the account the chat is signed in to, which its own
    backend uses to pick the data."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    signed_in_as: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
