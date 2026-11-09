"""Running a plan: one Inspect sample per scenario, the loop as solver,
the checker as scorer, then the records in the harness's format.

The agent runs in process, so Inspect's own model is `none`. A scripted
customer calls no model and the run costs $0; a model customer is
Inspect's `user` role, and a model-backed agent's model its `agent` role.
"""

from pathlib import Path

from inspect_ai import Task

# Inspect's own signature has a partly untyped parameter (`scanner`).
from inspect_ai import eval as inspect_eval  # pyright: ignore[reportUnknownVariableType]
from inspect_ai.dataset import Sample
from inspect_ai.model import Model

from flight_school.conversation.environment import run_models
from flight_school.conversation.loop import conversation
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.records import export_run
from flight_school.conversation.scoring import conversation_scorer

# Inspect's own log goes here, inside the run's folder, next to the records.
INSPECT_LOG_FOLDER = "inspect"


def build_task(plan: RunPlan) -> Task:
    dataset = [
        Sample(
            id=scenario.id, input=scenario.description, metadata={"scenario": scenario.model_dump()}
        )
        for scenario in plan.scenarios
    ]
    return Task(
        dataset=dataset,
        solver=conversation(
            plan.agent_factory,
            plan.world,
            plan.turn_limit,
            has_model_customer=plan.customer_model is not None,
        ),
        scorer=conversation_scorer(plan.world, plan.rules),
        time_limit=plan.time_limit_seconds,
    )


def model_roles(plan: RunPlan) -> dict[str, str | Model] | None:
    roles = {"user": plan.customer_model, "agent": plan.agent_model}
    named = {role: model for role, model in roles.items() if model is not None}
    return named or None


def run_plan(plan: RunPlan, run_dir: Path) -> None:
    """Run every scenario `plan.epochs` times and write the run's records."""
    models = run_models(plan.customer_model, plan.agent_model)
    [log] = inspect_eval(
        build_task(plan),
        model="none",
        model_roles=model_roles(plan),
        epochs=plan.epochs,
        log_dir=str(run_dir / INSPECT_LOG_FOLDER),
        display="none",
        # One crashing conversation becomes an errored trial; it doesn't
        # stop the others. The harness's run status says if too many did.
        fail_on_error=False,
    )
    export_run(log, run_dir, plan, models)
