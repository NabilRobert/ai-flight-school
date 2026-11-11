"""A run's conversations as Project 15's chat records (`chats.jsonl`), and
pairing two runs' chats for an A/B comparison."""

from pathlib import Path

import pytest
from agent_eval.records import load_run, sha256_hex
from id_chat_records import ChatRecord, Role, Source, Turn, read_jsonl
from inspect_ai.util import Store

from flight_school.conversation.loop import ConversationRecord
from flight_school.export.chats import CHATS_FILE, chat_record, chat_turns
from flight_school.export.pairs import PairingError, pair, pair_runs, summary
from flight_school.reference.sales_agent import healthy
from tests.test_sales import AGENT_REPLY, run_sales

RUN = {"run_id": "r1", "suite": "sales-id", "agent": "healthy"}


def chats_in(run_dir: Path) -> dict[str, ChatRecord]:
    """The run's chats, read and validated by Project 15's own reader."""
    return {chat.chat_id.rsplit("/", 1)[1]: chat for chat in read_jsonl(run_dir / CHATS_FILE)}


def record_of(
    customer_lines: list[str], replies: list[str], marker: str | None = None
) -> ConversationRecord:
    record = ConversationRecord(store=Store())
    record.customer_lines = customer_lines
    record.replies = [{"turn": n, "text": text} for n, text in enumerate(replies, start=1)]
    record.stop_marker = marker
    return record


def chat_of(*lines: tuple[Role, str]) -> ChatRecord:
    turns = tuple(Turn(index=n, role=role, text=text) for n, (role, text) in enumerate(lines))
    return ChatRecord(chat_id="c", source=Source.SYNTHETIC, domain="sales-id", turns=turns)


CUSTOMER, AGENT = Role.CUSTOMER, Role.AGENT


@pytest.fixture(scope="module")
def sales_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return run_sales(tmp_path_factory.mktemp("sales"), healthy, [])


def test_every_chat_validates_as_a_synthetic_chat_record(sales_run: Path) -> None:
    chats = chats_in(sales_run)
    assert sorted(chats) == ["menghilang-setelah-tanya-dp#1", "tanya-harga-tunai#1"]
    for chat in chats.values():
        assert chat.source == Source.SYNTHETIC
        assert chat.domain == "sales-id"


def test_a_ghosted_chat_ends_on_the_agents_message(sales_run: Path) -> None:
    chat = chats_in(sales_run)["menghilang-setelah-tanya-dp#1"]
    assert [turn.role for turn in chat.turns] == [CUSTOMER, AGENT]
    assert chat.turns[-1].text == AGENT_REPLY


def test_stop_markers_are_taken_out_of_what_the_customer_said(sales_run: Path) -> None:
    chat = chats_in(sales_run)["tanya-harga-tunai#1"]
    assert chat.turns[-1] == Turn(index=2, role=CUSTOMER, text="Oke makasih kak infonya.")
    assert (chat.outcome or {})["stop_marker"] == "###DONE###"


def test_the_runs_meta_vouches_for_its_chats(sales_run: Path) -> None:
    text = (sales_run / CHATS_FILE).read_text(encoding="utf-8")
    assert load_run(sales_run).meta["provenance"]["chats_sha256"] == sha256_hex(text)


def test_a_library_chat_names_its_persona_goal_and_tactic() -> None:
    trial = {"task_id": "cek-harga.pedagang-pasar.menawar", "attempt": 2}
    chat = chat_record(trial, record_of(["harga?"], []), RUN)
    assert chat is not None
    outcome = chat.outcome or {}
    assert (outcome["goal"], outcome["persona"], outcome["tactic"]) == (
        "cek-harga",
        "pedagang-pasar",
        "menawar",
    )
    assert outcome["customer_behaviours"] == ["menawar"]


def test_a_later_epoch_is_its_own_pair() -> None:
    trial = {"task_id": "tanya-harga-tunai", "attempt": 2}
    chat = chat_record(trial, record_of(["harga?"], []), RUN)
    assert chat is not None
    assert (chat.outcome or {})["pair_key"] == ["tanya-harga-tunai", 2]


def test_a_chat_where_nothing_was_said_is_left_out() -> None:
    # A scripted customer that ghosts on its first line: a chat record
    # needs at least one turn.
    trial = {"task_id": "t", "attempt": 1}
    assert chat_record(trial, record_of(["###GHOSTED###"], [], "###GHOSTED###"), RUN) is None


def test_a_ghosting_line_is_dropped_even_with_words_before_the_marker() -> None:
    record = record_of(["harga?", "ya udah deh ###GHOSTED###"], ["Rp18,9 juta."], "###GHOSTED###")
    assert [turn.role for turn in chat_turns(record)] == [CUSTOMER, AGENT]


def test_a_line_that_was_only_a_stop_marker_leaves_no_empty_turn() -> None:
    record = record_of(["harga?", "###DONE###"], ["Rp18,9 juta."], "###DONE###")
    assert [turn.text for turn in chat_turns(record)] == ["harga?", "Rp18,9 juta."]


def test_a_misspelt_stop_marker_is_taken_out_of_the_text_too() -> None:
    record = record_of(["harga?", "mahal ah ###GIVE_UP###"], ["Rp18,9 juta."], "###GAVE_UP###")
    assert chat_turns(record)[-1].text == "mahal ah"


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


def test_a_chat_without_a_pair_key_is_refused(tmp_path: Path, sales_run: Path) -> None:
    other = run_sales(tmp_path, healthy, [])
    text = (other / CHATS_FILE).read_text(encoding="utf-8")
    (other / CHATS_FILE).write_text(text.replace('"pair_key"', '"pair"'), encoding="utf-8")
    with pytest.raises(PairingError, match="has no pair key"):
        pair_runs(sales_run, other)


def test_an_arm_that_ends_sooner_diverges_after_its_last_reply() -> None:
    short = chat_of((CUSTOMER, "harga?"), (AGENT, "Rp18,9 juta."))
    longer = chat_of(
        (CUSTOMER, "harga?"), (AGENT, "Rp18,9 juta."), (CUSTOMER, "dp?"), (AGENT, "15%.")
    )
    assert pair(("t", 1), short, longer).diverged_at_turn == 2


def test_a_customer_that_differs_before_the_agents_do_is_flagged() -> None:
    first = chat_of((CUSTOMER, "harga?"), (AGENT, "Rp18,9 juta."))
    second = chat_of((CUSTOMER, "stok?"), (AGENT, "Rp18,9 juta."))
    assert not pair(("t", 1), first, second).has_same_customer


def test_the_customer_line_a_diverging_reply_answers_must_match() -> None:
    first = chat_of((CUSTOMER, "harga?"), (AGENT, "A"), (CUSTOMER, "dp?"), (AGENT, "B"))
    second = chat_of((CUSTOMER, "harga?"), (AGENT, "A"), (CUSTOMER, "stok?"), (AGENT, "C"))
    result = pair(("t", 1), first, second)
    assert (result.diverged_at_turn, result.has_same_customer) == (2, False)


def test_a_customer_reacting_differently_after_the_replies_differ_is_expected() -> None:
    first = chat_of((CUSTOMER, "harga?"), (AGENT, "A"), (CUSTOMER, "oke"))
    second = chat_of((CUSTOMER, "harga?"), (AGENT, "B"), (CUSTOMER, "kok gitu?"))
    assert pair(("t", 1), first, second).has_same_customer
