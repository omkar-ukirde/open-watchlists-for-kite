"""Tests for OpenWatchlists.

Most tests construct ``OpenWatchlists(live=False)`` so they read the
bundled snapshot and do no network IO — keeps the suite deterministic
and runnable in CI / offline. Live-mode behaviour has its own
dedicated tests with the network call mocked.
"""
from unittest.mock import patch

import pytest

from open_watchlists import OpenWatchlists


def fake_instruments():
    """A minimal kite.instruments() shaped fixture."""
    return [
        {
            "instrument_token": 738561,
            "exchange_token": 2885,
            "tradingsymbol": "RELIANCE",
            "name": "RELIANCE INDUSTRIES",
            "last_price": 0,
            "expiry": "",
            "strike": 0,
            "tick_size": 0.05,
            "lot_size": 1,
            "instrument_type": "EQ",
            "segment": "NSE",
            "exchange": "NSE",
        },
        {
            "instrument_token": 2953217,
            "exchange_token": 11536,
            "tradingsymbol": "TCS",
            "name": "TATA CONSULTANCY SERV LT",
            "last_price": 0,
            "expiry": "",
            "strike": 0,
            "tick_size": 0.05,
            "lot_size": 1,
            "instrument_type": "EQ",
            "segment": "NSE",
            "exchange": "NSE",
        },
    ]


class FakeKite:
    """Duck-typed stand-in for KiteConnect — only exposes what
    OpenWatchlists / LiveScreener call."""

    def __init__(self, all_instruments, nfo_instruments=None):
        self._all = all_instruments
        self._nfo = nfo_instruments or []

    def instruments(self, exchange=None):
        if exchange is None:
            return self._all
        if exchange == "NFO":
            return self._nfo
        return [i for i in self._all if i.get("exchange") == exchange]


# ----------------------------------------------------------------------
# Bundled-snapshot mode (live=False) — deterministic, no network
# ----------------------------------------------------------------------


def test_offline_mode_returns_unenriched_stubs():
    ow = OpenWatchlists(live=False)
    wl = ow.nifty50()
    assert len(wl) > 0
    for item in wl:
        assert item.instrument_token is None
        assert item.exchange == "NSE"


def test_enrichment_with_pre_loaded_instruments():
    ow = OpenWatchlists(instruments=fake_instruments(), live=False)
    wl = ow.nifty50()
    items_by_sym = {i.symbol: i for i in wl}
    assert items_by_sym["RELIANCE"].instrument_token == 738561
    assert items_by_sym["RELIANCE"].name == "RELIANCE INDUSTRIES"
    assert items_by_sym["TCS"].instrument_token == 2953217


def test_enrichment_with_kite_duck_type():
    kite = FakeKite(fake_instruments())
    ow = OpenWatchlists(kite, live=False)
    wl = ow.nifty50()
    items_by_sym = {i.symbol: i for i in wl}
    assert items_by_sym["RELIANCE"].instrument_token == 738561


def test_available_includes_core_lists():
    ow = OpenWatchlists(live=False)
    available = ow.available()
    for key in ("nifty50", "nifty100", "nifty500", "banknifty", "nifty_it"):
        assert key in available, f"missing {key!r}"


def test_available_includes_v0_3_indices():
    """v0.3 added the broader Nifty index family (live-only entries)."""
    ow = OpenWatchlists(live=False)
    available = ow.available()
    for key in (
        "nifty_midcap50",
        "nifty_smallcap50",
        "nifty_smallcap100",
        "nifty_smallcap250",
        "nifty_midsmallcap400",
        "nifty_largemidcap250",
        "nifty_microcap250",
        "nifty_totalmarket",
    ):
        assert key in available, f"missing {key!r}"


def test_get_unknown_list_raises():
    ow = OpenWatchlists(live=False)
    with pytest.raises(KeyError):
        ow.get("nifty_doesnt_exist")


def test_named_accessors_match_get():
    ow = OpenWatchlists(live=False)
    assert ow.nifty50().symbols == ow.get("nifty50").symbols
    assert ow.banknifty().symbols == ow.get("banknifty").symbols
    assert ow.nifty_it().symbols == ow.get("nifty_it").symbols


def test_nifty_hierarchy_subset_relationships():
    """NSE definition: Nifty 50 ⊆ Nifty 100 ⊆ Nifty 200 ⊆ Nifty 500."""
    ow = OpenWatchlists(live=False)
    n50 = set(ow.nifty50().symbols)
    n100 = set(ow.nifty100().symbols)
    n200 = set(ow.nifty200().symbols)
    n500 = set(ow.nifty500().symbols)
    assert n50 <= n100
    assert n100 <= n200
    assert n200 <= n500


def test_set_op_across_real_lists():
    ow = OpenWatchlists(live=False)
    n50 = ow.nifty50()
    banks = ow.banknifty()
    overlap = n50 & banks
    assert "HDFCBANK" in overlap.symbols
    assert "ICICIBANK" in overlap.symbols


def test_fno_underlyings_offline_returns_empty():
    ow = OpenWatchlists(live=False)
    fno = ow.fno_underlyings()
    assert len(fno) == 0


def test_fno_underlyings_from_kite():
    nfo = [
        {
            "instrument_token": 1,
            "tradingsymbol": "RELIANCE26JANFUT",
            "name": "RELIANCE",
            "instrument_type": "FUT",
            "segment": "NFO-FUT",
            "exchange": "NFO",
            "tick_size": 0.05,
            "lot_size": 250,
        },
        {
            "instrument_token": 2,
            "tradingsymbol": "RELIANCE26JAN3000CE",
            "name": "RELIANCE",
            "instrument_type": "CE",
            "segment": "NFO-OPT",
            "exchange": "NFO",
            "tick_size": 0.05,
            "lot_size": 250,
        },
        {
            "instrument_token": 3,
            "tradingsymbol": "TCS26JANFUT",
            "name": "TCS",
            "instrument_type": "FUT",
            "segment": "NFO-FUT",
            "exchange": "NFO",
            "tick_size": 0.05,
            "lot_size": 175,
        },
    ]
    kite = FakeKite(fake_instruments(), nfo_instruments=nfo)
    ow = OpenWatchlists(kite, live=False)
    fno = ow.fno_underlyings()
    assert set(fno.symbols) == {"RELIANCE", "TCS"}


def test_fno_underlyings_drops_index_underlyings():
    """Indices like NIFTY / BANKNIFTY / FINNIFTY have FUT contracts but
    no EQ-tradable instrument. They MUST be filtered out — otherwise
    they leak into the user's equity watchlist where you can't buy a
    single share. This is the v0.3.0 fix."""
    nfo = [
        {
            "tradingsymbol": "RELIANCE26JANFUT",
            "name": "RELIANCE",
            "instrument_type": "FUT",
            "exchange": "NFO",
        },
        {
            "tradingsymbol": "NIFTY26JANFUT",
            "name": "NIFTY",
            "instrument_type": "FUT",
            "exchange": "NFO",
        },
        {
            "tradingsymbol": "BANKNIFTY26JANFUT",
            "name": "BANKNIFTY",
            "instrument_type": "FUT",
            "exchange": "NFO",
        },
        {
            "tradingsymbol": "FINNIFTY26JANFUT",
            "name": "FINNIFTY",
            "instrument_type": "FUT",
            "exchange": "NFO",
        },
        {
            "tradingsymbol": "MIDCPNIFTY26JANFUT",
            "name": "MIDCPNIFTY",
            "instrument_type": "FUT",
            "exchange": "NFO",
        },
    ]
    # fake_instruments() only has RELIANCE and TCS as NSE EQ — none of
    # the indices have an EQ entry, so they should all be filtered.
    kite = FakeKite(fake_instruments(), nfo_instruments=nfo)
    ow = OpenWatchlists(kite, live=False)
    fno = ow.fno_underlyings()
    assert "RELIANCE" in fno.symbols
    for index_name in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"):
        assert index_name not in fno.symbols, f"index {index_name} leaked into F&O underlyings"


def test_metadata_exposes_source_url():
    ow = OpenWatchlists(live=False)
    meta = ow.metadata("nifty50")
    assert meta["name"] == "Nifty 50"
    assert "nseindia.com" in meta["source_url"]


# ----------------------------------------------------------------------
# Live-fetch mode — network mocked via urllib.request.urlopen
# ----------------------------------------------------------------------


def _fake_urlopen_factory(csv_body: str):
    """Build a context-manager-compatible urlopen replacement that
    returns the given CSV bytes regardless of URL."""
    class _FakeResp:
        def __init__(self, body):
            self._body = body.encode("utf-8")
        def read(self):
            return self._body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    def _fake(req, timeout=None):
        return _FakeResp(csv_body)
    return _fake


def test_live_mode_fetches_from_nse():
    """In live mode, ``get`` calls urlopen instead of reading bundled file."""
    fake_csv = "Company Name,Industry,Symbol,Series,ISIN Code\n" \
               "Foo Ltd,Tech,FOO,EQ,INE000A01000\n" \
               "Bar Ltd,Tech,BAR,EQ,INE000A02000\n"
    with patch(
        "open_watchlists._data.urllib.request.urlopen",
        _fake_urlopen_factory(fake_csv),
    ):
        ow = OpenWatchlists(live=True)
        wl = ow.nifty50()
        # The mocked CSV returns FOO and BAR, not the bundled Nifty 50
        # constituents — proves the live fetch ran and won.
        assert wl.symbols == ["FOO", "BAR"]


def test_live_mode_falls_back_to_bundled_on_network_error():
    """If urlopen raises, we fall through to the bundled snapshot."""
    def _failing_urlopen(req, timeout=None):
        raise OSError("simulated network failure")
    with patch(
        "open_watchlists._data.urllib.request.urlopen",
        _failing_urlopen,
    ):
        ow = OpenWatchlists(live=True)
        wl = ow.nifty50()
        # We got SOMETHING — the bundled 50-stock snapshot.
        assert len(wl) > 0
        assert "RELIANCE" in wl.symbols  # known bundled-snapshot member


def test_live_mode_caches_within_instance():
    """Two calls for the same list_key should make only one HTTP call."""
    fake_csv = "Symbol\nFOO\nBAR\n"
    call_count = {"n": 0}
    def _counting_urlopen(req, timeout=None):
        call_count["n"] += 1
        class _R:
            def read(self): return fake_csv.encode("utf-8")
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _R()
    with patch(
        "open_watchlists._data.urllib.request.urlopen",
        _counting_urlopen,
    ):
        ow = OpenWatchlists(live=True)
        ow.nifty50()
        ow.nifty50()
        ow.nifty50()
        assert call_count["n"] == 1


def test_live_only_list_works_without_bundled_file():
    """Lists without a bundled .txt (new v0.3 indices) must still work
    in live mode."""
    fake_csv = "Symbol\nSTOCK1\nSTOCK2\nSTOCK3\n"
    with patch(
        "open_watchlists._data.urllib.request.urlopen",
        _fake_urlopen_factory(fake_csv),
    ):
        ow = OpenWatchlists(live=True)
        wl = ow.get("nifty_microcap250")
        assert wl.symbols == ["STOCK1", "STOCK2", "STOCK3"]


def test_live_only_list_fails_clearly_when_offline():
    """Without bundled snapshot AND without network, the user should
    see a clear FileNotFoundError, not a cryptic stacktrace."""
    def _failing(req, timeout=None):
        raise OSError("no network")
    with patch(
        "open_watchlists._data.urllib.request.urlopen",
        _failing,
    ):
        ow = OpenWatchlists(live=True)
        with pytest.raises(FileNotFoundError):
            ow.get("nifty_microcap250")
