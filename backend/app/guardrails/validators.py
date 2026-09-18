"""Output validation — groundedness + PII.

**Why not the Guardrails AI library:** its hub-based validator downloads and
version pinning were the single largest time sink in this project, and what
matters is not the name of a library but understanding *why a final answer should
be verified, and how*. Two small checks do that job, with zero
extra dependency.

Two checks:

1. **Groundedness (LLM)** — is every claim in the answer actually supported by
   the context? This is the real hallucination net. The `generate` prompt
   already says "only from the context", but a prompt is a request, not a
   guarantee — a model can still add from its training knowledge. This is a
   second, *independent* look at what came out.

2. **PII (regex)** — email / phone / card / SSN patterns. Regex on purpose, not
   an LLM: PII detection should be deterministic, and another LLM call adds
   latency without adding trust.

No toxicity check, deliberately. The inputs are a controlled corpus plus search
snippets, and without a proper classifier an LLM-based "is this toxic" check
would be decoration — better to leave it out than to claim it and not verify it.
"""

import re
from dataclasses import dataclass, field
from typing import List

from langchain_core.prompts import ChatPromptTemplate

from app.config import get_llm

GROUNDEDNESS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are checking whether an answer is fully supported by the given context.\n"
            "Answer 'yes' only if every factual claim in the answer can be verified from "
            "the context. Answer 'no' if the answer adds any fact that is not in the "
            "context.\n"
            "An answer that simply says the context is insufficient counts as 'yes'.\n"
            "Output only 'yes' or 'no'. Do not explain.",
        ),
        ("human", "Context:\n{context}\n\nAnswer:\n{answer}"),
    ]
)

# High-confidence patterns only. A loose regex (any 10-digit number, say) fires
# false positives on almost every technical answer.
PII_PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_intl": re.compile(r"\+\d{1,3}[\s-]?\d{6,12}\b"),
}


@dataclass
class ValidationResult:
    """A simple result object for the node."""

    validated_output: str
    passed: bool
    grounded: bool
    pii_found: List[str] = field(default_factory=list)
    reason: str = ""


def check_pii(text: str) -> List[str]:
    """Names of the PII types found. Never the values — writing those into a log
    is the very leak this is trying to prevent."""
    return [name for name, pattern in PII_PATTERNS.items() if pattern.search(text)]


def check_groundedness(answer: str, context: List[str]) -> bool:
    """A small temperature-0 LLM call. Fails open, not closed.

    If the check itself crashes, blocking the answer would be wrong — the answer
    was already built from verified context. So an exception means `True` (assume
    grounded) and a note in the log. Failing closed would let one flaky network
    call turn the whole system into "I cannot tell you anything".
    """
    if not context:
        return True  # there was no context at all — `generate` will have said so

    chain = GROUNDEDNESS_PROMPT | get_llm(temperature=0.0)
    verdict = chain.invoke(
        {"context": "\n\n---\n\n".join(context), "answer": answer}
    ).content

    # The same defensive parsing the grader uses.
    from app.nodes.grade_documents import parse_verdict

    return parse_verdict(verdict) == "yes"


def validate_answer(answer: str, context: List[str], question: str = "") -> ValidationResult:
    """Final scan of the answer. A failure **flags, it does not block**.

    Deliberately non-destructive: an ungrounded answer gets a clear warning
    attached, not suppressed. Showing a hallucination *being caught* is more
    convincing in a demo than making it disappear — and "this may be wrong" serves
    the user better than a blank screen.

    PII is different: it gets redacted, because flagging it while still displaying
    it is the leak.
    """
    pii_found = check_pii(answer)
    output = answer

    if pii_found:
        for name in pii_found:
            output = PII_PATTERNS[name].sub(f"[REDACTED:{name}]", output)

    try:
        grounded = check_groundedness(output, context)
        ground_note = ""
    except Exception as exc:  # noqa: BLE001 — fails open, see the docstring above
        grounded = True
        ground_note = f" (groundedness check did not run: {type(exc).__name__})"

    if not grounded:
        output = (
            "⚠️ This answer could not be fully verified against the retrieved context — "
            "treat it with caution.\n\n" + output
        )

    reasons = []
    if not grounded:
        reasons.append("ungrounded")
    if pii_found:
        reasons.append(f"pii={','.join(pii_found)}")

    return ValidationResult(
        validated_output=output,
        passed=grounded and not pii_found,
        grounded=grounded,
        pii_found=pii_found,
        reason=("; ".join(reasons) or "clean") + ground_note,
    )
