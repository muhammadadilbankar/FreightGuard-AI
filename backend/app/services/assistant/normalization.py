"""Safe normalization helpers for untrusted assistant questions."""

from __future__ import annotations

import re

HYPHENS = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-"})


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.translate(HYPHENS).strip()).casefold()


def normalize_route(value: str) -> str:
    return re.sub(r"\s*-\s*", "-", normalize_text(value))
