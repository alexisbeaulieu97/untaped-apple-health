"""The local SQLite mirror of an Apple Health export.

Apple exports the complete history every time, so ``rebuild`` is a snapshot: it
drops and recreates the tables. Queries reduce data *here* (filter + aggregate)
so callers — especially an agent — get small results instead of raw dumps.
"""

from __future__ import annotations

import os
import sqlite3
import statistics
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from untaped_apple_health.domain.metrics import alias_for
from untaped_apple_health.domain.query import QuerySpec, bin_size_minutes
from untaped_apple_health.domain.record import Record

_BATCH = 5000

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    value REAL,
    value_text TEXT,
    unit TEXT,
    source_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metadata (
    record_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    source_path TEXT NOT NULL,
    source_mtime REAL,
    synced_at TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    first_ts TEXT,
    last_ts TEXT
);
CREATE INDEX IF NOT EXISTS ix_records_type_start ON records (type, start);
CREATE INDEX IF NOT EXISTS ix_metadata_record ON metadata (record_id, key);
"""


def default_database_path() -> Path:
    """The default DB location under the untaped data dir (mirrors core's XDG layout).

    The DB lives in its own ``apple-health/`` subdirectory so that tightening the
    directory to ``0700`` (see ``open_session``) scopes to this plugin rather than
    the shared ``untaped/`` data dir, which also holds the managed venv and other
    plugins' state.
    """
    data_home = os.environ.get("XDG_DATA_HOME")
    root = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return root / "untaped" / "apple-health" / "apple-health.db"


@dataclass(frozen=True, slots=True)
class SyncResult:
    record_count: int
    first_ts: str | None
    last_ts: str | None
    source_path: str


class HealthDatabase:
    """A connection to the local Health mirror, plus ingest and query operations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    @classmethod
    @contextmanager
    def open(cls, path: Path | str) -> Iterator[HealthDatabase]:
        """Open (creating if needed) the DB at ``path`` with owner-only permissions."""
        connection = sqlite3.connect(path)
        try:
            connection.row_factory = sqlite3.Row
            if str(path) != ":memory:":
                os.chmod(path, 0o600)
            connection.executescript(_CREATE_SQL)
            yield cls(connection)
        finally:
            connection.close()

    # -- ingest -----------------------------------------------------------

    def rebuild(
        self,
        records: Iterable[Record],
        *,
        source_path: Path | str,
        synced_at: str,
        source_mtime: float | None = None,
    ) -> SyncResult:
        """Replace all data with ``records`` (a full-snapshot rebuild).

        The clear and the re-insert run as one transaction. ``DELETE`` is issued
        with ``execute`` (not ``executescript``, which would force an
        intermediate commit), so a record stream that raises partway — a
        truncated or corrupt export, or a Ctrl-C — rolls back and leaves the
        previous mirror intact instead of wiping it.
        """
        conn = self._conn
        try:
            conn.execute("DELETE FROM records")
            conn.execute("DELETE FROM metadata")
            conn.execute("DELETE FROM sync_meta")
            count = 0
            first: str | None = None
            last: str | None = None
            rec_batch: list[tuple[object, ...]] = []
            meta_batch: list[tuple[object, ...]] = []
            for record in records:
                count += 1
                rec_batch.append(
                    (
                        count,
                        record.type,
                        record.start,
                        record.end,
                        record.value,
                        record.value_text,
                        record.unit,
                        record.source_name,
                    )
                )
                meta_batch.extend((count, key, value) for key, value in record.metadata)
                if first is None or record.start < first:
                    first = record.start
                if last is None or record.start > last:
                    last = record.start
                if len(rec_batch) >= _BATCH:
                    self._flush(rec_batch, meta_batch)
                    rec_batch.clear()
                    meta_batch.clear()
            self._flush(rec_batch, meta_batch)
            conn.execute(
                "INSERT INTO sync_meta "
                "(id, source_path, source_mtime, synced_at, record_count, first_ts, last_ts) "
                "VALUES (1, ?, ?, ?, ?, ?, ?)",
                (str(source_path), source_mtime, synced_at, count, first, last),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return SyncResult(
            record_count=count, first_ts=first, last_ts=last, source_path=str(source_path)
        )

    def _flush(
        self, rec_batch: list[tuple[object, ...]], meta_batch: list[tuple[object, ...]]
    ) -> None:
        if rec_batch:
            self._conn.executemany(
                "INSERT INTO records "
                "(id, type, start, end, value, value_text, unit, source_name) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rec_batch,
            )
        if meta_batch:
            self._conn.executemany(
                "INSERT INTO metadata (record_id, key, value) VALUES (?, ?, ?)",
                meta_batch,
            )

    # -- schema / status --------------------------------------------------

    def status(self) -> dict[str, object] | None:
        row = self._conn.execute(
            "SELECT source_path, source_mtime, synced_at, record_count, first_ts, last_ts "
            "FROM sync_meta WHERE id = 1"
        ).fetchone()
        return _to_dict(row) if row is not None else None

    def metric_overview(self) -> list[dict[str, object]]:
        cursor = self._conn.execute(
            "SELECT type, COUNT(*) AS count, MIN(start) AS first, MAX(start) AS last, "
            "COUNT(DISTINCT source_name) AS sources, MAX(unit) AS unit "
            "FROM records GROUP BY type ORDER BY count DESC"
        )
        rows: list[dict[str, object]] = []
        for row in cursor.fetchall():
            entry = _to_dict(row)
            entry["alias"] = alias_for(str(entry["type"]))
            rows.append(entry)
        return rows

    def metric_sources(self, type_: str) -> list[dict[str, object]]:
        cursor = self._conn.execute(
            "SELECT source_name AS source, COUNT(*) AS count, MIN(start) AS first, "
            "MAX(start) AS last, MAX(unit) AS unit "
            "FROM records WHERE type = ? GROUP BY source_name ORDER BY count DESC",
            (type_,),
        )
        return [_to_dict(row) for row in cursor.fetchall()]

    # -- query ------------------------------------------------------------

    def query(self, spec: QuerySpec) -> list[dict[str, object]]:
        where, params = _build_where(spec)
        if spec.agg == "raw":
            return self._raw(where, params, spec.limit)
        value_where = where + (" AND " if where else " WHERE ") + "value IS NOT NULL"
        if spec.agg == "summary":
            return self._summary(value_where, params)
        bin_size = spec.bin_size
        if bin_size is None:
            raise ValueError("bin aggregation requires a bin size (e.g. 15min, 1h, 1d)")
        return self._binned(value_where, params, bin_size)

    def _raw(self, where: str, params: list[object], limit: int) -> list[dict[str, object]]:
        cursor = self._conn.execute(
            "SELECT type, start, end, value, value_text, unit, source_name AS source "
            f"FROM records{where} ORDER BY start LIMIT ?",
            [*params, limit],
        )
        return [_to_dict(row) for row in cursor.fetchall()]

    def _summary(self, where: str, params: list[object]) -> list[dict[str, object]]:
        cursor = self._conn.execute(
            f"SELECT type, value, unit FROM records{where} ORDER BY type", params
        )
        # Exact median/stdev need every value in a group and SQLite has neither,
        # so we stream the cursor (no fetchall) and hold one value list per type:
        # peak memory is O(largest type's value count), not the whole result set.
        groups: dict[str, list[float]] = {}
        units: dict[str, object] = {}
        for row in cursor:
            groups.setdefault(row["type"], []).append(row["value"])
            units.setdefault(row["type"], row["unit"])
        return [_stats_row({"type": t}, values, units[t]) for t, values in groups.items()]

    def _binned(self, where: str, params: list[object], bin_size: str) -> list[dict[str, object]]:
        minutes = bin_size_minutes(bin_size)
        cursor = self._conn.execute(
            f"SELECT type, start, value, unit FROM records{where} ORDER BY start", params
        )
        groups: dict[tuple[str, str], list[float]] = {}
        units: dict[tuple[str, str], object] = {}
        for row in cursor:
            key = (row["type"], _bucket(row["start"], minutes))
            groups.setdefault(key, []).append(row["value"])
            units.setdefault(key, row["unit"])
        rows = [
            _stats_row({"type": t, "bin": bucket}, values, units[(t, bucket)])
            for (t, bucket), values in groups.items()
        ]
        return sorted(rows, key=lambda r: (str(r["type"]), str(r["bin"])))


def _build_where(spec: QuerySpec) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    if spec.types:
        placeholders = ",".join("?" for _ in spec.types)
        clauses.append(f"type IN ({placeholders})")
        params.extend(spec.types)
    if spec.date_from:
        clauses.append("substr(start, 1, 10) >= ?")
        params.append(spec.date_from)
    if spec.date_to:
        clauses.append("substr(start, 1, 10) <= ?")
        params.append(spec.date_to)
    if spec.time_from:
        clauses.append("substr(start, 12, 5) >= ?")
        params.append(spec.time_from)
    if spec.time_to:
        clauses.append("substr(start, 12, 5) <= ?")
        params.append(spec.time_to)
    if spec.source:
        clauses.append("instr(lower(source_name), lower(?)) > 0")
        params.append(spec.source)
    for key, value in spec.where_meta:
        clauses.append(
            "EXISTS (SELECT 1 FROM metadata m "
            "WHERE m.record_id = records.id AND m.key = ? AND m.value = ?)"
        )
        params.extend((key, value))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _stats_row(base: dict[str, object], values: list[float], unit: object) -> dict[str, object]:
    return {
        **base,
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.mean(values), 1),
        "median": round(statistics.median(values), 1),
        "stdev": round(statistics.stdev(values), 1) if len(values) > 1 else 0.0,
        "unit": unit,
    }


def _bucket(start: str, minutes: int) -> str:
    # ``start`` is fixed-width ``YYYY-MM-DD HH:MM:SS`` (see export_reader), so we
    # slice rather than parse. The time-of-day is floored into the bin and the
    # date is preserved, so a 1d bin collapses to that day's midnight.
    minute_of_day = int(start[11:13]) * 60 + int(start[14:16])
    floored = minute_of_day // minutes * minutes
    return f"{start[:10]} {floored // 60:02d}:{floored % 60:02d}"


def _to_dict(row: sqlite3.Row) -> dict[str, object]:
    # `.keys()` is required, not `in row`: iterating a sqlite3.Row yields its
    # values, not its column names, so SIM118's rewrite would be wrong here.
    return {key: row[key] for key in row.keys()}  # noqa: SIM118
