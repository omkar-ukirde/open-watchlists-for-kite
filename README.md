# open-watchlists-for-kite

Composable, official-source-only predefined watchlists for [Zerodha Kite Connect](https://kite.trade/docs/connect/v3/). Nifty index families, Bank Nifty, sectoral indices, F&O underlyings — all derivable from Zerodha's documented `instruments()` API and NSE's published index CSVs. Zero scraping, zero internal endpoints, zero enctoken/CSRF gymnastics.

## Why

Kite Connect exposes the building blocks (instruments dump, holdings, quotes) but no "predefined watchlist" API. The web app *has* them — Nifty 50, Bank Nifty, sectoral lists — but those are served by Kite-Web-internal endpoints protected by CSRF tokens you can't get over the official API surface. Reverse-engineering those is fragile, against Zerodha's grain, and breaks the moment a cookie name changes.

This package takes the other path: **assemble the same lists from sources Zerodha already supports**, and add the composition primitives (`|`, `&`, `-`, `^`) that make watchlists actually useful for algo work.

## Install

```bash
pip install open-watchlists-for-kite
```

Optional `update` extra if you want to refresh bundled constituent data yourself:

```bash
pip install "open-watchlists-for-kite[update]"
```

## Quick start

```python
from kiteconnect import KiteConnect
from open_watchlists import OpenWatchlists

kite = KiteConnect(api_key="...")
kite.set_access_token("...")

ow = OpenWatchlists(kite)

# Predefined lists, fully enriched with instrument_token / tick_size / lot_size
nifty50 = ow.nifty50()
banknifty = ow.banknifty()
fno = ow.fno_underlyings()        # derived live from kite.instruments('NFO')

# Composition
banks_with_fno = ow.banknifty() & fno
mid_small = ow.nifty500() - ow.nifty100()
my_universe = (ow.nifty100() | ow.banknifty()) & fno

# Iterate
for item in nifty50:
    print(item.symbol, item.instrument_token, item.tick_size, item.lot_size)

# Hand off to existing Kite-shaped consumers
nifty50.to_kite_format()   # list[dict] in kite.instruments() column shape
nifty50.to_dict()          # {symbol: {...}} dict
```

## Live screeners (v0.2)

Snapshot-based filters and rankings over any `Watchlist` universe, all powered by a single batched `kite.quote()` call. Access via `ow.live`:

```python
ow = OpenWatchlists(kite)
universe = ow.nifty500()                              # or any composed list

# Rankings — strict semantics: gainers > 0%, losers < 0% (never overlap)
ow.live.top_gainers(universe, n=10)
ow.live.top_losers(universe, n=10)
ow.live.top_by_volume(universe, n=10)                 # ranked by today's volume
ow.live.top_by_traded_value(universe, n=10)           # volume × LTP (better liquidity signal)

# Threshold filters
ow.live.gainers_above(universe, percent=2.0)          # %change ≥ 2.0 (inclusive)
ow.live.losers_below(universe, percent=2.0)           # %change ≤ -2.0 (sign-tolerant)

# Day-extreme proximity
ow.live.at_day_high(universe, tolerance_pct=0.1)      # within 0.1% of today's high
ow.live.at_day_low(universe, tolerance_pct=0.1)

# Strict above/below previous close
ow.live.above_prev_close(universe)                    # %change > 0  (excludes flat)
ow.live.below_prev_close(universe)                    # %change < 0

# Raw stats — when you want numbers, not a ranked list
ow.live.snapshot(universe)
# → {"RELIANCE": {"last_price": 1234.5, "change_percent": 2.1, "volume": ..., "ohlc": {...}}, ...}
```

Screener results are regular `Watchlist` objects — `|`, `&`, `-` all compose with the bundled lists:

```python
# Buzzers within F&O
ow.live.top_by_traded_value(ow.fno_underlyings(), n=20)

# Banking gainers that are also F&O
ow.live.top_gainers(ow.banknifty(), n=10) & ow.fno_underlyings()

# Mid-caps that are *not* trading near day's high (counter-trend candidates)
ow.nifty_midcap150() - ow.live.at_day_high(ow.nifty_midcap150())
```

Strict-vs-inclusive at zero: `top_gainers` / `above_prev_close` use **strict** `> 0`, so `top_gainers ∩ top_losers = ∅` is always true. For inclusive `≥ 0` use `gainers_above(universe, 0.0)`.

## Available predefined lists (v0.1)

| Key | Source | Notes |
| --- | --- | --- |
| `nifty50` | NSE | Flagship benchmark |
| `nifty_next50` | NSE | Stocks 51-100 |
| `nifty100` | NSE | Top 100 by free-float mcap |
| `nifty200` | NSE | Top 200 |
| `nifty500` | NSE | Top 500 (~96% of free-float mcap) |
| `nifty_midcap150` | NSE | Mid-cap segment of Nifty 500 |
| `banknifty` | NSE | Bank Nifty constituents |
| `nifty_it` | NSE | IT sector |
| `nifty_pharma` | NSE | Pharma sector |
| `nifty_auto` | NSE | Auto sector |
| `nifty_fmcg` | NSE | FMCG sector |
| `nifty_metal` | NSE | Metal sector |
| `nifty_realty` | NSE | Realty sector |
| `nifty_energy` | NSE | Energy + power |
| `nifty_financial_services` | NSE | Financials |
| `fno_underlyings` | Kite Connect API (live) | Every NSE EQ symbol with F&O contracts |

`ow.available()` returns the keys; `ow.metadata(key)` returns descriptive metadata.

## Composition

Every list returns a `Watchlist` — an ordered, deduplicated collection that supports:

```python
a | b   # Union (preserves order: left first, then unique items from right)
a & b   # Intersection (left's order)
a - b   # Difference
a ^ b   # Symmetric difference
a.filter(lambda item: item.lot_size > 0)
a.map(fn)
```

Equality and set operations are keyed on `(exchange, tradingsymbol)`, so the same symbol on NSE vs BSE stays distinct.

## Working offline

`OpenWatchlists()` works without a Kite instance — predefined lists still return their constituent symbols, just without enrichment (`instrument_token`, `tick_size`, `lot_size` are `None` / defaults). Useful for testing, CI, or simple symbol-set arithmetic.

```python
from open_watchlists import OpenWatchlists

ow = OpenWatchlists()
overlap = ow.nifty50() & ow.banknifty()
print(overlap.symbols)
```

## Refreshing bundled NSE data

NSE reviews index composition roughly twice a year (March / September). The package ships a snapshot; refresh it whenever you need the latest:

```bash
open-watchlists-update
```

The CLI re-downloads each list's source CSV directly from `archives.nseindia.com` and rewrites the bundled `.txt` files in your installed package.

## What this library does NOT do

By design:

- **No Kite Web scraping.** Nothing hits `kite.zerodha.com` outside of `KiteConnect`'s documented endpoints.
- **No enctoken / CSRF tokens.** Pure Kite Connect bearer-token auth.
- **No historical-data-backed screeners** *(yet)*. 52-week high/low, 20-day H/L, moving averages, RSI, etc. all need `kite.historical_data()` calls per symbol — different rate-limit profile, different caching story. Coming in v0.3.
- **No BSE support yet.** v0.1 is NSE-only, mirroring most retail algo use cases.

## Architecture

```
OpenWatchlists(kite)
    ├── ow.<list_name>()  → Watchlist
    │       reads bundled data/<list>.txt
    │       enriches against kite.instruments() (cached)
    │
    ├── ow.fno_underlyings()  → Watchlist
    │       reads kite.instruments('NFO')
    │       extracts unique 'name' field from FUT rows
    │       enriches against NSE EQ
    │
    └── ow.get(key)  → generic accessor for any key in available()
```

The `kite.instruments()` call is made at most once per `OpenWatchlists` instance and cached. Pass `instruments=<pre-fetched-list>` to the constructor to share a cache across instances.

## Compatibility

Works with anything exposing a `instruments(exchange=None) -> list[dict]` method — the official [`kiteconnect`](https://pypi.org/project/kiteconnect/) package, in-house wrappers, mocks for testing, etc. Python 3.9+.

## License

MIT. See [LICENSE](LICENSE).
