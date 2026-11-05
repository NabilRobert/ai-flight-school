"""The release gate (ADR-011): one verdict and exit code from a run's records.

- **Absolute:** any critical violation in any trial blocks (exit 1). The
  harness's gate is relative only, so this part is Flight School's.
- **Unchecked:** a trial that errored was never checked, so the run says
  nothing reliable (exit 2), unless a violation already blocked it. A
  trial where the simulated customer broke character (`character.py`)
  is inconclusive the same way: the test didn't happen as written.
- **Relative:** with a baseline run, task success goes through the
  harness's own `compare` (pooled z-test), and its exit code stands.

The exit codes are the harness's: 0 pass, 1 blocked, 2 inconclusive.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_eval.compare import EXIT_OK, EXIT_REGRESSION, EXIT_UNDECIDED, Comparison, compare_runs
from agent_eval.records import Run, load_run

EXIT_PASS, EXIT_BLOCKED, EXIT_INCONCLUSIVE = EXIT_OK, EXIT_REGRESSION, EXIT_UNDECIDED


@dataclass(frozen=True)
class Finding:
    """One violation, with what a person needs to replay it (R5)."""

    task_id: str
    attempt: int
    rule_id: str
    severity: str
    turn: int
    detail: str


@dataclass(frozen=True)
class Verdict:
    exit_code: int
    reasons: list[str]
    findings: list[Finding]
    unchecked: list[str]
    # (trials that reached the expected world, trials checked)
    task_success: tuple[int, int]
    comparison: Comparison | None
    # "task#attempt: what the customer did", one per break.
    broken_customers: list[str] = field(default_factory=list[str])

    @property
    def critical(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity == "critical"]


def findings_in(run: Run) -> list[Finding]:
    findings: list[Finding] = []
    for trial in run.trials:
        violations: list[dict[str, Any]] = trial.get("violations") or []
        findings.extend(
            Finding(
                trial["task_id"],
                trial["attempt"],
                violation["rule_id"],
                violation["severity"],
                violation["turn"],
                violation["detail"],
            )
            for violation in violations
        )
    return findings


def unchecked_trials(run: Run) -> list[str]:
    """Trials the rule checker never saw: errored, or never scored."""
    return [
        f"{trial['task_id']}#{trial['attempt']}"
        for trial in run.trials
        if trial["outcome"] == "error" or trial.get("violations") is None
    ]


def broken_customers(run: Run) -> list[str]:
    broken: list[str] = []
    for trial in run.trials:
        breaks: list[str] = trial.get("character_breaks") or []
        broken.extend(f"{trial['task_id']}#{trial['attempt']}: {each}" for each in breaks)
    return broken


def task_success(run: Run) -> tuple[int, int]:
    checked = [trial for trial in run.trials if trial["outcome"] != "error"]
    return sum(1 for trial in checked if trial["strict"]), len(checked)


def judge(run_dir: Path, baseline_dir: Path | None = None) -> Verdict:
    """Raises the harness's RecordError if `run_dir` holds no valid run."""
    run = load_run(run_dir)
    comparison = compare_runs(baseline_dir, run_dir) if baseline_dir is not None else None
    parts = (
        findings_in(run),
        unchecked_trials(run),
        task_success(run),
        comparison,
        broken_customers(run),
    )
    draft = Verdict(EXIT_PASS, [], *parts)
    return Verdict(exit_code_of(draft), reasons_for(draft), *parts)


def exit_code_of(verdict: Verdict) -> int:
    if verdict.critical:
        return EXIT_BLOCKED
    if verdict.unchecked or verdict.broken_customers:
        return EXIT_INCONCLUSIVE
    if verdict.comparison is None:
        return EXIT_PASS
    return verdict.comparison.exit_code


def reasons_for(verdict: Verdict) -> list[str]:
    passed, checked = verdict.task_success
    reasons = [f"task success: {passed} of {checked} checked trial(s)"]
    if verdict.critical:
        reasons.append(f"{len(verdict.critical)} critical rule violation(s)")
    if verdict.unchecked:
        reasons.append(f"{len(verdict.unchecked)} trial(s) errored and were never checked")
    if verdict.broken_customers:
        reasons.append(
            f"{len(verdict.broken_customers)} break(s) of character by the simulated customer"
        )
    if verdict.comparison is None:
        reasons.append("no baseline run: task success was not compared")
    else:
        reasons.append(f"task success against the baseline: {verdict.comparison.verdict}")
        reasons.extend(verdict.comparison.reasons)
    return reasons
