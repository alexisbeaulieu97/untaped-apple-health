"""Profile settings contributed by the Apple Health plugin.

These let ``sync`` find the export and the local mirror without arguments. They
hold only filesystem paths — no secrets — so no ``SecretStr`` is needed.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class AppleHealthSettings(BaseModel):
    """Where the Apple Health export lives and where to keep the local mirror."""

    export_path: Path | None = None
    db_path: Path | None = None
