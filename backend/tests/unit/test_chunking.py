import pytest

from app.document_processing.chunking import chunk_pages


def test_short_page_becomes_a_single_chunk():
    chunks = chunk_pages(["short text"], chunk_size=1000, overlap=100)
    assert len(chunks) == 1
    assert chunks[0].page_number == 0
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "short text"


def test_empty_pages_are_skipped():
    chunks = chunk_pages(["", "   ", "real content"], chunk_size=1000, overlap=100)
    assert len(chunks) == 1
    assert chunks[0].page_number == 2


def test_long_page_splits_with_overlap():
    text = "x" * 2500
    chunks = chunk_pages([text], chunk_size=1000, overlap=100)
    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    assert len(chunks[0].text) == 1000
    assert len(chunks[1].text) == 1000
    assert len(chunks[2].text) == 700
    # the overlap region is identical between consecutive chunks
    assert chunks[0].text[-100:] == chunks[1].text[:100]


def test_page_numbers_are_preserved_across_multiple_pages():
    chunks = chunk_pages(["page zero", "page one"], chunk_size=1000, overlap=100)
    assert [c.page_number for c in chunks] == [0, 1]


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_pages(["text"], chunk_size=100, overlap=100)
