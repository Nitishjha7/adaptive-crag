"""`generate` node — verified context se final answer.

Dono branches (local-hit aur web-fallback) yahin merge hote hain. Ye node sirf
`state["documents"]` padhta hai — usse farak nahi padta ki wo chunks Chroma se
aaye ya Tavily se. Isliye ek hi prompt maintain karna padta hai, do nahi.
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
        # Defensive: retrieval khaali aayi (empty collection / ingestion nahi chali).
        # Yahan LLM call karna paisa waste hai aur model ko apni training knowledge
        # se bolne ka nyota — jo poore project ke khilaf hai.
        return {
            "generation": (
                "No context was available to answer this question — the knowledge base "
                "returned nothing and the web fallback produced no results."
            ),
            "logs": ["generate -> skipped (no documents in state)"],
        }

    context = "\n\n---\n\n".join(documents)
    # temperature 0 — answer context se grounded hona chahiye, creative nahi.
    chain = GENERATE_PROMPT | get_llm(temperature=0.0)
    answer = chain.invoke({"context": context, "question": question}).content.strip()

    return {
        "generation": answer,
        "logs": [f"generate -> {len(answer)} chars from {len(documents)} docs"],
    }
