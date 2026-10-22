"""Small, pure helpers shared by the matching rules."""
import re
from typing import Any


def number(value: Any) -> float | None:
    """A numeric fact value as float; None for missing/non-numeric (a
    boolean is not a number here, even though Python says it is)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalise(text: str) -> str:
    """Lower-case, alphanumerics only — for loose name matching such as
    "ISO/IEC 27001" vs "iso 27001" or "Node.js" vs "nodejs"."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def format_inr(amount: float | None) -> str:
    """₹ amount in crore/lakh, the way tender documents state it."""
    if amount is None:
        return "an unstated amount"
    if amount >= 1e7:
        return f"₹{amount / 1e7:,.2f} Cr".replace(".00 Cr", " Cr")
    if amount >= 1e5:
        return f"₹{amount / 1e5:,.2f} L".replace(".00 L", " L")
    return f"₹{amount:,.0f}"
