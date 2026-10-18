"""
`get_llm_client()` builds the adapter named by LLM_PROVIDER. The
Anthropic adapter is imported lazily so the vendor SDK is only loaded
when that provider is actually selected.
"""
from app.core.config import Settings, get_settings
from app.core.exceptions import LLMNotConfiguredError
from app.intelligence.llm.base import LLMClient, LLMResult

__all__ = ["LLMClient", "LLMResult", "get_llm_client"]


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMNotConfiguredError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        from app.intelligence.llm.anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            effort=settings.anthropic_effort,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_request_timeout_seconds,
            refusal_fallback=settings.anthropic_refusal_fallback,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMNotConfiguredError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set")
        from app.intelligence.llm.openai_client import OpenAICompatibleLLMClient

        return OpenAICompatibleLLMClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_request_timeout_seconds,
        )

    raise LLMNotConfiguredError(f"Unknown LLM_PROVIDER {settings.llm_provider!r} (expected 'anthropic' or 'openai')")
