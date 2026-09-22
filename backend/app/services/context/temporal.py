"""Inclusive effective-interval compilation with explicit rule precedence."""

import calendar
from datetime import date, timedelta
import re

from ...domain.context_notes import EffectiveInterval, TemporalBasis
from .errors import TemporalCompilationError

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH_TOKEN = "|".join(sorted(_MONTHS, key=len, reverse=True))
_EXPLICIT_RANGE = re.compile(
    rf"\bfrom\s+({_MONTH_TOKEN})\.?\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?"
    rf"\s+(?:to|through)\s+({_MONTH_TOKEN})\.?\s+(\d{{1,2}})"
    rf"(?:,?\s+(\d{{4}}))?\b",
    re.IGNORECASE,
)
_APPROXIMATE_WEEK = re.compile(
    r"\bfor\s+(?:(?:about|approximately|roughly)\s+)?(?:a|one)\s+week\b",
    re.IGNORECASE,
)
_CALENDAR_QUARTER = re.compile(r"\bthis\s+quarter\b", re.IGNORECASE)
_CALENDAR_WEEK = re.compile(r"\b(?:festival\s+week|this\s+week)\b", re.IGNORECASE)
_OPEN_ENDED = re.compile(
    r"\b(?:starting\s+this\s+week|was\s+(?:introduced|commissioned))\b",
    re.IGNORECASE,
)
_STATE_AFTER_COMPLETION = re.compile(
    r"\b(?:returned\s+to\s+normal|after\b.{0,100}\b(?:was\s+)?completed)\b",
    re.IGNORECASE,
)
_TEMPORAL_HINT = re.compile(
    r"\b(?:week|weeks|month|months|quarter|until|since|from|through)\b",
    re.IGNORECASE,
)


def resolve_effective_interval(
    source_date: date, original_text: str
) -> EffectiveInterval:
    """Resolve a supported interval using most-specific-first rules."""
    if not isinstance(source_date, date):
        raise TemporalCompilationError("source_date must be a date.")
    if not isinstance(original_text, str) or not original_text.strip():
        raise TemporalCompilationError("original_text must contain non-blank text.")

    explicit = _EXPLICIT_RANGE.search(original_text)
    if explicit:
        start, end = _parse_explicit_range(source_date, explicit)
        return EffectiveInterval(
            effective_from=start,
            effective_to=end,
            temporal_basis=TemporalBasis.EXPLICIT_RANGE,
        )

    if _APPROXIMATE_WEEK.search(original_text):
        return EffectiveInterval(
            effective_from=source_date,
            effective_to=source_date + timedelta(days=6),
            temporal_basis=TemporalBasis.APPROXIMATE_WEEK,
        )

    if _CALENDAR_QUARTER.search(original_text):
        quarter_start_month = ((source_date.month - 1) // 3) * 3 + 1
        quarter_end_month = quarter_start_month + 2
        quarter_end_day = calendar.monthrange(
            source_date.year, quarter_end_month
        )[1]
        return EffectiveInterval(
            effective_from=date(source_date.year, quarter_start_month, 1),
            effective_to=date(
                source_date.year, quarter_end_month, quarter_end_day
            ),
            temporal_basis=TemporalBasis.CALENDAR_QUARTER,
        )

    # "Starting this week" is a continuing state, not a bounded calendar week.
    if _OPEN_ENDED.search(original_text):
        return EffectiveInterval(
            effective_from=source_date,
            effective_to=None,
            temporal_basis=TemporalBasis.OPEN_ENDED_START,
        )

    if _CALENDAR_WEEK.search(original_text):
        week_start = source_date - timedelta(days=source_date.weekday())
        return EffectiveInterval(
            effective_from=week_start,
            effective_to=week_start + timedelta(days=6),
            temporal_basis=TemporalBasis.CALENDAR_WEEK,
        )

    if _STATE_AFTER_COMPLETION.search(original_text):
        return EffectiveInterval(
            effective_from=source_date,
            effective_to=None,
            temporal_basis=TemporalBasis.STATE_AFTER_COMPLETION,
        )

    warnings = {"temporal_scope_defaulted_to_source_date"}
    if _TEMPORAL_HINT.search(original_text):
        warnings.add("temporal_phrase_ambiguous")
    return EffectiveInterval(
        effective_from=source_date,
        effective_to=source_date,
        temporal_basis=TemporalBasis.SOURCE_DATE_FALLBACK,
        warnings=tuple(sorted(warnings)),
    )


def _parse_explicit_range(
    source_date: date, match: re.Match[str]
) -> tuple[date, date]:
    start_month = _MONTHS[match.group(1).casefold()]
    start_day = int(match.group(2))
    start_year = int(match.group(3)) if match.group(3) else source_date.year
    end_month = _MONTHS[match.group(4).casefold()]
    end_day = int(match.group(5))
    end_year = int(match.group(6)) if match.group(6) else start_year
    if match.group(6) is None and (end_month, end_day) < (start_month, start_day):
        if start_month >= 10 and end_month <= 3:
            end_year += 1
        else:
            raise TemporalCompilationError(
                "Explicit effective interval ends before it starts."
            )
    try:
        start = date(start_year, start_month, start_day)
        end = date(end_year, end_month, end_day)
    except ValueError as exc:
        raise TemporalCompilationError(
            "Explicit effective interval contains an impossible date."
        ) from exc
    if end < start:
        raise TemporalCompilationError(
            "Explicit effective interval ends before it starts."
        )
    return start, end
