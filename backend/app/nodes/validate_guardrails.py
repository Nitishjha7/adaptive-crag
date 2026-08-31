"""`validate_guardrails` node — graph ka aakhri safety net.

`generate` ka prompt bolta hai "sirf context se jawab do". Wo ek guzarish hai,
guarantee nahi — model chupke se apni training knowledge daal sakta hai. Ye node
us answer par ek doosri, independent nazar hai: kya har claim sach me context se
supported hai, aur kya koi PII leak ho raha hai.

Yahi node `final_output` bharta hai — wahi field API return karti hai.
"""

from app.guardrails.validators import validate_answer
from app.schemas.crag_state import CRAGState


def run(state: CRAGState) -> dict:
    generation = state.get("generation") or ""
    documents = state.get("documents") or []

    result = validate_answer(
        answer=generation,
        context=documents,
        question=state.get("question", ""),
    )

    return {
        "final_output": result.validated_output,
        "logs": [f"validate_guardrails -> pass={result.passed} ({result.reason})"],
    }
