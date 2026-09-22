"""Focused exceptions for deterministic analytics failures."""


class AnalyticsError(Exception):
    """Base class for expected weekly analytics failures."""


class AnalyticsInputError(AnalyticsError):
    """The normalized shipment frame violates the analytics input contract."""


class AnalyticsInvariantError(AnalyticsError):
    """An internal aggregation or reconciliation invariant failed."""


class CandidateDetectionError(AnalyticsError):
    """A percentage comparison or candidate-rule contract was violated."""
