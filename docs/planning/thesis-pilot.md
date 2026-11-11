# Thesis pilot: simulated Indonesian sales customers

*2026-11-04, planned. 2026-11-09: built (see "Built so far" below).
2026-11-11: run; the results are in the
[pilot note](../thesis-pilot-note.md). Arthur's answers are below (decided 2026-11-04, relayed by the
thesis-proposal session). Asked for by the thesis-proposal session; this
is part B of Project 15 (`id-chat-research`). Everything here is
synthetic.*

## Built so far (2026-11-09, $0, no model run yet)

What exists, on `feat/sales-pilot`, tested on `mockllm`:
- **Core:** `###GHOSTED###`; `pass_when: customer_done` (the harness's
  `result_match` over `[{"stop_marker": "###DONE###"}]`); a model customer
  that opens with the scenario's first line and is seeded per (scenario,
  epoch), stored as `customer_seed`; a library's own `prompt.txt`; the
  Indonesian in-character checks ("ini bot ya?" asked of the agent isn't
  a break; the customer calling itself a bot is).
- **`examples/sales-id/`:** a fictional motorbike dealer; 12 personas, 4
  goals and 16 tactics (768 crossings), an Indonesian customer prompt,
  and two scripted chats for $0 checks.
- **Sales agents:** `reference/sales_agent.py: healthy` and
  `never_quotes_price`, on Inspect's `agent` role (`--agent-model`), not
  seeded.
- **Provenance:** each local model's Ollama digest and Ollama's version,
  read before the run; the customer's is in the data fingerprint.
- **Export:** `chats.jsonl` with every run, built with Project 15's
  `id_chat_records.ChatRecord` (tag v0.1.0), so every record is validated
  as it is written; its hash is in the meta. Flight School's own facts go
  in `outcome`. `flightschool pairs` reads the chats back with
  `read_jsonl` and reports `diverged_at_turn` and whether the customer
  matched until then.
- **Harness:** pinned at `ca28398`, the paired-gate merge.
  `plan-pairs --baseline 0.8 --drop 0.3` says 30 pairs catch the drop
  84% of the time, with 2.9% false alarms; 50 pairs leave margin. A
  20-point drop needs 60.

**Changed from the plan (Arthur agreed all three, 2026-11-09):**
- **The library is written from scratch,** from the behaviours this plan
  names, not built from the pilot chats or the 24 role-play cards:
  reading those was blocked as possible personal data.
- **Ollama, not llama-server:** there's no llama-server on the Mac, and
  the disk has 15 GB free, so the plan uses the models already pulled:
  `qwen3.5:4b` (4.0 GB) as the customer and `llama3.2:3b` (2.0 GB) as the
  agent, two families, no download. These are smaller than the planned
  8–9B models, a stated limit of the pilot.

**Smoke check (2026-11-09, 5 local calls, $0):**
- `llama3.2:3b` as the healthy agent answered the first line in about 9 s,
  model load included, in plain Indonesian. It got the DP arithmetic
  slightly wrong (Rp3.537.500 for 15% of Rp23.500.000): a 3B agent's
  limit, and not what the degradation tests.
- `qwen3.5:4b` as the customer took 118 s and 2,265 tokens for one line,
  because it thinks by default. With thinking off (now the default for
  Ollama models) it took about 9 s, model load included, and stayed in
  character.
- **Estimate:** about 13 generations per chat at 4 to 6 s each, so about
  1 minute a chat and 2 to 3.5 hours for 150. The first 5 chats are timed
  before the rest.
- **Memory:** `ollama ps` showed `qwen3.5:4b` at about 9 GB (its 24k
  context) on a 16 GB Mac; with `llama3.2:3b` both take about 12 GB, so
  nothing else heavy runs alongside.

**Not built:** timestamps for slow replies (a known limit for RQ1).

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
| Pilot scale | 3 runs (healthy, healthy again, one seeded degradation) × 50 scenarios × 1 epoch |

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
  - roughly 60 to 90 s per conversation on the Mac with an 8B model;
  - so 150 conversations take about 2.5 to 4 hours.
- **Download:** two models from different families, about 10 GB in all
  (Arthur's answer 2 below).

## Done when

- 3 runs × 50 scenarios are complete. Every trial has its pair in the
  other runs, with the same seed.
- The export validates against Project 15's `ChatRecord`, and every
  record has `source: "synthetic"`.
- Project 2's paired comparison reads both runs and gives a verdict.
- A one-page pilot note gives:
  - the outcome counts;
  - how often the customer broke character;
  - how many pairs stayed identical to the first different reply;
  - and, as a known limit, that RQ1 can't be piloted on AI-written "real"
    chats.

## Arthur's answers (2026-11-04)

1. **Slot:** after slice 4, ahead of slices 5 to 7.
2. **Models:** two different model families, one for the customer and one
   for the judge, so the judge can't favour its own family's text (that
   bias is what RQ2 measures). For example, Sailor2-8B as the customer and
   Qwen3.5-9B as the judge, or the reverse; the pair is confirmed with
   Project 15's judge choice. That's about 10 GB of downloads in all, and
   each one's size is reported before it starts.
3. **Pass rule:** "customer ended `###DONE###`", as a placeholder until
   Project 15's rubric judge exists. Results label it as the simulator
   grading itself, not a valid quality measure.
4. **Agents:** the healthy and degraded sales agents are generic reference
   sales agents in Flight School.

## Interface with Project 2 (agreed 2026-11-04)

Agreed with the harness session. Its side is on branch
`docs/paired-conversations-plan` (commit 7f2e8df).

- **Runs:** three runs in the harness's record format: healthy, healthy
  again (the A/A false-alarm check, which also measures pair correlation),
  and the degradation. Each is 50 scenarios × 1 epoch, not 25 × 2, because
  the interval resamples scenarios.
- **Pair key:** `(task_id, attempt)`.
  - `task_id` is the scenario (persona × goal × tactic). In the pilot
    there's one goal per persona.
  - `attempt` is the epoch.
  - The customer seed comes from `(task_id, epoch)` and is stored as
    `customer_seed`.
  - The opening line comes from the persona card, so turn 1 is identical
    in both arms.
- **Task hash:** the task's `prompt` holds the persona card and the goal
  and tactic text, so the hash covers the scenario.
- **The customer is part of the environment:** `provenance.data_fingerprint`
  hashes the persona cards, the customer model file's hash, the
  llama-server build and the generation settings. Each part is also listed
  in provenance, for readers. The harness's `compare` already refuses runs
  whose fingerprints differ (exit 2), so this needs no harness change. The
  agent variant's name, model and settings go in the existing `agent` and
  `target` fields.
- **Pass:** the harness's existing `result_match` grader over one row:
  expected `[{"stop_marker": "###DONE###"}]`, graded
  `[{"stop_marker": <actual>}]`. It regrades exactly, with no model call
  and no new grader kind. The suite's name and description say the pass is
  "the simulator grading itself". Later, each rubric construct becomes its
  own grader, whose spec carries the judge model and codebook hash.
- **Per trial:** `diverged_at_turn`, the first turn where the two arms'
  agent replies differ. The gate doesn't use it; the thesis reports it.
- **Reproducibility:** both arms run on the same Mac with the same server
  build and the same model file. llama.cpp's seeded output isn't promised
  to match across builds or hardware.
- **ChatRecords:** Flight School's own export, `chats.jsonl` beside the
  run, with `chats_sha256` in `meta.provenance`. The harness neither reads
  nor checks it: the gate decides from `trials.jsonl` alone.
- **Degradation:** the agent never quotes a price, DP or instalment ("silakan
  datang ke showroom ya kak"). Price-first and credit questions are the
  most common behaviours in the pilot chats (19 and 16 of 40), so the drop
  should be large. With no judge noise, 50 pairs catch a 20-point drop 78%
  of the time and a 30-point drop 96% of the time (Project 2's numbers). A
  smaller drop is published as inconclusive.
- **The harness side is built** (2026-11-04): `agent-eval compare --gate v3`
  (paired, a 95% bootstrap interval over scenarios) and `agent-eval
  plan-pairs`. They're on the harness's `feat/paired-gate` (adb959b), not
  merged yet. Before the pilot runs: pin the harness at that merge commit,
  check the pair count with `plan-pairs --baseline 0.8 --drop 0.3`, and
  compare healthy against healthy again with `--gate v3` before the
  degraded run.
- **Time:** about 60 to 90 s per conversation, estimated; 150 conversations
  take about 2.5 to 4 hours. It is measured on the first 5 conversations
  before the full runs.
