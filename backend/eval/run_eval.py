"""Routing eval — measures the grader instead of trusting it.

The README used to say "routing was 5/5 correct" on five demo queries. That is
an anecdote, not a measurement. This harness turns it into a number.

    python -m eval.run_eval                       # the full set
    python -m eval.run_eval --limit 5             # smoke run, saves rate limit
    python -m eval.run_eval --only web            # fallback cases only
    python -m eval.run_eval --out eval/results.json

**What is measured**

Routing is a binary classification: every question should go `local` or `web`.
Plain accuracy is not enough, because the two errors do not cost the same:

- **Missed fallback** (should have gone `web`, went `local`) — the system
  answered from documents it judged sufficient when they were not. That is the
  hallucination the whole of CRAG exists to prevent. **The expensive error.**
- **Unnecessary fallback** (should have gone `local`, went `web`) — one extra
  web call and some latency. **The cheap error.**

So both error counts are reported next to the headline accuracy, and the exit
code gates on **missed fallbacks** — the metric that actually matters. Put the
threshold on the error that is expensive.

**Groundedness rate** is reported too: how many answers came back clean from the
guardrails. A different axis from routing — an answer can be ungrounded even when
the route was right.

**Answer correctness**, where the dataset provides a label, is the third axis:
whether the answer was actually right, which neither of the other two tells you.

**Latency by route** is printed but is not a route signal at this scale — Groq's
throttling swamps the difference. See RESULTS.md; the cost argument rests on LLM
call counts, which are exact.

**This eval is not deterministic.** Web cases hit live DuckDuckGo, and an LLM at
temperature 0 is still not byte-identical. A difference of ±1 case between runs
is normal, which is why no headline number is quoted to a decimal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from app.graph.build_graph import build_crag_graph
from app.schemas.crag_state import initial_state
from eval.answer_verdict import extract_verdict

HERE = Path(__file__).parent


def default_scenarios() -> Path:
    """Scenarios file `CORPUS` ke saath chalti hai.

    Pehle ye hardcoded `scenarios.json` (concepts) tha. Uska nateeja ek chupa
    hua measurement bug tha: `CORPUS=scifact` set karke eval chalao, to index
    the index was SciFact's but the questions were the concepts ones. The eval
    does not crash — it quietly prints confident, meaningless routing numbers,
    and the failure looks like *the router being wrong* when the setup was wrong.

    That is the kind of bug this project most wants to avoid: a measurement that
    blames the wrong component. So the default follows the corpus; `--scenarios`
    can still override it.
    """
    corpus = os.getenv("CORPUS", "concepts").strip() or "concepts"
    name = "scenarios.json" if corpus == "concepts" else f"scenarios_{corpus}.json"
    return HERE / name

# source_type -> label. Graph "vector_db"/"web_search" bolta hai, scenarios
# "local"/"web" — mapping ek jagah rakhi hai taaki dono vocabularies alag reh
# sakein aur eval graph ke internals se tightly coupled na ho.
ROUTE_OF_SOURCE = {"vector_db": "local", "web_search": "web"}

# A third label. "local"/"web" mean the corpus does or does not hold the answer.
# "ambiguous" ka matlab hai **reasonable log disagree karenge** — corpus topic ko
# half-covers the topic. Accuracy is meaningless on these; stability
# measure hoti hai (neeche score() dekh).
AMBIGUOUS = "ambiguous"


# Which nodes make an LLM call. Not `retrieve` or `web_search_fallback` —
# ek vector search hai, doosra HTTP search. Ye list graph ke saath badalni padegi
# if a new LLM node is added, so it lives in one place.
LLM_NODES = ("grade_documents", "transform_query", "generate", "validate_guardrails")


def count_llm_calls(logs: List[str]) -> int:
    """Trace se LLM calls gino.

    **Why this metric rather than latency.** The whole "why adaptive, why not
    always search" argument rests on cost. Latency cannot measure that at this
    scale — Groq's throttling dominates so completely that the route difference
    drowns in it (details in RESULTS.md).

    Call count us problem se azaad hai: ye graph ke structure se aata hai, timing
    not from timing. Run it twice and the number is the same. That is what
    claim ki ja sakti hai.
    """
    return sum(1 for line in logs if line.split(" ")[0] in LLM_NODES)


# ---------------------------------------------------------------------------
# running one case
# ---------------------------------------------------------------------------

def run_case(graph, case: Dict[str, Any], max_attempts: int = 3) -> Dict[str, Any]:
    """Ek question chalao aur observed route + metrics lauta do.

    Groq free tier pe rate limit asli problem hai (self-healing-sql-agent me yahi
    turned out to be the biggest blocker), so the whole case is re-run with
    exponential backoff. Retries are reported in `attempts` — a run that shows
    retries is a run whose numbers deserve suspicion.
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
                # 4s, 16s — enough to cross Groq's per-minute window
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

        # **Retrieval recall@k** — sirf tab jab dataset gold docs deta ho (BEIR).
        # The metric that was impossible on the concepts corpus: there was no
        # ground truth about which chunk was correct, so retrieval quality could
        # not be measured at all — which is why the reranker A/B came out flat.
        # Here there are qrels, so this can actually move.
        gold = case.get("gold_docs") or []
        if gold and expected == "local":
            retrieved = set(final.get("sources") or [])
            recall_hit = any(g in retrieved for g in gold)
        else:
            recall_hit = None

        # **Answer correctness** — sirf un SciFact cases pe jinke saath dataset ka
        # apna SUPPORT/CONTRADICT label aata hai.
        #
        # Routing, recall and groundedness all fail to say whether the answer was
        # *right*. Groundedness only says the answer matches the context it got —
        # a wrong answer built from the wrong context can pass it. This is the gap
        # RESULTS.md names, and the metric reranking should have moved.
        # Yahan tak pahunchne ka matlab hai graph.invoke safal raha — error
        # path upar hi return kar chuka hota hai.
        expected_verdict = case.get("expected_verdict") or ""
        if expected_verdict:
            observed_verdict = extract_verdict(question, answer)
            verdict_correct = observed_verdict == expected_verdict
        else:
            observed_verdict, verdict_correct = "", None

        return {
            "id": case["id"],
            "question": question,
            "expected_route": expected,
            "observed_route": observed,
            # `None` on ambiguous cases, not `False`. They have no single right
            # answer, and counting them as wrong would make the headline accuracy
            # meaningless — which is exactly why they were left out of the eval to
            # begin with. They are measured by stability instead.
            "routed_correctly": None if expected == AMBIGUOUS else observed == expected,
            "hard": bool(case.get("hard")),
            "relevance_score": final.get("relevance_score", ""),
            "transformed_query": final.get("transformed_query", ""),
            "guardrail_passed": final.get("guardrail_passed"),
            "keywords_expected": keywords,
            "keywords_found": hit,
            "keyword_hit": keyword_hit,
            "gold_docs": gold,
            "recall_hit": recall_hit,
            "expected_verdict": expected_verdict,
            "observed_verdict": observed_verdict,
            "verdict_correct": verdict_correct,
            "elapsed_ms": elapsed_ms,
            "llm_calls": count_llm_calls(final.get("logs", [])),
            "nodes_run": len(final.get("logs", [])),
            "attempts": attempt + 1,
            "answer": answer[:400],
            "error": "",
        }

    return {}  # unreachable: the loop always returns


def interleave(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Alternate local and web cases.

    **This fixes a real bug, it is not cosmetic.** The first run took cases in
    file order — all 12 local, then all 8 web. Cases #1-4 took 2-8 seconds and
    everything from #5 onward took 15-22 seconds regardless of route: Groq was
    throttling under sustained load, and because the local cases ran first, the
    entire slowdown landed in the local bucket.

    That run's "local 13.7s vs web 18.5s" therefore **was not measuring the cost
    of the route** — it was measuring the cost of position. And that number is
    the whole basis of the "why not always search the web" argument.

    Alternating spreads the throttling evenly across both buckets, so the
    difference belongs to the route again. Hence the default; `--order file`
    exists only to reproduce the original mistake.
    """
    local = [c for c in cases if c["expected_route"] == "local"]
    web = [c for c in cases if c["expected_route"] == "web"]
    # Ambiguous cases have to alternate too. This function used to build only
    # local/web buckets and **silently drop** everything else — the moment the
    # ambiguous label was added, 8 cases vanished without a single error. So now
    # anything that is in neither bucket is caught explicitly.
    rest = [c for c in cases if c["expected_route"] not in ("local", "web")]
    out: List[Dict[str, Any]] = []
    for i in range(max(len(local), len(web), len(rest))):
        if i < len(local):
            out.append(local[i])
        if i < len(web):
            out.append(web[i])
        if i < len(rest):
            out.append(rest[i])
    assert len(out) == len(cases), "interleave ne cases drop kiye"
    return out


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def score_ambiguous(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score ambiguous cases by **stability**, not by accuracy.

    These cases have no single right answer — the corpus half-covers the topic and
    two reasonable people would label them differently. Counting "correct route"
    would turn an arguable label into a metric, which is the reason RESULTS.md
    gives for leaving them out of the headline in the first place.

    But one thing is **objectively wrong** even on an ambiguous case: taking a
    different route each time the same question is asked. That is not a disputed
    label, that is grader non-determinism, and it is a real defect. So each case
    runs several times and the question becomes: was the route the same every
    time?

    The metric also earns its keep later. The reranker's whole point is to give
    the grader better chunks, so if reranking improves stability that is a
    **measurable** benefit — while the headline accuracy is pinned at 100% and
    cannot move at all.
    """
    by_id: Dict[Any, List[Dict[str, Any]]] = {}
    for r in rows:
        by_id.setdefault(r["id"], []).append(r)

    cases = []
    for case_id, runs in sorted(by_id.items()):
        routes = [r["observed_route"] for r in runs]
        stable = len(set(routes)) == 1
        cases.append({
            "id": case_id,
            "question": runs[0]["question"][:70],
            "runs": len(routes),
            "routes": routes,
            "stable": stable,
            # Majority route — kis taraf jhukav hai, ye batata hai grader kitna
            # conservative hai. Aadha-cover topic pe "web" jaana zyada safe hai.
            "majority": max(set(routes), key=routes.count) if routes else None,
        })

    repeated = [c for c in cases if c["runs"] > 1]
    stable = [c for c in repeated if c["stable"]]
    went_web = [c for c in cases if c["majority"] == "web"]

    return {
        "ambiguous_cases": len(cases),
        # Stability only means something if the case ran more than once. At
        # `--repeat 1` this is `None`, not `100.0` — a single run reported as
        # "perfectly stable" would be a lie.
        "ambiguous_stability_pct": (
            round(100.0 * len(stable) / len(repeated), 1) if repeated else None
        ),
        "ambiguous_unstable_ids": [c["id"] for c in repeated if not c["stable"]],
        "ambiguous_went_web": len(went_web),
        "ambiguous_detail": cases,
    }


def score(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_all = [r for r in results if not r.get("error")]
    errored = [r for r in results if r.get("error")]

    # Ambiguous cases stay **entirely out** of the headline metrics. Folding them
    # into accuracy would make the whole number arguable, and an eval's job is to
    # produce a number that can be defended.
    ambiguous_rows = [r for r in ok_all if r["expected_route"] == AMBIGUOUS]
    ok = [r for r in ok_all if r["expected_route"] != AMBIGUOUS]

    correct = [r for r in ok if r["routed_correctly"]]

    # Confusion matrix. The two errors are counted separately because they cost
    # different amounts.
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
        """`None` when the denominator is zero, not `0.0`.

        Not cosmetic. Running `--only local` leaves fallback recall with a zero
        denominator, and "0.0%" reads as a *failure* when the truth is that the
        metric is undefined on that subset. An eval's job is to avoid giving the
        wrong impression.
        """
        return round(100.0 * n / d, 1) if d else None

    hard = [r for r in ok if r.get("hard")]
    easy = [r for r in ok if not r.get("hard")]

    graded = [r for r in ok if r.get("guardrail_passed") is not None]
    keyword_checked = [r for r in ok if r.get("keyword_hit") is not None]
    verdict_checked = [r for r in ok if r.get("verdict_correct") is not None]
    verdict_given_gold = [r for r in verdict_checked if r.get("recall_hit")]
    recall_checked = [r for r in ok if r.get("recall_hit") is not None]

    def mean_ms(rows: List[Dict[str, Any]]) -> int:
        return int(sum(r["elapsed_ms"] for r in rows) / len(rows)) if rows else 0

    def mean_calls(rows: List[Dict[str, Any]]):
        return round(sum(r["llm_calls"] for r in rows) / len(rows), 2) if rows else None

    return {
        "total_cases": len(results),
        "errored": len(errored),
        "scored": len(ok),   # ambiguous cases are not counted here

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
        "recall_at_k_pct": pct(
            len([r for r in recall_checked if r["recall_hit"]]), len(recall_checked)
        ),
        "recall_checked": len(recall_checked),
        "answer_verdict_pct": pct(
            len([r for r in verdict_checked if r["verdict_correct"]]), len(verdict_checked)
        ),
        "answer_verdict_checked": len(verdict_checked),
        "answer_verdict_unclear": len(
            [r for r in verdict_checked if r.get("observed_verdict") == "UNCLEAR"]
        ),
        # If the gold document was never retrieved, a wrong answer is retrieval's
        # failure, not the generator's. This subset isolates the generator.
        "answer_verdict_given_gold_pct": pct(
            len([r for r in verdict_given_gold if r["verdict_correct"]]),
            len(verdict_given_gold),
        ),
        "answer_verdict_given_gold_checked": len(verdict_given_gold),
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
        **score_ambiguous(ambiguous_rows),
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
    if s.get("answer_verdict_checked"):
        n = s["answer_verdict_checked"]
        g = s["answer_verdict_given_gold_checked"]
        print(f"  Answer verdict        : {f('answer_verdict_pct')}  ({n} cases with a "
              f"dataset SUPPORT/CONTRADICT label)   <- whether the answer was RIGHT")
        print(f"    given gold retrieved: {f('answer_verdict_given_gold_pct')}  ({g} cases)"
              f"   <- isolates the generator from retrieval")
        if s.get("answer_verdict_unclear"):
            print(f"    took no position    : {s['answer_verdict_unclear']}")
    # Only shown when the dataset provides gold documents (BEIR). The concepts
    # corpus has no ground truth, so printing a false 0% here would be wrong.
    if s.get("recall_checked"):
        print(f"  Retrieval recall@k    : {f('recall_at_k_pct')}"
              f"  ({s['recall_checked']} cases with gold docs)"
              "   <- whether the right document was even retrieved")
    print()
    def n(v, suffix: str = "") -> str:
        return "n/a" if v in (None, 0) else f"{v}{suffix}"

    print(f"  LLM calls / query     : local {n(s['llm_calls_local_route'])}  vs  web {n(s['llm_calls_web_route'])}"
          "   <- the cost of correcting")
    print(f"  Mean latency          : local {n(s['mean_ms_local_route'], ' ms')}  vs  web {n(s['mean_ms_web_route'], ' ms')}")
    print("      (latency is throttling-dominated at this scale — not a route signal, see RESULTS.md)")
    # The ambiguous block is separate and deliberately *below* the headline —
    # it is a different axis, not a part of accuracy.
    if s["ambiguous_cases"]:
        print()
        print(f"  Ambiguous cases       : {s['ambiguous_cases']}   (excluded from accuracy above)")
        if s["ambiguous_stability_pct"] is None:
            print("      stability          : not measured — needs --repeat 2 or more")
        else:
            print(f"      route stability    : {s['ambiguous_stability_pct']}%"
                  f"   {s['ambiguous_unstable_ids'] or ''}")
            print("      (same question, repeated: did it pick the same route every time?)")
        print(f"      leaned web         : {s['ambiguous_went_web']}/{s['ambiguous_cases']}"
              "   (higher = more conservative grader)")

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
    p.add_argument("--scenarios", default="",
                   help="scenarios JSON; default follows CORPUS "
                        "(concepts -> scenarios.json, scifact -> scenarios_scifact.json)")
    p.add_argument("--out", default="", help="write per-case JSON results here")
    p.add_argument("--limit", type=int, default=0, help="run only the first N cases")
    p.add_argument("--only", choices=["local", "web"], default="",
                   help="run only cases with this expected route")
    p.add_argument("--max-missed-fallbacks", type=int, default=1,
                   help="exit non-zero above this many missed fallbacks (the expensive error)")
    p.add_argument("--order", choices=["interleave", "file"], default="interleave",
                   help="case order; 'interleave' alternates local/web (default)")
    p.add_argument("--repeat", type=int, default=1, metavar="N",
                   help="run each AMBIGUOUS case N times to measure routing stability "
                        "(default 1; 3 is enough to catch a flapping grader)")
    p.add_argument("--skip-ambiguous", action="store_true",
                   help="run only the labelled local/web cases")
    args = p.parse_args()

    scenarios_path = Path(args.scenarios) if args.scenarios else default_scenarios()
    if not scenarios_path.exists():
        print(f"[eval] scenarios file not found: {scenarios_path}", file=sys.stderr)
        return 2
    print(f"[eval] corpus={os.getenv('CORPUS', 'concepts')}  scenarios={scenarios_path.name}")
    cases = json.loads(scenarios_path.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["expected_route"] == args.only]
    if args.skip_ambiguous:
        cases = [c for c in cases if c["expected_route"] != AMBIGUOUS]
    if args.order == "interleave":
        cases = interleave(cases)
    if args.limit:
        cases = cases[: args.limit]

    # Duplicate ambiguous cases N times. No attempt to space the repeats apart:
    # running the same question back-to-back has no cache-like effect (the graph
    # is stateless), and keeping them together concentrates the rate-limit backoff
    # in one place.
    if args.repeat > 1:
        expanded = []
        for c in cases:
            expanded.extend([c] * (args.repeat if c["expected_route"] == AMBIGUOUS else 1))
        cases = expanded

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

    # Gate on missed fallbacks, not overall accuracy. An unnecessary fallback is
    # one extra web call; a missed fallback is the hallucination this whole system
    # exists to prevent. The threshold belongs on that error.
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
