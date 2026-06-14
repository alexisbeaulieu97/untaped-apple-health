"""untaped-apple-health: query your Apple Health export as a local database.

``app`` is re-exported lazily (PEP 562) so importing this package — which core
does at plugin discovery time — never pulls in the Cyclopts CLI stack. The CLI
module is imported only when ``app`` is actually accessed.
"""

from typing import Any

__all__ = ["app"]


def __getattr__(name: str) -> Any:
    if name == "app":
        # A top-level import would defeat this module's whole purpose: the PEP
        # 562 lazy re-export exists so plugin discovery does not import the CLI
        # stack. Deferring the import is inherent to the pattern.
        from untaped_apple_health.cli import app  # noqa: PLC0415

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
