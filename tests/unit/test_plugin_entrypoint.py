"""Entry point and root-app integration checks for the apple-health plugin."""

from __future__ import annotations

from collections.abc import Iterator
from importlib.metadata import entry_points
from pathlib import Path

import pytest
from untaped.api import CliSpec, PluginManifest, PluginRegistry
from untaped.main import build_app
from untaped.plugins import register_plugins
from untaped.settings import get_settings
from untaped.testing import CliInvoker

from untaped_apple_health.plugin import plugin as apple_health_plugin
from untaped_apple_health.settings import AppleHealthSettings


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("UNTAPED_CONFIG", str(tmp_path / "config.yml"))
    monkeypatch.delenv("UNTAPED_PROFILE", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_entry_point_is_declared() -> None:
    matches = [
        ep
        for ep in entry_points(group="untaped.plugins")
        if ep.name == "apple-health" and ep.value == "untaped_apple_health.plugin:plugin"
    ]
    assert matches


def test_declares_api_version_5() -> None:
    assert apple_health_plugin.untaped_api_version == 5


def test_manifest_shape() -> None:
    manifest = apple_health_plugin.manifest()

    assert isinstance(manifest, PluginManifest)
    cli_spec = manifest.clis[0]
    assert isinstance(cli_spec, CliSpec)
    assert cli_spec.name == "apple-health"
    assert cli_spec.import_path == "untaped_apple_health.cli:app"
    assert cli_spec.help
    assert manifest.profile_settings == {"apple_health": AppleHealthSettings}
    assert [skill.name for skill in manifest.skills] == ["untaped-apple-health"]
    assert not manifest.root_options
    assert manifest.settings_layout is None
    assert not manifest.state_settings
    assert not manifest.themes
    assert not manifest.diagnostics


def test_root_app_can_register_plugin() -> None:
    app = build_app(plugins=[apple_health_plugin])

    result = CliInvoker().invoke(app, ["apple-health", "--help"])

    assert result.exit_code == 0, result.output
    assert "Apple Health" in result.output


def test_plugin_registers_agent_skill() -> None:
    registry = PluginRegistry()

    register_plugins(registry, [apple_health_plugin])

    assert registry.load_errors == []
    spec = registry.skills["untaped-apple-health"]
    assert spec.source.joinpath("SKILL.md").is_file()
    assert "apple-health" in registry.lazy_clis
