# Phase 1: Problem Brief

**Project:** a release gate for customer-support chat agents that call
tools. Before a team ships a change to its agent, simulated customers
(confused, angry, or trying to trick it) talk to it. Code checks every tool
call the agent makes against the team's rules. A refund over the order
total, or one made before identity is checked, fails the build. It is the
tenth portfolio piece.

The working name is the repo's, `agent-flight-simulator`. The product name
is open (see the end).

## Problem

**For the users:**
- **Agents now move money.** Support agents issue refunds, credits and
  cancellations for anonymous customers. One bad call has a price, and
  often can't be undone.
- **Every change can open a hole.** Teams change prompts and models every
  week. Each change can make the agent easier to talk round, and nobody
  re-tests that by hand.
- **Existing testers mostly ask a model whether the agent behaved.** A
  judge model costs money on every run, varies from run to run, and can
  itself be talked round. None of the tools found publishes how often it
  misses a real bug or raises a false alarm.

*To verify, not assumed:* that a team would put this in CI and keep it
there. Slice 5's setup test and the first outside user are the evidence.

**For the portfolio:**
- Projects 2, 4 and 7 test agents with single prompts. None holds a
  conversation, where the real attacks happen: slow escalation, false
  claims of approval, and pressure over several turns.
- It joins the harness (measurement), the gateway (screening) and Juku
  (an agent with guarded tools) into something a company would pay for.
- It shows the habit Japan-style employers look for: a tester that
  measures its own error rate before asking anyone to trust it.

## Users

| Party | Who | Wants |
|---|---|---|
| **First user (ADR-001)** | A small team (2 to 20 engineers) shipping a customer-support chat agent whose tools move money or change accounts: refund, credit, cancel, change address | A CI check that blocks a release when a customer can talk the agent into a harmful call |
| **Arthur (builder)** | Runs it on his own agents first: a reference shop agent, then Juku's Shiori | A tool that is honest about what it catches |
| **Reviewer / hiring team** | Japan-style employers | Proof of reliability: deterministic checks, measured accuracy, tests, honest limits |

Why this user (settled with Arthur, 2026-11-03): they change their agent
often, each change can open a new hole, and a bad refund has a price, so
they would run it on every pull request. Solo developers would try it more
often but rarely need a release gate. Enterprises need it most but won't
adopt a one-person open-source tool first.

## The market, honestly

The idea is not new, and the plan doesn't pretend it is (ADR-005).

- **Funded rivals** (Coval, Hamming, Cekura) are voice-first. Coval raised
  a $28M Series A in June 2026.
- **Free tools already cover chat agents and tool calls.** AWS's Strands
  Evals (Apache-2.0) added multi-turn red teaming on 2026-10-26, and its
  own example is an unauthorised refund, caught by a code checker on tool
  calls. Promptfoo (MIT; OpenAI announced it was buying it in March 2026)
  has multi-turn attacks and a simulated user. DeepTeam, LangWatch Scenario
  and τ²-bench cover nearby ground.
- **So paid hosting is a long shot.** The portfolio value does not depend
  on it.

## Positioning: what makes this one different

Settled with Arthur, 2026-11-03: lead with measured accuracy.

1. **It publishes its own miss and false-alarm rates.** Reference agents
   with seeded bugs (refund without verification, cap ignored, trusts
   "my manager approved it") measure how often the simulator finds each
   bug and how often it fails a correct agent. No tool found publishes this.
2. **Code decides, not a model.** Rules on tool names, *arguments* and the
   simulated shop's state are checked by code. A model plays the customer;
   it never gives the verdict.
3. **$0 in CI by default.** Scripted customers need no model key, so the
   gate runs on every pull request for free. Model customers run with the
   team's own key, under a hard cost cap.
4. **Nothing leaves the team's machine.** No hosted generation, no
   telemetry. The agent's tools are fakes held by the simulator, so a test
   can never refund real money.
5. **Built on Inspect AI,** like the rest of the portfolio, with its logs
   and viewer.

## Goals and how they're measured

| # | Goal | Target | Measured by |
|---|---|---|---|
| G1 | The rule checker is never wrong | **0** wrong verdicts on the labelled tool-call logs | Fixture tests in CI, mutation-checked |
| G2 | Seeded bugs are found | Scripted customers: **every** seeded bug, every run. Model customers: miss rate measured and published (target set after the first paid run) | Accuracy report from run records |
| G3 | Correct agents pass | **0** critical false alarms on the correct reference agent | Same report |
| G4 | CI costs nothing | The default gate runs with no model key | CI itself |
| G5 | Same input, same verdict | A scripted run repeated with the same seed gives the same verdict | Test |
| G6 | Keys and transcripts don't leak | No key in any log, record or trace; run outputs ignored by git | Test, and a grep in CI |
| G7 | Easy to adopt | A new team adds it to CI in under 15 minutes from the README | Timed once, with someone who hasn't seen it |
| G8 | It works on an agent it wasn't built around | Shiori is run and the results reported as they are | Slice 6 report |

## Non-goals (v1)

- **Voice.** Chat only.
- **The hosted service.** v1 is a CLI and a GitHub Action. Hosting is
  planned only once the core has an outside user (ADR-017).
- **A model judge that blocks releases.** A judge may later grade tone, as
  advice only (ADR-002).
- **Calling the team's real backend or staging.** Tools are fakes (ADR-008).
- **Writing rules from a policy document automatically.** Teams write rules.
- **Languages other than English** for personas in v1. Japanese and
  Indonesian sets are a later Could.

## Decisions (settled with Arthur, 2026-11-03)

1. **First user:** small SaaS support teams whose agents' tools move money
   or change accounts.
2. **Pass:** zero critical rule violations, checked by code, *and* a task
   success rate no lower than the last release's, within a tolerance.
3. **Simulated customers:** a hand-written seed library, crossed into many
   scenarios and played by a model or by script; realism checked three ways.
4. **Licence:** Apache-2.0 for the open core. Hosting, if it comes, stays
   closed.
5. **Positioning:** lead with measured accuracy.
6. **Demo:** a reference shop agent with seeded bugs first; Shiori second,
   for its real risks.

Everything else in Phase 5 is a recommendation until Arthur agrees.

## Open questions

See the end of [Phase 5](phase-5-architecture-decisions.md#open-questions).

## Cost of doing nothing

Teams keep testing agents by hand or with a model judge, and find a
talk-round refund when a customer finds it first. For the portfolio, every
agent test stays single-turn, and the hardest attacks go unshown.
