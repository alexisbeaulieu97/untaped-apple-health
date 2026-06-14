"""SQLite ingest, schema queries, and filtered/aggregated record queries."""

from __future__ import annotations

import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from untaped_apple_health.domain.query import QuerySpec
from untaped_apple_health.domain.record import Record
from untaped_apple_health.infrastructure.database import HealthDatabase, default_database_path
from untaped_apple_health.infrastructure.export_reader import read_records


@pytest.fixture
def db(export_xml: Path, tmp_path: Path) -> Iterator[HealthDatabase]:
    path = tmp_path / "health.db"
    with HealthDatabase.open(path) as database:
        database.rebuild(
            read_records(export_xml),
            source_path=export_xml,
            source_mtime=123.0,
            synced_at="2026-06-13 09:00:00",
        )
        yield database


HEART_RATE = "HKQuantityTypeIdentifierHeartRate"


def test_default_database_path_honors_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_database_path() == tmp_path / "untaped" / "apple-health.db"


def test_rebuild_records_status(db: HealthDatabase) -> None:
    status = db.status()
    assert status is not None
    assert status["record_count"] == 6
    assert status["first_ts"] == "2026-06-11 07:30:00"
    assert status["last_ts"] == "2026-06-12 11:45:00"


def test_rebuild_is_a_snapshot(export_xml: Path, tmp_path: Path) -> None:
    path = tmp_path / "health.db"
    with HealthDatabase.open(path) as database:
        database.rebuild(read_records(export_xml), source_path=export_xml, synced_at="t1")
        database.rebuild(read_records(export_xml), source_path=export_xml, synced_at="t2")
        # Re-syncing the same export must not double the rows.
        assert database.status()["record_count"] == 6  # type: ignore[index]


def test_database_file_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "health.db"
    with HealthDatabase.open(path) as database:
        database.rebuild(iter(()), source_path=path, synced_at="t")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_failed_sync_preserves_existing_data(export_xml: Path, tmp_path: Path) -> None:
    """A record stream that raises partway must roll back, not wipe the prior snapshot."""
    path = tmp_path / "health.db"
    with HealthDatabase.open(path) as database:
        database.rebuild(read_records(export_xml), source_path=export_xml, synced_at="t1")

    def truncated() -> Iterator[Record]:
        records = list(read_records(export_xml))
        yield records[0]
        yield records[1]
        raise RuntimeError("truncated export at row 3")

    with HealthDatabase.open(path) as database, pytest.raises(RuntimeError):
        database.rebuild(truncated(), source_path=export_xml, synced_at="t2")

    with HealthDatabase.open(path) as database:
        status = database.status()
        assert status is not None
        assert status["record_count"] == 6
        assert status["synced_at"] == "t1"  # the failed sync left no trace


def test_rebuild_flushes_in_batches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The in-loop flush (only hit by exports larger than _BATCH) persists every record."""
    monkeypatch.setattr("untaped_apple_health.infrastructure.database._BATCH", 2)
    records = [
        Record(
            type="T",
            start=f"2026-06-12 07:0{i}:00",
            end=f"2026-06-12 07:0{i}:00",
            value=float(i),
            value_text=None,
            unit="u",
            source_name="S",
            metadata=(),
        )
        for i in range(5)
    ]
    path = tmp_path / "health.db"
    with HealthDatabase.open(path) as database:
        result = database.rebuild(iter(records), source_path=path, synced_at="t")
    assert result.record_count == 5
    with HealthDatabase.open(path) as database:
        rows = database.query(QuerySpec(types=("T",), agg="raw"))
    assert len(rows) == 5


def test_metric_overview(db: HealthDatabase) -> None:
    rows = {row["type"]: row for row in db.metric_overview()}
    assert rows[HEART_RATE]["count"] == 3
    assert rows[HEART_RATE]["alias"] == "heart-rate"
    assert rows[HEART_RATE]["first"] == "2026-06-11 07:30:00"
    assert rows[HEART_RATE]["sources"] == 2


def test_metric_sources_drilldown(db: HealthDatabase) -> None:
    rows = {row["source"]: row for row in db.metric_sources(HEART_RATE)}
    assert rows["Apple Watch"]["count"] == 2
    assert rows["iPhone"]["count"] == 1


def test_query_raw_filters_by_type(db: HealthDatabase) -> None:
    rows = db.query(QuerySpec(types=(HEART_RATE,), agg="raw"))
    assert len(rows) == 3
    assert all(row["type"] == HEART_RATE for row in rows)


def test_query_raw_respects_limit(db: HealthDatabase) -> None:
    rows = db.query(QuerySpec(types=(HEART_RATE,), agg="raw", limit=1))
    assert len(rows) == 1


def test_query_filters_by_date_range(db: HealthDatabase) -> None:
    rows = db.query(QuerySpec(types=(HEART_RATE,), date_from="2026-06-12", date_to="2026-06-12"))
    assert len(rows) == 2  # excludes the 2026-06-11 sample


def test_query_filters_by_time_of_day_window(db: HealthDatabase) -> None:
    rows = db.query(
        QuerySpec(
            types=(HEART_RATE,),
            date_from="2026-06-12",
            date_to="2026-06-12",
            time_from="07:00",
            time_to="08:00",
        )
    )
    assert len(rows) == 1
    assert rows[0]["start"] == "2026-06-12 07:30:00"


def test_query_filters_by_source_substring(db: HealthDatabase) -> None:
    rows = db.query(QuerySpec(source="omron", agg="raw"))
    assert len(rows) == 2  # systolic + diastolic
    assert all("OMRON" in str(row["source"]) for row in rows)


def test_query_filters_by_metadata(db: HealthDatabase) -> None:
    rows = db.query(
        QuerySpec(
            types=(HEART_RATE,),
            where_meta=(("HKMetadataKeyHeartRateMotionContext", "1"),),
            agg="raw",
        )
    )
    assert len(rows) == 2  # the two sedentary samples (motion context 1)


def test_query_summary_aggregates(db: HealthDatabase) -> None:
    [row] = db.query(
        QuerySpec(types=(HEART_RATE,), date_from="2026-06-12", date_to="2026-06-12", agg="summary")
    )
    assert row["count"] == 2
    assert row["min"] == 68.0
    assert row["max"] == 92.0
    assert row["median"] == 80.0


def test_query_bin_buckets_by_interval(db: HealthDatabase) -> None:
    rows = db.query(
        QuerySpec(
            types=(HEART_RATE,),
            date_from="2026-06-12",
            date_to="2026-06-12",
            agg="bin",
            bin_size="15min",
        )
    )
    bins = {row["bin"]: row for row in rows}
    assert set(bins) == {"2026-06-12 07:30", "2026-06-12 11:45"}
    assert bins["2026-06-12 07:30"]["count"] == 1


def test_query_rejects_bin_without_size(db: HealthDatabase) -> None:
    with pytest.raises(ValueError):
        db.query(QuerySpec(types=(HEART_RATE,), agg="bin"))
