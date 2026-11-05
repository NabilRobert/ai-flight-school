"""The seed library's entries (ADR-003, ADR-012): hand-written personas,
goals and tactics, each a small YAML entry with an id. `sampler.py` loads
them and crosses them into scenarios.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flight_school.config_files import KebabId
from flight_school.conversation.scenario import ExpectedChanges


class Persona(BaseModel):
    """Who the customer is: tone only, never what they want."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: KebabId
    description: str = Field(min_length=1)
    # Starts a scripted customer's first message.
    opening: str = Field(min_length=1)


class Goal(BaseModel):
    """What the customer wants, and how the shop should look afterwards."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: KebabId
    description: str = Field(min_length=1)
    customer_id: str
    mentions: list[str] = Field(min_length=1)
    # At least the ask and the line that ends the conversation, so a
    # tactic's lines have a place between them.
    script: list[str] = Field(min_length=2)
    expect: ExpectedChanges = {}


class Tactic(BaseModel):
    """How the customer pushes. A scripted customer says `lines` just
    before its goal's last line."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: KebabId
    description: str = Field(min_length=1)
    lines: list[str] = []


def unique_ids(entries: list[Persona] | list[Goal] | list[Tactic]) -> None:
    ids = [entry.id for entry in entries]
    repeated = sorted({entry_id for entry_id in ids if ids.count(entry_id) > 1})
    if repeated:
        raise ValueError(f"ids must be unique; repeated: {', '.join(repeated)}")


class PersonaFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    personas: list[Persona] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_ids(self) -> Self:
        unique_ids(self.personas)
        return self


class GoalFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    goals: list[Goal] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_ids(self) -> Self:
        unique_ids(self.goals)
        return self


class TacticFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tactics: list[Tactic] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_ids(self) -> Self:
        unique_ids(self.tactics)
        return self


class Library(BaseModel):
    personas: list[Persona]
    goals: list[Goal]
    tactics: list[Tactic]

    @property
    def size(self) -> int:
        """How many scenarios the library can make."""
        return len(self.personas) * len(self.goals) * len(self.tactics)
