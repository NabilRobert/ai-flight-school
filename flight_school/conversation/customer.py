"""The simulated customer's side of the loop (ADR-003, S3 and S4): a
scripted customer that says its scenario's lines, or a model customer
that plays the scenario's prompt.

The model customer is Inspect's `user` model role, so a run picks it with
`model_roles={"user": ...}` and tests use `mockllm` at $0. It sees the
chat from its own side: its lines are the assistant's, the agent's are
the user's.

Two runs of the same scenario must give the customer the same draws, so
an A/B comparison can pair them (thesis pilot): the customer opens with
the scenario's first scripted line, and its seed comes from the scenario
and the epoch. The draws stay the same only while the agent's replies do;
after the first different reply, the customer reacts to it.
"""

import hashlib
from collections.abc import Awaitable, Callable, Sequence

from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageUser,
    GenerateConfig,
    get_model,
)

from flight_school.conversation.agent import Message
from flight_school.conversation.scenario import Scenario

# The chat so far, oldest first; returns the customer's next line.
Customer = Callable[[Sequence[Message]], Awaitable[str]]

# What the model customer is shown before it writes its first line: chat
# models answer a user turn, and the agent hasn't said anything yet.
CHAT_OPENED = "(The support chat is open. Write your first message.)"


def scripted_customer(scenario: Scenario) -> Customer:
    async def say(chat: Sequence[Message]) -> str:
        lines_said = sum(1 for message in chat if message.speaker == "customer")
        return scenario.script[lines_said]

    return say


def customer_seed(scenario_id: str, epoch: int) -> int:
    """The same seed for the same scenario and epoch, in every run."""
    digest = hashlib.sha256(f"{scenario_id}#{epoch}".encode()).digest()
    return int.from_bytes(digest[:4])


def model_customer(scenario: Scenario, seed: int) -> Customer:
    if not scenario.customer_prompt:
        raise ValueError(
            f"scenario {scenario.id} has no customer prompt: a model customer needs a"
            " library scenario (flightschool run --sample)"
        )
    model = get_model(role="user", required=True)

    async def say(chat: Sequence[Message]) -> str:
        if not chat:
            return scenario.script[0]
        output = await model.generate(
            customer_view(scenario, chat), config=GenerateConfig(seed=seed)
        )
        return output.completion

    return say


def customer_view(scenario: Scenario, chat: Sequence[Message]) -> list[ChatMessage]:
    messages: list[ChatMessage] = [
        ChatMessageSystem(content=scenario.customer_prompt),
        ChatMessageUser(content=CHAT_OPENED),
    ]
    for message in chat:
        if message.speaker == "customer":
            messages.append(ChatMessageAssistant(content=message.text))
        else:
            messages.append(ChatMessageUser(content=message.text))
    return messages
