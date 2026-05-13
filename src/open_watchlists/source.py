"""``OpenWatchlists`` — the main client.

Builds predefined Watchlists from official sources only. Strictly avoids
internal Kite Web endpoints, scraping, or any non-public Zerodha API.
Inputs come from exactly two places:

1. ``KiteConnect.instruments()`` — Zerodha's public instruments dump.
2. Bundled snapshots of NSE-published index constituent CSVs (see
   ``data/_manifest.json``).

The accepted ``kite`` argument is duck-typed — anything exposing
``instruments(exchange=None)`` with a Kite-shaped dict response will work,
including the official ``kiteconnect.KiteConnect`` class and any
in-house wrappers around it.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional

from . import _data, _resolve
from .watchlist import Watchlist, WatchlistItem


class OpenWatchlists:
    """Builds predefined Watchlists from official sources.

    Args:
        kite: An authenticated ``KiteConnect`` instance (or any object
            exposing ``instruments(exchange=None) -> list[dict]``). May be
            ``None`` — in that case predefined list methods still return
            Watchlists, but each ``WatchlistItem`` will have
            ``instrument_token=None`` (un-enriched).
        instruments: Pre-fetched instruments list. If supplied,
            ``kite.instruments()`` is not called. Useful for sharing one
            instruments cache across many ``OpenWatchlists`` instances.
    """

    def __init__(
        self,
        kite: Optional[Any] = None,
        instruments: Optional[Iterable[dict]] = None,
    ) -> None:
        self._kite = kite
        self._instruments_index: Optional[dict] = None
        if instruments is not None:
            self._instruments_index = _resolve.build_instruments_index(instruments)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def available(self) -> List[str]:
        """Return the keys of every bundled predefined watchlist."""
        return _data.list_available()

    def metadata(self, list_key: str) -> dict:
        """Return metadata (name, file, source_url, description) for a list."""
        return _data.get_metadata(list_key)

    # ------------------------------------------------------------------
    # Generic accessor
    # ------------------------------------------------------------------

    def get(self, list_key: str) -> Watchlist:
        """Return the Watchlist for any bundled key (see ``available()``)."""
        symbols = _data.load_symbols(list_key)
        return self._make_watchlist(symbols, name=list_key)

    # ------------------------------------------------------------------
    # Named accessors (ergonomics — same as get(key) under the hood)
    # ------------------------------------------------------------------

    def nifty50(self) -> Watchlist:
        return self.get("nifty50")

    def nifty_next50(self) -> Watchlist:
        return self.get("nifty_next50")

    def nifty100(self) -> Watchlist:
        return self.get("nifty100")

    def nifty200(self) -> Watchlist:
        return self.get("nifty200")

    def nifty500(self) -> Watchlist:
        return self.get("nifty500")

    def nifty_midcap150(self) -> Watchlist:
        return self.get("nifty_midcap150")

    def banknifty(self) -> Watchlist:
        return self.get("banknifty")

    def nifty_it(self) -> Watchlist:
        return self.get("nifty_it")

    def nifty_pharma(self) -> Watchlist:
        return self.get("nifty_pharma")

    def nifty_auto(self) -> Watchlist:
        return self.get("nifty_auto")

    def nifty_fmcg(self) -> Watchlist:
        return self.get("nifty_fmcg")

    def nifty_metal(self) -> Watchlist:
        return self.get("nifty_metal")

    def nifty_realty(self) -> Watchlist:
        return self.get("nifty_realty")

    def nifty_energy(self) -> Watchlist:
        return self.get("nifty_energy")

    def nifty_financial_services(self) -> Watchlist:
        return self.get("nifty_financial_services")

    # ------------------------------------------------------------------
    # F&O underlyings — derived live from kite.instruments(), not bundled
    # ------------------------------------------------------------------

    def fno_underlyings(self) -> Watchlist:
        """All NSE equity symbols that currently have F&O contracts on NFO.

        Implemented by scanning ``kite.instruments('NFO')`` for ``FUT``
        instruments, extracting the unique ``name`` field (which is the
        underlying symbol), and re-resolving against NSE EQ to attach
        ``instrument_token`` / ``tick_size`` etc.

        Returns an empty Watchlist if no ``kite`` was supplied (since
        live derivation requires the API).
        """
        if self._kite is None:
            return Watchlist([], name="fno_underlyings")
        try:
            nfo = self._kite.instruments("NFO")
        except Exception:
            return Watchlist([], name="fno_underlyings")
        underlyings: set = set()
        for inst in nfo:
            itype = str(inst.get("instrument_type") or "").upper()
            name = str(inst.get("name") or "").strip().upper()
            if itype == "FUT" and name:
                underlyings.add(name)
        if not underlyings:
            return Watchlist([], name="fno_underlyings")
        items = self._enrich(sorted(underlyings), exchange="NSE")
        return Watchlist(items, name="fno_underlyings")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_instruments(self) -> None:
        if self._instruments_index is not None:
            return
        if self._kite is None:
            self._instruments_index = {}
            return
        instruments = self._kite.instruments()
        self._instruments_index = _resolve.build_instruments_index(instruments)

    def _enrich(self, symbols: Iterable[str], exchange: str = "NSE") -> List[WatchlistItem]:
        self._ensure_instruments()
        return _resolve.resolve_symbols(
            symbols, self._instruments_index or {}, exchange=exchange
        )

    def _make_watchlist(self, symbols: Iterable[str], name: str = "") -> Watchlist:
        items = self._enrich(symbols, exchange="NSE")
        return Watchlist(items, name=name)
