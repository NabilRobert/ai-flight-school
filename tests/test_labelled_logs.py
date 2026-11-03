"""The checker's main specification: every hand-labelled tool-call log in
tests/fixtures/logs gets exactly the verdict it is labelled with (G1).

Each case is replayed through a fresh FakeShop over examples/shop, so the
shop decides which calls succeeded, then checked with every example rule.
"""

from collections import Counter
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ConfigDict

from flight_school.log import AgentReply, ConversationLog
from flight_school.rules.checks import check
from flight_school.rules.schema import load_rules
from flight_school.world.schema import load_world
from flight_school.world.shop import FakeShop

EXAMPLES = Path(__file__).parent.parent / "examples" / "shop"
LOGS = Path(__file__).parent / "fixtures" / "logs"
WORLD = load_world(EXAMPLES / "world.yaml")
RULES = load_rules(EXAMPLES / "rules.yaml")


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn: int
    call: str | None = None
    arguments: dict[str, object] = {}
    reply: str | None = None


class LabelledCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    customer: str
    steps: list[Step]
    expected: list[str]


class LabelledFile(BaseModel):
    cases: list[LabelledCase]


def load_cases() -> list[LabelledCase]:
    cases: list[LabelledCase] = []
    for path in sorted(LOGS.glob("*.yaml")):
        cases.extend(LabelledFile.model_validate(yaml.safe_load(path.read_text())).cases)
    return cases


def replay(case: LabelledCase) -> ConversationLog:
    shop = FakeShop(WORLD)
    replies: list[AgentReply] = []
    for step in case.steps:
        if step.call is not None:
            shop.call(step.turn, step.call, step.arguments)
        if step.reply is not None:
            replies.append(AgentReply(step.turn, step.reply))
    return ConversationLog(case.customer, shop.calls, replies)


def verdict(case: LabelledCase) -> Counter[str]:
    return Counter(violation.rule_id for violation in check(replay(case), RULES, WORLD))


CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_labelled_log_gets_exactly_its_expected_violations(case: LabelledCase) -> None:
    assert verdict(case) == Counter(case.expected)


def test_case_names_are_unique() -> None:
    names = [case.name for case in CASES]
    assert len(names) == len(set(names))


def test_every_example_rule_fires_in_some_labelled_log() -> None:
    fired_somewhere = {rule_id for case in CASES for rule_id in case.expected}
    assert {rule.id for rule in RULES.rules} <= fired_somewhere
