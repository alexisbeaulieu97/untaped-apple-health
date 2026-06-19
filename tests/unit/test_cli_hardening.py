"""Pre-ship hardening: query-input validation, date keywords, sleep duration,
atomic sync, and status staleness — all exercised through the public CLI.

These cover the failure modes that unit-level helper tests missed: the
``today``/``yesterday`` keywords were resolved by ``timeparse`` yet never wired
into the query path, bad input tracebacked instead of erroring cleanly, and a
corrupt export wiped the existing mirror.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from untaped.settings import get_settings, register_profile_settings
from untaped.testing import CliInvoker, CliResult

from untaped_apple_health.cli import app
from untaped_apple_health.settings import AppleHealthSettings

HEART_RATE = "HKQuantityTypeIdentifierHeartRate"


@dataclass
class Env:
    cfg: Path
    db_path: Path
    export: Path


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, export_xml: Path) -> Iterator[Env]:
    register_profile_settings("apple_health", AppleHealthSettings)
    db_path = tmp_path / "health.db"
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        "profiles:\n  default:\n    apple_health:\n"
        f'      db_path: "{db_path}"\n      export_path: "{export_xml}"\n'
    )
    monkeypatch.setenv("UNTAPED_CONFIG", str(cfg))
    get_settings.cache_clear()
    yield Env(cfg=cfg, db_path=db_path, export=export_xml)
    get_settings.cache_clear()


def _write_export(path: Path, records: list[tuple[str, str, str]]) -> None:
    """Write a minimal export.xml from ``(type, 'YYYY-MM-DD HH:MM:SS', value)`` rows."""
    body = "\n".join(
        f'<Record type="{t}" sourceName="Test" unit="count/min" '
        f'startDate="{s} -0400" endDate="{s} -0400" value="{v}"/>'
        for t, s, v in records
    )
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<HealthData>\n{body}\n</HealthData>\n',
        encoding="utf-8",
    )


def _assert_clean_error(result: CliResult) -> None:
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output


# -- A2: date / time keywords are resolved before they reach SQL --------------


def test_from_today_keyword_filters_to_today(tmp_path: Path) -> None:
    today = dt.date.today()
    old = today - dt.timedelta(days=3)
    export = tmp_path / "dated.xml"
    _write_export(
        export,
        [(HEART_RATE, f"{today} 08:00:00", "70"), (HEART_RATE, f"{old} 08:00:00", "60")],
    )
    CliInvoker().invoke(app, ["sync", "--export", str(export)])
    result = CliInvoker().invoke(
        app, ["query", "--type", "heart-rate", "--from", "today", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)
    assert [row["value"] for row in rows] == [70.0]  # the 3-day-old sample is excluded


def test_from_yesterday_keyword_runs_and_includes_recent(tmp_path: Path) -> None:
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    export = tmp_path / "dated.xml"
    _write_export(
        export,
        [(HEART_RATE, f"{today} 08:00:00", "70"), (HEART_RATE, f"{yesterday} 08:00:00", "65")],
    )
    CliInvoker().invoke(app, ["sync", "--export", str(export)])
    result = CliInvoker().invoke(
        app, ["query", "--type", "heart-rate", "--from", "yesterday", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    assert {row["value"] for row in json.loads(result.stdout)} == {70.0, 65.0}


# -- A3: raw output carries `end` so sleep duration is computable -------------


def test_sleep_raw_includes_end() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(
        app, ["query", "--type", "sleep", "--agg", "raw", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    [row] = json.loads(result.stdout)
    assert row["start"] == "2026-06-12 00:10:00"
    assert row["end"] == "2026-06-12 06:30:00"
    assert row["value_text"] == "HKCategoryValueSleepAnalysisAsleepCore"


# -- A4 / B1 / B2: invalid input is a clean error, never a traceback ----------


def test_bad_date_is_clean_error() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["query", "--from", "notadate", "--format", "json"])
    _assert_clean_error(result)
    assert "--from" in result.output


def test_bad_time_is_clean_error() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(
        app, ["query", "--type", "heart-rate", "--time-from", "9pm", "--format", "json"]
    )
    _assert_clean_error(result)
    assert "--time-from" in result.output


def test_bin_without_size_is_clean_error() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["query", "--type", "heart-rate", "--agg", "bin"])
    _assert_clean_error(result)
    assert "--bin" in result.output


def test_unparseable_bin_is_clean_error() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(
        app, ["query", "--type", "heart-rate", "--agg", "bin", "--bin", "5xyz"]
    )
    _assert_clean_error(result)
    assert "--bin" in result.output


def test_multi_day_bin_is_clean_error() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(
        app, ["query", "--type", "heart-rate", "--agg", "bin", "--bin", "2d"]
    )
    _assert_clean_error(result)
    assert "1d" in result.output


def test_nonpositive_limit_is_clean_error() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["query", "--type", "heart-rate", "--limit", "0"])
    _assert_clean_error(result)
    assert "--limit" in result.output


# -- B3 + A1: a corrupt export errors cleanly AND preserves the prior mirror --


def test_zip_without_export_is_clean_error_and_preserves_data(tmp_path: Path) -> None:
    CliInvoker().invoke(app, ["sync"])  # good snapshot: 6 records
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("apple_health_export/notes.txt", "no xml here")

    result = CliInvoker().invoke(app, ["sync", "--export", str(bad)])
    _assert_clean_error(result)
    assert "export.xml" in result.output

    status = CliInvoker().invoke(app, ["status", "--format", "json"])
    row = json.loads(status.stdout)  # single entity → bare object {…}
    assert row["record_count"] == 6  # the failed sync did not wipe the mirror


# -- C1: status staleness falls back to the stored source, and honors --export


def test_status_staleness_without_configured_export(env: Env) -> None:
    env.cfg.write_text(
        f'profiles:\n  default:\n    apple_health:\n      db_path: "{env.db_path}"\n'
    )  # drop export_path
    get_settings.cache_clear()
    CliInvoker().invoke(app, ["sync", "--export", str(env.export)])
    result = CliInvoker().invoke(app, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    row = json.loads(result.stdout)  # single entity → bare object {…}
    assert row["synced"] is True
    assert row["stale"] is False  # resolved via the stored source_path, not None


def test_status_export_flag_detects_newer_file(env: Env, tmp_path: Path) -> None:
    CliInvoker().invoke(app, ["sync"])
    newer = tmp_path / "newer.xml"
    newer.write_text(env.export.read_text(encoding="utf-8"), encoding="utf-8")
    future = newer.stat().st_mtime + 10_000
    os.utime(newer, (future, future))
    result = CliInvoker().invoke(app, ["status", "--export", str(newer), "--format", "json"])
    assert result.exit_code == 0, result.output
    row = json.loads(result.stdout)  # single entity → bare object {…}
    assert row["stale"] is True


# -- Validate-first: a sync with nothing to import must not create the DB -----


def test_sync_no_export_configured_does_not_create_db(env: Env) -> None:
    env.cfg.write_text(
        f'profiles:\n  default:\n    apple_health:\n      db_path: "{env.db_path}"\n'
    )  # drop export_path
    get_settings.cache_clear()
    result = CliInvoker().invoke(app, ["sync"])
    _assert_clean_error(result)
    assert "export" in result.output.lower()
    assert not env.db_path.exists()  # no empty mirror left behind


def test_sync_missing_export_file_does_not_create_db(env: Env, tmp_path: Path) -> None:
    result = CliInvoker().invoke(app, ["sync", "--export", str(tmp_path / "nope.xml")])
    _assert_clean_error(result)
    assert "not found" in result.output.lower()
    assert not env.db_path.exists()


# -- Default-path layout: the DB lives in its own subdir; chmod scopes to it --
# The `env` fixture always configures an explicit db_path, so these drop it and
# point XDG at a temp dir to exercise default_database_path() + the 0700 chmod.


def test_failed_default_sync_leaves_shared_dir_untouched(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env.cfg.write_text(
        "profiles:\n  default:\n    apple_health: {}\n"
    )  # no db_path, no export_path → default path
    xdg = tmp_path / "xdg"
    shared = xdg / "untaped"
    shared.mkdir(parents=True)
    shared.chmod(0o755)
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    get_settings.cache_clear()

    result = CliInvoker().invoke(app, ["sync"])
    _assert_clean_error(result)
    assert not (shared / "apple-health").exists()  # plugin dir/DB never created
    assert stat.S_IMODE(shared.stat().st_mode) == 0o755  # shared dir not tightened


def test_default_sync_scopes_chmod_to_plugin_subdir(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env.cfg.write_text(
        f'profiles:\n  default:\n    apple_health:\n      export_path: "{env.export}"\n'
    )  # no db_path
    xdg = tmp_path / "xdg"
    shared = xdg / "untaped"
    shared.mkdir(parents=True)
    shared.chmod(0o755)
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    get_settings.cache_clear()

    result = CliInvoker().invoke(app, ["sync"])
    assert result.exit_code == 0, result.output
    assert (shared / "apple-health" / "apple-health.db").exists()
    assert stat.S_IMODE((shared / "apple-health").stat().st_mode) == 0o700  # plugin dir tightened
    assert stat.S_IMODE(shared.stat().st_mode) == 0o755  # shared dir untouched
