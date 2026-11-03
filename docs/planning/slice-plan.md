# Slice Plan and Cost Model

## Prerequisites (outside this repo)

| # | Prerequisite | Needed for | Who |
|---|---|---|---|
| P1 | Arthur OKs Phases 1, 2 and 5 | Slice 1 | Arthur |
| P2 | The GitHub repo exists | Pushing anything | Arthur |
| P3 | MIT licences on mcp-gateway and juku-agents (approved 2026-11-03) | Any future reuse of their code in the core (none planned in v1; running them for slice 6 is fine) | Their sessions |
| P4 | Someone who hasn't seen the scenario library, for the blind realism check (about an hour) | Slice 7 | Arthur, asking around |
| P5 | A top-up for the paid accuracy run, separate from Juku's $5 (approved, not a priority yet) | Slice 7 | Arthur |
| P6 | One developer who hasn't seen it, for the setup test; later, one support team | G7; any hosting decision | Arthur, asking around |

## Spikes (local, $0)

| # | Question | Method | Pass | Time |
|---|---|---|---|---|
| 1 | Do the harness's pins fit? | A scratch project depending on the harness at a pinned commit; import `compare`, `budget`, the record format | Imports and `agent-eval compare` work on a hand-made record; any pin conflict goes to the harness session | 30 min |
| 2 | Can Inspect play both sides at $0? | A solver with a `mockllm` customer (`role="user"`) and a `mockllm` agent calling one fake tool, 5 turns | The log shows both sides and the tool call with its arguments | 1 h |
| 3 | Can Strands Evals drive a non-Strands agent? | Read its docs and source; try its GOAT attacker against a plain Python agent with a scripted model | Answered; ADR-007 revisited if it can, cleanly | 1 h |
| 4 | Does the τ² user loop swallow errors? | Run `inspect_evals` τ² with a `mockllm` user that raises | Reproduced or not; if it is, Arthur reports it upstream | 30 min |
| 5 | Does the gateway's audit log give Shiori's tool calls in full? | Run Juku's eval stack with a scripted model; read the audit log | Calls and arguments present, or the gap written down | 1 h |
| 6 | Can ABCD be used? | Read its licence and terms | Licence allows publishing a labelled sample, or another dataset is chosen | 15 min |

## Slices

**Evaluation-driven order, as in Juku and the finance tracker:** the tests
and fixtures come first and fail. Then the code is written until they pass.
Each new test is mutation-checked once. Each slice updates `docs/guide.md`.

| Slice | Delivers | Done when | Cost |
|---|---|---|---|
| **1. Rule checker and fake shop** | Repo scaffold, README, LICENSE, CI, complexity rules; the world and rule schemas; the fake shop's tools; the tool-call log; the checker; labelled logs | See below | $0 |
| **2. Conversation loop** | The Inspect task: solver, scripted customer, in-process adapter (A1), scorer; records in the harness's format; turn limit and stop markers | A scripted conversation produces a record the harness's `compare` reads; a run with no stop marker is never a pass | $0 |
| **3. Reference agents and the gate** | The correct and seeded-bug reference agents (scripted); the absolute and relative gate; exit codes; `flightschool run`; the GitHub Action; the $0 accuracy report | Every seeded bug found, every run; 0 false alarms on the correct variant; same seed gives the same verdict; CI blocks a seeded-bug branch | $0 |
| **4. Seed library** | Personas, goals, tactics; the sampler and hashes; the model-customer path (tested with `mockllm`); in-character checks | Thousands of scenarios from a few dozen entries; a changed entry changes the hash; the model path runs end to end at $0 | $0 |
| **5. HTTP and MCP** | The chat endpoint contract (A2); the fake tools as an MCP server; the reference agent served over HTTP; key and outbound-call tests | The same verdicts over HTTP as in process; no key in any output; a timed setup by someone new (G7) | $0 |
| **6. Shiori** | The observer adapter (A3); scenarios for her real risks; a scripted run against Juku's eval stack | Results reported as they are, including what can't be tested (no memory between turns) | $0 |
| **7. Paid accuracy run (Should)** | Model customers against model-backed reference agents; miss rate per bug and tactic; the blind realism check | Arthur's OK for each paid run; numbers published with intervals | About $2 to $9, not funded |
| **8. Evidence and write-up** | Results from records; JOURNEY; portfolio entry (with the portfolio session) | Every number traces to a file | $0 |

Slices 1 to 6 cost nothing and need nothing from Arthur except P1 and P2.

## Slice 1 in detail: the first slice

**Scope:** pure Python, no I/O, no model, no Inspect. It is the part that
decides pass or fail, so it is built and proven first.

**Delivers:**
- `pyproject.toml` (uv), ruff with the complexity rules (`C901` at 10,
  `PLR0911`, `PLR0912`, `PLR0913`, `PLR0915`), pyright strict;
- `.github/workflows/ci.yml`, `LICENSE` (Apache-2.0), a README with a
  layout section, `docs/guide.md`;
- `flight_school/world/`: the world schema (Pydantic), a seeded copy per
  conversation, the fake shop's tools, the tool-call log;
- `flight_school/rules/`: the rule schema and the six checks in R2, as pure
  functions;
- `examples/shop/world.yaml` and `examples/shop/rules.yaml`;
- `tests/fixtures/logs/*.yaml`: about 40 hand-written tool-call logs, each
  labelled with the violations expected (none, or which rules);
- a short report: checks, fixtures, wrong verdicts.

**Order:**
1. Write the labelled logs and their loader. Tests fail.
2. Write the world and the fake tools until a log can be replayed into a
   final state.
3. Write each check until its fixtures pass.
4. Spend a pass trying to break it: an empty log, unknown tools, missing
   arguments, wrong types, huge amounts, negative amounts, unicode ids, a
   rule pointing at a field that doesn't exist, two subjects in one call.

**Done when:**
- wrong verdicts on the labelled logs: **0**;
- every rule kind has a fixture that fires and one that doesn't;
- a bad rule file fails validation with a message saying what to fix;
- CI is green, and the new tests are mutation-checked.

**Branch:** `feat/rule-checker`, from `main`, once `docs/planning` is
merged.

## Cost model

Full reasoning in [ADR-014](phase-5-architecture-decisions.md#adr-014-costs-the-teams-key-0-for-arthur-in-development).

| Item | Cost |
|---|---|
| Development, slices 1 to 6 | $0: scripted customers and agents |
| A team's default CI gate | $0: scripted |
| A team's model run, 600 conversations | About $3.50 customer side with gpt-5-mini, plus their agent's own cost; on their key |
| Hosting | None in v1: it runs in the team's CI |

**Slice 7's estimate (Arthur's money, not funded):** 7 reference variants
× 30 scenarios × 3 epochs = 630 conversations.

| | gpt-5-mini | gpt-5-nano |
|---|---|---|
| Customer side, about $0.006 a conversation | $3.80 | $0.75 |
| Reference agent, about $0.0074 a conversation (8 turns × 2,500 in, 150 out) | $4.70 | $0.95 |
| **Total** | **about $8.50** | **about $1.70** |

Recommended: one nano run first, then a smaller mini run if the nano
customer proves too weak to find the bugs. Prices are the harness's
checked Sumopod prices (2026-10-23); Juku's $5 can't be used.
