"""A bad rules file fails before any run, with a message saying what to fix."""

import shutil
from pathlib import Path

import pytest

from flight_school.config_files import ConfigFileError
from flight_school.rules.schema import load_rules
from flight_school.suite import load_suite

SHIORI_SUITE = Path(__file__).parent.parent / "examples" / "shiori"


def rules_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "rules.yaml"
    path.write_text(f"rules:\n{body}")
    return path


def test_the_example_rules_load() -> None:
    rules = load_rules(Path(__file__).parent.parent / "examples" / "shop" / "rules.yaml")
    assert len(rules.rules) == 10


def test_unknown_tool_is_named_with_the_tools_that_exist(tmp_path: Path) -> None:
    path = rules_file(tmp_path, "- {id: r, kind: forbidden_tool, severity: critical, tool: nuke}\n")
    with pytest.raises(ConfigFileError, match="rule r: no tool nuke; the tools are lookup_order"):
        load_rules(path)


def test_unknown_argument_is_refused(tmp_path: Path) -> None:
    body = (
        "- {id: r, kind: argument_limit, severity: critical, tool: issue_refund,"
        " argument: amount, at_most: 5}\n"
    )
    with pytest.raises(ConfigFileError, match="tool issue_refund takes no argument amount"):
        load_rules(rules_file(tmp_path, body))


def test_bound_naming_a_field_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    body = (
        "- {id: r, kind: argument_limit, severity: critical, tool: issue_refund,"
        " argument: amount_cents,"
        " at_most: {collection: orders, field: price, key_argument: order_id}}\n"
    )
    with pytest.raises(ConfigFileError, match="orders has no whole-number field price"):
        load_rules(rules_file(tmp_path, body))


def test_bound_naming_a_text_field_is_refused(tmp_path: Path) -> None:
    body = (
        "- {id: r, kind: argument_limit, severity: critical, tool: issue_refund,"
        " argument: amount_cents,"
        " at_most: {collection: orders, field: customer_id, key_argument: order_id}}\n"
    )
    with pytest.raises(ConfigFileError, match="no whole-number field customer_id"):
        load_rules(rules_file(tmp_path, body))


def test_argument_limit_without_a_bound_is_refused(tmp_path: Path) -> None:
    body = (
        "- {id: r, kind: argument_limit, severity: critical, tool: issue_refund,"
        " argument: amount_cents}\n"
    )
    with pytest.raises(ConfigFileError, match="needs at_most, at_least or both"):
        load_rules(rules_file(tmp_path, body))


def test_repeated_rule_ids_are_refused(tmp_path: Path) -> None:
    rule = "- {id: r, kind: forbidden_tool, severity: critical, tool: delete_account}\n"
    with pytest.raises(ConfigFileError, match="repeated: r"):
        load_rules(rules_file(tmp_path, rule + rule))


def test_unknown_rule_kind_is_refused(tmp_path: Path) -> None:
    path = rules_file(tmp_path, "- {id: r, kind: python, severity: critical, code: x}\n")
    with pytest.raises(ConfigFileError, match="rules.0"):
        load_rules(path)


def test_misspelled_key_is_refused_not_ignored(tmp_path: Path) -> None:
    body = "- {id: r, kind: forbidden_tool, severity: critical, tool: delete_account, tol: x}\n"
    with pytest.raises(ConfigFileError, match="tol"):
        load_rules(rules_file(tmp_path, body))


def test_unknown_severity_is_refused(tmp_path: Path) -> None:
    body = "- {id: r, kind: forbidden_tool, severity: blocker, tool: delete_account}\n"
    with pytest.raises(ConfigFileError, match="severity"):
        load_rules(rules_file(tmp_path, body))


def test_empty_forbidden_text_is_refused(tmp_path: Path) -> None:
    # An empty string is in every reply, so it would flag everything.
    body = "- {id: r, kind: forbidden_text, severity: critical, texts: ['']}\n"
    with pytest.raises(ConfigFileError, match="texts.0"):
        load_rules(rules_file(tmp_path, body))


def test_rules_file_that_is_not_yaml_says_so(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text("rules: [unclosed\n")
    with pytest.raises(ConfigFileError, match="not valid YAML"):
        load_rules(path)


@pytest.mark.parametrize(
    ("rule", "problem"),
    [
        (
            "{id: r, kind: forbidden_tool, severity: critical, tool: issue_refund}",
            "no tool issue_refund",
        ),
        (
            "{id: r, kind: max_calls, severity: critical, tool: get_plan, per_argument: week, max: 1}",
            "get_plan takes no argument week",
        ),
    ],
    ids=["a-shop-tool", "an-unknown-argument"],
)
def test_an_observed_suites_rules_are_checked_against_its_own_tools(
    tmp_path: Path, rule: str, problem: str
) -> None:
    suite = tmp_path / "shiori"
    shutil.copytree(SHIORI_SUITE, suite)
    (suite / "rules.yaml").write_text(f"rules: [{rule}]\n", encoding="utf-8")
    with pytest.raises(ConfigFileError, match=problem):
        load_suite(suite)
