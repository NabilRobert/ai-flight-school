"""The rules a team writes in `rules.yaml`: six fixed kinds, data only.

A rule file is never executed. It is validated twice: its shape here, and
its names against the agent's tools and the shop's data, so a rule that
names a tool or field that doesn't exist fails before any run (ADR-010).
The tools are the fake shop's, or an observed agent's own (A3), as its
suite's `tools.yaml` lists them.
"""

from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flight_school.config_files import ConfigFileError, KebabId, load_model
from flight_school.world.schema import COLLECTIONS
from flight_school.world.shop import SHOP_TOOLS

# Each tool's name, with the names of its arguments.
ToolArguments = Mapping[str, Collection[str]]
SHOP_TOOL_ARGUMENTS: dict[str, list[str]] = {
    name: list(spec.arguments.model_fields) for name, spec in SHOP_TOOLS.items()
}


class RuleBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: KebabId
    # Only critical rules block a release; warnings are reported.
    severity: Literal["critical", "warning"]


class FieldBound(BaseModel):
    """A limit read from the world: the `field` of the item in `collection`
    whose id the call passes as `key_argument`."""

    model_config = ConfigDict(extra="forbid", strict=True)

    collection: Literal["customers", "orders"]
    field: str
    key_argument: str


class ForbiddenTool(RuleBase):
    kind: Literal["forbidden_tool"]
    tool: str


class ArgumentLimit(RuleBase):
    kind: Literal["argument_limit"]
    tool: str
    argument: str
    at_most: int | FieldBound | None = None
    at_least: int | FieldBound | None = None

    @model_validator(mode="after")
    def check_has_a_bound(self) -> Self:
        if self.at_most is None and self.at_least is None:
            raise ValueError("an argument_limit needs at_most, at_least or both")
        return self

    def bounds(self) -> list[FieldBound]:
        return [b for b in (self.at_most, self.at_least) if isinstance(b, FieldBound)]


class RequiresBefore(RuleBase):
    kind: Literal["requires_before"]
    tool: str
    requires: str


class MaxCalls(RuleBase):
    kind: Literal["max_calls"]
    tool: str
    # Counted per value of this argument (per order); without one, per
    # conversation, for a tool that takes no arguments.
    per_argument: str | None = None
    max: int = Field(ge=0)


class SameSubject(RuleBase):
    kind: Literal["same_subject"]
    tools: list[str] = Field(min_length=1)


class ForbiddenText(RuleBase):
    kind: Literal["forbidden_text"]
    texts: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)


Rule = Annotated[
    ForbiddenTool | ArgumentLimit | RequiresBefore | MaxCalls | SameSubject | ForbiddenText,
    Field(discriminator="kind"),
]


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    rules: list[Rule]

    @model_validator(mode="after")
    def check_unique_ids(self) -> Self:
        ids = [rule.id for rule in self.rules]
        repeated = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
        if repeated:
            raise ValueError(f"rule ids must be unique; repeated: {', '.join(repeated)}")
        return self


def load_rules(path: Path, tools: ToolArguments = SHOP_TOOL_ARGUMENTS) -> RuleSet:
    rule_set = load_model(path, RuleSet)
    problems = [problem for rule in rule_set.rules for problem in unknown_names(rule, tools)]
    if problems:
        raise ConfigFileError(f"{path}: {' '.join(problems)} Fix the file and run again.")
    return rule_set


def unknown_names(rule: Rule, tools: ToolArguments) -> list[str]:
    """Each tool, argument and field the rule names that doesn't exist."""
    problems: list[str] = []
    for tool in tools_named(rule):
        if tool not in tools:
            problems.append(f"rule {rule.id}: no tool {tool}; the tools are {', '.join(tools)}.")
    for tool, argument in arguments_named(rule):
        if tool in tools and argument not in tools[tool]:
            problems.append(f"rule {rule.id}: tool {tool} takes no argument {argument}.")
    if isinstance(rule, ArgumentLimit):
        problems.extend(f"rule {rule.id}: {p}" for p in bound_problems(rule.bounds()))
    return problems


def tools_named(rule: Rule) -> list[str]:
    match rule:
        case SameSubject():
            return rule.tools
        case RequiresBefore():
            return [rule.tool, rule.requires]
        case ForbiddenText():
            return []
        case _:
            return [rule.tool]


def arguments_named(rule: Rule) -> list[tuple[str, str]]:
    match rule:
        case ArgumentLimit():
            keys = [bound.key_argument for bound in rule.bounds()]
            return [(rule.tool, rule.argument)] + [(rule.tool, key) for key in keys]
        case MaxCalls() if rule.per_argument is not None:
            return [(rule.tool, rule.per_argument)]
        case _:
            return []


def bound_problems(bounds: list[FieldBound]) -> list[str]:
    problems: list[str] = []
    for bound in bounds:
        field = COLLECTIONS[bound.collection].model_fields.get(bound.field)
        if field is None or field.annotation is not int:
            problems.append(f"{bound.collection} has no whole-number field {bound.field}.")
    return problems
