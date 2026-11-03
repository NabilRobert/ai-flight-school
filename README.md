# AI Flight School

A release gate for customer-support chat agents that call tools. Simulated
customers (confused, angry, or trying to trick it) talk to the agent; its
tools are fakes held by the gate; **code**, not a model, checks every tool
call against your rules. A refund over the order total, or one made before
the customer's identity is checked, fails the build.

**Status: slice 1 of 8.** This slice is the part that decides pass or fail:
the rule checker and the fake shop. There are no simulated customers or
agents yet. The plan is on the `docs/planning` branch.

## What works now

- **A fake shop** (`examples/shop/world.yaml`): customers, orders, and six
  tools an agent might have (`lookup_order`, `verify_identity`,
  `issue_refund`, `cancel_subscription`, `update_address`,
  `delete_account`). Each conversation gets its own copy, and every call
  is recorded with what the agent sent and whether it succeeded.
- **Rules as data** (`examples/shop/rules.yaml`), in six kinds:
  `forbidden_tool`, `argument_limit`, `requires_before`, `max_calls`,
  `same_subject`, `forbidden_text`. A rule naming a tool, argument or field
  that doesn't exist fails on load, with a message saying what to fix.
- **A checker** that turns a conversation's record into violations, with
  no model and no I/O.
- **46 hand-labelled conversations** (`tests/fixtures/logs/`), each marked
  with the violations it must produce. The checker gets all of them right.

## Run it

```bash
uv sync --extra dev && uv run pytest
```

Python 3.12 and [uv](https://docs.astral.sh/uv/). No model key, no network.

## Layout

| Folder | What it does |
|---|---|
| `flight_school/world/` | The shop's data (`schema.py`) and its tools (`shop.py`) |
| `flight_school/log.py` | The record of one conversation: calls and replies |
| `flight_school/rules/` | The rule kinds (`schema.py`) and the checker (`checks.py`) |
| `flight_school/config_files.py` | Loading YAML files, with errors that say what to fix |
| `examples/shop/` | The example world and rules |
| `tests/fixtures/logs/` | The labelled conversations, one file per rule kind |
| `docs/guide.md` | How a check runs, step by step, and a glossary |

## Licence

Apache-2.0. See [LICENSE](LICENSE).
