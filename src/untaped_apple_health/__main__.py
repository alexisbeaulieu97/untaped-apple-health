"""Console-script entrypoint for the ``untaped-apple-health`` CLI.

``untaped-apple-health`` is a standalone tool built on the untaped SDK:
``main()`` hands the Apple Health cyclopts app and a :class:`ToolSpec` to
``run_tool``, which mounts the shared ``config`` / ``profile`` / ``skills``
groups, wires the ``--profile`` / ``--verbose`` root options, and runs under
the SDK's error contract.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from untaped.api import SkillAsset, ToolSpec, run_tool

from untaped_apple_health.cli import app
from untaped_apple_health.settings import AppleHealthSettings

SPEC = ToolSpec(
    command="untaped-apple-health",
    section="apple_health",
    profile_model=AppleHealthSettings,
    skills=(
        SkillAsset(
            name="untaped-apple-health",
            source=Path(
                str(files("untaped_apple_health").joinpath("skills", "untaped-apple-health"))
            ),
            description="Query and analyze the user's Apple Health data.",
        ),
    ),
)


def main() -> object:
    """Run the ``untaped-apple-health`` CLI."""
    return run_tool(app, SPEC)


if __name__ == "__main__":
    main()
