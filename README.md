# AI Flight School

A release gate for customer-support chat agents that call tools. Simulated
customers (confused, angry, or trying to trick it) talk to the agent; its
tools are fakes held by the gate; **code**, not a model, checks every tool
call against your rules. A refund over the order total, or one made before
the customer's identity is checked, fails the build.

## Status

**Resumed on 2026-11-05, after a pause after slice 3. Slices 1 to 6 of 8
are built, all at $0. The thesis pilot's suite and tools are built; its
runs on local models haven't started.**

- **Works today:** the rule checker and the fake shop (slice 1); the
  conversation loop, with records the
  [agent-eval-harness](https://github.com/NabilRobert/agent-eval-harness)'s
  `compare` reads (slice 2); the release gate, the `flightschool` command,
  the GitHub Action, and a reference agent with seven seeded bugs that the
  gate catches in every trial (slice 3); the seed library, the sampler,
  the model-customer path and the in-character checks (slice 4); agents in
  any language over HTTP, with the fake tools served over MCP (slice 5);
  the observer for an agent that keeps its own tools, with a suite for
  Juku's Shiori, tested against a stand-in and run against the real
  Shiori on a scripted model, through mcp-gateway (slice 6); for the
  thesis pilot, an Indonesian sales suite, two sales agents on a model,
  paired customers across runs, and chat records for Project 15.
- **Tested without a real model:** the model customer runs end to end on
  Inspect's `mockllm`. No real model has played a customer yet.
- **Not done yet:** slice 5's timed setup test, where someone new adds
  the gate to CI from this README in under 15 minutes (G7). It needs a
  person; the steps are in the [slice plan](docs/planning/slice-plan.md).
  Shiori on a real model: the scripted run proves the plumbing, not
  her judgement, and a real model's run is paid.
- **Planned next:** the thesis pilot's three runs on local models
  ([thesis-pilot.md](docs/planning/thesis-pilot.md)); a paid
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
- **Agents in any language** (`--agent-url`): Flight School posts each
  turn to the agent's chat endpoint (`flight_school/http/contract.py`),
  and the agent calls its tools on an MCP server Flight School runs on
  `127.0.0.1`, one private URL per conversation. The reference agent gets
  the same verdict both ways. A key for the endpoint goes in
  `FLIGHTSCHOOL_AGENT_KEY`; it is sent, never written.
- **Agents that keep their own tools** (`--audit-log`, `--caller`): for
  an agent behind [mcp-gateway](https://github.com/NabilRobert/mcp-gateway),
  Flight School posts each turn as above and reads the calls it made
  from the gateway's audit log, so they are still observed, not
  self-reported. `examples/shiori/` is a suite for Juku's Shiori: another
  learner's data, abusing `request_replan`, and obeying planted text. Its
  rules name her own tools, listed in its `tools.yaml`.
- **The conversation loop**, on [Inspect AI](https://inspect.aisi.org.uk/):
  customer and agent take turns until the customer ends it with
  `###DONE###`, `###GAVE_UP###` or `###GHOSTED###` (left without a word).
  Running out of turns or time is never a pass, and an agent that crashes
  is an error, never a pass.
- **A sales suite for the thesis pilot** (`examples/sales-id/`):
  synthetic Indonesian WhatsApp chats with a fictional motorbike dealer,
  from 12 personas, 4 goals and 16 tactics. It has no tools and no rules;
  a chat passes when the customer ends with `###DONE###`. Two sales
  agents run on a model (`--agent-model`): `healthy` and
  `never_quotes_price`, the seeded degradation. A model customer opens
  with the same line and draws with the same seed in every run, so two
  runs pair up; `flightschool pairs` says where each pair first differs.
- **Chat records** (`chats.jsonl`): every run also writes its chats as
  Project 15's `ChatRecord` (its `id-chat-records` package), marked
  `source: "synthetic"`.
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

Gate an agent over HTTP, here the reference agent served locally:

```bash
uv run flightschool serve-reference --variant correct --port 8000 &
uv run flightschool run examples/shop --agent-url http://127.0.0.1:8000/chat
```

Your agent answers `POST` requests shaped like
`flight_school/http/contract.py: ChatRequest` with `{"reply": "..."}`, and
calls its tools over MCP on the request's `tools_url`.

Gate an agent that keeps its own tools behind mcp-gateway, reading its
calls from the gateway's audit log (`--caller` is its gateway key's name):

```bash
uv run flightschool run examples/shiori --agent-url http://127.0.0.1:8100/chat \
  --audit-log /path/to/gateway-audit.jsonl --caller shiori
```

Adding `--customer-model openai/gpt-5-mini` (any Inspect model) has a
model play the customers; that calls the provider on your key.

Run the sales suite on local models through Ollama, at $0, and pair two
runs:

```bash
uv run flightschool run examples/sales-id --sample 50 --seed 1 \
  --agent flight_school.reference.sales_agent:healthy --agent-model ollama/llama3.2:3b \
  --customer-model ollama/qwen3.5:4b --out runs/healthy
uv run flightschool pairs runs/healthy runs/healthy-again
```

In GitHub Actions:

```yaml
- uses: NabilRobert/ai-flight-school@main
  with:
    suite: examples/shop
    agent: my_support_bot.flight_school:agent
```

For an agent over HTTP, start it in an earlier step of the job and give
`agent-url` instead of `agent`, as the `gate` job in
`.github/workflows/ci.yml` does.

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
| `flight_school/cli.py` | The `flightschool` command: `run`, `accuracy`, `serve-reference` and `pairs` |
| `flight_school/suite.py` | Loading a suite folder (world, rules, scenarios, and an observed agent's tools) |
| `flight_school/http/` | Adapter A2: the chat contract, the HTTP adapter, the MCP tool server, and the local server helper |
| `flight_school/observer/` | Adapter A3: reading an agent's calls from mcp-gateway's audit log (`audit_log.py`), and the adapter (`adapter.py`) |
| `flight_school/library/` | The seed library's entries (`schema.py`), and crossing and sampling them into scenarios (`sampler.py`) |
| `flight_school/reference/` | The reference agent, its seeded bugs, the accuracy report, the agent served over HTTP (`http_agent.py`), and the sales agents (`sales_agent.py`) |
| `flight_school/export/` | Chat records for Project 15 (`chats.py`) and pairing two runs' chats (`pairs.py`) |
| `action.yml` | The GitHub Action |
| `flight_school/config_files.py` | Loading YAML files, with errors that say what to fix |
| `examples/shop/` | The example world, rules and scenarios; `library/` holds its seed library |
| `examples/shiori/` | A suite for Juku's Shiori, an observed agent: her tools (`tools.yaml`), rules and scenarios |
| `examples/sales-id/` | The thesis pilot's Indonesian sales suite: no tools or rules, a seed library and its own customer prompt |
| `tests/fixtures/logs/` | The labelled conversations, one file per rule kind |
| `tests/scripted_agents.py` | Agents that make fixed calls, for the loop's tests |
| `tests/observed_stub.py` | A stand-in Shiori that writes gateway audit lines, with seeded bugs |
| `docs/guide.md` | How a check runs, step by step, and a glossary |
| `docs/accuracy.md` | The $0 accuracy report, generated by `flightschool accuracy` |

## Licence

Apache-2.0. See [LICENSE](LICENSE).
