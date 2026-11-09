"""A run's conversations as Project 15's chat records (`chats.jsonl`): its
`id_chat_records.ChatRecord` (ADR-002 in `id-chat-research`), which
validates each record as it is built. Flight School's own facts about a
chat (persona, goal, tactic, stop marker, seed, pair key) go in its free
`outcome`, since the record refuses unknown fields.

Every record is `source: synthetic`: the customer is simulated. The stop
markers are test plumbing, not chat, so they are taken out of the text. A
customer who ghosts leaves without a word, so that last line is dropped
and the chat ends on the agent's message, as a real ghosting does.
"""

from pathlib import Path
from typing import Any

from id_chat_records import ChatRecord, Role, Source, Turn, write_jsonl

from flight_school.conversation.loop import ConversationRecord
from flight_school.conversation.scenario import GHOSTED_MARKER, STOP_MARKERS

CHATS_FILE = "chats.jsonl"
# A library scenario's id is "goal.persona.tactic" (sampler.py: scenario_from).
LIBRARY_ID_PARTS = 3


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
        said = [(Role.CUSTOMER, without_markers(customer_line))]
        if number < len(agent_lines):
            said.append((Role.AGENT, agent_lines[number].strip()))
        for role, text in said:
            if text:
                turns.append(Turn(index=len(turns), role=role, text=text))
    return turns


def library_ids(task_id: str) -> dict[str, str | None]:
    parts = task_id.split(".")
    if len(parts) != LIBRARY_ID_PARTS:
        return {"goal": None, "persona": None, "tactic": None}
    goal, persona, tactic = parts
    return {"goal": goal, "persona": persona, "tactic": tactic}


def chat_record(
    trial: dict[str, Any], record: ConversationRecord, run: dict[str, str]
) -> ChatRecord | None:
    """One trial as a chat record, or None if nothing was said (a scripted
    customer that ghosts on its first line). `run` names the run, its
    suite (the domain) and the agent variant."""
    turns = chat_turns(record)
    if not turns:
        return None
    task_id, attempt = trial["task_id"], trial["attempt"]
    ids = library_ids(task_id)
    return ChatRecord(
        chat_id=f"{run['run_id']}/{run['agent']}/{task_id}#{attempt}",
        source=Source.SYNTHETIC,
        domain=run["suite"],
        turns=tuple(turns),
        outcome={
            **ids,
            "customer_behaviours": [ids["tactic"]] if ids["tactic"] else [],
            "stop_marker": record.stop_marker,
            "agent_variant": run["agent"],
            "customer_seed": record.customer_seed,
            "pair_key": [task_id, attempt],
        },
    )


def write_chats(records: list[ChatRecord], run_dir: Path) -> str:
    """Write `chats.jsonl` and return its text, for the meta's hash."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / CHATS_FILE
    write_jsonl(records, path)
    return path.read_text(encoding="utf-8")
