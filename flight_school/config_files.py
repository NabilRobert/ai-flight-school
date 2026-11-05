"""Loading the YAML files a team writes (world, rules, scenarios) into validated models.

Every problem is reported as a `ConfigFileError` that names the file and
says what to fix, so a bad file fails before anything runs.
"""

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, ValidationError

# Rule and scenario ids: lower-case words joined by hyphens, so they read
# well in a report and can't collide by case.
KebabId = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]


class ConfigFileError(Exception):
    """A world, rules or scenarios file that can't be used as written."""


def load_model[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    """Read `path` as YAML and validate it as `model`."""
    try:
        data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigFileError(f"{path}: can't read it ({error.strerror}).") from error
    except yaml.YAMLError as error:
        raise ConfigFileError(f"{path}: not valid YAML. {error}") from error
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise ConfigFileError(f"{path}: {describe(error)} Fix the file and run again.") from error


def describe(error: ValidationError) -> str:
    """One line per problem, each with where it is in the file."""
    problems: list[str] = []
    for detail in error.errors():
        where = ".".join(str(part) for part in detail["loc"]) or "the file"
        problems.append(f"{where}: {detail['msg']}.")
    return " ".join(problems)
