"""Streaming reader over Apple Health ``export.xml`` (and ``.zip``)."""

from __future__ import annotations

from pathlib import Path

from untaped_apple_health.infrastructure.export_reader import read_records


def test_reads_every_record(export_xml: Path) -> None:
    records = list(read_records(export_xml))
    assert len(records) == 6


def test_strips_timezone_to_naive_local(export_xml: Path) -> None:
    first_hr = next(r for r in read_records(export_xml) if r.type.endswith("HeartRate"))
    assert first_hr.start == "2026-06-12 07:30:00"


def test_parses_numeric_value(export_xml: Path) -> None:
    first_hr = next(r for r in read_records(export_xml) if r.type.endswith("HeartRate"))
    assert first_hr.value == 68.0
    assert first_hr.value_text is None
    assert first_hr.unit == "count/min"
    assert first_hr.source_name == "Apple Watch"


def test_keeps_non_numeric_value_as_text(export_xml: Path) -> None:
    sleep = next(r for r in read_records(export_xml) if "Sleep" in r.type)
    assert sleep.value is None
    assert sleep.value_text == "HKCategoryValueSleepAnalysisAsleepCore"


def test_captures_metadata_entries(export_xml: Path) -> None:
    first_hr = next(r for r in read_records(export_xml) if r.type.endswith("HeartRate"))
    assert ("HKMetadataKeyHeartRateMotionContext", "1") in first_hr.metadata


def test_reads_from_zip_archive(export_zip: Path) -> None:
    records = list(read_records(export_zip))
    assert len(records) == 6
    assert any(r.value == 128.0 for r in records)  # systolic from the BP pair
