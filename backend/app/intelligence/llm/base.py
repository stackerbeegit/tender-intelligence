"""
Provider-agnostic LLM interface (docs/architecture.md §6). Application
code depends only on `LLMClient`; vendor SDKs/HTTP shapes live solely in
the adapter modules next to this one.

The one operation the intelligence layer needs is "give me a JSON object
matching this schema" — both supported providers can constrain output to
a JSON Schema natively, so callers never parse free text.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    model: str  # the model that actually served the request
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Configured model id, recorded on every row this client produces."""

    @abstractmethod
    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        """
        One request/response. `schema` is a JSON Schema object (all
        properties required, `additionalProperties: false` at every
        level). Raises `LLMResponseError` on any provider failure, refusal,
        truncation or unparseable output — never a vendor exception.
        """
