"""SciFact ke qrels se routing eval scenarios generate karo.

    python -m eval.build_scifact_scenarios --local 20 --out eval/scenarios_scifact.json

**Ye script kyun exist karta hai.** `scenarios.json` (concepts corpus wala) me
maine documents bhi likhe the aur labels bhi — RESULTS.md khud isko structural
bias bolta hai: *"one author writing both the corpus and the eval is its own
bias — the honest fix is someone else writing cases."*

Yahan wo fix ho jaata hai. `local` cases ke labels **SciFact ke apne qrels** se
aate hain: agar dataset kehta hai ki query Q ka jawab doc D me hai, aur D humne
ingest kiya hai, to Q ko local jaana chahiye. Maine ye label nahi banaya.

`web` cases abhi bhi haath se likhe hain, aur **ye maan lena zaroori hai** — par
wo aasan hissa hai: SciFact 2020-era scientific abstracts hain, to "aaj ka
pricing" ya "latest release" type sawaal us corpus me ho hi nahi sakte. Mushkil
half (local) ab dataset se aata hai.
"""

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent

# Ye web cases haath se likhe hain. Inhe aise chuna hai ki **koi bhi** static
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
    p.add_argument("--seed", type=int, default=17, help="reproducibility ke liye")
    p.add_argument(
        "--limit", type=int, default=0,
        help="wahi limit jo ingest me use ki thi — scenarios usi subset pe bane",
    )
    args = p.parse_args()

    from app.tools.beir_loader import load_corpus, load_qrels, load_queries

    # **Wahi limit jo ingest me di thi.** Warna scenarios poore corpus ke against
    # bante hain jabki index me subset hai — aur phir ek `local` case ka gold doc
    # index me hai hi nahi. Wo failure eval me *grader ki galti* jaisa dikhta,
    # jabki galti mismatch ki hoti.
    #
    # (Gold-first subset ki wajah se limit >= 283 pe ye vaise bhi match karta
    # hai, par mismatch ko design pe chhodna theek nahi.)
    corpus_ids = {doc_id for doc_id, _, _ in load_corpus("scifact", limit=args.limit)}
    queries = load_queries("scifact")
    qrels = load_qrels("scifact", "test")

    # Sirf wo queries jinka **gold doc humare ingested corpus me hai**. Agar gold
    # doc ingest hi nahi hua, to "local jaana chahiye" label jhootha hoga — system
    # ke paas wo jawab hai hi nahi.
    usable = [
        (qid, queries[qid], gold)
        for qid, gold in qrels.items()
        if qid in queries and any(d in corpus_ids for d in gold)
    ]
    if not usable:
        print("[build] ERROR: koi qrel query corpus se match nahi hui")
        return 1

    random.Random(args.seed).shuffle(usable)
    picked = usable[: args.local]

    cases = []
    for i, (qid, text, gold) in enumerate(picked, start=1):
        cases.append({
            "id": i,
            "question": text,
            "expected_route": "local",
            "source_doc": gold[0],
            "gold_docs": gold,
            "why": "SciFact qrels mark this claim as supported by an ingested abstract.",
            "label_source": "beir-qrels",
            "hard": False,
        })

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
