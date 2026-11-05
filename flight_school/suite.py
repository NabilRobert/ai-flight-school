"""A suite: the folder a team keeps its shop, rules and scenarios in.

`flightschool run examples/shop` reads `world.yaml`, `rules.yaml` and
`scenarios.yaml` from the folder, checks each, and names the suite after it.
A `library/` folder, if there is one, holds the seed library that
`flightschool run --sample` draws scenarios from.
"""

from dataclasses import dataclass
from pathlib import Path

from flight_school.conversation.scenario import Scenario, load_scenarios
from flight_school.library.sampler import load_library
from flight_school.library.schema import Library
from flight_school.rules.schema import RuleSet, load_rules
from flight_school.world.schema import World, load_world


@dataclass(frozen=True)
class Suite:
    name: str
    world: World
    rules: RuleSet
    scenarios: list[Scenario]
    library: Library | None = None


def load_suite(folder: Path) -> Suite:
    world = load_world(folder / "world.yaml")
    rules = load_rules(folder / "rules.yaml")
    scenarios = load_scenarios(folder / "scenarios.yaml", world).scenarios
    library_folder = folder / "library"
    library = load_library(library_folder, world) if library_folder.is_dir() else None
    return Suite(folder.resolve().name, world, rules, scenarios, library)
