"""`flightschool`: the command a team's CI runs (ADR-017).

- `flightschool run SUITE --agent module:factory` runs every scenario
  against the agent, writes the records, and exits with the gate's code:
  0 pass, 1 blocked, 2 inconclusive.
- `flightschool accuracy` measures Flight School itself on the reference
  agent's seeded bugs, at $0.
"""

import pkgutil
import sys
from pathlib import Path
from typing import Annotated, cast

import typer
from agent_eval.records import RecordError

from flight_school.config_files import ConfigFileError
from flight_school.conversation.agent import AgentFactory
from flight_school.conversation.loop import DEFAULT_TURN_LIMIT
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import run_plan
from flight_school.gate import EXIT_INCONCLUSIVE, Verdict, judge
from flight_school.reference.accuracy import accuracy_from_records, render, run_every_variant
from flight_school.suite import load_suite

app = typer.Typer(no_args_is_help=True, help="Simulated customers against your support agent.")

VERDICT_NAMES = {0: "pass", 1: "blocked", 2: "inconclusive"}


class AgentLoadError(Exception):
    """The --agent option doesn't name an importable agent factory."""


def load_agent(spec: str) -> AgentFactory:
    # The team's own modules import from where the command runs, as they
    # would in their tests (uvicorn's --app-dir does the same).
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    try:
        factory: object = pkgutil.resolve_name(spec)
    except (ImportError, AttributeError, ValueError) as error:
        raise AgentLoadError(
            f"can't load agent {spec!r} ({error}). Give it as module:attribute, "
            "for example flight_school.reference.agent:correct."
        ) from error
    if not callable(factory):
        raise AgentLoadError(f"{spec!r} isn't callable: it must be an agent factory.")
    return cast(AgentFactory, factory)


def print_verdict(verdict: Verdict, run_dir: Path) -> None:
    print(f"verdict: {VERDICT_NAMES[verdict.exit_code]} (exit {verdict.exit_code})")
    for reason in verdict.reasons:
        print(f"  reason: {reason}")
    for finding in verdict.findings:
        print(
            f"  {finding.severity}: {finding.task_id}#{finding.attempt} turn {finding.turn} "
            f"{finding.rule_id}: {finding.detail}"
        )
    for trial in verdict.unchecked:
        print(f"  unchecked: {trial}")
    print(f"records: {run_dir}")


def fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(EXIT_INCONCLUSIVE)


@app.command()
def run(  # noqa: PLR0913 -- each parameter is one of the command's options
    suite: Annotated[Path, typer.Argument(help="folder with world, rules and scenarios")],
    agent: Annotated[str, typer.Option(help="your agent factory, as module:attribute")],
    out: Annotated[Path, typer.Option(help="records folder (replaced)")] = Path(
        "runs/flightschool"
    ),
    baseline: Annotated[Path | None, typer.Option(help="a baseline run to compare with")] = None,
    epochs: Annotated[int, typer.Option(min=1, help="runs of each scenario")] = 1,
    turn_limit: Annotated[int, typer.Option(min=1)] = DEFAULT_TURN_LIMIT,
) -> None:
    """Run every scenario against the agent and gate on the result."""
    try:
        loaded = load_suite(suite)
        factory = load_agent(agent)
    except (ConfigFileError, AgentLoadError) as error:
        raise fail(str(error)) from error
    plan = RunPlan(
        loaded.world,
        loaded.rules,
        loaded.scenarios,
        factory,
        agent_name=agent,
        suite_name=loaded.name,
        turn_limit=turn_limit,
        epochs=epochs,
    )
    run_plan(plan, out)
    try:
        verdict = judge(out, baseline)
    except RecordError as error:
        raise fail(str(error)) from error
    print_verdict(verdict, out)
    raise typer.Exit(verdict.exit_code)


@app.command()
def accuracy(
    suite: Annotated[Path, typer.Argument()] = Path("examples/shop"),
    out: Annotated[Path, typer.Option(help="records folder (replaced)")] = Path("runs/accuracy"),
    report: Annotated[Path | None, typer.Option(help="also write the report here")] = None,
) -> None:
    """Run every reference variant; exit 1 unless every seeded bug is
    caught and the correct variant passes."""
    try:
        loaded = load_suite(suite)
    except ConfigFileError as error:
        raise fail(str(error)) from error
    run_every_variant(loaded, out)
    result = accuracy_from_records(out)
    text = render(result)
    print(text, end="")
    if report is not None:
        report.write_text(text, encoding="utf-8")
    raise typer.Exit(0 if result.is_clean else 1)
