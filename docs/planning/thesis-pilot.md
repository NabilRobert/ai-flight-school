# Thesis pilot: simulated Indonesian sales customers (proposed)

*2026-11-04. A plan only: nothing is built until Arthur agrees. Asked for
by the thesis-proposal session; this is part B of Project 15
(`id-chat-research`). Everything here is synthetic.*

## What the thesis needs from Flight School

The thesis asks whether LLM-based evaluation of customer-facing agents
can be trusted. Flight School's simulated customers are the simulator in
two of its questions:
- **RQ1:** how realistic the simulated customers are;
- **RQ3:** whether a simulator-plus-judge pipeline ranks agent versions
  correctly, with seeded degradations as ground truth.

The pilot shows the pipeline works end to end. It isn't evidence yet.

| Need | What Flight School provides |
|---|---|
| Sales customers in informal Indonesian: price first, haggling, DP and credit questions, ghosting, "ini bot ya?" | A second example suite, `examples/sales-id/`, whose seed library is built from the pilot chats' `persona` and `customer_behaviours` and the 24 role-play cards |
| The same customer against two agent versions | The same scenario, seed and epoch in both runs, so the harness's paired comparison (part D, Project 2) can pair trials on `(task_id, attempt)` |
| Output in Project 15's `ChatRecord` JSONL | An exporter from a run's records to `ChatRecord` (ADR-002 there), with `source: "synthetic"` |
| Pilot scale | 2 agent variants (healthy, plus one seeded degradation) × about 50 paired conversations |

## Where it fits

It needs slice 4: the seed library, the sampler and the model-customer
path. It doesn't need slices 5 to 7. **Proposed order:** slices 3 and 4
as planned, then this pilot (slice "T"), then 5 onward. The pilot doesn't
change ADR-001: Flight School stays a release gate for support teams, and
the sales suite is a research use of the same loop.

## What changes in Flight School

**Core: small, and each change useful beyond the thesis:**
- **A world with no tools.** A sales chat has no refunds. Empty rules and
  no tools must be a valid suite; the checker then finds nothing, and
  only task success decides.
- **A third stop marker, `###GHOSTED###`.** In a sales chat, a customer
  leaving without a word is a normal outcome (14 of the 40 pilot chats),
  not a broken run. The customer model emits the marker, and the exporter
  drops that final turn, so the chat ends on the agent's message, as a
  real ghosting does. The turn limit still fails a run (S5).
- **A customer seed per trial,** stored on the trial and passed to the
  customer model, so two runs give the same customer the same draws.
  Exact replay holds only while the agent's replies are the same; after
  the first different reply, the customer reacts to it. The thesis should
  report that, not hide it.

**New, in `examples/sales-id/` and `flight_school/export/`:**
- **Seed library:**
  - about 12 personas from the role-play cards;
  - goals from the pilot outcomes: buy, book a visit, compare, just
    checking a price;
  - tactics from the pilot's 16 behaviour tags.
  - Timing behaviours (`slow_reply`, `burst_messages`) become a style
    instruction plus timestamps in the export. Flight School's loop takes
    strict turns, so a burst is several customer lines joined into one
    turn. That is a known limit for RQ1's comparison.
- **A model customer** whose prompt is written in informal Indonesian,
  run on a **local open model at $0**: Sailor2-8B or Qwen3.5-9B through
  llama-server, the same server Project 15 uses. The in-character checks
  (S6) gain one for Indonesian: that the customer never reveals it is a
  test, even when asked "ini bot ya?".
- **Two sales reference agents** on a local model, built the way
  ADR-013's reference agents are:
  - **healthy:** answers price, stock, DP and credit questions;
  - **degraded:** one seeded degradation, such as weakened instructions
    that never offer a credit simulation.

  These are generic thesis agents. They contain no company prompt or
  code.
- **`ChatRecord` export:**
  - one record per trial: `format_version`, `chat_id` (run, variant,
    scenario, epoch), `source: "synthetic"`, `domain` and `turns`;
  - `outcome`: persona, goal and tactic ids, `customer_behaviours`, stop
    marker, agent variant, seed and pair key.

  It depends on Project 15's `ChatRecord` model, from its tagged release
  (its slice 7). It doesn't copy that model.

## Success measure for the pilot (open)

Only part of RQ3's pipeline exists before Project 15's rubric judge
(part C). **Proposed:** in the pilot, the stop marker decides. `###DONE###`
(booked, bought, or handed to a person while still interested) is a pass;
`###GAVE_UP###` and `###GHOSTED###` are fails. Rubric scores per construct
replace or join it once C is released. This is simulator-judged, which is
exactly what RQ3 questions, so the pilot report says so.

## Cost and time

- **Money:** $0. Local models only, and no paid run without Arthur's OK.
- **Compute:**
  - about 13 generations per conversation (the pilot chats average 13
    turns, both sides together);
  - roughly 70 s per conversation on the Mac with an 8B model;
  - so 100 conversations take about 2 hours.
- **Download:** an 8B model is about 5 GB. That's the same open question
  as Project 15's judge model, so one download can serve both.

## Done when

- 2 variants × 50 scenarios give two complete runs. Every trial in one
  has its pair in the other with the same seed.
- The export validates against Project 15's `ChatRecord`, and every
  record has `source: "synthetic"`.
- Project 2's paired comparison reads both runs and gives a verdict.
- A one-page pilot note gives:
  - the outcome counts;
  - how often the customer broke character;
  - how many pairs stayed identical to the first different reply;
  - and, as a known limit, that RQ1 can't be piloted on AI-written "real"
    chats.

## Questions for Arthur before building

1. Slot it after slice 4, ahead of slices 5 to 7?
2. The local model (about 5 GB). Share Project 15's choice?
3. The pilot's success measure: the stop marker, until the rubric judge
   exists?
4. Should Flight School build the two sales reference agents, as proposed
   here, or do they live in the thesis repo?

## Interface with Project 2 (to agree)

Proposed to the harness session, 2026-11-04. The pair key is `(task_id,
attempt)`. Both runs share a suite hash and a data fingerprint. Each trial
carries `customer_seed`, `scenario` (persona, goal and tactic ids) and,
once part C exists, `scores` per construct. Changes here once it replies.
