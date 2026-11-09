"""`flightschool`: the command a team's CI runs (ADR-017).

- `flightschool run SUITE --agent module:factory` runs every scenario
  against the agent, writes the records, and exits with the gate's code:
  0 pass, 1 blocked, 2 inconclusive. `--sample N --seed S` runs N
  scenarios drawn from the suite's seed library instead, and
  `--customer-model` has a model play the customers. `--agent-model`
  gives a model-backed in-process agent its model. `--agent-url`
  reaches an agent over HTTP instead, with its tools served over MCP;
  add `--audit-log` and `--caller` for an agent that keeps its own tools
  behind mcp-gateway, whose calls are read from the gateway's log.
- `flightschool serve-reference` serves the reference agent over HTTP,
  to try `--agent-url` against.
- `flightschool accuracy` measures Flight School itself on the reference
  agent's seeded bugs, at $0.
- `flightschool pairs RUN_A RUN_B` says where two runs' paired chats
  first differ, for an A/B comparison.
"""

import pkgutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit
from pathlib import Path
from typing import Annotated, cast, get_args

import typer
import uvicorn
from agent_eval.records import RecordError

from flight_school.config_files import ConfigFileError
from flight_school.conversation.agent import AgentFactory
from flight_school.conversation.environment import ModelEnvironmentError
from flight_school.conversation.loop import DEFAULT_TURN_LIMIT
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.scenario import Scenario
from flight_school.conversation.run import run_plan
from flight_school.export.pairs import PairingError, pair_runs, summary
from flight_school.gate import EXIT_INCONCLUSIVE, Verdict, judge
from flight_school.http.adapter import http_agent
from flight_school.http.serving import LOCALHOST
from flight_school.http.tool_server import running_tool_server
from flight_school.reference.accuracy import accuracy_from_records, render, run_every_variant
from flight_school.reference.agent import Bug
from flight_school.reference.http_agent import reference_app
from flight_school.library.sampler import sample_scenarios
from flight_school.observer.adapter import Observer, observed_agent
from flight_school.suite import Suite, load_suite
from flight_school.world.shop import SHOP_TOOLS

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


def checked_agent_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise AgentLoadError(f"--agent-url {url!r} isn't an http(s) URL.")
    if parts.username or parts.password:
        raise AgentLoadError(
            "--agent-url has a user name or password in it, which would end up in the records:"
            " put the key in FLIGHTSCHOOL_AGENT_KEY instead."
        )
    return url


def observer_for(suite: Suite, audit_log: Path | None, caller: str | None) -> Observer | None:
    """An observed suite (one with tools.yaml) needs the gateway's log and
    caller; a suite on the fake shop takes neither."""
    if suite.observed_tools is None:
        if audit_log is not None or caller is not None:
            raise AgentLoadError(
                f"--audit-log and --caller are for an observed agent's suite (one with a"
                f" tools.yaml); {suite.name} runs on the fake shop."
            )
        return None
    if audit_log is None or caller is None:
        raise AgentLoadError(
            f"suite {suite.name} is for an agent that keeps its own tools: give --audit-log"
            " (the gateway's audit log) and --caller (the agent's gateway key name)."
        )
    return Observer(audit_log, caller)


@contextmanager
def reaching_agent(
    agent: str | None, agent_url: str | None, observer: Observer | None
) -> Iterator[AgentFactory]:
    """The agent's factory; for --agent-url on the fake shop, with the MCP
    tool server running until the block ends."""
    if (agent is None) == (agent_url is None):
        raise AgentLoadError("give exactly one of --agent (in process) or --agent-url (HTTP).")
    if agent is not None:
        if observer is not None:
            raise AgentLoadError("an observed agent is reached over HTTP: give --agent-url.")
        yield load_agent(agent)
        return
    url = checked_agent_url(agent_url or "")
    if observer is not None:
        yield observed_agent(url, observer)
        return
    with running_tool_server() as tool_server:
        yield http_agent(url, tool_server)


def scenarios_to_run(suite: Suite, sample: int, seed: int) -> list[Scenario]:
    """The hand-written scenarios, or `sample` drawn from the library."""
    if sample == 0:
        return suite.scenarios
    if suite.library is None:
        raise ConfigFileError(f"suite {suite.name} has no library/ folder to sample from.")
    try:
        return sample_scenarios(suite.library, sample, seed)
    except ValueError as error:
        raise ConfigFileError(f"--sample: {error}.") from error


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
    for broken in verdict.broken_customers:
        print(f"  customer broke character: {broken}")
    print(f"records: {run_dir}")


def fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(EXIT_INCONCLUSIVE)


@app.command()
def run(  # noqa: PLR0913 -- each parameter is one of the command's options
    suite: Annotated[Path, typer.Argument(help="folder with world, rules and scenarios")],
    agent: Annotated[str | None, typer.Option(help="your agent factory, module:attribute")] = None,
    agent_url: Annotated[str | None, typer.Option(help="your agent's chat endpoint")] = None,
    out: Annotated[Path, typer.Option(help="records folder (replaced)")] = Path(
        "runs/flightschool"
    ),
    baseline: Annotated[Path | None, typer.Option(help="a baseline run to compare with")] = None,
    epochs: Annotated[int, typer.Option(min=1, help="runs of each scenario")] = 1,
    turn_limit: Annotated[int, typer.Option(min=1)] = DEFAULT_TURN_LIMIT,
    sample: Annotated[int, typer.Option(min=0, help="draw this many from the library")] = 0,
    seed: Annotated[int, typer.Option(help="which scenarios --sample draws")] = 0,
    customer_model: Annotated[
        str | None, typer.Option(help="Inspect model for the customers; costs on your key")
    ] = None,
    agent_model: Annotated[
        str | None, typer.Option(help="Inspect model for a model-backed --agent")
    ] = None,
    audit_log: Annotated[
        Path | None, typer.Option(help="observed agent: the gateway's audit log")
    ] = None,
    caller: Annotated[str | None, typer.Option(help="observed agent: its gateway caller")] = None,
) -> None:
    """Run every scenario against the agent and gate on the result."""
    try:
        loaded = load_suite(suite)
        scenarios = scenarios_to_run(loaded, sample, seed)
        observer = observer_for(loaded, audit_log, caller)
        with reaching_agent(agent, agent_url, observer) as factory:
            plan = RunPlan(
                loaded.world,
                loaded.rules,
                scenarios,
                factory,
                agent_name=agent or agent_url or "",
                suite_name=loaded.name,
                turn_limit=turn_limit,
                epochs=epochs,
                customer_model=customer_model,
                agent_model=agent_model,
                agent_url=agent_url,
                observer=observer,
                tool_names=tuple(loaded.observed_tools or SHOP_TOOLS),
            )
            run_plan(plan, out)
    except (ConfigFileError, AgentLoadError, ModelEnvironmentError, ValueError) as error:
        raise fail(str(error)) from error
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


@app.command()
def serve_reference(
    variant: Annotated[str, typer.Option(help="correct, or a seeded bug's name")] = "correct",
    port: Annotated[int, typer.Option()] = 8000,
) -> None:
    """Serve the reference agent's chat endpoint on this machine, at /chat."""
    bugs: tuple[str, ...] = get_args(Bug)
    bug = None if variant == "correct" else variant
    if bug is not None and bug not in bugs:
        raise fail(f"no variant {variant!r}; use correct or one of {', '.join(bugs)}.")
    uvicorn.run(
        reference_app(cast(Bug | None, bug)), host=LOCALHOST, port=port, log_level="warning"
    )


@app.command()
def pairs(
    run_a: Annotated[Path, typer.Argument()], run_b: Annotated[Path, typer.Argument()]
) -> None:
    """Where each pair of chats in two runs first differs."""
    try:
        print(summary(pair_runs(run_a, run_b)), end="")
    except PairingError as error:
        raise fail(str(error)) from error
