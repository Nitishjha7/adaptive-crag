"""SciFact ke qrels se routing eval scenarios generate karo.

    python -m eval.build_scifact_scenarios --local 20 --out eval/scenarios_scifact.json

**Why this script exists.** In `scenarios.json` (the concepts corpus) I wrote
both the documents and the labels, which RESULTS.md itself calls structural
bias: *"one author writing both the corpus and the eval is its own bias — the
honest fix is someone else writing cases."*

This is that fix. The `local` labels come from **SciFact's own qrels**: if the
dataset says query Q is answered by document D, and D is in our index, then Q
should stay local. I did not write that label.

The `web` cases are still hand-written, and **that has to be admitted** — but it
is the easy half. SciFact is 2020-era scientific abstracts, so questions about
today's pricing or the latest release cannot be in that corpus by construction.
The hard half now comes from the dataset.
"""

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent

# These web cases are hand-written, chosen so that **no** static
# scientific corpus inka jawab de hi na sake — live pricing, current limits,
# recent releases. Yahi wo axis hai jispe corpus definitionally khaali hai.
WEB_CASES = [
    "What is the current pricing of the Groq API per million tokens?",
    "What are the free tier rate limits on the Groq API right now?",
    "Which chat models are available on Groq today?",
    "What changed in the most recent LangGraph release?",
    "What is the context window of the newest Claude model?",
    "How much does OpenAI charge per million input tokens?",
    "Which vector database companies raised funding this year?",
    "What is the latest version of ChromaDB?",
]


def main() -> int:
    p = argparse.ArgumentParser(description="Generate SciFact routing scenarios")
    p.add_argument("--local", type=int, default=20, help="kitne local cases (qrels se)")
    p.add_argument("--web", type=int, default=8, help="kitne web cases")
    p.add_argument("--out", default=str(HERE / "scenarios_scifact.json"))
    p.add_argument("--seed", type=int, default=17, help="for reproducibility")
    p.add_argument(
        "--limit", type=int, default=0,
        help="wahi limit jo ingest me use ki thi — scenarios usi subset pe bane",
    )
    args = p.parse_args()

    from app.tools.beir_loader import (
        load_corpus,
        load_qrels,
        load_queries,
        load_query_verdicts,
    )

    # **Wahi limit jo ingest me di thi.** Warna scenarios poore corpus ke against
    # would be built against the full corpus while the index holds a subset, and
    # then a `local` case's gold document is simply not there. In the eval that
    # failure looks like *the grader being wrong*,
    # jabki galti mismatch ki hoti.
    #
    # (Because the subset is gold-first this happens to line up for limits >= 283
    # anyway, but leaving a mismatch to chance is not a design.)
    corpus_ids = {doc_id for doc_id, _, _ in load_corpus("scifact", limit=args.limit)}
    queries = load_queries("scifact")
    qrels = load_qrels("scifact", "test")
    # The answer-correctness label. Not present on every query — only the cases
    # that carry one get scored for answer quality; the rest run for routing only.
    verdicts = load_query_verdicts("scifact")

    # Sirf wo queries jinka **gold doc humare ingested corpus me hai**. Agar gold
    # document was never ingested, a "should stay local" label would be false —
    # the system does not have that answer.
    usable = [
        (qid, queries[qid], gold)
        for qid, gold in qrels.items()
        if qid in queries and any(d in corpus_ids for d in gold)
    ]
    if not usable:
        print("[build] ERROR: no qrel query matched the corpus")
        return 1

    random.Random(args.seed).shuffle(usable)
    picked = usable[: args.local]

    cases = []
    for i, (qid, text, gold) in enumerate(picked, start=1):
        case = {
            "id": i,
            "question": text,
            "expected_route": "local",
            "source_doc": gold[0],
            "gold_docs": gold,
            "why": "SciFact qrels mark this claim as supported by an ingested abstract.",
            "label_source": "beir-qrels",
            "hard": False,
        }
        # Dataset ka apna SUPPORT/CONTRADICT label, jahan wo maujood aur
        # and unambiguous. This is what makes it possible to measure whether the
        # answer was **right**, which neither routing nor groundedness tells you.
        if qid in verdicts:
            case["expected_verdict"] = verdicts[qid]
        cases.append(case)

    for j, q in enumerate(WEB_CASES[: args.web], start=len(cases) + 1):
        cases.append({
            "id": j,
            "question": q,
            "expected_route": "web",
            "source_doc": None,
            "why": "Live/product fact. SciFact is a static corpus of scientific abstracts.",
            "label_source": "hand-written",
            "hard": False,
        })

    out = {
        "_about": [
            "Routing eval for the BEIR SciFact corpus.",
            "",
            "`local` cases are NOT hand-labelled — they come from SciFact's own",
            "qrels. If the dataset says a claim is supported by abstract D, and D",
            "is in our index, the router should stay local. That removes the",
            "single-author bias the concepts-corpus eval admits to.",
            "",
            "`web` cases ARE hand-written, and that is worth stating. They were",
            "chosen so that no static scientific corpus could answer them - live",
            "pricing, current rate limits, recent releases. The easy half.",
            "",
            "Local cases carrying `expected_verdict` also have SciFact's own",
            "SUPPORT/CONTRADICT label. Those are the cases where answer",
            "*correctness* can be scored, not just routing and groundedness.",
            "Queries whose gold documents disagree with each other are skipped:",
            "on mixed evidence there is no honest right answer to score against.",
            "",
            "Regenerate with: python -m eval.build_scifact_scenarios --limit 500",
        ],
        "corpus": "scifact",
        "corpus_limit": args.limit,
        "cases": cases,
    }

    dest = Path(args.out)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[build] {len(cases)} cases ({args.local} local from qrels, "
          f"{min(args.web, len(WEB_CASES))} web hand-written) -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
