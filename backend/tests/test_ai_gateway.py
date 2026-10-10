"""
Tests for the AI Orchestration Gateway.

These tests mock the underlying LLM providers so no real API calls
are made during CI. We validate the routing, retry, and fallback
behaviour of the gateway.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_provider(response: str = "This is a test question.", raises=None):
    """Create a sync callable that either returns text or raises an exception."""
    def _provider(prompt, max_tokens, temperature):
        if raises:
            raise raises
        return response
    return _provider


def test_hf_provider_requests_errors_instead_of_hidden_fallback():
    """The gateway HF provider must not treat legacy text fallbacks as success."""
    from backend.app.core.ai_gateway import _call_hf_api

    calls = {}

    def fake_hf_generate(prompt, max_new_tokens, temperature, fallback_on_error=True):
        calls["fallback_on_error"] = fallback_on_error
        raise RuntimeError("HF credits depleted")

    with patch("backend.app.core.ml_models.is_hf_circuit_open", return_value=False), patch(
        "backend.app.core.ml_models._hf_api_generate", side_effect=fake_hf_generate
    ):
        with pytest.raises(RuntimeError):
            _call_hf_api("prompt", 10, 0.0)

    assert calls["fallback_on_error"] is False


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gateway_succeeds_on_first_provider():
    """Gateway returns first-provider result when it succeeds."""
    from backend.app.core.ai_gateway import ai_generate

    good_provider = make_mock_provider("What is polymorphism?")

    with patch(
        "backend.app.core.ai_gateway._PROVIDERS",
        [("mock_primary", good_provider)],
    ):
        result = await ai_generate("Generate a question", task="test")

    assert result.text == "What is polymorphism?"
    assert result.provider == "mock_primary"
    assert result.used_fallback is False
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_gateway_falls_back_to_second_provider():
    """Gateway automatically switches to secondary when primary fails."""
    from backend.app.core.ai_gateway import ai_generate

    failing_provider = make_mock_provider(raises=RuntimeError("Primary down"))
    backup_provider  = make_mock_provider("Backup answer here.")

    with patch(
        "backend.app.core.ai_gateway._PROVIDERS",
        [("mock_primary", failing_provider), ("mock_backup", backup_provider)],
    ), patch("backend.app.core.ai_gateway._MAX_RETRIES", 0):
        result = await ai_generate("Generate a question", task="test")

    assert result.text == "Backup answer here."
    assert result.provider == "mock_backup"
    assert result.used_fallback is False


@pytest.mark.asyncio
async def test_gateway_uses_template_fallback_when_all_fail():
    """Gateway returns template fallback when every provider fails."""
    from backend.app.core.ai_gateway import ai_generate

    failing_provider = make_mock_provider(raises=RuntimeError("Down"))

    with patch(
        "backend.app.core.ai_gateway._PROVIDERS",
        [("mock_primary", failing_provider)],
    ), patch("backend.app.core.ai_gateway._MAX_RETRIES", 0):
        result = await ai_generate(
            "Generate a question",
            task="test",
            fallback_text="Tell me about yourself.",
        )

    assert result.text == "Tell me about yourself."
    assert result.provider == "template_fallback"
    assert result.used_fallback is True
    assert result.error is not None


@pytest.mark.asyncio
async def test_gateway_retries_on_failure():
    """Gateway retries a failing provider before switching."""
    from backend.app.core.ai_gateway import ai_generate

    call_count = 0

    def flaky_provider(prompt, max_tokens, temperature):
        nonlocal call_count
        call_count += 1
        if call_count < 2:  # fail on first call, succeed on retry
            raise RuntimeError("Transient failure")
        return "Recovered after retry."

    with patch(
        "backend.app.core.ai_gateway._PROVIDERS",
        [("mock_flaky", flaky_provider)],
    ), patch("backend.app.core.ai_gateway._MAX_RETRIES", 2), \
       patch("backend.app.core.ai_gateway._RETRY_BASE_DELAY", 0.0):
        result = await ai_generate("Generate a question", task="test")

    assert result.text == "Recovered after retry."
    assert result.retries == 1
    assert call_count == 2


@pytest.mark.asyncio
async def test_gateway_result_has_required_fields():
    """AIResult dataclass has all required fields populated."""
    from backend.app.core.ai_gateway import ai_generate, AIResult

    good_provider = make_mock_provider("Describe a design pattern.")

    with patch(
        "backend.app.core.ai_gateway._PROVIDERS",
        [("mock_primary", good_provider)],
    ):
        result = await ai_generate("test prompt", task="unit_test")

    assert isinstance(result, AIResult)
    assert result.request_id   # non-empty string
    assert result.task == "unit_test"
    assert isinstance(result.latency_ms, float)


@pytest.mark.asyncio
async def test_convenience_wrappers_use_correct_tasks():
    """generate_interview_question and score_answer_llm label tasks correctly."""
    from backend.app.core.ai_gateway import (
        generate_interview_question,
        score_answer_llm,
        generate_followup_question,
    )

    good_provider = make_mock_provider("Question text here.")

    with patch(
        "backend.app.core.ai_gateway._PROVIDERS",
        [("mock_primary", good_provider)],
    ):
        q = await generate_interview_question("prompt")
        s = await score_answer_llm("prompt")
        f = await generate_followup_question("prompt")

    assert q.task == "question_generation"
    assert s.task == "answer_scoring"
    assert f.task == "followup_generation"


def test_call_groq_api_delegates_to_ml_models():
    """_call_groq_api calls _groq_api_generate with expected args."""
    from backend.app.core.ai_gateway import _call_groq_api

    with patch("backend.app.core.ml_models._groq_api_generate", return_value="Groq response") as mock_groq:
        res = _call_groq_api("Test prompt", 100, 0.5)
        assert res == "Groq response"
        mock_groq.assert_called_once_with("Test prompt", max_new_tokens=100, temperature=0.5)


def test_groq_api_generate_success():
    """_groq_api_generate successfully parses OpenAI-compatible response from Groq."""
    from backend.app.core.ml_models import _groq_api_generate

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Generated from Groq"}}]
    }

    with patch("os.getenv", side_effect=lambda k, d="": "mock_groq_key" if k == "GROQ_API_KEY" else d), \
         patch("requests.post", return_value=mock_resp):
        out = _groq_api_generate("Hello", 50, 0.0)
        assert out == "Generated from Groq"


def test_groq_api_generate_fallback_on_404():
    """_groq_api_generate tries next candidate model if current returns 404 model_not_found."""
    from backend.app.core.ml_models import _groq_api_generate

    resp_404 = MagicMock()
    resp_404.status_code = 404
    resp_404.text = '{"error":{"message":"The model does not exist","code":"model_not_found"}}'

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Fallback model worked"}}]
    }

    with patch("os.getenv", side_effect=lambda k, d="": "mock_groq_key" if k == "GROQ_API_KEY" else d), \
         patch("requests.post", side_effect=[resp_404, resp_200]):
        out = _groq_api_generate("Hello", 50, 0.0)
        assert out == "Fallback model worked"


def test_groq_api_generate_fallback_on_429():
    """_groq_api_generate tries next candidate model if current hits 429 rate limit."""
    from backend.app.core.ml_models import _groq_api_generate

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = '{"error":{"message":"Rate limit reached for model","code":"rate_limit_exceeded"}}'

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Model after 429 worked"}}]
    }

    with patch("os.getenv", side_effect=lambda k, d="": "mock_groq_key" if k == "GROQ_API_KEY" else d), \
         patch("requests.post", side_effect=[resp_429, resp_200]):
        out = _groq_api_generate("Hello", 50, 0.0)
        assert out == "Model after 429 worked"



@pytest.mark.asyncio
async def test_deterministic_error_fails_fast_without_retries():
    """Errors like 'GROQ_API_KEY not set' fail fast on attempt 1 without sleeping."""
    from backend.app.core.ai_gateway import _try_provider_with_retry

    call_count = 0

    def missing_key_provider(prompt, max_tokens, temperature):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("GROQ_API_KEY not set")

    with pytest.raises(RuntimeError) as exc_info:
        await _try_provider_with_retry(
            "groq",
            missing_key_provider,
            "test prompt",
            50,
            0.0,
            "req123",
            "test_task",
        )

    assert "GROQ_API_KEY not set" in str(exc_info.value)
    assert call_count == 1  # must NOT retry
