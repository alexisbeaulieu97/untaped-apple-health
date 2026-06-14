"""Untaped plugin manifest for the Apple Health domain.

API v5: declares the CLI (via a lazy ``CliSpec`` import path so ``untaped
--help`` never imports the command stack), the profile settings section, and
the agent skill. ``sync`` uses the v5 ``ui.progress()`` capability.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from untaped.api import CliSpec, PluginManifest, SkillSpec

from untaped_apple_health.settings import AppleHealthSettings


class AppleHealthPlugin:
    """Entry-point plugin object exposed through ``untaped.plugins``."""

    id = "apple-health"
    untaped_api_version = 5

    def manifest(self) -> PluginManifest:
        """Declare the Apple Health CLI, profile settings, and agent skill."""
        return PluginManifest(
            clis=(
                CliSpec(
                    name="apple-health",
                    import_path="untaped_apple_health.cli:app",
                    help="Query your Apple Health export as a local database.",
                ),
            ),
            profile_settings={"apple_health": AppleHealthSettings},
            skills=(
                SkillSpec(
                    name="untaped-apple-health",
                    source=Path(
                        str(
                            files("untaped_apple_health").joinpath("skills", "untaped-apple-health")
                        )
                    ),
                    description="Query and analyze the user's Apple Health data.",
                ),
            ),
        )


plugin = AppleHealthPlugin()
