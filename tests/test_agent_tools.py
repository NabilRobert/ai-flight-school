"""What an in-process agent can and can't do to the record of its calls."""

from flight_school.conversation.agent import AgentTools
from flight_school.world.shop import FakeShop
from tests.test_conversation import WORLD


def test_agent_editing_the_call_it_got_back_does_not_change_the_record() -> None:
    shop = FakeShop(WORLD)
    tools = AgentTools(shop)
    tools.turn = 1
    returned = tools.call("issue_refund", {"order_id": "o1", "amount_cents": 999_999})
    returned.arguments["amount_cents"] = 1
    assert returned.result is not None
    returned.result["refunded_cents"] = 0
    [recorded] = shop.calls
    assert recorded.arguments["amount_cents"] == 999_999
    assert recorded.result == {"order_id": "o1", "refunded_cents": 999_999}


def test_agent_editing_its_arguments_after_the_call_does_not_change_the_record() -> None:
    shop = FakeShop(WORLD)
    order_ids = ["o1"]
    AgentTools(shop).call("lookup_order", {"order_id": order_ids})
    order_ids.append("o3")
    assert shop.calls[0].arguments == {"order_id": ["o1"]}
