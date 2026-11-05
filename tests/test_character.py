"""In-character checks (S6): the crude ways a model customer breaks a test."""

from flight_school.conversation.character import character_breaks
from flight_school.library.sampler import scenario_from
from tests.test_library import LIBRARY

SCENARIO = scenario_from(LIBRARY.personas[0], LIBRARY.goals[0], LIBRARY.tactics[0])


def test_a_customer_that_calls_itself_an_ai_breaks_character() -> None:
    lines = ["As an AI, I can't really have an order o1.", "###DONE###"]
    assert character_breaks(SCENARIO, lines) == ["line 1: says it is a test ('As an AI')"]


def test_a_customer_that_starts_offering_help_has_flipped_roles() -> None:
    lines = ["Refund o1 please.", "How can I help you today?", "###DONE###"]
    assert character_breaks(SCENARIO, lines) == ["line 2: says it is a test ('How can I help you')"]


def test_eight_words_copied_from_the_prompt_are_quoting_its_instructions() -> None:
    copied = "never say you are an AI, a test or"
    assert character_breaks(SCENARIO, [f"About o1: {copied}", "###DONE###"]) == [
        "line 1: quotes its instructions"
    ]


def test_seven_words_from_the_prompt_are_not_quoting() -> None:
    assert character_breaks(SCENARIO, ["About o1: never say you are an AI, a", "###DONE###"]) == []


def test_a_customer_that_never_mentions_its_order_dropped_its_goal() -> None:
    lines = ["Hi, nice weather today.", "###DONE###"]
    assert character_breaks(SCENARIO, lines) == ["never mentions o1: dropped its goal"]


def test_a_goal_said_only_in_the_line_that_ends_the_chat_was_dropped() -> None:
    lines = ["Hi.", "About o1. ###DONE###"]
    assert character_breaks(SCENARIO, lines) == ["never mentions o1: dropped its goal"]


def test_a_hand_written_scenario_has_no_goal_to_drop() -> None:
    plain = SCENARIO.model_copy(update={"mentions": [], "customer_prompt": ""})
    assert character_breaks(plain, ["Hi.", "###DONE###"]) == []
