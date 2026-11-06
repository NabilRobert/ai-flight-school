"""The observer adapter (slice 6, A3) on the Shiori suite, against a stub
Shiori that writes gateway audit lines: each seeded bug is blocked by the
rule it breaks and nothing else, the correct stub passes, and a suite
that needs the observer can't be run without it."""

from pathlib import Path

import pytest
from agent_eval.records import load_run

from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import run_plan
from flight_school.gate import EXIT_INCONCLUSIVE, judge
from flight_school.http.serving import serve_in_thread
from flight_school.observer.adapter import Observer, observed_agent
from flight_school.suite import load_suite
from tests.observed_stub import CALLER, CHAT_PATH, STUB_BUGS, StubBug, stub_app
from tests.test_cli import EXAMPLES as SHOP_EXAMPLES
from tests.test_cli import flightschool

SHIORI = Path(__file__).parent.parent / "examples" / "shiori"
SUITE = load_suite(SHIORI)
EXPECTED_FINDINGS: dict[StubBug | None, set[tuple[str, str]]] = {
    None: set(),
    "replans-as-often-as-asked": {("asks-for-many-plans", "replan-at-most-once")},
    "repeats-other-learners-notes": {("claims-to-be-another-learner", "no-other-learners-notes")},
    "obeys-planted-note": {
        ("follows-planted-note", "replan-at-most-once"),
        ("follows-planted-note", "no-planted-code"),
    },
}


def run_observed(run_dir: Path, agent_url: str, audit_log: Path) -> Path:
    observer = Observer(audit_log, CALLER)
    plan = RunPlan(
        SUITE.world,
        SUITE.rules,
        SUITE.scenarios,
        observed_agent(agent_url, observer),
        agent_name="shiori",
        suite_name=SUITE.name,
        agent_url=agent_url,
        observer=observer,
        tool_names=tuple(SUITE.observed_tools or {}),
    )
    run_plan(plan, run_dir)
    return run_dir


@pytest.mark.parametrize("bug", STUB_BUGS, ids=lambda bug: bug or "correct")
def test_each_stub_variant_is_blocked_by_exactly_the_rule_it_breaks(
    tmp_path: Path, bug: StubBug | None
) -> None:
    audit_log = tmp_path / "audit.jsonl"
    audit_log.touch()
    with serve_in_thread(stub_app(audit_log, bug)) as base_url:
        verdict = judge(run_observed(tmp_path / "run", base_url + CHAT_PATH, audit_log))
    assert {(f.task_id, f.rule_id) for f in verdict.findings} == EXPECTED_FINDINGS[bug]
    assert verdict.exit_code == (0 if bug is None else 1)


def test_the_records_name_the_agent_as_observed_with_its_own_tools(tmp_path: Path) -> None:
    audit_log = tmp_path / "audit.jsonl"
    audit_log.touch()
    with serve_in_thread(stub_app(audit_log)) as base_url:
        run_observed(tmp_path / "run", base_url + CHAT_PATH, audit_log)
    meta = load_run(tmp_path / "run").meta
    assert meta["target"]["transport"] == "observed"
    assert "request_replan" in meta["agent"]["tool_allowlist"]


def test_a_missing_audit_log_makes_the_run_inconclusive_not_a_pass(tmp_path: Path) -> None:
    with serve_in_thread(stub_app(tmp_path / "elsewhere.jsonl")) as base_url:
        verdict = judge(run_observed(tmp_path / "run", base_url + CHAT_PATH, tmp_path / "no.jsonl"))
    assert verdict.exit_code == EXIT_INCONCLUSIVE


def test_the_cli_runs_an_observed_suite(tmp_path: Path) -> None:
    audit_log = tmp_path / "audit.jsonl"
    audit_log.touch()
    with serve_in_thread(stub_app(audit_log, "obeys-planted-note")) as base_url:
        code, output = flightschool(
            "run", SHIORI, "--agent-url", base_url + CHAT_PATH,
            "--audit-log", audit_log, "--caller", CALLER, "--out", tmp_path / "run",
        )  # fmt: skip
    assert code == 1
    assert "follows-planted-note#1 turn 1 no-planted-code" in output


@pytest.mark.parametrize(
    ("suite", "options", "hint"),
    [
        (SHIORI, ["--agent-url", "http://127.0.0.1:1/chat"], "give --audit-log"),
        (
            SHOP_EXAMPLES,
            ["--agent-url", "http://127.0.0.1:1/chat", "--caller", CALLER],
            "fake shop",
        ),
        (SHIORI, ["--agent", "x:y", "--audit-log", "a", "--caller", CALLER], "give --agent-url"),
    ],
    ids=["observed-suite-unobserved", "shop-suite-observed", "observed-in-process"],
)
def test_the_observer_options_must_match_the_suite(
    suite: Path, options: list[str], hint: str
) -> None:
    code, output = flightschool("run", suite, *options)
    assert code == 2
    assert hint in output
