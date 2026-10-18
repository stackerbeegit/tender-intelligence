"""
Anthropic (Claude) adapter, via the official `anthropic` SDK.

- Output is constrained with structured outputs (`output_config.format`
  json_schema), so the response text is guaranteed-valid JSON.
- Adaptive thinking is the model default; depth is tuned with
  `output_config.effort` (settings.anthropic_effort).
- Server-side refusal fallback (`fallbacks="default"`) is enabled: if the
  model's safety classifiers decline a request, the API re-runs it on
  Anthropic's recommended fallback model inside the same call. Long
  government documents occasionally contain text (security requirements,
  CCTV/surveillance specs) that can trip a classifier; a fallback is
  better than a silently-missing chunk. If the whole chain still refuses,
  that surfaces as `LLMResponseError`, never as empty output.
- Streaming is used so long extraction responses never hit an HTTP
  timeout; `get_final_message()` returns the complete message.
"""
import json
from typing import Any

import anthropic

from app.core.exceptions import LLMResponseError
from app.core.logging import get_logger
from app.intelligence.llm.base import LLMClient, LLMResult

logger = get_logger(__name__)

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicLLMClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        effort: str,
        max_output_tokens: int,
        timeout_seconds: float,
        refusal_fallback: bool = True,
    ):
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._effort = effort
        self._max_output_tokens = max_output_tokens
        self._refusal_fallback = refusal_fallback

    @property
    def model_name(self) -> str:
        return self._model

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        fallback_params: dict[str, Any] = (
            {"betas": [_FALLBACK_BETA], "fallbacks": "default"} if self._refusal_fallback else {}
        )
        try:
            with self._client.beta.messages.stream(
                model=self._model,
                max_tokens=self._max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
                **fallback_params,
            ) as stream:
                message = stream.get_final_message()
        except anthropic.APIConnectionError as exc:
            raise LLMResponseError(f"Could not reach the Anthropic API: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMResponseError(
                f"Anthropic API error {exc.status_code} (request id {exc.request_id}): {exc.message}"
            ) from exc

        if message.stop_reason == "refusal":
            category = message.stop_details.category if message.stop_details else None
            raise LLMResponseError(f"Model declined the request (refusal category: {category})")
        if message.stop_reason == "max_tokens":
            raise LLMResponseError(
                f"Response truncated at max_tokens={self._max_output_tokens}; "
                "lower LLM_MAX_CHARS_PER_CALL or raise LLM_MAX_OUTPUT_TOKENS"
            )

        text = "".join(block.text for block in message.content if block.type == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"Model output was not valid JSON: {exc}") from exc

        usage = {"input_tokens": message.usage.input_tokens, "output_tokens": message.usage.output_tokens}
        logger.info("Anthropic call model=%s stop=%s usage=%s", message.model, message.stop_reason, usage)
        return LLMResult(data=data, model=message.model, usage=usage)
