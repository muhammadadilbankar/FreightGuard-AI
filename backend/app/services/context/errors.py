"""Focused exceptions for deterministic context-note compilation."""


class ContextCompilationError(Exception):
    """Base class for expected context compilation failures."""


class ContextInputError(ContextCompilationError):
    """The Phase 2 note frame or route universe violates its contract."""


class ScopeCompilationError(ContextCompilationError):
    """Route scope cannot be represented safely."""


class TemporalCompilationError(ContextCompilationError):
    """A temporal phrase is invalid or impossible."""


class ImpactCompilationError(ContextCompilationError):
    """An impact claim cannot be represented consistently."""


class CompiledNoteContractError(ContextCompilationError):
    """A compiled note violates a cross-field invariant."""
