"""Date and clock parsing helpers (ported from the original script)."""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest

from untaped_apple_health.domain.timeparse import parse_clock, resolve_date


def test_resolve_date_parses_iso() -> None:
    assert resolve_date("2026-06-12") == date(2026, 6, 12)


def test_resolve_date_today_for_none() -> None:
    assert resolve_date(None) == date.today()


def test_resolve_date_today_keyword() -> None:
    assert resolve_date("today") == date.today()


def test_resolve_date_yesterday_keyword() -> None:
    assert resolve_date("yesterday") == date.today() - timedelta(days=1)


def test_resolve_date_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        resolve_date("not-a-date")


def test_parse_clock_returns_time() -> None:
    assert parse_clock("07:30") == time(7, 30)


def test_parse_clock_midnight() -> None:
    assert parse_clock("00:00") == time(0, 0)
