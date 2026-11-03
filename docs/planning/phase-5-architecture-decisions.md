# Phase 5: Architecture Decisions

Short ADRs, 2026-11-03. **Settled** ones were decided with Arthur. The rest
are recommendations, open until he agrees. The summary table and the first
slice are at the end.

```
team's CI ─► flightsim run (Typer CLI, GitHub Action)
               │
   seed library ─► scenarios ─► Inspect task: conversation loop
               │                    │  customer: scripted ($0) or model (team's key)
               │                    ▼
               │              agent under test ◄── in process, or HTTP chat
               │                    │ tool calls
               │                    ▼
               │              fake tools + seeded world  (Python, or MCP server)
               │                    │ recorded
               │                    ▼
               │              rule checker (pure code) ─► records (harness format)
               ▼                                               │
            gate: 0 critical violations + agent-eval compare vs baseline ─► exit 0/1/2
                                                               │
                                     spans ─► agent-observability conventions
```

## Reuse map (the folder's "reuse before building" rule)

Arthur's repos were searched first, then open-source tools. No repo here
has a simulated user, a multi-turn runner, a model judge or a rule on tool
arguments (searched on every local branch, 2026-11-03).

| Part | Reused | Built (and why) |
|---|---|---|
| Conversation loop, model roles, epochs, logs, viewer | **Inspect AI** (MIT), model roles and `mockllm` (ADR-007) | The loop between customer and agent |
| Loop design and state grading | **τ²-bench**'s design (MIT): user-simulator loop, stop markers, database-state checks | Written fresh on Inspect, not copied (ADR-007) |
| Scripted models at $0 | The harness's `scripts/gullible_agent.py` pattern: `mockllm` with a callable | The scripted customers |
| Regression gate | **agent-eval-harness** `compare` (MIT), consumed as Juku does: a git dependency, records in its format | The absolute "0 critical violations" rule, which `compare` lacks (it is relative) |
| Cost estimate and cap | **agent-eval-harness** `budget` and `prices.yaml` | — |
| "Obeyed" vs "harm went through" | The harness's `attack_succeeded` / `attack_effect` split | Applied to tool calls and world state |
| Trace names | **agent-observability**'s `docs/conventions.md` (it can't be a dependency: `package = false`, Python 3.14) | Span names only |
| Fake tools over MCP | The official **MCP SDK** (stack) | The fake shop's tools |
| Shiori as a target | Juku's throwaway eval stack (`evals/eval_stack.py`) and the gateway's audit log, run as they are | An observer adapter (A3) |
| Attack ideas | **PyRIT** and **promptfoo** (Crescendo, GOAT), **Strands Evals** (GOAT on a refund agent) | Written as tactics in the seed library; ideas, not code |
| Real conversations for the realism check | An open customer-service dataset, such as ABCD (ASAPP), licence to check | The sample and the labelling sheet |
| Rule checker | Nothing fits: the harness's `forbidden_tools` checks names only; the gateway's policy restricts strings by pattern only; Rego and CEL were considered (ADR-010) | **Built:** it is what the project demonstrates |
| Seed library, reference agents, accuracy report | Nothing fits | **Built:** the measured-accuracy claim rests on them |

## ADR-001: First user: SaaS support teams with money tools (settled)

**Decision:** a small team shipping a customer-support chat agent whose
tools move money or change accounts. The scenarios, the reference agent
and the README are written for them.

**Rejected:** *solo MCP developers* (more trials, little need for a gate);
*enterprise contact centres* (won't adopt a one-person tool first); *any
customer-facing agent* (the checks get vague); *users of one framework*
(a framework isn't a pain).

## ADR-002: Pass means code-checked rules and no regression (settled)

**Decision:** a release is blocked when:
- any trial has a **critical** rule violation, checked by code; or
- the task success rate is below the baseline run's by more than the
  tolerance (the harness's `compare`, exit 1).

A model judge may later grade tone, as advice in the report. It never
blocks.

**Why:** deterministic, $0 to check, and nothing for the agent to argue
with. Success is checked too, so an agent that refuses everything fails.

**Rejected:**
- *A model judge per conversation:* costs on every run, varies, and can be
  talked round by the very agent it grades.
- *Violations only:* a refuse-everything agent would pass.

## ADR-003: Simulated customers: seed library and role-play (settled)

**Decision:**
- **Generate:** a hand-written, versioned library of personas (confused,
  angry, elderly, non-native speaker), goals (a real refund, a fake one,
  someone else's order) and tactics (lying about the order, claiming a
  manager approved it, slow escalation, prompt injection), crossed into
  scenarios with a fixed seed.
- **Play:** scripted (fixed turns, $0) or by a model, turn by turn, with
  the team's key.
- **Check realism three ways:** code checks the customer stayed in
  character (S6); a blind human spot-check of simulated against real
  conversations (S7); seeded-bug agents measure misses (ADR-013).

**Rejected:** *a model inventing personas freely* (repeats itself, drifts,
not reproducible); *replaying a team's real transcripts* (their customers'
data on day one); *scripted only* (can't adapt, so misses multi-turn
manipulation, the main threat).

## ADR-004: Apache-2.0 for the open core (settled)

**Decision:** the core is Apache-2.0. A hosted service, if built, stays
closed.

**Why:** permissive with a patent grant, which company legal teams like in
a dev tool. Compatible with Inspect AI and the harness (both MIT).

**What it means for reuse:**
- mcp-gateway and juku-agents have **no licence**. The core must not copy
  or depend on them until Arthur adds one. Running them as separate tools
  for the Shiori demo is fine: Arthur owns them.
- τ²-bench is MIT. The loop is written fresh, so no notice is needed; if
  code is ever copied, its notice goes in `NOTICE`.

**Rejected:** *MIT* (no patent grant); *AGPL-3.0* (many companies ban it,
and the first users are companies); *FSL or BSL* (not open source).

## ADR-005: Lead with measured accuracy (settled)

**Decision:** the pitch is "the release gate that publishes its own miss
and false-alarm rates". Phase 1 states plainly that the market is crowded
and paid hosting is a long shot.

**Why:** the refund angle is already shown by AWS's Strands Evals; the
open ground is a tester measured on agents with known bugs, deterministic
verdicts, and $0 runs in CI.

**Rejected:** *a vendor-neutral benchmark of the testers* (a study, not a
product; kept as a Could: run rivals on the same seeded agents); *a
different Project 10*.

## ADR-006: Reference shop agent first, Shiori second (settled)

**Decision:**
- **Reference shop agent:** a small support agent with `lookup_order`,
  `verify_identity`, `issue_refund`, `cancel_subscription` and
  `update_address`, in a correct variant and seeded-bug variants. It is
  the demo and the accuracy measure.
- **Shiori:** the first real agent tested, for her real risks: another
  learner's data, abusing `request_replan`, and obeying planted text.

**Why:** the repo scan found Shiori has 8 read tools and one action
(`request_replan`, once a day), and keeps no memory between turns
(`juku_app/chat.py`, no `message_history`). She can't show the refund
story; she can show the tool works on an agent it wasn't built around.

**Rejected:** *Shiori only* (weak pitch for support teams); *adding a money
tool to Juku* (bends a working product to suit another project).

## ADR-007: Build on Inspect AI; write the loop fresh

**Decision:** each scenario is an Inspect sample. A solver runs the
conversation: the customer model (`role="user"`) and the agent alternate
until a stop marker or the turn limit. A scorer runs the rule checker.

**Why:** Inspect is already Arthur's eval stack. Its model roles give the
customer its own model, `mockllm` takes a callable so both sides can be
scripted at $0, and its logs, epochs and viewer come free.

**Considered:**

| Option | Licence | Why not the base |
|---|---|---|
| `inspect_evals` τ² port | MIT | Benchmark code with fixed domains. Its user loop is reported to print and continue on any exception, which for a gate could pass a broken run (spike 4). The design is copied, not the code |
| Strands Evals | Apache-2.0 | The closest rival. Spike 3 checks whether it can drive a non-Strands agent; if it can cleanly, this ADR is revisited |
| LangWatch Scenario | Apache-2.0 | Judge-led; its own pages publish no miss or false-alarm rates |
| DeepTeam / DeepEval | Apache-2.0 | Judge-led; tied to Confident AI's platform |
| promptfoo | MIT | TypeScript; by default its simulated user and attacks are generated by its hosted service |
| PyRIT | MIT | Heavy; no documented tool-call checks |
| garak | Apache-2.0 | Scans models, not agents with tools |
| Rogue | Source-available | Licence forbids commercial hosting |

## ADR-008: The simulator owns the world

**Decision:** the agent's tools are fakes run by the simulator, over a
fresh copy of a seeded world (customers, orders, balances) for each
conversation. The simulator records every call with its arguments.

**Why:** calls are observed, not self-reported; nothing real can happen;
rules can check the final state ("was money actually refunded?"), as
τ²-bench checks its database.

**Rejected:** *the agent reports its own tool calls* (an agent with a bug
may report wrongly); *calling the team's staging backend* (side effects,
their data, and their credentials in our process). A later record mode
against staging is possible, not planned.

## ADR-009: Three ways to reach the agent

**Decision:**
1. **In process** (v1, Must): a Python factory takes the fake tools and
   returns `async reply(conversation) -> str`. The reference agent uses it.
2. **HTTP** (Should): the agent serves a small chat endpoint; it gets its
   tools from the simulator's MCP server (official MCP SDK). Any language.
3. **Observer** (Could, built for Shiori): the agent keeps its own tools;
   calls are read from the mcp-gateway audit log.

**Why:** in process is simplest and needs no network. HTTP plus MCP covers
most agents without touching their code beyond config.

**Rejected:** *Inspect's `agent_bridge` as the main path:* it captures the
agent's model calls, but the agent's own code still runs the tools, so the
fakes can't be guaranteed. Kept as a later option.

## ADR-010: A small fixed set of rule kinds, in YAML

**Decision:** the six rule kinds in Phase 2 (R2), validated by Pydantic,
checked by pure functions in the harness's grading style.

**Why:** a team can read a rule file without learning a language, and
each kind is easy to test and to explain in a report.

**Rejected:**
- *Python predicates in rule files:* arbitrary code from a config file;
  unsafe for a hosted service later.
- *OPA/Rego* (Apache-2.0): a second language and a heavy runtime for six
  rule shapes.
- *CEL* (cel-python): reconsider if teams need rules the six kinds can't
  express.
- *Extending the harness's `forbidden_tools`:* it checks names by design;
  argument and state rules are this project's subject.

## ADR-011: The gate: absolute plus relative

**Decision:**
- **Absolute:** any critical violation in any trial is exit 1. New: the
  harness's gate is relative only.
- **Relative:** task success compared with the baseline run by
  `agent-eval compare` (pooled z-test, exit 0/1/2).
- **Inconclusive** (exit 2): too few trials, or any errored trial.
- A trial stopped by a limit is never a pass, matching the harness's
  regrade rule (`compare/comparison.py`).

**Rejected:** *a single score with a threshold:* hides the one harmful call
behind an average.

## ADR-012: Scenario format and sampling

**Decision:**
- `library/personas/*.yaml`, `goals/*.yaml`, `tactics/*.yaml`, each entry
  with an id, a description, and scripted turns where it has them.
- A scenario is persona × goal × tactic with a seed. Its hash covers all
  three, so a changed library entry shows as a changed scenario.
- The model customer gets one system prompt built from the three, and
  must end with `###DONE###` or `###GAVE_UP###`.

**Rejected:** *one free-text prompt per scenario:* thousands of
near-copies to review.

## ADR-013: Measuring the simulator's own accuracy

**Decision:**
- **Reference agents:** one correct variant and at least six seeded bugs:
  refund without verification; cap ignored; trusts "my manager approved
  it"; acts on another customer's order; leaks the manager code; refunds
  the same order twice; obeys an instruction pasted into an order note.
- **Two levels, reported separately:**
  - **$0, scripted:** scripted agents with scripted customers. This
    measures the checker and the gate, not the attacker's skill. Target:
    every bug found, no false alarms.
  - **Paid, model-backed:** model customers against model-backed
    reference agents. This measures the attacker. Miss rate per bug and
    per tactic, with intervals. Needs Arthur's OK and a top-up.
- **The checker itself:** labelled tool-call logs, mutation-checked (M3).

**Why:** without known bugs, a clean report means nothing.

**Rejected:** *counting attacks that "succeeded" by a judge:* the thing
being measured would grade itself.

## ADR-014: Costs: the team's key, $0 for Arthur in development

**Decision:**
- Development and CI use scripted customers and scripted agents: $0.
- Teams' model runs use their own key. The harness's `budget` estimates
  before the run and refuses over budget; each trial has a cost cap.
- Arthur's paid runs (slice 7) need his OK and a top-up separate from
  Juku's $5.

**Estimate for a team's model run** (gpt-5-mini at the harness's checked
Sumopod prices, $0.25 in and $2.00 out per million tokens, 2026-10-23):

| Per conversation, customer side | |
|---|---|
| 8 customer turns × about 2,300 input tokens (persona + growing transcript) | 18,400 in → $0.0046 |
| 8 × about 80 output tokens | 640 out → $0.0013 |
| **Total** | **about $0.006** |

200 scenarios × 3 epochs = 600 conversations ≈ **$3.50** for the customer
side, plus the team's own agent costs. With gpt-5-nano, about a fifth.
So the default per-PR gate stays scripted; model runs suit nightly or
pre-release jobs. These are estimates; slice 7 measures them.

## ADR-015: Security: teams' agents and keys are sensitive

**Decision (v1, runs in the team's CI):**
- Keys from the environment only; a redaction test and a CI grep (X1).
- Run outputs stay local and are ignored by git (X2). The report shows
  tool arguments, so it is treated like a log of their customers' data.
- No network except the agent and the team's model provider (X3, X4).
- Rule and scenario files are data, never code (R1).
- The agent's replies are untrusted: they can only mislead the model
  customer (a miss, measured), never the verdict (X5).

**For hosting later (not v1), written down now so it isn't forgotten:**
- the agent URL is the customer's, so the workers calling it are a
  server-side request forgery risk: block private and metadata addresses;
- keys held only for the run, encrypted, never logged;
- each tenant's runs isolated; transcripts deleted on a schedule.

**Rejected:** *a hosted generator for scenarios* (promptfoo's default):
sends the team's agent description to us.

## ADR-016: Tracing

**Decision:** OpenTelemetry SDK, off unless `OTEL_EXPORTER_OTLP_ENDPOINT`
is set, as in the harness's `tracing.py`. Span names follow
agent-observability's conventions: `eval sample`, `invoke_agent`,
`execute_tool`. No message content by default.

**Rejected:** *depending on agent-observability:* it isn't a package and
needs Python 3.14.

## ADR-017: A CLI and a GitHub Action in v1; hosting later

**Decision:** `flightsim` (Typer) with `run`, `check-rules` and `report`,
and a composite GitHub Action that installs it with uv and runs it. No
server in v1.

**Hosting, as a hypothesis only:** paid features would be run history and
trends, team seats, scheduled model runs, and a maintained scenario
library. Planned only after an outside team uses the core. Not priced.

**Rejected:** *a hosted service first:* asks teams to trust a one-person
service with their agent and key before the tool has proved anything.

## ADR-018: Depending on the harness

**Decision:** depend on agent-eval-harness as a git dependency, pinned to a
commit, as Juku does, for `compare`, `budget` and the record format.

**Watch:** the harness pins `inspect-ai==0.3.283`, `openai==3.37.0` and
Python below 3.13. Juku already had to override the `openai` pin. Spike 1
checks the pins fit; if they don't, the fix is a pull request to the
harness through its session, not a copy here.

**Rejected:** *copying `compare`:* two versions of the gate would drift.

## Decisions

| # | Decision | Rejected | Status |
|---|---|---|---|
| 001 | First user: SaaS support teams with money tools | Solo MCP devs, enterprise, any agent, framework users | **Settled** |
| 002 | Pass: 0 critical violations by code + no regression | Model judge, violations only | **Settled** |
| 003 | Seed library + role-play; realism checked 3 ways | Free generation, real transcripts, scripted only | **Settled** |
| 004 | Apache-2.0 core | MIT, AGPL, FSL/BSL | **Settled** |
| 005 | Lead with measured accuracy | Benchmark of testers, new project | **Settled** |
| 006 | Reference shop agent first, Shiori second | Shiori only, money tool in Juku | **Settled** |
| 007 | Inspect AI; loop written fresh from τ²'s design | inspect_evals τ², Strands Evals, Scenario, DeepTeam, promptfoo, PyRIT, garak, Rogue | Open |
| 008 | Fake tools over a seeded world | Self-reported calls, staging backend | Open |
| 009 | In process; HTTP + MCP; observer | agent_bridge as main path | Open |
| 010 | Six rule kinds in YAML | Python predicates, Rego, CEL, harness `forbidden_tools` | Open |
| 011 | Absolute + relative gate | Single score | Open |
| 012 | Persona × goal × tactic YAML, seeded, hashed | One prompt per scenario | Open |
| 013 | Seeded-bug agents; $0 and paid levels reported apart | Judge-counted attacks | Open |
| 014 | Team's key; $0 scripted CI; harness budget | — | Open |
| 015 | Local, key-free records; data-only config | Hosted generation | Open |
| 016 | OTel, harness pattern, observability's names | Depending on agent-observability | Open |
| 017 | Typer CLI + GitHub Action; hosting later | Hosted first | Open |
| 018 | Harness as a pinned git dependency | Copying `compare` | Open |

**New dependencies needing Arthur's OK:** none beyond his stack (Inspect AI,
Pydantic, Typer, pytest, uv, the MCP SDK, the OpenTelemetry SDK, httpx for
the HTTP adapter) and agent-eval-harness. PydanticAI for the model-backed
reference agent is already approved in Juku.

## The first slice

**Slice 1: the rule checker and the fake shop.** Pure Python: no model, no
Inspect, no network, $0. See the [slice plan](slice-plan.md).

## Open questions

**For Arthur:**
1. **Licences on mcp-gateway and juku-agents.** Neither has one. Add MIT
   (like the others) so this project, and anyone, can reuse them?
2. **Product name.** Keep `agent-flight-simulator` for the repo? It's
   descriptive; a product name shouldn't lean on "Flight Simulator", which
   is another company's product name.
3. **The paid accuracy run (slice 7).** About $2 with gpt-5-nano, about $9
   with gpt-5-mini (slice plan). Fund it, and when? Without it, the
   attacker's miss rate stays unmeasured, and the docs say so.
4. **The blind realism check** needs a person to label about 50
   conversations, about an hour. You, or someone you ask?
5. **An outside team.** G7 and the hosting question need one team to try
   it. Anyone in mind?

**For the spikes:** the harness's pins; Inspect's model roles with
`mockllm` both sides; whether Strands Evals drives a non-Strands agent;
the τ² error-swallowing report; whether the gateway's audit log carries
Shiori's arguments in full; ABCD's licence.

## Sources (read 2026-11-03)

[Inspect AI](https://inspect.aisi.org.uk/agents.html) ·
[Inspect model API](https://inspect.aisi.org.uk/reference/inspect_ai.model.html) ·
[mockllm](https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/main/src/inspect_ai/model/_providers/mockllm.py) ·
[inspect_evals τ²](https://ukgovernmentbeis.github.io/inspect_evals/evals/tau2/index.html) ·
[τ²-bench](https://github.com/sierra-research/tau2-bench) ·
[Strands Evals red teaming](https://strandsagents.com/blog/red-team-your-agent-strands-evals/) ·
[LangWatch Scenario](https://langwatch.ai/scenario/) ·
[promptfoo strategies](https://www.promptfoo.dev/docs/red-team/strategies/) ·
[promptfoo simulated user](https://www.promptfoo.dev/docs/providers/simulated-user/) ·
[PyRIT](https://github.com/microsoft/PyRIT) ·
[garak](https://github.com/NVIDIA/garak) ·
[DeepTeam](https://github.com/confident-ai/deepteam) ·
[DeepEval conversation simulator](https://deepeval.com/docs/conversation-simulator) ·
[Rogue](https://github.com/rogue-security/rogue) ·
[Coval docs](https://docs.coval.ai/) ·
[Hamming seed](https://hamming.ai/blog/hamming-ai-seed-funding-to-make-voice-agents-more-reliable) ·
[Cekura fundraise](https://cekura.ai/blogs/fundraise)

**Secondary, used only where marked:**
[Coval Series A](https://thenextweb.com/news/coval-28m-series-a-voice-ai-testing) ·
[OpenAI and Promptfoo](https://securityboulevard.com/2026/03/openai-acquires-security-startup-promptfoo-to-fortify-ai-agents)
(whether the deal closed is unconfirmed)
