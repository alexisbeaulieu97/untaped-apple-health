"""Stream ``<Record>`` elements out of an Apple Health export.

Apple Health exports are a single, potentially multi-hundred-megabyte
``export.xml``. We parse it incrementally with :func:`xml.etree.ElementTree.iterparse`
and clear the tree as we go so memory stays flat regardless of file size. The
source may be the raw ``export.xml`` or the ``export.zip`` Apple produces (which
contains ``apple_health_export/export.xml``).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

from untaped.api import ConfigError

from untaped_apple_health.domain.record import Record


def read_records(source: Path) -> Iterator[Record]:
    """Yield every ``Record`` in ``source`` (an ``export.xml`` or ``export.zip``)."""
    with _open_xml(source) as stream:
        # Track the root so we can clear it after each record; otherwise the
        # parsed (even if individually cleared) elements pile up under it.
        context = ET.iterparse(stream, events=("start", "end"))
        _, root = next(context)
        for event, elem in context:
            if event != "end" or elem.tag != "Record":
                continue
            record = _build_record(elem)
            if record is not None:
                yield record
            root.clear()


@contextmanager
def _open_xml(source: Path) -> Iterator[IO[bytes]]:
    if zipfile.is_zipfile(source):
        with (
            zipfile.ZipFile(source) as archive,
            archive.open(_export_member(archive)) as stream,
        ):
            yield stream
    else:
        with source.open("rb") as stream:
            yield stream


def _export_member(archive: zipfile.ZipFile) -> str:
    for name in archive.namelist():
        if name.endswith("export.xml"):
            return name
    raise ConfigError("no export.xml found inside the zip archive")


def _build_record(elem: ET.Element) -> Record | None:
    type_ = elem.get("type")
    start_raw = elem.get("startDate")
    if not type_ or not start_raw:
        return None
    start = _naive_local(start_raw)
    if start is None:
        return None
    end = _naive_local(elem.get("endDate", "")) or start
    value, value_text = _split_value(elem.get("value"))
    return Record(
        type=type_,
        start=start,
        end=end,
        value=value,
        value_text=value_text,
        unit=elem.get("unit"),
        source_name=elem.get("sourceName", ""),
        metadata=_metadata(elem),
    )


def _naive_local(raw: str) -> str | None:
    """Drop the timezone offset, keeping the local wall-clock ``YYYY-MM-DD HH:MM:SS``.

    Apple's timestamps are fixed-width local times (``2026-06-12 07:30:00 -0400``),
    so the first 19 characters are exactly the naive-local form.
    """
    return raw[:19] if len(raw) >= 19 else None


def _split_value(raw: str | None) -> tuple[float | None, str | None]:
    if raw is None:
        return None, None
    try:
        return float(raw), None
    except ValueError:
        return None, raw


def _metadata(elem: ET.Element) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for child in elem:
        if child.tag != "MetadataEntry":
            continue
        key = child.get("key")
        value = child.get("value")
        if key is not None and value is not None:
            pairs.append((key, value))
    return tuple(pairs)
