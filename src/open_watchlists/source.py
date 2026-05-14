"""``OpenWatchlists`` — the main client.

Builds predefined Watchlists from official sources only. Strictly avoids
internal Kite Web endpoints, scraping, or any non-public Zerodha API.
Inputs come from exactly three places:

1. ``KiteConnect.instruments()`` — Zerodha's public instruments dump.
2. Live NSE constituent CSVs at ``archives.nseindia.com`` (default
   path; fetched fresh on each list access, cached per-instance).
3. Bundled snapshots of NSE-published index constituent CSVs (see
   ``data/_manifest.json``) — used as fallback when live fetch fails
   or when ``live=False`` is passed.

The accepted ``kite`` argument is duck-typed — anything exposing
``instruments(exchange=None)`` with a Kite-shaped dict response will
work, including the official ``kiteconnect.KiteConnect`` class and any
in-house wrappers around it.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, List, Optional

from . import _data, _resolve
from .watchlist import Watchlist, WatchlistItem

logger = logging.getLogger(__name__)


class OpenWatchlists:
    """Builds predefined Watchlists from official sources.

    Args:
        kite: An authenticated ``KiteConnect`` instance (or any object
            exposing ``instruments(exchange=None) -> list[dict]``). May
            be ``None`` — predefined list methods still work but each
            ``WatchlistItem`` will have ``instrument_token=None``.
        instruments: Pre-fetched instruments list. If supplied,
            ``kite.instruments()`` is not called. Useful for sharing
            one instruments cache across many ``OpenWatchlists``
            instances.
        live: When ``True`` (the default), each call to ``get(key)`` /
            ``nifty50()`` / etc. fetches the latest constituent CSV
            from NSE archives over HTTPS. Results are cached for the
            lifetime of this instance, so repeated calls don't re-fetch.
            On network failure, falls back to the bundled snapshot if
            one is shipped for that list. Set ``False`` for fully
            offline / deterministic test runs — always reads bundled.
    """

    def __init__(
        self,
        kite: Optional[Any] = None,
        instruments: Optional[Iterable[dict]] = None,
        live: bool = True,
    ) -> None:
        self._kite = kite
        self._instruments_index: Optional[dict] = None
        self._live_mode = live
        self._live_cache: dict = {}
        self._screener = None  # LiveScreener, lazy-constructed via .live
        if instruments is not None:
            self._instruments_index = _resolve.build_instruments_index(instruments)

    # ------------------------------------------------------------------
    # Live screeners (lazy — imported on first access to keep import-time
    # graph minimal for users who never touch kite.quote()-based features)
    # ------------------------------------------------------------------

    @property
    def live(self):
        """Access live, ``kite.quote()``-backed screeners.

        Returns a :class:`LiveScreener` lazily bound to this instance's
        kite client. Requires an authenticated kite — methods on the
        returned object raise ``ValueError`` if ``kite=None`` was passed
        to ``OpenWatchlists``.

        Example::

            ow = OpenWatchlists(kite)
            gainers = ow.live.top_gainers(ow.nifty50(), n=5)
            buzzers = ow.live.top_by_traded_value(ow.fno_underlyings(), n=10)
        """
        if self._screener is None:
            from .live import LiveScreener
            self._screener = LiveScreener(self._kite)
        return self._screener

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
        """Return the Watchlist for any predefined key.

        In live mode (default), fetches from NSE archives the first
        time a given key is requested, then caches for the instance
        lifetime. Falls back to the bundled snapshot on network failure
        if one ships for that key.
        """
        symbols = self._resolve_symbols(list_key)
        return self._make_watchlist(symbols, name=list_key)

    def _resolve_symbols(self, list_key: str) -> List[str]:
        """Live-first symbol resolution with bundled-snapshot fallback."""
        if self._live_mode:
            if list_key in self._live_cache:
                return self._live_cache[list_key]
            try:
                symbols = _data.fetch_live(list_key)
                if not symbols:
                    raise RuntimeError(f"NSE returned 0 symbols for {list_key!r}")
                self._live_cache[list_key] = symbols
                return symbols
            except KeyError:
                # Unknown list_key — propagate, don't try bundled.
                raise
            except Exception as e:
                logger.warning(
                    "live fetch failed for %s: %s — trying bundled snapshot",
                    list_key, e,
                )

        # Either live mode is off, or live fetch failed and we're trying
        # the bundled fallback. Either way, this can also raise — let it.
        return _data.load_symbols(list_key)

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

    # v0.3-added named accessors for the broader Nifty index family.
    # These are live-only by default — no bundled snapshots ship for
    # them, so a network fetch happens the first time each is accessed.
    def nifty_midcap50(self) -> Watchlist:
        return self.get("nifty_midcap50")

    def nifty_smallcap50(self) -> Watchlist:
        return self.get("nifty_smallcap50")

    def nifty_smallcap100(self) -> Watchlist:
        return self.get("nifty_smallcap100")

    def nifty_smallcap250(self) -> Watchlist:
        return self.get("nifty_smallcap250")

    def nifty_midsmallcap400(self) -> Watchlist:
        return self.get("nifty_midsmallcap400")

    def nifty_largemidcap250(self) -> Watchlist:
        return self.get("nifty_largemidcap250")

    def nifty_microcap250(self) -> Watchlist:
        return self.get("nifty_microcap250")

    def nifty_totalmarket(self) -> Watchlist:
        return self.get("nifty_totalmarket")

    # ------------------------------------------------------------------
    # F&O underlyings — derived live from kite.instruments(), not bundled
    # ------------------------------------------------------------------

    def fno_underlyings(self) -> Watchlist:
        """All NSE **EQ-tradable** symbols that currently have F&O contracts on NFO.

        Implementation:
          1. Scan ``kite.instruments('NFO')`` for ``FUT`` rows and collect
             the unique ``name`` field — that's every distinct underlying.
          2. Cross-reference against the NSE EQ instruments dump and keep
             only names that ALSO exist with ``instrument_type == 'EQ'``.
             This drops index names like ``NIFTY``, ``BANKNIFTY``,
             ``FINNIFTY``, ``MIDCPNIFTY``, ``NIFTYNXT50`` — they have F&O
             contracts but no EQ instrument anyone can buy a single share
             of. Letting them through would put indices into the user's
             equity watchlist, which is wrong for cash-segment workflows.

        Returns an empty Watchlist if no ``kite`` was supplied (live
        derivation requires the API).
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

        # Intersect with NSE EQ — only keep underlyings that are
        # actually buyable in the cash segment.
        self._ensure_instruments()
        eq_symbols: set = set()
        for (ex, sym), inst in (self._instruments_index or {}).items():
            if ex != "NSE":
                continue
            if str(inst.get("instrument_type") or "").upper() == "EQ":
                eq_symbols.add(sym)

        tradable = underlyings & eq_symbols
        if not tradable:
            return Watchlist([], name="fno_underlyings")

        items = self._enrich(sorted(tradable), exchange="NSE")
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
