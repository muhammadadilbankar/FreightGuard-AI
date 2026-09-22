"""Focused exceptions for generated reporting artifacts."""


class ReportingError(Exception):
    """Base class for expected reporting failures."""


class OutputContractError(ReportingError):
    """A candidate output or serialized CSV violates its contract."""
