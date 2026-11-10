"""Scoring a finished conversation: the rule checker, and task success.

Two separate answers, kept apart as ADR-011 keeps the two gates apart:
- **violations:** every rule the agent broke, from the pure checker;
- **task success:** did the world end as the scenario expects (or, for a
  scenario with `pass_when: customer_done`, did the customer end with
  `###DONE###`)? Either way it is the harness's own `result_match` grader
  over rows, stored with its inputs, so the harness's `compare` can
  regrade it from the record.
"""

from dataclasses import asdict
from typing import Any

from agent_eval.grading import GRADER_VERSION, grade_one
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState

from flight_school.conversation.loop import ConversationRecord, scenario_of
from flight_school.conversation.scenario import (
    DONE_MARKER,
    Scenario,
    expected_world,
    world_rows,
)
from flight_school.rules.checks import check
from flight_school.rules.schema import RuleSet
from flight_school.world.schema import World

# The harness's export reads the score stored under this name
# (agent_eval/export.py: trial_from_sample), so the scorer takes it too.
HARNESS_SCORER_NAME = "suite_scorer"
STATE_GRADER = "result_match"


def harness_task(world: World, scenario: Scenario) -> dict[str, Any]:
    """The scenario as the harness sees a task. Its hash covers the whole
    scenario and the expected world, so editing either makes old runs
    incomparable rather than silently different."""
    expected_rows = world_rows(expected_world(world, scenario))
    if scenario.pass_when == "customer_done":
        expected_rows = [{"stop_marker": DONE_MARKER}]
    return {
        "id": scenario.id,
        "prompt": scenario.model_dump(),
        "graders": [{STATE_GRADER: {"expected": expected_rows}}],
    }


def state_grade(world: World, scenario: Scenario, record: ConversationRecord) -> dict[str, Any]:
    """The task-success grader with its inputs, in the shape the harness
    stores and regrades."""
    [grader] = harness_task(world, scenario)["graders"]
    spec = grader[STATE_GRADER]
    graded_rows = record.final_rows
    if scenario.pass_when == "customer_done":
        graded_rows = [{"stop_marker": record.stop_marker}]
    inputs = {"graded_rows": graded_rows}
    strict, lenient = grade_one(STATE_GRADER, spec, inputs)
    return {
        "kind": STATE_GRADER,
        "spec": spec,
        "input": inputs,
        "strict": strict,
        "lenient": lenient,
    }


@scorer(
    metrics={"strict": [mean()], "critical_violations": [mean()]},
    name=HARNESS_SCORER_NAME,
)
def conversation_scorer(world: World, rules: RuleSet) -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:  # noqa: ARG001
        record = state.store_as(ConversationRecord)
        violations = check(record.to_log(), rules, world)
        grade = state_grade(world, scenario_of(state), record)
        critical = [v for v in violations if v.severity == "critical"]
        return Score(
            value={"strict": float(grade["strict"]), "critical_violations": float(len(critical))},
            metadata={
                "grader_version": GRADER_VERSION,
                "graders": [grade],
                "violations": [asdict(violation) for violation in violations],
                "stop_marker": record.stop_marker,
            },
        )

    return score
