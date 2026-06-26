# untaped-apple-health

`untaped-apple-health` turns your Apple Health export into a local, queryable
database. It is a standalone CLI built on the
[`untaped`](https://github.com/alexisbeaulieu97/untaped) SDK, invoked as
`untaped-apple-health`, with these commands:

- `untaped-apple-health sync` — import `export.xml` (or `export.zip`) into a
  local SQLite mirror.
- `untaped-apple-health metrics` — list the metric types present in your
  export, with counts, date ranges, sources, and units.
- `untaped-apple-health query` — filter and aggregate records (server-side, so
  the output stays small) for analysis.
- `untaped-apple-health status` — report what was synced and whether your
  export is newer than the last sync.

It also ships the shared `config`, `profile`, and `skills` command groups every
untaped tool provides.

The tool deliberately does **not** hard-code any one analysis. It exposes the
data; the accompanying agent skill teaches an assistant how to query and
interpret it (dose-response, resting-HR trends, sleep, blood pressure, …).

> Health data is personal. The local database lives under your untaped data
> directory with owner-only permissions, and nothing about it is sent anywhere.

## Install

```bash
uv tool install untaped-apple-health
```

This also installs the `untaped-apple-health` agent skill; install it for Codex
or Claude with `untaped-apple-health skills install`.

> **Migration note:** `untaped-apple-health` used to be an `untaped` plugin
> (invoked through the old `untaped` command's `apple-health` group). It is now
> an independent CLI: `uv tool install untaped-apple-health` and call
> `untaped-apple-health …` directly.

## Getting your export

On the iPhone Health app: profile picture → **Export All Health Data** → share
the resulting `export.zip`. Point `untaped-apple-health sync` at that file (or
set `apple_health.export_path` in your profile so `sync` needs no argument):

```bash
untaped-apple-health config set export_path ~/Downloads/export.zip
```

## Commands

```text
untaped-apple-health sync --export ~/Downloads/export.zip
untaped-apple-health metrics
untaped-apple-health metrics --type heart-rate
untaped-apple-health query --type heart-rate --from 2026-06-12 \
  --time-from 07:00 --time-to 13:00 --agg bin --bin 15min
untaped-apple-health status
untaped-apple-health config|profile|skills ...
```

Settings are stored per profile in `~/.untaped/config.yml` (shared with the
other untaped tools). `--profile <name>` works in any token position.

## Development

```bash
uv sync
uv run pytest
uv run mypy
uv run ruff check --fix
uv run ruff format
uv run untaped-apple-health --help
```

See [AGENTS.md](./AGENTS.md) for architecture rules and tool-specific
invariants.

## Security

Please report suspected vulnerabilities privately. See
[SECURITY.md](./SECURITY.md).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) and [AGENTS.md](./AGENTS.md) for the
local workflow, architecture rules, and tool-specific invariants.

## License

MIT. See [LICENSE](./LICENSE).
