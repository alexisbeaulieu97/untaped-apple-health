"""Use-cases orchestrating the export reader and the SQLite database."""

from __future__ import annotations

from pathlib import Path

from untaped.api import ConfigError

from untaped_apple_health.domain.metrics import resolve_metric_type
from untaped_apple_health.domain.query import Aggregation, QuerySpec, bin_size_minutes
from untaped_apple_health.domain.timeparse import parse_clock, resolve_date
from untaped_apple_health.infrastructure.database import HealthDatabase, SyncResult
from untaped_apple_health.infrastructure.export_reader import read_records


class SyncExport:
    """Import an ``export.xml`` / ``export.zip`` into the database (full snapshot)."""

    def __init__(self, database: HealthDatabase) -> None:
        self._database = database

    def __call__(self, export_path: Path, *, synced_at: str) -> SyncResult:
        if not export_path.exists():
            raise ConfigError(
                f"Apple Health export not found at {export_path}. Pass --export PATH or set "
                "`apple_health.export_path` in your profile (Health app → Export All Health Data)."
            )
        return self._database.rebuild(
            read_records(export_path),
            source_path=export_path,
            synced_at=synced_at,
            source_mtime=export_path.stat().st_mtime,
        )


def resolve_export_path(explicit: Path | None, configured: Path | None) -> Path:
    """Resolve and validate the export to sync, before any database is opened.

    The single sync-input validation point (mirrors :func:`build_query_spec`): an
    unconfigured export *and* a missing file both surface as :class:`ConfigError`
    — a clean CLI error — and crucially this runs *before* ``open_session`` creates
    the DB, so a sync with nothing to import leaves no empty mirror behind.
    """
    candidate = explicit or configured
    if candidate is None:
        raise ConfigError(
            "No Apple Health export configured. Pass --export PATH or set "
            "`apple_health.export_path` (Health app → Export All Health Data)."
        )
    export_path = Path(candidate).expanduser()
    if not export_path.exists():
        raise ConfigError(
            f"Apple Health export not found at {export_path}. Pass --export PATH or set "
            "`apple_health.export_path` in your profile (Health app → Export All Health Data)."
        )
    return export_path


def build_query_spec(
    *,
    types: tuple[str, ...] = (),
    date_from: str | None = None,
    date_to: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    source: str | None = None,
    where_meta: tuple[tuple[str, str], ...] = (),
    agg: Aggregation = "raw",
    bin_size: str | None = None,
    limit: int = 1000,
) -> QuerySpec:
    """Validate query inputs, resolve friendly aliases, and assemble a :class:`QuerySpec`.

    This is the single validation point for a query: bad dates, times, bin
    sizes, or limits surface as :class:`ConfigError` (a clean CLI error) rather
    than a traceback from deep in the database layer. ``today`` / ``yesterday``
    are resolved here too — without this the keywords reach SQL as literal
    strings and silently match nothing.
    """
    if agg == "bin" and bin_size is None:
        raise ConfigError("--agg bin requires --bin, e.g. 15min, 1h, or 1d")
    if bin_size is not None:
        _validate_bin_size(bin_size)
    if limit < 1:
        raise ConfigError("--limit must be >= 1")
    return QuerySpec(
        types=tuple(resolve_metric_type(metric) for metric in types),
        date_from=_resolve_date(date_from, "--from"),
        date_to=_resolve_date(date_to, "--to"),
        time_from=_resolve_clock(time_from, "--time-from"),
        time_to=_resolve_clock(time_to, "--time-to"),
        source=source,
        where_meta=where_meta,
        agg=agg,
        bin_size=bin_size,
        limit=limit,
    )


def _resolve_date(value: str | None, flag: str) -> str | None:
    if value is None:
        return None
    try:
        return resolve_date(value).isoformat()
    except ValueError:
        raise ConfigError(
            f"{flag} must be YYYY-MM-DD, today, or yesterday; got {value!r}"
        ) from None


def _resolve_clock(value: str | None, flag: str) -> str | None:
    if value is None:
        return None
    try:
        return parse_clock(value).strftime("%H:%M")
    except ValueError:
        raise ConfigError(f"{flag} must be HH:MM; got {value!r}") from None


def _validate_bin_size(bin_size: str) -> None:
    try:
        bin_size_minutes(bin_size)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def report_status(database: HealthDatabase, export_path: Path | None) -> dict[str, object]:
    """The sync status plus whether the export on disk is newer than the last sync.

    ``export_path`` is the live export to compare against (an explicit
    ``--export`` or the configured path). When neither is given, fall back to
    the path recorded at sync time so staleness still resolves.
    """
    status = database.status()
    if status is None:
        return {"synced": False}
    report: dict[str, object] = {**status, "synced": True}
    source = export_path or _stored_source(status)
    if source is not None and source.exists():
        stored = status.get("source_mtime")
        current = source.stat().st_mtime
        report["stale"] = bool(isinstance(stored, (int, float)) and current > stored)
    else:
        report["stale"] = None
    return report


def _stored_source(status: dict[str, object]) -> Path | None:
    source_path = status.get("source_path")
    return Path(source_path) if isinstance(source_path, str) else None
