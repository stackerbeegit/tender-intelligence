"""
Deterministic checks that a generated draft bid only states what its
inputs support. The draft is AI-written, so "never invent credentials" is
enforced here in code — the same idea as Sprint 4's citation check:

- every rupee amount must equal (within 0.5%) an amount in the inputs;
- every certification named (ISO nnnnn, CMMI level n, CERT-In) must be
  named in the inputs, at the same level;
- every "N years" claim must use a number present in the inputs;
- placeholders (`[TO FILL: …]`) are excluded — they mark what people must
  supply, so their wording isn't a claim.

What this cannot check: free-text claims with no number or certificate in
them (e.g. an invented client name). The prompt forbids naming projects
in free text — past projects are referenced by id and rendered from the
profile — and the draft is always labelled for human review.
"""
import re
from collections.abc import Iterable

PLACEHOLDER = re.compile(r"\[TO FILL:[^\]]*\]", re.IGNORECASE)

_UNIT = r"(crores?|cr\.?|lakhs?|lacs?|lac|l)\b"
_SYMBOL_AMOUNT = re.compile(r"(?:₹|\bRs\.?|\bINR)\s*([\d,]+(?:\.\d+)?)\s*(?:" + _UNIT + ")?", re.IGNORECASE)
_WORD_AMOUNT = re.compile(r"\b([\d,]+(?:\.\d+)?)\s*(crores?|cr\b|lakhs?|lacs?)\b", re.IGNORECASE)
_YEARS = re.compile(r"\b(\d{1,2})\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)
_ISO = re.compile(r"\bISO\s*/?\s*(?:IEC\s*)?[:\-]?\s*(\d{4,5})", re.IGNORECASE)
_CMMI = re.compile(r"\bCMMI\b[^.;\d]{0,30}?(?:level|ML|L)\s*[-:]?\s*(\d)", re.IGNORECASE)
_CERT_IN = re.compile(r"\bCERT[\s-]?In\b", re.IGNORECASE)


def _multiplier(unit: str | None) -> float:
    unit = (unit or "").lower().rstrip(".")
    if unit.startswith("cr"):
        return 1e7
    if unit.startswith("la") or unit == "l":
        return 1e5
    return 1.0


def amounts(text: str) -> list[float]:
    """Rupee amounts in `text`: "₹10 Cr", "Rs. 5,00,000", "2 crore"."""
    found: list[tuple[int, float]] = []
    for pattern in (_SYMBOL_AMOUNT, _WORD_AMOUNT):
        for match in pattern.finditer(text):
            try:
                value = float(match.group(1).replace(",", "")) * _multiplier(match.group(2))
            except ValueError:
                continue
            found.append((match.start(1), value))
    # The two patterns overlap on "₹10 Cr"; keep one value per position.
    return list({start: value for start, value in found}.values())


def years(text: str) -> set[int]:
    return {int(n) for n in _YEARS.findall(text)}


def certifications(text: str) -> set[str]:
    """Exact mentions: {"iso:27001", "cmmi:3", "cert-in"}."""
    found = {f"iso:{n}" for n in _ISO.findall(text)} | {f"cmmi:{n}" for n in _CMMI.findall(text)}
    if _CERT_IN.search(text):
        found.add("cert-in")
    return found


def strip_placeholders(text: str) -> str:
    return PLACEHOLDER.sub(" ", text)


def find_placeholders(text: str) -> list[str]:
    return [m.group(0) for m in PLACEHOLDER.finditer(text)]


def _matches(value: float, allowed: Iterable[float]) -> bool:
    return any(abs(value - a) <= max(1.0, 0.005 * abs(a)) for a in allowed)


def _inr(value: float) -> str:
    if value >= 1e7:
        return f"₹{value / 1e7:g} Cr"
    if value >= 1e5:
        return f"₹{value / 1e5:g} L"
    return f"₹{value:,.0f}"


def check_text(
    where: str,
    text: str,
    *,
    allowed_amounts: set[float],
    allowed_years: set[int],
    allowed_certifications: set[str],
) -> list[str]:
    claims = strip_placeholders(text)
    problems = []
    for value in amounts(claims):
        if not _matches(value, allowed_amounts):
            problems.append(f"{where}: amount {_inr(value)} is not in the tender facts or company profile")
    for n in sorted(years(claims) - allowed_years):
        problems.append(f"{where}: '{n} years' is not supported by the tender facts or company profile")
    for cert in sorted(certifications(claims) - allowed_certifications):
        problems.append(f"{where}: certification {cert.replace('iso:', 'ISO ').replace('cmmi:', 'CMMI Level ')} "
                        "is not in the company profile or tender")
    return problems
