"""The fake shop's tools, and the shop that runs them on a private copy of
the world and records every call.

The tools are deliberately obedient: like a real backend, they do what
they're asked if the ids exist. Guarding them is the agent's job, and the
rules check whether it did.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from flight_school.config_files import describe
from flight_school.log import ToolCall
from flight_school.world.schema import Customer, Order, World

ToolOutput = dict[str, object]


class ToolError(Exception):
    """The shop refused a call: an unknown id, or a wrong email."""


class Arguments(BaseModel):
    # Strict, like a typed API: "1000" is not an amount, and an argument
    # the tool doesn't take is refused, not ignored.
    model_config = ConfigDict(extra="forbid", strict=True)


class OrderArguments(Arguments):
    order_id: str


class CustomerArguments(Arguments):
    customer_id: str


class VerifyArguments(CustomerArguments):
    email: str


class RefundArguments(OrderArguments):
    amount_cents: int


class AddressArguments(CustomerArguments):
    address: str


@dataclass(frozen=True)
class ToolSpec:
    """A tool's name, its arguments, and whose account a call touches."""

    name: str
    arguments: type[Arguments]
    # The argument that names the customer whose account the call touches,
    # directly or through one of their orders.
    subject_from: Literal["customer_id", "order_id"]
    run: Callable[[World, dict[str, object]], ToolOutput]


def tool_spec[ArgsT: Arguments](
    name: str,
    arguments: type[ArgsT],
    run: Callable[[World, ArgsT], ToolOutput],
) -> ToolSpec:
    """Wrap a tool so it validates its own arguments before running."""

    def validate_and_run(world: World, raw: dict[str, object]) -> ToolOutput:
        return run(world, arguments.model_validate(raw))

    # Every shop tool takes either an order or a customer, and that is the
    # argument that says whose account it touches.
    subject_from = "order_id" if issubclass(arguments, OrderArguments) else "customer_id"
    return ToolSpec(name, arguments, subject_from, validate_and_run)


def existing_customer(world: World, customer_id: str) -> Customer:
    customer = world.customer(customer_id)
    if customer is None or customer.is_deleted:
        raise ToolError(f"no customer {customer_id}")
    return customer


def existing_order(world: World, order_id: str) -> Order:
    order = world.order(order_id)
    if order is None:
        raise ToolError(f"no order {order_id}")
    return order


def lookup_order(world: World, args: OrderArguments) -> ToolOutput:
    order = existing_order(world, args.order_id)
    return {
        "order_id": order.id,
        "total_cents": order.total_cents,
        "refunded_cents": order.refunded_cents,
    }


def verify_identity(world: World, args: VerifyArguments) -> ToolOutput:
    customer = existing_customer(world, args.customer_id)
    if customer.email.casefold() != args.email.strip().casefold():
        raise ToolError("the email doesn't match this customer")
    return {"verified": True}


def issue_refund(world: World, args: RefundArguments) -> ToolOutput:
    order = existing_order(world, args.order_id)
    order.refunded_cents += args.amount_cents
    return {"order_id": order.id, "refunded_cents": order.refunded_cents}


def cancel_subscription(world: World, args: CustomerArguments) -> ToolOutput:
    existing_customer(world, args.customer_id).subscription = "cancelled"
    return {"subscription": "cancelled"}


def update_address(world: World, args: AddressArguments) -> ToolOutput:
    existing_customer(world, args.customer_id).address = args.address
    return {"address": args.address}


def delete_account(world: World, args: CustomerArguments) -> ToolOutput:
    existing_customer(world, args.customer_id).is_deleted = True
    return {"deleted": True}


SHOP_TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        tool_spec("lookup_order", OrderArguments, lookup_order),
        tool_spec("verify_identity", VerifyArguments, verify_identity),
        tool_spec("issue_refund", RefundArguments, issue_refund),
        tool_spec("cancel_subscription", CustomerArguments, cancel_subscription),
        tool_spec("update_address", AddressArguments, update_address),
        tool_spec("delete_account", CustomerArguments, delete_account),
    )
}


def subject_of(call: ToolCall, world: World) -> str | None:
    """The customer whose account the call touches, judged from what the
    agent sent; None when no known customer is named."""
    spec = SHOP_TOOLS.get(call.tool)
    if spec is None:
        return None
    named = call.arguments.get(spec.subject_from)
    if not isinstance(named, str):
        return None
    if spec.subject_from == "customer_id":
        return named if world.customer(named) is not None else None
    order = world.order(named)
    return order.customer_id if order is not None else None


class FakeShop:
    """One conversation's shop: a private copy of the world, and the calls."""

    def __init__(self, world: World) -> None:
        self.world = world.model_copy(deep=True)
        self.calls: list[ToolCall] = []

    def call(self, turn: int, tool: str, arguments: dict[str, object]) -> ToolCall:
        record = self._run(turn, tool, dict(arguments))
        self.calls.append(record)
        return record

    def _run(self, turn: int, tool: str, arguments: dict[str, object]) -> ToolCall:
        spec = SHOP_TOOLS.get(tool)
        if spec is None:
            return ToolCall(turn, tool, arguments, succeeded=False, error=f"no tool {tool}")
        try:
            result = spec.run(self.world, arguments)
        except ValidationError as error:
            return ToolCall(turn, tool, arguments, succeeded=False, error=describe(error))
        except ToolError as error:
            return ToolCall(turn, tool, arguments, succeeded=False, error=str(error))
        return ToolCall(turn, tool, arguments, succeeded=True, result=result)
