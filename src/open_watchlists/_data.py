"""Data-source loader for predefined watchlists.

Two paths, both reading the same ``data/_manifest.json``:

1. **Bundled** — read the snapshotted ``.txt`` file shipped with the
   package via ``importlib.resources``. No network IO. Falls back here
   when live fetch is disabled or fails.
2. **Live** — fetch the constituent CSV directly from NSE archives
   (``archives.nseindia.com/content/indices/ind_*.csv``) over HTTPS
   using stdlib ``urllib`` so the library has zero new runtime deps.

Live is the default for ``OpenWatchlists`` because index constituents
drift between releases and most users would rather get a stale-by-one-
network-call result than a stale-by-six-months snapshot. The bundled
files exist as offline fallback.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import urllib.request
from importlib import resources
from typing import Dict, List

logger = logging.getLogger(__name__)


# Identifying User-Agent is enough for the NSE archives endpoint —
# they only reject empty / non-browser UAs.
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; open-watchlists-for-kite; "
        "+https://github.com/omkar-ukirde/open-watchlists-for-kite)"
    ),
    "Accept": "text/csv,application/csv,text/plain,*/*",
}


def _data_files():
    return resources.files(__package__) / "data"


def load_manifest() -> Dict:
    ref = _data_files() / "_manifest.json"
    return json.loads(ref.read_text(encoding="utf-8"))


def load_symbols(list_key: str) -> List[str]:
    """Read symbols for ``list_key`` from the bundled snapshot.

    Raises ``KeyError`` for unknown keys, ``FileNotFoundError`` for keys
    that have no bundled snapshot (live-only lists). Callers should
    catch ``FileNotFoundError`` and fall through to ``fetch_live`` or
    surface a clearer message.
    """
    manifest = load_manifest()
    listmeta = manifest["lists"].get(list_key)
    if not listmeta:
        available = sorted(manifest["lists"].keys())
        raise KeyError(
            f"Unknown predefined list {list_key!r}. Available: {available}"
        )
    filename = listmeta.get("file")
    if not filename:
        raise FileNotFoundError(
            f"No bundled snapshot for {list_key!r} — live mode required."
        )
    ref = _data_files() / filename
    try:
        text = ref.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Bundled file {filename!r} for list {list_key!r} not found in package."
        ) from e
    return [line.strip() for line in text.splitlines() if line.strip()]


def fetch_live(list_key: str, timeout: float = 30.0) -> List[str]:
    """Fetch the latest constituents directly from the manifest's
    ``source_url``. Returns parsed ``Symbol`` column values.

    Raises ``KeyError`` for unknown keys, ``ValueError`` if the manifest
    entry has no ``source_url``, and propagates ``urllib`` errors on
    network failure.
    """
    manifest = load_manifest()
    listmeta = manifest["lists"].get(list_key)
    if not listmeta:
        available = sorted(manifest["lists"].keys())
        raise KeyError(
            f"Unknown predefined list {list_key!r}. Available: {available}"
        )
    url = listmeta.get("source_url")
    if not url:
        raise ValueError(f"List {list_key!r} has no source_url for live fetch.")
    req = urllib.request.Request(url, headers=NSE_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return _parse_symbols_csv(text)


def _parse_symbols_csv(text: str) -> List[str]:
    """Extract Symbol column from a NSE constituent CSV string."""
    reader = csv.DictReader(io.StringIO(text))
    out: List[str] = []
    for row in reader:
        sym = (row.get("Symbol") or row.get("symbol") or "").strip()
        if sym:
            out.append(sym)
    return out


def list_available() -> List[str]:
    return sorted(load_manifest()["lists"].keys())


def get_metadata(list_key: str) -> Dict:
    manifest = load_manifest()
    meta = manifest["lists"].get(list_key)
    if not meta:
        raise KeyError(f"Unknown predefined list {list_key!r}")
    return dict(meta)
