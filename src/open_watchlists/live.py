"""Live, kite.quote()-backed screeners over a Watchlist universe.

Every screener here requires an authenticated kite instance because they
all derive from ``kite.quote()`` — Zerodha's documented endpoint returning
a snapshot of last price, today's OHLC, volume, and previous-day close.

Strictly the documented Kite Connect API surface — no scraping, no
``kite.historical_data()`` (use the historical-data module for that, coming
in v0.3). Single batched fetch per screener call: ``kite.quote()`` accepts
up to 500 instruments, so most universes fit in one call.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .watchlist import Watchlist, WatchlistItem


# Kite Connect's documented quote-batch ceiling. Universes larger than this
# get split into multiple calls; results are merged before ranking.
KITE_QUOTE_BATCH = 500


def _instrument_keys(universe: Watchlist) -> List[str]:
    """Build the ``EXCHANGE:SYMBOL`` keys kite.quote() expects."""
    return [f"{i.exchange}:{i.symbol}" for i in universe]


def _fetch_quotes(kite: Any, universe: Watchlist) -> Dict[str, Dict[str, Any]]:
    """Fetch quotes for every item in the universe.

    Returns ``{symbol: quote_dict}`` keyed by bare tradingsymbol (with the
    ``EXCHANGE:`` prefix stripped). A failing batch is logged-and-skipped
    rather than raised — partial results are more useful than nothing on
    a flaky connection.
    """
    instruments = _instrument_keys(universe)
    if not instruments:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for offset in range(0, len(instruments), KITE_QUOTE_BATCH):
        batch = instruments[offset:offset + KITE_QUOTE_BATCH]
        try:
            quotes = kite.quote(batch)
        except Exception:
            continue
        for k, v in (quotes or {}).items():
            # Kite returns "NSE:RELIANCE"-keyed dict. Re-key on bare symbol
            # because our Watchlist items are keyed that way too.
            symbol = k.split(":", 1)[1] if ":" in k else k
            out[symbol] = v
    return out


def _change_percent(q: Dict[str, Any]) -> Optional[float]:
    """Compute today's %-change from a quote. Returns ``None`` if either the
    last price or yesterday's close is missing / non-positive — we'd rather
    drop the symbol from the ranking than rank it on garbage."""
    try:
        last = float(q.get("last_price") or 0)
        prev_close = float((q.get("ohlc") or {}).get("close") or 0)
    except (TypeError, ValueError):
        return None
    if prev_close <= 0 or last <= 0:
        return None
    return (last - prev_close) / prev_close * 100.0


class LiveScreener:
    """Snapshot-based screeners over a ``Watchlist`` universe.

    Access via ``OpenWatchlists.live`` — not instantiated directly.

    Every method takes a ``Watchlist`` as the universe (any of the v0.1
    predefined lists or composed lists work) and returns a ``Watchlist``
    of items meeting the screen. Ranking-style screens return items in
    rank order; filter-style screens return items in the universe's
    original order.
    """

    def __init__(self, kite: Optional[Any]) -> None:
        self._kite = kite

    # ------------------------------------------------------------------
    # Raw snapshot — useful when you want stats, not a ranked Watchlist
    # ------------------------------------------------------------------

    def snapshot(self, universe: Watchlist) -> Dict[str, Dict[str, Any]]:
        """Return ``{symbol: {last_price, change_percent, volume, ohlc, average_price}}``.

        One batched ``kite.quote()`` pass. Symbols missing from the
        response (illiquid / delisted / typos) are omitted from the result
        rather than emitted with null values.
        """
        self._require_kite()
        quotes = _fetch_quotes(self._kite, universe)
        out: Dict[str, Dict[str, Any]] = {}
        for item in universe:
            q = quotes.get(item.symbol)
            if q is None:
                continue
            out[item.symbol] = {
                "last_price": q.get("last_price"),
                "change_percent": _change_percent(q),
                "volume": q.get("volume"),
                "ohlc": q.get("ohlc"),
                "average_price": q.get("average_price"),
            }
        return out

    # ------------------------------------------------------------------
    # %-change rankings
    # ------------------------------------------------------------------

    def top_gainers(self, universe: Watchlist, n: int = 10) -> Watchlist:
        """Top ``n`` items with strict ``%change > 0`` (high → low).

        A 0%-change stock is neither a gainer nor a loser, so it's
        excluded — making ``top_gainers ∩ top_losers`` always empty,
        which matches what callers usually want from set composition.
        """
        items = self._filter_sort_by_change(universe, lambda cp: cp > 0, descending=True)
        return self._wrap(items[:n], "top_gainers", universe, n=n)

    def top_losers(self, universe: Watchlist, n: int = 10) -> Watchlist:
        """Top ``n`` items with strict ``%change < 0`` (low → high)."""
        items = self._filter_sort_by_change(universe, lambda cp: cp < 0, descending=False)
        return self._wrap(items[:n], "top_losers", universe, n=n)

    def gainers_above(self, universe: Watchlist, percent: float) -> Watchlist:
        """All items with today's %-change ≥ ``percent``, sorted desc.

        Inclusive threshold — pass ``percent=2.0`` to include a stock
        sitting at exactly +2.0%. For the strict ``> 0`` semantics, use
        :meth:`above_prev_close`.
        """
        items = self._filter_sort_by_change(
            universe, lambda cp: cp >= percent, descending=True
        )
        return self._wrap(items, "gainers_above", universe, threshold=f"{percent}%")

    def losers_below(self, universe: Watchlist, percent: float) -> Watchlist:
        """All items with today's %-change ≤ ``-|percent|``, sorted asc
        (most negative first). Sign-tolerant: pass either ``2.0`` or
        ``-2.0`` — both mean "stocks down at least 2%"."""
        threshold = -abs(percent)
        items = self._filter_sort_by_change(
            universe, lambda cp: cp <= threshold, descending=False
        )
        return self._wrap(items, "losers_below", universe, threshold=f"{percent}%")

    def above_prev_close(self, universe: Watchlist) -> Watchlist:
        """All items trading strictly above yesterday's close (``%change > 0``).

        Note this is the strict variant — a stock at exactly 0% is not
        "above" prev close. For the inclusive ``>= 0`` semantics use
        ``gainers_above(universe, 0.0)``.
        """
        items = self._filter_sort_by_change(universe, lambda cp: cp > 0, descending=True)
        return self._wrap(items, "above_prev_close", universe)

    def below_prev_close(self, universe: Watchlist) -> Watchlist:
        """All items trading strictly below yesterday's close (``%change < 0``)."""
        items = self._filter_sort_by_change(universe, lambda cp: cp < 0, descending=False)
        return self._wrap(items, "below_prev_close", universe)

    # ------------------------------------------------------------------
    # Liquidity rankings
    # ------------------------------------------------------------------

    def top_by_volume(self, universe: Watchlist, n: int = 10) -> Watchlist:
        """Top ``n`` items by today's traded quantity (high → low)."""
        self._require_kite()
        quotes = _fetch_quotes(self._kite, universe)
        scored: List[Tuple[int, WatchlistItem]] = []
        for item in universe:
            try:
                vol = int(quotes.get(item.symbol, {}).get("volume") or 0)
            except (TypeError, ValueError):
                continue
            if vol > 0:
                scored.append((vol, item))
        scored.sort(key=lambda t: t[0], reverse=True)
        return self._wrap(
            [it for _, it in scored[:n]],
            "top_by_volume",
            universe,
            n=n,
        )

    def top_by_traded_value(self, universe: Watchlist, n: int = 10) -> Watchlist:
        """Top ``n`` items by today's traded **value** (volume × LTP).

        Better proxy for liquidity than raw volume because it normalizes
        across price levels — 1 lakh shares of a ₹10 stock is not the
        same kind of liquidity as 1 lakh shares of a ₹2000 stock.
        """
        self._require_kite()
        quotes = _fetch_quotes(self._kite, universe)
        scored: List[Tuple[float, WatchlistItem]] = []
        for item in universe:
            q = quotes.get(item.symbol, {})
            try:
                vol = int(q.get("volume") or 0)
                price = float(q.get("last_price") or 0)
            except (TypeError, ValueError):
                continue
            value = vol * price
            if value > 0:
                scored.append((value, item))
        scored.sort(key=lambda t: t[0], reverse=True)
        return self._wrap(
            [it for _, it in scored[:n]],
            "top_by_traded_value",
            universe,
            n=n,
        )

    # ------------------------------------------------------------------
    # Day-extreme proximity
    # ------------------------------------------------------------------

    def at_day_high(self, universe: Watchlist, tolerance_pct: float = 0.1) -> Watchlist:
        """Items whose last price is within ``tolerance_pct`` of today's
        intraday high. Default 0.1% catches stocks 'sitting at high'."""
        self._require_kite()
        quotes = _fetch_quotes(self._kite, universe)
        kept: List[WatchlistItem] = []
        for item in universe:
            q = quotes.get(item.symbol, {})
            try:
                last = float(q.get("last_price") or 0)
                high = float((q.get("ohlc") or {}).get("high") or 0)
            except (TypeError, ValueError):
                continue
            if high <= 0 or last <= 0:
                continue
            gap = (high - last) / high * 100.0
            if gap <= tolerance_pct:
                kept.append(item)
        return self._wrap(kept, "at_day_high", universe, tolerance=f"{tolerance_pct}%")

    def at_day_low(self, universe: Watchlist, tolerance_pct: float = 0.1) -> Watchlist:
        """Items whose last price is within ``tolerance_pct`` of today's
        intraday low."""
        self._require_kite()
        quotes = _fetch_quotes(self._kite, universe)
        kept: List[WatchlistItem] = []
        for item in universe:
            q = quotes.get(item.symbol, {})
            try:
                last = float(q.get("last_price") or 0)
                low = float((q.get("ohlc") or {}).get("low") or 0)
            except (TypeError, ValueError):
                continue
            if low <= 0 or last <= 0:
                continue
            gap = (last - low) / low * 100.0
            if gap <= tolerance_pct:
                kept.append(item)
        return self._wrap(kept, "at_day_low", universe, tolerance=f"{tolerance_pct}%")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_kite(self) -> None:
        if self._kite is None:
            raise ValueError(
                "Live screeners require an authenticated kite instance. "
                "Construct OpenWatchlists(kite=<KiteConnect>) before calling .live methods."
            )

    def _filter_sort_by_change(
        self,
        universe: Watchlist,
        predicate,
        descending: bool,
    ) -> List[WatchlistItem]:
        """Shared engine for every %change-based screen: fetch one
        batch of quotes, keep items where ``predicate(change_percent)``
        is truthy, return sorted by %change."""
        self._require_kite()
        quotes = _fetch_quotes(self._kite, universe)
        scored: List[Tuple[float, WatchlistItem]] = []
        for item in universe:
            cp = _change_percent(quotes.get(item.symbol, {}))
            if cp is not None and predicate(cp):
                scored.append((cp, item))
        scored.sort(key=lambda t: t[0], reverse=descending)
        return [it for _, it in scored]

    @staticmethod
    def _wrap(
        items: List[WatchlistItem],
        op: str,
        universe: Watchlist,
        **params: Any,
    ) -> Watchlist:
        """Compose a descriptive name like ``top_gainers(nifty50,n=10)``."""
        bits = ",".join(f"{k}={v}" for k, v in params.items())
        univ = universe.name or "universe"
        name = f"{op}({univ}{',' + bits if bits else ''})"
        return Watchlist(items, name=name)
