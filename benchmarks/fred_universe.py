"""Systematic FRED daily-series universe — no hand-curation.

The earlier benchmark used a list of ~50 tickers I picked, which invites the
"you cherry-picked the series" critique. This enumerates the universe by a
fixed, reproducible rule instead: take the top-N FRED series tagged *daily*,
ordered by popularity (descending). Popularity is FRED's own usage ranking, so
the rule is documented and independent of the forecasters being compared.

The resolved ID list is cached to benchmarks/data/universe_daily.json so the
run is reproducible and works offline afterwards.

  python benchmarks/fred_universe.py            # resolve + cache the universe
"""

from __future__ import annotations
import json
import os
import re
import time
import urllib.parse
import urllib.request

from fred import _api_key, _HERE  # type: ignore

_CACHE = os.path.join(_HERE, "data")
_UNIVERSE_JSON = os.path.join(_CACHE, "universe_daily.json")


def _get(path, **params):
    params.update(api_key=_api_key(), file_type="json")
    url = "https://api.stlouisfed.org/fred/" + path + "?" + urllib.parse.urlencode(params)
    return json.loads(urllib.request.urlopen(url, timeout=30).read())


def enumerate_daily(n_candidates=3000, refresh=False):
    """Return [{id,title,popularity,obs_start,freq}] — top-N daily series by
    popularity. Cached to universe_daily.json (pass refresh=True to re-resolve)."""
    if not refresh and os.path.exists(_UNIVERSE_JSON):
        cached = json.load(open(_UNIVERSE_JSON))
        if len(cached) >= n_candidates:
            return cached[:n_candidates]

    out = []
    offset = 0
    while len(out) < n_candidates:
        page = _get("tags/series", tag_names="daily", order_by="popularity",
                    sort_order="desc", limit=1000, offset=offset)
        rows = page.get("seriess", [])
        if not rows:
            break
        for s in rows:
            out.append({
                "id": s["id"],
                "title": s.get("title", "")[:80],
                "popularity": s.get("popularity", 0),
                "obs_start": s.get("observation_start", ""),
                "freq": s.get("frequency_short", ""),
            })
        offset += 1000
        time.sleep(0.5)  # be polite to the API
    out = out[:n_candidates]
    os.makedirs(_CACHE, exist_ok=True)
    json.dump(out, open(_UNIVERSE_JSON, "w"))
    return out


def family(series_id):
    """Coarse family key for de-correlating the win-rate: the leading run of
    capital letters (e.g. DGS10->DGS, DEXJPUS->DEX, BAMLH0A0HYM2->BAMLH,
    T10Y2Y->T). Many FRED families are a curve or a panel (yields by maturity,
    FX by counterparty) that are far from independent; clustering on this key
    lets the summary report a family-weighted rate as a robustness check."""
    m = re.match(r"^[A-Z]+", series_id)
    return (m.group(0)[:4] if m else series_id)


_CLASS_RULES = [
    ("rates", r"treasury|yield|fed funds|interest rate|repo|libor|sofr|bill|note|bond"),
    ("fx", r"exchange rate|/ u\.s\.|u\.s\. dollar|currency|won|yen|euro|peso|yuan|real|pound"),
    ("credit", r"spread|option-adjusted|high yield|corporate|aaa|baa|bbb|cds"),
    ("equity", r"s&p|nasdaq|dow|wilshire|equity|stock|vix|volatility index"),
    ("commodity", r"crude|oil|gas|gold|brent|wti|natural gas|commodity"),
]


def asset_class(title):
    """Approximate asset class from the title keywords (for the breakdown only)."""
    t = title.lower()
    for name, pat in _CLASS_RULES:
        if re.search(pat, t):
            return name
    return "other"


if __name__ == "__main__":
    u = enumerate_daily()
    print(f"resolved {len(u)} daily series -> {_UNIVERSE_JSON}")
    from collections import Counter
    cls = Counter(asset_class(s["title"]) for s in u)
    fam = Counter(family(s["id"]) for s in u)
    print("by class:", dict(cls))
    print("distinct families:", len(fam), " top:", fam.most_common(8))
