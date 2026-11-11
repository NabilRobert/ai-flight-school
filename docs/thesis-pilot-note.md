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

**Correction (found after the run).** 5 customer lines wrote a marker
slightly wrong (`###GIVE_UP###`, `###GAVE_UP##`), and the loop, reading
markers exactly, let those chats go on. In one never-quotes-price chat
(`cek-harga.pedagang-pasar.tanya-syarat`) the customer gave up on line 2,
went on, and ended DONE, so it passed. Read correctly, never-quotes-price
passes 37, not 38, and only 2 chats ghosted, not 4. The committed records
are kept as they ran; the loop now reads such markers
(`scenario.py: stop_marker_in`), and the verdicts below say what the
corrected records give.

**The paired gate (`agent-eval compare --gate v3`, harness `ca28398`):**
- healthy → healthy-again: no regression, +8 points (95% interval −6 to
  +24). No false alarm.
- healthy → never-quotes-price: no regression, −4 points (−18 to +10).
  Corrected: inconclusive, −6 points (−20 to +8).
- healthy-again → never-quotes-price: inconclusive, −12 points (−26 to
  +2). Corrected: inconclusive, −14 points (−28 to 0).

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
2. **The pairing is untested past the first reply.** The agent wasn't
   seeded, so the arms part at reply 1 every time and the customer's
   seed never gets to match a later line. The agent now gets the trial's
   seed too (see "Since the pilot").
3. **Not enough pairs for small effects.** `agent-eval plan-pairs
   --baseline 0.84` says a 12-point drop needs 130 pairs, a 14-point
   drop 100 and a 6-point drop 410; the plan's 50 were sized for a
   30-point drop. See [thesis-pilot.md](planning/thesis-pilot.md), "After
   the pilot".

## Limits of the simulator

- **Ghosting doesn't take.** In the `menghilang` (ghosting) tactic the
  customer ghosted 0 times in 18 chats; it ended politely instead. Across
  all runs only 2 of 150 chats really ghosted (4 as recorded, see the
  correction). The tactic only said to leave "without saying goodbye"
  when an answer dodged, and the prompt's ghosting line was generic.
- **The 3B agent invents things:** brands such as "Yamaha" for the
  fictional dealer, and slightly wrong DP sums. That's a limit of a 3B
  model, not what the degradation tests.
- **No character breaks** in 150 chats by the Indonesian checks, including
  the `curiga-bot` ("ini bot ya?") tactic.
- **RQ1 can't be piloted on AI-written "real" chats:** realism needs real
  chats as the reference, and the pilot has none.
- **Smaller models than planned** (4B and 3B, not 8 to 9B), and bursts of
  messages are joined into one turn.

## Since the pilot (2026-11-11, offline, not yet run on a model)

- **Stop markers:** a misspelt marker now ends the chat (any case, two or
  more hashes each side, GIVE for GAVE); a hashtag such as `#done` still
  doesn't.
- **Ghosting:** the `menghilang` tactic now names when to leave (no
  number given, or "come to the showroom first"), and the prompt says a
  ghosting message is the marker alone. Whether a 4B customer now ghosts
  is unknown until the next local run. If it still doesn't, ghosting
  could come from the loop instead (end the chat after N dodged turns),
  at the cost of a rule that doesn't depend on the customer model.
- **The agent is seeded:** a model agent gets the trial's seed
  (`AgentTools.seed`, the customer's seed), recorded as `agent_seed` on
  each trial and chat, and as the rule in the meta. Ollama's
  OpenAI-compatible API lists `seed` and "reproducible outputs", and
  Inspect passes the seed through; that it gives identical replies here
  isn't tested yet. Two agents with different instructions still part at
  reply 1 when their first replies differ: the seed only removes the
  sampling noise.
- These change every library scenario's prompt, so new runs can't be
  compared with the pilot's records; the next pilot reruns all arms.

## Next, for the thesis sessions to decide

- Grade the pilot chats with Project 15's rubric judge when it exists,
  and see whether it ranks never-quotes-price below both healthy runs.
- Size the next run with `plan-pairs` for the effect the judge sees.
