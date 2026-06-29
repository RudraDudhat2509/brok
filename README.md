# Brok

**An MCP server that estimates a system's real capacity, finds its bottleneck, surfaces the trade-offs you are making, and roasts the design in a dry deterministic voice, all grounded in cited numbers instead of LLM guesswork.**

You point it at an architecture (a `docker-compose.yml` or a list of components) and tell it the scale you expect. It tells you which component breaks first, roughly how many users the design supports, the trade-offs each component carries, and why. The reasoning is deterministic. No model runs in the core, so it is free to run and it gives the same answer every time.

Named after Brok, the blunt dwarf smith of Norse myth (and Sindri's gruffer, funnier brother in God of War): he respects work that holds and has no patience for the lazy kind. The dry-roast voice is built: it phrases every verdict in Brok's blunt register, while the numbers stay computed by the deterministic engine.

---

## The problem

Most people, and increasingly most AI coding assistants, design systems without knowing the limits of what they drew. A single Postgres for everything. A CDN in front of writes. Six sequential cross region calls. Nobody finds out the design dies at 12,000 users until it actually does.

The obvious AI approach, "ask the model if my architecture is good," produces confident, generic, ungrounded advice. Frontier models are mediocre at system design and small local models are worse. So the naive build is a wrapper that returns plausible sounding nonsense.

Brok takes the opposite approach: **the model never reasons about systems. Deterministic code does, using real, cited numbers.**

---

## What it does today

Given an architecture and an expected scale, Brok returns:

- the **bottleneck** component (the first thing to saturate),
- the **max user capacity** the design supports before that wall,
- the **per component utilization** (load versus its cited ceiling),
- a **latency warning** when a component is past the queueing knee (about 70% utilization), with how many times its idle latency you are already paying and the user count it stays safe to,
- a **rough monthly cost** (compute plus egress), so you see the bill, not just the breaking point,
- the **trade-offs** each component carries (when it is fine, what it costs, the move when you outgrow it), curated and cited,
- the **assumptions** it made for any inputs you did not provide, stated plainly,
- all of it phrased in the **Brok roast voice**, a deterministic narrator layer (no model, fixed templates, real numbers).

Worked example (`api` + Postgres + Redis at 2,000,000 daily users):

```
BROK: PUSHING IT

api is a touch over, about 1.7x. You get to about 1,152,000 users before it
complains. run more instances behind the load balancer, it scales out fine.

Confidence: low.

Receipts:
  api: ~3,472/sec vs ~2,000 ceiling
  db: ~316/sec vs ~1,000 ceiling
  cache: ~3,157/sec vs ~100,000 ceiling

THE TRADE-OFFS YOU ARE MAKING:
  app_server: fine almost always, as a stateless app tier.
    cost: a single instance caps at low thousands of req/sec; state must live
    elsewhere. outgrow it: add instances behind the load balancer.
  relational_db: fine under about 500 writes/sec and a dataset one machine can hold.
    cost: a single point of failure, writes cap near 1k/sec. outgrow it:
    read-heavy add replicas, write-bound shard by a high cardinality key.
```

Note what it caught: the wall is the single **app tier**, not the database everyone worries about. A cache absorbs the reads, so Postgres is fine, and the single app instance saturates first. That is the kind of non obvious, specific result the deterministic engine produces, and the trade-off section tells you the move before you hit the wall.

---

## The data behind it

Brok does not invent numbers. Every capacity verdict traces to a curated, cited capability table (the conservative low end of each range is used for verdicts):

| Component | Throughput (single instance) | Source |
|-----------|------------------------------|--------|
| Relational DB (Postgres) | ~1,000 to 1,875 writes/sec, plan a change at 500+ | [PostgreSQL write benchmarks](https://dev.to/haikasatryan/postgresql-write-performance-what-the-benchmarks-wont-tell-you-mm7) |
| Cache (Redis) | ~100,000 ops/sec, 1,000,000+ pipelined | [Redis benchmarks](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/benchmarks/) |
| Queue (Kafka) | ~millions of messages/sec per cluster | [Confluent: Kafka performance](https://developer.confluent.io/learn/kafka-performance/) |
| App server | ~2,000 to 8,000 requests/sec | order of magnitude |
| CDN | huge read fan out, zero help for writes | a CDN is a read cache |

Capacity is computed with standard [back of the envelope estimation](https://bytebytego.com/courses/system-design-interview/back-of-the-envelope-estimation) and [Little's Law](https://en.wikipedia.org/wiki/Little's_law). The goal is the right order of magnitude: within 2x is fine, off by 100x means you designed the wrong system.

---

## It is benchmarked, and the benchmark is honest

Run it yourself:

```bash
python scripts/bench.py
```

```
Brok benchmark scorecard

  bottleneck accuracy : 100%
  capacity within 2x  : 100%
  off by 100x         : 0
  citeability         : 100%
  overload accuracy   : 100%
```

What that does and does not mean matters, so here is the honest framing. The benchmark validates three things on a curated golden set:

1. **Consistency.** On controlled designs, does the engine reproduce its own cited ceilings end to end? (The expected capacities are derived by hand from the published ceilings, not read back from the engine, so it is not circular.)
2. **Behavior.** Does it abstain on unknown components, and does it avoid crying wolf on a tiny hobby app?
3. **Honesty.** Real systems like Instagram (which sharded for data volume, not throughput) and Discord (a read hot partition) are included as documented out of model cases. They run, they stay visible in the scorecard, and they are excluded from accuracy scoring because they sit outside what a single instance throughput model can judge.

So the claim is precise: **Brok is internally consistent with its cited numbers, behaves correctly, and is honest about what it cannot see.** It is not a claim that it predicts every real world scaling wall.

---

## How it works

```
  Claude Code (or any MCP client)
        |
        v
  Brok MCP
        |
   parse to a Design Graph        <- the caller does any English parsing;
        |                            Brok only consumes structured input
        v
   capacity + latency + cost lens <- cited ceilings, back of envelope math,
        |                            queueing knee, curated cost table
        v
   trade-off layer + roast voice  <- curated cited trade-offs, phrased by a
        |                            template narrator (still no model)
        v
   verdict: bottleneck + max users + utilization + latency + cost + trade-offs
```

The split is the whole point. The calling assistant (which is already an LLM) turns your prose or code into a structured graph. Brok's engine, which contains no model and makes no network calls, does the actual reasoning against cited numbers. That is why it is free, deterministic, and not a wrapper.

---

## Limits (read this before trusting a verdict)

Brok is honest about its boundaries on purpose:

- **Latency is relative, not absolute.** The queueing signal tells you how many times the idle latency you are paying at a given load (`1 / (1 - utilization)`), not a millisecond number. Absolute latency needs per-handler compute time and cache hit rates Brok cannot know, so it does not invent them.
- **Cost is order of magnitude.** Compute is a mid-tier table and egress is computed from your traffic; the figure is a "right ballpark" sanity check on the bill, not a billing forecast. Storage volume and per-request charges are not modeled.
- **Throughput only.** It reasons about request throughput, not data volume, connection limits, hot partitions, or lock contention, which is where many real databases actually die.
- **Single instance.** It does not model replicas or shards. It tells you when a single instance of a component is the wall, which is exactly the advice a pre scaling design needs.
- **Order of magnitude.** Component throughput varies 10x to 100x by hardware and config, so treat the numbers as "right ballpark," not precise.
- **It abstains.** Hand it a component it has no cited number for, and it says so rather than guessing.

---

## Install

```bash
git clone https://github.com/RudraDudhat2509/brok
cd brok
pip install -e ".[dev]"
```

Add it to an MCP client (for example Claude Desktop), in the `mcpServers` block:

```json
{
  "mcpServers": {
    "brok": { "command": "python", "args": ["-m", "brok.server"] }
  }
}
```

---

## Usage

Brok exposes two tools. The calling assistant picks the right one and, importantly, should pass the expected scale (`expected_dau`); without it, the result falls back to assumed defaults and is reported as low confidence.

**`review_architecture(compose_yaml, expected_dau=..., read_write_ratio=..., ...)`**
When the project has a `docker-compose.yml`, the assistant reads it and passes the contents plus the expected scale.

**`review_components(components, expected_dau=..., ...)`**
When there is no compose file, the assistant infers the components from the code or the user's description and passes them as a list of `{"name", "type"}` dicts. Valid types: `relational_db`, `cache`, `queue`, `cdn`, `app_server`, `object_store`, `load_balancer`. Anything else is reported as not estimated.

Both return a structured result the assistant can display and reason over:

```python
import brok.server as s

result = s.review_architecture(
    """
    services:
      api:   { build: . }
      db:    { image: postgres:16 }
      cache: { image: redis:7 }
    """,
    expected_dau=2_000_000,
)

print(result["bottleneck"])   # "api"
print(result["max_dau"])      # 1152000
print(result["roast_text"])   # the Brok-voiced verdict, the headline to show
print(result["tradeoffs"])    # structured trade-offs per component, to reason over
print(result["cost"])         # rough monthly compute plus egress
```

Returned fields: `bottleneck`, `max_dau`, `confidence`, `assumptions`, `utilizations`, `notes`, `tradeoffs`, `cost`, `report_text`, `roast_text`.

A companion Claude Code skill ships in [`skill/SKILL.md`](skill/SKILL.md): it tells the assistant to consult Brok whenever it is designing, scaling, or reviewing a system, or choosing a datastore, cache, or queue.

---

## Roadmap

Built and benchmarked today: the capacity engine and the golden set benchmark, a usable MCP surface, the curated trade-off knowledge layer, the Brok roast voice (a deterministic narrator that phrases the findings in Brok's dry register, see [docs/brok-voice.md](docs/brok-voice.md), while the numbers stay computed by the engine), a queueing-aware latency signal (the knee), and a rough cost lens (compute plus egress).

Ahead:

- **Anti pattern linter.** Structural checks for single points of failure, dual writes, write to CDN, and hot partitions (the failure mode behind the Discord case above).
- **Connection and data-volume limits.** The throughput model does not yet see connection-pool exhaustion or data-volume walls, which is where many real databases actually die.

---

## Why it is built this way

Brok is deliberately the opposite of a confident guess. The intelligence lives in cited data and arithmetic, the model is kept away from the judgment, and the tool abstains when it does not know. The roast is deterministic too: the voice phrases the findings, the engine computes them, so a verdict you can trust is never traded away for a line that sounds good.

## Development

```bash
pip install -e ".[dev]"
pytest -q          # the full deterministic test suite
python scripts/bench.py   # the capacity benchmark scorecard
```

Everything runs with no API key and no network.
