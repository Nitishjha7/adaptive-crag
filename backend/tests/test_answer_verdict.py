"""Defensive parsing of the answer-verdict extraction.

The same problem as `grade_documents.parse_verdict`, on a new axis: the model is
asked for one word and sometimes returns a sentence.

There is an extra trap here that the grader did not have: **a phrase like "does
not support" contains the substring "support".** If `SUPPORT` were checked first,
"the answer does not support the claim" would be read as `SUPPORT` and the metric
would quietly invert. Hence `CONTRADICT` is checked first, and these tests lock
that order in.

`UNCLEAR` is not merged into `CONTRADICT`. An answer that takes no position is a
different thing from a wrong one, and counting them together would be the same
"not measured vs scored zero" mistake this project keeps avoiding.
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
        # Took no position -> UNCLEAR, not CONTRADICT
        ("", "UNCLEAR"),
        (None, "UNCLEAR"),
        ("I cannot tell from this answer", "UNCLEAR"),
        # The real trap: the verdict is inverted despite the "support" substring
        ("the answer does not support the claim", "CONTRADICT"),
        ("NOT SUPPORT", "CONTRADICT"),
    ],
)
def test_parse_verdict(raw, expected):
    assert parse_verdict(raw) == expected


def test_contradict_is_checked_before_support():
    """Order-dependence made explicit — the bug that would quietly invert the metric.

    The grader's parser carries the same lesson (`no` before `yes`), and for the
    same reason in both places: one verdict's name hides inside the other's text.
    """
    assert parse_verdict("does not support") == "CONTRADICT"
    assert parse_verdict("supports") == "SUPPORT"
