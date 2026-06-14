"""Application use-cases: sync, query-spec building, and status reporting."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from untaped.api import ConfigError

from untaped_apple_health.application import SyncExport, build_query_spec, report_status
from untaped_apple_health.infrastructure.database import HealthDatabase

HEART_RATE = "HKQuantityTypeIdentifierHeartRate"


@pytest.fixture
def database(tmp_path: Path) -> Iterator[HealthDatabase]:
    with HealthDatabase.open(tmp_path / "health.db") as db:
        yield db


def test_sync_export_ingests_records(database: HealthDatabase, export_xml: Path) -> None:
    result = SyncExport(database)(export_xml, synced_at="2026-06-13 09:00:00")
    assert result.record_count == 6
    assert database.status() is not None


def test_sync_export_rejects_missing_file(database: HealthDatabase, tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        SyncExport(database)(tmp_path / "nope.xml", synced_at="t")


def test_build_query_spec_resolves_aliases() -> None:
    spec = build_query_spec(types=("heart-rate",), agg="summary")
    assert spec.types == (HEART_RATE,)
    assert spec.agg == "summary"


def test_build_query_spec_passes_raw_identifiers_through() -> None:
    spec = build_query_spec(types=(HEART_RATE,))
    assert spec.types == (HEART_RATE,)


def test_report_status_when_never_synced(database: HealthDatabase, tmp_path: Path) -> None:
    report = report_status(database, tmp_path / "export.xml")
    assert report["synced"] is False


def test_report_status_is_fresh_right_after_sync(
    database: HealthDatabase, export_xml: Path
) -> None:
    SyncExport(database)(export_xml, synced_at="t")
    report = report_status(database, export_xml)
    assert report["synced"] is True
    assert report["stale"] is False


def test_report_status_detects_stale_export(database: HealthDatabase, export_xml: Path) -> None:
    SyncExport(database)(export_xml, synced_at="t")
    future = export_xml.stat().st_mtime + 1000
    os.utime(export_xml, (future, future))
    report = report_status(database, export_xml)
    assert report["stale"] is True
