"""Friendly aliases over Apple's verbose ``HKQuantityTypeIdentifier*`` names.

The query and metrics commands accept either a friendly alias (``heart-rate``)
or a raw HK identifier. Unknown names pass through untouched so the agent can
always fall back to a raw identifier it discovered via ``apple-health metrics``.
"""

from __future__ import annotations

_ALIASES: dict[str, str] = {
    "heart-rate": "HKQuantityTypeIdentifierHeartRate",
    "resting-heart-rate": "HKQuantityTypeIdentifierRestingHeartRate",
    "walking-heart-rate": "HKQuantityTypeIdentifierWalkingHeartRateAverage",
    "hrv": "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
    "bp-systolic": "HKQuantityTypeIdentifierBloodPressureSystolic",
    "bp-diastolic": "HKQuantityTypeIdentifierBloodPressureDiastolic",
    "respiratory-rate": "HKQuantityTypeIdentifierRespiratoryRate",
    "spo2": "HKQuantityTypeIdentifierOxygenSaturation",
    "body-temperature": "HKQuantityTypeIdentifierBodyTemperature",
    "steps": "HKQuantityTypeIdentifierStepCount",
    "distance-walking": "HKQuantityTypeIdentifierDistanceWalkingRunning",
    "active-energy": "HKQuantityTypeIdentifierActiveEnergyBurned",
    "basal-energy": "HKQuantityTypeIdentifierBasalEnergyBurned",
    "body-mass": "HKQuantityTypeIdentifierBodyMass",
    "body-fat": "HKQuantityTypeIdentifierBodyFatPercentage",
    "sleep": "HKCategoryTypeIdentifierSleepAnalysis",
}

_REVERSE: dict[str, str] = {identifier: alias for alias, identifier in _ALIASES.items()}


def resolve_metric_type(name: str) -> str:
    """Return the HK identifier for ``name`` (alias or already-raw identifier)."""
    return _ALIASES.get(name.lower(), name)


def alias_for(identifier: str) -> str | None:
    """Return the friendly alias for an HK identifier, or ``None`` if there is none."""
    return _REVERSE.get(identifier)
