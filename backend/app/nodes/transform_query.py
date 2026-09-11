"""`transform_query` node — natural language question -> keyword search query.

Runs only on the fallback path. People write conversationally ("can you help me
understand how X works"); search engines want keywords. Dropping the filler
leaves the terms that actually discriminate between documents.

This is a small LLM call — cheap next to generating a whole answer.
"""

from langchain_core.prompts import ChatPromptTemplate

from app.config import get_llm
from app.schemas.crag_state import CRAGState

REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Rewrite the user question into a concise, keyword-focused web search query.\n"
            "Keep proper nouns, product names, and technical terms exactly as written.\n"
            "Drop conversational filler.\n"
            "Return only the rewritten query — no quotes, no preamble, no explanation.",
        ),
        ("human", "{question}"),
    ]
)


def run(state: CRAGState) -> dict:
    question = state["question"]

    raw = (REWRITE_PROMPT | get_llm(temperature=0.0)).invoke(
        {"question": question}
    ).content.strip().strip('"')

    # If the model returns nothing usable, the original question is the better
    # query — one bad rewrite wastes the entire fallback path.
    rewritten = raw if raw else question

    return {
        "transformed_query": rewritten,
        "logs": [f"transform_query -> {rewritten!r}"],
    }
