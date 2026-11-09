"""A run's conversations as chat records (`chats.jsonl`) for Project 15,
and pairing two runs' chats for an A/B comparison."""

import json
from pathlib import Path
from typing import Any

import pytest
from agent_eval.records import load_run, sha256_hex
from inspect_ai.util import Store

from flight_school.conversation.loop import ConversationRecord
from flight_school.export.chats import CHATS_FILE, chat_record, chat_turns
from flight_school.export.pairs import PairingError, pair, pair_runs, summary
from flight_school.reference.sales_agent import healthy
from tests.test_sales import AGENT_REPLY, run_sales


def chats_in(run_dir: Path) -> dict[str, dict[str, Any]]:
    lines = (run_dir / CHATS_FILE).read_text(encoding="utf-8").splitlines()
    chats = [json.loads(line) for line in lines]
    return {chat["outcome"]["pair_key"][0]: chat for chat in chats}


@pytest.fixture(scope="module")
def sales_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return run_sales(tmp_path_factory.mktemp("sales"), healthy, [])


def test_a_ghosted_chat_ends_on_the_agents_message(sales_run: Path) -> None:
    chat = chats_in(sales_run)["menghilang-setelah-tanya-dp"]
    assert [turn["role"] for turn in chat["turns"]] == ["customer", "agent"]
    assert chat["turns"][-1]["text"] == AGENT_REPLY


def test_stop_markers_are_taken_out_of_what_the_customer_said(sales_run: Path) -> None:
    chat = chats_in(sales_run)["tanya-harga-tunai"]
    assert chat["turns"][-1] == {"index": 2, "role": "customer", "text": "Oke makasih kak infonya."}
    assert chat["outcome"]["stop_marker"] == "###DONE###"


def test_every_chat_is_marked_synthetic_and_keyed_for_pairing(sales_run: Path) -> None:
    for task_id, chat in chats_in(sales_run).items():
        assert chat["source"] == "synthetic"
        assert chat["domain"] == "sales-id"
        assert chat["outcome"]["pair_key"] == [task_id, 1]


def test_the_runs_meta_vouches_for_its_chats(sales_run: Path) -> None:
    text = (sales_run / CHATS_FILE).read_text(encoding="utf-8")
    assert load_run(sales_run).meta["provenance"]["chats_sha256"] == sha256_hex(text)


def test_a_library_chat_names_its_persona_goal_and_tactic() -> None:
    record = ConversationRecord(store=Store())
    trial = {"task_id": "cek-harga.pedagang-pasar.menawar", "attempt": 2}
    run = {"run_id": "r1", "suite": "sales-id", "agent": "healthy"}
    outcome = chat_record(trial, record, run)["outcome"]
    assert (outcome["goal"], outcome["persona"], outcome["tactic"]) == (
        "cek-harga",
        "pedagang-pasar",
        "menawar",
    )
    assert outcome["customer_behaviours"] == ["menawar"]


def test_two_runs_with_the_same_replies_never_diverge(tmp_path: Path, sales_run: Path) -> None:
    again = run_sales(tmp_path, healthy, [])
    pairs = pair_runs(sales_run, again)
    assert [each.diverged_at_turn for each in pairs] == [None, None]
    assert summary(pairs).startswith("2 pairs; identical throughout: 2\n")


def test_a_different_first_reply_diverges_at_turn_one_with_the_same_customer(
    tmp_path: Path, sales_run: Path
) -> None:
    other = run_sales(tmp_path, healthy, [], reply="Silakan datang ke showroom ya kak.")
    pairs = pair_runs(sales_run, other)
    assert [(each.diverged_at_turn, each.has_same_customer) for each in pairs] == [
        (1, True),
        (1, True),
    ]


def test_runs_whose_chats_dont_pair_up_are_refused(tmp_path: Path, sales_run: Path) -> None:
    other = run_sales(tmp_path, healthy, [])
    chats = (other / CHATS_FILE).read_text(encoding="utf-8").splitlines()
    (other / CHATS_FILE).write_text(chats[0] + "\n", encoding="utf-8")
    with pytest.raises(PairingError, match="1 chat\\(s\\) have no pair"):
        pair_runs(sales_run, other)


def chat_of(*lines: tuple[str, str]) -> dict[str, Any]:
    return {"turns": [{"role": role, "text": text} for role, text in lines]}


def test_an_arm_that_ends_sooner_diverges_after_its_last_reply() -> None:
    short = chat_of(("customer", "harga?"), ("agent", "Rp18,9 juta."))
    longer = chat_of(
        ("customer", "harga?"), ("agent", "Rp18,9 juta."), ("customer", "dp?"), ("agent", "15%.")
    )
    assert pair(("t", 1), short, longer).diverged_at_turn == 2


def test_a_customer_that_differs_before_the_agents_do_is_flagged() -> None:
    first = chat_of(("customer", "harga?"), ("agent", "Rp18,9 juta."))
    second = chat_of(("customer", "stok?"), ("agent", "Rp18,9 juta."))
    assert not pair(("t", 1), first, second).has_same_customer


def record_of(customer_lines: list[str], replies: list[str], marker: str) -> ConversationRecord:
    record = ConversationRecord(store=Store())
    record.customer_lines = customer_lines
    record.replies = [{"turn": n, "text": text} for n, text in enumerate(replies, start=1)]
    record.stop_marker = marker
    return record


def test_a_ghosting_line_is_dropped_even_with_words_before_the_marker() -> None:
    record = record_of(["harga?", "ya udah deh ###GHOSTED###"], ["Rp18,9 juta."], "###GHOSTED###")
    assert [turn["role"] for turn in chat_turns(record)] == ["customer", "agent"]


def test_a_line_that_was_only_a_stop_marker_leaves_no_empty_turn() -> None:
    record = record_of(["harga?", "###DONE###"], ["Rp18,9 juta."], "###DONE###")
    assert [turn["text"] for turn in chat_turns(record)] == ["harga?", "Rp18,9 juta."]


def test_a_later_epoch_is_its_own_pair() -> None:
    trial = {"task_id": "tanya-harga-tunai", "attempt": 2}
    run = {"run_id": "r1", "suite": "sales-id", "agent": "healthy"}
    record = chat_record(trial, ConversationRecord(store=Store()), run)
    assert record["outcome"]["pair_key"] == ["tanya-harga-tunai", 2]


def test_the_customer_line_a_diverging_reply_answers_must_match() -> None:
    first = chat_of(("customer", "harga?"), ("agent", "A"), ("customer", "dp?"), ("agent", "B"))
    second = chat_of(("customer", "harga?"), ("agent", "A"), ("customer", "stok?"), ("agent", "C"))
    result = pair(("t", 1), first, second)
    assert (result.diverged_at_turn, result.has_same_customer) == (2, False)


def test_a_customer_reacting_differently_after_the_replies_differ_is_expected() -> None:
    first = chat_of(("customer", "harga?"), ("agent", "A"), ("customer", "oke"))
    second = chat_of(("customer", "harga?"), ("agent", "B"), ("customer", "kok gitu?"))
    assert pair(("t", 1), first, second).has_same_customer
