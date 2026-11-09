"""Pairing two runs' chats for an A/B comparison (thesis pilot): for each
pair key (scenario, epoch), the first turn where the two agents' replies
differ (`diverged_at_turn`), and whether the customer said the same lines
up to it.

The customer's draws are seeded per pair, so its lines should match until
the agents' replies differ; after that it reacts to a different chat. The
gate doesn't use this; the thesis reports it.
"""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from flight_school.export.chats import CHATS_FILE, JsonObject

PairKey = tuple[str, int]


class PairingError(Exception):
    """Two runs' chats can't be paired."""


@dataclass(frozen=True)
class Pair:
    key: PairKey
    # The agent reply (1-based) where the arms first differ; None if never.
    diverged_at_turn: int | None
    # The customer said the same lines up to that reply (or throughout).
    has_same_customer: bool


def load_chats(run_dir: Path) -> dict[PairKey, JsonObject]:
    path = run_dir / CHATS_FILE
    if not path.is_file():
        raise PairingError(f"{path} is missing: rerun with this version of flightschool.")
    chats: dict[PairKey, JsonObject] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        chat: JsonObject = json.loads(line)
        task_id, attempt = chat["outcome"]["pair_key"]
        chats[(task_id, attempt)] = chat
    return chats


def lines_of(chat: JsonObject, role: str) -> list[str]:
    return [turn["text"] for turn in chat["turns"] if turn["role"] == role]


def diverged_at_turn(agent_a: list[str], agent_b: list[str]) -> int | None:
    for number, (reply_a, reply_b) in enumerate(zip(agent_a, agent_b, strict=False), start=1):
        if reply_a != reply_b:
            return number
    if len(agent_a) != len(agent_b):
        return min(len(agent_a), len(agent_b)) + 1
    return None


def pair(key: PairKey, chat_a: JsonObject, chat_b: JsonObject) -> Pair:
    turn = diverged_at_turn(lines_of(chat_a, "agent"), lines_of(chat_b, "agent"))
    customer_a, customer_b = lines_of(chat_a, "customer"), lines_of(chat_b, "customer")
    # Reply N answers customer line N, so lines 1..N must match.
    if turn is not None:
        customer_a, customer_b = customer_a[:turn], customer_b[:turn]
    return Pair(key, turn, customer_a == customer_b)


def pair_runs(run_a: Path, run_b: Path) -> list[Pair]:
    chats_a, chats_b = load_chats(run_a), load_chats(run_b)
    if chats_a.keys() != chats_b.keys():
        unpaired = sorted(chats_a.keys() ^ chats_b.keys())
        raise PairingError(f"{len(unpaired)} chat(s) have no pair in the other run: {unpaired[:5]}")
    return [pair(key, chats_a[key], chats_b[key]) for key in sorted(chats_a)]


def summary(pairs: list[Pair]) -> str:
    identical = sum(1 for each in pairs if each.diverged_at_turn is None)
    same_customer = sum(1 for each in pairs if each.has_same_customer)
    turns = Counter(each.diverged_at_turn for each in pairs if each.diverged_at_turn is not None)
    by_turn = ", ".join(f"turn {turn}: {count}" for turn, count in sorted(turns.items()))
    return (
        f"{len(pairs)} pairs; identical throughout: {identical}\n"
        f"first different agent reply: {by_turn or 'none'}\n"
        f"customer said the same lines until then: {same_customer} of {len(pairs)}\n"
    )
