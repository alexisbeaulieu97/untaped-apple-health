# untaped-apple-health

`untaped-apple-health` turns your Apple Health export into a local, queryable
database for [`untaped`](https://github.com/alexisbeaulieu97/untaped). It adds
the `untaped apple-health` command group:

- `apple-health sync` — import `export.xml` (or `export.zip`) into a local
  SQLite mirror.
- `apple-health metrics` — list the metric types present in your export, with
  counts, date ranges, sources, and units.
- `apple-health query` — filter and aggregate records (server-side, so the
  output stays small) for analysis.
- `apple-health status` — report what was synced and whether your export is
  newer than the last sync.

The plugin deliberately does **not** hard-code any one analysis. It exposes
the data; the accompanying agent skill teaches an assistant how to query and
interpret it (dose-response, resting-HR trends, sleep, blood pressure, …).

> Health data is personal. The local database lives under your untaped data
> directory with owner-only permissions, and nothing about it is sent anywhere.

## Install

Install both `untaped` and this plugin from git:

```bash
uv tool install "git+https://github.com/alexisbeaulieu97/untaped.git" \
  --with "untaped-apple-health @ git+https://github.com/alexisbeaulieu97/untaped-apple-health.git" \
  --no-sources \
  --force
```

For managed plugin state, editable source installs, and multi-plugin sync
examples, see the core
[`untaped` plugin docs](https://github.com/alexisbeaulieu97/untaped/blob/main/docs/plugins.md).

This plugin also contributes the `untaped-apple-health` agent skill. After the
plugin is installed, use the core
[`untaped` agent skill docs](https://github.com/alexisbeaulieu97/untaped/blob/main/docs/skills.md)
to install it for Codex or Claude.

## Getting your export

On the iPhone Health app: profile picture → **Export All Health Data** → share
the resulting `export.zip`. Point `apple-health sync` at that file (or set
`apple_health.export_path` in your profile so `sync` needs no argument).

## Commands

```text
untaped apple-health sync --export ~/Downloads/export.zip
untaped apple-health metrics
untaped apple-health metrics --type heart-rate
untaped apple-health query --type heart-rate --from 2026-06-12 \
  --time-from 07:00 --time-to 13:00 --agg bin --bin 15min
untaped apple-health status
```

## Development

```bash
uv sync
uv run pytest
uv run mypy
uv run ruff check --fix
uv run ruff format
uv run untaped apple-health --help
```

See [AGENTS.md](./AGENTS.md) for architecture rules and plugin-specific
invariants.
