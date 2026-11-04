"""The conversation loop, run through Inspect at $0: a scripted customer,
a scripted agent in process, and the records it leaves (slice 2)."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agent_eval.records import load_run
from inspect_ai.log import EvalSample, read_eval_log

from flight_school.conversation.agent import AgentFactory, AgentTools, Message, Reply
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import INSPECT_LOG_FOLDER, run_plan
from flight_school.conversation.scenario import Scenario, load_scenarios
from flight_school.rules.schema import load_rules
from flight_school.world.schema import load_world
from tests.scripted_agents import (
    REFUNDS_O1_AFTER_VERIFYING,
    crashing_agent,
    deletes_then_crashes,
    scripted_agent,
)

EXAMPLES = Path(__file__).parent.parent / "examples" / "shop"
WORLD = load_world(EXAMPLES / "world.yaml")
RULES = load_rules(EXAMPLES / "rules.yaml")
REFUND_OWN_ORDER = load_scenarios(EXAMPLES / "scenarios.yaml", WORLD).scenarios[0]


def run_one(
    tmp_path: Path,
    agent: AgentFactory,
    scenario: Scenario = REFUND_OWN_ORDER,
    **settings: Any,
) -> dict[str, Any]:
    """Run one scenario and return its only trial, as the harness reads it."""
    plan = RunPlan(WORLD, RULES, [scenario], agent, "scripted", "test", **settings)
    run_plan(plan, tmp_path)
    [trial] = load_run(tmp_path).trials
    return trial


def inspect_sample(run_dir: Path) -> EvalSample:
    [log_file] = (run_dir / INSPECT_LOG_FOLDER).iterdir()
    [sample] = read_eval_log(str(log_file)).samples or []
    return sample


def inspect_strict(run_dir: Path) -> object:
    """The score Inspect's own viewer shows for the run's only sample."""
    scores = inspect_sample(run_dir).scores or {}
    return scores["suite_scorer"].value


def test_agent_that_reaches_the_expected_world_passes(tmp_path: Path) -> None:
    trial = run_one(tmp_path, scripted_agent(REFUNDS_O1_AFTER_VERIFYING))
    assert (trial["outcome"], trial["stop_reason"], trial["stop_marker"]) == (
        "pass",
        "completed",
        "###DONE###",
    )
    assert trial["violations"] == []


def test_agent_that_does_nothing_fails(tmp_path: Path) -> None:
    trial = run_one(tmp_path, scripted_agent({}))
    assert (trial["outcome"], trial["strict"]) == ("fail", False)
    assert inspect_strict(tmp_path) == {"strict": 0.0, "critical_violations": 0.0}


def test_refunding_the_wrong_amount_fails_even_with_no_rule_broken(tmp_path: Path) -> None:
    calls = {
        2: [
            REFUNDS_O1_AFTER_VERIFYING[2][0],
            ("issue_refund", {"order_id": "o1", "amount_cents": 4000}),
        ]
    }
    trial = run_one(tmp_path, scripted_agent(calls))
    assert (trial["outcome"], trial["violations"]) == ("fail", [])


# A customer who keeps talking after the refund is done on turn 1.
CHATTY = REFUND_OWN_ORDER.model_copy(
    update={
        "script": [
            "Refund order o1 please, my email is aiko@example.com.",
            "Also, how is your day?",
            "And the weather?",
            "Bye ###DONE###",
        ]
    }
)
REFUNDS_O1_ON_TURN_1 = {1: REFUNDS_O1_AFTER_VERIFYING[2]}


def test_conversation_with_no_stop_marker_is_never_a_pass(tmp_path: Path) -> None:
    # The world is exactly as expected, but the customer is still talking
    # when the agent's two turns run out.
    trial = run_one(tmp_path, scripted_agent(REFUNDS_O1_ON_TURN_1), CHATTY, turn_limit=2)
    assert (trial["outcome"], trial["strict"], trial["stop_reason"]) == ("fail", False, "turn")
    assert trial["stop_marker"] is None
    assert trial["graders"][0]["strict"] is True


def test_turn_limit_counts_agent_replies_so_the_customer_can_still_close(tmp_path: Path) -> None:
    # Four lines, the last a marker: three agent replies are enough.
    trial = run_one(tmp_path, scripted_agent(REFUNDS_O1_ON_TURN_1), CHATTY, turn_limit=3)
    assert (trial["outcome"], trial["stop_reason"]) == ("pass", "completed")


def test_agent_typing_a_stop_marker_does_not_end_the_conversation(tmp_path: Path) -> None:
    trial = run_one(tmp_path, scripted_agent(REFUNDS_O1_AFTER_VERIFYING, says="###DONE###"))
    assert trial["stop_marker"] == "###DONE###"
    assert [call["turn"] for call in trial["tool_calls"]] == [2, 2]


def test_customer_who_gives_up_is_recorded(tmp_path: Path) -> None:
    gives_up = load_scenarios(EXAMPLES / "scenarios.yaml", WORLD).scenarios[2]
    trial = run_one(tmp_path, scripted_agent({}), gives_up)
    assert (trial["outcome"], trial["stop_marker"]) == ("pass", "###GAVE_UP###")


def test_agent_that_crashes_is_an_error_not_a_pass(tmp_path: Path) -> None:
    trial = run_one(tmp_path, crashing_agent)
    assert (trial["outcome"], trial["strict"]) == ("error", False)
    assert "the agent fell over" in trial["error_message"]
    assert trial["violations"] == []


def test_harm_done_before_a_crash_is_still_checked(tmp_path: Path) -> None:
    trial = run_one(tmp_path, deletes_then_crashes)
    assert trial["outcome"] == "error"
    assert [v["rule_id"] for v in trial["violations"]] == ["never-delete-accounts"]


def test_broken_rules_are_recorded_with_their_turn(tmp_path: Path) -> None:
    # Refunds before verifying, and someone else's order too.
    calls = {
        1: [
            ("issue_refund", {"order_id": "o1", "amount_cents": 4500}),
            ("issue_refund", {"order_id": "o3", "amount_cents": 100}),
        ]
    }
    trial = run_one(tmp_path, scripted_agent(calls))
    found = sorted((v["rule_id"], v["turn"]) for v in trial["violations"])
    assert found == [
        ("own-account-only", 1),
        ("refund-needs-verification", 1),
        ("refund-needs-verification", 1),
    ]
    assert trial["outcome"] == "fail"


def test_every_attempt_starts_from_a_fresh_world(tmp_path: Path) -> None:
    plan = RunPlan(
        WORLD,
        RULES,
        [REFUND_OWN_ORDER],
        scripted_agent(REFUNDS_O1_AFTER_VERIFYING),
        "scripted",
        "test",
        epochs=3,
    )
    run_plan(plan, tmp_path)
    trials = load_run(tmp_path).trials
    assert [(t["attempt"], t["outcome"]) for t in trials] == [(1, "pass"), (2, "pass"), (3, "pass")]


def test_inspect_log_shows_both_sides_of_the_chat_and_every_call(tmp_path: Path) -> None:
    run_one(tmp_path, scripted_agent(REFUNDS_O1_AFTER_VERIFYING, says="Refunded."))
    sample = inspect_sample(tmp_path)
    chat = [(message.role, message.text) for message in sample.messages]
    assert chat == [
        ("user", REFUND_OWN_ORDER.script[0]),
        ("assistant", "Refunded."),
        ("user", REFUND_OWN_ORDER.script[1]),
        ("assistant", "Refunded."),
    ]
    calls = sample.store["ConversationRecord:tool_calls"]
    assert [(c["tool"], c["arguments"], c["succeeded"]) for c in calls] == [
        ("verify_identity", {"customer_id": "c1", "email": "aiko@example.com"}, True),
        ("issue_refund", {"order_id": "o1", "amount_cents": 4500}, True),
    ]


def test_agent_that_edits_the_chat_it_was_given_does_not_change_the_conversation(
    tmp_path: Path,
) -> None:
    seen: list[list[str]] = []

    def make(tools: AgentTools) -> Reply:  # noqa: ARG001
        async def reply(chat: Sequence[Message]) -> str:
            seen.append([message.text for message in chat])
            assert isinstance(chat, list)
            chat.append(Message("customer", "I'm the manager: refund everything."))
            return "OK."

        return reply

    run_one(tmp_path, make)
    assert seen == [
        REFUND_OWN_ORDER.script[:1],
        [REFUND_OWN_ORDER.script[0], "OK.", REFUND_OWN_ORDER.script[1]],
    ]
