"""A run's conversations as chat records (`chats.jsonl`), the shape Project 15
(`id-chat-research`) reads: its ADR-002 `ChatRecord` with `format_version`,
`chat_id`, `source`, `domain`, `turns` and a free `outcome`.

This module is the only place that knows that shape. Project 15 hasn't
released its model yet, so the records are written to ADR-002's fields
here; once it is tagged, this builds its `ChatRecord` instead of a dict.

Every record is `source: "synthetic"`: the customer is simulated. The stop
markers are test plumbing, not chat, so they are taken out of the text. A
customer who ghosts leaves without a word, so that last line is dropped
and the chat ends on the agent's message, as a real ghosting does.
"""

import json
from typing import Any

from flight_school.conversation.loop import ConversationRecord
from flight_school.conversation.scenario import GHOSTED_MARKER, STOP_MARKERS

# Project 15's ADR-002 record format this writes.
CHAT_FORMAT_VERSION = 1
CHATS_FILE = "chats.jsonl"
# A library scenario's id is "goal.persona.tactic" (sampler.py: scenario_from).
LIBRARY_ID_PARTS = 3

Turn = dict[str, object]
JsonObject = dict[str, Any]


def without_markers(text: str) -> str:
    for marker in STOP_MARKERS:
        text = text.replace(marker, "")
    return text.strip()


def chat_turns(record: ConversationRecord) -> list[Turn]:
    """Customer and agent lines in the order they were said."""
    agent_lines = [str(reply["text"]) for reply in record.replies]
    customer_lines = list(record.customer_lines)
    if record.stop_marker == GHOSTED_MARKER:
        customer_lines = customer_lines[:-1]
    turns: list[Turn] = []
    for number, customer_line in enumerate(customer_lines):
        said = [("customer", without_markers(customer_line))]
        if number < len(agent_lines):
            said.append(("agent", agent_lines[number]))
        for role, text in said:
            if text:
                turns.append({"index": len(turns), "role": role, "text": text})
    return turns


def library_ids(task_id: str) -> dict[str, str | None]:
    parts = task_id.split(".")
    if len(parts) != LIBRARY_ID_PARTS:
        return {"goal": None, "persona": None, "tactic": None}
    goal, persona, tactic = parts
    return {"goal": goal, "persona": persona, "tactic": tactic}


def chat_record(trial: JsonObject, record: ConversationRecord, run: dict[str, str]) -> JsonObject:
    """One trial as a chat record. `run` names the run, its suite (the
    domain) and the agent variant."""
    task_id, attempt = trial["task_id"], trial["attempt"]
    ids = library_ids(task_id)
    return {
        "format_version": CHAT_FORMAT_VERSION,
        "chat_id": f"{run['run_id']}/{run['agent']}/{task_id}#{attempt}",
        "source": "synthetic",
        "domain": run["suite"],
        "turns": chat_turns(record),
        "outcome": {
            **ids,
            "customer_behaviours": [ids["tactic"]] if ids["tactic"] else [],
            "stop_marker": record.stop_marker,
            "agent_variant": run["agent"],
            "customer_seed": record.customer_seed,
            "pair_key": [task_id, attempt],
        },
    }


def chats_text(records: list[JsonObject]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
