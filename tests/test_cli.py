"""`flightschool run`: the exit code CI acts on, and errors that say what to fix."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from flight_school.cli import app
from flight_school.http.serving import serve_in_thread
from flight_school.reference.http_agent import CHAT_PATH, reference_app

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


def test_sample_runs_scenarios_drawn_from_the_library(tmp_path: Path) -> None:
    agent = "flight_school.reference.agent:correct"
    code, output = flightschool(
        "run", EXAMPLES, "--agent", agent, "--out", tmp_path, "--sample", "5", "--seed", "3"
    )
    assert code == 0
    assert "task success: 5 of 5 checked trial(s)" in output


def test_sample_from_a_suite_without_a_library_is_inconclusive(tmp_path: Path) -> None:
    suite = tmp_path / "suite"
    suite.mkdir()
    for name in ("world.yaml", "rules.yaml", "scenarios.yaml"):
        (suite / name).write_text((EXAMPLES / name).read_text(encoding="utf-8"), encoding="utf-8")
    agent = "flight_school.reference.agent:correct"
    code, output = flightschool("run", suite, "--agent", agent, "--sample", "5")
    assert code == 2
    assert "suite suite has no library/ folder" in output


def test_sampling_more_than_the_library_holds_is_inconclusive() -> None:
    agent = "flight_school.reference.agent:correct"
    code, output = flightschool("run", EXAMPLES, "--agent", agent, "--sample", "5000")
    assert code == 2
    assert "can sample 1 to 1440 scenarios" in output


def test_a_model_customer_for_hand_written_scenarios_is_inconclusive() -> None:
    agent = "flight_school.reference.agent:correct"
    code, output = flightschool(
        "run", EXAMPLES, "--agent", agent, "--customer-model", "mockllm/model"
    )
    assert code == 2
    assert "needs library scenarios" in output


def test_agent_url_runs_the_suite_over_http(tmp_path: Path) -> None:
    with serve_in_thread(reference_app()) as base_url:
        code, output = flightschool(
            "run", EXAMPLES, "--agent-url", base_url + CHAT_PATH, "--out", tmp_path
        )
    assert code == 0
    assert "verdict: pass (exit 0)" in output


@pytest.mark.parametrize(
    "options",
    [[], ["--agent", "flight_school.reference.agent:correct", "--agent-url", "http://x/chat"]],
    ids=["neither", "both"],
)
def test_exactly_one_way_to_reach_the_agent_is_required(options: list[str]) -> None:
    code, output = flightschool("run", EXAMPLES, *options)
    assert code == 2
    assert "give exactly one of --agent" in output


def test_an_agent_url_with_a_password_in_it_is_refused() -> None:
    code, output = flightschool("run", EXAMPLES, "--agent-url", "http://me:secret@127.0.0.1/chat")
    assert code == 2
    assert "put the key in FLIGHTSCHOOL_AGENT_KEY" in output
    assert "secret" not in output


def test_serving_an_unknown_reference_variant_is_refused() -> None:
    code, output = flightschool("serve-reference", "--variant", "nope")
    assert code == 2
    assert "no variant 'nope'" in output
