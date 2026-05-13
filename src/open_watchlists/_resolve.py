"""Symbol → WatchlistItem resolution against Kite's instruments dump.

The shapes used here exactly match ``KiteConnect.instruments()`` output:
each row is a dict with keys ``instrument_token``, ``tradingsymbol``,
``name``, ``tick_size``, ``lot_size``, ``segment``, ``exchange``,
``instrument_type``. That's the API contract documented at
https://kite.trade/docs/connect/v3/market-data-and-instruments/.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from .watchlist import WatchlistItem


def build_instruments_index(instruments: Iterable[Dict]) -> Dict[Tuple[str, str], Dict]:
    """Index a Kite instruments-dump iterable by ``(exchange, tradingsymbol)``."""
    index: Dict[Tuple[str, str], Dict] = {}
    for inst in instruments:
        ex = str(inst.get("exchange") or "").strip().upper()
        sym = str(inst.get("tradingsymbol") or "").strip().upper()
        if not ex or not sym:
            continue
        index[(ex, sym)] = inst
    return index


def resolve_symbols(
    symbols: Iterable[str],
    instruments_index: Dict[Tuple[str, str], Dict],
    exchange: str = "NSE",
) -> List[WatchlistItem]:
    """Enrich each symbol with Kite metadata. Symbols absent from the
    index are still returned, with ``instrument_token=None`` — so callers
    can detect mismatches without losing count parity with the source list."""
    items: List[WatchlistItem] = []
    ex_upper = exchange.strip().upper()
    for sym in symbols:
        sym_u = str(sym).strip().upper()
        if not sym_u:
            continue
        info = instruments_index.get((ex_upper, sym_u))
        if info is None:
            items.append(WatchlistItem(symbol=sym_u, exchange=ex_upper))
            continue
        token_raw = info.get("instrument_token")
        try:
            token = int(token_raw) if token_raw not in (None, "") else None
        except (TypeError, ValueError):
            token = None
        try:
            tick = float(info.get("tick_size") or 0.05)
        except (TypeError, ValueError):
            tick = 0.05
        try:
            lot = int(info.get("lot_size") or 1)
        except (TypeError, ValueError):
            lot = 1
        items.append(
            WatchlistItem(
                symbol=sym_u,
                instrument_token=token,
                name=str(info.get("name") or ""),
                segment=str(info.get("segment") or ""),
                tick_size=tick,
                lot_size=lot,
                exchange=ex_upper,
            )
        )
    return items
