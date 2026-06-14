"""Parse the date and clock strings accepted on the command line.

These mirror the semantics of an earlier analysis script so the agent
can keep using ``today`` / ``yesterday`` / ``YYYY-MM-DD`` and ``HH:MM``.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta


def resolve_date(value: str | None) -> date:
    """Resolve ``today`` (or ``None``), ``yesterday``, or an ISO ``YYYY-MM-DD``."""
    if value is None or value == "today":
        return date.today()
    if value == "yesterday":
        return date.today() - timedelta(days=1)
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_clock(value: str) -> time:
    """Parse an ``HH:MM`` wall-clock string into a :class:`datetime.time`."""
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour, minute)
