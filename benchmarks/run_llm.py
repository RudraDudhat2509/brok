"""LLM baseline on the 21 hand-derived cases. 3 runs each at temp 0 and 0.7, same traffic inputs brok gets."""
import json, os, pathlib, statistics as st, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from capacity_cases import CASES
for l in (pathlib.Path(__file__).parent.parent / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"):
        a, _, b = l.partition("="); os.environ[a.strip()] = b.strip().strip('"').strip("'")
from groq import Groq
from openai import OpenAI

SYS = """You are a systems engineer estimating architecture capacity.
Return ONLY JSON: {"bottleneck": "<component NAME that saturates first, or null if it cannot be estimated>",
"max_users_dau": <integer max daily active users before the bottleneck saturates, or null>, "reasoning": "<one sentence>"}"""

def prompt(comps, t):
    return (f"Components (name, type): {comps}\nRequests per user per day: {t['requests_per_user_per_day']}\n"
            f"Peak-to-average factor: {t['peak_factor']}\nReads per write: {t['read_write_ratio']}\n"
            f"Payload: {t['payload_kb']} KB\nWhat is the bottleneck and the max DAU?")

def run(client, model, temp):
    res = []
    for r in range(3):
        for name, comps, t, eb, ed in CASES:
            for attempt in range(3):
                try:
                    out = json.loads(client.chat.completions.create(
                        model=model, temperature=temp, response_format={"type": "json_object"},
                        messages=[{"role": "system", "content": SYS}, {"role": "user", "content": prompt(comps, t)}]
                    ).choices[0].message.content); break
                except Exception as e:
                    time.sleep(3 * (attempt + 1)); out = {"error": str(e)[:80]}
            b = out.get("bottleneck"); d = out.get("max_users_dau")
            try: d = int(d) if d is not None else None
            except Exception: d = None
            bn = (b == eb) or (eb is None and b in (None, "null", "None"))
            w2 = (ed is None and d is None) or (ed is not None and d and 0.5 <= d / ed <= 2)
            x100 = ed is not None and (not d or d / ed >= 100 or d / ed <= 0.01)
            print(r, name, b, d, flush=True); res.append(dict(run=r, case=name, bn=bn, w2=bool(w2), x100=bool(x100), d=d, exp=ed, err=out.get("error")))
            time.sleep(0.4)
    return res

def summarize(label, res):
    bn = [sum(x["bn"] for x in res if x["run"] == r) / 21 for r in range(3)]
    cap = [x for x in res if x["exp"] is not None]
    w2 = [sum(x["w2"] for x in cap if x["run"] == r) / 19 for r in range(3)]
    x100 = [sum(x["x100"] for x in cap if x["run"] == r) for r in range(3)]
    # run-to-run: cases where the 3 runs disagree on bottleneck / on exact DAU
    per = {}
    for x in res: per.setdefault(x["case"], []).append(x)
    unstable_d = sum(len({y["d"] for y in v}) > 1 for v in per.values())
    errs = sum(1 for x in res if x["err"])
    print(f"{label}: bottleneck acc per run {['%.0f%%'%(100*v) for v in bn]} mean {100*st.mean(bn):.1f}% | "
          f"within2x per run {['%.0f%%'%(100*v) for v in w2]} mean {100*st.mean(w2):.1f}% | "
          f"off>=100x per run {x100} | cases whose DAU answer changed across 3 runs: {unstable_d}/21 | api errors {errs}")
    return res

if __name__ == "__main__":
    out = {}
    models = [("groq gpt-oss-120b", Groq(api_key=os.environ["GROQ_API_KEY"]), "openai/gpt-oss-120b")]
    if os.environ.get("OPEN_API_KEY"):
        models.append(("openai gpt-4o-mini", OpenAI(api_key=os.environ["OPEN_API_KEY"]), "gpt-4o-mini"))
    for label, c, m in models:
        for temp in (0.0, 0.7):
            out[f"{label} T={temp}"] = summarize(f"{label} T={temp}", run(c, m, temp))
    json.dump(out, open(pathlib.Path(__file__).parent / "raw" / "llm_results.json", "w"), indent=1)
