"""The thesis pilot's sales suite (`examples/sales-id`), at $0: a sales chat
passes only when the customer ends with ###DONE###, the sales agents send
their own instructions to their model, and the library's Indonesian prompt
reaches the customer."""

from pathlib import Path

import pytest
from agent_eval.records import load_run
from inspect_ai.model import ChatMessage, GenerateConfig, Model, ModelOutput, get_model
from inspect_ai.tool import ToolChoice, ToolInfo

from flight_school.config_files import ConfigFileError
from flight_school.conversation.agent import AgentFactory
from flight_school.conversation.environment import OLLAMA_EXTRA_BODY
from flight_school.conversation.plan import RunPlan
from flight_school.conversation.run import model_roles, run_plan
from flight_school.gate import judge
from flight_school.library.sampler import load_library, sample_scenarios
from flight_school.reference.sales_agent import (
    HEALTHY_INSTRUCTIONS,
    NEVER_QUOTES_PRICE_INSTRUCTIONS,
    healthy,
    never_quotes_price,
)
from flight_school.suite import load_suite

SALES = Path(__file__).parent.parent / "examples" / "sales-id"
SUITE = load_suite(SALES)
AGENT_REPLY = "Skuter 110 Rp18.900.000 OTR ya kak."
Sent = list[list[ChatMessage]]


def agent_model(sent: Sent, reply: str = AGENT_REPLY) -> Model:
    """A mockllm sales agent that always says `reply` and keeps what it
    was sent."""

    def generate(
        messages: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        del tools, tool_choice, config
        sent.append(messages)
        return ModelOutput.from_content("mockllm", reply)

    return get_model("mockllm/model", custom_outputs=generate, memoize=False)


def run_sales(tmp_path: Path, agent: AgentFactory, sent: Sent, reply: str = AGENT_REPLY) -> Path:
    plan = RunPlan(
        SUITE.world,
        SUITE.rules,
        SUITE.scenarios,
        agent,
        "healthy",
        SUITE.name,
        agent_model=agent_model(sent, reply),
    )
    run_plan(plan, tmp_path)
    return tmp_path


def test_a_sales_chat_passes_only_when_the_customer_ends_done(tmp_path: Path) -> None:
    verdict = judge(run_sales(tmp_path, healthy, []))
    outcomes = {trial["task_id"]: trial["outcome"] for trial in load_run(tmp_path).trials}
    # Ghosting is a normal ending in sales, not a broken run, but it isn't a pass.
    assert outcomes == {"tanya-harga-tunai": "pass", "menghilang-setelah-tanya-dp": "fail"}
    assert verdict.findings == []
    assert verdict.task_success == (1, 2)


def test_the_ghosted_marker_is_recorded_as_the_way_the_chat_ended(tmp_path: Path) -> None:
    run_sales(tmp_path, healthy, [])
    markers = {trial["task_id"]: trial["stop_marker"] for trial in load_run(tmp_path).trials}
    assert markers["menghilang-setelah-tanya-dp"] == "###GHOSTED###"


@pytest.mark.parametrize(
    ("agent", "instructions"),
    [(healthy, HEALTHY_INSTRUCTIONS), (never_quotes_price, NEVER_QUOTES_PRICE_INSTRUCTIONS)],
    ids=["healthy", "never-quotes-price"],
)
def test_a_sales_agent_sends_its_instructions_and_the_chat_from_its_side(
    tmp_path: Path, agent: AgentFactory, instructions: str
) -> None:
    sent: Sent = []
    run_sales(tmp_path, agent, sent)
    first = sent[0]
    assert [message.role for message in first] == ["system", "user"]
    assert first[0].text == instructions
    assert first[1].text == SUITE.scenarios[0].script[0]


def test_the_model_agent_is_recorded_as_the_runs_agent(tmp_path: Path) -> None:
    run_sales(tmp_path, healthy, [])
    assert load_run(tmp_path).meta["agent"]["model"] == "mockllm/model"


def test_the_library_prompt_reaches_the_customer_in_indonesian() -> None:
    assert SUITE.library is not None
    [scenario] = sample_scenarios(SUITE.library, 1, seed=0)
    assert scenario.customer_prompt.startswith("Kamu berperan sebagai calon pembeli")
    assert "###GHOSTED###" in scenario.customer_prompt
    assert scenario.pass_when == "customer_done"


def test_a_library_prompt_with_an_unknown_placeholder_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "library"
    folder.mkdir()
    for name in ("personas.yaml", "goals.yaml", "tactics.yaml"):
        (folder / name).write_text((SALES / "library" / name).read_text(encoding="utf-8"))
    (folder / "prompt.txt").write_text("Siapa kamu: {persona}. Nama: {nama}", encoding="utf-8")
    with pytest.raises(ConfigFileError, match="unknown placeholder 'nama'"):
        load_library(folder, SUITE.world)


def test_a_local_agent_model_is_run_with_thinking_off() -> None:
    plan = RunPlan(
        SUITE.world,
        SUITE.rules,
        SUITE.scenarios,
        healthy,
        "healthy",
        SUITE.name,
        agent_model="ollama/llama3.2:3b",
    )
    agent = (model_roles(plan) or {})["agent"]
    assert isinstance(agent, Model)
    assert agent.config.extra_body == OLLAMA_EXTRA_BODY
