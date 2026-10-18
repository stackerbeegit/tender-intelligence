# Intelligence

LLM-backed structured extraction (Sprint 4). See `docs/architecture.md` §6 and
`docs/development-plan.md` (Sprint 4) for the design rationale.

```text
llm/
  base.py               LLMClient.complete_json(system, user, schema) -> LLMResult
  anthropic_client.py   official `anthropic` SDK, structured outputs, refusal fallback
  openai_client.py      any OpenAI-compatible /chat/completions endpoint (httpx)
  __init__.py           get_llm_client() — picks the adapter from LLM_PROVIDER
extraction/
  schemas.py            JSON Schemas the model's output is constrained to
  prompts.py            system prompts + user prompt builders
  citations.py          verifies a quote really appears on the cited page
  extractor.py          page batching -> LLM call per batch -> verified facts
summary.py              executive summary + categories, written from verified facts only
```

The orchestration (database reads/writes, run status) lives in
`app/services/tender_intelligence_service.py`; nothing in this package touches the
database.

**Rules this package follows:**
- No vendor SDK is imported outside its adapter module.
- A fact is stored only if its verbatim quote is found on the page it cites
  (`extraction/citations.py`). Anything else is dropped and counted, not stored.
- The summary never sees raw document text, only verified facts, so it can't introduce
  claims the documents don't support.
- Deterministic comparisons (does Stackerbee's turnover meet the requirement?) are not
  done here. They belong to Sprint 5's matching engine, in plain Python.

**Coming later:** RAG question-answering over `tender_embeddings` (Sprint 7).
