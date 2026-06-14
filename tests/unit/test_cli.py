"""End-to-end CLI behavior, invoking the apple-health app directly."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from untaped.settings import get_settings, register_profile_settings
from untaped.testing import CliInvoker

from untaped_apple_health.cli import app
from untaped_apple_health.settings import AppleHealthSettings


@dataclass
class Env:
    cfg: Path
    db_path: Path
    export: Path


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, export_xml: Path) -> Iterator[Env]:
    # Invoking the app directly skips plugin registration, so mirror the
    # manifest's profile-settings contribution before each test.
    register_profile_settings("apple_health", AppleHealthSettings)
    db_path = tmp_path / "health.db"
    cfg = tmp_path / "config.yml"
    cfg.write_text(f'apple_health:\n  db_path: "{db_path}"\n  export_path: "{export_xml}"\n')
    monkeypatch.setenv("UNTAPED_CONFIG", str(cfg))
    get_settings.cache_clear()
    yield Env(cfg=cfg, db_path=db_path, export=export_xml)
    get_settings.cache_clear()


HEART_RATE = "HKQuantityTypeIdentifierHeartRate"


def test_sync_reports_record_count() -> None:
    result = CliInvoker().invoke(app, ["sync"])
    assert result.exit_code == 0, result.output
    assert "6" in result.output


def test_metrics_lists_types_after_sync() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["metrics", "--format", "json"])
    assert result.exit_code == 0, result.output
    rows = {row["type"]: row for row in json.loads(result.stdout)}
    assert rows[HEART_RATE]["count"] == 3
    assert rows[HEART_RATE]["alias"] == "heart-rate"


def test_metrics_empty_before_sync_is_clean_json() -> None:
    result = CliInvoker().invoke(app, ["metrics", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == []


def test_query_raw_defaults_to_json() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["query", "--type", "heart-rate"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)
    assert len(rows) == 3
    assert all(row["type"] == HEART_RATE for row in rows)


def test_query_bin_returns_small_payload() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(
        app,
        [
            "query",
            "--type",
            "heart-rate",
            "--from",
            "2026-06-12",
            "--to",
            "2026-06-12",
            "--agg",
            "bin",
            "--bin",
            "15min",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    bins = {row["bin"] for row in json.loads(result.stdout)}
    assert bins == {"2026-06-12 07:30", "2026-06-12 11:45"}


def test_query_where_meta_filters() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(
        app,
        [
            "query",
            "--type",
            "heart-rate",
            "--where-meta",
            "HKMetadataKeyHeartRateMotionContext=1",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)) == 2


def test_status_reports_synced(env: Env) -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    [row] = json.loads(result.stdout)
    assert row["synced"] is True
    assert row["record_count"] == 6


def test_sync_without_export_errors(env: Env) -> None:
    env.cfg.write_text(f'apple_health:\n  db_path: "{env.db_path}"\n')
    get_settings.cache_clear()
    result = CliInvoker().invoke(app, ["sync"])
    assert result.exit_code != 0
    assert "export" in result.output.lower()
