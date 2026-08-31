"""Output validation — groundedness + PII.

**Guardrails AI library kyun nahi:** us library ka hub-based validator download
aur version pinning is project ka sabse bada time-sink hai, aur jo cheez interview
me matter karti hai wo library ka naam nahi — ye samajh hai ki *final answer ko
verify kyun karna chahiye aur kaise*. Do chhote checks wahi kaam karte hain, zero
extra dependency ke saath.

Do checks:

1. **Groundedness (LLM)** — kya answer ka har claim diye gaye context se supported
   hai? Ye asli hallucination net hai. `generate` ka prompt already "sirf context
   se" bolta hai, lekin prompt ek guzarish hai, guarantee nahi — model apni
   training knowledge se chupke se add kar sakta hai. Ye check us par ek doosri,
   *independent* nazar hai.

2. **PII (regex)** — email / phone / card / SSN patterns. Deliberately regex hai,
   LLM nahi: PII detection me deterministic hona chahiye, aur ek aur LLM call
   latency badhata hai bina kisi bharose ke faayde ke.

Toxicity check jaan-boojh ke chhoda hai: input controlled corpus + search snippets
hai, aur bina ek proper classifier ke "toxic" ka LLM-based check dikhawa hota —
uska naam lena aur usse verify na karna, dono me se doosra behtar hai.
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

# Sirf high-confidence patterns. Loose regex (jaise koi bhi 10-digit number)
# har technical answer me false positive deta hai.
PII_PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_intl": re.compile(r"\+\d{1,3}[\s-]?\d{6,12}\b"),
}


@dataclass
class ValidationResult:
    """Node ke liye ek simple result object."""

    validated_output: str
    passed: bool
    grounded: bool
    pii_found: List[str] = field(default_factory=list)
    reason: str = ""


def check_pii(text: str) -> List[str]:
    """Mile hue PII types ke naam. Values kabhi return nahi karte — unhe log me
    likhna wahi leak hai jise rokne ki koshish kar rahe hain."""
    return [name for name, pattern in PII_PATTERNS.items() if pattern.search(text)]


def check_groundedness(answer: str, context: List[str]) -> bool:
    """Ek chhota temperature-0 LLM call. Fail-open, fail-closed nahi.

    Agar ye check hi crash ho jaye to answer block karna galat hai — wo already
    verified context se bana hai. Isliye exception pe `True` (grounded maan lo)
    aur node log me note. Fail-closed hone se ek flaky network call poore system
    ko "kuch nahi bata sakta" bana deta.
    """
    if not context:
        return True  # kuch context hi nahi tha — `generate` ne already bol diya hoga

    chain = GROUNDEDNESS_PROMPT | get_llm(temperature=0.0)
    verdict = chain.invoke(
        {"context": "\n\n---\n\n".join(context), "answer": answer}
    ).content

    # Wahi defensive parsing jo grader me hai.
    from app.nodes.grade_documents import parse_verdict

    return parse_verdict(verdict) == "yes"


def validate_answer(answer: str, context: List[str], question: str = "") -> ValidationResult:
    """Final answer scan. Fail hone pe answer **block nahi hota, flag hota hai**.

    v1 me deliberately non-destructive: ungrounded answer ke saath ek saaf warning
    jodi jaati hai, use chhupaya nahi jaata. Demo me hallucination *pakda gaya*
    dikhana usse gayab kar dene se zyada convincing hai — aur user ke liye bhi
    "ye shayad galat hai" khaali screen se behtar hai.

    PII alag baat hai — wo redact hota hai, kyunki flag karke dikhana leak hi hai.
    """
    pii_found = check_pii(answer)
    output = answer

    if pii_found:
        for name in pii_found:
            output = PII_PATTERNS[name].sub(f"[REDACTED:{name}]", output)

    try:
        grounded = check_groundedness(output, context)
        ground_note = ""
    except Exception as exc:  # noqa: BLE001 — fail-open, upar wali docstring dekh
        grounded = True
        ground_note = f" (groundedness check nahi chal paaya: {type(exc).__name__})"

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
