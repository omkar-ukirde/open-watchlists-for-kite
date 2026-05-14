"""Basic end-to-end example.

Run after installing the package and obtaining a Kite Connect access_token::

    pip install open-watchlists-for-kite kiteconnect
    python examples/basic_usage.py

Set KITE_API_KEY and KITE_ACCESS_TOKEN in your environment before running.
"""
from __future__ import annotations

import os

from kiteconnect import KiteConnect

from open_watchlists import OpenWatchlists


def main() -> None:
    api_key = os.environ["KITE_API_KEY"]
    access_token = os.environ["KITE_ACCESS_TOKEN"]

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    ow = OpenWatchlists(kite)

    print("Available predefined lists:")
    for name in ow.available():
        print(f"  - {name}")

    # ------------------------------------------------------------------
    # Predefined list
    # ------------------------------------------------------------------
    print("\n=== Nifty 50 (first 5) ===")
    nifty50 = ow.nifty50()
    print(f"{len(nifty50)} items")
    for it in list(nifty50)[:5]:
        print(f"  {it.symbol:12} token={it.instrument_token:<10} {it.name}")

    # ------------------------------------------------------------------
    # Live derivation from Kite instruments
    # ------------------------------------------------------------------
    print("\n=== F&O underlyings ===")
    fno = ow.fno_underlyings()
    print(f"{len(fno)} symbols on NFO")

    # ------------------------------------------------------------------
    # Composition — set operations
    # ------------------------------------------------------------------
    print("\n=== Mid/small caps (Nifty 500 minus Nifty 100) ===")
    mid_small = ow.nifty500() - ow.nifty100()
    print(f"{len(mid_small)} symbols")

    print("\n=== Banks with active F&O ===")
    bank_fno = ow.banknifty() & ow.fno_underlyings()
    for it in bank_fno:
        print(f"  {it.symbol:12} tick={it.tick_size} lot={it.lot_size}")

    # ------------------------------------------------------------------
    # Hand off to existing Kite-shaped consumers
    # ------------------------------------------------------------------
    payload = nifty50.to_kite_format()
    print(f"\nFirst Kite-format row: {payload[0]}")

    # ------------------------------------------------------------------
    # v0.2 live screeners — single batched kite.quote() per call
    # ------------------------------------------------------------------
    print("\n=== Top 5 gainers in Nifty 50 (live) ===")
    snapshot = ow.live.snapshot(nifty50)
    for it in ow.live.top_gainers(nifty50, n=5):
        stats = snapshot.get(it.symbol, {})
        chg = stats.get("change_percent")
        if chg is not None:
            print(f"  {it.symbol:12} {chg:+.2f}%  LTP={stats.get('last_price')}")

    print("\n=== Top 5 buzzers (traded value) in F&O ===")
    for it in ow.live.top_by_traded_value(fno, n=5):
        print(f"  {it.symbol}")

    print("\n=== Bank Nifty stocks near day's high ===")
    near_high = ow.live.at_day_high(ow.banknifty(), tolerance_pct=0.5)
    for it in near_high:
        print(f"  {it.symbol}")


if __name__ == "__main__":
    main()
