"""`transform_query` node — natural language question -> keyword search query.

Sirf fallback path pe chalta hai. User conversational likhta hai ("can you help
me understand how X works"); search engine ko keywords chahiye. Filler hatane se
wahi terms bachte hain jo documents ke beech farak karte hain.

Ye ek chhota LLM call hai — poore answer generate karne ke muqable sasta.
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

    # Model kabhi khaali ya bakwaas lauta de to original question hi behtar hai —
    # ek kharab rewrite se poora fallback path bekaar ho jaata hai.
    rewritten = raw if raw else question

    return {
        "transformed_query": rewritten,
        "logs": [f"transform_query -> {rewritten!r}"],
    }
