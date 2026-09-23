"""Shared route declarations and date policy."""

from datetime import date

from ..schemas import ErrorResponse
from ...state.errors import InvalidQueryError

ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Not found"},
    409: {"model": ErrorResponse, "description": "Run already in progress"},
    422: {"model": ErrorResponse, "description": "Invalid request"},
    500: {"model": ErrorResponse, "description": "Run failed"},
    503: {"model": ErrorResponse, "description": "Analysis unavailable"},
}


def validate_weeks(week_from: date | None, week_to: date | None) -> None:
    if week_from:
        validate_monday(week_from)
    if week_to:
        validate_monday(week_to)
    if week_from and week_to and week_from > week_to:
        raise InvalidQueryError("week_from must be on or before week_to.")


def validate_monday(value: date) -> None:
    if value.weekday() != 0:
        raise InvalidQueryError("Week dates must be Mondays.")
