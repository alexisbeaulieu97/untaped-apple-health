# Contributing

Thanks for contributing to `untaped-apple-health`.

## Local Setup

```bash
uv sync
uv run pytest
uv run mypy
uv run ruff check --fix
uv run ruff format
uv run untaped-apple-health --help
uv run pre-commit run --all-files
```

## Documentation

Update `README.md`, `AGENTS.md`, and
`src/untaped_apple_health/skills/untaped-apple-health/SKILL.md` when a change
affects command behavior, settings, workflows, output contracts, or
agent-facing usage.

## Sensitive Data

Do not include secrets, real customer configurations, real Apple Health
exports, derived personal health fixtures, production logs, or private data in
issues, tests, fixtures, or examples. Use tiny synthetic XML data for tests and
examples.
