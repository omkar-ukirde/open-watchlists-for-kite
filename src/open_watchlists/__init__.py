"""Composable, official-source-only predefined watchlists for Zerodha Kite Connect.

Quick start::

    from kiteconnect import KiteConnect
    from open_watchlists import OpenWatchlists

    kite = KiteConnect(api_key="...")
    kite.set_access_token("...")

    ow = OpenWatchlists(kite)

    # Predefined lists (return Watchlist objects)
    nifty50 = ow.nifty50()
    banknifty = ow.banknifty()
    fno = ow.fno_underlyings()       # derived live from kite.instruments('NFO')

    # Set operations
    nifty50_in_fno = nifty50 & fno
    mid_small = ow.nifty500() - ow.nifty100()
    banking_fno = ow.banknifty() & fno

    # Iterate / consume
    for item in nifty50:
        print(item.symbol, item.instrument_token, item.tick_size)

    # Hand off to existing Kite-shaped consumers
    nifty50.to_kite_format()   # list[dict] in kite.instruments() shape
    nifty50.to_dict()          # {symbol: {...}} dict

This library does NOT scrape Kite Web internal endpoints or use enctoken /
CSRF based access. Every datapoint is sourced from Zerodha's documented
``KiteConnect.instruments()`` API or NSE-published index CSVs.
"""

from .source import OpenWatchlists
from .watchlist import Watchlist, WatchlistItem

__version__ = "0.3.0"
__all__ = ["OpenWatchlists", "Watchlist", "WatchlistItem", "__version__"]
