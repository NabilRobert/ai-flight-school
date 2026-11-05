"""A bad scenarios file fails before any run, and `expect` means exactly
the changes it lists."""

from pathlib import Path

import pytest

from flight_school.config_files import ConfigFileError
from flight_school.conversation.scenario import Scenario, expected_world, load_scenarios
from flight_school.world.schema import load_world

EXAMPLES = Path(__file__).parent.parent / "examples" / "shop"
WORLD = load_world(EXAMPLES / "world.yaml")


def scenarios_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "scenarios.yaml"
    path.write_text(f"scenarios:\n{body}")
    return path


def scenario(**changes: object) -> Scenario:
    fields: dict[str, object] = {
        "id": "s",
        "description": "a test",
        "customer_id": "c1",
        "script": ["hi", "bye ###DONE###"],
    }
    return Scenario.model_validate({**fields, **changes})


def test_the_example_scenarios_load_with_the_plain_refund_first() -> None:
    # Other tests take the first scenario as the plain, harmless request.
    scenarios = load_scenarios(EXAMPLES / "scenarios.yaml", WORLD).scenarios
    assert scenarios[0].id == "refund-own-order"


def test_script_whose_last_line_has_no_stop_marker_is_refused() -> None:
    with pytest.raises(ValueError, match="last line must end the conversation"):
        scenario(script=["hi", "bye"])


def test_unquoted_marker_lost_to_a_yaml_comment_is_explained(tmp_path: Path) -> None:
    body = "- id: s\n  description: d\n  customer_id: c1\n  script:\n    - Thanks! ###DONE###\n"
    with pytest.raises(ConfigFileError, match="quote that line"):
        load_scenarios(scenarios_file(tmp_path, body), WORLD)


def test_stop_marker_before_the_last_line_is_refused() -> None:
    with pytest.raises(ValueError, match="line 1 has a stop marker"):
        scenario(script=["###GAVE_UP###", "bye ###DONE###"])


def test_repeated_scenario_id_is_refused(tmp_path: Path) -> None:
    line = "- {id: s, description: d, customer_id: c1, script: ['###DONE###']}\n"
    with pytest.raises(ConfigFileError, match="scenario ids must be unique; repeated: s"):
        load_scenarios(scenarios_file(tmp_path, line + line), WORLD)


def test_unknown_customer_is_refused_with_the_file_named(tmp_path: Path) -> None:
    body = "- {id: s, description: d, customer_id: c9, script: ['###DONE###']}\n"
    with pytest.raises(ConfigFileError, match=r"scenarios.yaml: scenario s: no customer c9"):
        load_scenarios(scenarios_file(tmp_path, body), WORLD)


def test_expected_change_to_an_unknown_item_is_refused() -> None:
    with pytest.raises(ConfigFileError, match="no orders item o9"):
        expected_world(WORLD, scenario(expect={"orders": {"o9": {"refunded_cents": 1}}}))


def test_expected_change_to_an_unknown_field_is_refused() -> None:
    with pytest.raises(ConfigFileError, match="Extra inputs are not permitted"):
        expected_world(WORLD, scenario(expect={"orders": {"o1": {"refund": 1}}}))


def test_expected_change_of_the_wrong_type_is_refused() -> None:
    with pytest.raises(ConfigFileError, match="refunded_cents: Input should be a valid integer"):
        expected_world(WORLD, scenario(expect={"orders": {"o1": {"refunded_cents": "4500"}}}))


def test_expected_world_changes_only_the_listed_fields() -> None:
    expected = expected_world(WORLD, scenario(expect={"orders": {"o1": {"refunded_cents": 4500}}}))
    changed = [
        (before, after)
        for before, after in zip(WORLD.orders, expected.orders, strict=True)
        if before != after
    ]
    assert [(before.id, after.refunded_cents) for before, after in changed] == [("o1", 4500)]
    assert expected.customers == WORLD.customers
