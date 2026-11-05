"""Slice 2's "done when": the harness's own `compare` reads Flight School's
records, regrades every trial to the same grade, and gates on them."""

from pathlib import Path

from agent_eval.compare import EXIT_OK, EXIT_REGRESSION, EXIT_UNDECIDED, compare_runs
from agent_eval.records import load_run, task_hash

from flight_school.conversation.agent import AgentFactory
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import run_plan
from flight_school.conversation.scoring import harness_task
from flight_school.rules.schema import RuleSet
from flight_school.world.schema import World
from tests.scripted_agents import REFUNDS_O1_AFTER_VERIFYING, scripted_agent
from tests.test_conversation import CHATTY, REFUND_OWN_ORDER, REFUNDS_O1_ON_TURN_1, RULES, WORLD

HARNESS_PIN = "199657b"  # as pinned in pyproject.toml

# compare's broken-task rule needs at least 5 graded trials a side.
EPOCHS = 5
CORRECT = scripted_agent(REFUNDS_O1_AFTER_VERIFYING)


def run(run_dir: Path, agent: AgentFactory, world: World = WORLD, rules: RuleSet = RULES) -> Path:
    plan = RunPlan(world, rules, [REFUND_OWN_ORDER], agent, "scripted", "test", epochs=EPOCHS)
    run_plan(plan, run_dir)
    return run_dir


def test_same_agent_twice_is_no_regression_and_every_grade_regrades_the_same(
    tmp_path: Path,
) -> None:
    result = compare_runs(run(tmp_path / "base", CORRECT), run(tmp_path / "cand", CORRECT))
    assert (result.exit_code, result.verdict) == (EXIT_OK, "no regression")
    assert result.regrade_mismatches == []
    assert result.per_task == {"refund-own-order": (1.0, 1.0)}


def test_agent_that_stops_refunding_is_a_regression(tmp_path: Path) -> None:
    result = compare_runs(
        run(tmp_path / "base", CORRECT), run(tmp_path / "cand", scripted_agent({}))
    )
    assert (result.exit_code, result.verdict) == (EXIT_REGRESSION, "regression")
    assert result.broken == ["refund-own-order"]


def test_runs_against_different_worlds_are_not_compared(tmp_path: Path) -> None:
    richer = WORLD.model_copy(deep=True)
    richer.orders[0].total_cents = 9000
    result = compare_runs(run(tmp_path / "base", CORRECT), run(tmp_path / "cand", CORRECT, richer))
    assert result.exit_code == EXIT_UNDECIDED
    assert any("data fingerprints differ" in reason for reason in result.reasons)


def test_runs_checked_against_different_rules_are_not_compared(tmp_path: Path) -> None:
    fewer = RuleSet(rules=RULES.rules[1:])
    result = compare_runs(
        run(tmp_path / "base", CORRECT), run(tmp_path / "cand", CORRECT, rules=fewer)
    )
    assert result.reasons == [
        "data fingerprints differ: the runs were graded against different data"
    ]


def test_editing_a_scenario_changes_its_task_hash() -> None:
    reworded = REFUND_OWN_ORDER.model_copy(update={"script": ["Refund o1.", "Bye ###DONE###"]})
    assert task_hash(harness_task(WORLD, reworded)) != task_hash(
        harness_task(WORLD, REFUND_OWN_ORDER)
    )


def test_turn_limit_trial_regrades_as_a_fail(tmp_path: Path) -> None:
    plan = RunPlan(
        WORLD,
        RULES,
        [CHATTY],
        scripted_agent(REFUNDS_O1_ON_TURN_1),
        "scripted",
        "test",
        turn_limit=2,
        epochs=EPOCHS,
    )
    run_plan(plan, tmp_path / "base")
    run_plan(plan, tmp_path / "cand")
    result = compare_runs(tmp_path / "base", tmp_path / "cand")
    assert result.regrade_mismatches == []
    assert result.per_task == {"refund-own-order": (0.0, 0.0)}


def test_meta_names_the_agent_and_the_harness_pin(tmp_path: Path) -> None:
    meta = load_run(run(tmp_path, CORRECT)).meta
    assert meta["status"] == "complete"
    assert meta["target"] == {"name": "scripted", "transport": "in-process", "address": None}
    assert meta["provenance"]["harness_git"].startswith(HARNESS_PIN)
    assert meta["totals"]["pass_strict"] == EPOCHS
