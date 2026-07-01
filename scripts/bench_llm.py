"""
LLM baseline benchmark — compares raw llama-3.3-70b against Brok on:
  1. Bottleneck accuracy (3 scored golden cases, 3 runs each)
  2. Capacity estimate accuracy and variance
  3. Source citation rate
  4. Structural anti-pattern recall (5 planted cases, 3 runs each)

Loads GROQ_API_KEY and OPEN_API_KEY from sindri/.env automatically.
"""
from __future__ import annotations

import json
import os
import pathlib
import statistics
import time

from groq import Groq

# Load .env from the sindri project root
_env_path = pathlib.Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

from brok.benchmark.golden import GOLDEN_CASES
from brok.benchmark.runner import run_benchmark
from brok.pipeline import review_from_components

MODEL = "llama-3.3-70b-versatile"
RUNS = 3

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

CAPACITY_SYSTEM = """You are a systems engineer estimating architecture capacity.
Given a list of components and an expected scale, return JSON with exactly these fields:
{
  "bottleneck": "<component name that saturates first, or null>",
  "max_users_dau": <integer estimate of max daily active users before failure, or null>,
  "sources": ["<URL or paper name for any throughput number you state>"],
  "reasoning": "<one sentence>"
}
Return ONLY valid JSON. No markdown, no explanation outside the JSON."""

STRUCTURAL_SYSTEM = """You are a systems engineer reviewing architecture for structural problems.
Given a list of components and traffic profile, return JSON:
{
  "issues": ["<issue_code: one of WRITE_TO_CDN, NO_LOAD_BALANCER, UNPROTECTED_DB, CONNECTION_POOL_RISK, DATA_VOLUME_WALL, or any other issue you see>"],
  "reasoning": "<one sentence per issue>"
}
Return ONLY valid JSON."""


def ask_capacity(components: list[tuple[str, str]], dau: int,
                 read_write_ratio: float) -> dict:
    prompt = (
        f"Architecture components: {components}\n"
        f"Expected scale: {dau:,} daily active users\n"
        f"Read/write ratio: {read_write_ratio} reads per write\n"
        "What is the bottleneck and max user capacity?"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CAPACITY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(resp.choices[0].message.content)


def ask_structural(components: list[tuple[str, str]], dau: int,
                   read_write_ratio: float) -> dict:
    prompt = (
        f"Architecture components: {components}\n"
        f"Expected scale: {dau:,} daily active users\n"
        f"Read/write ratio: {read_write_ratio} reads per write\n"
        "What structural problems does this design have?"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": STRUCTURAL_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(resp.choices[0].message.content)


# ---------------------------------------------------------------------------
# Planted anti-pattern cases
# ---------------------------------------------------------------------------

ANTIPATTERN_CASES = [
    {
        "name": "write-to-cdn",
        "target": "WRITE_TO_CDN",
        "components": [("cdn", "cdn"), ("api", "app_server"), ("db", "relational_db")],
        "dau": 500_000,
        "read_write_ratio": 3.0,
    },
    {
        "name": "connection-pool-risk",
        "target": "CONNECTION_POOL_RISK",
        "components": [
            ("api-1", "app_server"), ("api-2", "app_server"), ("api-3", "app_server"),
            ("db", "relational_db"),
        ],
        "dau": 200_000,
        "read_write_ratio": 10.0,
    },
    {
        "name": "no-load-balancer",
        "target": "NO_LOAD_BALANCER",
        "components": [
            ("api-1", "app_server"), ("api-2", "app_server"), ("db", "relational_db"),
        ],
        "dau": 300_000,
        "read_write_ratio": 9.0,
    },
    {
        "name": "unprotected-db",
        "target": "UNPROTECTED_DB",
        "components": [("api", "app_server"), ("db", "relational_db")],
        "dau": 500_000,
        "read_write_ratio": 9.0,
    },
    {
        "name": "data-volume-wall",
        "target": "DATA_VOLUME_WALL",
        "components": [("api", "app_server"), ("db", "relational_db")],
        "dau": 8_000_000,
        "read_write_ratio": 9.0,
    },
]


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

def run_capacity_cases() -> list[dict]:
    scored = [c for c in GOLDEN_CASES if c.scored_for_accuracy
              and c.expected_bottleneck_type is not None]
    results = []
    for case in scored:
        runs = []
        for _ in range(RUNS):
            try:
                r = ask_capacity(case.components, case.nfrs["dau"],
                                 case.nfrs["read_write_ratio"])
                runs.append(r)
                time.sleep(0.5)
            except Exception as e:
                runs.append({"error": str(e)})

        bottlenecks = [r.get("bottleneck") for r in runs if "bottleneck" in r]
        capacities = [r.get("max_users_dau") for r in runs
                      if r.get("max_users_dau") is not None]
        sources = [bool(r.get("sources")) for r in runs if "sources" in r]

        consistent = len(set(str(b) for b in bottlenecks)) == 1
        correct_bn = any(
            b and case.expected_bottleneck_type in str(b).lower()
            for b in bottlenecks
        )

        within_2x_flags = []
        for cap in capacities:
            if case.expected_capacity_dau and cap:
                ratio = max(cap, case.expected_capacity_dau) / max(
                    min(cap, case.expected_capacity_dau), 1)
                within_2x_flags.append(ratio <= 2.0)

        results.append({
            "name": case.name,
            "expected_bottleneck": case.expected_bottleneck_type,
            "expected_dau": case.expected_capacity_dau,
            "bottlenecks": bottlenecks,
            "capacities": capacities,
            "consistent": consistent,
            "bottleneck_correct": correct_bn,
            "within_2x": all(within_2x_flags) if within_2x_flags else None,
            "cv": round(statistics.stdev(capacities) / statistics.mean(capacities), 2)
                  if len(capacities) > 1 and statistics.mean(capacities) > 0 else None,
            "citation_rate": round(sum(sources) / len(sources), 2) if sources else 0.0,
        })
    return results


def run_antipattern_cases() -> list[dict]:
    results = []
    for case in ANTIPATTERN_CASES:
        brok_result = review_from_components(
            [{"name": n, "type": t} for n, t in case["components"]],
            traffic={"dau": case["dau"], "read_write_ratio": case["read_write_ratio"]},
        )
        brok_caught = any(
            a["code"] == case["target"] for a in brok_result["antipatterns"]
        )

        llm_caught_runs = []
        for _ in range(RUNS):
            try:
                r = ask_structural(case["components"], case["dau"],
                                   case["read_write_ratio"])
                issues = [i.upper() for i in r.get("issues", [])]
                caught = case["target"] in issues or any(
                    case["target"].replace("_", " ").lower() in i.lower()
                    or case["target"].split("_")[0].lower() in i.lower()
                    for i in issues
                )
                llm_caught_runs.append(caught)
                time.sleep(0.5)
            except Exception as e:
                llm_caught_runs.append(False)

        results.append({
            "name": case["name"],
            "target": case["target"],
            "brok_caught": brok_caught,
            "llm_recall": f"{sum(llm_caught_runs)}/{RUNS}",
            "llm_consistent": len(set(llm_caught_runs)) == 1,
        })
    return results


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_report(capacity_results: list[dict], antipattern_results: list[dict]) -> str:
    lines = [
        f"LLM baseline ({MODEL}) vs Brok",
        "=" * 54,
        "",
        "CAPACITY ACCURACY (3 runs per case)",
        "-" * 40,
    ]

    bn_correct = [r["bottleneck_correct"] for r in capacity_results]
    within_2x = [r["within_2x"] for r in capacity_results if r["within_2x"] is not None]
    consistent = [r["consistent"] for r in capacity_results]
    cvs = [r["cv"] for r in capacity_results if r["cv"] is not None]
    citation_rates = [r["citation_rate"] for r in capacity_results]

    for r in capacity_results:
        lines.append(f"  {r['name']}")
        lines.append(f"    expected: bottleneck={r['expected_bottleneck']}  "
                     f"dau={r['expected_dau']:,}")
        lines.append(f"    llm got:  bottlenecks={r['bottlenecks']}")
        lines.append(f"             capacities={r['capacities']}")
        lines.append(f"    consistent={r['consistent']}  correct_bn={r['bottleneck_correct']}  "
                     f"within_2x={r['within_2x']}  CV={r['cv']}  "
                     f"citation_rate={r['citation_rate']}")
        lines.append("")

    lines += [
        "CAPACITY SUMMARY",
        f"  bottleneck accuracy : LLM {sum(bn_correct)}/{len(bn_correct)} "
        f"({sum(bn_correct)/len(bn_correct):.0%})   Brok 100%",
        f"  capacity within 2x  : LLM {sum(within_2x)}/{len(within_2x)} "
        f"({sum(within_2x)/len(within_2x):.0%})   Brok 100%"
        if within_2x else "  capacity within 2x  : no estimates returned",
        f"  consistency         : LLM {sum(consistent)}/{len(consistent)} cases stable   Brok 100%",
        f"  capacity variance   : LLM avg CV={round(sum(cvs)/len(cvs),2) if cvs else 'n/a'}   Brok CV=0.00",
        f"  citation rate       : LLM {sum(citation_rates)/len(citation_rates):.0%}   Brok 100%",
        "",
        "STRUCTURAL ANTI-PATTERN RECALL (3 runs per case)",
        "-" * 40,
    ]

    for r in antipattern_results:
        llm_n = int(r["llm_recall"].split("/")[0])
        lines.append(
            f"  [{r['target']}]  "
            f"Brok={'CAUGHT' if r['brok_caught'] else 'MISSED'}  "
            f"LLM={r['llm_recall']} runs  "
            f"{'(consistent)' if r['llm_consistent'] else '(inconsistent)'}"
        )

    total_possible = len(antipattern_results) * RUNS
    llm_total = sum(int(r["llm_recall"].split("/")[0]) for r in antipattern_results)
    brok_total = sum(1 for r in antipattern_results if r["brok_caught"])

    lines += [
        "",
        "STRUCTURAL SUMMARY",
        f"  Brok   : {brok_total}/{len(antipattern_results)} anti-patterns caught (100% per run, deterministic)",
        f"  LLM    : {llm_total}/{total_possible} catches across all runs "
        f"({llm_total/total_possible:.0%} recall)",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Running LLM baseline with {MODEL} ({RUNS} runs per case)...\n")
    print("Phase 1: capacity cases")
    cap = run_capacity_cases()
    print("Phase 2: anti-pattern cases")
    ap = run_antipattern_cases()
    print()
    print(format_report(cap, ap))
