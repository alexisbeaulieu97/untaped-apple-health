# AGENTS.md — untaped-apple-health

The Apple Health plugin for `untaped`. It mirrors an Apple Health `export.xml`
into a local SQLite database and exposes filter/aggregate queries over it. The
analysis intelligence lives in the agent skill, not in hard-coded commands.

## Architecture (DDD, mirrors the other untaped plugins)

- `domain/` — pure, no I/O: the `Record` value object, metric-type aliases, the
  `QuerySpec` value object + bin-size parsing, and date/clock parsing.
- `infrastructure/` —
  - `export_reader.py`: streaming `iterparse` over `export.xml` (and the
    `apple_health_export/export.xml` member inside a `.zip`), yielding every
    `<Record>` with its metadata. Memory-safe for multi-hundred-MB exports.
  - `database.py`: SQLite schema, snapshot-rebuild ingest, and query execution
    (filters + aggregation). Owns the data-dir / DB path.
- `application/` — use-cases: `SyncExport`, `build_query_spec` (the single
  query-input validation point), and `report_status`.
- `cli/` — thin Cyclopts commands; parse args + config, call a use-case, render
  via core's `render_rows`. JSON is the agent-facing default.
- `skills/untaped-apple-health/SKILL.md` — how an agent should query/interpret.

## Hard rules

1. **The plugin exposes data; the agent analyses it.** Do not add hard-coded
   medication/titration/correlation commands. New capability = a new query
   shape or a new skill recipe, not frozen statistics.
2. **Queries must reduce server-side.** Health exports are huge. Every `query`
   path must support filtering + aggregation so responses stay small; never
   stream raw records unbounded (the `raw` mode is capped by `--limit`).
3. **Snapshot model.** Apple exports the complete history every time, so `sync`
   rebuilds the DB from scratch. No incremental merge, no dedup.
4. **Timestamps are naive local wall-clock** (tz stripped on ingest, matching
   the original script). This is what makes time-of-day-window filtering work.
5. **Health data is sensitive.** The DB lives under the untaped data dir with
   `0600` permissions. Never log record values. Never commit real exports or
   fixtures derived from real data — tests use tiny synthetic XML only.

## Plugin contract

API version 5 (`untaped>=0.5.1`): `manifest()` returns a `PluginManifest` with
a `CliSpec`, `profile_settings={"apple_health": AppleHealthSettings}`, and a
`SkillSpec`. `sync` uses the v5 `ui.progress()` capability for the import. Keep
the CLI import lazy (the `CliSpec.import_path` + PEP 562 `__getattr__` in the
package root) so `untaped --help` never imports the command stack.

## Typed pipe format (`--format pipe`)

Requires `untaped>=0.5.1`. Each row-producing command tags its `--format pipe`
NDJSON envelopes with a namespaced `kind` hint via `render_rows(..., kind=...)`:

- `metrics` → `health.metric` (per-source drill-in via `--type` → `health.metric-source`)
- `query`   → `health.record`
- `status`  → `health.status`

(`sync` produces no rows, so it has no `kind`.)

## Development

```bash
uv sync
uv run pytest        # coverage gate: 80%
uv run mypy
uv run ruff check --fix
uv run ruff format
```

Bump `version` in `pyproject.toml` with any user-facing change. Release per the
core `untaped` AGENTS.md § Releasing (gates → PR → merge → `gh release create`).
