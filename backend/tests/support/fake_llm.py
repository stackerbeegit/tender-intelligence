"""
A scripted stand-in for a real LLM provider, used wherever tests exercise
the intelligence pipeline. It behaves like a model reading excerpts: for
an extraction call it returns only the canned items whose page is in
that call's excerpt, shaped to the full JSON Schema (absent keys padded
with null, as a strict-mode provider would return them). No network, no
API key, deterministic.

What this proves: everything around the model — batching, citation
verification, persistence, summary wiring, failure handling. It does not
prove the quality of a real model's extraction; that needs a live run
against a provider (see docs/development-plan.md, Sprint 4 notes).
"""
import copy
import json
import re
from pathlib import Path
from typing import Any

from app.core.exceptions import LLMResponseError
from app.intelligence.extraction.schemas import EXTRACTION_SCHEMA, SUMMARY_SCHEMA
from app.intelligence.llm.base import LLMClient, LLMResult

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "intelligence"
_PAGE_MARKER = re.compile(r"^=== PAGE (\d+) ===$", re.MULTILINE)


def load_rfp_responses() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "sample_rfp_llm_responses.json").read_text())


def pad_to_schema(value: Any, schema: dict[str, Any]) -> Any:
    if "anyOf" in schema:
        if value is None:
            return None
        schema = next(s for s in schema["anyOf"] if s.get("type") != "null")
    if schema.get("type") == "object":
        value = value or {}
        unknown = set(value) - set(schema["properties"])
        assert not unknown, f"canned response has keys outside the schema: {unknown}"
        return {key: pad_to_schema(value.get(key), sub) for key, sub in schema["properties"].items()}
    if schema.get("type") == "array":
        return [pad_to_schema(item, schema["items"]) for item in (value or [])]
    if "enum" in schema and value is not None:
        assert value in schema["enum"], f"{value!r} not in schema enum"
    return value


class FakeLLMClient(LLMClient):
    def __init__(self, responses: dict[str, Any] | None = None, fail_on_call: int | None = None):
        self.responses = responses if responses is not None else load_rfp_responses()
        self.fail_on_call = fail_on_call  # 1-indexed call number that raises
        self.calls: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return "fake-model"

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> LLMResult:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if self.fail_on_call == len(self.calls):
            raise LLMResponseError("simulated provider outage")

        if schema is EXTRACTION_SCHEMA:
            pages_in_excerpt = {int(n) for n in _PAGE_MARKER.findall(user)}
            data = {
                kind: [
                    {k: v for k, v in item.items() if not k.startswith("_")}
                    for item in self.responses.get(kind, [])
                    if item.get("_seen_on_page", item["page_number"]) in pages_in_excerpt
                ]
                for kind in ("requirements", "eligibility")
            }
        elif schema is SUMMARY_SCHEMA:
            data = copy.deepcopy(self.responses["summary"])
        else:  # pragma: no cover
            raise AssertionError("unexpected schema")

        return LLMResult(
            data=pad_to_schema(data, schema), model="fake-model", usage={"input_tokens": 100, "output_tokens": 50}
        )
