"""Focused exceptions for generated reporting artifacts."""


class ReportingError(Exception):
    """Base class for expected reporting failures."""


class OutputContractError(ReportingError):
    """A candidate output or serialized CSV violates its contract."""


class CompiledNotesSerializationError(ReportingError):
    """A compiled-note JSONL artifact violates its serialization contract."""


class EvidenceAuditError(ReportingError):
    """The evidence audit JSONL violates its contract."""


class EvidenceOutputContractError(ReportingError):
    """The evidence-reviewed CSV violates its contract."""
