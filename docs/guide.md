# Guide

How AI Flight School decides pass or fail, for someone reading the code
for the first time. This covers slice 1: the fake shop and the rule
checker. Simulated customers and agents arrive in slices 2 to 4.

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
| **Agent under test** | The team's support chatbot that the gate is testing | Not in slice 1 |
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

## Where to change things

- **Add a tool to the shop:** in `world/shop.py`, add an arguments model,
  a function, and a `tool_spec(...)` entry in `SHOP_TOOLS`. Rules can name
  it at once.
- **Change the example rules or data:** `examples/shop/rules.yaml` and
  `examples/shop/world.yaml`. Every labelled log is checked against them,
  so run the tests.
- **Add a labelled conversation:** add a case to the file in
  `tests/fixtures/logs/` for the rule kind it's about. Name it as a
  sentence, list its steps, and list the rule ids it must break.
- **Add a rule kind:** a model in `rules/schema.py` (and in the `Rule`
  union), a branch in `checks.py: check_rule`, its names in `tools_named`
  or `arguments_named`, and labelled logs that fire and don't fire.
