"""What one run is: the shop, the rules, the scenarios, the agent and the
limits. The loop, the scorer and the records all read it from here.

A plan is checked when it is made, so a run that couldn't give a
trustworthy verdict (a limit that never stops anything, a scenario for a
customer who doesn't exist) never starts.
"""

from dataclasses import dataclass

from flight_school.conversation.agent import AgentFactory
from flight_school.conversation.loop import DEFAULT_TURN_LIMIT
from flight_school.conversation.scenario import Scenario, ScenarioSet, expected_world
from flight_school.rules.schema import RuleSet
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

    def __post_init__(self) -> None:
        for name in ("turn_limit", "time_limit_seconds", "epochs"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1, not {getattr(self, name)}")
        # The same checks as a scenarios file gets: unique ids, at least one.
        ScenarioSet(scenarios=self.scenarios)
        for scenario in self.scenarios:
            expected_world(self.world, scenario)
