"""The description of a record query — what to filter and how to aggregate.

This is a pure value object. The CLI builds it (resolving friendly aliases to
HK identifiers first); the database executes it. Aggregation is what keeps a
query's result small enough to hand to an agent:

- ``raw``     — individual records, capped by ``limit``.
- ``summary`` — count/min/max/mean/median/stdev per type.
- ``bin``     — the same stats per ``bin_size`` time bucket per type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Aggregation = Literal["raw", "summary", "bin"]

_BIN_UNITS = {"min": 1, "h": 60, "d": 1440}
_MINUTES_PER_DAY = 1440


def bin_size_minutes(bin_size: str) -> int:
    """Parse a bin size like ``15min`` / ``1h`` / ``1d`` into minutes.

    Raises ``ValueError`` for an unrecognized format, a non-positive size, or a
    size larger than one day — ``_bucket`` floors within a single day, so
    multi-day bins are not supported (``2d`` would silently behave as ``1d``).
    """
    match = re.fullmatch(r"(\d+)(min|h|d)", bin_size)
    if match is None:
        raise ValueError(f"--bin must look like 15min, 1h, or 1d; got {bin_size!r}")
    minutes = int(match.group(1)) * _BIN_UNITS[match.group(2)]
    if minutes < 1:
        raise ValueError(f"--bin must be positive; got {bin_size!r}")
    if minutes > _MINUTES_PER_DAY:
        raise ValueError(f"--bin supports sizes up to 1d; got {bin_size!r}")
    return minutes


@dataclass(frozen=True, slots=True)
class QuerySpec:
    types: tuple[str, ...] = ()
    date_from: str | None = None
    date_to: str | None = None
    time_from: str | None = None
    time_to: str | None = None
    source: str | None = None
    where_meta: tuple[tuple[str, str], ...] = ()
    agg: Aggregation = "raw"
    bin_size: str | None = None
    limit: int = 1000
