"""Extract a SUPPORT/CONTRADICT verdict from a generated answer, to score answer quality.

**Why this exists.** The eval measured three things: was the route right, was the
gold document retrieved, and was the answer grounded in whatever context it got.
None of them says whether the answer was *actually correct*. `RESULTS.md` names
the gap itself:

    "Reranking is not useless - it is aimed at the wrong metric here. It should
    help the *answer*, and this eval does not measure answer quality."

SciFact is a claim-verification dataset, so the gap can be closed **without an
LLM judge**: the dataset records whether the gold abstract supports or
contradicts each claim. All this module has to do is read what our answer said,
and the two get compared.

**Extraction is not judging, and the distinction matters.** An LLM judge is asked
"is this answer good?", which is the model's opinion standing in for a
measurement. Here the model is asked only for a *reading*: did this text call the
claim true or false? Right and wrong are decided by the dataset, not the model.

It is still the weakest link in the chain, and RESULTS.md says so — one misread
flips one case, and a misread is indistinguishable from a wrong answer in the
score.

`UNCLEAR` is kept separate rather than folded into `CONTRADICT`. An answer that
takes no position is a different thing from a wrong one, and collapsing them
would be the same "not measured vs scored zero" mistake this project keeps
avoiding.
"""

from langchain_core.prompts import ChatPromptTemplate

from app.config import get_llm

EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You read an answer and report what position it takes on a claim.\n"
            "You are NOT judging whether the answer is good, and NOT deciding "
            "whether the claim is true. Report only what the text says.\n\n"
            "Reply with exactly one word:\n"
            "SUPPORT   - the answer asserts the claim is true\n"
            "CONTRADICT - the answer asserts the claim is false, or states the opposite\n"
            "UNCLEAR   - the answer takes no position, hedges, or says it cannot tell\n\n"
            "No explanation. No punctuation. One word.",
        ),
        ("human", "Claim: {claim}\n\nAnswer:\n{answer}"),
    ]
)


def parse_verdict(raw: str) -> str:
    """Squeeze the model's output into three values, defensively.

    Same problem as `grade_documents.parse_verdict`, and for the same reason:
    however tight the prompt, a model sometimes returns a sentence.

    Order matters here too. `CONTRADICT` is checked first because a phrase like
    "does not support" contains the substring "support" — checking `SUPPORT`
    first would read that answer backwards.
    """
    v = (raw or "").strip().upper()
    if "CONTRADICT" in v or "NOT SUPPORT" in v or "DOES NOT" in v:
        return "CONTRADICT"
    if "UNCLEAR" in v or "CANNOT" in v:
        return "UNCLEAR"
    if "SUPPORT" in v:
        return "SUPPORT"
    return "UNCLEAR"


def extract_verdict(claim: str, answer: str) -> str:
    """`"SUPPORT" | "CONTRADICT" | "UNCLEAR"`.

    temperature 0, for the reason the grader uses it: if one answer produces two
    different verdicts across runs, the metric is worthless.
    """
    if not (answer or "").strip():
        return "UNCLEAR"
    chain = EXTRACT_PROMPT | get_llm(temperature=0.0)
    return parse_verdict(chain.invoke({"claim": claim, "answer": answer}).content)
