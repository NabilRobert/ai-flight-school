# AI Flight School

A release gate for customer-support chat agents that call tools. Simulated
customers (confused, angry, or trying to trick it) talk to the agent; its
tools are fakes held by the gate; **code**, not a model, checks every tool
call against your rules. A refund over the order total, or one made before
the customer's identity is checked, fails the build.

## Status

**Resumed on 2026-11-05, after a pause after slice 3. Slices 1 to 4 of 8
are built, all at $0.**

- **Works today:** the rule checker and the fake shop (slice 1); the
  conversation loop, with records the
  [agent-eval-harness](https://github.com/NabilRobert/agent-eval-harness)'s
  `compare` reads (slice 2); the release gate, the `flightschool` command,
  the GitHub Action, and a reference agent with seven seeded bugs that the
  gate catches in every trial (slice 3); the seed library, the sampler,
  the model-customer path and the in-character checks (slice 4).
- **Tested without a real model:** the model customer runs end to end on
  Inspect's `mockllm`. No real model has played a customer yet.
- **Planned next:** a thesis pilot with simulated Indonesian sales
  customers on local models; the agent over HTTP and the fake tools as an
  MCP server (slice 5); a run against a real agent (slice 6); a paid
  accuracy run with model customers (slice 7, needs a budget not yet
  funded); the write-up (slice 8). The plan is in
  [docs/planning/](docs/planning/slice-plan.md).

Try it with the commands in [Run it](#run-it).

## What works now

- **A fake shop** (`examples/shop/world.yaml`): customers, orders, and seven
  tools an agent might have (`lookup_order`, `list_orders`, `verify_identity`,
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
- **A seed library** (`examples/shop/library/`): 12 personas, 10 goals and
  12 tactics, which cross into 1,440 scenarios. `--sample N --seed S`
  draws the same N for the same seed. Editing an entry changes the task
  hash of every scenario built from it.
- **Model customers:** `--customer-model` has an Inspect model play the
  customer from a prompt built from the persona, goal and tactic. Code
  checks it stayed in character (it didn't call itself an AI, quote its
  instructions, or drop its goal); a run where it broke character is
  inconclusive.
- **The conversation loop**, on [Inspect AI](https://inspect.aisi.org.uk/):
  customer and agent take turns until the customer ends it with
  `###DONE###` or `###GAVE_UP###`. Running out of turns or time is never a
  pass, and an agent that crashes is an error, never a pass.
- **Records in the harness's format** (`meta.json`, `trials.jsonl`), built
  with the harness's own code. Its `compare` regrades them and gates a
  changed agent against a baseline.
- **The gate:** `flightschool run` exits 1 on any critical violation in
  any trial. It exits 2 when a trial errored. With `--baseline`, it also
  exits 1 when task success drops, judged by the harness's `compare`.
- **Measured accuracy at $0** ([docs/accuracy.md](docs/accuracy.md)): all
  7 seeded bugs caught in every trial, with no false alarm on the correct
  agent. Scripted on both sides, so this measures the checker and the
  gate, not a simulated customer's skill.

## Run it

```bash
uv sync --extra dev && uv run pytest
```

Gate an agent (a factory, as `module:attribute`; see `docs/guide.md`):

```bash
uv run flightschool run examples/shop --agent flight_school.reference.agent:correct
```

Draw 50 scenarios from the seed library instead (still scripted, $0):

```bash
uv run flightschool run examples/shop --agent flight_school.reference.agent:correct --sample 50 --seed 1
```

Adding `--customer-model openai/gpt-5-mini` (any Inspect model) has a
model play the customers; that calls the provider on your key.

In GitHub Actions:

```yaml
- uses: NabilRobert/ai-flight-school@main
  with:
    suite: examples/shop
    agent: my_support_bot.flight_school:agent
```

Python 3.12 and [uv](https://docs.astral.sh/uv/). No model key unless you use
`--customer-model`; the first
`uv sync` fetches the harness from GitHub.

## Layout

| Folder | What it does |
|---|---|
| `flight_school/world/` | The shop's data (`schema.py`) and its tools (`shop.py`) |
| `flight_school/log.py` | The record of one conversation: calls and replies |
| `flight_school/rules/` | The rule kinds (`schema.py`) and the checker (`checks.py`) |
| `flight_school/conversation/` | Scenarios, the agent adapter, the customer (scripted or model) and its in-character checks, the loop, the scorer, the records |
| `flight_school/gate.py` | The release gate: one exit code from a run's records |
| `flight_school/cli.py` | The `flightschool` command: `run` and `accuracy` |
| `flight_school/suite.py` | Loading a suite folder (world, rules, scenarios) |
| `flight_school/library/` | The seed library's entries (`schema.py`), and crossing and sampling them into scenarios (`sampler.py`) |
| `flight_school/reference/` | The reference agent, its seeded bugs, and the accuracy report |
| `action.yml` | The GitHub Action |
| `flight_school/config_files.py` | Loading YAML files, with errors that say what to fix |
| `examples/shop/` | The example world, rules and scenarios; `library/` holds its seed library |
| `tests/fixtures/logs/` | The labelled conversations, one file per rule kind |
| `tests/scripted_agents.py` | Agents that make fixed calls, for the loop's tests |
| `docs/guide.md` | How a check runs, step by step, and a glossary |
| `docs/accuracy.md` | The $0 accuracy report, generated by `flightschool accuracy` |

## Licence

Apache-2.0. See [LICENSE](LICENSE).
