"""`validate_guardrails` node — the graph's last safety net.

The `generate` prompt says "answer only from the context". That is a request,
not a guarantee — a model can still slip in its training knowledge. This node
takes a second, independent look at the answer: is every claim actually
supported by the context, and is any PII leaking?

It fills `final_output`, which is the field the API returns.
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
        "guardrail_passed": result.passed,
        "logs": [f"validate_guardrails -> pass={result.passed} ({result.reason})"],
    }
