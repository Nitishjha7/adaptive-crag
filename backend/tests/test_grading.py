"""The grader's defensive output parsing.

No matter how tight the prompt, the LLM sometimes returns extra text around
the verdict. If parsing relied on an exact match, every such case would
quietly become `no` and trigger a pointless web call — or worse, become `yes`.
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
        # Confused output -> safe default `no`: one extra web call, not a hallucination
        ("I cannot determine that", "no"),
        ("no, the documents do not say yes to this", "no"),
    ],
)
def test_parse_verdict(raw, expected):
    assert parse_verdict(raw) == expected


# --- web snippet se URL extraction -----------------------------------------

import pytest as _pytest  # noqa: E402

from app.nodes.web_search_fallback import extract_urls  # noqa: E402


@_pytest.mark.parametrize(
    "snippets,expected",
    [
        (["text\n[source: https://a.com]"], ["https://a.com"]),
        # dedupe, order preserve
        (
            ["a\n[source: https://x.com]", "b\n[source: https://x.com]"],
            ["https://x.com"],
        ),
        # URL na ho to snippet skip ho jaye, crash na kare
        (["plain text with no marker"], []),
        ([], []),
    ],
)
def test_extract_urls(snippets, expected):
    assert extract_urls(snippets) == expected
