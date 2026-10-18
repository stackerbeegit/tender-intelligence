"""
Works out which state a GeM bid belongs to. GeM's listing payload carries
no location at all, so two sources are used:

1. The bid PDF's "Consignees/Reporting Officer" table — the delivery
   location. Civil bids show `Name / 522503,Address...`, so the pincode is
   read; defence bids mask the address (`***********SRI GANGANAGAR`) and
   only the city/district survives. BOQ bids keep the consignee list in a
   separate BOQ file and yield nothing here.
2. The buyer's department name — state-government buyers are named like
   "Home Department Andhra Pradesh". This is the buyer's state, used for
   the organisation, not as a delivery location.

Pincode/city -> state comes from `locations.json`, built from GeM's own
state/city dropdown data by `scripts/build_gem_locations.py`.
"""
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.connectors.base.types import NormalisedLocation

_LOCATIONS_PATH = Path(__file__).parent / "locations.json"

# Each consignee table starts at its "/Address" column header; the rows sit
# between it and the next section, well within this many characters.
_CONSIGNEE_SECTION_CHARS = 1500
_SECTION_END = re.compile(r"/Buyer Added|/Technical Specifications|/Specification|Specification Document")
_ADDRESS_PINCODE =re.compile(r"(?<!\d)(\d{6})\s*,")
_MASKED_CITY = re.compile(r"\*{5,}\s*\*{5,}\s*([^\n*]+)")
_CITY_QUALIFIERS = re.compile(r"\b(RURAL|URBAN|CITY|NORTH|SOUTH|EAST|WEST|CENTRAL|NEW|OLD|DISTRICT)\b")


@lru_cache(maxsize=1)
def _lookup() -> dict:
    data = json.loads(_LOCATIONS_PATH.read_text())
    two_digit: dict[str, Counter] = {}
    for pin, state in data["pincodes"].items():
        two_digit.setdefault(pin[:2], Counter())[state] += 1
    data["pincode_circles"] = {p: votes.most_common(1)[0][0] for p, votes in two_digit.items()}
    return data


def state_for_pincode(pincode: str) -> str | None:
    lookup = _lookup()
    return (
        lookup["pincodes"].get(pincode)
        or lookup["pincode_prefixes"].get(pincode[:3])
        or lookup["pincode_circles"].get(pincode[:2])
    )


def state_for_city(city: str) -> str | None:
    cities = _lookup()["cities"]
    name = city.strip().upper()
    if name in cities:
        return cities[name]
    for part in re.split(r"[/,()-]", name):
        part = _CITY_QUALIFIERS.sub("", part).strip()
        if part in cities:
            return cities[part]
    return None


def state_from_department(department: str | None) -> str | None:
    """'Home Department Andhra Pradesh' -> 'Andhra Pradesh'."""
    if not department:
        return None
    tail = re.sub(r"[^a-z ]", " ", department.lower().replace("&", " and "))
    tail = " ".join(tail.split())
    for state in sorted(_lookup()["states"], key=len, reverse=True):
        key = " ".join(re.sub(r"[^a-z ]", " ", state.lower().replace("&", " and ")).split())
        if tail.endswith(" " + key) or tail == key:
            return state
    return None


def consignee_locations(pages: list[str]) -> tuple[NormalisedLocation, ...]:
    text = "\n".join(pages)
    found: list[NormalisedLocation] = []
    seen: set[tuple] = set()

    for header in re.finditer(r"/Address", text):
        section = text[header.end() : header.end() + _CONSIGNEE_SECTION_CHARS]
        section = _SECTION_END.split(section, maxsplit=1)[0]
        candidates = [
            NormalisedLocation(state=state_for_pincode(pin), pincode=pin)
            for pin in _ADDRESS_PINCODE.findall(section)
        ] + [
            NormalisedLocation(state=state_for_city(city), city=city.strip().title())
            for city in _MASKED_CITY.findall(section)
        ]
        for loc in candidates:
            key = (loc.state, loc.city, loc.pincode)
            if loc.state and key not in seen:
                seen.add(key)
                found.append(loc)
    return tuple(found)
