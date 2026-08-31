"""`grade_documents` node — project ka core #1.

LLM binary relevance grader. Answer generate karne se **pehle** ye decide karta
hai ki retrieved context sach me sawaal ka jawab de sakta hai ya nahi.

Yahi naive RAG se asli difference hai. Similarity search hamesha k results deta
hai — chahe corpus me kuch relevant ho ya na ho — aur low similarity score kabhi
LLM tak pahunchta hi nahi. Ye node wo faisla explicit banata hai.
"""

from langchain_core.prompts import ChatPromptTemplate

from app.config import get_llm
from app.schemas.crag_state import CRAGState

GRADER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a grader assessing whether retrieved documents are relevant to a "
            "user question.\n"
            "Answer with a single word: 'yes' if the documents contain information that "
            "helps answer the question, otherwise 'no'.\n"
            "Do not explain. Do not add punctuation. Output only 'yes' or 'no'.",
        ),
        ("human", "Question: {question}\n\nRetrieved documents:\n{documents}"),
    ]
)


def parse_verdict(raw: str) -> str:
    """LLM output ko "yes"/"no" me squeeze karo — defensively.

    Prompt kitna bhi tight ho, model kabhi kabhi "Yes." ya "yes, because..." de
    deta hai. Agar exact match pe depend karein to wo case silently `no` ban
    jaata aur bewajah web call trigger hota.

    Order matter karta hai: pehle `no` check karo. "no" ka substring check `yes`
    se pehle isliye ki "yes" string "no" me nahi milti, lekin ek explanation me
    dono aa sakte hain — aur us confused case me safe default `no` hai (ek extra
    web call, hallucination nahi).
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
        # Kuch retrieve hi nahi hua — grade karne ko kuch nahi. Seedha fallback.
        return {
            "relevance_score": "no",
            "logs": ["grade_documents -> no (koi document retrieve nahi hua)"],
        }

    # temperature 0 — routing deterministic hona chahiye. Ek hi query pe kabhi
    # local, kabhi web jaana debug karna aur demo karna dono impossible bana deta.
    chain = GRADER_PROMPT | get_llm(temperature=0.0)
    raw = chain.invoke(
        {
            "question": state["question"],
            "documents": "\n\n---\n\n".join(documents),
        }
    ).content

    score = parse_verdict(raw)

    return {
        "relevance_score": score,
        "logs": [f"grade_documents -> {score} (raw={raw.strip()[:40]!r})"],
    }
