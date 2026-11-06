"""Reading an agent's tool calls from mcp-gateway's audit log (ADR-009, A3).

The gateway writes one JSON line per event (its `audit.py`): a `call`
line when a call arrives, with its decision (`forwarding`, `denied` or
`rate_limited`), the tool and its arguments (secret-looking fields
redacted); then, for a forwarded call, a `result` line with the same
`call_id`, saying whether the tool returned an error. The tool's output
is never logged, only its hash, so an observed call has no `result`.

The log is read as data and fails closed: a line that isn't JSON, or a
format version this code doesn't know, stops the trial as an error
rather than dropping calls and passing.
"""

import json
from pathlib import Path
from typing import Any, cast

from flight_school.log import ToolCall

# The gateway's `audit.SCHEMA_VERSION` this reader was written against:
# the same at 66227a2 (the commit Juku's eval stack runs) and 76d58ad.
SCHEMA_VERSION = 1
# Result decisions where the tool never ran: the upstream failed or the
# gateway couldn't reach it. Any other result (allowed, annotated,
# logged, blocked, gateway_error) means it ran: a blocked output still
# had its side effect.
NOT_RUN = frozenset({"upstream_error"})

Line = dict[str, Any]


class AuditLogError(Exception):
    """The audit log can't be read as the gateway writes it."""


def read_from(path: Path, offset: int) -> tuple[list[Line], int]:
    """The complete lines written after byte `offset`, and the offset to
    read from next time. A line still being written is left for then."""
    with path.open("rb") as log_file:
        if log_file.seek(0, 2) < offset:
            raise AuditLogError(
                f"the audit log {path} got shorter during the turn: was it rotated or"
                " replaced? This turn's calls can't be read; rerun with the gateway left alone."
            )
        log_file.seek(offset)
        data = log_file.read()
    complete = data[: data.rfind(b"\n") + 1]
    return [parse(raw) for raw in complete.splitlines()], offset + len(complete)


def parse(raw: bytes) -> Line:
    try:
        line: object = json.loads(raw)
    except ValueError as error:
        raise AuditLogError(f"a line of the audit log isn't JSON: {raw[:80]!r}") from error
    if not isinstance(line, dict) or cast(Line, line).get("schema_version") != SCHEMA_VERSION:
        raise AuditLogError(
            f"an audit line isn't in gateway log format {SCHEMA_VERSION}: {raw[:80]!r}."
            " Check the gateway's version against flight_school/observer/audit_log.py."
        )
    return cast(Line, line)


def observed_calls(lines: list[Line], caller: str, turn: int) -> list[ToolCall]:
    """`caller`'s calls in `lines`, in the order they arrived, each with
    whether the tool ran without an error."""
    results = {line["call_id"]: line for line in lines if line.get("kind") == "result"}
    calls: list[ToolCall] = []
    for line in lines:
        if line.get("kind") != "call" or line.get("caller") != caller:
            continue
        error = call_error(line, results.get(line["call_id"]))
        arguments: dict[str, object] = line.get("arguments") or {}
        calls.append(ToolCall(turn, line["tool"], arguments, succeeded=error is None, error=error))
    return calls


def call_error(call: Line, result: Line | None) -> str | None:
    """Why the call didn't go through, or None if the tool ran cleanly."""
    if call["decision"] != "forwarding":
        return f"gateway {call['decision']}: {detail_of(call)}"
    if result is None:
        return "forwarded, but the audit log has no result for it"
    if result["decision"] in NOT_RUN:
        return f"gateway {result['decision']}: {detail_of(result)}"
    if result.get("is_error"):
        return "the tool returned an error"
    return None


def detail_of(line: Line) -> str:
    """The gateway's own words for a decision: a denial's reason, a rate
    limit, or an upstream error (on a `call` line before 76d58ad)."""
    return str(line.get("reason") or line.get("limit") or line.get("error") or "")
