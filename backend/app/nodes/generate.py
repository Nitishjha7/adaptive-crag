"""`generate` node — the final answer, from verified context.

Both branches (local hit and web fallback) merge here. This node reads only
`state["documents"]` and does not care whether those chunks came from Chroma or
from a search API, so there is one prompt to maintain rather than two.
"""

from langchain_core.prompts import ChatPromptTemplate

from app.config import get_llm
from app.schemas.crag_state import CRAGState

GENERATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a precise question-answering assistant.\n"
            "Answer the question using ONLY the provided context. Do not use prior "
            "knowledge, and do not add facts that are not in the context.\n"
            "If the context does not contain enough information to answer, say exactly "
            "that the provided context does not cover it — do not guess.\n"
            "Be concise: two to five sentences.",
        ),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)


def run(state: CRAGState) -> dict:
    documents = state.get("documents") or []
    question = state["question"]

    if not documents:
        # Defensive: retrieval came back empty (empty collection, or ingestion
        # never ran). Calling the LLM here would waste a call and invite the model
        # to answer from its training knowledge, which is what this project exists
        # to prevent.
        return {
            "generation": (
                "No context was available to answer this question — the knowledge base "
                "returned nothing and the web fallback produced no results."
            ),
            "logs": ["generate -> skipped (no documents in state)"],
        }

    context = "\n\n---\n\n".join(documents)
    memory_note = state.get("memory_note") or ""
    if memory_note:
        context = f"{context}\n\n---\n\n{memory_note}"

    # temperature 0 — the answer should be grounded in the context, not creative.
    chain = GENERATE_PROMPT | get_llm(temperature=0.0)
    answer = chain.invoke({"context": context, "question": question}).content.strip()

    return {
        "generation": answer,
        "logs": [f"generate -> {len(answer)} chars from {len(documents)} docs"],
    }
