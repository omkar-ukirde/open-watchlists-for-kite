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
    """Duck-typed stand-in for KiteConnect — only exposes what OpenWatchlists uses."""

    def __init__(self, all_instruments, nfo_instruments=None):
        self._all = all_instruments
        self._nfo = nfo_instruments or []

    def instruments(self, exchange=None):
        if exchange is None:
            return self._all
        if exchange == "NFO":
            return self._nfo
        return [i for i in self._all if i.get("exchange") == exchange]


def test_offline_mode_returns_unenriched_stubs():
    ow = OpenWatchlists()
    wl = ow.nifty50()
    assert len(wl) > 0
    for item in wl:
        assert item.instrument_token is None
        assert item.exchange == "NSE"


def test_enrichment_with_pre_loaded_instruments():
    ow = OpenWatchlists(instruments=fake_instruments())
    wl = ow.nifty50()
    items_by_sym = {i.symbol: i for i in wl}
    assert items_by_sym["RELIANCE"].instrument_token == 738561
    assert items_by_sym["RELIANCE"].name == "RELIANCE INDUSTRIES"
    assert items_by_sym["TCS"].instrument_token == 2953217


def test_enrichment_with_kite_duck_type():
    kite = FakeKite(fake_instruments())
    ow = OpenWatchlists(kite)
    wl = ow.nifty50()
    items_by_sym = {i.symbol: i for i in wl}
    assert items_by_sym["RELIANCE"].instrument_token == 738561


def test_available_includes_core_lists():
    ow = OpenWatchlists()
    available = ow.available()
    for key in ("nifty50", "nifty100", "nifty500", "banknifty", "nifty_it"):
        assert key in available, f"missing {key!r}"


def test_get_unknown_list_raises():
    ow = OpenWatchlists()
    with pytest.raises(KeyError):
        ow.get("nifty_doesnt_exist")


def test_named_accessors_match_get():
    ow = OpenWatchlists()
    assert ow.nifty50().symbols == ow.get("nifty50").symbols
    assert ow.banknifty().symbols == ow.get("banknifty").symbols
    assert ow.nifty_it().symbols == ow.get("nifty_it").symbols


def test_nifty_hierarchy_subset_relationships():
    """NSE definition: Nifty 50 ⊆ Nifty 100 ⊆ Nifty 200 ⊆ Nifty 500."""
    ow = OpenWatchlists()
    n50 = set(ow.nifty50().symbols)
    n100 = set(ow.nifty100().symbols)
    n200 = set(ow.nifty200().symbols)
    n500 = set(ow.nifty500().symbols)
    assert n50 <= n100
    assert n100 <= n200
    assert n200 <= n500


def test_set_op_across_real_lists():
    ow = OpenWatchlists()
    n50 = ow.nifty50()
    banks = ow.banknifty()
    overlap = n50 & banks
    # Several Nifty 50 banks should be in Bank Nifty
    assert "HDFCBANK" in overlap.symbols
    assert "ICICIBANK" in overlap.symbols


def test_fno_underlyings_offline_returns_empty():
    ow = OpenWatchlists()
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
    ow = OpenWatchlists(kite)
    fno = ow.fno_underlyings()
    # Only FUT instruments contribute to underlyings, CE/PE are ignored
    assert set(fno.symbols) == {"RELIANCE", "TCS"}


def test_metadata_exposes_source_url():
    ow = OpenWatchlists()
    meta = ow.metadata("nifty50")
    assert meta["name"] == "Nifty 50"
    assert "nseindia.com" in meta["source_url"]
