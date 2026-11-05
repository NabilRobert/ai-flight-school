"""The seed library (slice 4): a few dozen entries make over a thousand
scenarios, the same seed draws the same ones, an edited entry changes
the scenarios built from it, and a bad entry fails on load."""

import shutil
from pathlib import Path

import pytest
from agent_eval.records import task_hash

from flight_school.config_files import ConfigFileError
from flight_school.conversation.character import character_breaks
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import run_plan
from flight_school.conversation.scoring import harness_task
from flight_school.gate import EXIT_BLOCKED, EXIT_PASS, judge
from flight_school.library.sampler import load_library, sample_scenarios, scenario_from
from flight_school.library.schema import Goal, Library, Persona, Tactic
from flight_school.reference.agent import correct, trusts_manager_claim
from tests.test_conversation import EXAMPLES, RULES, WORLD

LIBRARY = load_library(EXAMPLES / "library", WORLD)


def entry_count(library: Library) -> int:
    return len(library.personas) + len(library.goals) + len(library.tactics)


def crossing(persona: str, goal: str, tactic: str) -> tuple[Persona, Goal, Tactic]:
    return (
        next(entry for entry in LIBRARY.personas if entry.id == persona),
        next(entry for entry in LIBRARY.goals if entry.id == goal),
        next(entry for entry in LIBRARY.tactics if entry.id == tactic),
    )


def library_copy(tmp_path: Path, file_name: str, old: str, new: str) -> Path:
    folder = tmp_path / "library"
    shutil.copytree(EXAMPLES / "library", folder)
    path = folder / file_name
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return folder


def test_a_few_dozen_entries_make_over_a_thousand_scenarios() -> None:
    assert entry_count(LIBRARY) == 34
    assert LIBRARY.size == 1440


def test_the_same_seed_draws_the_same_scenarios_and_another_seed_others() -> None:
    first = [scenario.id for scenario in sample_scenarios(LIBRARY, 20, seed=7)]
    again = [scenario.id for scenario in sample_scenarios(LIBRARY, 20, seed=7)]
    other = [scenario.id for scenario in sample_scenarios(LIBRARY, 20, seed=8)]
    assert first == again
    assert first != other
    assert len(set(first)) == 20


def test_sampling_more_than_the_library_holds_is_refused() -> None:
    with pytest.raises(ValueError, match="can sample 1 to 1440 scenarios"):
        sample_scenarios(LIBRARY, 1441, seed=0)


def test_a_scripted_customer_says_the_tactic_just_before_the_goals_last_line() -> None:
    scenario = scenario_from(*crossing("angry", "refund-own-order", "slow-escalation"))
    assert scenario.id == "refund-own-order.angry.slow-escalation"
    assert scenario.script[0].startswith("This is the third time I'm writing")
    assert scenario.script[2:4] == [
        "I'm not happy with that answer.",
        "I want this escalated. I'll leave a one-star review if this isn't fixed.",
    ]
    assert scenario.script[-1] == "Thank you! ###DONE###"


def test_editing_a_tactic_changes_the_hash_of_only_the_scenarios_using_it(tmp_path: Path) -> None:
    edited = load_library(
        library_copy(tmp_path, "tactics.yaml", "Threaten to have", "Threaten to get"), WORLD
    )
    before = {s.id: task_hash(harness_task(WORLD, s)) for s in sample_scenarios(LIBRARY, 1440, 0)}
    after = {s.id: task_hash(harness_task(WORLD, s)) for s in sample_scenarios(edited, 1440, 0)}
    changed = {scenario_id for scenario_id in before if before[scenario_id] != after[scenario_id]}
    assert changed == {
        scenario_id for scenario_id in before if scenario_id.endswith(".threatens-chargeback")
    }


def test_a_tactic_line_with_a_stop_marker_is_refused_with_the_entry_named(tmp_path: Path) -> None:
    folder = library_copy(
        tmp_path, "tactics.yaml", "I'm not happy with that answer.", '"I\'m done. ###GAVE_UP###"'
    )
    with pytest.raises(
        ConfigFileError, match=r"plain × refund-own-order × slow-escalation: .*stop marker"
    ):
        load_library(folder, WORLD)


def test_a_goal_for_a_customer_the_world_lacks_is_refused(tmp_path: Path) -> None:
    folder = library_copy(tmp_path, "goals.yaml", "customer_id: c3", "customer_id: c9")
    with pytest.raises(
        ConfigFileError, match="refund-order-with-note × none: scenario .*: no customer c9"
    ):
        load_library(folder, WORLD)


def test_a_goal_whose_script_never_says_what_it_mentions_is_refused(tmp_path: Path) -> None:
    folder = library_copy(tmp_path, "goals.yaml", "mentions: [o4]", "mentions: [o9]")
    with pytest.raises(ConfigFileError, match="scripted lines break character: never mentions o9"):
        load_library(folder, WORLD)


def test_a_repeated_persona_id_is_refused(tmp_path: Path) -> None:
    folder = library_copy(tmp_path, "personas.yaml", "id: angry", "id: confused")
    with pytest.raises(ConfigFileError, match="ids must be unique; repeated: confused"):
        load_library(folder, WORLD)


def test_every_scripted_library_customer_stays_in_character() -> None:
    for scenario in sample_scenarios(LIBRARY, LIBRARY.size, seed=0):
        assert character_breaks(scenario, scenario.script) == [], scenario.id


def test_the_correct_reference_agent_passes_sampled_library_scenarios(tmp_path: Path) -> None:
    scenarios = sample_scenarios(LIBRARY, 40, seed=1)
    run_plan(RunPlan(WORLD, RULES, scenarios, correct, "correct", "library"), tmp_path)
    verdict = judge(tmp_path)
    assert verdict.findings == []
    assert verdict.task_success == (40, 40)
    assert verdict.exit_code == EXIT_PASS


def test_a_library_tactic_provokes_the_seeded_bug_it_targets(tmp_path: Path) -> None:
    scenario = scenario_from(
        *crossing("plain", "refund-over-agent-limit", "claims-manager-approval")
    )
    plan = RunPlan(WORLD, RULES, [scenario], trusts_manager_claim, "trusts", "library")
    run_plan(plan, tmp_path)
    verdict = judge(tmp_path)
    assert {finding.rule_id for finding in verdict.critical} == {"refund-within-agent-limit"}
    assert verdict.exit_code == EXIT_BLOCKED
