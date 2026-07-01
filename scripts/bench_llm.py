"""
LLM baseline benchmark — three-way comparison: llama-3.3-70b vs gpt-4o-mini vs Brok

Metrics:
  1. Bottleneck accuracy       (3 scored golden cases, 3 runs each)
  2. Capacity within 2x        (same cases)
  3. Capacity variance (CV)    (same cases)
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
from openai import OpenAI

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
_env_path = pathlib.Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ[_k.strip()] = _v.strip().strip('"').strip("'")

from brok.benchmark.golden import GOLDEN_CASES
from brok.pipeline import review_from_components

RUNS = 3
GROQ_MODEL = "llama-3.3-70b-versatile"
OAI_MODEL = "gpt-4o-mini"

groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
oai_client = OpenAI(api_key=os.environ["OPEN_API_KEY"])

# ---------------------------------------------------------------------------
# Prompts
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

# ---------------------------------------------------------------------------
# API callers (provider-agnostic interface)
# ---------------------------------------------------------------------------

def _call(client, model: str, system: str, user: str) -> dict:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(resp.choices[0].message.content)


def ask_capacity(client, model: str,
                 components: list[tuple[str, str]], dau: int,
                 read_write_ratio: float) -> dict:
    prompt = (
        f"Architecture components: {components}\n"
        f"Expected scale: {dau:,} daily active users\n"
        f"Read/write ratio: {read_write_ratio} reads per write\n"
        "What is the bottleneck and max user capacity?"
    )
    return _call(client, model, CAPACITY_SYSTEM, prompt)


def ask_structural(client, model: str,
                   components: list[tuple[str, str]], dau: int,
                   read_write_ratio: float) -> dict:
    prompt = (
        f"Architecture components: {components}\n"
        f"Expected scale: {dau:,} daily active users\n"
        f"Read/write ratio: {read_write_ratio} reads per write\n"
        "What structural problems does this design have?"
    )
    return _call(client, model, STRUCTURAL_SYSTEM, prompt)

# ---------------------------------------------------------------------------
# Anti-pattern cases
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

def _score_capacity_runs(runs: list[dict], expected_bottleneck: str,
                          expected_dau: int) -> dict:
    bottlenecks = [r.get("bottleneck") for r in runs if "bottleneck" in r]
    capacities = [r.get("max_users_dau") for r in runs
                  if r.get("max_users_dau") is not None]
    sources = [bool(r.get("sources")) for r in runs if "sources" in r]

    within_2x_flags = []
    for cap in capacities:
        if expected_dau and cap:
            ratio = max(cap, expected_dau) / max(min(cap, expected_dau), 1)
            within_2x_flags.append(ratio <= 2.0)

    return {
        "bottlenecks": bottlenecks,
        "capacities": capacities,
        "consistent": len(set(str(b) for b in bottlenecks)) == 1 and len(bottlenecks) > 0,
        "bottleneck_correct": any(
            b and expected_bottleneck in str(b).lower() for b in bottlenecks
        ),
        "within_2x": all(within_2x_flags) if within_2x_flags else None,
        "cv": round(statistics.stdev(capacities) / statistics.mean(capacities), 2)
              if len(capacities) > 1 and statistics.mean(capacities) > 0 else None,
        "citation_rate": round(sum(sources) / len(sources), 2) if sources else 0.0,
    }


def run_capacity_cases(client, model: str) -> list[dict]:
    scored = [c for c in GOLDEN_CASES
              if c.scored_for_accuracy and c.expected_bottleneck_type is not None]
    results = []
    for case in scored:
        runs = []
        for _ in range(RUNS):
            try:
                runs.append(ask_capacity(client, model, case.components,
                                         case.nfrs["dau"], case.nfrs["read_write_ratio"]))
                time.sleep(0.4)
            except Exception as e:
                runs.append({"error": str(e)})

        scored_run = _score_capacity_runs(runs, case.expected_bottleneck_type,
                                          case.expected_capacity_dau)
        results.append({"name": case.name,
                        "expected_bottleneck": case.expected_bottleneck_type,
                        "expected_dau": case.expected_capacity_dau,
                        **scored_run})
    return results


def run_antipattern_cases(client, model: str) -> list[dict]:
    results = []
    for case in ANTIPATTERN_CASES:
        brok_result = review_from_components(
            [{"name": n, "type": t} for n, t in case["components"]],
            traffic={"dau": case["dau"], "read_write_ratio": case["read_write_ratio"]},
        )
        brok_caught = any(a["code"] == case["target"]
                          for a in brok_result["antipatterns"])

        llm_runs = []
        for _ in range(RUNS):
            try:
                r = ask_structural(client, model, case["components"],
                                   case["dau"], case["read_write_ratio"])
                issues = [i.upper() for i in r.get("issues", [])]
                caught = case["target"] in issues or any(
                    case["target"].replace("_", " ").lower() in i.lower()
                    or case["target"].split("_")[0].lower() in i.lower()
                    for i in issues
                )
                llm_runs.append(caught)
                time.sleep(0.4)
            except Exception:
                llm_runs.append(False)

        results.append({
            "name": case["name"],
            "target": case["target"],
            "brok_caught": brok_caught,
            "llm_recall": f"{sum(llm_runs)}/{RUNS}",
            "llm_consistent": len(set(llm_runs)) == 1,
        })
    return results

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _cap_summary(results: list[dict]) -> dict:
    bn = [r["bottleneck_correct"] for r in results]
    w2x = [r["within_2x"] for r in results if r["within_2x"] is not None]
    cvs = [r["cv"] for r in results if r["cv"] is not None]
    return {
        "bn_pct": f"{sum(bn)/len(bn):.0%}" if bn else "n/a",
        "w2x_pct": f"{sum(w2x)/len(w2x):.0%}" if w2x else "n/a",
        "cv": f"{sum(cvs)/len(cvs):.2f}" if cvs else "n/a",
    }


def _ap_summary(results: list[dict]) -> dict:
    total = len(results) * RUNS
    caught = sum(int(r["llm_recall"].split("/")[0]) for r in results)
    return {"recall": f"{caught/total:.0%}", "caught": caught, "total": total}


def format_report(groq_cap, groq_ap, oai_cap, oai_ap) -> str:
    gs = _cap_summary(groq_cap)
    os_ = _cap_summary(oai_cap)
    gas = _ap_summary(groq_ap)
    oas = _ap_summary(oai_ap)

    W = 22
    lines = [
        "=" * 70,
        f"{'METRIC':<30} {'llama-3.3-70b':>{W}} {'gpt-4o-mini':>{W}} {'Brok':>{W}}",
        "=" * 70,
        "",
        "CAPACITY",
        f"  {'bottleneck accuracy':<28} {gs['bn_pct']:>{W}} {os_['bn_pct']:>{W}} {'100%':>{W}}",
        f"  {'capacity within 2x':<28} {gs['w2x_pct']:>{W}} {os_['w2x_pct']:>{W}} {'100%':>{W}}",
        f"  {'estimate variance (CV)':<28} {gs['cv']:>{W}} {os_['cv']:>{W}} {'0.00':>{W}}",
        "",
        "STRUCTURAL ANTI-PATTERN RECALL",
    ]

    for g, o in zip(groq_ap, oai_ap):
        g_val = g["llm_recall"]
        o_val = o["llm_recall"]
        brok_val = "3/3" if g["brok_caught"] else "0/3"
        lines.append(f"  {g['target']:<28} {g_val:>{W}} {o_val:>{W}} {brok_val:>{W}}")

    lines += [
        "",
        f"  {'overall recall':<28} {gas['recall']:>{W}} {oas['recall']:>{W}} {'100%':>{W}}",
        "=" * 70,
        "",
        "PER-CASE DETAIL (capacity)",
        "-" * 50,
    ]

    for g, o in zip(groq_cap, oai_cap):
        lines.append(f"  {g['name']}")
        lines.append(f"    expected  bn={g['expected_bottleneck']}  dau={g['expected_dau']:,}")
        lines.append(f"    llama     bn={g['bottlenecks']}  caps={g['capacities']}")
        lines.append(f"    gpt4omini bn={o['bottlenecks']}  caps={o['capacities']}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Phase 1: capacity cases — {GROQ_MODEL}")
    groq_cap = run_capacity_cases(groq_client, GROQ_MODEL)
    print(f"Phase 2: anti-pattern cases — {GROQ_MODEL}")
    groq_ap = run_antipattern_cases(groq_client, GROQ_MODEL)

    print(f"Phase 3: capacity cases — {OAI_MODEL}")
    oai_cap = run_capacity_cases(oai_client, OAI_MODEL)
    print(f"Phase 4: anti-pattern cases — {OAI_MODEL}")
    oai_ap = run_antipattern_cases(oai_client, OAI_MODEL)

    print()
    print(format_report(groq_cap, groq_ap, oai_cap, oai_ap))
