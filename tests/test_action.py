"""The GitHub Action passes its inputs safely."""

import re
from pathlib import Path
from typing import Any

import yaml

ACTION = Path(__file__).parent.parent / "action.yml"


def test_no_step_pastes_an_input_into_its_script() -> None:
    action: dict[str, Any] = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    scripts = [step["run"] for step in action["runs"]["steps"] if "run" in step]
    assert scripts
    assert not any(re.search(r"\$\{\{", script) for script in scripts)
