from open_watchlists import Watchlist, WatchlistItem


def item(sym, **kw):
    return WatchlistItem(symbol=sym, **kw)


def test_normalizes_symbol_and_exchange_case():
    i = WatchlistItem(symbol="reliance", exchange="nse")
    assert i.symbol == "RELIANCE"
    assert i.exchange == "NSE"


def test_dedup_preserves_insertion_order():
    wl = Watchlist([item("RELIANCE"), item("TCS"), item("RELIANCE")])
    assert wl.symbols == ["RELIANCE", "TCS"]
    assert len(wl) == 2


def test_same_symbol_different_exchange_kept():
    wl = Watchlist([
        WatchlistItem("RELIANCE", exchange="NSE"),
        WatchlistItem("RELIANCE", exchange="BSE"),
    ])
    assert len(wl) == 2


def test_union():
    a = Watchlist([item("RELIANCE"), item("TCS")])
    b = Watchlist([item("TCS"), item("INFY")])
    u = a | b
    assert u.symbols == ["RELIANCE", "TCS", "INFY"]


def test_intersection_preserves_left_order():
    a = Watchlist([item("RELIANCE"), item("TCS"), item("INFY")])
    b = Watchlist([item("INFY"), item("TCS"), item("WIPRO")])
    i = a & b
    assert i.symbols == ["TCS", "INFY"]


def test_difference():
    a = Watchlist([item("RELIANCE"), item("TCS"), item("INFY")])
    b = Watchlist([item("TCS")])
    assert (a - b).symbols == ["RELIANCE", "INFY"]


def test_symmetric_difference():
    a = Watchlist([item("A"), item("B")])
    b = Watchlist([item("B"), item("C")])
    assert set((a ^ b).symbols) == {"A", "C"}


def test_contains_is_case_insensitive():
    wl = Watchlist([item("RELIANCE")])
    assert "RELIANCE" in wl
    assert "reliance" in wl
    assert "INFY" not in wl


def test_contains_item_respects_exchange():
    wl = Watchlist([WatchlistItem("RELIANCE", exchange="NSE")])
    assert WatchlistItem("RELIANCE", exchange="NSE") in wl
    assert WatchlistItem("RELIANCE", exchange="BSE") not in wl


def test_filter_keeps_name():
    wl = Watchlist(
        [
            WatchlistItem("RELIANCE", segment="NSE"),
            WatchlistItem("NIFTY26JANFUT", segment="NFO-FUT"),
        ],
        name="mix",
    )
    eq_only = wl.filter(lambda i: i.segment == "NSE")
    assert eq_only.symbols == ["RELIANCE"]
    assert eq_only.name == "mix"


def test_to_dict_round_trip_shape():
    wl = Watchlist([WatchlistItem("RELIANCE", instrument_token=738561, name="RELIANCE INDUSTRIES")])
    d = wl.to_dict()
    assert d["RELIANCE"]["instrument_token"] == 738561
    assert d["RELIANCE"]["name"] == "RELIANCE INDUSTRIES"


def test_to_kite_format_uses_tradingsymbol_key():
    wl = Watchlist([WatchlistItem("RELIANCE", instrument_token=738561)])
    rows = wl.to_kite_format()
    assert len(rows) == 1
    assert rows[0]["tradingsymbol"] == "RELIANCE"
    assert rows[0]["instrument_token"] == 738561


def test_equality_by_keys():
    a = Watchlist([item("A"), item("B")])
    b = Watchlist([item("A"), item("B")])
    assert a == b


def test_repr_pluralization():
    assert "1 item)" in repr(Watchlist([item("RELIANCE")]))
    assert "2 items)" in repr(Watchlist([item("RELIANCE"), item("TCS")]))


def test_set_ops_carry_combined_name():
    a = Watchlist([item("A")], name="alpha")
    b = Watchlist([item("B")], name="beta")
    assert (a | b).name == "(alpha | beta)"
    assert (a & b).name == "(alpha & beta)"
    assert (a - b).name == "(alpha - beta)"


def test_iteration_yields_in_order():
    items = [item("RELIANCE"), item("TCS"), item("INFY")]
    wl = Watchlist(items)
    assert [x.symbol for x in wl] == ["RELIANCE", "TCS", "INFY"]
