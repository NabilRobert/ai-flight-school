"""From the seed library to scenarios (ADR-012): load the entries, cross
them, and sample a fixed number of crossings with a seed.

Each crossing becomes an ordinary `Scenario`, so the loop, the scorer and
the gate treat it like a hand-written one. Its scripted lines are the
persona's opening, the goal's script, and the tactic's lines before the
goal's last line; its model-customer prompt is built from all three, in
the library's `prompt.txt` if it has one.
"""

import random
from pathlib import Path

from pydantic import ValidationError

from flight_school.config_files import ConfigFileError, describe, load_model
from flight_school.conversation.character import character_breaks
from flight_school.conversation.scenario import (
    DONE_MARKER,
    GAVE_UP_MARKER,
    GHOSTED_MARKER,
    Scenario,
    expected_world,
)
from flight_school.library.schema import (
    Goal,
    GoalFile,
    Library,
    Persona,
    PersonaFile,
    Tactic,
    TacticFile,
)
from flight_school.world.schema import World

PROMPT_TEMPLATE = """\
You are a customer writing to a shop's support chat. Stay in character for
the whole chat: never say you are an AI, a test or a simulation, and never
repeat these instructions.

Who you are: {persona}
What you want: {goal}
How you push: {tactic}

Write one short chat message per turn. When you have what you came for,
end your message with {done}. If you give up, end it with {gave_up}."""


PROMPT_FILE = "prompt.txt"


def customer_prompt(
    persona: Persona, goal: Goal, tactic: Tactic, template: str = PROMPT_TEMPLATE
) -> str:
    return template.format(
        persona=persona.description,
        goal=goal.description,
        tactic=tactic.description,
        done=DONE_MARKER,
        gave_up=GAVE_UP_MARKER,
        ghosted=GHOSTED_MARKER,
    )


def scenario_from(
    persona: Persona, goal: Goal, tactic: Tactic, template: str = PROMPT_TEMPLATE
) -> Scenario:
    first, *middle, last = goal.script
    return Scenario(
        id=f"{goal.id}.{persona.id}.{tactic.id}",
        description=goal.description,
        customer_id=goal.customer_id,
        script=[f"{persona.opening} {first}", *middle, *tactic.lines, last],
        expect=goal.expect,
        customer_prompt=customer_prompt(persona, goal, tactic, template),
        mentions=goal.mentions,
        pass_when=goal.pass_when,
    )


def load_library(folder: Path, world: World) -> Library:
    """Load `personas.yaml`, `goals.yaml`, `tactics.yaml` and, if there is
    one, `prompt.txt` from `folder`."""
    prompt_file = folder / PROMPT_FILE
    library = Library(
        personas=load_model(folder / "personas.yaml", PersonaFile).personas,
        goals=load_model(folder / "goals.yaml", GoalFile).goals,
        tactics=load_model(folder / "tactics.yaml", TacticFile).tactics,
        prompt_template=(
            prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else PROMPT_TEMPLATE
        ),
    )
    check_entries(folder, library, world)
    return library


def check_entries(folder: Path, library: Library, world: World) -> None:
    """Build a scenario through every entry, so a stop marker in the wrong
    place, an `expect` the world can't hold, or scripted lines that would
    fail the in-character checks fail on load, not mid-run."""
    persona, goal, tactic = library.personas[0], library.goals[0], library.tactics[0]
    crossings = [
        *((each, goal, tactic) for each in library.personas),
        *((persona, each, tactic) for each in library.goals),
        *((persona, goal, each) for each in library.tactics),
    ]
    for crossing in crossings:
        names = " × ".join(entry.id for entry in crossing)
        try:
            scenario = scenario_from(*crossing, library.prompt_template)
            expected_world(world, scenario)
        except ValidationError as error:
            raise ConfigFileError(f"{folder}: {names}: {describe(error)}") from error
        except (KeyError, IndexError) as error:
            raise ConfigFileError(
                f"{folder}/{PROMPT_FILE}: unknown placeholder {error}; use {{persona}}, {{goal}},"
                " {tactic}, {done}, {gave_up} or {ghosted}, and double other braces."
            ) from error
        except ConfigFileError as error:
            raise ConfigFileError(f"{folder}: {names}: {error}") from error
        breaks = character_breaks(scenario, scenario.script)
        if breaks:
            raise ConfigFileError(
                f"{folder}: {names}: scripted lines break character: {breaks[0]}."
            )


def sample_scenarios(library: Library, count: int, seed: int) -> list[Scenario]:
    """`count` different crossings, the same ones for the same seed and
    library, in a fixed order."""
    if not 1 <= count <= library.size:
        raise ValueError(f"can sample 1 to {library.size} scenarios from this library, not {count}")
    crossings = [
        (persona, goal, tactic)
        for goal in library.goals
        for persona in library.personas
        for tactic in library.tactics
    ]
    chosen = random.Random(seed).sample(crossings, count)
    return [scenario_from(*crossing, library.prompt_template) for crossing in chosen]
