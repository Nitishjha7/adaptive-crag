"""Output validation — groundedness flagging aur PII redaction."""

import pytest

from app.guardrails.validators import check_pii, validate_answer


class TestPII:
    def test_email_redacted(self):
        result = validate_answer("Contact nitish@example.com", context=[], question="")
        assert "nitish@example.com" not in result.validated_output
        assert "[REDACTED:email]" in result.validated_output
        assert result.pii_found == ["email"]
        assert not result.passed

    def test_clean_text_untouched(self):
        text = "Chunk overlap keeps boundary sentences retrievable."
        assert check_pii(text) == []

    def test_technical_text_is_not_a_false_positive(self):
        """Regex tight rakhne ka test. Loose pattern (koi bhi lamba number) har
        technical answer pe trip karta — dimensions, chunk sizes, version numbers."""
        text = "The model produces 384-dimensional vectors with chunk size 800 and overlap 100."
        assert check_pii(text) == []


class TestGroundedness:
    def test_ungrounded_answer_is_flagged_not_hidden(self, fake_llm):
        """Answer chhupaya nahi jaata — warning ke saath dikhaya jaata hai.

        Hallucination *pakda gaya* dikhna usse gayab kar dene se zyada useful hai,
        aur user ke liye "ye shayad galat hai" khaali screen se behtar hai.
        """
        fake_llm.grounded = "no"

        result = validate_answer("Some claim.", context=["unrelated context"], question="")

        assert not result.grounded
        assert not result.passed
        assert "Some claim." in result.validated_output, "original answer chhupana nahi chahiye"
        assert result.validated_output.startswith("\u26a0\ufe0f")

    def test_grounded_answer_passes_through_unchanged(self, fake_llm):
        fake_llm.grounded = "yes"
        answer = "Overlap keeps boundary sentences retrievable."

        result = validate_answer(answer, context=["some context"], question="")

        assert result.passed
        assert result.validated_output == answer

    def test_check_failure_fails_open(self, monkeypatch):
        """Check khud crash ho jaye to answer block nahi hona chahiye.

        Wo already verified context se bana hai. Fail-closed hone se ek flaky
        network call poore system ko "kuch nahi bata sakta" bana deta.
        """
        import app.guardrails.validators as validators

        def _boom(answer, context):
            raise RuntimeError("groq unreachable")

        monkeypatch.setattr(validators, "check_groundedness", _boom)

        result = validate_answer("A normal answer.", context=["ctx"], question="")

        assert result.passed, "infra error pe answer block nahi hona chahiye"
        assert result.validated_output == "A normal answer."
        assert "nahi chal paaya" in result.reason

    def test_no_context_is_trivially_grounded(self, fake_llm):
        """Context hi nahi tha -- `generate` already bol chuka hoga ki wo nahi jaanta."""
        result = validate_answer("I don't have enough context.", context=[], question="")
        assert result.grounded
