# AI Flight School

A release gate for customer-support chat agents that call tools. Simulated
customers (confused, angry, or trying to trick it) talk to the agent; its
tools are fakes held by the gate; **code**, not a model, checks every tool
call against your rules. A refund over the order total, or one made before
the customer's identity is checked, fails the build.

**Status: slice 2 of 8.** The rule checker and the fake shop (slice 1),
and the conversation loop (slice 2): a scripted customer talks to an agent
running in process, and each run is written as records the
[agent-eval-harness](https://github.com/NabilRobert/agent-eval-harness)'s
`compare` reads. There are no model customers and no reference agents yet.
The plan is on the `docs/planning` branch.

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
  no model and no I/O. 46 hand-labelled conversations
  (`tests/fixtures/logs/`) check it; it gets all of them right.
- **Scenarios** (`examples/shop/scenarios.yaml`): who the customer is,
  their lines, and how the shop's data should look afterwards.
- **The conversation loop**, on [Inspect AI](https://inspect.aisi.org.uk/):
  customer and agent take turns until the customer ends it with
  `###DONE###` or `###GAVE_UP###`. Running out of turns or time is never a
  pass, and an agent that crashes is an error, never a pass.
- **Records in the harness's format** (`meta.json`, `trials.jsonl`), built
  with the harness's own code. Its `compare` regrades them and gates a
  changed agent against a baseline.

## Run it

```bash
uv sync --extra dev && uv run pytest
```

Python 3.12 and [uv](https://docs.astral.sh/uv/). No model key; the first
`uv sync` fetches the harness from GitHub.

## Layout

| Folder | What it does |
|---|---|
| `flight_school/world/` | The shop's data (`schema.py`) and its tools (`shop.py`) |
| `flight_school/log.py` | The record of one conversation: calls and replies |
| `flight_school/rules/` | The rule kinds (`schema.py`) and the checker (`checks.py`) |
| `flight_school/conversation/` | Scenarios, the agent adapter, the loop, the scorer, the records |
| `flight_school/config_files.py` | Loading YAML files, with errors that say what to fix |
| `examples/shop/` | The example world, rules and scenarios |
| `tests/fixtures/logs/` | The labelled conversations, one file per rule kind |
| `tests/scripted_agents.py` | Agents that make fixed calls, for the loop's tests |
| `docs/guide.md` | How a check runs, step by step, and a glossary |

## Licence

Apache-2.0. See [LICENSE](LICENSE).
