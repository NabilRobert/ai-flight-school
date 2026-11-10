"""The HTTP adapter and the MCP tool server (slice 5, A2): the same
verdicts as in process, one conversation's tools out of another's reach,
a broken endpoint never passing, and no key or stray call leaving the run."""

import asyncio
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from agent_eval.records import load_run
from mcp import Client
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from flight_school.conversation.agent import AgentFactory, AgentTools
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import run_plan
from flight_school.gate import EXIT_INCONCLUSIVE, Verdict, judge
from flight_school.http.adapter import AGENT_KEY_VARIABLE, http_agent
from flight_school.http.serving import serve_in_thread
from flight_school.http.tool_server import MCP_PATH, running_tool_server
from flight_school.reference.agent import Bug, reference_agent
from flight_school.reference.http_agent import CHAT_PATH, reference_app
from flight_school.suite import load_suite
from flight_school.world.shop import FakeShop
from tests.test_conversation import EXAMPLES

SUITE = load_suite(EXAMPLES)
VARIANTS: list[Bug | None] = [
    None,
    "skips-verification",
    "ignores-refund-limit",
    "trusts-manager-claim",
    "acts-on-others-orders",
    "leaks-manager-code",
    "refunds-twice",
    "obeys-order-notes",
]


def run_dir_with(run_dir: Path, factory: AgentFactory, agent_url: str | None = None) -> Path:
    plan = RunPlan(
        SUITE.world, SUITE.rules, SUITE.scenarios, factory, "agent", "shop", agent_url=agent_url
    )
    run_plan(plan, run_dir)
    return run_dir


def run_over_http(run_dir: Path, agent_url: str) -> Path:
    with running_tool_server() as tool_server:
        return run_dir_with(run_dir, http_agent(agent_url, tool_server), agent_url)


def summary(verdict: Verdict) -> tuple[int, list[tuple[str, str, int]], tuple[int, int]]:
    findings = sorted((f.task_id, f.rule_id, f.turn) for f in verdict.findings)
    return verdict.exit_code, findings, verdict.task_success


@pytest.mark.parametrize("bug", VARIANTS, ids=lambda bug: bug or "correct")
def test_each_reference_variant_gets_the_same_verdict_over_http(
    tmp_path: Path, bug: Bug | None
) -> None:
    in_process = judge(run_dir_with(tmp_path / "in-process", reference_agent(bug)))
    with serve_in_thread(reference_app(bug)) as base_url:
        over_http = judge(run_over_http(tmp_path / "http", base_url + CHAT_PATH))
    assert summary(over_http) == summary(in_process)


def test_the_records_name_the_agent_url_as_an_http_target(tmp_path: Path) -> None:
    with serve_in_thread(reference_app()) as base_url:
        run_over_http(tmp_path, base_url + CHAT_PATH)
    target = load_run(tmp_path).meta["target"]
    assert (target["transport"], target["address"]) == ("http", base_url + CHAT_PATH)


async def call_tool(url: str, tool: str, arguments: dict[str, object]) -> Any:
    async with Client(url) as client:
        return await client.call_tool(tool, arguments)


def test_a_call_reaches_only_its_own_conversations_shop() -> None:
    shops = [FakeShop(SUITE.world), FakeShop(SUITE.world)]
    with running_tool_server() as tool_server:
        first_url, _ = [tool_server.register(AgentTools(shop)) for shop in shops]
        asyncio.run(call_tool(first_url, "list_orders", {"customer_id": "c1"}))
        guessed = asyncio.run(
            call_tool(f"{tool_server.base_url}{MCP_PATH}?conversation=guessed", "list_orders", {})
        )
    assert [[call.tool for call in shop.calls] for shop in shops] == [["list_orders"], []]
    assert guessed.is_error
    assert "unknown conversation" in guessed.content[0].text


async def listed_tools(url: str) -> Any:
    async with Client(url) as client:
        return (await client.list_tools()).tools


def test_the_tool_list_tells_an_agent_what_each_tool_does_and_which_only_read() -> None:
    # An agent outside the repo has only this list; a guard that allows
    # only read-only tools outside a sandbox reads the hints.
    with running_tool_server() as tool_server:
        url = tool_server.register(AgentTools(FakeShop(SUITE.world)))
        tools = asyncio.run(listed_tools(url))
    assert all(tool.description for tool in tools)
    hints = {
        tool.name: (tool.annotations.read_only_hint, tool.annotations.destructive_hint)
        for tool in tools
    }
    reads = {"lookup_order", "list_orders", "verify_identity"}
    writes = {"issue_refund", "cancel_subscription", "update_address", "delete_account"}
    assert hints == {name: (True, False) for name in reads} | {
        name: (False, True) for name in writes
    }


def test_a_refused_call_comes_back_as_an_mcp_error_with_the_shops_reason() -> None:
    with running_tool_server() as tool_server:
        url = tool_server.register(AgentTools(FakeShop(SUITE.world)))
        result = asyncio.run(
            call_tool(url, "verify_identity", {"customer_id": "c1", "email": "nope@example.com"})
        )
    assert result.is_error
    assert result.content[0].text == "the email doesn't match this customer"


def agent_answering(response: Response, seen_headers: list[str] | None = None) -> Starlette:
    async def chat(request: Request) -> Response:
        if seen_headers is not None:
            seen_headers.append(request.headers.get("authorization", ""))
        return response

    return Starlette(routes=[Route(CHAT_PATH, chat, methods=["POST"])])


@pytest.mark.parametrize(
    "response",
    [
        # A failing status counts even with a reply in the body.
        JSONResponse({"reply": "All done!"}, status_code=500),
        JSONResponse({"text": "wrong field"}),
    ],
    ids=["server-error", "breaks-the-contract"],
)
def test_an_endpoint_that_fails_makes_the_run_inconclusive(
    tmp_path: Path, response: Response
) -> None:
    with serve_in_thread(agent_answering(response)) as base_url:
        verdict = judge(run_over_http(tmp_path, base_url + CHAT_PATH))
    assert verdict.exit_code == EXIT_INCONCLUSIVE
    assert len(verdict.unchecked) == len(SUITE.scenarios)


def test_a_redirect_is_not_followed_to_another_agent(tmp_path: Path) -> None:
    # Followed, it would send the chat somewhere not configured (X4).
    with serve_in_thread(reference_app()) as other_agent:
        redirect = RedirectResponse(other_agent + CHAT_PATH, status_code=307)
        with serve_in_thread(agent_answering(redirect)) as base_url:
            verdict = judge(run_over_http(tmp_path, base_url + CHAT_PATH))
    assert verdict.exit_code == EXIT_INCONCLUSIVE


def test_the_agent_key_is_sent_but_never_written_or_printed_even_when_the_agent_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    key = "fs-test-key-8c1d0b"
    monkeypatch.setenv(AGENT_KEY_VARIABLE, key)
    seen: list[str] = []
    with serve_in_thread(agent_answering(Response(status_code=500), seen)) as base_url:
        run_over_http(tmp_path / "run", base_url + CHAT_PATH)
    assert seen and all(header == f"Bearer {key}" for header in seen)
    written = [path for path in (tmp_path / "run").rglob("*") if path.is_file()]
    assert written
    assert [path for path in written if key.encode() in path.read_bytes()] == []
    printed = capfd.readouterr()
    assert key not in printed.out + printed.err


@pytest.fixture
def connections(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[str, int]]]:
    """Every outbound connection this process opens, as (host, port)."""
    opened: list[tuple[str, int]] = []
    original = socket.socket.connect

    def record(self: socket.socket, address: Any) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6):
            opened.append((address[0], address[1]))
        original(self, address)

    monkeypatch.setattr(socket.socket, "connect", record)
    yield opened


def test_a_run_over_http_connects_only_to_the_agent_and_its_own_tool_server(
    tmp_path: Path, connections: list[tuple[str, int]]
) -> None:
    with serve_in_thread(reference_app()) as base_url:
        agent_port = int(base_url.rsplit(":", 1)[1])
        with running_tool_server() as tool_server:
            tool_port = int(tool_server.base_url.rsplit(":", 1)[1])
            run_dir_with(tmp_path, http_agent(base_url + CHAT_PATH, tool_server))
    assert {port for _, port in connections} == {agent_port, tool_port}
    assert {host for host, _ in connections} == {"127.0.0.1"}
