"""Focused errors for retrieval and deterministic evidence review."""


class EvidenceError(Exception):
    """Base class for expected Phase 7 failures."""


class EvidenceInputError(EvidenceError):
    """Candidate or compiled-note input violates its contract."""


class RetrievalConfigurationError(EvidenceError):
    """Retrieval configuration is invalid."""


class EmbeddingProviderError(EvidenceError):
    """A local embedding provider could not load or encode safely."""


class RetrievalContractError(EvidenceError):
    """A sparse, dense, fused, or recall result violates its contract."""


class EvidenceGateError(EvidenceError):
    """A candidate-note pair cannot be assessed consistently."""


class EvidenceDecisionError(EvidenceError):
    """Assessments cannot be reconciled into one valid decision."""
