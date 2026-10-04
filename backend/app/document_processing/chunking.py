"""
Splits extracted page text into bounded chunks, each tagged with the page
it came from. This exists so a large tender document is never sent to an
LLM whole (brief §7/§18/architecture.md §5) — Sprint 4's intelligence
layer and Sprint 7's embeddings both consume `chunk_pages()`'s output.
Nothing persists a chunk to the database yet (no `tender_embeddings`
table until Sprint 7); this is a pure, directly-testable function ready
for both to call.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    page_number: int  # 0-indexed, matching `pages` lists elsewhere
    chunk_index: int  # index within the page, 0-indexed
    text: str


def chunk_pages(pages: list[str], chunk_size: int = 1000, overlap: int = 100) -> list[DocumentChunk]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[DocumentChunk] = []
    for page_number, page_text in enumerate(pages):
        stripped = page_text.strip()
        if not stripped:
            continue

        if len(stripped) <= chunk_size:
            chunks.append(DocumentChunk(page_number=page_number, chunk_index=0, text=stripped))
            continue

        start = 0
        chunk_index = 0
        step = chunk_size - overlap
        while start < len(stripped):
            chunk_text = stripped[start : start + chunk_size]
            chunks.append(DocumentChunk(page_number=page_number, chunk_index=chunk_index, text=chunk_text))
            chunk_index += 1
            start += step

    return chunks
