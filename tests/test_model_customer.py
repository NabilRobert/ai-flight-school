"""The model-customer path (S4), end to end at $0: Inspect's `mockllm`
plays the customer as a model would, through the `user` model role."""

from pathlib import Path

import pytest
from agent_eval.records import load_run
from inspect_ai.model import ChatMessage, GenerateConfig, Model, ModelOutput, get_model
from inspect_ai.tool import ToolChoice, ToolInfo

from flight_school.conversation.customer import CHAT_OPENED, trial_seed
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import run_plan
from flight_school.gate import EXIT_INCONCLUSIVE, EXIT_PASS, judge
from flight_school.library.sampler import scenario_from
from flight_school.reference.agent import correct
from tests.test_conversation import REFUND_OWN_ORDER, RULES, WORLD
from tests.test_library import crossing

# Aiko's refund, as a model customer might go on after the scenario's
# opening line, which it always says as written.
AIKO_LINES = [
    "Sure, my email is aiko@example.com.",
    "Lovely, thank you! ###DONE###",
]
SCENARIO = scenario_from(*crossing("plain", "refund-own-order", "none"))
Calls = list[tuple[list[ChatMessage], GenerateConfig]]


def customer_saying(lines: list[str], calls: Calls) -> Model:
    """A mockllm customer that says `lines` in order, one per call, and
    keeps what it was sent."""

    def generate(
        messages: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        del tools, tool_choice
        calls.append((messages, config))
        return ModelOutput.from_content("mockllm", lines[len(calls) - 1])

    return get_model("mockllm/model", custom_outputs=generate, memoize=False)


def run_with(tmp_path: Path, customer: Model, epochs: int = 1) -> Path:
    plan = RunPlan(
        WORLD, RULES, [SCENARIO], correct, "correct", "test", epochs=epochs, customer_model=customer
    )
    run_plan(plan, tmp_path)
    return tmp_path


def test_a_model_customer_runs_end_to_end_and_the_correct_agent_passes(tmp_path: Path) -> None:
    verdict = judge(run_with(tmp_path, customer_saying(AIKO_LINES, [])))
    assert verdict.task_success == (1, 1)
    assert verdict.exit_code == EXIT_PASS
    [trial] = load_run(tmp_path).trials
    assert trial["stop_marker"] == "###DONE###"
    assert trial["character_breaks"] == []


def test_the_model_customer_sees_its_prompt_and_the_chat_from_its_own_side(tmp_path: Path) -> None:
    calls: Calls = []
    run_with(tmp_path, customer_saying(AIKO_LINES, calls))
    first, _ = calls[0]
    assert [message.role for message in first] == ["system", "user", "assistant", "user"]
    assert first[0].text == SCENARIO.customer_prompt
    assert first[1].text == CHAT_OPENED


def test_the_model_customer_opens_with_the_scenarios_first_line(tmp_path: Path) -> None:
    # So turn 1 is the same in every run of the scenario, and an A/B
    # comparison starts from the same message.
    calls: Calls = []
    run_with(tmp_path, customer_saying(AIKO_LINES, calls))
    first, _ = calls[0]
    assert first[2].text == SCENARIO.script[0]
    assert len(calls) == len(AIKO_LINES)


def test_each_epoch_gets_its_own_customer_seed_the_same_in_every_run(tmp_path: Path) -> None:
    calls: Calls = []
    run_with(tmp_path, customer_saying(AIKO_LINES * 2, calls), epochs=2)
    seeds = {trial["attempt"]: trial["customer_seed"] for trial in load_run(tmp_path).trials}
    assert seeds == {epoch: trial_seed(SCENARIO.id, epoch) for epoch in (1, 2)}
    assert seeds[1] != seeds[2]
    assert {config.seed for _, config in calls} == set(seeds.values())


def test_a_model_customer_that_breaks_character_makes_the_run_inconclusive(tmp_path: Path) -> None:
    lines = ["As an AI, my email is aiko@example.com.", *AIKO_LINES[1:]]
    verdict = judge(run_with(tmp_path, customer_saying(lines, [])))
    assert verdict.broken_customers == [
        "refund-own-order.plain.none#1: line 2: says it is a test ('As an AI')"
    ]
    assert verdict.exit_code == EXIT_INCONCLUSIVE


def test_a_model_customer_and_a_scripted_one_are_never_compared(tmp_path: Path) -> None:
    run_plan(RunPlan(WORLD, RULES, [SCENARIO], correct, "correct", "test"), tmp_path / "scripted")
    run_with(tmp_path / "model", customer_saying(AIKO_LINES, []))
    fingerprints = {
        load_run(tmp_path / name).meta["provenance"]["data_fingerprint"]
        for name in ("scripted", "model")
    }
    assert len(fingerprints) == 2


def test_a_model_customer_needs_library_scenarios() -> None:
    with pytest.raises(ValueError, match="refund-own-order has no customer prompt"):
        RunPlan(WORLD, RULES, [REFUND_OWN_ORDER], correct, "c", "t", customer_model="mockllm/model")
