"""A run's records in the harness's format (ADR-018): `meta.json` and
`trials.jsonl`, which the harness's `compare` and `report` read.

Each trial is built by the harness's own `trial_from_sample`, so the
pass/fail/error rules and the limit rule are the harness's, not a copy.
Flight School adds fields the harness ignores: the shop's record of
tool calls, the rule violations (for every trial, errored ones too), the
stop marker, where the simulated customer broke character, and a model
customer's seed.
"""

import importlib.metadata
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agent_eval.export import EXPORT_VERSION, run_status, totals, trial_from_sample
from agent_eval.records import ordered_json, sha256_hex, stable_json, task_hash, write_run
from inspect_ai.log import EvalLog, EvalSample
from inspect_ai.util import Store

from flight_school.conversation.loop import ConversationRecord
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.scoring import HARNESS_SCORER_NAME, harness_task
from flight_school.rules.checks import check
from flight_school.rules.schema import RuleSet
from flight_school.world.schema import World


def data_fingerprint(world: World, rules: RuleSet, customer: str) -> str:
    """The world, the rules and the customer a run was checked against.
    The harness's `compare` refuses two runs whose fingerprints differ, so
    a model-customer run is never compared with a scripted one. Hashed from
    the parsed files, so a comment edit doesn't make runs incomparable."""
    data = {"world": world.model_dump(), "rules": rules.model_dump(), "customer": customer}
    return sha256_hex(stable_json(data))


def harness_commit() -> str | None:
    """The harness commit installed, from the git pin in pyproject.toml."""
    direct_url = importlib.metadata.distribution("agent-eval-harness").read_text("direct_url.json")
    if direct_url is None:
        return None
    vcs_info: dict[str, Any] = json.loads(direct_url).get("vcs_info", {})
    return vcs_info.get("commit_id")


def trial_with_conversation(
    sample: EvalSample, task_hashes: dict[str, str], plan: RunPlan
) -> dict[str, Any]:
    trial = trial_from_sample(sample, task_hashes)
    record = ConversationRecord(store=Store(sample.store))
    score = (sample.scores or {}).get(HARNESS_SCORER_NAME)
    # The shop's record, from the store, so a trial that crashed still
    # shows what the agent did. (In process there are no Inspect tool
    # events for the harness to read.)
    trial["tool_calls"] = record.tool_calls
    if score is not None:
        trial["violations"] = (score.metadata or {})["violations"]
    else:
        # Inspect doesn't score a trial that errored, but the checker is
        # pure, so the calls made before the error are still checked: an
        # agent that does harm and then crashes must block, not just be
        # inconclusive. The trial stays an error either way.
        violations = check(record.to_log(), plan.rules, plan.world)
        trial["violations"] = [asdict(violation) for violation in violations]
    trial["stop_marker"] = record.stop_marker
    trial["character_breaks"] = record.character_breaks
    trial["customer_seed"] = record.customer_seed
    return trial


def build_meta(
    log: EvalLog, trials: list[dict[str, Any]], task_hashes: dict[str, str], plan: RunPlan
) -> dict[str, Any]:
    return {
        "run_id": log.eval.run_id,
        "created_at": log.eval.created,
        "status": run_status(log.status, trials),
        "inspect_status": log.status,
        "suite": {
            "name": plan.suite_name,
            "sha256": sha256_hex(ordered_json(sorted(task_hashes.items()))),
            "frozen": False,
            "task_hashes": task_hashes,
            "task_tags": {task_id: [] for task_id in task_hashes},
        },
        # Scripted runs cost nothing; slice 7 fills these for model runs.
        "budget": None,
        "price": None,
        "target": {
            "name": plan.agent_name,
            "transport": plan.transport,
            "address": plan.agent_url,
        },
        "agent": {
            "model": plan.agent_name,
            "model_args": {},
            "system_prompt_sha256": None,
            "system_prompt": None,
            "tool_allowlist": sorted(plan.tool_names),
            "limits": {"turn_limit": plan.turn_limit},
            "epochs": plan.epochs,
        },
        "provenance": {
            "data_fingerprint": data_fingerprint(plan.world, plan.rules, plan.customer_name),
            "models_reported": [],
            "harness_git": harness_commit(),
            "inspect_ai_version": importlib.metadata.version("inspect-ai"),
        },
        "export_version": EXPORT_VERSION,
        "totals": totals(trials),
    }


def export_run(log: EvalLog, run_dir: Path, plan: RunPlan) -> None:
    task_hashes = {s.id: task_hash(harness_task(plan.world, s)) for s in plan.scenarios}
    trials = [trial_with_conversation(sample, task_hashes, plan) for sample in log.samples or []]
    write_run(run_dir, build_meta(log, trials, task_hashes, plan), trials)
