"""A suite: the folder a team keeps its shop, rules and scenarios in.

`flightschool run examples/shop` reads `world.yaml`, `rules.yaml` and
`scenarios.yaml` from the folder, checks each, and names the suite after it.
A `library/` folder, if there is one, holds the seed library that
`flightschool run --sample` draws scenarios from.

A suite for an observed agent (A3), one that keeps its own tools, also
has a `tools.yaml` naming those tools and their arguments, so its rules
are checked against them instead of the fake shop's.
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from flight_school.config_files import load_model
from flight_school.conversation.scenario import Scenario, load_scenarios
from flight_school.library.sampler import load_library
from flight_school.library.schema import Library
from flight_school.rules.schema import SHOP_TOOL_ARGUMENTS, RuleSet, load_rules
from flight_school.world.schema import World, load_world


class ToolFile(BaseModel):
    """An observed agent's tools: each name, with its argument names."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tools: dict[str, list[str]] = Field(min_length=1)


@dataclass(frozen=True)
class Suite:
    name: str
    world: World
    rules: RuleSet
    scenarios: list[Scenario]
    library: Library | None = None
    # An observed agent's own tools; None for an agent on the fake shop.
    observed_tools: dict[str, list[str]] | None = None


def load_suite(folder: Path) -> Suite:
    world = load_world(folder / "world.yaml")
    tools_file = folder / "tools.yaml"
    observed_tools = load_model(tools_file, ToolFile).tools if tools_file.is_file() else None
    rules = load_rules(folder / "rules.yaml", observed_tools or SHOP_TOOL_ARGUMENTS)
    scenarios = load_scenarios(folder / "scenarios.yaml", world).scenarios
    library_folder = folder / "library"
    library = load_library(library_folder, world) if library_folder.is_dir() else None
    return Suite(folder.resolve().name, world, rules, scenarios, library, observed_tools)
