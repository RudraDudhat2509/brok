# Brok benchmarks

All numbers measured on 2026-10-08 on one Windows machine (Python 3.12.7) with the commands below. Raw outputs are in `benchmarks/raw/`.

| Metric | Value | Baseline | n | Command | Reproduced? |
|---|---|---|---|---|---|
| Tests passing | 359 / 359 | n/a | 359 | `python -m pytest -o addopts=""` | yes |
| Line coverage | 98% (878 stmts, 17 missed) | n/a | 31 modules | `python -m pytest --cov=brok` | yes |
| Original golden set (capacity) | bottleneck 100%, within 2x 100%, off by 100x: 0, citeability 100%, overload 100% | n/a | 4 scored + 3 documented | `python scripts/bench.py` | yes |
| Expanded capacity set: bottleneck accuracy | 21 / 21 | gpt-4o-mini 66.7% mean, gpt-oss-120b 17.5% mean | 21 cases | `python benchmarks/run_capacity.py` | yes |
| Expanded capacity set: max DAU within 2x | 19 / 19 | gpt-4o-mini 0%, gpt-oss-120b 12.3% (T=0) / 10.5% (T=0.7) | 19 cases | same | yes |
| Expanded capacity set: off by 100x or more | 0 / 19 | gpt-4o-mini 17-18 of 19 per run, gpt-oss-120b 12-17 of 19 per run | 19 cases | same | yes |
| Correct abstain on non-estimable designs | 2 / 2 | n/a | 2 | same | yes |
| Determinism | byte-identical output | n/a | 20 designs x 10 runs | `python benchmarks/run_capacity.py` | yes |
| `review_from_components` latency | p50 0.19 ms, p95 0.27 ms | n/a | 500 calls | same | yes |
| KB retrieval, original 30 queries | recall@1 55.0%, recall@3 93.3%, recall@5 98.3%, MRR 0.928 | n/a | 30 | `python benchmarks/run_retrieval.py` | recall@3 yes, see note 1 |
| KB retrieval, 20 new paraphrase/typo queries | recall@1 57.5%, recall@3 82.5%, recall@5 87.5%, MRR 0.796 | n/a | 20 | same | yes |
| Hallucination guard | 10 / 10 | n/a | 10 | `python scripts/bench_query.py` | yes |
| `search()` latency (model warm) | p50 17.9 ms, p95 22.9 ms | n/a | 300 calls | `python benchmarks/run_retrieval.py` | yes |

## LLM comparison detail

Same 21 designs, same traffic inputs given to each model, 3 runs per setting. The LLMs were not given the cited ceilings.

| Model | Temp | Bottleneck acc (3 runs) | Within 2x (3 runs) | Off by 100x or more (3 runs, of 19) | Cases whose DAU answer changed across runs |
|---|---|---|---|---|---|
| brok | n/a | 100% | 100% | 0 | 0 / 21 |
| openai gpt-4o-mini | 0 | 67 / 67 / 67% | 0 / 0 / 0% | 18 / 18 / 18 | 1 / 21 |
| openai gpt-4o-mini | 0.7 | 67 / 62 / 67% | 0 / 0 / 0% | 18 / 17 / 17 | 15 / 21 |
| groq gpt-oss-120b | 0 | 14 / 19 / 19% | 5 / 16 / 16% | 17 / 13 / 14 | 6 / 21 |
| groq gpt-oss-120b | 0.7 | 19 / 19 / 14% | 16 / 11 / 5% | 13 / 12 / 15 | 12 / 21 |

## Caveats a skeptical engineer would raise

1. **The capacity numbers are a consistency check, not validation against reality.** I derived the expected answers by hand from the same cited ceilings in `brok/kb.py`, so 21/21 with zero error shows the engine implements its own spec correctly. It does not show those ceilings predict real systems. The three out-of-model documented cases (Instagram, Discord) are the honest evidence that it does not model data-volume or hot-partition walls.
2. **The LLM baseline is a fair-input, unfair-knowledge comparison.** The LLMs saw the traffic numbers but not the ceilings, and they were asked for a bare number. gpt-4o-mini mostly answered about 2,000, which looks like requests per second, not DAU. A better prompt would close part of the gap. Treat the LLM rows as "a plain prompt gets this", not "LLMs can't do this".
3. **gpt-oss-120b returned null instead of a number in 44 of 57 capacity answers** (40 of 57 at T=0.7). I counted those as misses. There were 0 API errors, so this is the model's output, but it makes its accuracy a floor.
4. **Original commit message claimed 98.3% retrieval recall.** That is recall@5. The benchmark script's own gate is recall@3, which reproduces at 93.3%. Use 93.3% when you say "recall@3".
5. **Recall@1 is structurally capped.** Most queries expect 2 entries, so a perfect system scores 50% on recall@1 for those. Do not quote recall@1 as a weakness or a strength.
6. **Retrieval drops from 93.3% to 82.5% on queries I wrote after the fact.** Two of the 20 returned no matches at all (similarity cutoff 0.25): "my table is too big for one machine, how do i split it up" and "serve images and javascript bundles close to users". That gap is a hint the KB or its queries are tuned to the original phrasing. n=20 is small.
7. **I did not change any brok source.** New files are only under `benchmarks/`.
8. Cost: 126 gpt-4o-mini calls (63 per temperature setting), roughly a cent or two at list price (estimated, not metered). The 126 Groq calls were free tier. A first attempt with `llama-3.3-70b-versatile` returned 404 (no access on this key), so I used `openai/gpt-oss-120b` instead.

## Not run

- `scripts/bench_llm.py` as written: it hard-codes `llama-3.3-70b-versatile`, which this Groq key can no longer access. `benchmarks/run_llm.py` replaces it on the expanded set.
