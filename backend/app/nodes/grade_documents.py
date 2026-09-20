"""`grade_documents` node — the core of the project.

An LLM binary relevance grader. **Before** anything is generated, this decides
whether the retrieved context can actually answer the question.

This is the real difference from naive RAG. Similarity search always returns k
results whether or not anything relevant exists, and a low similarity score
never reaches the LLM. This node makes that judgement explicit.
"""

from langchain_core.prompts import ChatPromptTemplate

from app.config import get_llm
from app.schemas.crag_state import CRAGState

GRADER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a grader deciding whether retrieved documents are worth "
            "answering from.\n"
            "Say 'yes' if they mention the subject of the question, even only "
            "partially - a partial answer from the right source beats a web "
            "search.\n"
            "Say 'no' only if they are about an entirely different subject, or "
            "if the question needs current facts - prices, releases, dates - "
            "that static documents cannot hold.\n"
            "Output only 'yes' or 'no'. No explanation, no punctuation.",
        ),
        ("human", "Question: {question}\n\nRetrieved documents:\n{documents}"),
    ]
)


def parse_verdict(raw: str) -> str:
    """Squeeze the model's output into "yes"/"no", defensively.

    However tight the prompt, a model occasionally returns "Yes." or
    "yes, because...". Matching exactly would silently turn those into `no` and
    trigger a pointless web call.

    Order matters: check `no` first. "yes" never appears inside "no", but an
    explanation can contain both — and in that confused case the safe default is
    `no` (one extra web call, not a hallucination).
    """
    v = (raw or "").strip().lower()
    if v.startswith("no") or v == "n":
        return "no"
    if "yes" in v:
        return "yes"
    return "no"


def run(state: CRAGState) -> dict:
    documents = state.get("documents") or []

    if not documents:
        # Nothing was retrieved, so there is nothing to grade. Straight to fallback.
        return {
            "relevance_score": "no",
            "logs": ["grade_documents -> no (nothing was retrieved)"],
        }

    # temperature 0, but that is not a determinism guarantee: on a
    # mixture-of-experts model the expert routing still varies, and this grader
    # was observed returning yes and no for the same question and the same
    # chunks. Groq ignores `seed`, so the defence is the prompt above - a
    # criterion the model cannot read two ways is what makes the verdict stable,
    # not the sampling parameters.
    chain = GRADER_PROMPT | get_llm(temperature=0.0)
    raw = chain.invoke(
        {
            "question": state["question"],
            # All chunks in one call. Per-chunk grading would be more granular but
            # costs k times the LLM calls, and the whole cost argument rests on
            # call counts. One consequence worth knowing: joining them means
            # ordering is invisible to the grader, so reranking could
            # not move the routing numbers (see eval/RESULTS.md).
            "documents": "\n\n---\n\n".join(documents),
        }
    ).content

    score = parse_verdict(raw)

    return {
        "relevance_score": score,
        "logs": [f"grade_documents -> {score} (raw={raw.strip()[:40]!r})"],
    }
