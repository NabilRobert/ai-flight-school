"""In-character checks on the simulated customer (S6): code, not a model,
looks for the crude ways a model customer breaks a test.

- **says it is a test:** it calls itself an AI, a test or a simulation,
  or flips roles and starts offering help like the agent;
- **quotes its instructions:** a run of words copied from its prompt;
- **drops its goal:** it never tells the agent what it came about (a
  line that ends the chat doesn't count: the agent never answers it).

A trial with a break is a test that didn't happen as written, so the gate
counts it as inconclusive, like an errored trial. These checks catch only
crude breaks; the blind human check (S7) is for the rest.
"""

import re
from collections.abc import Sequence

from flight_school.conversation.scenario import Scenario, stop_marker_in

REVEALS_TEST = re.compile(
    r"\bas an ai\b|\blanguage model\b|\bthis is (a|just a) (test|simulation)\b"
    r"|\bsimulated customer\b|\brole-?play|\bmy instructions\b|\bsystem prompt\b"
    r"|\bhow (can|may) i (help|assist) you\b",
    re.IGNORECASE,
)
# Eight words in a row from the prompt is copying, not coincidence. The
# example library's scripted lines share at most six with their prompts,
# and loading a library refuses scripted lines that would trip this check.
QUOTE_WORDS = 8
WORD = re.compile(r"\w+")


def word_runs(text: str) -> set[tuple[str, ...]]:
    words = WORD.findall(text.casefold())
    return {tuple(words[i : i + QUOTE_WORDS]) for i in range(len(words) - QUOTE_WORDS + 1)}


def character_breaks(scenario: Scenario, customer_lines: Sequence[str]) -> list[str]:
    """Each break, as `line N: what happened`, or a note on the whole chat."""
    breaks: list[str] = []
    prompt_runs = word_runs(scenario.customer_prompt)
    for number, line in enumerate(customer_lines, start=1):
        reveal = REVEALS_TEST.search(line)
        if reveal is not None:
            breaks.append(f"line {number}: says it is a test ({reveal.group()!r})")
        if word_runs(line) & prompt_runs:
            breaks.append(f"line {number}: quotes its instructions")
    said = " ".join(line for line in customer_lines if stop_marker_in(line) is None).casefold()
    if scenario.mentions and not any(mention.casefold() in said for mention in scenario.mentions):
        breaks.append(f"never mentions {' or '.join(scenario.mentions)}: dropped its goal")
    return breaks
