"""Tests for the live screener layer.

Uses a hand-rolled FakeKite with predictable quote payloads — no network IO,
no kiteconnect dependency. The quote shapes mirror Kite Connect's documented
response: last_price, volume, ohlc{open,high,low,close}, average_price.
"""
import pytest

from open_watchlists import OpenWatchlists, Watchlist, WatchlistItem


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def make_quote(last_price, prev_close, volume, day_high=None, day_low=None):
    """Build a Kite-shaped quote dict for testing."""
    return {
        "last_price": last_price,
        "volume": volume,
        "ohlc": {
            "open": prev_close,
            "high": day_high if day_high is not None else max(last_price, prev_close),
            "low": day_low if day_low is not None else min(last_price, prev_close),
            "close": prev_close,
        },
        "average_price": last_price,
    }


# A 5-stock universe with deterministic quote data:
#   RELIANCE: +5% (gainer, big volume)
#   TCS:      +2%
#   INFY:     -1%
#   HDFCBANK: -3% (loser)
#   ITC:      0%  (at prev close)
QUOTES = {
    "NSE:RELIANCE": make_quote(last_price=1050.0, prev_close=1000.0, volume=1_000_000, day_high=1055.0, day_low=999.0),
    "NSE:TCS":      make_quote(last_price=4080.0, prev_close=4000.0, volume=200_000,  day_high=4100.0, day_low=3990.0),
    "NSE:INFY":     make_quote(last_price=1485.0, prev_close=1500.0, volume=500_000,  day_high=1510.0, day_low=1480.0),
    "NSE:HDFCBANK": make_quote(last_price=1455.0, prev_close=1500.0, volume=750_000,  day_high=1499.0, day_low=1450.0),
    "NSE:ITC":      make_quote(last_price=450.0,  prev_close=450.0,  volume=100_000,  day_high=455.0,  day_low=445.0),
}


def _instrument_row(symbol, token):
    return {
        "instrument_token": token,
        "tradingsymbol": symbol,
        "name": symbol,
        "tick_size": 0.05,
        "lot_size": 1,
        "instrument_type": "EQ",
        "segment": "NSE",
        "exchange": "NSE",
    }


INSTRUMENTS = [
    _instrument_row("RELIANCE", 738561),
    _instrument_row("TCS",      2953217),
    _instrument_row("INFY",     408065),
    _instrument_row("HDFCBANK", 341249),
    _instrument_row("ITC",      424961),
]


class FakeKite:
    """Implements just the methods OpenWatchlists / LiveScreener call."""

    def __init__(self, instruments, quotes):
        self._instruments = instruments
        self._quotes = quotes
        self.quote_calls = 0

    def instruments(self, exchange=None):
        if exchange is None:
            return self._instruments
        return [i for i in self._instruments if i["exchange"] == exchange]

    def quote(self, keys):
        self.quote_calls += 1
        return {k: self._quotes[k] for k in keys if k in self._quotes}


@pytest.fixture
def kite():
    return FakeKite(INSTRUMENTS, QUOTES)


@pytest.fixture
def ow(kite):
    return OpenWatchlists(kite)


@pytest.fixture
def universe(ow):
    """The 5-stock universe matching our quote fixture."""
    items = [WatchlistItem(s) for s in ("RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC")]
    return Watchlist(items, name="test_universe")


# ----------------------------------------------------------------------
# Snapshot
# ----------------------------------------------------------------------


def test_snapshot_returns_quote_data_keyed_by_symbol(ow, universe):
    snap = ow.live.snapshot(universe)
    assert set(snap.keys()) == {"RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC"}
    assert snap["RELIANCE"]["last_price"] == 1050.0
    assert snap["RELIANCE"]["volume"] == 1_000_000
    assert snap["RELIANCE"]["change_percent"] == pytest.approx(5.0)
    assert snap["INFY"]["change_percent"] == pytest.approx(-1.0)
    assert snap["ITC"]["change_percent"] == pytest.approx(0.0)


def test_snapshot_uses_single_quote_call(ow, universe, kite):
    kite.quote_calls = 0
    ow.live.snapshot(universe)
    assert kite.quote_calls == 1


# ----------------------------------------------------------------------
# Top gainers / losers
# ----------------------------------------------------------------------


def test_top_gainers_ranked_high_to_low(ow, universe):
    """top_gainers is strict: only %change > 0. ITC at 0% is excluded."""
    gainers = ow.live.top_gainers(universe, n=3)
    assert gainers.symbols == ["RELIANCE", "TCS"]  # +5%, +2% — ITC excluded


def test_top_losers_ranked_low_to_high(ow, universe):
    losers = ow.live.top_losers(universe, n=2)
    assert losers.symbols == ["HDFCBANK", "INFY"]  # -3%, -1%


def test_top_gainers_excludes_unchanged_and_losers(ow, universe):
    """No matter how generous n is, top_gainers never includes 0% or negative."""
    gainers = ow.live.top_gainers(universe, n=100)
    assert gainers.symbols == ["RELIANCE", "TCS"]


def test_gainers_and_losers_are_disjoint(ow, universe):
    """Strict semantics: a stock is never simultaneously a gainer and a loser."""
    g = set(ow.live.top_gainers(universe, n=100).symbols)
    l = set(ow.live.top_losers(universe, n=100).symbols)
    assert g & l == set()


def test_top_gainers_name_carries_universe_and_params(ow, universe):
    gainers = ow.live.top_gainers(universe, n=3)
    assert "test_universe" in gainers.name
    assert "n=3" in gainers.name


# ----------------------------------------------------------------------
# Threshold filters
# ----------------------------------------------------------------------


def test_gainers_above_threshold(ow, universe):
    above_2pct = ow.live.gainers_above(universe, percent=2.0)
    # RELIANCE +5, TCS +2 qualify
    assert above_2pct.symbols == ["RELIANCE", "TCS"]


def test_gainers_above_zero_includes_unchanged(ow, universe):
    above_0 = ow.live.gainers_above(universe, percent=0.0)
    # +5, +2, 0 qualify (>= 0); -1, -3 don't
    assert set(above_0.symbols) == {"RELIANCE", "TCS", "ITC"}


def test_losers_below_normalizes_sign(ow, universe):
    """losers_below(2) and losers_below(-2) should behave identically."""
    a = ow.live.losers_below(universe, percent=2.0).symbols
    b = ow.live.losers_below(universe, percent=-2.0).symbols
    assert a == b == ["HDFCBANK"]  # only -3% qualifies as <= -2%


def test_above_prev_close_is_strict(ow, universe):
    """above_prev_close uses strict > 0 — ITC at exactly 0% is NOT above."""
    above = ow.live.above_prev_close(universe)
    assert set(above.symbols) == {"RELIANCE", "TCS"}


def test_below_prev_close_is_strict(ow, universe):
    """below_prev_close uses strict < 0 — ITC at 0% is NOT below."""
    below = ow.live.below_prev_close(universe)
    assert set(below.symbols) == {"INFY", "HDFCBANK"}


def test_above_prev_close_and_gainers_above_zero_differ(ow, universe):
    """gainers_above(0) is inclusive (>= 0) — includes ITC at 0%.
    above_prev_close is strict (> 0) — excludes ITC."""
    inclusive = set(ow.live.gainers_above(universe, 0.0).symbols)
    strict = set(ow.live.above_prev_close(universe).symbols)
    assert inclusive == {"RELIANCE", "TCS", "ITC"}
    assert strict == {"RELIANCE", "TCS"}
    assert "ITC" in inclusive - strict


# ----------------------------------------------------------------------
# Volume / liquidity
# ----------------------------------------------------------------------


def test_top_by_volume(ow, universe):
    top_vol = ow.live.top_by_volume(universe, n=3)
    # RELIANCE 1M, HDFCBANK 750k, INFY 500k
    assert top_vol.symbols == ["RELIANCE", "HDFCBANK", "INFY"]


def test_top_by_traded_value(ow, universe):
    """Traded value = volume × LTP. Ordering can differ from raw volume."""
    top_value = ow.live.top_by_traded_value(universe, n=3)
    # RELIANCE: 1M × 1050 = 1.05B
    # HDFCBANK: 750k × 1455 = ~1.09B  <- bigger than RELIANCE!
    # TCS:      200k × 4080 = ~816M
    # INFY:     500k × 1485 = ~742M
    # ITC:      100k × 450 = 45M
    assert top_value.symbols == ["HDFCBANK", "RELIANCE", "TCS"]


# ----------------------------------------------------------------------
# Day-extreme proximity
# ----------------------------------------------------------------------


def test_at_day_high_finds_items_at_top(ow):
    """HDFCBANK LTP 1455 vs day high 1499 → ~2.94% gap. RELIANCE LTP 1050
    vs day high 1055 → ~0.47% gap. With tolerance 1%, only RELIANCE qualifies."""
    items = [WatchlistItem("RELIANCE"), WatchlistItem("HDFCBANK")]
    universe = Watchlist(items, name="u")
    near_high = ow.live.at_day_high(universe, tolerance_pct=1.0)
    assert near_high.symbols == ["RELIANCE"]


def test_at_day_low_finds_items_at_bottom(ow):
    """RELIANCE LTP 1050 vs day low 999 → ~5.1% from low.
    HDFCBANK LTP 1455 vs day low 1450 → ~0.34% from low.
    With tolerance 1%, only HDFCBANK qualifies."""
    items = [WatchlistItem("RELIANCE"), WatchlistItem("HDFCBANK")]
    universe = Watchlist(items, name="u")
    near_low = ow.live.at_day_low(universe, tolerance_pct=1.0)
    assert near_low.symbols == ["HDFCBANK"]


# ----------------------------------------------------------------------
# Composition with v0.1 set ops
# ----------------------------------------------------------------------


def test_screener_output_is_composable_with_set_ops(ow, universe):
    """Screener results are plain Watchlists, so | & - all just work."""
    gainers = ow.live.top_gainers(universe, n=10)  # strict > 0: RELI, TCS
    losers = ow.live.top_losers(universe, n=10)    # strict < 0: HDFCBANK, INFY
    union = gainers | losers
    assert set(union.symbols) == {"RELIANCE", "TCS", "HDFCBANK", "INFY"}
    overlap = gainers & losers
    assert len(overlap) == 0  # strict semantics guarantee no overlap


# ----------------------------------------------------------------------
# Error handling
# ----------------------------------------------------------------------


def test_offline_mode_raises_clear_error():
    ow_offline = OpenWatchlists()  # no kite
    universe = Watchlist([WatchlistItem("RELIANCE")], name="u")
    with pytest.raises(ValueError, match="authenticated kite"):
        ow_offline.live.top_gainers(universe, n=5)


def test_missing_quote_data_drops_symbol_silently(ow):
    """Symbols absent from the kite.quote() response don't break the screener."""
    universe = Watchlist(
        [WatchlistItem("RELIANCE"), WatchlistItem("NONEXISTENT")],
        name="u",
    )
    gainers = ow.live.top_gainers(universe, n=5)
    assert gainers.symbols == ["RELIANCE"]


def test_quote_failure_yields_empty_snapshot():
    """If kite.quote() raises, snapshot returns {} rather than propagating."""

    class FailingKite(FakeKite):
        def quote(self, keys):
            raise RuntimeError("network down")

    failing = FailingKite(INSTRUMENTS, QUOTES)
    ow_failing = OpenWatchlists(failing)
    universe = Watchlist([WatchlistItem("RELIANCE")], name="u")
    snap = ow_failing.live.snapshot(universe)
    assert snap == {}


def test_live_property_caches_instance(ow):
    """Repeated access returns the same LiveScreener — no per-call allocation."""
    assert ow.live is ow.live
