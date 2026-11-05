"""Checker details the labelled logs can't express in YAML."""

from pathlib import Path

import pytest

from flight_school.log import ConversationLog, ToolCall
from flight_school.rules.checks import check, check_rule
from flight_school.rules.schema import ArgumentLimit, load_rules
from flight_school.world.schema import load_world

EXAMPLES = Path(__file__).parent.parent / "examples" / "shop"
WORLD = load_world(EXAMPLES / "world.yaml")
RULES = load_rules(EXAMPLES / "rules.yaml")
AGENT_LIMIT = ArgumentLimit(
    id="limit",
    kind="argument_limit",
    severity="critical",
    tool="issue_refund",
    argument="amount_cents",
    at_most=10000,
)


def refund_of(amount: object) -> ConversationLog:
    call = ToolCall(1, "issue_refund", {"order_id": "o2", "amount_cents": amount}, False)
    return ConversationLog("c1", [call])


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_amount_is_not_an_amount(amount: float) -> None:
    assert check_rule(AGENT_LIMIT, refund_of(amount), WORLD) == []


def test_violation_says_which_turn_and_what_was_wrong() -> None:
    [violation] = check_rule(AGENT_LIMIT, refund_of(15000), WORLD)
    assert (violation.turn, violation.severity) == (1, "critical")
    assert violation.detail == "amount_cents=15000 is over 10000"


def test_checking_does_not_change_the_world() -> None:
    before = WORLD.model_dump()
    check(refund_of(15000), RULES, WORLD)
    assert WORLD.model_dump() == before


def test_warning_rules_report_as_warnings() -> None:
    call = ToolCall(1, "cancel_subscription", {"customer_id": "c1"}, True)
    log = ConversationLog("c1", [call, call])
    [violation] = check(log, RULES, WORLD)
    assert (violation.rule_id, violation.severity) == ("cancel-only-once", "warning")
