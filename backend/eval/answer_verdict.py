"""Generated answer se SUPPORT/CONTRADICT verdict nikalo — answer quality naapne ke liye.

**Ye kyun exist karta hai.** Ab tak eval teen cheezein naapta tha: route sahi
tha ya nahi, gold document retrieve hua ya nahi, aur answer apne context se
grounded tha ya nahi. Teeno me se **koi bhi** ye nahi batata ki answer *sach me
sahi* tha. `RESULTS.md` khud ye gap likhta hai:

    "Reranking is not useless - it is aimed at the wrong metric here. It should
    help the *answer*, and this eval does not measure answer quality."

SciFact claim-verification dataset hai, to yahan wo gap bharna mumkin hai **bina
LLM-judge ke**: dataset khud batata hai ki gold abstract claim ko support karta
hai ya contradict. Hume sirf itna nikalna hai ki hamare answer ne kya kaha, aur
dono milane hain.

**Extraction judging nahi hai — aur ye farak zaroori hai.** LLM-judge se poochha
jaata hai "kya ye answer accha hai", jo uski apni raay hoti hai. Yahan LLM se
sirf ek **reading** maangi jaati hai: is text ne claim ko sach kaha ya jhooth?
Sahi-galat ka faisla dataset karta hai, model nahi. Phir bhi ye chain ki sabse
kamzor kadi hai aur RESULTS.md me aise hi likha hai — ek misread aur case galat
score ho jaata hai.

`UNCLEAR` alag se rakha hai, `CONTRADICT` me nahi milaya. Answer jo koi stand hi
na le, wo galat answer se alag cheez hai — aur dono ko ek me milana wahi
"measure nahi hua vs zero" wali galti hai jisse ye project bachta aaya hai.
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
    """Model output ko teen values me squeeze karo — defensively.

    `grade_documents.parse_verdict` jaisa hi, aur usi wajah se: prompt kitna bhi
    tight ho, model kabhi "SUPPORT." ya "The answer supports..." de deta hai.

    Order yahan bhi matter karta hai. `CONTRADICT` pehle check hota hai kyunki
    "does not support" jaise jumle me "support" substring maujood hai — agar
    `SUPPORT` pehle check karein to ulta jawab nikal aayega.
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

    temperature 0 — wahi wajah jo grader me hai: ek hi answer pe do baar do alag
    verdict aaye to metric hi bekaar hai.
    """
    if not (answer or "").strip():
        return "UNCLEAR"
    chain = EXTRACT_PROMPT | get_llm(temperature=0.0)
    return parse_verdict(chain.invoke({"claim": claim, "answer": answer}).content)
