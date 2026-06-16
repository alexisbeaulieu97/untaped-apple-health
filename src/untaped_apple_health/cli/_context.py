"""Composition root: resolve settings and open the database for one command.

Mirrors the other plugins' one-shot context pattern — ``app_context()``
resolves settings exactly once (honoring the root ``--profile`` selector) and
hands back a frozen snapshot, so nothing leaks into ambient process state.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from untaped.api import app_context

from untaped_apple_health.infrastructure.database import HealthDatabase, default_database_path
from untaped_apple_health.settings import AppleHealthSettings

if TYPE_CHECKING:
    from untaped.api import UiContext


@contextmanager
def open_session() -> Iterator[tuple[HealthDatabase, AppleHealthSettings, UiContext]]:
    """Yield an open database, the resolved settings, and a themed UI context."""
    context = app_context()
    settings = context.section("apple_health", AppleHealthSettings)
    # strict=False: a misconfigured theme must not fail an otherwise-valid query.
    ui = context.ui(strict=False)
    db_path = (settings.db_path or default_database_path()).expanduser()
    parent = db_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    # Health data is sensitive: keep the data dir owner-only (the DB file is
    # chmod 0600 in HealthDatabase.open). mkdir's mode is umask-masked and is
    # ignored when the dir already exists, so set it explicitly here.
    os.chmod(parent, 0o700)
    with HealthDatabase.open(db_path) as database:
        yield database, settings, ui
