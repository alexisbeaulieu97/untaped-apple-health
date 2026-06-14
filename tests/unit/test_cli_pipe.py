"""``--format pipe`` envelopes are tagged with a namespaced ``kind`` hint.

Producers pass ``kind=`` to core's ``render_rows`` so downstream untaped
commands can recognize the record shape. Each command syncs first (the pipe
format emits one envelope line per row, so an empty result emits nothing).
"""

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
    register_profile_settings("apple_health", AppleHealthSettings)
    db_path = tmp_path / "health.db"
    cfg = tmp_path / "config.yml"
    cfg.write_text(f'apple_health:\n  db_path: "{db_path}"\n  export_path: "{export_xml}"\n')
    monkeypatch.setenv("UNTAPED_CONFIG", str(cfg))
    get_settings.cache_clear()
    yield Env(cfg=cfg, db_path=db_path, export=export_xml)
    get_settings.cache_clear()


def _first_envelope(stdout: str) -> dict[str, object]:
    return json.loads(stdout.strip().splitlines()[0])  # type: ignore[no-any-return]


def test_metrics_pipe_is_tagged() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["metrics", "--format", "pipe"])
    assert result.exit_code == 0, result.output
    envelope = _first_envelope(result.stdout)
    assert envelope["untaped"] == "1"
    assert envelope["kind"] == "health.metric"


def test_metrics_drilldown_pipe_has_its_own_kind() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["metrics", "--type", "heart-rate", "--format", "pipe"])
    assert result.exit_code == 0, result.output
    envelope = _first_envelope(result.stdout)
    assert envelope["kind"] == "health.metric-source"


def test_query_pipe_is_tagged() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["query", "--type", "heart-rate", "--format", "pipe"])
    assert result.exit_code == 0, result.output
    envelope = _first_envelope(result.stdout)
    assert envelope["untaped"] == "1"
    assert envelope["kind"] == "health.record"


def test_status_pipe_is_tagged() -> None:
    CliInvoker().invoke(app, ["sync"])
    result = CliInvoker().invoke(app, ["status", "--format", "pipe"])
    assert result.exit_code == 0, result.output
    envelope = _first_envelope(result.stdout)
    assert envelope["untaped"] == "1"
    assert envelope["kind"] == "health.status"
