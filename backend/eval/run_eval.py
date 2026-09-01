"""Routing eval — grader ko measure karta hai, uspe bharosa nahi karta.

`docs/ROADMAP.md` ka point A. README ab tak bolta tha "routing 5/5 sahi aayi" —
paanch demo queries pe. Wo ek anecdote hai, measurement nahi. Ye harness usko
number me badalta hai.

    python -m eval.run_eval                       # poora set
    python -m eval.run_eval --limit 5             # smoke run (rate limit bachao)
    python -m eval.run_eval --only web            # sirf fallback cases
    python -m eval.run_eval --out eval/results.json

**Kya measure hota hai**

Routing ek binary classification hai: har question ko `local` ya `web` jaana
chahiye. Isliye plain accuracy kaafi nahi — dono errors ki keemat alag hai:

- **Missed fallback** (`web` chahiye tha, `local` gaya) — system ne un documents
  se jawab bana diya jinhe khud "sufficient" samjha, jabki the nahi. Yahi wo
  hallucination hai jise rokne ke liye poora CRAG banaya gaya hai. **Ye mehnga
  error hai.**
- **Unnecessary fallback** (`local` chahiye tha, `web` gaya) — ek extra web call
  aur thodi latency. **Ye sasta error hai.**

Isliye headline accuracy ke saath dono error counts alag report hote hain, aur
exit code **missed fallbacks** pe gate karta hai — usi metric pe jo sach me
matter karti hai. (Yahi pattern code-guardian ke routing eval me bhi hai:
threshold us error pe lagao jo mehnga ho.)

**Groundedness rate** bhi report hota hai — kitne answers guardrails se clean
nikle. Ye routing se alag axis hai: sahi route lene ke baad bhi answer ungrounded
ho sakta hai.

**Latency by route** — local vs web ka average. Yahi "adaptive kyun, hamesha web
kyun nahi" wale argument ka asli number hai.

**Ye eval deterministic nahi hai.** Web cases live DuckDuckGo hit karte hain, aur
LLM temperature 0 pe bhi bilkul identical nahi rehta. Do runs me ±1 case ka farak
normal hai. Isiliye headline pe koi decimal nahi likha jaata.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from app.graph.build_graph import build_crag_graph
from app.schemas.crag_state import initial_state

HERE = Path(__file__).parent
DEFAULT_SCENARIOS = HERE / "scenarios.json"

# source_type -> label. Graph "vector_db"/"web_search" bolta hai, scenarios
# "local"/"web" — mapping ek jagah rakhi hai taaki dono vocabularies alag reh
# sakein aur eval graph ke internals se tightly coupled na ho.
ROUTE_OF_SOURCE = {"vector_db": "local", "web_search": "web"}


# Kaunse node LLM call karte hain. `retrieve` aur `web_search_fallback` nahi —
# ek vector search hai, doosra HTTP search. Ye list graph ke saath badalni padegi
# agar koi naya LLM node aaye; isliye ek jagah rakhi hai.
LLM_NODES = ("grade_documents", "transform_query", "generate", "validate_guardrails")


def count_llm_calls(logs: List[str]) -> int:
    """Trace se LLM calls gino.

    **Latency ki jagah yahi metric kyun.** "Adaptive kyun, hamesha web search
    kyun nahi" ka poora argument cost pe khada hai. Latency se wo cost measure
    karne ki koshish ki thi aur wo fail hui — Groq ki throttling itni hawi hai
    ki route ka farak usme doob jaata hai (detail RESULTS.md me).

    Call count us problem se azaad hai: ye graph ke structure se aata hai, timing
    se nahi. Do baar chalao, wahi number milega. Yahi wo cheez hai jo asli me
    claim ki ja sakti hai.
    """
    return sum(1 for line in logs if line.split(" ")[0] in LLM_NODES)


# ---------------------------------------------------------------------------
# running one case
# ---------------------------------------------------------------------------

def run_case(graph, case: Dict[str, Any], max_attempts: int = 3) -> Dict[str, Any]:
    """Ek question chalao aur observed route + metrics lauta do.

    Groq free tier pe rate limit asli problem hai (self-healing-sql-agent me yahi
    sabse bada atkaav nikla tha), isliye exponential backoff ke saath poora case
    retry hota hai. Retry ko result me count karte hain — agar koi run bahut
    retries dikhaye to number ko shak ki nazar se dekhna chahiye.
    """
    question = case["question"]
    last_error = ""

    for attempt in range(max_attempts):
        started = time.perf_counter()
        try:
            final = graph.invoke(initial_state(question))
        except Exception as exc:  # noqa: BLE001 — rate limit, network, model 404
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < max_attempts - 1:
                # 4s, 16s — Groq ka per-minute window isse cross ho jaata hai
                time.sleep(4 ** (attempt + 1))
                continue
            return {
                "id": case["id"],
                "question": question,
                "expected_route": case["expected_route"],
                "observed_route": None,
                "routed_correctly": False,
                "error": last_error,
                "attempts": attempt + 1,
            }

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        source_type = final.get("source_type", "")
        observed = ROUTE_OF_SOURCE.get(source_type)

        answer = final.get("final_output") or final.get("generation") or ""
        expected = case["expected_route"]

        # Keyword check sirf local cases pe. Web cases ka text live search se
        # aata hai — usme keyword na milna model ki galti ho bhi sakti hai aur
        # us din ke search results ki bhi. Aise signal ko metric banana galat hai.
        keywords = case.get("expect_keywords") or []
        if expected == "local" and keywords:
            hit = [k for k in keywords if k.lower() in answer.lower()]
            keyword_hit = len(hit) > 0
        else:
            hit, keyword_hit = [], None

        return {
            "id": case["id"],
            "question": question,
            "expected_route": expected,
            "observed_route": observed,
            "routed_correctly": observed == expected,
            "hard": bool(case.get("hard")),
            "relevance_score": final.get("relevance_score", ""),
            "transformed_query": final.get("transformed_query", ""),
            "guardrail_passed": final.get("guardrail_passed"),
            "keywords_expected": keywords,
            "keywords_found": hit,
            "keyword_hit": keyword_hit,
            "elapsed_ms": elapsed_ms,
            "llm_calls": count_llm_calls(final.get("logs", [])),
            "nodes_run": len(final.get("logs", [])),
            "attempts": attempt + 1,
            "answer": answer[:400],
            "error": "",
        }

    return {}  # unreachable, loop hamesha return karta hai


def interleave(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """local aur web cases ko alternate karo.

    **Ye ek asli bug ka fix hai, cosmetic nahi.** Pehle run me cases file order
    me chale — pehle saare 12 local, phir saare 8 web. Result: case #1-4 me
    2-8 sec lage, aur #5 se aage har case 15-22 sec, chahe route koi bhi ho.
    Yaani Groq sustained load pe throttle kar raha tha, aur wo slowdown poora ka
    poora local bucket me gir gaya.

    Us run ka "local 13.7s vs web 18.5s" comparison isliye **route ka cost measure
    kar hi nahi raha tha** — wo position ka cost measure kar raha tha. Aur yahi
    number us poore argument ki jaan hai ki "hamesha web search kyun nahi".

    Alternate karne se throttling dono buckets pe barabar padti hai, to difference
    wapas route ka ho jaata hai. Isiliye ye default hai; `--order file` sirf
    reproduce karne ke liye rakha hai.
    """
    local = [c for c in cases if c["expected_route"] == "local"]
    web = [c for c in cases if c["expected_route"] == "web"]
    out: List[Dict[str, Any]] = []
    for i in range(max(len(local), len(web))):
        if i < len(local):
            out.append(local[i])
        if i < len(web):
            out.append(web[i])
    return out


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def score(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [r for r in results if not r.get("error")]
    errored = [r for r in results if r.get("error")]

    correct = [r for r in ok if r["routed_correctly"]]

    # Confusion matrix. Dono errors alag ginte hain kyunki dono ki keemat alag hai.
    missed_fallback = [
        r for r in ok if r["expected_route"] == "web" and r["observed_route"] == "local"
    ]
    unnecessary_fallback = [
        r for r in ok if r["expected_route"] == "local" and r["observed_route"] == "web"
    ]

    web_cases = [r for r in ok if r["expected_route"] == "web"]
    local_cases = [r for r in ok if r["expected_route"] == "local"]
    went_web = [r for r in ok if r["observed_route"] == "web"]

    def pct(n: int, d: int):
        """Denominator zero ho to `None`, `0.0` nahi.

        Ye cosmetic nahi hai: `--only local` chalane pe fallback recall ka
        denominator zero hota hai, aur "0.0%" padhne me *failure* lagta hai
        jabki sach ye hai ki wo metric is subset pe defined hi nahi. Ek eval ka
        kaam hi galat impression na dena hai.
        """
        return round(100.0 * n / d, 1) if d else None

    hard = [r for r in ok if r.get("hard")]
    easy = [r for r in ok if not r.get("hard")]

    graded = [r for r in ok if r.get("guardrail_passed") is not None]
    keyword_checked = [r for r in ok if r.get("keyword_hit") is not None]

    def mean_ms(rows: List[Dict[str, Any]]) -> int:
        return int(sum(r["elapsed_ms"] for r in rows) / len(rows)) if rows else 0

    def mean_calls(rows: List[Dict[str, Any]]):
        return round(sum(r["llm_calls"] for r in rows) / len(rows), 2) if rows else None

    return {
        "total_cases": len(results),
        "errored": len(errored),
        "scored": len(ok),

        "routing_accuracy_pct": pct(len(correct), len(ok)),
        "routing_correct": len(correct),

        # Fallback ko positive class maan kar. Recall = jo cases web maangte the,
        # unme se kitne actually web gaye. Yahi wo metric hai jo hallucination
        # se bachati hai.
        "fallback_recall_pct": pct(len(web_cases) - len(missed_fallback), len(web_cases)),
        "fallback_precision_pct": pct(len(web_cases) - len(missed_fallback), len(went_web)),

        "missed_fallbacks": len(missed_fallback),
        "missed_fallback_ids": [r["id"] for r in missed_fallback],
        "unnecessary_fallbacks": len(unnecessary_fallback),
        "unnecessary_fallback_ids": [r["id"] for r in unnecessary_fallback],

        "accuracy_easy_pct": pct(len([r for r in easy if r["routed_correctly"]]), len(easy)),
        "accuracy_hard_pct": pct(len([r for r in hard if r["routed_correctly"]]), len(hard)),
        "hard_case_count": len(hard),

        "groundedness_pass_pct": pct(
            len([r for r in graded if r["guardrail_passed"]]), len(graded)
        ),
        "keyword_hit_pct": pct(
            len([r for r in keyword_checked if r["keyword_hit"]]), len(keyword_checked)
        ),

        "mean_ms_local_route": mean_ms([r for r in ok if r["observed_route"] == "local"]),
        "mean_ms_web_route": mean_ms([r for r in ok if r["observed_route"] == "web"]),
        "llm_calls_local_route": mean_calls([r for r in ok if r["observed_route"] == "local"]),
        "llm_calls_web_route": mean_calls([r for r in ok if r["observed_route"] == "web"]),

        "local_case_count": len(local_cases),
        "web_case_count": len(web_cases),
        "total_retries": sum(r.get("attempts", 1) - 1 for r in results),
    }


def print_report(results: List[Dict[str, Any]], s: Dict[str, Any]) -> None:
    print()
    print("=" * 72)
    print("ADAPTIVE CRAG — ROUTING EVAL")
    print("=" * 72)

    print(f"\n{'id':<4} {'expected':<9} {'observed':<9} {'ok':<4} {'hard':<5} {'ms':>6}  question")
    print("-" * 72)
    for r in results:
        if r.get("error"):
            print(f"{r['id']:<4} {r['expected_route']:<9} {'ERROR':<9} {'-':<4} {'-':<5} {'-':>6}  {r['question'][:34]}")
            continue
        mark = "ok" if r["routed_correctly"] else "MISS"
        print(
            f"{r['id']:<4} {r['expected_route']:<9} {str(r['observed_route']):<9} "
            f"{mark:<4} {('yes' if r.get('hard') else ''):<5} {r['elapsed_ms']:>6}  {r['question'][:34]}"
        )

    def f(key: str) -> str:
        v = s[key]
        return "n/a" if v is None else f"{v}%"

    print("\n" + "-" * 72)
    print(f"  Routing accuracy      : {f('routing_accuracy_pct')}  ({s['routing_correct']}/{s['scored']})")
    print(f"    on easy cases       : {f('accuracy_easy_pct')}")
    print(f"    on hard cases       : {f('accuracy_hard_pct')}  ({s['hard_case_count']} cases)")
    print()
    print(f"  Fallback recall       : {f('fallback_recall_pct')}   <- the metric that matters")
    print(f"  Fallback precision    : {f('fallback_precision_pct')}")
    print()
    print(f"  Missed fallbacks      : {s['missed_fallbacks']}  {s['missed_fallback_ids'] or ''}   (expensive error)")
    print(f"  Unnecessary fallbacks : {s['unnecessary_fallbacks']}  {s['unnecessary_fallback_ids'] or ''}   (cheap error)")
    print()
    print(f"  Groundedness pass     : {f('groundedness_pass_pct')}")
    print(f"  Keyword hit (local)   : {f('keyword_hit_pct')}")
    print()
    print(f"  LLM calls / query     : local {s['llm_calls_local_route']}  vs  web {s['llm_calls_web_route']}"
          "   <- the cost of correcting")
    print(f"  Mean latency          : local {s['mean_ms_local_route']} ms  vs  web {s['mean_ms_web_route']} ms")
    print("      (latency is throttling-dominated at this scale — not a route signal, see RESULTS.md)")
    if s["errored"]:
        print(f"\n  ⚠️  {s['errored']} case(s) errored out and were excluded from scoring")
    if s["total_retries"]:
        print(f"  ⚠️  {s['total_retries']} retry/retries were needed (rate limiting)")
    print("-" * 72)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Measure CRAG routing on labelled queries.")
    p.add_argument("--scenarios", default=str(DEFAULT_SCENARIOS))
    p.add_argument("--out", default="", help="write per-case JSON results here")
    p.add_argument("--limit", type=int, default=0, help="run only the first N cases")
    p.add_argument("--only", choices=["local", "web"], default="",
                   help="run only cases with this expected route")
    p.add_argument("--max-missed-fallbacks", type=int, default=1,
                   help="exit non-zero above this many missed fallbacks (the expensive error)")
    p.add_argument("--order", choices=["interleave", "file"], default="interleave",
                   help="case order; 'interleave' alternates local/web (default)")
    args = p.parse_args()

    cases = json.loads(Path(args.scenarios).read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["expected_route"] == args.only]
    if args.order == "interleave":
        cases = interleave(cases)
    if args.limit:
        cases = cases[: args.limit]

    print(f"Running {len(cases)} case(s)...", flush=True)
    graph = build_crag_graph()

    results = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] #{case['id']} {case['question'][:52]}", flush=True)
        results.append(run_case(graph, case))

    s = score(results)
    print_report(results, s)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"summary": s, "results": results}, indent=2), encoding="utf-8"
        )
        print(f"\nWrote {out}")

    # Gate missed fallbacks pe, overall accuracy pe nahi. Ek unnecessary fallback
    # ek extra web call hai; ek missed fallback wo hallucination hai jise rokne
    # ke liye ye poora system bana hai. Threshold usi error pe hona chahiye.
    if s["missed_fallbacks"] > args.max_missed_fallbacks:
        print(
            f"\nFAIL: {s['missed_fallbacks']} missed fallbacks "
            f"(limit {args.max_missed_fallbacks})"
        )
        return 1

    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
