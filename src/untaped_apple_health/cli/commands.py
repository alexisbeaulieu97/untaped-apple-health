"""Cyclopts commands: ``untaped apple-health sync / metrics / query / status``.

Thin by design — each command parses arguments, calls a use-case or the
database, and renders through core's ``render_rows``. JSON is the default for
``query`` because its primary consumer is an agent.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter
from untaped.api import (
    ColumnsOption,
    ConfigError,
    FormatOption,
    app_context,
    create_app,
    echo,
    emit,
    render_rows,
    report_errors,
)

from untaped_apple_health.application import (
    SyncExport,
    build_query_spec,
    report_status,
    resolve_export_path,
)
from untaped_apple_health.cli._context import open_session
from untaped_apple_health.domain.metrics import resolve_metric_type
from untaped_apple_health.domain.query import Aggregation
from untaped_apple_health.settings import AppleHealthSettings

ExportOption = Annotated[
    Path | None,
    Parameter(name="--export", help="Path to export.xml or export.zip (defaults to settings)."),
]
TypeListOption = Annotated[
    list[str] | None,
    Parameter(name=["--type", "-t"], help="Metric type or friendly alias; repeatable."),
]
SingleTypeOption = Annotated[
    str | None,
    Parameter(name=["--type", "-t"], help="Drill into one metric type or alias."),
]
FromOption = Annotated[
    str | None,
    Parameter(name="--from", help="Start date: YYYY-MM-DD, today, or yesterday."),
]
ToOption = Annotated[str | None, Parameter(name="--to", help="End date (inclusive): YYYY-MM-DD.")]
TimeFromOption = Annotated[
    str | None, Parameter(name="--time-from", help="Time-of-day window start, HH:MM.")
]
TimeToOption = Annotated[
    str | None, Parameter(name="--time-to", help="Time-of-day window end, HH:MM.")
]
SourceOption = Annotated[
    str | None, Parameter(name="--source", help="Only records whose source contains this text.")
]
WhereMetaOption = Annotated[
    list[str] | None,
    Parameter(name="--where-meta", help="Metadata filter key=value; repeatable."),
]
AggOption = Annotated[
    Aggregation,
    Parameter(name="--agg", help="raw (records), summary (stats), or bin (stats per interval)."),
]
BinOption = Annotated[
    str | None, Parameter(name="--bin", help="Bucket size for --agg bin: 15min, 1h, 1d.")
]
LimitOption = Annotated[int, Parameter(name="--limit", help="Maximum rows returned by --agg raw.")]

app = create_app(
    name="apple-health",
    help="Query your Apple Health export as a local database.",
)


@app.command(name="sync")
def sync_command(*, export: ExportOption = None) -> None:
    """Import an Apple Health export into the local database (full snapshot)."""
    with report_errors():
        # Validate the export *before* open_session creates/chmods the DB, so a
        # sync with nothing to import leaves no empty mirror behind.
        settings = app_context().section("apple_health", AppleHealthSettings)
        source = resolve_export_path(export, settings.export_path)
        with open_session() as (database, _settings, ui):
            with ui.progress(f"Importing {source.name}") as handle:
                handle.update("Reading and indexing records…")
                result = SyncExport(database)(source, synced_at=_now())
            echo(
                f"Synced {result.record_count:,} records "
                f"({result.first_ts} → {result.last_ts}) from {source}",
                err=True,
            )


@app.command(name="metrics")
def metrics_command(
    *,
    metric: SingleTypeOption = None,
    fmt: FormatOption = "table",
    columns: ColumnsOption = None,
) -> None:
    """List the metric types in the export — the schema to query against.

    With ``--type`` it drills into one type, breaking it down by source device.
    """
    with report_errors(), open_session() as (database, _settings, _ui):
        if metric is not None:
            rows = database.metric_sources(resolve_metric_type(metric))
            kind = "health.metric-source"
        else:
            rows = database.metric_overview()
            kind = "health.metric"
        echo(
            render_rows(
                rows,
                fmt=fmt,
                columns=columns,
                kind=kind,
                empty="No data yet — run `untaped apple-health sync` first.",
            )
        )


@app.command(name="query")
def query_command(
    *,
    metric: TypeListOption = None,
    date_from: FromOption = None,
    date_to: ToOption = None,
    time_from: TimeFromOption = None,
    time_to: TimeToOption = None,
    source: SourceOption = None,
    where_meta: WhereMetaOption = None,
    agg: AggOption = "raw",
    bin_size: BinOption = None,
    limit: LimitOption = 1000,
    fmt: FormatOption = "json",
    columns: ColumnsOption = None,
) -> None:
    """Filter and aggregate records.

    Aggregating (``--agg summary`` or ``--agg bin``) reduces the result on the
    server side, which is what keeps a query small enough to hand to an agent.
    """
    with report_errors(), open_session() as (database, _settings, _ui):
        spec = build_query_spec(
            types=tuple(metric or ()),
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            source=source,
            where_meta=_parse_meta(where_meta),
            agg=agg,
            bin_size=bin_size,
            limit=limit,
        )
        rows = database.query(spec)
        echo(
            render_rows(
                rows,
                fmt=fmt,
                columns=columns,
                kind="health.record",
                empty="No records match the query.",
            )
        )


@app.command(name="status")
def status_command(
    *,
    export: ExportOption = None,
    fmt: FormatOption = "table",
    columns: ColumnsOption = None,
) -> None:
    """Show what was synced and whether the export on disk is newer than the sync."""
    with report_errors(), open_session() as (database, settings, _ui):
        report = report_status(database, _optional_export(export, settings))
        emit(report, fmt=fmt, columns=columns, kind="health.status")


def _optional_export(explicit: Path | None, settings: AppleHealthSettings) -> Path | None:
    candidate = explicit or settings.export_path
    return Path(candidate).expanduser() if candidate is not None else None


def _parse_meta(items: list[str] | None) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for item in items or []:
        key, separator, value = item.partition("=")
        if not separator:
            raise ConfigError(f"--where-meta expects key=value, got {item!r}")
        pairs.append((key, value))
    return tuple(pairs)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
