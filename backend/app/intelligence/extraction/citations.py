"""
Deterministic citation check: a fact is only kept if its quote really
appears on the page it cites. This is what turns "every extracted fact
carries a document/page citation" from a prompt instruction into a
guarantee — an LLM that misquotes, paraphrases or invents a clause has
that item dropped, not stored.

Matching is exact after normalising things PDF text extraction mangles
inconsistently and that don't change meaning: whitespace/line breaks,
case, curly vs straight quotes, dash variants, and hyphenation at line
ends.
"""
import re
import unicodedata

_CHAR_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        " ": " ",
    }
)
_LINE_END_HYPHEN = re.compile(r"(\w)-\s*\n\s*(\w)")
_WHITESPACE = re.compile(r"\s+")

# Quotes shorter than this are too generic to prove anything (e.g. "Yes").
MIN_QUOTE_CHARS = 12


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _LINE_END_HYPHEN.sub(r"\1\2", text)
    text = text.translate(_CHAR_MAP).lower()
    return _WHITESPACE.sub(" ", text).strip()


def quote_on_page(quote: str, page_text: str) -> bool:
    normalised_quote = normalise(quote)
    if len(normalised_quote) < MIN_QUOTE_CHARS:
        return False
    return normalised_quote in normalise(page_text)
