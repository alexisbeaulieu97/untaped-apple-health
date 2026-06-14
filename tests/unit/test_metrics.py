"""Friendly metric-type aliases over Apple's HK identifiers."""

from __future__ import annotations

from untaped_apple_health.domain.metrics import alias_for, resolve_metric_type


def test_resolve_known_alias() -> None:
    assert resolve_metric_type("heart-rate") == "HKQuantityTypeIdentifierHeartRate"


def test_resolve_is_case_insensitive() -> None:
    assert resolve_metric_type("Heart-Rate") == "HKQuantityTypeIdentifierHeartRate"


def test_resolve_passes_through_raw_identifier() -> None:
    raw = "HKQuantityTypeIdentifierHeartRate"
    assert resolve_metric_type(raw) == raw


def test_resolve_passes_through_unknown_identifier() -> None:
    # An unknown raw type is assumed to be a valid HK identifier we just don't
    # have an alias for — it must reach the query unchanged.
    assert resolve_metric_type("HKQuantityTypeIdentifierSomethingNew") == (
        "HKQuantityTypeIdentifierSomethingNew"
    )


def test_alias_for_known_identifier() -> None:
    assert alias_for("HKQuantityTypeIdentifierStepCount") == "steps"


def test_alias_for_unknown_identifier_is_none() -> None:
    assert alias_for("HKQuantityTypeIdentifierSomethingNew") is None
