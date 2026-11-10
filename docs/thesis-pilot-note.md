# Thesis pilot note (2026-11-11)

The pilot planned in [thesis-pilot.md](planning/thesis-pilot.md), run once
at $0 on local models. Every chat is synthetic. **The pipeline works end
to end, and the result is a warning: the pilot's placeholder pass rule
didn't see the seeded degradation.** That is the question RQ3 asks, so it
is a finding, not a failure of the pilot.

## What ran

- **Suite:** `examples/sales-id`, 50 scenarios drawn with `--seed 1`, 1
  epoch, a turn limit of 10, one chat at a time.
- **Customer:** `ollama/qwen3.5:4b` (digest `7f3251fa…`), thinking off,
  seeded per (scenario, epoch). **Agent:** `ollama/llama3.2:3b` (digest
  `a80c4f17…`), not seeded. Ollama 0.40.11. All three runs share one
  data fingerprint.
- **Runs:** `healthy`, `healthy-again` (the A/A check) and
  `never-quotes-price` (the degradation). Their records are in
  [pilot-runs/2026-11-11/](pilot-runs/2026-11-11/).
- **Time:** 150 chats in 2 h 14 min (2,645 s, 2,975 s and 2,427 s), about
  54 s a chat, inside the 2 to 3.5 hour estimate. A 5-chat timing run
  came first (335 s).

## Results

| Run | Pass (`###DONE###`) | Gave up | Ghosted | Turn limit | Character breaks | Agent gave a price |
|---|---|---|---|---|---|---|
| healthy | 40 | 9 | 1 | 0 | 0 | 39 of 50 |
| healthy-again | 44 | 3 | 1 | 2 | 0 | 42 of 50 |
| never-quotes-price | 38 | 10 | 2 | 0 | 0 | 14 of 50 |

"Agent gave a price" is a pattern match on the agent's lines (`Rp`, a
`x.xxx.xxx` amount or "juta"), a rough check outside the gate.

**The paired gate (`agent-eval compare --gate v3`, harness `ca28398`):**
- healthy → healthy-again: no regression, +8 points (95% interval −6 to
  +24). No false alarm.
- healthy → never-quotes-price: no regression, −4 points (−18 to +10).
- healthy-again → never-quotes-price: inconclusive, −12 points (−26 to
  +2).

**Pairs (`flightschool pairs`):** in all 50 pairs of both comparisons the
agents' first replies already differ, and the customer's lines match up
to there in all 50. That match is weak evidence: the customer's first line
is the scenario's scripted opening, so it can't differ.

## What it shows

1. **The degradation worked; the measure missed it.** The degraded agent
   gave a price in 14 chats, not 39 to 42. But the simulated customer
   accepted "come to the showroom" and still ended `###DONE###`: 7 credit
   or price chats passed with no price given. The pass rate fell by 2 to
   6 points, less than the 4-point swing between the two healthy runs. A
   customer that grades itself is too lenient to rank these agents, which
   is the RQ3 concern in [thesis-pilot.md](planning/thesis-pilot.md). A
   rubric judge that asks "was the price question answered?" (Project
   15's part C) should see the drop; the rough price check above does.
2. **The pairing is untested past the first reply.** The agent isn't
   seeded, so the arms part at reply 1 every time and the customer's
   seed never gets to match a later line. Seeding the agent too (Ollama
   takes a seed) would show how long the arms stay identical.
3. **Not enough pairs for small effects.** `agent-eval plan-pairs
   --baseline 0.84 --drop 0.12` says a 12-point drop needs 130 pairs; the
   plan's 50 were sized for a 30-point drop.

## Limits of the simulator

- **Ghosting doesn't take.** In the `menghilang` (ghosting) tactic the
  customer ghosted 0 times in 18 chats; it ended politely instead. Across
  all runs only 4 of 150 chats ghosted. With a 4B customer, ghosting
  should come from the loop (stop after N turns), not from the prompt.
- **The 3B agent invents things:** brands such as "Yamaha" for the
  fictional dealer, and slightly wrong DP sums. That's a limit of a 3B
  model, not what the degradation tests.
- **No character breaks** in 150 chats by the Indonesian checks, including
  the `curiga-bot` ("ini bot ya?") tactic.
- **RQ1 can't be piloted on AI-written "real" chats:** realism needs real
  chats as the reference, and the pilot has none.
- **Smaller models than planned** (4B and 3B, not 8 to 9B), and bursts of
  messages are joined into one turn.

## Next, for the thesis sessions to decide

- Grade the pilot chats with Project 15's rubric judge when it exists,
  and see whether it ranks never-quotes-price below both healthy runs.
- Seed the agent, so pairs diverge later than reply 1.
- Size the next run with `plan-pairs` for the effect the judge sees.
