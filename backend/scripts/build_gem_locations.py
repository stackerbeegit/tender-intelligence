"""
Rebuilds app/connectors/gem/locations.json — the state lookup the GeM
connector uses to turn a bid's consignee pincode/city into a state.

Source: GeM's own advance-search dropdown endpoints (`/state-list-adv` and
`/city-list-adv`), the same public calls bidplus.gem.gov.in/advance-search
makes for any anonymous visitor. One request per state, rate-limited like
the crawler. Re-run only when GeM's state/city list changes:

    python scripts/build_gem_locations.py
"""
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "connectors" / "gem" / "locations.json"
_CSRF_PATTERN = re.compile(r"csrf_bd_gem_nk'\s*:\s*'([a-f0-9]+)'")


def main() -> None:
    settings = get_settings()
    client = httpx.Client(
        base_url=settings.gem_bidplus_base_url,
        headers={"User-Agent": settings.crawler_user_agent},
        timeout=settings.gem_request_timeout_seconds,
        follow_redirects=True,
    )
    page = client.get("/advance-search")
    page.raise_for_status()
    csrf = _CSRF_PATTERN.search(page.text).group(1)

    states_resp = client.post("/state-list-adv", data={"csrf_bd_gem_nk": csrf})
    states_resp.raise_for_status()
    gem_states = [row["state_name"] for row in json.loads(states_resp.text)["data"] if row["state_name"]]

    cities: dict[str, str] = {}
    pincodes: dict[str, str] = {}
    prefix_votes: dict[str, Counter] = defaultdict(Counter)
    states: list[str] = []
    for gem_state in gem_states:
        time.sleep(settings.crawler_default_rate_limit_seconds)
        state = gem_state.title().replace(" And ", " and ")
        states.append(state)
        resp = client.post("/city-list-adv", data={"state_name": gem_state, "csrf_bd_gem_nk": csrf})
        resp.raise_for_status()
        for row in json.loads(resp.text).get("data") or []:
            city = (row.get("city_name") or "").strip().upper()
            pin = (row.get("pin_code") or "").strip()
            if city:
                cities.setdefault(city, state)
            if re.fullmatch(r"\d{6}", pin):
                pincodes.setdefault(pin, state)
                prefix_votes[pin[:3]][state] += 1
        print(f"{state}: {len(json.loads(resp.text).get('data') or [])} cities")

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "states": sorted(states),
                "cities": dict(sorted(cities.items())),
                "pincodes": dict(sorted(pincodes.items())),
                # 3-digit pincode prefix (India Post sorting district) -> the
                # state most of GeM's listed pincodes under it belong to.
                "pincode_prefixes": {p: v.most_common(1)[0][0] for p, v in sorted(prefix_votes.items())},
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"Wrote {OUTPUT_PATH} ({len(states)} states, {len(cities)} cities, {len(pincodes)} pincodes)")


if __name__ == "__main__":
    main()
