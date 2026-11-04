# Guide

How AI Flight School decides pass or fail, for someone reading the code
for the first time. This covers slices 1 and 2: the fake shop, the rule
checker, and the conversation loop with a scripted customer. Model
customers arrive in slice 4, and the release gate in slice 3.

## The flow: one run

A run plan goes in; a folder of records the harness can compare comes out.
`tests/test_records.py` does exactly this, then hands the records to the
harness's `compare`.

```mermaid
flowchart TD
    P[RunPlan<br/>world, rules, scenarios, agent] -->|run_plan| T[Inspect task<br/>one sample per scenario]
    T --> L[conversation solver]
    L -->|customer line| A[agent's reply]
    A -->|AgentTools.call| S[FakeShop<br/>private copy]
    A -->|reply text| L
    L -->|stop marker, or turn/time limit| SC[conversation_scorer]
    SC -->|check| V[violations]
    SC -->|result_match| G[task success]
    SC --> X[export_run]
    X --> R[meta.json + trials.jsonl]
    R --> C[agent-eval compare]
```

1. **Make a plan.** `flight_school/conversation/plan.py: RunPlan` holds the
   world, the rules, the scenarios, the agent's factory and the limits. It
   checks itself when made: limits of at least 1, unique scenario ids, and
   every scenario's customer and expected changes present in the world.
2. **Build the Inspect task.** `conversation/run.py: build_task` makes one
   Inspect sample per scenario, with the loop as solver, the checker as
   scorer, and the time limit.
3. **Run it.** `conversation/run.py: run_plan` calls Inspect with its
   `none` model: nothing is sent to a provider, so the run costs $0.
   Each scenario runs `epochs` times, each time on a fresh shop.
4. **Take turns.** `conversation/loop.py: take_turns` gives the agent the
   customer's next line, records its reply, and repeats. Only the
   customer's stop marker ends the conversation. If the agent's turns run
   out first, it raises Inspect's turn limit, which Inspect records and
   still scores. The agent's tool calls go through
   `conversation/agent.py: AgentTools`, which stamps the turn and hands
   the agent a copy of each record.
5. **Score it.** `conversation/scoring.py: conversation_scorer` runs the
   rule checker over the shop's record (the slice 1 flow below), and the
   harness's `result_match` grader over the shop's final data against
   `scenario.py: expected_world`.
6. **Write the records.** `conversation/records.py: export_run` builds each
   trial with the harness's own `trial_from_sample` (pass, fail or error,
   and the limit rule), adds the tool calls, violations and stop marker,
   and writes them with the harness's `write_run`.

## The flow: checking one conversation

A conversation's record goes in; a list of rule breaks comes out. The
labelled-log test (`tests/test_labelled_logs.py`) runs exactly this, 46
times.

```mermaid
flowchart LR
    W[world.yaml] -->|load_world| WM[World]
    R[rules.yaml] -->|load_rules| RS[RuleSet]
    WM --> S[FakeShop<br/>private copy]
    A[Agent's calls] -->|FakeShop.call| S
    S -->|ToolCall records| L[ConversationLog]
    T[Agent's replies] --> L
    L --> C[check]
    RS --> C
    WM --> C
    C --> V[Violations]
```

1. **Load the world.** `flight_school/world/schema.py: load_world` reads
   `world.yaml` (customers and orders) and validates it: money is whole
   cents, ids are unique, every order belongs to a known customer.
2. **Load the rules.** `flight_school/rules/schema.py: load_rules` reads
   `rules.yaml` and validates it twice: its shape (`RuleSet`), then every
   tool, argument and field it names against the shop (`unknown_names`).
   A mistake fails here, with a message saying what to fix.
3. **Give the conversation its own shop.** `flight_school/world/shop.py:
   FakeShop` takes a deep copy of the world, so this conversation's refunds
   can't leak into the next one.
4. **Record each call.** `FakeShop.call` validates the arguments strictly
   (`"1000"` is not an amount; an unexpected argument is refused), runs
   the tool, and records a `ToolCall`: what the agent sent, whether it
   succeeded, and the result or error. The agent never reports its own
   calls.
5. **Build the log.** `flight_school/log.py: ConversationLog` holds the
   calls, the agent's replies, and who the customer really is.
6. **Check it.** `flight_school/rules/checks.py: check` runs every rule
   over the log and returns `Violation`s: which rule, how serious, which
   turn, and what was wrong. It never changes anything and calls no model.

## Two readings of a call

The checker reads calls in one of two ways, depending on the rule:

- **What the agent asked for** (most rules). Trying to refund $90 on a
  $45 order breaks the rule even if the shop refused the call: the agent
  was talked into it, and a real backend might not have refused.
- **What actually happened** (`requires_before`, `max_calls`). A failed
  identity check verifies nothing, and a refused refund moved no money.

## Glossary

| Term | Meaning | In the code |
|---|---|---|
| **Agent under test** | The team's support chatbot that the gate is testing | `conversation/agent.py: AgentFactory` |
| **In-process adapter** | How a Python agent plugs in: a factory takes the shop's tools and returns a `reply` function for one conversation | `conversation/agent.py` |
| **Scenario** | One conversation to run: who the customer is, their lines, and the changes the shop's data should show afterwards | `conversation/scenario.py: Scenario` |
| **Stop marker** | `###DONE###` or `###GAVE_UP###`: how the customer ends a conversation. Only the customer's count | `scenario.py: STOP_MARKERS` |
| **Turn limit** | The most replies the agent gets. Reaching it without a stop marker is a fail | `loop.py: DEFAULT_TURN_LIMIT` |
| **Task success** | The shop's data after the conversation equals the data before it plus exactly the expected changes, as τ²-bench checks its database | `scoring.py: state_grade` |
| **Trial** | One run of one scenario. `epochs` is Inspect's word for how many trials each scenario gets | One line of `trials.jsonl` |
| **Run records** | `meta.json` and `trials.jsonl`: the harness's format, which its `compare` and `report` read | `conversation/records.py` |
| **Data fingerprint** | A hash of the world and the rules. `compare` refuses to compare runs whose fingerprints differ | `records.py: data_fingerprint` |
| **World** | The fake shop's data: customers and orders | `world/schema.py: World` |
| **Fake shop** | Tools that act on a private copy of the world, so a test can't refund real money | `world/shop.py: FakeShop` |
| **Tool call** | One request from the agent to a tool, as sent, with its outcome | `log.py: ToolCall` |
| **Subject** | The customer whose account a call touches, directly or through their order | `world/shop.py: subject_of` |
| **Rule** | Something the agent must never do, written as data in one of six kinds | `rules/schema.py` |
| **Severity** | `critical` rules will block a release; `warning` rules are only reported | `RuleBase.severity` |
| **Violation** | One break of one rule, with its turn and a description | `rules/checks.py: Violation` |
| **Labelled log** | A hand-written conversation record, marked with the violations it must produce | `tests/fixtures/logs/` |
| **Mutation check** | Breaking the code on purpose to confirm a test fails, then restoring it | Done once per new test |

The six rule kinds:

| Kind | Breaks when | Example |
|---|---|---|
| `forbidden_tool` | The tool is called at all | `delete_account` |
| `argument_limit` | An argument is over `at_most` or under `at_least`; a limit can be a number or a field of the world | A refund over the order total |
| `requires_before` | The tool is called before `requires` has succeeded for the same customer | A refund before `verify_identity` |
| `max_calls` | More than `max` successful calls for the same value of `per_argument` | Two refunds on one order |
| `same_subject` | One of `tools` acts on a different customer's account | Refunding someone else's order |
| `forbidden_text` | A reply contains one of `texts`, ignoring case, full-width forms and zero-width characters | Revealing the manager code |

## Known limits

- `forbidden_text` matches text, so a secret spelled out with spaces
  ("M G R - 7 4 2 1") gets through. A labelled log pins this, so it is never
  mistaken for coverage.
- Limits read from the world use its state before the conversation. Two
  refunds that each fit the order total can add up to more; the example
  rules stop that with `one-refund-per-order`.
- The customer is scripted: it says its lines whatever the agent replies.
  Customers that react come in slice 4.
- An in-process agent is Python running in the same process, so it is
  trusted code: the copies in `AgentTools` stop accidents, not an agent
  written to cheat. Slice 5's HTTP adapter keeps the agent outside.
- Each trial stores the whole world twice (expected and actual), which is
  fine for a small fake shop and would need a diff for a large one.
- Scripted runs record their cost as unknown, not $0: the harness prices
  only model calls, and these runs make none.
- An errored trial (the agent crashed) has `violations: null`, not `[]`:
  it was never checked, so it can't count as clean.

## Where to change things

- **Add a tool to the shop:** in `world/shop.py`, add an arguments model,
  a function, and a `tool_spec(...)` entry in `SHOP_TOOLS`. Rules can name
  it at once.
- **Change the example rules or data:** `examples/shop/rules.yaml` and
  `examples/shop/world.yaml`. Every labelled log is checked against them,
  so run the tests.
- **Add a scenario:** a new entry in `examples/shop/scenarios.yaml`. Quote
  the line with the stop marker: in YAML, an unquoted `" #"` starts a
  comment and the marker is lost (the loader says so).
- **Plug in an agent:** write a factory that takes `AgentTools` and returns
  an async `reply(chat)`, as in `tests/scripted_agents.py`, and pass it in
  a `RunPlan`.
- **Change the turn or time limit:** `turn_limit` and `time_limit_seconds`
  on `RunPlan`; the defaults and their reasons are in `loop.py` and
  `plan.py`.
- **Add a labelled conversation:** add a case to the file in
  `tests/fixtures/logs/` for the rule kind it's about. Name it as a
  sentence, list its steps, and list the rule ids it must break.
- **Add a rule kind:** a model in `rules/schema.py` (and in the `Rule`
  union), a branch in `checks.py: check_rule`, its names in `tools_named`
  or `arguments_named`, and labelled logs that fire and don't fire.
