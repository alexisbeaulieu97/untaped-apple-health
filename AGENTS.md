# AGENTS.md — untaped-apple-health

A standalone CLI built on the `untaped` SDK, invoked as `untaped-apple-health`.
It mirrors an Apple Health `export.xml` into a local SQLite database and exposes
filter/aggregate queries over it. The analysis intelligence lives in the agent
skill, not in hard-coded commands. The `untaped` SDK owns config loading, output
helpers, profile selection, the shared `config` / `profile` / `skills` command
groups, and shared errors.

## Architecture (DDD, mirrors the other untaped tools)

- `domain/` — pure, no I/O: the `Record` value object, metric-type aliases, the
  `QuerySpec` value object + bin-size parsing, and date/clock parsing.
- `infrastructure/` —
  - `export_reader.py`: streaming `iterparse` over `export.xml` (and the
    `apple_health_export/export.xml` member inside a `.zip`), yielding every
    `<Record>` with its metadata. Memory-safe for multi-hundred-MB exports.
  - `database.py`: SQLite schema, snapshot-rebuild ingest, and query execution
    (filters + aggregation). Owns the data-dir / DB path.
- `application/` — use-cases: `SyncExport`, `resolve_export_path` (the single
  sync-input validation point — runs before the DB is opened so a sync with
  nothing to import leaves no empty mirror), `build_query_spec` (the single
  query-input validation point), and `report_status`.
- `cli/` — thin Cyclopts commands; parse args + config, call a use-case, render
  via core's `render_rows`. JSON is the agent-facing default.
- `skills/untaped-apple-health/SKILL.md` — how an agent should query/interpret.

## Hard rules

1. **The tool exposes data; the agent analyses it.** Do not add hard-coded
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

## Tool entry point

`untaped-apple-health` is a standalone CLI (`untaped>=0.6`). `__main__.main()`
hands the Cyclopts `app` (re-exported from `untaped_apple_health.cli`) and a
`ToolSpec` to the SDK's `run_tool`. The `ToolSpec` declares
`command="untaped-apple-health"`, `section="apple_health"` (underscored —
note the command itself is hyphenated), `profile_model=AppleHealthSettings`,
and one `SkillAsset` for the packaged agent skill. `run_tool` mounts the shared
`config` / `profile` / `skills` groups, wires the `--profile` / `--verbose`
root options, and runs under the SDK's error contract. The console script is
declared in `pyproject.toml` under `[project.scripts]` as
`untaped-apple-health = "untaped_apple_health.__main__:main"`; there is no
`untaped.plugins` entry point. `sync` uses the SDK's `ui.progress()` capability
for the import. The package root re-exports `app` lazily (PEP 562
`__getattr__`) so importing the package never eagerly pulls in the command
tree.

## Typed pipe format (`--format pipe`)

Each row-producing command tags its `--format pipe`
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
uv run untaped-apple-health --help
```

Bump `version` in `pyproject.toml` with any user-facing change. Release per the
core `untaped` AGENTS.md § Releasing (gates → PR → merge → `gh release create`).
