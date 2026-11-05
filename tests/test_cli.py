"""`flightschool run`: the exit code CI acts on, and errors that say what to fix."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from flight_school.cli import app

EXAMPLES = Path(__file__).parent.parent / "examples" / "shop"
RUNNER = CliRunner()


def flightschool(*args: str | Path) -> tuple[int, str]:
    result = RUNNER.invoke(app, [str(arg) for arg in args])
    return result.exit_code, result.output


def test_correct_reference_agent_passes(tmp_path: Path) -> None:
    agent = "flight_school.reference.agent:correct"
    code, output = flightschool("run", EXAMPLES, "--agent", agent, "--out", tmp_path)
    assert code == 0
    assert "verdict: pass (exit 0)" in output


def test_seeded_bug_is_blocked_and_named_so_it_can_be_replayed(tmp_path: Path) -> None:
    agent = "flight_school.reference.agent:obeys_order_notes"
    code, output = flightschool("run", EXAMPLES, "--agent", agent, "--out", tmp_path)
    assert code == 1
    assert "critical: order-note-with-instructions#1 turn 1 never-delete-accounts" in output


def test_a_teams_own_module_is_imported_from_where_the_command_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "my_agent.py").write_text(
        "from flight_school.reference.agent import correct as factory\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    code, _ = flightschool("run", EXAMPLES, "--agent", "my_agent:factory", "--out", "runs/x")
    assert code == 0


def test_an_agent_that_cannot_be_loaded_is_inconclusive_with_a_hint(tmp_path: Path) -> None:
    code, output = flightschool("run", EXAMPLES, "--agent", "nope:agent", "--out", tmp_path)
    assert code == 2
    assert "Give it as module:attribute" in output


def test_a_folder_without_the_suite_files_is_inconclusive_and_names_the_file(
    tmp_path: Path,
) -> None:
    agent = "flight_school.reference.agent:correct"
    code, output = flightschool("run", tmp_path, "--agent", agent, "--out", tmp_path / "out")
    assert code == 2
    assert "world.yaml: can't read it" in output


def test_same_agent_against_its_own_baseline_is_no_regression(tmp_path: Path) -> None:
    agent = "flight_school.reference.agent:correct"
    flightschool("run", EXAMPLES, "--agent", agent, "--out", tmp_path / "base")
    code, output = flightschool(
        "run",
        EXAMPLES,
        "--agent",
        agent,
        "--out",
        tmp_path / "cand",
        "--baseline",
        tmp_path / "base",
    )
    assert code == 0
    assert "task success against the baseline: no regression" in output


def test_an_agent_that_is_not_a_factory_is_refused(tmp_path: Path) -> None:
    agent = "flight_school.reference.agent:MANAGER_CODE"
    code, output = flightschool("run", EXAMPLES, "--agent", agent, "--out", tmp_path)
    assert code == 2
    assert "isn't callable" in output
