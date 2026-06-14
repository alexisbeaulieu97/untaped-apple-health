"""Shared synthetic Apple Health export fixtures.

These are tiny, hand-written, and entirely fictional — no real health data is
ever committed. A handful of records exercise every shape the reader and
database care about: numeric quantities with metadata, a blood-pressure pair,
and a non-numeric sleep category value.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

SAMPLE_EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
 <ExportDate value="2026-06-13 09:00:00 -0400"/>
 <Me HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexMale"/>
 <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Apple Watch"
   unit="count/min" startDate="2026-06-12 07:30:00 -0400"
   endDate="2026-06-12 07:30:00 -0400" value="68">
  <MetadataEntry key="HKMetadataKeyHeartRateMotionContext" value="1"/>
 </Record>
 <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Apple Watch"
   unit="count/min" startDate="2026-06-12 11:45:00 -0400"
   endDate="2026-06-12 11:45:00 -0400" value="92">
  <MetadataEntry key="HKMetadataKeyHeartRateMotionContext" value="2"/>
 </Record>
 <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="iPhone"
   unit="count/min" startDate="2026-06-11 07:30:00 -0400"
   endDate="2026-06-11 07:30:00 -0400" value="70">
  <MetadataEntry key="HKMetadataKeyHeartRateMotionContext" value="1"/>
 </Record>
 <Record type="HKQuantityTypeIdentifierBloodPressureSystolic" sourceName="OMRON connect"
   unit="mmHg" startDate="2026-06-12 08:00:00 -0400"
   endDate="2026-06-12 08:00:00 -0400" value="128"/>
 <Record type="HKQuantityTypeIdentifierBloodPressureDiastolic" sourceName="OMRON connect"
   unit="mmHg" startDate="2026-06-12 08:00:00 -0400"
   endDate="2026-06-12 08:00:00 -0400" value="82"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Apple Watch"
   startDate="2026-06-12 00:10:00 -0400" endDate="2026-06-12 06:30:00 -0400"
   value="HKCategoryValueSleepAnalysisAsleepCore"/>
</HealthData>
"""


@pytest.fixture
def export_xml(tmp_path: Path) -> Path:
    """A synthetic ``export.xml`` file on disk."""
    path = tmp_path / "export.xml"
    path.write_text(SAMPLE_EXPORT_XML, encoding="utf-8")
    return path


@pytest.fixture
def export_zip(tmp_path: Path) -> Path:
    """A synthetic ``export.zip`` laid out like Apple's real export archive."""
    path = tmp_path / "export.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("apple_health_export/export.xml", SAMPLE_EXPORT_XML)
    return path
