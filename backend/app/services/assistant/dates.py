"""Bounded, timezone-free natural-language date parsing."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from ...domain.assistant import ClarificationOption, ClarificationRequest

MONTHS = {name.casefold(): index for index, name in enumerate(calendar.month_name) if name}


@dataclass(frozen=True, slots=True)
class DateResolution:
    week_of: date | None = None
    week_from: date | None = None
    week_to: date | None = None
    clarification: ClarificationRequest | None = None
    invalid: str | None = None


def resolve_dates(question: str, available_dates: tuple[date, ...]) -> DateResolution:
    explicit_range = re.search(
        r"(?:from|between)\s+(\d{4}-\d{2}-\d{2})\s+(?:to|and)\s+"
        r"(\d{4}-\d{2}-\d{2})",
        question,
    )
    if explicit_range:
        try:
            start = date.fromisoformat(explicit_range.group(1))
            end = date.fromisoformat(explicit_range.group(2))
        except ValueError:
            return DateResolution(invalid="The supplied date range is invalid.")
        if start > end:
            return DateResolution(invalid="The start date must not follow the end date.")
        return DateResolution(week_from=start, week_to=end)

    exact = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", question)
    if exact:
        try:
            value = date.fromisoformat(exact.group(1))
        except ValueError:
            return DateResolution(invalid="The supplied date is invalid.")
        if value.weekday() != 0:
            return DateResolution(
                clarification=ClarificationRequest(
                    question="Candidate dates must be Mondays. Which analyzed week do you mean?"
                )
            )
        return DateResolution(week_of=value, week_from=value, week_to=value)

    between = re.search(
        r"between\s+([a-z]+)\s+(\d{4})\s+and\s+([a-z]+)\s+(\d{4})",
        question,
    )
    if between:
        left = _month_bounds(between.group(1), int(between.group(2)))
        right = _month_bounds(between.group(3), int(between.group(4)))
        if left is None or right is None:
            return DateResolution(invalid="The requested month is not supported.")
        return DateResolution(week_from=left[0], week_to=right[1])

    year_only = re.search(r"\b(?:in\s+)?(20\d{2})\b", question)
    month_match = re.search(
        r"\b(" + "|".join(MONTHS) + r")\b(?:\s+(20\d{2}))?",
        question,
    )
    if month_match:
        month_name = month_match.group(1)
        explicit_year = month_match.group(2)
        if explicit_year:
            bounds = _month_bounds(month_name, int(explicit_year))
            assert bounds is not None
            if "after " + month_name in question:
                return DateResolution(week_from=_next_day(bounds[1]))
            if "before " + month_name in question:
                return DateResolution(week_to=_previous_day(bounds[0]))
            return DateResolution(week_from=bounds[0], week_to=bounds[1])
        years = sorted({value.year for value in available_dates if value.month == MONTHS[month_name]})
        if len(years) > 1:
            return DateResolution(
                clarification=ClarificationRequest(
                    question=f"I found data in more than one {month_name.title()}. Which period do you mean?",
                    options=tuple(
                        ClarificationOption(
                            option_id=f"{month_name}-{year}",
                            label=f"{month_name.title()} {year}",
                            value=f"{month_name.title()} {year}",
                        )
                        for year in years[:5]
                    ),
                )
            )
        if len(years) == 1:
            bounds = _month_bounds(month_name, years[0])
            assert bounds is not None
            return DateResolution(week_from=bounds[0], week_to=bounds[1])
        return DateResolution(invalid="No snapshot data matches that month.")
    if year_only:
        year = int(year_only.group(1))
        return DateResolution(week_from=date(year, 1, 1), week_to=date(year, 12, 31))
    return DateResolution()


def _month_bounds(name: str, year: int) -> tuple[date, date] | None:
    month = MONTHS.get(name.casefold())
    if month is None:
        return None
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _next_day(value: date) -> date:
    return date.fromordinal(value.toordinal() + 1)


def _previous_day(value: date) -> date:
    return date.fromordinal(value.toordinal() - 1)
