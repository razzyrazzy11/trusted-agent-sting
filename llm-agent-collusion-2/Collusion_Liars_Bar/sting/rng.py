"""Seeded random streams for common random numbers across arms.

Every random draw in a study game comes from a stream keyed by what it is for, never from
the global `random` state. Two sequences with the same seed but different arms therefore
see the same names, deals (per round index, per role), revolvers, first players and sting
card orders, until their play diverges. This replaces the harness's global-`random` draws
(deal, target card, bullet position, first player, round restarts).
"""
from __future__ import annotations

import hashlib
import random


def derive_seed(*parts) -> int:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def stream(*parts) -> random.Random:
    return random.Random(derive_seed(*parts))
