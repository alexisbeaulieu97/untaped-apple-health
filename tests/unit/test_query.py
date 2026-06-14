"""The bin-size parser shared by the query builder and the database."""

from __future__ import annotations

import pytest

from untaped_apple_health.domain.query import bin_size_minutes


def test_parses_minutes_hours_days() -> None:
    assert bin_size_minutes("15min") == 15
    assert bin_size_minutes("1h") == 60
    assert bin_size_minutes("1d") == 1440


@pytest.mark.parametrize("bad", ["5xyz", "", "min", "1w", "1.5h", "h1"])
def test_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError):
        bin_size_minutes(bad)


def test_rejects_zero() -> None:
    with pytest.raises(ValueError, match="positive"):
        bin_size_minutes("0min")


def test_rejects_multi_day() -> None:
    with pytest.raises(ValueError, match="up to 1d"):
        bin_size_minutes("2d")
