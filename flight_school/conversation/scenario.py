"""A scenario: who the simulated customer is, what they say, and how the
shop's data should look when the conversation is over.

Scenarios are written out in full in `scenarios.yaml`, or built from the
seed library (persona × goal × tactic, `flight_school/library/`). A
library scenario also carries what a model customer needs: its prompt
and what it must mention.

Task success is judged the way τ²-bench judges it: the world after the
conversation must equal the world before it with exactly the expected
changes applied. A refund on the wrong order, or a second refund, changes
a row nobody expected to change, and fails.
"""

import re
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from flight_school.config_files import ConfigFileError, describe, load_model
from flight_school.world.schema import COLLECTIONS, World

# How a simulated customer ends a conversation (ADR-012). A conversation
# that ends any other way (the turn limit) is never a pass. A sales
# customer may also leave without a word (thesis pilot): that is a normal
# ending there, not a broken run, so it gets its own marker.
DONE_MARKER = "###DONE###"
GAVE_UP_MARKER = "###GAVE_UP###"
GHOSTED_MARKER = "###GHOSTED###"
STOP_MARKERS = (DONE_MARKER, GAVE_UP_MARKER, GHOSTED_MARKER)

# collection -> item id -> field -> its value after the conversation.
ExpectedChanges = dict[str, dict[str, dict[str, object]]]
Row = dict[str, object]
# A kebab-case id, or library entry ids joined by dots
# ("refund-own-order.angry.insists").
ScenarioId = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)*$")]


# A model customer doesn't always copy a marker exactly. In the thesis
# pilot's 150 chats, 5 lines had `###GIVE_UP###` or `###GAVE_UP##`; read
# exactly, they didn't end the chat, and one such customer went on to
# end DONE and pass. So a marker counts with any case, two or more hashes
# each side, spaces inside, and GIVE for GAVE. Two hashes each side keep
# a hashtag such as "#done" from ending a chat.
STOP_MARKER_PATTERN = re.compile(r"#{2,}\s*(DONE|G[AI]VE[ _]?UP|GHOSTED)\s*#{2,}", re.IGNORECASE)
MARKER_BY_WORD = {"DONE": DONE_MARKER, "GAVEUP": GAVE_UP_MARKER, "GHOSTED": GHOSTED_MARKER}


def stop_marker_in(text: str) -> str | None:
    """The marker that ends the chat, written exactly; the first if a line
    has two."""
    found = STOP_MARKER_PATTERN.search(text)
    if found is None:
        return None
    word = re.sub(r"[ _]", "", found.group(1).upper()).replace("GIVE", "GAVE")
    return MARKER_BY_WORD[word]


def without_stop_markers(text: str) -> str:
    return STOP_MARKER_PATTERN.sub("", text).strip()


# What makes a trial pass: the shop's data ends as `expect` says
# (τ²-bench's check), or, where there is no data to change (a sales chat),
# the customer ends with DONE_MARKER. The second is the simulator grading
# itself, so its results must say so.
PassWhen = Literal["world_matches", "customer_done"]


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: ScenarioId
    description: str = Field(min_length=1)
    # Who the customer really is, whatever they claim in the chat.
    customer_id: str
    # The customer's lines, one per turn. The last one ends the
    # conversation with a stop marker.
    script: list[str] = Field(min_length=1)
    expect: ExpectedChanges = {}
    # Library scenarios only. A model customer plays from the prompt; a
    # customer who never says any of `mentions` has dropped its goal.
    # Every field of the three library entries ends up in the scenario,
    # so editing one changes its task hash and old runs become
    # incomparable (ADR-012).
    customer_prompt: str = ""
    mentions: list[str] = []
    pass_when: PassWhen = "world_matches"

    @model_validator(mode="after")
    def check_stop_markers(self) -> Self:
        if stop_marker_in(self.script[-1]) is None:
            raise ValueError(
                f"the script's last line must end the conversation with {' or '.join(STOP_MARKERS)}"
                " (in YAML, quote that line: an unquoted ' #' starts a comment)"
            )
        for number, line in enumerate(self.script[:-1], start=1):
            if stop_marker_in(line) is not None:
                raise ValueError(
                    f"line {number} has a stop marker, so the lines after it would never be said"
                )
        return self


class ScenarioSet(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scenarios: list[Scenario] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_ids(self) -> Self:
        ids = [scenario.id for scenario in self.scenarios]
        repeated = sorted({scenario_id for scenario_id in ids if ids.count(scenario_id) > 1})
        if repeated:
            raise ValueError(f"scenario ids must be unique; repeated: {', '.join(repeated)}")
        return self


def load_scenarios(path: Path, world: World) -> ScenarioSet:
    """Load and check every scenario against the world it will run in."""
    scenario_set = load_model(path, ScenarioSet)
    for scenario in scenario_set.scenarios:
        try:
            expected_world(world, scenario)
        except ConfigFileError as error:
            raise ConfigFileError(f"{path}: {error} Fix the file and run again.") from error
    return scenario_set


def expected_world(world: World, scenario: Scenario) -> World:
    """The world as it should be after the scenario: `world` with the
    scenario's expected changes applied, each one validated like the world
    file itself (an unknown field or a wrong type is refused)."""
    if world.customer(scenario.customer_id) is None:
        raise ConfigFileError(f"scenario {scenario.id}: no customer {scenario.customer_id}.")
    data = world.model_dump()
    for collection, changes in scenario.expect.items():
        if collection not in COLLECTIONS:
            raise ConfigFileError(
                f"scenario {scenario.id}: no collection {collection}; "
                f"the collections are {', '.join(COLLECTIONS)}."
            )
        items_by_id: dict[str, Row] = {item["id"]: item for item in data[collection]}
        for item_id, fields in changes.items():
            if item_id not in items_by_id:
                raise ConfigFileError(f"scenario {scenario.id}: no {collection} item {item_id}.")
            items_by_id[item_id].update(fields)
    try:
        return World.model_validate(data)
    except ValidationError as error:
        raise ConfigFileError(f"scenario {scenario.id}: expect: {describe(error)}") from error


def world_rows(world: World) -> list[Row]:
    """Every item in the world as one row, tagged with its collection, in
    the shape the harness's `result_match` grader compares."""
    rows: list[Row] = []
    for collection in COLLECTIONS:
        items: list[BaseModel] = getattr(world, collection)
        rows.extend({"collection": collection, **item.model_dump()} for item in items)
    return rows
