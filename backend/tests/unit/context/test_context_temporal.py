"""Tests for inclusive effective-interval rule precedence."""

from datetime import date

import pytest

from backend.app.domain.context_notes import TemporalBasis
from backend.app.services.context import (
    TemporalCompilationError,
    resolve_effective_interval,
)


@pytest.mark.parametrize(
    ("source", "text", "start", "end"),
    [
        (date(2025, 2, 1), "from Feb 4 to Feb 9", date(2025, 2, 4), date(2025, 2, 9)),
        (date(2025, 2, 1), "from February 24 through March 8", date(2025, 2, 24), date(2025, 3, 8)),
        (date(2025, 12, 1), "from Dec 29 to Jan 4", date(2025, 12, 29), date(2026, 1, 4)),
        (date(2024, 2, 1), "from Feb 28 to Feb 29", date(2024, 2, 28), date(2024, 2, 29)),
    ],
)
def test_explicit_ranges_are_inclusive(
    source: date, text: str, start: date, end: date
) -> None:
    result = resolve_effective_interval(source, text)

    assert result.effective_from == start
    assert result.effective_to == end
    assert result.temporal_basis == TemporalBasis.EXPLICIT_RANGE


@pytest.mark.parametrize(
    "text", ["from Feb 30 to Mar 2", "from Jun 10 to May 1", "from Dec 5, 2025 to Jan 2, 2025"]
)
def test_impossible_or_reversed_ranges_fail(text: str) -> None:
    with pytest.raises(TemporalCompilationError):
        resolve_effective_interval(date(2025, 1, 1), text)


def test_calendar_week_uses_containing_monday_and_sunday() -> None:
    result = resolve_effective_interval(
        date(2025, 1, 22), "The festival week increased demand."
    )

    assert result.effective_from == date(2025, 1, 20)
    assert result.effective_to == date(2025, 1, 26)
    assert result.temporal_basis == TemporalBasis.CALENDAR_WEEK


def test_approximate_week_takes_precedence_over_generic_week() -> None:
    result = resolve_effective_interval(
        date(2025, 1, 22), "Starting this week, delays lasted for about a week."
    )

    assert result.effective_from == date(2025, 1, 22)
    assert result.effective_to == date(2025, 1, 28)
    assert result.temporal_basis == TemporalBasis.APPROXIMATE_WEEK


@pytest.mark.parametrize(
    ("source", "start", "end"),
    [
        (date(2025, 2, 10), date(2025, 1, 1), date(2025, 3, 31)),
        (date(2025, 5, 10), date(2025, 4, 1), date(2025, 6, 30)),
        (date(2025, 8, 10), date(2025, 7, 1), date(2025, 9, 30)),
        (date(2025, 11, 10), date(2025, 10, 1), date(2025, 12, 31)),
    ],
)
def test_calendar_quarters(source: date, start: date, end: date) -> None:
    result = resolve_effective_interval(source, "Stable this quarter.")

    assert (result.effective_from, result.effective_to) == (start, end)
    assert result.temporal_basis == TemporalBasis.CALENDAR_QUARTER


@pytest.mark.parametrize(
    ("text", "basis"),
    [
        ("Prices rose starting this week.", TemporalBasis.OPEN_ENDED_START),
        ("A toll plaza was commissioned.", TemporalBasis.OPEN_ENDED_START),
        ("A mandate was introduced.", TemporalBasis.OPEN_ENDED_START),
        ("The route returned to normal.", TemporalBasis.STATE_AFTER_COMPLETION),
        ("Conditions improved after work was completed.", TemporalBasis.STATE_AFTER_COMPLETION),
    ],
)
def test_open_ended_state_rules(text: str, basis: TemporalBasis) -> None:
    source = date(2025, 3, 17)
    result = resolve_effective_interval(source, text)

    assert result.effective_from == source
    assert result.effective_to is None
    assert result.temporal_basis == basis


def test_conservative_fallback_is_one_day_and_warned() -> None:
    source = date(2025, 4, 3)
    result = resolve_effective_interval(source, "An event occurred locally.")

    assert result.effective_from == result.effective_to == source
    assert result.temporal_basis == TemporalBasis.SOURCE_DATE_FALLBACK
    assert result.warnings == ("temporal_scope_defaulted_to_source_date",)


def test_unsupported_temporal_phrase_is_flagged_as_ambiguous() -> None:
    result = resolve_effective_interval(
        date(2025, 4, 3), "Conditions may persist for the next few weeks."
    )

    assert result.temporal_basis == TemporalBasis.SOURCE_DATE_FALLBACK
    assert result.warnings == (
        "temporal_phrase_ambiguous",
        "temporal_scope_defaulted_to_source_date",
    )
