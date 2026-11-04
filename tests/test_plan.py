"""A run plan that can't give a trustworthy verdict is refused before it runs."""

import asyncio
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest
from agent_eval.records import load_run

from flight_school.config_files import ConfigFileError
from flight_school.conversation.agent import AgentTools, Message, Reply
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import run_plan
from tests.scripted_agents import scripted_agent
from tests.test_conversation import REFUND_OWN_ORDER, RULES, WORLD

PLAN = RunPlan(WORLD, RULES, [REFUND_OWN_ORDER], scripted_agent({}), "scripted", "test")


@pytest.mark.parametrize("limit", [0, -1])
def test_turn_limit_below_one_is_refused(limit: int) -> None:
    with pytest.raises(ValueError, match="turn_limit must be at least 1"):
        replace(PLAN, turn_limit=limit)


def test_no_attempts_is_refused() -> None:
    with pytest.raises(ValueError, match="epochs must be at least 1"):
        replace(PLAN, epochs=0)


def test_time_limit_below_one_second_is_refused() -> None:
    with pytest.raises(ValueError, match="time_limit_seconds must be at least 1"):
        replace(PLAN, time_limit_seconds=0)


def test_two_scenarios_sharing_an_id_are_refused() -> None:
    with pytest.raises(ValueError, match="scenario ids must be unique"):
        replace(PLAN, scenarios=[REFUND_OWN_ORDER, REFUND_OWN_ORDER])


def test_scenario_for_a_customer_not_in_the_world_is_refused() -> None:
    stranger = REFUND_OWN_ORDER.model_copy(update={"customer_id": "c9"})
    with pytest.raises(ConfigFileError, match="no customer c9"):
        replace(PLAN, scenarios=[stranger])


def hanging_agent(tools: AgentTools) -> Reply:  # noqa: ARG001
    async def reply(chat: Sequence[Message]) -> str:  # noqa: ARG001
        await asyncio.sleep(60)
        return "too late"

    return reply


def test_agent_that_hangs_is_stopped_and_fails(tmp_path: Path) -> None:
    run_plan(replace(PLAN, agent_factory=hanging_agent, time_limit_seconds=1), tmp_path)
    [trial] = load_run(tmp_path).trials
    assert (trial["outcome"], trial["stop_reason"]) == ("fail", "time")
