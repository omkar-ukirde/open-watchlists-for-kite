"""CLI: refresh bundled NSE constituent lists from official source CSVs.

Usage::

    python -m open_watchlists.update
    open-watchlists-update          # if installed via pip

Re-downloads each list defined in ``data/_manifest.json`` directly from
NSE's public archives and rewrites the corresponding ``.txt`` file
inside the installed package. NSE only — no internal-Kite endpoints.
``requests`` is required (``pip install open-watchlists-for-kite[update]``).
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from typing import List, Optional


# Polite User-Agent — NSE rejects bare/empty UAs on its archive endpoints.
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; open-watchlists-for-kite/0.1; "
        "+https://github.com/omkar-ukirde/open-watchlists-for-kite)"
    ),
    "Accept": "text/csv,application/csv,text/plain,*/*",
}


def _fetch(url: str) -> str:
    try:
        import requests
    except ImportError:
        sys.stderr.write(
            "requests is required for updates: "
            "pip install 'open-watchlists-for-kite[update]'\n"
        )
        sys.exit(2)
    resp = requests.get(url, headers=NSE_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def _parse_symbols(csv_text: str) -> List[str]:
    reader = csv.DictReader(io.StringIO(csv_text))
    symbols: List[str] = []
    for row in reader:
        sym = (row.get("Symbol") or row.get("symbol") or "").strip()
        if sym:
            symbols.append(sym)
    return symbols


def main(argv: Optional[List[str]] = None) -> int:
    pkg_data = Path(__file__).parent / "data"
    manifest_path = pkg_data / "_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    failures: List[str] = []
    for key, meta in manifest["lists"].items():
        url = meta.get("source_url")
        if not url:
            print(f"skip {key}: no source_url")
            continue
        try:
            print(f"fetching {key} ...")
            text = _fetch(url)
            symbols = _parse_symbols(text)
            if not symbols:
                raise ValueError("parsed 0 symbols")
            (pkg_data / meta["file"]).write_text(
                "\n".join(symbols) + "\n", encoding="utf-8"
            )
            print(f"  wrote {len(symbols)} symbols → {meta['file']}")
        except Exception as e:  # noqa: BLE001 — surface any fetcher error
            print(f"  FAILED: {e}")
            failures.append(key)

    if failures:
        print(f"\n{len(failures)} list(s) failed: {failures}")
        return 1
    print("\nAll lists refreshed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
