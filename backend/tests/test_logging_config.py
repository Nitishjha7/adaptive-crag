"""JSON log formatting — no real LLM or network involved, just a formatter."""

import json
import logging

from app.logging_config import JsonFormatter


def _make_record(msg="hello", extra=None, exc_info=None):
    record = logging.LogRecord(
        name="app.main",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return record


def test_format_produces_valid_json_with_core_fields():
    formatted = JsonFormatter().format(_make_record("query completed"))
    payload = json.loads(formatted)

    assert payload["message"] == "query completed"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.main"
    assert "timestamp" in payload


def test_extra_fields_ride_through_untouched():
    """route/relevance_score/guardrail_passed — the fields this project's
    query-completion log line actually attaches — must survive formatting
    rather than being silently dropped."""
    formatted = JsonFormatter().format(
        _make_record(
            "query completed",
            extra={"route": "web_search", "relevance_score": "no", "guardrail_passed": True},
        )
    )
    payload = json.loads(formatted)

    assert payload["route"] == "web_search"
    assert payload["relevance_score"] == "no"
    assert payload["guardrail_passed"] is True


def test_exception_info_is_captured():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record("failed", exc_info=sys.exc_info())

    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]
