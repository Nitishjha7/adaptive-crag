"""Answer-verdict extraction ka defensive parsing.

Wahi problem jo `grade_documents.parse_verdict` me hai, ek naye axis pe. Model se
ek word maanga jaata hai aur wo kabhi kabhi jumla de deta hai.

Yahan ek extra trap hai jo grader me nahi tha: **"does not support" jaise phrase
me "support" substring maujood hai.** Agar `SUPPORT` ka check pehle chale, to
"the answer does not support the claim" ulta `SUPPORT` padh liya jaayega — aur
metric chup-chaap ulti ho jaayegi. Isiliye `CONTRADICT` pehle check hota hai,
aur ye tests wahi order lock karte hain.

`UNCLEAR` ko `CONTRADICT` me merge nahi kiya gaya. Jo answer koi stand hi na le,
wo galat answer se alag cheez hai — dono ko ek ginna wahi "not measured vs
scored zero" wali galti hogi jisse ye project bachta aaya hai.
"""

import pytest

from eval.answer_verdict import parse_verdict


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("SUPPORT", "SUPPORT"),
        ("support", "SUPPORT"),
        ("  SUPPORT  ", "SUPPORT"),
        ("SUPPORT.", "SUPPORT"),
        ("The answer supports the claim", "SUPPORT"),
        ("CONTRADICT", "CONTRADICT"),
        ("contradict", "CONTRADICT"),
        ("CONTRADICT.", "CONTRADICT"),
        ("UNCLEAR", "UNCLEAR"),
        # Stand hi nahi liya -> UNCLEAR, CONTRADICT nahi
        ("", "UNCLEAR"),
        (None, "UNCLEAR"),
        ("I cannot tell from this answer", "UNCLEAR"),
        # Asli trap: "support" substring ke bawajood verdict ulta hai
        ("the answer does not support the claim", "CONTRADICT"),
        ("NOT SUPPORT", "CONTRADICT"),
    ],
)
def test_parse_verdict(raw, expected):
    assert parse_verdict(raw) == expected


def test_contradict_is_checked_before_support():
    """Order-dependence explicit — ye wahi bug hai jo chup-chaap metric ulti karta.

    Grader wale parser me bhi yahi sabak hai (`no` pehle, `yes` baad me), aur
    dono jagah wajah ek hi hai: ek verdict ka naam doosre ke text me chhupa
    baitha hai.
    """
    assert parse_verdict("does not support") == "CONTRADICT"
    assert parse_verdict("supports") == "SUPPORT"
