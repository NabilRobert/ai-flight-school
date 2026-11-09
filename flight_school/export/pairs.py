"""Pairing two runs' chats for an A/B comparison (thesis pilot): for each
pair key (scenario, epoch), the first turn where the two agents' replies
differ (`diverged_at_turn`), and whether the customer said the same lines
up to it.

The customer's draws are seeded per pair, so its lines should match until
the agents' replies differ; after that it reacts to a different chat. The
gate doesn't use this; the thesis reports it.
"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from id_chat_records import ChatRecord, Role, read_jsonl

from flight_school.export.chats import CHATS_FILE

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


def load_chats(run_dir: Path) -> dict[PairKey, ChatRecord]:
    path = run_dir / CHATS_FILE
    if not path.is_file():
        raise PairingError(f"{path} is missing: rerun with this version of flightschool.")
    chats: dict[PairKey, ChatRecord] = {}
    try:
        for chat in read_jsonl(path):
            chats[pair_key_of(chat)] = chat
    except ValueError as error:
        raise PairingError(f"{path}: {error}") from error
    return chats


def pair_key_of(chat: ChatRecord) -> PairKey:
    match (chat.outcome or {}).get("pair_key"):
        case [str(task_id), int(attempt)]:
            return task_id, attempt
        case other:
            raise ValueError(f"chat {chat.chat_id} has no pair key [task_id, attempt]: {other!r}")


def lines_of(chat: ChatRecord, role: Role) -> list[str]:
    return [turn.text for turn in chat.turns if turn.role == role]


def diverged_at_turn(agent_a: list[str], agent_b: list[str]) -> int | None:
    for number, (reply_a, reply_b) in enumerate(zip(agent_a, agent_b, strict=False), start=1):
        if reply_a != reply_b:
            return number
    if len(agent_a) != len(agent_b):
        return min(len(agent_a), len(agent_b)) + 1
    return None


def pair(key: PairKey, chat_a: ChatRecord, chat_b: ChatRecord) -> Pair:
    turn = diverged_at_turn(lines_of(chat_a, Role.AGENT), lines_of(chat_b, Role.AGENT))
    customer_a, customer_b = lines_of(chat_a, Role.CUSTOMER), lines_of(chat_b, Role.CUSTOMER)
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
