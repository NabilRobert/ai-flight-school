"""Reading tool calls from mcp-gateway's audit log (A3): each gateway
decision becomes the right call record, and a log that can't be read as
the gateway writes it stops the trial instead of passing it."""

import json
from pathlib import Path
from typing import Any

import pytest

from flight_school.observer.audit_log import AuditLogError, observed_calls, read_from
from tests.observed_stub import append, call_lines, gateway_line


def calls_in(tmp_path: Path, lines: list[dict[str, Any]]) -> list[tuple[str, bool, str | None]]:
    log = tmp_path / "audit.jsonl"
    append(log, lines)
    read, _ = read_from(log, 0)
    return [(call.tool, call.succeeded, call.error) for call in observed_calls(read, "shiori", 1)]


def test_a_forwarded_call_that_ran_is_observed_with_its_arguments(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    append(log, call_lines("search_words", {"query": "taberu"}))
    lines, _ = read_from(log, 0)
    [call] = observed_calls(lines, "shiori", turn=3)
    assert (call.turn, call.tool, call.arguments, call.succeeded) == (
        3,
        "search_words",
        {"query": "taberu"},
        True,
    )


def forwarded_with(**result: Any) -> list[dict[str, Any]]:
    call, _ = call_lines("request_replan")
    return [call, gateway_line("result", tool="request_replan", call_id=call["call_id"], **result)]


@pytest.mark.parametrize(
    ("lines", "error"),
    [
        ([gateway_line("call", "denied", "request_replan", reason="not allowed")], "not allowed"),
        ([gateway_line("call", "rate_limited", "request_replan", limit="10/min")], "10/min"),
        (forwarded_with(decision="allowed", is_error=True), "the tool returned an error"),
        (forwarded_with(decision="upstream_error", error="ConnectError"), "ConnectError"),
        # How the gateway at 66227a2, which Juku's eval stack runs, logs it.
        ([gateway_line("call", "upstream_error", "get_plan", error="ReadTimeout")], "ReadTimeout"),
        (call_lines("request_replan")[:1], "has no result"),
    ],
    ids=[
        "denied",
        "rate-limited",
        "tool-error",
        "upstream-failed",
        "upstream-failed-old",
        "no-result",
    ],
)
def test_a_call_that_did_not_run_cleanly_is_observed_as_failed(
    tmp_path: Path, lines: list[dict[str, Any]], error: str
) -> None:
    [(_, succeeded, reason)] = calls_in(tmp_path, lines)
    assert not succeeded
    assert reason is not None and error in reason


def test_a_call_whose_output_the_gateway_blocked_still_ran(tmp_path: Path) -> None:
    # The side effect happened; only the agent was kept from the output.
    lines = forwarded_with(decision="blocked", is_error=False)
    assert calls_in(tmp_path, lines) == [("request_replan", True, None)]


def test_only_the_observed_agents_own_calls_are_counted(tmp_path: Path) -> None:
    keiko, _ = call_lines("get_plan")
    keiko["caller"] = "keiko"
    assert calls_in(tmp_path, [keiko, *call_lines("get_memory")]) == [("get_memory", True, None)]


def test_a_line_still_being_written_is_left_for_the_next_read(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    first, second = call_lines("get_memory")
    log.write_text(json.dumps(first) + "\n" + json.dumps(second)[:20], encoding="utf-8")
    lines, offset = read_from(log, 0)
    assert len(lines) == 1
    with log.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(second)[20:] + "\n")
    rest, _ = read_from(log, offset)
    assert [line["kind"] for line in rest] == ["result"]


@pytest.mark.parametrize(
    "raw",
    ['{"torn": \n', json.dumps({**call_lines("get_memory")[0], "schema_version": 2}) + "\n"],
    ids=["not-json", "unknown-format"],
)
def test_a_log_not_in_the_gateways_format_stops_the_trial(tmp_path: Path, raw: str) -> None:
    log = tmp_path / "audit.jsonl"
    log.write_text(raw, encoding="utf-8")
    with pytest.raises(AuditLogError):
        read_from(log, 0)


def test_a_log_replaced_during_the_turn_stops_the_trial(tmp_path: Path) -> None:
    # Read from the old offset, a new shorter file would show no calls.
    log = tmp_path / "audit.jsonl"
    append(log, call_lines("get_memory"))
    offset = log.stat().st_size
    log.write_text("", encoding="utf-8")
    with pytest.raises(AuditLogError, match="got shorter"):
        read_from(log, offset)
