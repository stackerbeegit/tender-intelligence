"""
OpenAI-compatible adapter: any endpoint implementing
`POST {base_url}/chat/completions` with `response_format: json_schema`
(OpenAI itself, Azure OpenAI-compatible gateways, vLLM, Ollama's OpenAI
endpoint, ...). Plain httpx rather than a vendor SDK, so pointing
OPENAI_BASE_URL at a self-hosted model needs no extra dependency.
"""
import json
from typing import Any

import httpx

from app.core.exceptions import LLMResponseError
from app.core.logging import get_logger
from app.intelligence.llm.base import LLMClient, LLMResult

logger = get_logger(__name__)


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        max_output_tokens: int,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,  # tests inject httpx.MockTransport
    ):
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
            transport=transport,
        )

    @property
    def model_name(self) -> str:
        return self._model

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        payload = {
            "model": self._model,
            "max_tokens": self._max_output_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "schema": schema, "strict": True},
            },
        }
        try:
            response = self._http.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            raise LLMResponseError(f"Could not reach the LLM endpoint: {exc}") from exc
        if response.status_code >= 400:
            raise LLMResponseError(f"LLM endpoint returned HTTP {response.status_code}: {response.text[:500]}")

        try:
            body = response.json()
            choice = body["choices"][0]
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMResponseError(f"Unexpected response shape from LLM endpoint: {exc}") from exc

        if choice.get("finish_reason") == "length":
            raise LLMResponseError(
                f"Response truncated at max_tokens={self._max_output_tokens}; "
                "lower LLM_MAX_CHARS_PER_CALL or raise LLM_MAX_OUTPUT_TOKENS"
            )
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise LLMResponseError(f"Model declined the request: {message['refusal']}")

        try:
            data = json.loads(message.get("content") or "")
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"Model output was not valid JSON: {exc}") from exc

        raw_usage = body.get("usage") or {}
        usage = {
            "input_tokens": raw_usage.get("prompt_tokens", 0),
            "output_tokens": raw_usage.get("completion_tokens", 0),
        }
        served_by = body.get("model", self._model)
        logger.info("OpenAI-compatible call model=%s usage=%s", served_by, usage)
        return LLMResult(data=data, model=served_by, usage=usage)
