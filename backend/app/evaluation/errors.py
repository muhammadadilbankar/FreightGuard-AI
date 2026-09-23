"""Focused evaluation failures."""


class EvaluationError(Exception):
    """Base evaluation failure."""


class EvaluationConfigurationError(EvaluationError):
    pass


class FixtureContractError(EvaluationError):
    pass


class EvaluationExecutionError(EvaluationError):
    pass


class ReproducibilityError(EvaluationError):
    pass


class ArtifactValidationError(EvaluationError):
    pass


class ReportGenerationError(EvaluationError):
    pass
