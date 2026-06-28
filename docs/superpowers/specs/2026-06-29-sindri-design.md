# Sindri — MCP Design Spec

**Name:** Sindri — the Norse master smith. An MCP that forges better systems: it reviews your architecture, estimates real capacity, and roasts bad decisions in a dry, unhinged senior-architect voice.
**Date:** 2026-06-29
**Author:** Rudra Dudhat
**Status:** Design drafted, pending spec review → implementation plan

---

## 1. Problem Statement

People — increasingly "vibecoders" using AI assistants — design systems they don't understand the limits of. They wire up a single Postgres for everything, put a CDN in front of writes, make six sequential cross-region calls, and have no idea their design dies at 12k users until it actually does. The knowledge to catch this exists (capacity estimation, distributed-systems anti-patterns) but lives in senior engineers' heads, not in the loop where designs get made.

Meanwhile, the obvious AI approach — "ask the LLM if my architecture is good" — produces **generic, confident, ungrounded advice**. Frontier models are mediocre at system design; small/local models are worse. So the naive build is a wrapper that gives plausible-sounding nonsense.

**Sindri is an MCP that Claude Code (or any coding assistant) calls while designing a system. It parses the design, runs deterministic capacity/latency/cost analysis grounded in cited real-world numbers, and returns a verdict-first roast: the bottleneck, the max user capacity, and the single highest-leverage fix — which the assistant can then apply and re-check.**

The intelligence lives in a deterministic engine, not the model. That is what makes it accurate, non-generic, and runnable on a free local model.

---

## 2. Vision

> An MCP that Claude Code calls while designing a system. It estimates real capacity (how many users this design actually supports), gives specific non-generic recommendations, and delivers verdicts in a dry, unhinged senior-architect roast voice — *"a CDN for 10k writes? are you a philanthropist?"* The magic test: it should feel **unreal to design better systems** with it on.

---

## 3. Goals & Non-Goals

### Goals (v1)
1. Given a design (read from code, or described in prose), return a verdict-first report: **bottleneck component, max user capacity, p99 latency vs SLO, rough monthly cost, and the one highest-leverage fix.**
2. Every finding is **grounded** — traces to a cited number, a named anti-pattern, or arithmetic. Never "the model thinks so."
3. **Zero structured input from the human.** Read their code; parse their sentence; assume-and-state the rest.
4. **Closed loop:** the assistant can apply the recommended fix and re-run to show the capacity jump.
5. Runs on a **small, local, free model** (the model only parses-glue and phrases; it never reasons about systems).
6. **Confidence-gated roast:** loud where the verdict is robust, soft/abstaining where it hinges on a guessed input.

### Non-Goals (v1)
- Not a code profiler. It reviews the **architecture**, not the implementation; it will not catch a missing index, an N+1, or a hot key. This boundary is stated to the user.
- Not availability/consistency *math* in v1 (handled qualitatively by the anti-pattern linter; full availability math is roadmap).
- Not a diagram tool. It may ingest C4/diagrams later, but v1 reads code + prose.
- Not a hosted service. Local-only, like Receipts v1.
- Not security review.

---

## 4. Architecture — the wrapper-killer engine

One principle: **the LLM never reasons about systems. Deterministic code does. The model only (a) glues unstructured prose into the graph and (b) phrases findings in the roast voice.**

```
  Claude Code ──calls──> [Sindri MCP]
        │
        ▼
  ① Design Graph build
     - deterministic config parsers (package.json, docker-compose,
       SQL/Prisma schema, Terraform)  ← real code, not the LLM
     - small LLM only to glue prose + fill gaps
     - SHOW THE GRAPH BACK for one-tap confirm
        │
        ▼
  ② Lens engine (deterministic) over the graph:
     - Capacity lens  (throughput KB)
     - Latency lens   (latency-numbers KB, critical-path sum)
     - Cost lens      ($/component KB)
     + Anti-pattern linter (structural rules)
        │
        ▼
  ③ Findings + confidence  (bottleneck, max capacity, p99, $, the one fix)
        │
        ▼
  ④ Roast narrator (small LLM — voice ONLY, never judgment)
        │
        ▼
  Verdict-first roast report → Claude Code → (optionally apply fix, re-run)
```

### ① The Design Graph
A C4-inspired structured model: **components** (each tagged with a `type`: `relational_db`, `cache`, `queue`, `cdn`, `app_server`, `object_store`, `load_balancer`, `search_index`…), **edges** (data flow with read/write + rate), **datastores** (consistency/replication props), and **NFRs/traffic** (DAU, req/user/day, read:write ratio, payload size, retention, latency SLO, regions).

**Guardrail 1 — deterministic config parsing.** The accuracy path must not depend on a 7B model reading code. Real parsers extract structure from `package.json`, `docker-compose.yml`, SQL/Prisma schema, Terraform, etc. The LLM is used only to glue prose and fill gaps the parsers can't. This collapses the garbage-in risk and makes the open-source-model story rock-solid.

**Guardrail 2 — show the graph back.** Before analyzing, Sindri returns "here is the system I understood — correct?" for one-tap confirmation. Cheap, kills most parse errors.

### ② The lens engine
Each lens is "walk the graph, apply a per-component number-table, compare to a target, find the weakest link." Same mechanism, different table. See §5.

### ③ Findings + confidence
Deterministic. Computes the bottleneck (first component to saturate), max user capacity (the load at saturation), critical-path p99, rough monthly cost, and ranks fixes by capacity-gained-per-effort.

### ④ The roast narrator
The model takes fixed findings and phrases them in the dry/unhinged register. It cannot roast a number it didn't compute, so the personality is safe. Same deterministic-core/LLM-narrates pattern as Receipts and diffprompt.

---

## 5. The Lenses (v1: capacity, latency, cost)

Not three products — three tables over one graph. Interconnected (Little's Law ties latency↔throughput, so a latency bottleneck under load becomes a capacity bottleneck).

| Lens | Number-table (KB) | Verdict | Roast flavor |
|------|-------------------|---------|--------------|
| **Capacity** | throughput ceilings: Postgres single primary ~1k w/s (plan change at 500+), Redis ~100k ops/s, Kafka ~1M msg/s | max users + bottleneck component | *"this Postgres is doing the work of eight and getting paid for one"* |
| **Latency** | latency numbers: same-DC RTT ~0.5ms, cross-region ~80ms, disk seek, cache hit ~1ms, summed along the critical path | will it meet the p99 SLO + slowest hop | *"six sequential cross-region calls — your p99 is a postcard"* |
| **Cost** | rough $/component/month | monthly bill + where the waste is | *"a CDN for 10k writes — are you a philanthropist?"* |

**Anti-pattern linter** (qualitative, structural — covers the reliability/consistency angle in v1): SPOF, dual-write, write-to-CDN, cache-without-invalidation, hot partition (skewed key), sync call in hot path to slow dependency, distributed monolith, missing health checks. Each rule = a structural condition over the graph + a roast line + a cited remediation.

**Guardrail 5 — KB as ranges + order-of-magnitude, every number cited.** Component throughput varies 10-100x by config/hardware/schema; a single point value is a liability. The KB stores ranges and cites sources; verdicts use the back-of-envelope bar (within 2x = fine, 100x = wrong system). "You're ~8x over, somewhere between 5-15x" is honest and still a devastating roast.

---

## 6. Input Model (designed for "dumb" vibecoders — zero structured input)

The human never structures anything. The structuring is Sindri's job, via Claude Code.

- **Mode A — infer from code (default, zero input).** Deterministic parsers read the repo (compose, schema, deps, infra) → graph. The user just asks "is this gonna fall over?"
- **Mode B — freeform prose.** "Food delivery app, Postgres, Next.js, one box." LLM-glued into the graph.
- **Mode C — guided.** Only the 2-3 inputs that swing the verdict (roughly how many users; read- or write-heavy), in plain language. Never a form.

**The missing-numbers problem (assume-and-state).** Vibecoders give no numbers, and the verdict is dominated by traffic assumptions. So Sindri assumes archetype-based defaults, **states them loudly at the top of every report, and lets the user correct in plain English**:

> *"You gave no numbers, so I assumed ~100k daily users, 10 reads per write, 50KB payloads. If you're tiny (under ~1k users) ignore all of this, you're fine. If you're dreaming of 5M, tell me and watch this get ugly."*

The user corrects by talking ("nah it's 2 million") → re-run.

---

## 7. The Five Guardrails (first-class requirements)

These are *requirements*, not nice-to-haves. They are the difference between "a rigorous tool with a funny voice" and "a confidently-wrong comedian."

1. **Deterministic config parsing** — real parsers on structured files; the model barely touches the accuracy path (§4①).
2. **Show the understood graph back** for one-tap confirm before analyzing (§4①).
3. **Confidence-gated roast** — roast loud only where the verdict survives the unknown inputs; soften or abstain where it hinges on a guessed number. A wrong confident roast is the one thing that kills trust. (The Receipts abstention lesson.)
4. **State the boundary** — "I review the architecture, not your code; I won't catch a missing index." Honesty defines the lane.
5. **KB as cited ranges + order-of-magnitude** (§5).

---

## 8. Output & UX

**Verdict-first roast report:**

```
Assuming ~100k daily users, read-heavy (correct me).

🔴 BOTTLENECK: orders-db (Postgres, single primary)
   ~8,000 writes/sec needed. It caps around 1,000. You are ~8x over the wall.
   Max capacity as-designed: ~12k daily users before write latency goes vertical.
   "Mate, this Postgres is doing the work of eight and getting paid for one.
    Shard by customer_id or put a queue in front before it unionizes."

⏱  p99 ~420ms vs your 200ms SLO — the orders write path is the drag.
💸 ~$340/mo, and ~$200 of it is a CDN doing nothing for your writes.

➡  ONE FIX (10x headroom): move media to S3 + add a read replica.
   Want me to apply it?
```

**UX principles:**
- **One highest-leverage fix first** (ranked by capacity-gained-per-effort), never a wall of findings.
- **Closed loop:** "want me to apply it?" → Claude Code patches the code → re-runs → shows the before/after number ("12k → 110k users"). Only possible because CC is the caller; this is the signature retention moment.
- **Verdict + assumptions at the top**, always correctable in plain English.
- **Never breaks:** the math/anti-pattern layer runs with no API key; only the roast phrasing needs a model, and it degrades to plain text gracefully.

---

## 9. MCP Tool Surface

| Tool | Purpose |
|------|---------|
| `review_architecture(source?, nfrs?)` | The core call. Builds graph (from repo or prose), runs all lenses, returns the roast report. |
| `estimate_capacity(source?)` | Just the capacity math + bottleneck + max users. |
| `whats_my_bottleneck(source?)` | The single weakest link, fast. |
| `simulate_change(source, change)` | Re-run after a proposed change; report the capacity/latency/cost delta (powers the closed loop). |
| `explain_finding(id)` | The one-line *why* (Little's Law, why shard) — teaches while it roasts. |

---

## 10. Grounding & Validation (acceptance criteria)

Accuracy is a *testable* claim, not a vibe.

- **Golden set of real systems.** ~10-20 well-documented architectures with known outcomes (e.g., Instagram scaling to ~14M users on a handful of Postgres; published "how we scaled X to N" posts; postmortems). Feed Sindri the design; assert it predicts the **right bottleneck and the right order-of-magnitude capacity**. Honest scope: this is a sanity suite, not a statistical eval (the data is sparse).
- **Order-of-magnitude bar.** Within 2x = pass; 100x = fail. (Back-of-envelope's own standard.)
- **Citeability test.** Every emitted number traces to a KB entry with a source. A finding with no citation is a bug.
- **Abstain outside coverage.** Hand it an exotic component with no KB entry → it says "outside what I can estimate rigorously, here's what I can/can't check" rather than bluffing. Pinned by tests.
- **Confidence-gate test.** A verdict that flips on a guessed input must be emitted as soft/low-confidence, not a loud roast.

---

## 11. Model Strategy (small, local, free)

- The deterministic engine (parsers, KB, lens math, anti-pattern linter, fix ranking) runs with **no model at all**.
- The model does two easy jobs: **prose-glue extraction** (structured output, constrained decoding — 7B-class is fine) and **roast phrasing** (style generation — zero correctness risk because content is fixed).
- Reuse the local-model infra pattern already proven in diffprompt (Ollama, `qwen2.5:7b`). Provider-agnostic; degrades to plain-text output with no model.
- This is the **Mimic philosophy**: distill the decision into cheap deterministic code so a tiny/no model agrees with the expensive one. The engine *is* the distilled decision.

---

## 12. Retention / Loyalty

**In v1 (inherent to the core, not extra features):**
- The **closed-loop fix** + live before/after capacity number (the signature moment).
- **One highest-leverage fix first** (a win every run).
- **Never breaks** (zero-config math layer).
- **The roast voice** (+ rare, earned praise — scarcity makes both land).

**Roadmap (first item first):**
- **Architecture health-score over time** — local persistence; "3 weeks ago you died at 12k users, you're now at 1.2M." The fitness-tracker loop; strongest structural retention lever.
- **Shareable scorecard** ("survived 2M simulated users 🏆") — feeds the build-in-public X flywheel.
- **Teaches while it roasts** (the one-line why) — on-brand with the SD curriculum.
- **Remembers you** (your stack, scale, past corrections) — friction drops with use.

---

## 13. v1 Scope (Locked)

- **Lenses:** capacity + latency + cost. Reliability/consistency via the anti-pattern linter (qualitative). Availability math = roadmap.
- **Component types (KB) for v1:** relational_db, cache, queue, cdn, app_server, object_store, load_balancer (≈7, the common vibecoder stack). Cited ranges each.
- **Anti-patterns for v1:** ~8 high-value structural rules (SPOF, dual-write, write-to-CDN, cache-without-invalidation, hot partition, sync-call-to-slow-dep, distributed monolith, missing health check).
- **Input:** Mode A (deterministic config parse) default + Mode B (prose) + Mode C (≤3 guided questions); assume-and-state; show-graph-back.
- **Output:** verdict-first roast, one-fix-first, closed-loop apply + re-run.
- **Guardrails:** all five (§7) are first-class.
- **Validation:** golden set + order-of-magnitude bar + citeability + abstain-outside-coverage (§10).
- **Model:** local/free; deterministic core needs none.
- **Local-only.** No hosting, no monetization.

---

## 14. Edge Cases

- **No numbers given** → assume-and-state + sensitivity note; soften the roast where the verdict hinges on the guess.
- **Hobby project / tiny scale** → "you're fine, stop optimizing" rather than a scary roast. (Don't roast a to-do app for not being web-scale.)
- **Trivial graph** (one app + one DB, Mode A on an early repo) → still give the honest "this is fine until ~N users, here's your first wall."
- **Exotic / unknown component** → abstain on that node, analyze the rest, say what was skipped.
- **Contradictory NFRs** (strong consistency + multi-region + low-latency writes) → flag the impossibility (CAP), don't pick silently.
- **No model available** → run the full deterministic engine; emit plain-text findings without the roast voice.
- **Parser can't read the repo** (no compose/schema) → fall back to Mode B/C; never crash.

---

## 15. Tech Stack

- **Language:** Python 3.11+. MCP Python SDK (FastMCP).
- **Parsers:** stdlib + targeted libs for `package.json`/`docker-compose.yml`/SQL/Prisma/Terraform.
- **Engine:** pure-Python deterministic (KB as data files, lens math, rules). Pydantic for the graph + findings.
- **Model:** local via Ollama (diffprompt pattern), provider-agnostic; optional, degrade-able.
- **Validation:** pytest golden-set; order-of-magnitude assertions.

---

## 16. Open Questions

1. **KB sourcing effort.** Curating cited throughput/latency/cost ranges for ~7 component types is real work — seed from published benchmarks + the back-of-envelope canon, mark each with a source + confidence.
2. **Golden-set size.** Realistically ~10-20 documented systems; accept it's a sanity suite, not a statistical eval.
3. **Closed-loop "apply fix" boundary.** How much does Sindri itself propose vs how much does Claude Code implement? Lean: Sindri emits the structured fix, CC applies it (Sindri stays advisory; CC owns the edit).
4. **Cost KB volatility.** Cloud pricing drifts; store as rough order-of-magnitude with a "rough" disclaimer, not precise quotes.

---

## 17. Next Step

→ Invoke the **writing-plans** skill to turn this into a staged implementation plan. Likely Plan 1 (walking skeleton): Design Graph models + deterministic config parsers (one or two: compose + schema) + the capacity lens + a small capability KB + the verdict/bottleneck math + a plain-text report (roast narrator and the other lenses follow). Build subagent-driven, TDD, per-task deterministic gate — same as Receipts.
