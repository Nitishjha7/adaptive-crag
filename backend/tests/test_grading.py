"""Grader ka defensive output parsing.

Prompt kitna bhi tight ho, LLM kabhi kabhi extra text de deta hai. Agar exact
match pe depend karein to har aisa case chupke se `no` ban jaata aur bewajah web
call trigger hota — ya usse bura, `yes` ban jaata.
"""

import pytest

from app.nodes.grade_documents import parse_verdict


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("yes", "yes"),
        ("Yes.", "yes"),
        ("  YES  ", "yes"),
        ("yes, the documents cover this", "yes"),
        ("no", "no"),
        ("No.", "no"),
        ("n", "no"),
        ("", "no"),
        (None, "no"),
        # Confused output -> safe default `no`: ek extra web call, hallucination nahi
        ("I cannot determine that", "no"),
        ("no, the documents do not say yes to this", "no"),
    ],
)
def test_parse_verdict(raw, expected):
    assert parse_verdict(raw) == expected
