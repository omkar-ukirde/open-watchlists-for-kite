"""Loader for bundled NSE constituent lists.

Reads ``data/_manifest.json`` and the per-list ``.txt`` files shipped
inside the package via ``importlib.resources``. No network IO here.
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Dict, List


def _data_files():
    return resources.files(__package__) / "data"


def load_manifest() -> Dict:
    ref = _data_files() / "_manifest.json"
    return json.loads(ref.read_text(encoding="utf-8"))


def load_symbols(list_key: str) -> List[str]:
    manifest = load_manifest()
    listmeta = manifest["lists"].get(list_key)
    if not listmeta:
        available = sorted(manifest["lists"].keys())
        raise KeyError(
            f"Unknown predefined list {list_key!r}. Available: {available}"
        )
    ref = _data_files() / listmeta["file"]
    text = ref.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def list_available() -> List[str]:
    return sorted(load_manifest()["lists"].keys())


def get_metadata(list_key: str) -> Dict:
    manifest = load_manifest()
    meta = manifest["lists"].get(list_key)
    if not meta:
        raise KeyError(f"Unknown predefined list {list_key!r}")
    return dict(meta)
