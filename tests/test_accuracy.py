"""Slice 3's "done when", at $0: every seeded bug is caught in every trial,
the correct variant raises no false alarm, and the verdicts repeat."""

import shutil
from pathlib import Path
from typing import get_args

import pytest

from flight_school.reference.accuracy import (
    SEEDED_BUGS,
    Accuracy,
    BugResult,
    SeededBug,
    accuracy_from_records,
    bug_result,
    run_every_variant,
    run_variant,
)
from flight_school.gate import EXIT_BLOCKED, Verdict
from flight_school.reference.agent import Bug, reference_agent
from flight_school.suite import load_suite

SUITE = load_suite(Path(__file__).parent.parent / "examples" / "shop")


@pytest.fixture(scope="module")
def accuracy_runs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("accuracy")
    run_every_variant(SUITE, out)
    return out


@pytest.fixture(scope="module")
def accuracy(accuracy_runs: Path) -> Accuracy:
    return accuracy_from_records(accuracy_runs)


def test_every_bug_the_agent_can_have_has_a_scenario_and_rule_in_the_suite() -> None:
    assert sorted(seeded.bug for seeded in SEEDED_BUGS) == sorted(get_args(Bug))
    scenario_ids = {scenario.id for scenario in SUITE.scenarios}
    rule_ids = {rule.id for rule in SUITE.rules.rules}
    for seeded in SEEDED_BUGS:
        assert seeded.scenario_id in scenario_ids
        assert seeded.rule_id in rule_ids


def test_every_seeded_bug_is_caught_in_every_trial_and_blocked(accuracy: Accuracy) -> None:
    missed = [result.seeded.bug for result in accuracy.bugs if not result.is_found]
    assert missed == []


def test_correct_variant_has_no_false_alarm(accuracy: Accuracy) -> None:
    assert accuracy.correct.exit_code == 0
    assert accuracy.correct.findings == []
    passed, checked = accuracy.correct.task_success
    assert passed == checked > 0


def test_same_agent_twice_gives_the_same_verdict(
    accuracy: Accuracy, accuracy_runs: Path, tmp_path: Path
) -> None:
    # The accuracy run already judged "correct" against a second run of itself.
    assert accuracy.correct.comparison is not None
    assert accuracy.correct.comparison.verdict == "no regression"
    seeded = SEEDED_BUGS[0]
    shutil.copytree(accuracy_runs / "baseline", tmp_path / "baseline")
    run_variant(SUITE, reference_agent(seeded.bug), seeded.bug, tmp_path / seeded.bug)
    [first] = [result for result in accuracy.bugs if result.seeded == seeded]
    again = bug_result(seeded, tmp_path)
    assert (again.verdict.exit_code, again.verdict.findings) == (
        first.verdict.exit_code,
        first.verdict.findings,
    )


def test_the_report_comes_from_the_records(accuracy_runs: Path, tmp_path: Path) -> None:
    # Swap one bug's records for the correct agent's: the report must notice.
    out = tmp_path / "swapped"
    shutil.copytree(accuracy_runs, out)
    bug = SEEDED_BUGS[0].bug
    shutil.rmtree(out / bug)
    shutil.copytree(out / "correct", out / bug)
    [swapped] = [r for r in accuracy_from_records(out).bugs if r.seeded.bug == bug]
    assert not swapped.is_found
    assert swapped.caught == 0


def test_a_bug_counts_as_caught_only_by_the_rule_expected_to_catch_it(
    accuracy_runs: Path,
) -> None:
    wrong_rule = SeededBug("skips-verification", "refund-without-proof", "own-account-only")
    assert bug_result(wrong_rule, accuracy_runs).caught == 0


def test_a_bug_caught_in_only_some_trials_is_not_found() -> None:
    blocked = Verdict(EXIT_BLOCKED, [], [], [], (0, 5), None)
    assert not BugResult(SEEDED_BUGS[0], blocked, caught=4, trials=5).is_found
    assert BugResult(SEEDED_BUGS[0], blocked, caught=5, trials=5).is_found


def test_a_violation_on_the_correct_variant_spoils_the_result(
    accuracy_runs: Path, tmp_path: Path
) -> None:
    out = tmp_path / "swapped"
    shutil.copytree(accuracy_runs, out)
    shutil.rmtree(out / "correct")
    shutil.copytree(out / SEEDED_BUGS[0].bug, out / "correct")
    assert not accuracy_from_records(out).is_clean


def test_the_untouched_accuracy_run_is_clean(accuracy: Accuracy) -> None:
    assert accuracy.is_clean
