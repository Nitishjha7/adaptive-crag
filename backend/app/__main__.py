"""CLI harness — graph ko FastAPI ke bina chala ke dekhne ke liye.

    python -m app "why does chunk overlap matter?"
    python -m app                  # default demo query

The smallest possible debugging loop: one process, one invoke, the full trace
printed.
"""

import sys

from app.graph.build_graph import build_crag_graph
from app.schemas.crag_state import initial_state

DEFAULT_QUESTION = "Why does chunk overlap matter when splitting documents?"


def main() -> int:
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION

    graph = build_crag_graph()
    final = graph.invoke(initial_state(question))

    print(f"\nQ: {question}\n")
    print("--- trace " + "-" * 50)
    for line in final.get("logs", []):
        print(f"  {line}")
    print("--- answer " + "-" * 49)
    # `final_output` is only filled once guardrails run, so fall back to the
    # raw generation.
    print(final.get("final_output") or final.get("generation") or "(none)")
    print("--- meta " + "-" * 51)
    print(f"  source_type     : {final.get('source_type')}")
    print(f"  sources         : {', '.join(final.get('sources') or []) or '(none)'}")
    print(f"  relevance_score : {final.get('relevance_score') or '(Phase 3)'}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
