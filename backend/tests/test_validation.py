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
        technical answer — dimensions, chunk sizes, version numbers."""
        text = "The model produces 384-dimensional vectors with chunk size 800 and overlap 100."
        assert check_pii(text) == []


class TestGroundedness:
    def test_ungrounded_answer_is_flagged_not_hidden(self, fake_llm):
        """The answer is not hidden — it is shown with a warning attached.

        Hallucination *pakda gaya* dikhna usse gayab kar dene se zyada useful hai,
        aur user ke liye "ye shayad galat hai" khaali screen se behtar hai.
        """
        fake_llm.grounded = "no"

        result = validate_answer("Some claim.", context=["unrelated context"], question="")

        assert not result.grounded
        assert not result.passed
        assert "Some claim." in result.validated_output, "the original answer must not be hidden"
        assert result.validated_output.startswith("\u26a0\ufe0f")

    def test_grounded_answer_passes_through_unchanged(self, fake_llm):
        fake_llm.grounded = "yes"
        answer = "Overlap keeps boundary sentences retrievable."

        result = validate_answer(answer, context=["some context"], question="")

        assert result.passed
        assert result.validated_output == answer

    def test_check_failure_fails_open(self, monkeypatch):
        """If the check itself crashes, the answer must not be blocked.

        Wo already verified context se bana hai. Fail-closed hone se ek flaky
        network call would turn the whole system into "I cannot tell you anything".
        """
        import app.guardrails.validators as validators

        def _boom(answer, context):
            raise RuntimeError("groq unreachable")

        monkeypatch.setattr(validators, "check_groundedness", _boom)

        result = validate_answer("A normal answer.", context=["ctx"], question="")

        assert result.passed, "an infrastructure error must not block the answer"
        assert result.validated_output == "A normal answer."
        assert "did not run" in result.reason

    def test_no_context_is_trivially_grounded(self, fake_llm):
        """There was no context at all -- `generate` will already have said so."""
        result = validate_answer("I don't have enough context.", context=[], question="")
        assert result.grounded
