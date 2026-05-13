"""Watchlist and WatchlistItem — the core data types.

A Watchlist is an ordered, deduplicated collection of WatchlistItems that
supports set-style composition via ``|`` (union), ``&`` (intersection),
``-`` (difference), and ``^`` (symmetric difference). Equality and set
operations are keyed on ``(exchange, symbol)`` so the same tradingsymbol
on NSE and BSE are treated as distinct instruments.

The class deliberately mirrors Zerodha Kite's instrument shape — every
field on ``WatchlistItem`` maps directly to a column in
``kite.instruments()`` — so a Watchlist can be fed straight into
order placement, GTT creation, or any other Kite Connect call without
adapter glue.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator, List, Optional


@dataclass(frozen=True)
class WatchlistItem:
    """A single instrument, enriched from Kite's instruments dump.

    Fields mirror the columns returned by ``KiteConnect.instruments()``
    so a list of these can be consumed by any Kite-aware code path.
    """

    symbol: str
    instrument_token: Optional[int] = None
    name: str = ""
    segment: str = ""
    tick_size: float = 0.05
    lot_size: int = 1
    exchange: str = "NSE"

    def __post_init__(self) -> None:
        # Normalize symbol/exchange on construction so equality and set
        # operations behave consistently regardless of caller casing.
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "exchange", self.exchange.strip().upper())


class Watchlist:
    """Ordered, deduplicated collection of ``WatchlistItem`` with set ops.

    Set operations preserve the order of the left operand for shared items
    and append items unique to the right operand in their original order.
    """

    __slots__ = ("name", "_items", "_index")

    def __init__(self, items: Iterable[WatchlistItem], name: str = "") -> None:
        self.name = name
        self._items: List[WatchlistItem] = []
        self._index: dict = {}
        for item in items:
            self._add_item(item)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _add_item(self, item: WatchlistItem) -> None:
        key = (item.exchange, item.symbol)
        if key not in self._index:
            self._index[key] = len(self._items)
            self._items.append(item)

    # ------------------------------------------------------------------
    # Iteration / sizing / membership
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[WatchlistItem]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, symbol_or_item: Any) -> bool:
        if isinstance(symbol_or_item, WatchlistItem):
            return (symbol_or_item.exchange, symbol_or_item.symbol) in self._index
        sym = str(symbol_or_item).strip().upper()
        for key in self._index:
            if key[1] == sym:
                return True
        return False

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    @property
    def symbols(self) -> List[str]:
        return [i.symbol for i in self._items]

    @property
    def items(self) -> List[WatchlistItem]:
        return list(self._items)

    # ------------------------------------------------------------------
    # Set algebra
    # ------------------------------------------------------------------

    def _combined_name(self, op: str, other: "Watchlist") -> str:
        if self.name and other.name:
            return f"({self.name} {op} {other.name})"
        return ""

    def __or__(self, other: "Watchlist") -> "Watchlist":
        if not isinstance(other, Watchlist):
            return NotImplemented
        merged = list(self._items)
        seen = set(self._index)
        for item in other._items:
            key = (item.exchange, item.symbol)
            if key not in seen:
                merged.append(item)
                seen.add(key)
        return Watchlist(merged, name=self._combined_name("|", other))

    def __and__(self, other: "Watchlist") -> "Watchlist":
        if not isinstance(other, Watchlist):
            return NotImplemented
        other_keys = set(other._index)
        kept = [i for i in self._items if (i.exchange, i.symbol) in other_keys]
        return Watchlist(kept, name=self._combined_name("&", other))

    def __sub__(self, other: "Watchlist") -> "Watchlist":
        if not isinstance(other, Watchlist):
            return NotImplemented
        other_keys = set(other._index)
        kept = [i for i in self._items if (i.exchange, i.symbol) not in other_keys]
        return Watchlist(kept, name=self._combined_name("-", other))

    def __xor__(self, other: "Watchlist") -> "Watchlist":
        if not isinstance(other, Watchlist):
            return NotImplemented
        return (self - other) | (other - self)

    # ------------------------------------------------------------------
    # Equality / hashing
    # ------------------------------------------------------------------

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Watchlist):
            return NotImplemented
        return list(self._index) == list(other._index)

    def __hash__(self) -> int:
        return hash(tuple(self._index))

    # ------------------------------------------------------------------
    # Filtering / transformation
    # ------------------------------------------------------------------

    def filter(self, predicate: Callable[[WatchlistItem], bool]) -> "Watchlist":
        return Watchlist((i for i in self._items if predicate(i)), name=self.name)

    def map(self, fn: Callable[[WatchlistItem], WatchlistItem]) -> "Watchlist":
        return Watchlist((fn(i) for i in self._items), name=self.name)

    # ------------------------------------------------------------------
    # Serialization — Kite-compatible
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a ``{symbol: {...}}`` dict matching the shape this app's
        existing watchlist consumers (and Kite Connect responses) use."""
        return {
            i.symbol: {
                "symbol": i.symbol,
                "instrument_token": i.instrument_token,
                "name": i.name,
                "segment": i.segment,
                "tick_size": i.tick_size,
                "lot_size": i.lot_size,
                "exchange": i.exchange,
            }
            for i in self._items
        }

    def to_kite_format(self) -> List[dict]:
        """Return a list of dicts in ``kite.instruments()`` column shape."""
        return [
            {
                "instrument_token": i.instrument_token,
                "tradingsymbol": i.symbol,
                "name": i.name,
                "tick_size": i.tick_size,
                "lot_size": i.lot_size,
                "segment": i.segment,
                "exchange": i.exchange,
            }
            for i in self._items
        ]

    def __repr__(self) -> str:
        n = len(self)
        plural = "" if n == 1 else "s"
        if self.name:
            return f"<Watchlist {self.name!r} ({n} item{plural})>"
        return f"<Watchlist ({n} item{plural})>"
