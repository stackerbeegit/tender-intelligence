"""
Adapter tests. The OpenAI-compatible adapter is driven through a real
httpx client with a MockTransport (so the exact request body it sends is
asserted); the Anthropic adapter's SDK client is swapped for a stub at
the `beta.messages.stream` boundary, since the SDK's own transport is
not ours to test.
"""
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import LLMNotConfiguredError, LLMResponseError
from app.intelligence.llm import get_llm_client
from app.intelligence.llm.anthropic_client import AnthropicLLMClient
from app.intelligence.llm.openai_client import OpenAICompatibleLLMClient

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


# --- factory ---


def test_factory_requires_api_key_for_selected_provider():
    with pytest.raises(LLMNotConfiguredError, match="ANTHROPIC_API_KEY"):
        get_llm_client(Settings(llm_provider="anthropic", anthropic_api_key=""))
    with pytest.raises(LLMNotConfiguredError, match="OPENAI_API_KEY"):
        get_llm_client(Settings(llm_provider="openai", openai_api_key=""))


def test_factory_rejects_unknown_provider():
    with pytest.raises(LLMNotConfiguredError, match="Unknown LLM_PROVIDER"):
        get_llm_client(Settings(llm_provider="mystery"))


def test_factory_builds_each_adapter():
    assert isinstance(get_llm_client(Settings(llm_provider="anthropic", anthropic_api_key="k")), AnthropicLLMClient)
    client = get_llm_client(Settings(llm_provider="openai", openai_api_key="k", openai_model="m"))
    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.model_name == "m"


# --- OpenAI-compatible adapter ---


def _openai_client(handler) -> OpenAICompatibleLLMClient:
    return OpenAICompatibleLLMClient(
        api_key="test-key",
        model="test-model",
        base_url="http://llm.local/v1/",
        max_output_tokens=1000,
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )


def test_openai_adapter_sends_json_schema_and_parses_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "test-model-2026",
                "choices": [{"finish_reason": "stop", "message": {"content": '{"answer": "42"}'}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3},
            },
        )

    result = _openai_client(handler).complete_json(system="sys", user="usr", schema=SCHEMA)

    assert seen["url"] == "http://llm.local/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["response_format"]["json_schema"]["schema"] == SCHEMA
    assert seen["body"]["response_format"]["json_schema"]["strict"] is True
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert result.data == {"answer": "42"}
    assert result.model == "test-model-2026"
    assert result.usage == {"input_tokens": 11, "output_tokens": 3}


@pytest.mark.parametrize(
    "response, message",
    [
        (httpx.Response(500, text="boom"), "HTTP 500"),
        (httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{"}}]}), "truncated"),
        (httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"refusal": "no"}}]}), "declined"),
        (httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}]}), "not valid JSON"),
        (httpx.Response(200, json={"unexpected": True}), "Unexpected response shape"),
    ],
)
def test_openai_adapter_translates_failures(response, message):
    with pytest.raises(LLMResponseError, match=message):
        _openai_client(lambda request: response).complete_json(system="s", user="u", schema=SCHEMA)


def test_openai_adapter_translates_network_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMResponseError, match="Could not reach"):
        _openai_client(handler).complete_json(system="s", user="u", schema=SCHEMA)


# --- Anthropic adapter ---


class _StubStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


def _message(stop_reason="end_turn", text='{"answer": "42"}', stop_details=None):
    return SimpleNamespace(
        model="claude-opus-5-5",
        stop_reason=stop_reason,
        stop_details=stop_details,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=20, output_tokens=5),
    )


def _anthropic_client(stream_impl) -> AnthropicLLMClient:
    client = AnthropicLLMClient(
        api_key="test", model="claude-opus-5-5", effort="medium", max_output_tokens=1000, timeout_seconds=5
    )
    client._client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream_impl)))
    return client


def test_anthropic_adapter_requests_structured_output_with_fallbacks():
    seen = {}

    def stream(**kwargs):
        seen.update(kwargs)
        return _StubStream(_message())

    result = _anthropic_client(stream).complete_json(system="sys", user="usr", schema=SCHEMA)

    assert seen["model"] == "claude-opus-5-5"
    assert seen["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert seen["fallbacks"] == "default"
    assert seen["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in seen and "temperature" not in seen
    assert result.data == {"answer": "42"}
    assert result.usage == {"input_tokens": 20, "output_tokens": 5}


def test_anthropic_adapter_can_disable_refusal_fallback():
    seen = {}

    def stream(**kwargs):
        seen.update(kwargs)
        return _StubStream(_message())

    client = _anthropic_client(stream)
    client._refusal_fallback = False
    client.complete_json(system="s", user="u", schema=SCHEMA)

    assert "fallbacks" not in seen and "betas" not in seen


def test_anthropic_adapter_reports_refusal():
    def stream(**kwargs):
        return _StubStream(_message(stop_reason="refusal", text="", stop_details=SimpleNamespace(category="cyber")))

    with pytest.raises(LLMResponseError, match="declined.*cyber"):
        _anthropic_client(stream).complete_json(system="s", user="u", schema=SCHEMA)


def test_anthropic_adapter_reports_truncation():
    def stream(**kwargs):
        return _StubStream(_message(stop_reason="max_tokens", text='{"ans'))

    with pytest.raises(LLMResponseError, match="truncated"):
        _anthropic_client(stream).complete_json(system="s", user="u", schema=SCHEMA)


def test_anthropic_adapter_translates_sdk_errors():
    def stream(**kwargs):
        request = httpx2_request()
        raise anthropic.APIConnectionError(request=request)

    with pytest.raises(LLMResponseError, match="Could not reach the Anthropic API"):
        _anthropic_client(stream).complete_json(system="s", user="u", schema=SCHEMA)


def httpx2_request():
    """anthropic 1.x is built on httpx2, so its exceptions want an httpx2
    request object, not one from the `httpx` package."""
    import httpx2

    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
