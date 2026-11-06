"""What one run is: the shop, the rules, the scenarios, the agent and the
limits. The loop, the scorer and the records all read it from here.

A plan is checked when it is made, so a run that couldn't give a
trustworthy verdict (a limit that never stops anything, a scenario for a
customer who doesn't exist) never starts.
"""

from dataclasses import dataclass

from inspect_ai.model import Model

from flight_school.conversation.agent import AgentFactory
from flight_school.conversation.loop import DEFAULT_TURN_LIMIT
from flight_school.conversation.scenario import Scenario, ScenarioSet, expected_world
from flight_school.observer.adapter import Observer
from flight_school.rules.schema import RuleSet
from flight_school.world.shop import SHOP_TOOLS
from flight_school.world.schema import World

# Wall-clock time one conversation may take before it is stopped and
# failed, so a hung agent can't hang the team's CI. A scripted run takes
# milliseconds; a model-backed agent at about 10 s a turn for the 10-turn
# limit needs about 100 s, and this leaves room for a slow provider.
DEFAULT_TIME_LIMIT_SECONDS = 300


@dataclass(frozen=True)
class RunPlan:
    world: World
    rules: RuleSet
    scenarios: list[Scenario]
    agent_factory: AgentFactory
    # Recorded as the run's target, so `compare` names a changed agent.
    agent_name: str
    suite_name: str
    turn_limit: int = DEFAULT_TURN_LIMIT
    time_limit_seconds: int = DEFAULT_TIME_LIMIT_SECONDS
    # Inspect's word for repeats: each scenario runs this many times.
    epochs: int = 1
    # None: every customer says its scripted lines, at $0. Otherwise the
    # model that plays the customers, on the team's key.
    customer_model: str | Model | None = None
    # Set when the agent is reached over HTTP (A2); recorded as the target.
    agent_url: str | None = None
    # Set when the agent keeps its own tools (A3), with their names.
    observer: Observer | None = None
    tool_names: tuple[str, ...] = tuple(SHOP_TOOLS)

    @property
    def transport(self) -> str:
        if self.observer is not None:
            return "observed"
        return "in-process" if self.agent_url is None else "http"

    @property
    def customer_name(self) -> str:
        return "scripted" if self.customer_model is None else str(self.customer_model)

    def __post_init__(self) -> None:
        for name in ("turn_limit", "time_limit_seconds", "epochs"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1, not {getattr(self, name)}")
        # The same checks as a scenarios file gets: unique ids, at least one.
        ScenarioSet(scenarios=self.scenarios)
        for scenario in self.scenarios:
            expected_world(self.world, scenario)
            if self.customer_model is not None and not scenario.customer_prompt:
                raise ValueError(
                    f"scenario {scenario.id} has no customer prompt: a model customer"
                    " needs library scenarios (flightschool run --sample)"
                )
