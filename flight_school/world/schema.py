"""The shop's data, as a team writes it in `world.yaml`.

Money is whole cents in an `int`, never a float. The tools in `shop.py`
change a copy of this data; the file itself is never changed.
"""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flight_school.config_files import load_model


class Customer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    name: str
    email: str
    address: str
    subscription: Literal["active", "cancelled"]
    is_deleted: bool = False


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    customer_id: str
    total_cents: int = Field(ge=0)
    refunded_cents: int = 0
    # Free text anyone could have written (a customer, a courier), so the
    # agent must read it as data, never as instructions to follow.
    note: str = ""


class World(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    customers: list[Customer]
    orders: list[Order]

    @model_validator(mode="after")
    def check_references(self) -> Self:
        customer_ids = [customer.id for customer in self.customers]
        order_ids = [order.id for order in self.orders]
        for kind, ids in (("customer", customer_ids), ("order", order_ids)):
            if len(set(ids)) != len(ids):
                raise ValueError(f"two {kind}s share an id; each id must be unique")
        for order in self.orders:
            if order.customer_id not in customer_ids:
                raise ValueError(f"order {order.id} names unknown customer {order.customer_id}")
        return self

    def customer(self, customer_id: str) -> Customer | None:
        return next((c for c in self.customers if c.id == customer_id), None)

    def order(self, order_id: str) -> Order | None:
        return next((o for o in self.orders if o.id == order_id), None)


# What a rule's `collection` can name, and the model behind each.
COLLECTIONS: dict[str, type[BaseModel]] = {"customers": Customer, "orders": Order}


def load_world(path: Path) -> World:
    return load_model(path, World)
