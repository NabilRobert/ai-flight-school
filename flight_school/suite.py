"""A suite: the folder a team keeps its shop, rules and scenarios in.

`flightschool run examples/shop` reads `world.yaml`, `rules.yaml` and
`scenarios.yaml` from the folder, checks each, and names the suite after it.
"""

from dataclasses import dataclass
from pathlib import Path

from flight_school.conversation.scenario import Scenario, load_scenarios
from flight_school.rules.schema import RuleSet, load_rules
from flight_school.world.schema import World, load_world


@dataclass(frozen=True)
class Suite:
    name: str
    world: World
    rules: RuleSet
    scenarios: list[Scenario]


def load_suite(folder: Path) -> Suite:
    world = load_world(folder / "world.yaml")
    rules = load_rules(folder / "rules.yaml")
    scenarios = load_scenarios(folder / "scenarios.yaml", world).scenarios
    return Suite(folder.resolve().name, world, rules, scenarios)
