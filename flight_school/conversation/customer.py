"""The simulated customer's side of the loop (ADR-003, S3 and S4): a
scripted customer that says its scenario's lines, or a model customer
that plays the scenario's prompt.

The model customer is Inspect's `user` model role, so a run picks it with
`model_roles={"user": ...}` and tests use `mockllm` at $0. It sees the
chat from its own side: its lines are the assistant's, the agent's are
the user's.
"""

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


def model_customer(scenario: Scenario) -> Customer:
    if not scenario.customer_prompt:
        raise ValueError(
            f"scenario {scenario.id} has no customer prompt: a model customer needs a"
            " library scenario (flightschool run --sample)"
        )
    model = get_model(role="user", required=True)

    async def say(chat: Sequence[Message]) -> str:
        output = await model.generate(
            customer_view(scenario, chat), config=GenerateConfig(seed=scenario.seed)
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
