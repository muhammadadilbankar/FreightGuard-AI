"""Focused exceptions for grounded explanation generation."""

from ...domain.explanations import ExplanationFailureCode


class ExplanationError(Exception):
    """Base class for expected Phase 8 failures."""


class ExplanationInputError(ExplanationError):
    """An authoritative Phase 7 packet is inconsistent."""


class PromptConstructionError(ExplanationError):
    """A versioned prompt could not be built safely."""


class ProviderConfigurationError(ExplanationError):
    """Live provider configuration is missing or unsupported."""


class ProviderCallError(ExplanationError):
    """A normalized provider failure with retry metadata."""

    def __init__(
        self,
        code: ExplanationFailureCode,
        *,
        transient: bool,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.transient = transient


class ExplanationValidationError(ExplanationError):
    """A generated response violates grounding constraints."""


class ExplanationCacheError(ExplanationError):
    """The content-addressed cache is missing, corrupt, or inconsistent."""


class ExplanationReconciliationError(ExplanationError):
    """Final records cannot be reconciled with Phase 7 authority."""
