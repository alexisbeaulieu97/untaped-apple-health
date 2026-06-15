---
name: untaped-apple-health
description: Use when querying or analyzing the user's Apple Health data — heart rate, blood pressure, sleep, steps, weight, or how a metric responds to a medication/intervention over time. The tool mirrors the Health export into a local SQLite database; you compose queries and interpret the results.
---

# untaped-apple-health

You query the user's Apple Health data through `untaped-apple-health`, a local
SQLite mirror of their Health export. **The tool exposes the data; you do the
analysis.** There is no built-in report — you compose queries and interpret the
results for the user.

## Data model

- The database is a **snapshot** of an `export.xml` the user exported from the
  iPhone Health app. It is only as current as the last sync. If results look
  stale, run `untaped-apple-health status`; if the export on disk is newer than
  the last sync (or the user just re-exported), run `untaped-apple-health sync`.
- Timestamps are **local wall-clock** (`YYYY-MM-DD HH:MM:SS`). A "time-of-day
  window" like 07:00–13:00 means that clock time on each day.
- Values are **device-reported**. Several sources (Apple Watch, iPhone, OMRON,
  third-party apps) may log the same metric; use `--source` to disambiguate.

## Workflow

1. **Discover** what's available: `untaped-apple-health metrics`. This is the
   schema — types present, counts, date ranges, source devices, units. Drill
   into one type with `--type heart-rate` for a per-device breakdown.
2. **Query**: `untaped-apple-health query …` (JSON by default).
3. **Interpret** the small, aggregated result for the user.

## Token discipline (important)

High-frequency metrics — heart rate above all — have tens of thousands of
samples. **Never pull raw heart rate over a wide range.** Always aggregate:

- `--agg summary` → count / min / max / mean / median / stdev for the matched set.
- `--agg bin --bin 15min|1h|1d` → those stats per time bucket.
- `--agg raw` only with tight filters and a small `--limit`.

`summary` and `bin` reduce **numeric** readings only; a category metric (e.g.
`sleep`, whose value is text in `value_text`) returns nothing under them — use
`--agg raw` for those.

## Query options

- `--type` friendly alias (`heart-rate`, `resting-heart-rate`, `bp-systolic`,
  `bp-diastolic`, `steps`, `sleep`, `hrv`, `spo2`, `body-mass`, …) or a raw
  `HK…` identifier from `metrics`. Repeatable.
- `--from` / `--to` date bounds (`YYYY-MM-DD`, `today`, `yesterday`).
- `--time-from` / `--time-to` time-of-day window (`HH:MM`).
- `--source` substring match on the source device (e.g. `Watch`, `OMRON`).
- `--where-meta key=value` metadata filter (repeatable).
- `--agg` / `--bin` / `--limit` as above.

## Recipes

These parameters are **starting hypotheses, not gospel** — adjust them per the
user's situation.

### Dose / intervention response (e.g. a morning medication)
Compare a metric in a window around the dose against the same window on a
control (no-dose) day. Heart rate, binned, sedentary-only to approximate resting:

```
untaped-apple-health query --type heart-rate \
  --from 2026-06-12 --to 2026-06-12 --time-from 07:00 --time-to 13:00 \
  --where-meta HKMetadataKeyHeartRateMotionContext=1 \
  --agg bin --bin 15min
```

Prior practice: peak effect ≈ 4–5 h post-dose, pre-dose baseline ≈ 45 min
before the dose, sedentary motion filter for a resting estimate. Run the same
query on a control day and compare medians/floors. Motion-context values:
`0`=notSet, `1`=sedentary, `2`=active.

### Resting heart-rate trend
```
untaped-apple-health query --type resting-heart-rate --from 2026-05-01 --agg bin --bin 1d
```

### Blood pressure over a period
```
untaped-apple-health query --type bp-systolic  --from 2026-06-08 --agg raw
untaped-apple-health query --type bp-diastolic --from 2026-06-08 --agg raw
```
Pair systolic/diastolic by timestamp. Readings are often **duplicated** in the
export (the same measurement logged twice, even from a single source) — dedup by
`(start, value)` before counting or averaging. ACC/AHA reference ranges — a label
for discussion, **not a diagnosis**: normal `<120/80`; elevated `120–129 / <80`;
stage 1 `130–139 or 80–89`; stage 2 `≥140 or ≥90`; crisis `≥180 or ≥120` (seek
care). Always present these as ranges to discuss with a clinician.

### Sleep last night
A night crosses midnight, so pull a **two-day** window and pick the contiguous
evening→morning block. `--from yesterday` alone catches the tail of the night
*before* last plus the start of last night — two partial nights:
```
untaped-apple-health query --type sleep --from 2026-06-12 --to 2026-06-13 --agg raw
```
Sleep is a category metric: the stage is in `value_text`, with each segment's
`start`/`end` giving its span. **The segments overlap** — `…SleepAnalysisInBed`
is an envelope that *contains* the `…AsleepDeep` / `…AsleepCore` / `…AsleepREM`
stages — so totalling stages naively double-counts. Instead:

- **Time asleep** = total of `AsleepDeep` + `AsleepCore` + `AsleepREM` only.
  Never add `InBed` (it brackets the asleep time) or `Awake`. Those asleep
  stages are contiguous, so summing their durations works; if any overlap
  (e.g. two sources logging the same night), union the intervals instead.
- **Time in bed** = the `InBed` segments (or the night's first start → last end).

A full night should land in a believable range (≈7–9 h is typical); a
double-digit "asleep" total is the tell that two nights or the `InBed` envelope
slipped in.

## Piping into another untaped tool (`--format pipe`)

`--format pipe` emits the self-describing NDJSON interchange stream — one
`{"untaped": "1", "kind": "...", "record": {...}}` envelope per row — for piping
into another untaped tool rather than for you to read directly. Each command
tags its records with a namespaced `kind` hint:

- `metrics` → `health.metric` (with `--type`, the per-source drill-in → `health.metric-source`)
- `query`   → `health.record`
- `status`  → `health.status`

```
untaped-apple-health query --type heart-rate --agg bin --bin 1d --format pipe \
  | untaped-<some-consumer>
```

When you just want to read or analyze results yourself, stay on JSON (the
`query` default) — `pipe` is for machine-to-machine handoff.

## Caveats

- Never present any reading or category as a diagnosis. These are reference
  labels and device measurements to discuss with a clinician.
- The database is a local mirror; re-run `sync` after the user re-exports.
