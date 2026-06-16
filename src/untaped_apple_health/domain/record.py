"""The one value object the whole tool moves around: a single Health record."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Record:
    """One ``<Record>`` from an Apple Health export, normalized for storage.

    ``start`` / ``end`` are naive-local wall-clock strings (``YYYY-MM-DD
    HH:MM:SS``); the timezone offset is dropped on read so time-of-day window
    queries work directly. ``value`` holds the numeric reading when the record
    is a quantity; ``value_text`` holds the raw string for category records
    (e.g. sleep stages). ``metadata`` is the record's ``MetadataEntry`` pairs.
    """

    type: str
    start: str
    end: str
    value: float | None
    value_text: str | None
    unit: str | None
    source_name: str
    metadata: tuple[tuple[str, str], ...]
