# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-05-14

### Added

- **Live fetch mode** — `OpenWatchlists` now defaults to `live=True`, meaning each call to `get(key)` / `nifty50()` / etc. hits the NSE archive URL on first access (cached per-instance for the lifetime of the object). On network failure, falls back to the bundled snapshot when one exists. Pass `live=False` for fully offline / deterministic test runs.
- **8 new Nifty index families** (live-only — no bundled snapshot, fetched fresh from NSE):
  - `nifty_midcap50` (50)
  - `nifty_smallcap50` (50)
  - `nifty_smallcap100` (100)
  - `nifty_smallcap250` (250)
  - `nifty_midsmallcap400` (Midcap 150 ∪ Smallcap 250)
  - `nifty_largemidcap250` (Nifty 100 ∪ Midcap 150)
  - `nifty_microcap250` (250 beyond Nifty 500)
  - `nifty_totalmarket` (Nifty 500 ∪ Microcap 250)
- Named accessor methods for each of the above (`ow.nifty_midcap50()`, etc.).

### Fixed

- **`fno_underlyings()` no longer leaks index names** like `NIFTY` / `BANKNIFTY` / `FINNIFTY` / `MIDCPNIFTY` / `NIFTYNXT50`. Previously, every unique `name` from NFO `FUT` rows was returned — but index futures share a `name` with the index itself, which has no NSE EQ counterpart you can buy as a single share. Now cross-referenced against the NSE EQ instruments dump and filtered to underlyings that exist as `instrument_type == 'EQ'`.

### Changed

- Manifest entries can now omit the `file` field for live-only lists (no bundled snapshot required).
- Existing tests updated to construct `OpenWatchlists(live=False)` so the suite stays deterministic and offline-safe.

### Notes

- This is a soft-breaking change for any caller that relied on `fno_underlyings()` returning index names. If you actually wanted those, query `kite.instruments('NFO')` directly — that's the right tool.
- Zero new runtime dependencies. Live fetch uses stdlib `urllib`.

## [0.2.0] - 2026-05-14

### Added

- **Live screeners** (`OpenWatchlists.live`) — runtime, `kite.quote()`-backed filters and rankings over any `Watchlist` universe:
  - `top_gainers(universe, n)` / `top_losers(universe, n)` — strict `>0` / `<0` `%change` rankings.
  - `gainers_above(universe, percent)` / `losers_below(universe, percent)` — inclusive threshold filters.
  - `top_by_volume(universe, n)` — ranked by today's traded quantity.
  - `top_by_traded_value(universe, n)` — ranked by today's traded value (volume × LTP); better liquidity proxy.
  - `at_day_high(universe, tolerance_pct)` / `at_day_low(universe, tolerance_pct)` — proximity to today's intraday extremes.
  - `above_prev_close(universe)` / `below_prev_close(universe)` — strict comparison to yesterday's close.
  - `snapshot(universe)` — `{symbol: {last_price, change_percent, volume, ohlc, average_price}}` dict in one batched call.
- Live screener results are regular `Watchlist` objects — set operations (`|`, `&`, `-`, `^`) and filters compose with v0.1 lists out of the box.
- Single batched `kite.quote()` fetch per screener call (up to 500 instruments per batch; larger universes split automatically).
- 22 new tests covering ranking semantics, threshold edge cases, strict-vs-inclusive boundary at 0%, missing-quote handling, and `kite.quote()` failure modes.

### Changed

- Strict semantics for `top_gainers` / `top_losers`: items at exactly 0% are excluded from both, guaranteeing `top_gainers ∩ top_losers = ∅`.
- `above_prev_close` / `below_prev_close` use strict `>` / `<` comparison (was inclusive). Use `gainers_above(universe, 0.0)` for inclusive `>= 0` semantics.

### Notes

- Historical-data-backed screeners (52-week H/L, 20-day H/L, DMAs) are intentionally **not** in v0.2 — they require `kite.historical_data()` per symbol, which has different rate-limit characteristics. Coming in v0.3.

## [0.1.0] - 2026-05-13

### Added

- Initial public release.
- 15 bundled NSE predefined watchlists: `nifty50`, `nifty_next50`, `nifty100`, `nifty200`, `nifty500`, `nifty_midcap150`, `banknifty`, and 8 sectoral indices (IT, Pharma, Auto, FMCG, Metal, Realty, Energy, Financial Services).
- `fno_underlyings()` — derived live from `kite.instruments('NFO')`.
- `Watchlist` class with `|`, `&`, `-`, `^`, `filter`, `map`, `to_dict`, `to_kite_format`.
- `WatchlistItem` mirroring Kite's instruments-dump shape.
- Offline mode — works without an authenticated Kite instance (un-enriched items).
- `open-watchlists-update` CLI to refresh bundled constituents from NSE archives.
- 27 tests, MIT licensed.
