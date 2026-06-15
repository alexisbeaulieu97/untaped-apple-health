"""Entry-point and SDK-wiring checks for the untaped-apple-health CLI.

untaped-apple-health is now a standalone tool: it ships a console script that
runs ``run_tool(app, SPEC)`` instead of an ``untaped.plugins`` entry point.
These tests drive the wired app's meta exactly as the installed CLI would.
``AppleHealthSettings`` holds only filesystem paths (no secrets), so the
github reference's redaction test is replaced by a config round-trip.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from importlib.metadata import entry_points
from pathlib import Path

import pytest
from untaped.api import build_tool_app
from untaped.identity import reset_tool_command
from untaped.settings import get_settings, reset_config_registry_for_tests
from untaped.testing import CliInvoker

from untaped_apple_health.__main__ import SPEC, main
from untaped_apple_health.cli import app as _build_reference_app  # noqa: F401 - import smoke

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    cfg = tmp_path / "config.yml"
    monkeypatch.setenv("UNTAPED_CONFIG", str(cfg))
    monkeypatch.delenv("UNTAPED_PROFILE", raising=False)
    reset_config_registry_for_tests()
    reset_tool_command()
    get_settings.cache_clear()
    yield cfg
    reset_config_registry_for_tests()
    reset_tool_command()
    get_settings.cache_clear()


def _wired():
    from untaped_apple_health.cli import app

    return build_tool_app(app, SPEC)


def test_console_script_is_declared() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert (
        data["project"]["scripts"]["untaped-apple-health"]
        == "untaped_apple_health.__main__:main"
    )


def test_no_untaped_plugins_entry_point() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert "untaped.plugins" not in data["project"].get("entry-points", {})
    assert not [ep for ep in entry_points(group="untaped.plugins") if ep.name == "apple-health"]


def test_spec_is_well_formed() -> None:
    assert SPEC.command == "untaped-apple-health"
    assert SPEC.section == "apple_health"
    assert callable(main)
    (skill,) = SPEC.skills
    assert skill.name == "untaped-apple-health"
    assert skill.source.joinpath("SKILL.md").is_file()


def test_config_round_trips_apple_health_settings(_isolate: Path) -> None:
    # AppleHealthSettings holds only paths (no secrets), so instead of a
    # redaction test we assert a value written under the tool's section is
    # read back by `config get` and listed under `apple_health.export_path`.
    _isolate.write_text(
        "profiles:\n  default:\n    apple_health:\n      export_path: /some/export.zip\n",
        encoding="utf-8",
    )
    get_settings.cache_clear()
    wired = _wired()

    get_result = CliInvoker().invoke(
        wired.meta, ["config", "get", "export_path", "--format", "raw"]
    )
    assert get_result.exit_code == 0, get_result.output
    assert "/some/export.zip" in get_result.stdout

    list_result = CliInvoker().invoke(
        wired.meta,
        ["config", "list", "--format", "raw", "--columns", "key", "--columns", "value"],
    )
    assert list_result.exit_code == 0, list_result.output
    assert "apple_health.export_path" in list_result.stdout


def test_profile_group_and_flag_resolve(_isolate: Path) -> None:
    _isolate.write_text(
        "profiles:\n"
        "  work:\n"
        "    apple_health:\n"
        "      export_path: /work/export.zip\n"
        "active: work\n",
        encoding="utf-8",
    )
    get_settings.cache_clear()
    wired = _wired()
    result = CliInvoker().invoke(
        wired.meta,
        ["config", "get", "export_path", "--format", "raw", "--profile", "work"],
    )
    assert result.exit_code == 0, result.output
    assert "/work/export.zip" in result.stdout


def test_program_name_is_tool_command(_isolate: Path) -> None:
    wired = _wired()
    result = CliInvoker().invoke(wired.meta, ["--help"])
    assert "untaped-apple-health" in result.output
